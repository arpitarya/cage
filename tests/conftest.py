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
    # The copilot import also scans VS Code's chat-session store — point it at a
    # throwaway dir so a pathless sweep never reads the developer's real sessions.
    monkeypatch.setenv("CAGE_VSCODE_USER", str(tmp_path / "vscode-user"))
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
