"""`cage import-claude` — hookless metering from on-disk Claude Code transcripts."""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import clicmds, ledger, paths


def _claude_line(uuid: str, tin: int, tout: int) -> str:
    return json.dumps({"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


def _args(path=None, project=None, since=None):
    return SimpleNamespace(path=path, project=project, since=since)


def _init_root(d, monkeypatch):
    (d / ".cage").mkdir(parents=True)
    monkeypatch.chdir(d)
    return d


def test_import_records_calls(tmp_path, monkeypatch, capsys):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n" + _claude_line("u2", 200, 60) + "\n",
                  encoding="utf-8")
    assert clicmds.cmd_import_claude(_args(path=str(tp))) == 0
    calls = ledger.calls(root)
    assert len(calls) == 2
    assert calls[0]["tokens_in"] == 100 and calls[0]["tokens_out"] == 50
    assert calls[1]["tokens_in"] == 200 and calls[0]["agent"] == "claude-code"
    assert "imported 2 Claude call(s) from 1 transcript(s)." in capsys.readouterr().out


def test_reimport_is_idempotent(tmp_path, monkeypatch):
    root = _init_root(tmp_path, monkeypatch)
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    clicmds.cmd_import_claude(_args(path=str(tp)))
    after_first = b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls"))
    clicmds.cmd_import_claude(_args(path=str(tp)))  # same uuid → no double count
    assert len(ledger.calls(root)) == 1
    assert b"".join(p.read_bytes() for p in paths.Footprint(root).shards("calls")) == after_first  # byte-identical ledger


def test_project_filter_selects_only_matching_slug(tmp_path, monkeypatch):
    root = tmp_path / "ledger"
    _init_root(root, monkeypatch)
    home = tmp_path / "home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    proj_a, proj_b = tmp_path / "projA", tmp_path / "projB"
    proj_a.mkdir(); proj_b.mkdir()
    dir_a = home / "projects" / paths.claude_project_slug(proj_a)
    dir_b = home / "projects" / paths.claude_project_slug(proj_b)
    dir_a.mkdir(parents=True); dir_b.mkdir(parents=True)
    (dir_a / "a.jsonl").write_text(_claude_line("ua", 10, 5) + "\n", encoding="utf-8")
    (dir_b / "b.jsonl").write_text(_claude_line("ub", 20, 7) + "\n", encoding="utf-8")
    clicmds.cmd_import_claude(_args(project=str(proj_a)))
    calls = ledger.calls(root)
    assert len(calls) == 1 and calls[0]["tokens_in"] == 10  # only project A's session


def test_malformed_transcript_does_not_abort_scan(tmp_path, monkeypatch):
    root = _init_root(tmp_path, monkeypatch)
    scan = tmp_path / "scan"
    scan.mkdir()
    (scan / "good.jsonl").write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    (scan / "bad.jsonl").write_text("{not json\nnope\n", encoding="utf-8")
    assert clicmds.cmd_import_claude(_args(path=str(scan))) == 0  # no raise
    assert len(ledger.calls(root)) == 1  # the good file still imported
