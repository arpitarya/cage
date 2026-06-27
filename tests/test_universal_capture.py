"""Universal capture (plan §3.6.5) — explicit `import`/`export` over a global ledger.

Covers: ledger-resolution precedence (`--ledger`/`CAGE_BASE` → project `.cage/` → global
`~/.cage`); capture into the global ledger with no project; the additive `project` field
(Claude-stamped, absent for the others); the incremental file-stat cursor; `cage export`
(jsonl/csv/json, `--no-import`, filters, summary-matches-report); `cage watch` single
cycle + clean exit; and malformed-policy fail-open on the capture path. cage installs NO
OS scheduler — that invariant is asserted in test_doctor.py.
"""
from __future__ import annotations

import csv
import io
import json
from types import SimpleNamespace

from cage import (clicmds, exportcmd, importcmd, initcmd, ledger, paths, policy,
                  report, transcript, watchcmd)


def _imp_args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _claude_line(uuid, tin, tout, cwd="/Users/me/my_programs/widget"):
    return json.dumps({"type": "assistant", "uuid": uuid, "cwd": cwd,
                       "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


def _isolate_agent_homes(d, monkeypatch):
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))


# ── ledger resolution precedence ──────────────────────────────────────────────

def test_resolution_precedence(tmp_path, monkeypatch):
    # Global tier: no project, no override → CAGE_HOME/.cage (autouse-isolated off real home).
    fresh = tmp_path / "no-project"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    monkeypatch.delenv("CAGE_BASE", raising=False)
    assert paths.resolve_root() == paths.global_home()
    assert paths.Footprint(paths.resolve_root()).base == paths.global_base()
    assert paths.active_ledger_source().startswith("global")

    # Project tier: a `.cage/` in cwd wins over global.
    proj = tmp_path / "proj"
    (proj / ".cage").mkdir(parents=True)
    monkeypatch.chdir(proj)
    assert paths.resolve_root() == proj
    assert paths.active_ledger_source().startswith("project")

    # Override tier: CAGE_BASE (what `--ledger` sets) re-bases every Footprint, beating both.
    override = tmp_path / "store"
    monkeypatch.setenv("CAGE_BASE", str(override))
    assert paths.Footprint(paths.resolve_root()).base == override
    assert paths.active_ledger_source().startswith("override")


def test_ledger_flag_sets_cage_base(tmp_path, monkeypatch):
    from cage import cli
    monkeypatch.delenv("CAGE_BASE", raising=False)
    store = tmp_path / "mystore"
    cli.main(["--ledger", str(store), "report"])  # read-only; just exercises wiring
    import os
    assert os.environ.get("CAGE_BASE") == str(store)


# ── capture into the global ledger with no project ────────────────────────────

def test_import_with_no_project_lands_in_global_ledger(tmp_path, monkeypatch, capsys):
    fresh = tmp_path / "random-dir"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    _isolate_agent_homes(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")

    assert clicmds.cmd_import(_imp_args(agent="claude", path=str(tp))) == 0
    assert "imported 1 call" in capsys.readouterr().out
    # Landed in the global ledger, NOT a stray .cage scattered into the random cwd.
    assert len(ledger.calls(paths.global_home())) == 1
    assert not (fresh / ".cage").exists()


def test_report_reads_global_ledger_for_no_project_user(tmp_path, monkeypatch, capsys):
    fresh = tmp_path / "elsewhere"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    _isolate_agent_homes(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    clicmds.cmd_import(_imp_args(agent="claude", path=str(tp)))
    capsys.readouterr()
    assert clicmds.cmd_report(SimpleNamespace(by="agent", since=None, scope=None,
                                              project=None, team=False, json=False)) == 0
    assert "claude-code" in capsys.readouterr().out  # the global spend shows up


# ── the additive `project` field ──────────────────────────────────────────────

def test_project_stamped_for_claude_from_cwd_basename(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 10, 5, cwd="/Users/me/code/alpha") + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert rows and rows[0]["project"] == "alpha"  # basename only — never the full path
    assert "/" not in rows[0]["project"]


def test_project_absent_for_copilot_and_kiro(tmp_path):
    cop = tmp_path / "events.jsonl"
    cop.write_text(json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T10:00:00Z",
                               "data": {"modelMetrics": {"gpt-5": {"usage": {
                                   "inputTokens": 100, "outputTokens": 20}}}}}) + "\n",
                   encoding="utf-8")
    krow = tmp_path / "tokens_generated.jsonl"
    krow.write_text(json.dumps({"model": "agent", "provider": "kiro",
                                "promptTokens": 50, "generatedTokens": 0}) + "\n", encoding="utf-8")
    assert all(r["project"] == "" for r in transcript.parse_copilot_calls(cop, session="x"))
    assert all(r["project"] == "" for r in transcript.parse_kiro_calls(krow))


def test_report_project_filter(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    from cage import schema
    for proj, tin in (("alpha", 100), ("beta", 200), ("alpha", 300)):
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="anthropic", model="claude-opus-4-8",
            tokens_in=tin, tokens_out=10, agent="claude-code", project=proj))
    rep = report.summarize(root, policy.load(None), dim="project", project="alpha")
    assert set(rep["groups"]) == {"alpha"}
    assert rep["total"]["calls"] == 2 and rep["total"]["tokens_in"] == 400


# ── incremental file-stat cursor ──────────────────────────────────────────────

def test_cursor_skips_unchanged_files(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")

    importcmd.run(root, "claude", _imp_args(agent="claude", path=str(tp)))
    assert len(ledger.calls(root)) == 1
    cur = json.loads(paths.Footprint(root).cursors.read_text())
    assert str(tp) in cur["claude"] and "_last_import" in cur  # high-water recorded

    # Second run: file unchanged → cursor skip (recorded), still idempotent.
    log = paths.Footprint(root).debug_log
    importcmd.run(root, "claude", _imp_args(agent="claude", path=str(tp)))
    assert len(ledger.calls(root)) == 1
    events = [json.loads(l) for l in log.read_text().splitlines()]
    assert any(e.get("skip") == "cursor-unchanged" for e in events)

    # Append a new turn (size/mtime change) → the cursor lets it through.
    with tp.open("a", encoding="utf-8") as fh:
        fh.write(_claude_line("u2", 70, 30) + "\n")
    importcmd.run(root, "claude", _imp_args(agent="claude", path=str(tp)))
    assert len(ledger.calls(root)) == 2


# ── cage export ───────────────────────────────────────────────────────────────

def _seed(root):
    from cage import schema
    for i, (agent, model, tin) in enumerate((("claude-code", "claude-opus-4-8", 100),
                                             ("codex", "gpt-5", 200))):
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="anthropic" if agent == "claude-code" else "openai",
            model=model, tokens_in=tin, tokens_out=10, agent=agent,
            project="alpha" if agent == "claude-code" else "", call_id=f"c_seed{i}"))


def _export_args(**kw):
    base = dict(format="jsonl", since=None, project=None, agent=None,
                do_import=False, output=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_export_jsonl_is_valid_and_lossless(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _seed(root)
    exportcmd.run(root, _export_args(format="jsonl"), pol=policy.load(None))
    out = capsys.readouterr().out
    rows = [json.loads(l) for l in out.splitlines() if l.strip()]
    assert len(rows) == 2 and all("tokens_in" in r and "project" in r for r in rows)


def test_export_csv_has_header_and_rows(tmp_path, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _seed(root)
    exportcmd.run(root, _export_args(format="csv"), pol=policy.load(None))
    out = capsys.readouterr().out
    reader = list(csv.DictReader(io.StringIO(out)))
    assert len(reader) == 2 and reader[0]["agent"] == "claude-code"


def test_export_empty_ledger_is_valid_artifact(tmp_path, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    exportcmd.run(root, _export_args(format="csv"), pol=policy.load(None))
    out = capsys.readouterr().out
    assert out.splitlines()[0].startswith("id,ts,session")  # header-only, not a crash
    exportcmd.run(root, _export_args(format="json"), pol=policy.load(None))
    assert json.loads(capsys.readouterr().out)["total"]["calls"] == 0


def test_export_json_summary_totals_match_report(tmp_path, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _seed(root)
    pol = policy.load(None)
    exportcmd.run(root, _export_args(format="json"), pol=pol)
    summary = json.loads(capsys.readouterr().out)
    rep = report.summarize(root, pol, dim="agent")
    assert summary["total"]["calls"] == rep["total"]["calls"]
    assert round(summary["total"]["usd"], 6) == round(rep["total"]["usd"], 6)


def test_export_filters(tmp_path, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _seed(root)
    exportcmd.run(root, _export_args(format="jsonl", agent="codex"), pol=policy.load(None))
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["agent"] == "codex"
    exportcmd.run(root, _export_args(format="jsonl", project="alpha"), pol=policy.load(None))
    rows = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.strip()]
    assert len(rows) == 1 and rows[0]["project"] == "alpha"


def test_export_no_import_leaves_ledger_unchanged(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _isolate_agent_homes(tmp_path, monkeypatch)
    _seed(root)
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    exportcmd.run(root, _export_args(format="jsonl", do_import=False), pol=policy.load(None))
    after = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    assert after == before  # --no-import never refreshes


def test_export_default_imports_first_and_announces(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    _isolate_agent_homes(tmp_path, monkeypatch)  # default import sweeps empty homes → 0 new
    exportcmd.run(root, _export_args(format="jsonl", do_import=True), pol=policy.load(None))
    err = capsys.readouterr().err
    assert "↻ imported" in err  # the refresh side effect is always visible (on stderr)


def test_export_to_file(tmp_path, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    _seed(root)
    out = tmp_path / "spend.jsonl"
    exportcmd.run(root, _export_args(format="jsonl", output=str(out)), pol=policy.load(None))
    assert out.exists() and len(out.read_text().splitlines()) == 2
    assert "wrote 2 call(s)" in capsys.readouterr().err  # status to stderr, file to disk


# ── cage watch ────────────────────────────────────────────────────────────────

def test_watch_runs_one_cycle_then_clean_exit(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    cycles = []
    monkeypatch.setattr(watchcmd.importcmd, "run",
                        lambda r, a, args: cycles.append(a) or ["✔ stub"])

    def _interrupt(_secs):
        raise KeyboardInterrupt

    monkeypatch.setattr(watchcmd.time, "sleep", _interrupt)
    rc = watchcmd.run(root, SimpleNamespace(agent="all", interval=1, since=None))
    assert rc == 0                         # Ctrl-C → clean exit, no traceback
    assert cycles == ["all"]               # exactly one import cycle before the interrupt
    out = capsys.readouterr().out
    assert "stopped" in out and "No OS job" in out


# ── malformed policy fail-open on capture ─────────────────────────────────────

def test_capture_failopen_on_malformed_policy(tmp_path, monkeypatch, capsys):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    _isolate_agent_homes(tmp_path, monkeypatch)
    # A duplicate [debug] table makes tomllib raise — capture must fail open, not traceback.
    (root / ".cage" / "policy.toml").write_text(
        "[debug]\nenabled = true\n[debug]\nenabled = false\n", encoding="utf-8")
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    assert clicmds.cmd_import(_imp_args(agent="claude", path=str(tp))) == 0
    assert len(ledger.calls(root)) == 1  # imported despite the broken policy
