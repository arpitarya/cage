"""Universal capture (plan §3.6.5) — explicit `import`/`export` over a global ledger.

Covers: ledger-resolution precedence (`--ledger`/`CAGE_BASE` → project `.cage/` → global
`~/.cage`); capture into the global ledger with no project; the additive `project` field
(Claude-stamped, absent for the others); the incremental file-stat cursor; `cage data export`
(jsonl/csv/json, `--no-import`, filters, summary-matches-report); `cage data watch` single
cycle + clean exit; and malformed-policy fail-open on the capture path. cage installs NO
OS scheduler — that invariant is asserted in test_doctor.py.
"""
from __future__ import annotations

import csv
import io
import json
from types import SimpleNamespace

from conftest import metric_twin
from cage import (chats, clicmds, importcmd, initcmd, ledger, paths, policy,
                  transcript)
from srcseed import mkcage


def _imp_args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _claude_line(uuid, tin, tout, cwd="/Users/me/my_programs/widget"):
    return json.dumps({"type": "assistant", "uuid": uuid, "cwd": cwd,
                       "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


def _isolate_agent_homes(d, monkeypatch):
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR"):
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
    cli.main(["--ledger", str(store), "insights", "chats"])  # read-only; exercises wiring
    import os
    assert os.environ.get("CAGE_BASE") == str(store)


# ── capture into the global ledger with no project ────────────────────────────

def test_import_with_no_project_lands_in_global_ledger(tmp_path, monkeypatch, capsys):
    fresh = tmp_path / "random-dir"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    _isolate_agent_homes(tmp_path, monkeypatch)
    mkcage(paths.global_home())  # `--path` reads its patterns from the resolved ledger's cage.toml
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
    mkcage(paths.global_home())  # `--path` reads its patterns from the resolved ledger's cage.toml
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    clicmds.cmd_import(_imp_args(agent="claude", path=str(tp)))
    capsys.readouterr()
    # `cmd_report` was the original reader; SURFACE-CUT deleted it, so this asserts the
    # same thing through a surviving derived view — a no-project user reads the GLOBAL
    # ledger, which is the resolution rule under test.
    assert clicmds.cmd_chats(SimpleNamespace(
        since=None, agent=None, all=False, json=False, csv=None, no_import=True,
        export=None, stamp=False, quiet=False, why_ledger=False)) == 0
    assert "claude" in capsys.readouterr().out  # the global usage shows up


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


def test_cursor_skips_unchanged_files(tmp_path, monkeypatch):
    root = mkcage(tmp_path / "proj")  # `--path` needs a materialized `path_globs`
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


# ── cage data export ───────────────────────────────────────────────────────────────

def _seed(root):
    from cage import schema
    for i, (agent, model, tin) in enumerate((("claude-code", "claude-opus-4-8", 100),
                                             ("copilot", "gpt-5", 200))):
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="anthropic" if agent == "claude-code" else "openai",
            model=model, tokens_in=tin, tokens_out=10, agent=agent,
            project="alpha" if agent == "claude-code" else "", call_id=f"c_seed{i}"))


def _export_args(**kw):
    base = dict(format="jsonl", since=None, project=None, agent=None,
                do_import=False, output=None)
    base.update(kw)
    return SimpleNamespace(**base)


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
    # Fail-open still holds where it is defined to: exit 0, no traceback, capture never
    # raises into the caller. What a broken policy now costs is the `--path` sweep itself:
    # its patterns live in `[sources] path_globs` (path-globs handoff §5), and an
    # unreadable config declares none — so cage scans nothing rather than guessing at a
    # glob. That is the deliberate no-code-fallback rule, and it is announced, not silent.
    out = capsys.readouterr().out
    assert len(ledger.calls(root)) == 0
    assert "no `path_globs` declared for claude" in out
    assert "cage setup --sync-sources" in out

# ── `cage data export` and `--project` lost their surfaces (SURFACE-CUT) ──────
# Nine export/watch cases and `test_report_project_filter` went with their commands.
# **The CAPTURE half all of them depended on is untouched and still pinned above**:
# ledger resolution precedence, the no-project global landing, the file-stat cursor, and
# the `project` stamping rules (claude from the cwd basename, empty for copilot/kiro).
# What is gone is every DERIVED reader of `project` — `cage report --project` (plan
# §3.7) was the only one, so the field is still recorded and no view groups by it.
# `cage import --project` survives, but that is an import SCOPE, not a view.
# Filed in work/OPEN-WORK.md.
