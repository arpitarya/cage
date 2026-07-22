"""Capture health — make silent zero-capture loud (docs/capture-health).

When an agent is installed but its log source matched nothing, `cage report`/`cage
doctor` say so instead of printing confident totals from the agents that still work.
The warning is triple-gated so it can never become a false-positive nag: it fires for
an agent only when **home exists AND 0 files matched AND the agent has never captured
a row**. Clause 3 makes it self-silencing.

The gate logic (`report.capture_warnings`) is a pure function of the recorded
`_health`, so most gates are asserted directly on it; the recording path
(`importcmd.run` → `cursors.json["_health"]`) is asserted end-to-end for the traps
(copilot two-source, kiro file-source, disabled-by-policy, self-heal, cleanup, fail-open).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import (agents, cleanup, importcmd, ledger, paths, policy, report,
                  schema)

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch):
    """Point every agent home at a throwaway dir (hermetic capture) and return the
    project root with a `.cage/`."""
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    return root


def _imp(root, agent="all"):
    return importcmd.run(root, agent,
                         SimpleNamespace(agent=agent, path=None, project=None, since=None))


def _health(root):
    return importcmd.capture_health(root)


def _codex_log(root):
    """Plant one codex rollout so its source matches a file (glob `**/rollout-*.jsonl`)."""
    d = paths.codex_home() / "sessions" / "2026" / "06"
    d.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"timestamp": "2026-06-14T10:00:00Z", "type": "event_msg",
                       "payload": {"type": "token_count", "info": {
                           "total_token_usage": {"input_tokens": 100, "output_tokens": 40,
                                                 "cached_input_tokens": 0}},
                           "model": "gpt-5.3-codex"}})
    (d / "rollout-2026-06-14-x.jsonl").write_text(line + "\n", encoding="utf-8")


# ── the triple gate, asserted purely on report.capture_warnings ────────────────

def _rec(home=True, files=0, captured=False):
    return {"home": home, "home_path": "~/.codex", "src": "~/.codex/sessions",
            "files": files, "captured": captured}


def test_all_three_true_yields_exactly_one_warning():
    warns = report.capture_warnings({"codex": _rec()})
    assert len(warns) == 1
    assert "⚠ codex: ~/.codex exists but ~/.codex/sessions matched 0 files" in warns[0]
    assert "cage doctor --paths" in warns[0]                         # runnable fix
    assert "[sources.codex] replace=true, paths=[]" in warns[0]      # documented opt-out


def test_gate1_home_absent_suppresses():
    assert report.capture_warnings({"codex": _rec(home=False)}) == []


def test_gate2_files_found_suppresses():
    assert report.capture_warnings({"codex": _rec(files=3)}) == []


def test_gate3_captured_suppresses():
    assert report.capture_warnings({"codex": _rec(captured=True)}) == []


def test_no_health_record_is_silent():
    assert report.capture_warnings(None) == []
    assert report.capture_warnings({}) == []


def test_warnings_are_in_surfaces_order():
    recs = {a: _rec() for a in reversed(agents.SURFACES)}
    for a, r in recs.items():
        r["home_path"], r["src"] = f"~/.{a}", f"~/.{a}/x"
    warns = report.capture_warnings(recs)
    named = [w.split(":")[0].removeprefix("⚠ ").strip() for w in warns]
    assert named == list(agents.SURFACES)  # rendered in SURFACES order regardless of input


# ── recording path: importcmd.run → cursors.json["_health"] ────────────────────

def test_installed_but_empty_agent_records_a_gated_record(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)              # codex installed, no sessions
    _imp(root)
    rec = _health(root)["codex"]
    assert rec["home"] is True and rec["files"] == 0 and rec["captured"] is False
    assert report.capture_warnings(_health(root))       # → warns


def test_self_silencing_a_prior_row_clears_the_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)              # installed, still no sessions
    # a codex row already in the ledger (captured in some earlier run) ⇒ gate 3 fails
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="r", provider="openai", model="gpt-5.3-codex",
                                   agent="codex", tokens_in=10, session="s"))
    _imp(root)
    assert _health(root)["codex"]["captured"] is True
    assert report.capture_warnings(_health(root)) == []  # never nags an agent with rows


def test_first_ever_import_marks_the_agent_captured_same_run(tmp_path, monkeypatch):
    # F2 regression (docs/regression/2026-07-22-capture-report.md): the VERY FIRST import
    # of an agent must record `captured=True` in the SAME run. The run-shared `captured`
    # set is snapshotted from the ledger *before* this run's appends, so a brand-new
    # surface isn't in it yet — before the fix it read `captured=False` until a *second*
    # import, leaving `cage doctor` claiming an agent wasn't capturing while its
    # freshly-imported rows already sat in the ledger. `imported > 0` closes the off-by-one.
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _codex_log(root)                                     # a real codex log, empty ledger
    _imp(root)                                           # codex's first-ever capture
    rec = _health(root)["codex"]
    assert rec["files"] > 0 and rec["captured"] is True  # captured in THIS run, not the next
    assert report.capture_warnings(_health(root)) == []  # so doctor/report never nag


def test_self_healing_files_reappear_clears_the_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _imp(root)
    assert report.capture_warnings(_health(root))        # warns: 0 files
    _codex_log(root)                                     # fix the path (plant a log)
    _imp(root)
    assert _health(root)["codex"]["files"] > 0
    assert report.capture_warnings(_health(root)) == []  # cleared, no other action


def test_disabled_by_policy_is_silent(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)              # installed…
    (root / ".cage" / "policy.toml").write_text(       # …but disabled by policy
        "[sources.codex]\nreplace = true\npaths = []\n", encoding="utf-8")
    _imp(root)
    assert "codex" not in _health(root)                 # no record ⇒ no warn
    assert report.capture_warnings(_health(root)) == []


def test_copilot_cli_only_with_files_is_silent(tmp_path, monkeypatch):
    # The §8 trap: copilot has two sources (CLI + VS Code). A CLI-only user with CLI
    # files present must not be nagged for the absent VS Code store.
    root = _isolate(tmp_path, monkeypatch)
    sess = paths.copilot_home() / "session-state" / "sid"
    sess.mkdir(parents=True)
    (sess / "events.jsonl").write_text(json.dumps({"type": "session.shutdown",
        "usage": {"input_tokens": 50, "output_tokens": 10}, "model": "claude-sonnet-4-6"}) + "\n",
        encoding="utf-8")
    _imp(root)
    assert _health(root)["copilot"]["files"] > 0         # CLI source matched
    assert report.capture_warnings(_health(root)) == []  # silent despite no VS Code dir


def test_kiro_present_but_empty_is_silent_not_broken(tmp_path, monkeypatch):
    # Kiro is a FILE source: `_scan` takes raw=[src] when the file exists, so len(raw)=1
    # even for an empty log. Gate 2 means "no data location", not "no rows" — a
    # present-but-empty kiro log is normal (coarse by design), never a "broken" nag.
    root = _isolate(tmp_path, monkeypatch)
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True)
    log.write_text("", encoding="utf-8")                # the file exists but is empty
    _imp(root)
    assert _health(root)["kiro"]["files"] == 1           # the file counts as matched
    assert report.capture_warnings(_health(root)) == []  # so kiro never warns


def test_single_agent_import_does_not_erase_other_agents_health(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    paths.claude_home().mkdir(parents=True)
    _imp(root, "all")
    assert {"codex", "claude"} <= set(_health(root))
    _imp(root, "codex")                                 # a single-agent sweep
    assert {"codex", "claude"} <= set(_health(root))    # claude's record survives


# ── cleanup, fail-open ─────────────────────────────────────────────────────────

def test_health_survives_cursor_cleanup(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    _imp(root)
    before = _health(root)
    assert before
    # Inject an orphan cursor (absolute, non-existent) so the orphan-cursor prune
    # actually rewrites cursors.json — the pass that could clobber `_health`. Use an
    # OS-native absolute path (under tmp_path, never created) rather than a POSIX
    # "/gone/…": Python 3.13's ntpath.isabs no longer treats a single-slash path as
    # absolute on Windows, so a "/gone/…" cursor would slip past the orphan guard
    # (os.path.isabs) there and the prune would be a no-op (real cursors are drive-
    # absolute C:\…, so production is unaffected — this is test-data only).
    orphan = str(tmp_path / "gone-abs" / "rollout-x.jsonl")  # absolute on all OSes, absent
    foot = paths.Footprint(root)
    cur = json.loads(foot.cursors.read_text(encoding="utf-8"))
    cur.setdefault("codex", {})[orphan] = [1, 2.0]
    foot.cursors.write_text(json.dumps(cur), encoding="utf-8")
    pol = policy.load(None)
    counts = cleanup.prune(root, pol, days=0)
    assert counts.get("cursor-orphan")                  # the rewrite really ran
    after = json.loads(foot.cursors.read_text(encoding="utf-8"))
    assert orphan not in after.get("codex", {})         # orphan dropped
    assert _health(root) == before                      # …but `_health` is untouched


def test_health_write_failure_does_not_break_import(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.codex_home().mkdir(parents=True)
    monkeypatch.setattr(importcmd, "_home_markers",
                        lambda a: (_ for _ in ()).throw(RuntimeError("boom")))
    lines = _imp(root)                                  # must not raise
    assert any("codex" in l for l in lines)             # import still produced its output
    assert _health(root).get("codex") is None           # health just wasn't recorded


# ── purity, table byte-identity, CSV cleanliness ──────────────────────────────

def test_render_report_is_pure_of_the_filesystem(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="r", provider="anthropic",
                                   model="claude-sonnet-4-6", agent="claude",
                                   tokens_in=1000, tokens_out=100, session="s"))
    rep = report.summarize(root, policy.load(None), dim="agent")
    H = {"codex": _rec()}
    a = report.render_report(rep, health=H)
    # Deleting every home dir must not change the rendered output — render reads only `H`.
    for env in _HOME_ENVS:
        d = tmp_path / f"home-{env.lower()}"
        if d.exists():
            import shutil
            shutil.rmtree(d)
    b = report.render_report(rep, health=H)
    assert a == b and "⚠ codex" in a                     # identical, and the warning shows


def test_table_is_byte_identical_with_and_without_a_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="r", provider="anthropic",
                                   model="claude-sonnet-4-6", agent="claude",
                                   tokens_in=1000, tokens_out=100, session="s"))
    rep = report.summarize(root, policy.load(None), dim="agent")
    without = report.render_report(rep, health=None)
    withw = report.render_report(rep, health={"codex": _rec()})
    # The title + table block (everything before the footer) is untouched by the warning.
    assert without.split("\n\n")[:2] == withw.split("\n\n")[:2]
    assert "⚠ codex" in withw and "⚠ codex" not in without


def test_csv_never_carries_the_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="r", provider="anthropic",
                                   model="claude-sonnet-4-6", agent="claude",
                                   tokens_in=1000, tokens_out=100, session="s"))
    rep = report.summarize(root, policy.load(None), dim="agent")
    csv = report.render_csv(rep)                          # render_csv takes no health
    assert "⚠" not in csv and "capture is off" not in csv
