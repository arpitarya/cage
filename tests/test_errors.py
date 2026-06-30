"""Error-handling boundary tests (handoff: cage error-handling hardening).

Two things are verified here, both additive and boundary-only:

  1. The CLI exit-code contract — `cli.main` maps CageError -> 1 (clean line),
     KeyboardInterrupt -> 130, an unexpected exception -> 1 (full traceback only
     under CAGE_DEBUG), and argparse usage errors -> 2 (stdlib default).
  2. The constitutional fail-open write paths stay fail-open — a forced internal
     error in `ledger.append` / `metering.meter` / a hook never propagates, and
     the hook swallow is reachable via `debuglog` (not truly silent).

Nothing here rewrites a fail-open block; these are tests + the new typed-error
render path only.
"""
from __future__ import annotations

import io

import pytest

from cage import cli, clicmds, hooks, ledger, mcpserver, metering
from cage.errors import CageError


def _raise(exc):
    """A command/callable that raises ``exc`` regardless of how it's called."""
    def fn(*args, **kwargs):
        raise exc
    return fn


# --- cli.main() exit-code contract ----------------------------------------

def test_main_cageerror_exits_1_clean(monkeypatch, capsys):
    monkeypatch.setattr(clicmds, "cmd_report", _raise(CageError("bad thing")))
    assert cli.main(["report"]) == 1
    out = capsys.readouterr()
    assert out.err.strip() == "error: bad thing"
    assert "Traceback" not in out.err


def test_main_keyboardinterrupt_exits_130(monkeypatch):
    monkeypatch.setattr(clicmds, "cmd_report", _raise(KeyboardInterrupt()))
    assert cli.main(["report"]) == 130


def test_main_unexpected_exits_1_no_traceback(monkeypatch, capsys):
    monkeypatch.delenv("CAGE_DEBUG", raising=False)
    monkeypatch.setattr(clicmds, "cmd_report", _raise(RuntimeError("kaboom")))
    assert cli.main(["report"]) == 1
    out = capsys.readouterr()
    assert "error: kaboom" in out.err
    assert "Traceback" not in out.err


def test_main_unexpected_traceback_under_debug(monkeypatch, capsys):
    monkeypatch.setenv("CAGE_DEBUG", "1")
    monkeypatch.setattr(clicmds, "cmd_report", _raise(RuntimeError("kaboom")))
    assert cli.main(["report"]) == 1
    out = capsys.readouterr()
    assert "error: kaboom" in out.err
    assert "Traceback (most recent call last)" in out.err


def test_unknown_subcommand_exits_2():
    """argparse renders its own usage error and exits 2 (before main's try)."""
    with pytest.raises(SystemExit) as ex:
        cli.main(["frobnicate-nope"])
    assert ex.value.code == 2


# --- malformed policy.toml at a read boundary -----------------------------

def test_malformed_policy_clean_error(proj, monkeypatch, capsys):
    (proj / ".cage").mkdir()
    (proj / ".cage" / "policy.toml").write_text("this = = not valid toml [[[\n")
    monkeypatch.chdir(proj)
    assert cli.main(["report"]) == 1
    out = capsys.readouterr()
    assert out.err.startswith("error: policy.toml:")
    assert "Traceback" not in out.err


# --- agent / MCP boundary (already crash-proof; verify it) -----------------

def test_mcp_unknown_tool_is_error():
    reply = mcpserver._handle({"id": 1, "method": "tools/call",
                               "params": {"name": "cage_nope", "arguments": {}}})
    assert reply["result"]["isError"] is True
    assert "error:" in reply["result"]["content"][0]["text"]


def test_mcp_missing_required_arg_is_error():
    reply = mcpserver._handle({"id": 2, "method": "tools/call",
                               "params": {"name": "cage_why", "arguments": {}}})
    assert reply["result"]["isError"] is True


def test_mcp_bad_json_line_skipped_no_crash():
    out = io.StringIO()
    mcpserver.serve(stdin=io.StringIO("not json at all\n{still bad\n"), stdout=out)
    assert out.getvalue() == ""  # malformed lines are skipped; the server stays up


def test_verify_still_exits_zero(proj, monkeypatch):
    """`cage verify` is report-only and must keep exiting 0 (never a build gate)."""
    monkeypatch.chdir(proj)
    assert cli.main(["verify"]) == 0


# --- fail-open write paths (verify, do not rewrite) -----------------------

def test_ledger_append_returns_false_not_raise(tmp_path):
    """A write that can't happen (parent is a file) returns False, never raises."""
    blocker = tmp_path / "blocker"
    blocker.write_text("x")
    assert ledger.append(blocker / "sub" / "x.jsonl", {"a": 1}) is False


def test_meter_swallows_its_own_cleanup_error(monkeypatch):
    """A failure while *recording* the call must not escape the metered block."""
    monkeypatch.setattr(metering, "record_call", _raise(RuntimeError("record failed")))
    with metering.meter("route") as rec:  # must complete without raising
        rec.provider = "anthropic"
        rec.model = "claude-opus-4-8"
        rec.tokens_in = 10


def test_meter_cleanup_error_is_traced(monkeypatch):
    """The meter cleanup swallow is reachable via debuglog (not truly silent)."""
    traced = []
    monkeypatch.setattr(metering, "record_call", _raise(RuntimeError("record failed")))
    monkeypatch.setattr("cage.debuglog.exception",
                        lambda *a, **k: traced.append((a, k)))
    with metering.meter("route") as rec:
        rec.provider = "anthropic"
        rec.model = "claude-opus-4-8"
        rec.tokens_in = 10
    assert traced, "meter's fail-open cleanup must be traceable via debuglog"


def test_meter_does_not_swallow_user_exception(monkeypatch):
    """meter is fail-open on *its own* cleanup, never on the metered code's error."""
    monkeypatch.setattr(metering, "record_call", lambda **k: "id")
    with pytest.raises(ValueError):
        with metering.meter("route") as rec:
            rec.provider = "anthropic"
            rec.model = "claude-opus-4-8"
            raise ValueError("user code blew up")


def test_hook_stop_failopen_and_traced(monkeypatch):
    """A capture error inside the Stop hook never breaks the turn (exit 0) and is
    surfaced via debuglog (reachable under CAGE_DEBUG) — not a silent swallow."""
    traced = []
    monkeypatch.setattr(hooks, "_stdin_json", lambda: {})
    monkeypatch.setattr(hooks, "_capture_calls", _raise(RuntimeError("capture boom")))
    monkeypatch.setattr(hooks.debuglog, "exception",
                        lambda *a, **k: traced.append((a, k)))
    assert hooks.stop() == 0
    assert traced, "the Stop-hook swallow must be traceable via debuglog, not silent"
