"""`cage import [--agent ...]` — unified hookless metering across all four agents.

Claude + Codex import on-disk transcripts; Copilot + Kiro (no usage log) print the
proxy fallback. Every surface in agents.SURFACES is reachable and first-class.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import agents, clicmds, hooks, importcmd, ledger, paths


def _args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _init_root(d, monkeypatch):
    (d / ".cage").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


def _claude_line(uuid, tin, tout):
    return json.dumps({"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


def _codex_line(cid, tin, tout):
    return json.dumps({"id": cid, "timestamp": "2026-06-14T10:00:00Z",
                       "payload": {"type": "token_count", "model": "gpt-5",
                                   "info": {"last_token_usage": {"input_tokens": tin,
                                                                 "output_tokens": tout}}}})


# --- every agent is reachable -------------------------------------------------

def test_all_four_agents_reachable(tmp_path, monkeypatch, capsys):
    _init_root(tmp_path, monkeypatch)
    for a in agents.SURFACES:
        assert clicmds.cmd_import(_args(agent=a)) == 0  # never raises, always exits 0
    capsys.readouterr()


def test_default_all_runs_every_adapter(tmp_path, monkeypatch, capsys):
    _init_root(tmp_path, monkeypatch)
    assert clicmds.cmd_import(_args()) == 0  # --agent all is the default
    out = capsys.readouterr().out
    for a in agents.SURFACES:
        assert a in out  # one line per agent, none dropped


# --- log-bearing agents: import + idempotency ---------------------------------

def test_claude_import_counts_and_idempotent(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n" + _claude_line("u2", 200, 60) + "\n",
                  encoding="utf-8")
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))
    calls = ledger.calls(root)
    assert len(calls) == 2
    assert calls[0]["tokens_in"] == 100 and calls[0]["tokens_out"] == 50
    assert "✔ claude: imported 2 call(s) from 1 file(s)." in capsys.readouterr().out
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))  # re-import → no double count
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == before


def test_codex_import_counts_and_idempotent(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "rollout-2026.jsonl"
    tp.write_text(_codex_line("c1", 80, 40) + "\n", encoding="utf-8")
    clicmds.cmd_import(_args(agent="codex", path=str(tp)))
    calls = ledger.calls(root)
    assert len(calls) == 1 and calls[0]["tokens_in"] == 80 and calls[0]["agent"] == "codex"
    assert "✔ codex: imported 1 call(s) from 1 file(s)." in capsys.readouterr().out
    before = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    clicmds.cmd_import(_args(agent="codex", path=str(tp)))
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == before


def test_import_is_noop_when_hook_already_recorded_same_turns(tmp_path, monkeypatch, capsys):
    """A call seen by both a hook and an import dedupes by id (no double-count)."""
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("dup", 100, 50) + "\n", encoding="utf-8")
    from cage import transcript
    hooks.append_new(root, transcript.parse_calls(tp, session=tp.stem))  # the live hook got it
    capsys.readouterr()
    clicmds.cmd_import(_args(agent="claude", path=str(tp)))  # import the same turn
    assert len(ledger.calls(root)) == 1  # still one — id dedupe across hook + import
    assert "imported 0 call(s)" in capsys.readouterr().out


def test_malformed_file_does_not_abort(tmp_path, monkeypatch):
    root = _init_root(tmp_path, monkeypatch)
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "good.jsonl").write_text(_claude_line("u1", 10, 5) + "\n", encoding="utf-8")
    (scan / "bad.jsonl").write_text("{not json\n", encoding="utf-8")
    assert clicmds.cmd_import(_args(agent="claude", path=str(scan))) == 0
    assert len(ledger.calls(root)) == 1  # the good file still imported


# --- no-log agents: proxy fallback, zero writes -------------------------------

def test_copilot_and_kiro_print_proxy_line_and_write_nothing(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    for a in ("copilot", "kiro"):
        assert clicmds.cmd_import(_args(agent=a)) == 0
        out = capsys.readouterr().out
        assert out.strip() == f"· {a}: no on-disk usage log — meter via the proxy: cage meter -- <cmd>"
    assert ledger.calls(root) == []  # no usage signal fabricated for a log-less agent


def test_proxy_line_helper_matches_for_every_non_log_agent():
    for a in agents.SURFACES:
        if a not in importcmd.LOG_BEARING:
            assert importcmd.proxy_line(a) == \
                f"· {a}: no on-disk usage log — meter via the proxy: cage meter -- <cmd>"
