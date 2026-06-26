"""Shared fixtures — an isolated project root with the demo ledger seeded."""
from __future__ import annotations

import pytest

from cage import demo, metering


@pytest.fixture(autouse=True)
def _bare_cage_in_hooks(monkeypatch):
    """Pin `paths.cage_bin` to bare ``cage`` for tests. Production resolves it to the
    absolute path (so GUI agents' hooks find it); tests assert the stable bare command."""
    monkeypatch.setattr("cage.paths.cage_bin", lambda: "cage")


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
