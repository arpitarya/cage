"""Capture-path observability — `cage/debuglog.py` + hook/import instrumentation.

The capture path is fail-open everywhere; these tests pin the new diagnostic layer
that makes it *observable* without changing it: off by default (no file, ledger
byte-identical), metadata-only (no prompt bodies), a per-(agent,event) heartbeat, and
recorded tracebacks where the path previously swallowed exceptions silently.
"""
from __future__ import annotations

import json

import pytest

from cage import agents, debuglog, doctorcmd, hooks, importcmd, initcmd, paths, schema


def _events(root) -> list[dict]:
    log = paths.Footprint(root).debug_log
    return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def _row(**kw) -> dict:
    return schema.make_call(route="direct", provider="anthropic", model="claude-x",
                            tokens_in=10, tokens_out=5, **kw)


# --- the logger itself -------------------------------------------------------

def test_event_writes_structured_line_when_enabled(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    debuglog.event(proj, agent="claude", event="stop", appended=2)
    rows = _events(proj)
    assert rows and rows[-1]["event"] == "stop"
    assert rows[-1]["agent"] == "claude" and rows[-1]["appended"] == 2
    assert "ts" in rows[-1]


def test_no_file_and_no_overhead_when_off(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.delenv("CAGE_DEBUG", raising=False)  # default off
    debuglog.event(proj, agent="claude", event="stop")
    debuglog.heartbeat(proj, "claude", "stop", str(proj))
    assert not paths.Footprint(proj).debug_log.exists()
    assert not paths.Footprint(proj).hooks_seen.exists()


def test_logger_is_self_fail_open(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")

    def boom(*a, **k):
        raise OSError("disk full")

    monkeypatch.setattr(debuglog, "_append", boom)
    # A broken logger must be swallowed — capture survives it.
    debuglog.event(proj, agent="x", event="y")
    debuglog.exception(proj, "ctx", ValueError("v"))
    debuglog.heartbeat(proj, "x", "y", str(proj))


def test_heartbeat_last_write_wins_per_key(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    debuglog.heartbeat(proj, "codex", "import", "/first")
    debuglog.heartbeat(proj, "codex", "import", "/second")
    seen = debuglog.last_seen(proj)
    assert seen[("codex", "import")]["cwd"] == "/second"


# --- hook instrumentation ----------------------------------------------------

def _wire_stop(proj, monkeypatch, parse):
    payload = {"cwd": str(proj), "transcript_path": str(proj / "t.jsonl"), "session_id": "s1"}
    monkeypatch.setattr(hooks, "_stdin_json", lambda: payload)
    monkeypatch.setattr("cage.transcript.parse_calls", parse)


def test_stop_hook_logs_event_and_heartbeat(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    _wire_stop(proj, monkeypatch, lambda p, session="": [])
    assert hooks.stop() == 0
    assert any(e["event"] == "stop" for e in _events(proj))
    assert ("claude", "stop") in debuglog.last_seen(proj)


def test_parser_exception_is_recorded_and_hook_still_returns_0(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")

    def boom(*a, **k):
        raise RuntimeError("parser blew up")

    _wire_stop(proj, monkeypatch, boom)
    assert hooks.stop() == 0  # fail-open preserved
    exc = [e for e in _events(proj) if e.get("event") == "exception"]
    assert exc and exc[-1]["error"] == "RuntimeError"
    assert "traceback" in exc[-1] and "parser blew up" in exc[-1]["traceback"]


def test_debug_log_carries_no_prompt_or_response_bodies(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    sentinel = "SECRET_PROMPT_BODY_DO_NOT_LOG"
    payload = {"cwd": str(proj), "transcript_path": str(proj / "t.jsonl"),
               "session_id": "s1", "prompt": sentinel, "response": sentinel}
    monkeypatch.setattr(hooks, "_stdin_json", lambda: payload)
    monkeypatch.setattr("cage.transcript.parse_calls", lambda p, session="": [_row(call_id="c1")])
    hooks.stop()
    text = paths.Footprint(proj).debug_log.read_text()
    assert sentinel not in text  # no body ever reaches the log
    allowed = {"ts", "agent", "event", "cwd", "resolved_root", "cage_present",
               "transcript_path_present", "result", "appended", "context", "error",
               "traceback", "tool_name", "files_buffered", "skip", "sha_present",
               "buffers", "rows_written", "banner_shown", "src", "files", "parsed",
               "deduped", "note", "capture_enabled", "candidates"}
    for e in _events(proj):
        assert set(e).issubset(allowed), f"unexpected keys logged: {set(e) - allowed}"


# --- import instrumentation --------------------------------------------------

class _Args:
    agent = "all"
    path = None
    project = None
    since = None


@pytest.mark.parametrize("agent", list(agents.SURFACES))
def test_every_agent_import_logs_a_structured_event(proj, monkeypatch, tmp_path, agent):
    """Four-agent coverage is provable, not implied: driven off `agents.SURFACES`, every
    surface must emit a metadata-only import event (agent, src, files, parsed/appended/
    deduped) — a newly added agent that doesn't log fails this test."""
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    empty = tmp_path / "src"
    empty.mkdir()  # an empty source dir → 0 files, but the event is still recorded

    class A:
        path = str(empty)
        project = None
        since = None

    importcmd.run(proj, agent, A())
    detail = [e for e in _events(proj)
              if e.get("agent") == agent and e.get("result") == "ok" and "src" in e]
    assert detail, f"no structured import event recorded for {agent}"
    d = detail[-1]
    assert {"files", "parsed", "appended", "deduped"} <= set(d)


def test_since_filtered_skip_is_logged(proj, monkeypatch, tmp_path):
    import os
    import time
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    src = tmp_path / "src"
    src.mkdir()
    old = src / "old.jsonl"
    old.write_text("{}\n", encoding="utf-8")
    stale = time.time() - 60 * 60 * 24 * 30  # 30d ago
    os.utime(old, (stale, stale))

    class A:
        path = str(src)
        project = None
        since = "1d"

    importcmd.run(proj, "claude", A())  # the only candidate is older than the window
    assert any(e.get("skip") == "since-filtered" for e in _events(proj))


def test_capture_disabled_skip_is_logged(proj, monkeypatch):
    # Capture is global by default now (no cwd-`.cage` guard — a hook firing outside a
    # project lands in the resolved sink, never a stray footprint, see paths.resolve_root).
    # The one remaining import skip is the consumer's capture switch: with it off, run()
    # no-ops with a recorded `capture-disabled` event and a visible line.
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    out = importcmd.run(proj, "all", _Args())
    assert any("capture disabled" in line for line in out)
    assert any(e.get("skip") == "capture-disabled" for e in _events(proj))


# --- doctor surface ----------------------------------------------------------

def test_doctor_trace_off_says_how_to_enable(proj):
    initcmd.run(proj)
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "trace")
    assert "capture debug off" in detail and "CAGE_DEBUG=1" in detail


def test_doctor_shows_per_agent_last_fired_including_never(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    debuglog.heartbeat(proj, "claude", "stop", str(proj))
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "trace")
    assert "capture debug ON" in detail
    assert "claude" in detail and "last fired" in detail
    assert "never fired" in detail  # codex / copilot / kiro have no heartbeat yet


# --- the core invariant: debug never changes capture -------------------------

def test_ledger_byte_identical_with_debug_on_vs_off(tmp_path, monkeypatch):
    row = _row(call_id="c1", ts="2026-06-01T00:00:00+00:00")

    def capture(root):
        initcmd.run(root)
        payload = {"cwd": str(root), "transcript_path": str(root / "t.jsonl"), "session_id": "s"}
        monkeypatch.setattr(hooks, "_stdin_json", lambda: payload)
        monkeypatch.setattr("cage.transcript.parse_calls", lambda p, session="": [dict(row)])
        assert hooks.stop() == 0

    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()

    monkeypatch.delenv("CAGE_DEBUG", raising=False)
    capture(a)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    capture(b)

    shard_a = paths.Footprint(a).shard("calls", row["ts"])
    shard_b = paths.Footprint(b).shard("calls", row["ts"])
    assert shard_a.read_bytes() == shard_b.read_bytes()  # capture is byte-identical
    assert not paths.Footprint(a).debug_log.exists()     # off ⇒ no debug file
    assert paths.Footprint(b).debug_log.exists()         # on  ⇒ events recorded


def test_main_exits_cleanly_on_ctrl_c(monkeypatch, capsys):
    """Ctrl-C (e.g. aborting the `cage setup` wizard) exits 130 with no traceback."""
    from cage import cli, clicmds

    def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(clicmds, "cmd_overview", interrupt)
    assert cli.main([]) == 130
    assert "aborted" in capsys.readouterr().out
