"""Capture health — make silent zero-capture loud (docs/capture-health).

When an agent is installed but its log source matched nothing, `cage
doctor` say so instead of printing confident totals from the agents that still work.
The warning is triple-gated so it can never become a false-positive nag: it fires for
an agent only when **home exists AND 0 files matched AND the agent has never captured
a row**. Clause 3 makes it self-silencing.

The gate logic (`doctorcmd.capture_warnings`) is a pure function of the recorded
`_health`, so most gates are asserted directly on it; the recording path
(`importcmd.run` → `cursors.json["_health"]`) is asserted end-to-end for the traps
(copilot two-source, kiro file-source, disabled-by-policy, self-heal, cleanup, fail-open).
"""
from __future__ import annotations

import json
from types import SimpleNamespace

# Recorded history: `ledger.spend` supersedes a post-cutover `calls` row for the
# three metric-ledger agents, so an unstamped (now()) fixture row would vanish.
LEDGER_TS = "2026-06-01T12:00:00Z"

from conftest import metric_twin
from cage import (agents, cleanup, doctorcmd, importcmd, ledger, paths, policy,
                  schema)
from srcseed import mkcage

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch):
    """Point every agent home at a throwaway dir (hermetic capture) and return the
    project root with a `.cage/`."""
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / "proj"
    mkcage(root)
    monkeypatch.chdir(root)
    return root


def _imp(root, agent="all"):
    return importcmd.run(root, agent,
                         SimpleNamespace(agent=agent, path=None, project=None, since=None))


def _health(root):
    return importcmd.capture_health(root)


def _copilot_log(root):
    """Plant one copilot CLI session so its source matches a file (glob `*/events.jsonl`)
    and actually parses to a row (`transcript.parse_copilot_calls`)."""
    d = paths.copilot_home() / "session-state" / "sid"
    d.mkdir(parents=True, exist_ok=True)
    line = json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T10:00:00Z",
                       "data": {"modelMetrics": {"claude-sonnet-4-6": {
                           "usage": {"input_tokens": 100, "output_tokens": 40}}}}})
    (d / "events.jsonl").write_text(line + "\n", encoding="utf-8")


# ── the triple gate, asserted purely on doctorcmd.capture_warnings ────────────────

def _rec(home=True, files=0, captured=False):
    return {"home": home, "home_path": "~/.copilot", "src": "~/.copilot/session-state",
            "files": files, "captured": captured}


def test_all_three_true_yields_exactly_one_warning():
    warns = doctorcmd.capture_warnings({"copilot": _rec()})
    assert len(warns) == 1
    assert "⚠ copilot: ~/.copilot exists but ~/.copilot/session-state matched 0 files" in warns[0]
    assert "cage doctor --paths" in warns[0]                         # runnable fix
    assert "[sources.copilot] replace=true, paths=[]" in warns[0]    # documented opt-out


def test_gate1_home_absent_suppresses():
    assert doctorcmd.capture_warnings({"copilot": _rec(home=False)}) == []


def test_gate2_files_found_suppresses():
    assert doctorcmd.capture_warnings({"copilot": _rec(files=3)}) == []


def test_gate3_captured_suppresses():
    assert doctorcmd.capture_warnings({"copilot": _rec(captured=True)}) == []


def test_no_health_record_is_silent():
    assert doctorcmd.capture_warnings(None) == []
    assert doctorcmd.capture_warnings({}) == []


def test_warnings_are_in_surfaces_order():
    recs = {a: _rec() for a in reversed(agents.SURFACES)}
    for a, r in recs.items():
        r["home_path"], r["src"] = f"~/.{a}", f"~/.{a}/x"
    warns = doctorcmd.capture_warnings(recs)
    named = [w.split(":")[0].removeprefix("⚠ ").strip() for w in warns]
    assert named == list(agents.SURFACES)  # rendered in SURFACES order regardless of input


# ── recording path: importcmd.run → cursors.json["_health"] ────────────────────

def test_installed_but_empty_agent_records_a_gated_record(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)            # copilot installed, no sessions
    _imp(root)
    rec = _health(root)["copilot"]
    assert rec["home"] is True and rec["files"] == 0 and rec["captured"] is False
    assert doctorcmd.capture_warnings(_health(root))       # → warns


def test_self_silencing_a_prior_row_clears_the_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)            # installed, still no sessions
    # a copilot row already in the ledger (captured in some earlier run) ⇒ gate 3 fails
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="r", provider="anthropic", model="claude-sonnet-4-6",
                                   agent="copilot", tokens_in=10, session="s",
                                   ts=LEDGER_TS))
    _imp(root)
    assert _health(root)["copilot"]["captured"] is True
    assert doctorcmd.capture_warnings(_health(root)) == []  # never nags an agent with rows


def test_first_ever_import_marks_the_agent_captured_same_run(tmp_path, monkeypatch):
    # F2 regression (work/regression/2026-07-22-capture-report.md): the VERY FIRST import
    # of an agent must record `captured=True` in the SAME run. The run-shared `captured`
    # set is snapshotted from the ledger *before* this run's appends, so a brand-new
    # surface isn't in it yet — before the fix it read `captured=False` until a *second*
    # import, leaving `cage doctor` claiming an agent wasn't capturing while its
    # freshly-imported rows already sat in the ledger. `imported > 0` closes the off-by-one.
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)
    _copilot_log(root)                                   # a real copilot log, empty ledger
    _imp(root)                                           # copilot's first-ever capture
    rec = _health(root)["copilot"]
    assert rec["files"] > 0 and rec["captured"] is True  # captured in THIS run, not the next
    assert doctorcmd.capture_warnings(_health(root)) == []  # so doctor/report never nag


def test_self_healing_files_reappear_clears_the_warning(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)
    _imp(root)
    assert doctorcmd.capture_warnings(_health(root))        # warns: 0 files
    _copilot_log(root)                                   # fix the path (plant a log)
    _imp(root)
    assert _health(root)["copilot"]["files"] > 0
    assert doctorcmd.capture_warnings(_health(root)) == []  # cleared, no other action


def test_disabled_by_policy_is_silent(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)            # installed…
    # …but NOT declared in [sources] (Directive A, §3.6): an agent with no
    # [sources.<agent>] entry is simply never swept — the new way to "disable" a surface,
    # replacing the old `replace = true` + empty `paths`. Declare claude only.
    (root / ".cage" / "cage.toml").write_text(
        '[[sources.claude]]\npath = "$CLAUDE_CONFIG_DIR/projects"\nglob = "**/*.jsonl"\n',
        encoding="utf-8")
    _imp(root)
    assert "copilot" not in _health(root)                # no source ⇒ never swept ⇒ no warn
    assert doctorcmd.capture_warnings(_health(root)) == []


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
    assert doctorcmd.capture_warnings(_health(root)) == []  # silent despite no VS Code dir


def test_kiro_present_but_empty_is_silent_not_broken(tmp_path, monkeypatch):
    # Kiro is a FILE source: `_scan` takes raw=[src] when the file exists, so len(raw)=1
    # even for an empty log. Gate 2 means "no data location", not "no rows" — a
    # present-but-empty kiro log is normal (coarse by design), never a "broken" nag.
    # Since ADR-LEDGER (2026-08-15) kiro's health rides THIS run's own active ledger,
    # like every other agent — no separate machine sink to record it against.
    root = _isolate(tmp_path, monkeypatch)
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True)
    log.write_text("", encoding="utf-8")                # the file exists but is empty
    _imp(root)
    gh = _health(root)
    assert gh["kiro"]["files"] == 1                      # the file counts as matched
    assert doctorcmd.capture_warnings(gh) == []             # so kiro never warns


def test_stale_pre_reversal_kiro_health_is_refreshed_not_left_dangling(tmp_path, monkeypatch):
    # Before ADR-LEDGER, a routed-away kiro left no health record in the project (it
    # captured elsewhere) — a stale record from that era, if present, had to be dropped
    # or it would nag "installed but matched 0 files" forever. Since ADR-LEDGER, kiro
    # captures HERE every run, so a stale record is simply overwritten with a fresh,
    # accurate one — the same as any other agent's health always was.
    root = _isolate(tmp_path, monkeypatch)
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True)
    log.write_text("", encoding="utf-8")
    # a stale record from before ADR-LEDGER (kiro was routed away, so this project
    # never saw a real capture and the record was left saying so)
    foot = paths.Footprint(root)
    foot.state.mkdir(parents=True, exist_ok=True)
    foot.cursors.write_text(json.dumps({"_health": {"kiro": {"home": True, "files": 0,
                                                            "captured": False}},
                                        "kiro": {"/some/log": [1, 2.0]}}), encoding="utf-8")
    _imp(root)
    cur = json.loads(foot.cursors.read_text(encoding="utf-8"))
    assert cur["_health"]["kiro"]["files"] == 1           # refreshed by THIS run's real scan
    assert doctorcmd.capture_warnings(_health(root)) == []


def test_single_agent_import_does_not_erase_other_agents_health(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)
    paths.claude_home().mkdir(parents=True)
    _imp(root, "all")
    assert {"copilot", "claude"} <= set(_health(root))
    _imp(root, "copilot")                               # a single-agent sweep
    assert {"copilot", "claude"} <= set(_health(root))  # claude's record survives


# ── cleanup, fail-open ─────────────────────────────────────────────────────────

def test_health_survives_cursor_cleanup(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)
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
    orphan = str(tmp_path / "gone-abs" / "events.jsonl")  # absolute on all OSes, absent
    foot = paths.Footprint(root)
    cur = json.loads(foot.cursors.read_text(encoding="utf-8"))
    cur.setdefault("copilot", {})[orphan] = [1, 2.0]
    foot.cursors.write_text(json.dumps(cur), encoding="utf-8")
    pol = policy.load(None)
    counts = cleanup.prune(root, pol, days=0)
    assert counts.get("cursor-orphan")                  # the rewrite really ran
    after = json.loads(foot.cursors.read_text(encoding="utf-8"))
    assert orphan not in after.get("copilot", {})       # orphan dropped
    assert _health(root) == before                      # …but `_health` is untouched


def test_health_write_failure_does_not_break_import(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    paths.copilot_home().mkdir(parents=True)
    monkeypatch.setattr(importcmd, "_home_markers",
                        lambda a: (_ for _ in ()).throw(RuntimeError("boom")))
    lines = _imp(root)                                  # must not raise
    assert any("copilot" in l for l in lines)           # import still produced its output
    assert _health(root).get("copilot") is None         # health just wasn't recorded


# ── purity, table byte-identity, CSV cleanliness ──────────────────────────────

# ── The RENDER-side assertions went with `cage report` (SURFACE-CUT, 2026-08-14) ──
# Three tests here pinned `report.render_report`: that it is pure of the filesystem,
# that the table block is byte-identical with and without a warning, and that `--csv`
# never carries the ⚠. All three were properties of the deleted report renderer.
# **The gate itself is still fully tested above** — `doctorcmd.capture_warnings` is a
# pure function of the passed `_health` record, and every clause of the triple gate has
# its own case. `cage doctor` is now the sole renderer of these warnings.
