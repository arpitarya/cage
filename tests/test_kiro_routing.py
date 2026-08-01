"""Kiro capture routing — two stores, two opposite fixes (ADR 0006).

- **IDE** (`tokens_generated.jsonl`): one global file with no project/session/timestamp,
  so its rows are a *machine* fact and route to the machine ledger. One copy per machine
  ⇒ double-counting is impossible by construction.
- **CLI** (`conversations_v2` SQLite): keyed by the cwd it ran in, with a real
  conversation id — genuinely project-attributable, so it gets the opposite treatment:
  scoped to the project tree and stamped with `project`.

The load-bearing risk this file exists to pin is the *collateral*: `importcmd.run` was
built on "one active sink per run", and the IDE half deliberately breaks it. So the
claude/copilot legs are asserted **byte-identical**, and the sweep summary is asserted
never to count a row that landed in another ledger.
"""
from __future__ import annotations

import json
import sqlite3
from types import SimpleNamespace

from cage import importcmd, ledger, paths, report, transcript
from srcseed import mkcage

_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate(tmp_path, monkeypatch, name="proj"):
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    root = tmp_path / name
    mkcage(root)
    monkeypatch.chdir(root)
    return root


def _args(agent="all", **kw):
    return SimpleNamespace(agent=agent, path=None, project=None, since=None, **kw)


def _kiro_log(lines=2, start=100):
    log = paths.kiro_token_log()
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text("".join(
        json.dumps({"model": "agent", "provider": "kiro",
                    "promptTokens": start + i, "generatedTokens": 0}) + "\n"
        for i in range(lines)), encoding="utf-8")
    return log


def _claude_log(uuid="u1", tin=100, tout=20):
    d = paths.claude_home() / "projects" / "p"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{uuid}.jsonl").write_text(json.dumps({
        "type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
        "cwd": "/w/demo",
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": tin, "output_tokens": tout}}}) + "\n",
        encoding="utf-8")


def _shards(root):
    return b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))


# ── the resolver: one place the rule lives ────────────────────────────────────

def test_kiro_sink_is_the_machine_ledger_from_inside_a_project(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    assert paths.kiro_ledger(root) == paths.global_home()
    assert paths.kiro_routed(root) == paths.global_home()


def test_no_routing_when_the_machine_ledger_is_already_the_active_sink(tmp_path, monkeypatch):
    # No project ⇒ the sweep root IS the machine ledger ⇒ nothing to route, and (the
    # reason this matters) no second lock on a file this process already holds.
    monkeypatch.chdir(tmp_path)
    g = paths.global_home()
    assert paths.kiro_routed(g) is None


def test_explicit_ledger_override_always_wins(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_BASE", str(tmp_path / "lab" / ".cage"))
    assert paths.kiro_routed(root) is None      # cage never routes around a named sink
    assert paths.kiro_ledger(root) == root


def test_cage_ledger_dir_override_also_collapses_the_legs(tmp_path, monkeypatch):
    # CAGE_LEDGER re-points the ledger dir alone: both "sinks" are then the same files,
    # so there is nothing to route (compared on the resolved ledger dir, not the root).
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_LEDGER", str(tmp_path / "shared-ledger"))
    assert paths.kiro_routed(root) is None


# ── the routing itself ────────────────────────────────────────────────────────

def test_ide_rows_land_in_the_machine_ledger_not_the_project(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert ledger.calls(root) == []
    assert len(ledger.calls(paths.global_home())) == 2


def test_two_projects_one_machine_records_the_turn_exactly_once(tmp_path, monkeypatch):
    """The whole point of ADR 0006. Kiro's log is one global file, so before this the
    same turn landed in every ledger that ever imported it."""
    a = _isolate(tmp_path, monkeypatch, "a")
    _kiro_log(3)
    importcmd.run(a, "all", _args())
    b = _isolate(tmp_path, monkeypatch, "b")
    importcmd.run(b, "all", _args())
    machine = ledger.calls(paths.global_home())
    assert len(machine) == 3 and len({c["id"] for c in machine}) == 3
    assert ledger.calls(a) == [] and ledger.calls(b) == []


def test_reimport_is_idempotent_against_the_machine_ledger(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    before = _shards(paths.global_home())
    lines = importcmd.run(root, "all", _args())
    assert _shards(paths.global_home()) == before          # 0 new, byte-identical
    assert any("imported 0 call(s)" in l for l in lines if "kiro" in l)


def test_ledger_override_keeps_kiro_in_the_named_ledger(tmp_path, monkeypatch):
    # cage-lab's isolation depends on this: under --ledger, kiro does NOT escape.
    root = _isolate(tmp_path, monkeypatch)
    base = tmp_path / "lab" / ".cage"                      # the lab's own named store
    base.mkdir(parents=True)
    (base / "cage.toml").write_text(
        paths.Footprint(root).policy.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setenv("CAGE_BASE", str(base))
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert len(ledger.calls(root)) == 2                    # Footprint is re-based to `base`
    # The default machine ledger is never even created: under an override every Footprint
    # is re-based, so `ledger.calls(global_home())` would read `base` too — the honest
    # assertion is against the directory on disk.
    assert not (paths.global_home() / ".cage" / "ledger").exists()


# ── the hard constraint: the other two agents are untouched ───────────────────

def test_claude_and_copilot_capture_is_byte_identical(tmp_path, monkeypatch):
    """Asserted, not reasoned about. The same claude sweep is run twice — once with a
    kiro log present (so the routed leg fires) and once without — and the project
    ledger's rows must be identical either way. `import_id` is the per-sweep manifest FK
    (a fresh id per run, non-deterministic by nature, like `ts`) and is stripped, exactly
    as the fixture corpus does."""
    def sweep(name, with_kiro):
        root = _isolate(tmp_path, monkeypatch, name)
        _claude_log()
        if with_kiro:
            _kiro_log(2)
        importcmd.run(root, "all", _args())
        rows = ledger.calls(root)
        assert rows, "the claude leg must actually capture, or this proves nothing"
        return [{k: v for k, v in r.items() if k != "import_id"} for r in rows]

    assert sweep("no-kiro", False) == sweep("with-kiro", True)


def test_the_project_ledger_never_gains_a_kiro_row(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    _claude_log()
    _kiro_log(4)
    importcmd.run(root, "all", _args())
    assert {c["agent"] for c in ledger.calls(root)} == {"claude-code"}


# ── the summary line never counts cross-ledger rows ───────────────────────────

def test_summary_never_counts_rows_that_landed_elsewhere(tmp_path, monkeypatch):
    """Two guarantees in one: the per-agent kiro line NAMES its sink, and the rollup
    table (which reads this sweep's appended rows) totals only the local ones."""
    root = _isolate(tmp_path, monkeypatch)
    _claude_log(tin=100, tout=20)
    _kiro_log(2, start=1000)                # 1000 + 1001 tokens, all routed away
    lines = importcmd.run(root, "all", _args())
    text = "\n".join(lines)
    kiro_line = next(l for l in lines if l.startswith("✔ kiro"))
    assert str(paths.Footprint(paths.global_home()).base) in kiro_line
    assert "machine ledger" in kiro_line
    total = next(l for l in lines if l.strip().startswith("total"))
    assert "100" in total and "1,000" not in total and "2,001" not in total
    assert "kiro" not in text.split("agent    surface")[-1]  # not a rollup bucket either


def test_capture_on_read_summary_counts_only_local_rows(tmp_path, monkeypatch):
    # The read-side twin: `· captured N new` must not announce rows a project report
    # will never show.
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")
    _kiro_log(3)
    summary = importcmd.ensure_captured(root, _args(no_import=False))
    assert summary is None                                  # nothing landed HERE
    assert len(ledger.calls(paths.global_home())) == 3       # but kiro was captured


# ── the capture switches compose as AND ───────────────────────────────────────

def test_machine_ledger_capture_switch_can_veto_the_routed_leg(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    g = paths.Footprint(paths.global_home())
    g.base.mkdir(parents=True, exist_ok=True)
    g.policy.write_text("[capture]\nenabled = false\n", encoding="utf-8")
    _kiro_log(2)
    lines = importcmd.run(root, "all", _args())
    assert ledger.calls(paths.global_home()) == []
    assert any("disabled at the machine ledger" in l for l in lines)  # never silent


def test_project_capture_switch_still_pauses_everything(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    _kiro_log(2)
    importcmd.run(root, "all", _args())
    assert ledger.calls(paths.global_home()) == []


# ── the read side explains the absence ────────────────────────────────────────

def test_project_report_explains_kiros_absence(tmp_path, monkeypatch):
    from cage import policy
    root = _isolate(tmp_path, monkeypatch)
    pol = policy.load(paths.Footprint(root).policy)
    line = report.kiro_routed_line(root, pol)
    assert str(paths.Footprint(paths.global_home()).base) in line
    assert "cage query kiro-routing" in line


def test_machine_ledger_report_has_nothing_to_explain(tmp_path, monkeypatch):
    from cage import policy
    monkeypatch.chdir(tmp_path)
    g = paths.global_home()
    assert report.kiro_routed_line(g, policy.load(None)) == ""


# ── K3/K4: the two HONEST-LIMITs, pinned so they can't regress silently ───────

def _rep(**kw):
    base = {"dim": "agent", "since": None, "groups": {}, "kiro_rows": 0}
    base.update(kw)
    return base


def test_k3_kiro_limit_states_no_time_session_or_project():
    """K3 (finding: kiro rows carry no time/session/project). Fires on ANY kiro row —
    a wider gate than the input-only caveat, because the limit holds even if kiro one
    day reports output tokens."""
    line = report._kiro_limits_caveat(_rep(kiro_rows=3), usd=False)
    assert "no per-turn time, session or project" in line
    assert report._kiro_limits_caveat(_rep(kiro_rows=0), usd=False) == ""


def test_k3_composes_with_the_input_only_caveat_without_repeating_it():
    both = report._kiro_limits_caveat(_rep(kiro_rows=3, kiro_input_only=True), usd=True)
    assert "input-only log — cost understated" in both and "also carry" in both
    assert both.count("kiro:") == 1


def test_k3_names_the_since_window_as_the_reading_that_would_be_wrong():
    """The `ts` is stamped at IMPORT, so a window includes/excludes kiro rows by when
    the import ran — not coarse, *wrong*. It gets its own ⚠."""
    windowed = report._kiro_limits_caveat(_rep(kiro_rows=3, since="7d"), usd=False)
    assert "timestamped at IMPORT" in windowed
    assert "IMPORT" not in report._kiro_limits_caveat(_rep(kiro_rows=3), usd=False)


def test_k4_blank_surface_reads_as_the_source_does_not_say():
    """K4 (finding: per-surface attribution is agent-dependent). Claude's CLI and VS Code
    share one store with no marker, so a blank cell must never be read as "cli"."""
    # `claude-code` is what a claude row's `agent` field actually holds — the caveat must
    # match the real stamp, not the SURFACES name.
    groups = {"—": {"calls": 2, "agents": ["claude-code"]}}
    line = report._surface_caveat(_rep(dim="surface", groups=groups))
    assert "the source does not say" in line and 'never "cli"' in line


def test_k4_is_silent_off_the_surface_view_and_without_claude_rows():
    groups = {"—": {"calls": 2, "agents": ["claude-code"]}}
    assert report._surface_caveat(_rep(dim="agent", groups=groups)) == ""
    assert report._surface_caveat(_rep(dim="surface",
                                       groups={"vscode": {"calls": 1,
                                                          "agents": ["copilot"]}})) == ""


# ── kiro CLI: the OPPOSITE fix ────────────────────────────────────────────────

def _cli_db(path, rows):
    """rows = [(key/cwd, conversation_id)] — a minimal conversations_v2 store."""
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE conversations_v2 (key TEXT, conversation_id TEXT, "
                "value TEXT, created_at INTEGER, updated_at INTEGER)")
    for key, cid in rows:
        doc = {"model_info": {"model_id": "claude-haiku-4.5"},
               "user_turn_metadata": {"usage_info": [{"value": 0.5, "unit": "credit"}]},
               "history": [{"user": {"content": "SECRET"},
                            "request_metadata": {"context_usage_percentage": 3.0}}]}
        con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                    (key, cid, json.dumps(doc), 1, 2))
    con.commit()
    con.close()
    return path


def test_cli_credits_are_scoped_to_the_workspace_tree(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3",
                 [("/w/mine", "c1"), ("/w/mine/sub", "c2"), ("/w/other", "c3"),
                  ("/w/mine-lab", "c4")])
    rows = transcript.parse_kiro_cli_credits(db, workspace="/w/mine")
    # the tree, not the directory — and never the sibling whose name merely starts the same
    assert {r["session"] for r in rows} == {"c1", "c2"}


def test_cli_credits_unscoped_reads_the_whole_machine(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/a", "c1"), ("/w/b", "c2")])
    assert len(transcript.parse_kiro_cli_credits(db)) == 2


def test_cli_credit_row_stamps_project_basename_never_the_path(tmp_path):
    db = _cli_db(tmp_path / "data.sqlite3", [("/w/my-repo/sub", "c1")])
    row = transcript.parse_kiro_cli_credits(db)[0]
    assert row["project"] == "sub"                 # the cwd basename, like a call row
    assert "/w/my-repo" not in json.dumps(row)     # the path never enters the ledger


def test_cli_key_normalization_survives_a_symlinked_workspace(tmp_path):
    """The near-miss that returns zero rows and reads as "no kiro usage": kiro stores the
    symlink-RESOLVED cwd (verified on a real store — `/tmp/x` is keyed `/private/tmp/x`),
    so the workspace must be resolved the same way before comparison."""
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    db = _cli_db(tmp_path / "data.sqlite3", [(str(real), "c1")])
    assert len(transcript.parse_kiro_cli_credits(db, workspace=str(link))) == 1


def test_cli_workspace_resolver_precedence(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    assert paths.kiro_cli_workspace(root) == str(root.resolve())   # project tree
    monkeypatch.chdir(tmp_path)
    assert paths.kiro_cli_workspace(paths.global_home()) == ""     # the whole machine


def test_cli_credits_import_is_scoped_and_stamped(tmp_path, monkeypatch):
    root = _isolate(tmp_path, monkeypatch)
    db = _cli_db(tmp_path / "kiro-cli" / "data.sqlite3",
                 [(str(root.resolve()), "mine"), ("/elsewhere", "theirs")])
    foot = paths.Footprint(root)
    foot.policy.write_text(foot.policy.read_text(encoding="utf-8")
                           + f'\n[[sources.kirocli]]\npath = "{db}"\n'
                             'glob = "*"\nformat = "kiro-cli"\n', encoding="utf-8")
    importcmd.run(root, "all", _args())
    credits = ledger.read_kind(root, "credits")
    assert [c["session"] for c in credits] == ["mine"]   # the other cwd is not this project
    assert credits[0]["project"] == root.name
