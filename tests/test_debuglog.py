"""Capture-path observability — `cage/debuglog.py` + hook/import instrumentation.

The capture path is fail-open everywhere; these tests pin the new diagnostic layer
that makes it *observable* without changing it: off by default (no file, ledger
byte-identical), metadata-only (no prompt bodies), a per-(agent,event) heartbeat, and
recorded tracebacks where the path previously swallowed exceptions silently.
"""
from __future__ import annotations

import json

import pytest

from types import SimpleNamespace

from cage import agents, debuglog, doctorcmd, importcmd, initcmd, ledger, paths, schema


def _events(root) -> list[dict]:
    log = paths.Footprint(root).debug_log
    return [json.loads(l) for l in log.read_text().splitlines()] if log.exists() else []


def _row(**kw) -> dict:
    return schema.make_call(route="direct", provider="anthropic", model="claude-x",
                            tokens_in=10, tokens_out=5, **kw)


def _import_args(**kw) -> SimpleNamespace:
    return SimpleNamespace(agent=kw.pop("agent", "claude"), path=kw.pop("path", None),
                           project=None, since=None, **kw)


def _claude_transcript(path, *, tin=100, tout=50, secret=None) -> str:
    """A one-turn Claude transcript. ``secret`` (if given) is stashed in a message-body
    field the parser must never read — a live PII tripwire for the debug log."""
    msg = {"model": "claude-opus-4-8",
           "usage": {"input_tokens": tin, "output_tokens": tout}}
    rec = {"type": "assistant", "uuid": "u1", "timestamp": "2026-06-14T10:00:00Z",
           "message": msg}
    if secret is not None:
        rec["message"]["content"] = secret
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    return str(path)


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


def test_event_writes_under_an_explicit_cage_base_override(tmp_path, monkeypatch):
    """A ``--ledger``/``CAGE_BASE`` scratch root is an *explicit* sink — the footprint
    re-bases onto it, so the debug log belongs there. Before v0.31.4 the guard tested
    ``cwd/.cage`` (unrelated to the override) and went silent, taking the F6 receipt
    trace with it — see work/regression/2026-07-24-f1-root-cause.md."""
    base, cwd = tmp_path / "scratch", tmp_path / "elsewhere"
    cwd.mkdir()  # a bare cwd: no .cage/ of its own
    monkeypatch.setenv("CAGE_BASE", str(base))
    monkeypatch.setenv("CAGE_DEBUG", "1")
    monkeypatch.delenv("CAGE_DEBUG_LOG", raising=False)

    debuglog.event(cwd, event="receipt", tool="graphify", produced=True, skip_reason="")

    rows = [json.loads(l) for l in (base / "state" / "debug.log").read_text().splitlines()]
    assert rows[-1]["event"] == "receipt" and rows[-1]["tool"] == "graphify"
    assert rows[-1]["produced"] is True
    assert not (cwd / ".cage").exists()  # still never scatters a footprint beside the cwd


def test_event_still_refused_in_a_bare_cwd_with_no_cage_and_no_override(tmp_path, monkeypatch):
    """The guard is opened only for the explicit-override case. With neither ``.cage/``
    nor ``CAGE_BASE``/``CAGE_DEBUG_LOG``, logging must still refuse rather than create a
    stray footprint that ``find_project_root`` would later read as a project."""
    bare = tmp_path / "bare"
    bare.mkdir()
    monkeypatch.setenv("CAGE_DEBUG", "1")
    for env in ("CAGE_BASE", "CAGE_DEBUG_LOG"):
        monkeypatch.delenv(env, raising=False)

    debuglog.event(bare, event="receipt", tool="graphify", produced=True)

    assert not (bare / ".cage").exists()
    assert list(bare.iterdir()) == []  # nothing written at all


def test_derived_view_byte_identical_with_debug_under_cage_base_on_vs_off(tmp_path, monkeypatch):
    """Opening the guard is observability only: it can never move a reported number.
    Same ledger + same policy ⇒ a byte-identical derived view, debug on or off."""
    from cage import chats, demo, policy

    def rendered(base, debug: bool) -> str:
        monkeypatch.setenv("CAGE_BASE", str(base))
        monkeypatch.delenv("CAGE_DEBUG_LOG", raising=False)
        monkeypatch.setenv("CAGE_DEBUG", "1") if debug else \
            monkeypatch.delenv("CAGE_DEBUG", raising=False)
        cwd = base.parent / f"cwd-{base.name}"
        cwd.mkdir()
        demo.seed(cwd)
        debuglog.event(cwd, event="receipt", tool="graphify", produced=True)
        return chats.render_chats(chats.summarize(cwd, policy.load(None)))

    off = rendered(tmp_path / "off", debug=False)
    on = rendered(tmp_path / "on", debug=True)
    assert off == on
    assert not (tmp_path / "off" / "state" / "debug.log").exists()  # off ⇒ no file
    assert (tmp_path / "on" / "state" / "debug.log").exists()       # on  ⇒ recorded


def test_heartbeat_last_write_wins_per_key(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    debuglog.heartbeat(proj, "kiro", "import", "/first")
    debuglog.heartbeat(proj, "kiro", "import", "/second")
    seen = debuglog.last_seen(proj)
    assert seen[("kiro", "import")]["cwd"] == "/second"


# --- import instrumentation (the surviving capture path) ---------------------

def test_import_logs_events_under_debug(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    tp = _claude_transcript(proj / "t.jsonl")
    importcmd.run(proj, "claude", _import_args(path=tp))
    events = _events(proj)
    assert events, "an import under CAGE_DEBUG must leave a breadcrumb"
    assert any(e.get("agent") == "claude" for e in events)


def test_parser_exception_is_recorded_and_import_still_returns(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")

    def boom(*a, **k):
        raise RuntimeError("parser blew up")

    monkeypatch.setattr("cage.transcript.parse_calls", boom)
    tp = _claude_transcript(proj / "t.jsonl")
    importcmd.run(proj, "claude", _import_args(path=tp))  # fail-open: never raises
    exc = [e for e in _events(proj) if e.get("event") == "exception"]
    assert exc and exc[-1]["error"] == "RuntimeError"
    assert "traceback" in exc[-1] and "parser blew up" in exc[-1]["traceback"]


def test_debug_log_carries_no_prompt_or_response_bodies(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    sentinel = "SECRET_PROMPT_BODY_DO_NOT_LOG"
    # the secret lives in a message-body field the parser never reads
    tp = _claude_transcript(proj / "t.jsonl", secret=sentinel)
    importcmd.run(proj, "claude", _import_args(path=tp))
    text = paths.Footprint(proj).debug_log.read_text()
    assert sentinel not in text  # no body ever reaches the log
    allowed = {"ts", "agent", "event", "cwd", "resolved_root", "cage_present",
               "transcript_path_present", "result", "appended", "context", "error",
               "traceback", "tool_name", "files_buffered", "skip", "sha_present",
               "buffers", "rows_written", "banner_shown", "src", "files", "parsed",
               "deduped", "note", "capture_enabled", "candidates",
               "exists", "pattern", "files_matched",
               # CLAUDE-METRICS's own ingest event (_ingest_claude_metrics) —
               # counts only, same discipline as every other debuglog event here.
               "kind", "filesets"}
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
    """Three-agent coverage is provable, not implied: driven off `agents.SURFACES`, every
    surface must emit a metadata-only import event (agent, src, files, parsed/appended/
    deduped) — a newly added agent that doesn't log fails this test.

    The event lands in the log of the ledger that agent captured INTO, which for kiro is
    the machine ledger (ADR 0006) — same guarantee, one hop away."""
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    empty = tmp_path / "src"
    empty.mkdir()  # an empty source dir → 0 files, but the event is still recorded

    class A:
        path = str(empty)
        project = None
        since = None

    importcmd.run(proj, agent, A())
    logged_in = paths.global_home() if paths.kiro_routed(proj) and agent == "kiro" else proj
    # "kind" marks a non-calls sibling event (credits/copilot-metrics — COPILOT-METRICS
    # gives copilot a second, differently-shaped "src"-bearing event on the SAME agent
    # name) — excluded here because this test targets the *calls*-ingest contract
    # specifically, the one `_ingest` (not `_ingest_credits`/`_ingest_copilot_metrics`)
    # emits.
    detail = [e for e in _events(logged_in)
              if e.get("agent") == agent and e.get("result") == "ok" and "src" in e
              and "kind" not in e]
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


def test_doctor_shows_per_agent_last_event_including_never(proj, monkeypatch):
    initcmd.run(proj)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    debuglog.heartbeat(proj, "claude", "import", str(proj))
    detail = next(c["detail"] for c in doctorcmd.run(proj)["checks"] if c["name"] == "trace")
    assert "capture debug ON" in detail
    assert "claude" in detail and "last event" in detail
    assert "no capture events seen yet" in detail  # copilot / kiro have no heartbeat yet


# --- the core invariant: debug never changes capture -------------------------

def test_ledger_byte_identical_with_debug_on_vs_off(tmp_path, monkeypatch):
    def capture(root):
        initcmd.run(root)
        tp = _claude_transcript(root / "t.jsonl", tin=100, tout=50)
        importcmd.run(root, "claude", _import_args(path=tp))

    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()

    monkeypatch.delenv("CAGE_DEBUG", raising=False)
    capture(a)
    monkeypatch.setenv("CAGE_DEBUG", "1")
    capture(b)

    # Normalize out the per-sweep `import_id` (a fresh random capture-manifest FK each
    # run, plan §4) — it varies by run, not by the debug switch under test.
    def _rows(root):
        return [{k: v for k, v in c.items() if k != "import_id"}
                for c in ledger.calls(root)]
    assert _rows(a) and _rows(a) == _rows(b)             # capture unchanged by debug
    assert not paths.Footprint(a).debug_log.exists()     # off ⇒ no debug file
    assert paths.Footprint(b).debug_log.exists()         # on  ⇒ events recorded


def test_main_exits_cleanly_on_ctrl_c(monkeypatch, capsys):
    """Ctrl-C (e.g. aborting the `cage setup` wizard) exits 130 with no traceback."""
    from cage import cli, clicmds

    def interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setattr(clicmds, "cmd_chats", interrupt)
    assert cli.main(["insights", "chats"]) == 130
    assert "aborted" in capsys.readouterr().out
