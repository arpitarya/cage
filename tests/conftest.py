"""Shared fixtures — an isolated project root with the demo ledger seeded."""
from __future__ import annotations

import pytest

from cage import demo, metering


@pytest.fixture(autouse=True)
def _bare_cage_in_hooks(monkeypatch, tmp_path):
    """Pin `paths.cage_bin` to bare ``cage`` for tests. Production resolves it to the
    absolute path (so GUI agents' hooks find it); tests assert the stable bare command.

    Also redirect the global ledger (`paths.global_home`) off the real ``~/.cage`` to a
    throwaway per-test dir via ``CAGE_HOME``, so a no-project read/capture (which now falls
    back to the global ledger, plan §3.6.5) can never see or pollute the developer's real
    global ledger — tests stay hermetic and deterministic."""
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "cage")
    monkeypatch.setenv("CAGE_HOME", str(tmp_path / "global-home"))
    # Capture-on-read is the new primary path (capture-architecture Phase 1), but it
    # couples a read to a write and would sweep the developer's REAL agent homes from
    # inside a `cage report`. Pin it OFF for the whole suite so every determinism/golden
    # test reads a FIXED ledger (the hard requirement); the dedicated capture-on-read
    # tests opt back in with `monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "1")` over
    # isolated empty homes.
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "0")
    # The copilot import also scans VS Code's chat-session store — point it at a
    # throwaway dir so a pathless sweep never reads the developer's real sessions.
    monkeypatch.setenv("CAGE_VSCODE_USER", str(tmp_path / "vscode-user"))
    # Redirect every agent home off the real machine. `cage doctor`'s wiring-liveness
    # check (cage/wiringscan.py) deliberately scans USER-LEVEL artifacts — both real
    # F1 failures were user-level — so without this the suite reads the developer's own
    # ~/.claude/settings.json and ~/.copilot/hooks, and a stale artifact on one machine
    # turns doctor tests red for reasons that have nothing to do with the code. Tests
    # that need their own agent homes (test_portable_wiring, test_wiringscan) override
    # these with their own `homes` fixture.
    for var, sub in (("CLAUDE_CONFIG_DIR", "claude-home"), ("CODEX_HOME", "codex-home"),
                     ("COPILOT_HOME", "copilot-home"), ("KIRO_HOME", "kiro-home")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    # `cage --ledger` sets `CAGE_BASE` via os.environ (process-scoped in production); clear
    # it per test so a `--ledger` test can't re-base a later test's Footprint.
    monkeypatch.delenv("CAGE_BASE", raising=False)


@pytest.fixture
def proj(tmp_path):
    """A clean project root (no .cage/ yet — the ledger auto-creates on append)."""
    metering._policy_for.cache_clear()
    return tmp_path


@pytest.fixture
def seeded(proj):
    """The §4.4 worked example seeded into ``proj``; yields (root, call_id)."""
    call_id = demo.seed(proj)
    return proj, call_id
