"""The CI-GF `present` leg's corpus-sizing invariant (`tools/cigraphify.py`).

A graphify query only files a savings receipt when the answer is genuinely cheaper
than the source files it cites (`graphifymeter._meter`) — a corpus that is too small
makes every query honestly `unmeasurable`, and a CI leg with no assertion that a
receipt actually landed would go green on the strength of graphify running, never on
the strength of interception having been proven. That is exactly what the first draft
of `tests/fixtures/cicorpus/` did (see the module docstring in `tools/cigraphify.py`).

These tests pin the fix at the unit level — no real graphify, no subprocess, no
corpus — by monkeypatching the two seams `check_bare_graphify_is_intercepted` reads
(the shell call and the ledger read) and proving it refuses to report success on an
empty or zero-saving result. This is the regression test for "the leg can pass while
asserting nothing"; it is not a duplicate of `tools/cigraphify.py`'s own logic, since
it exercises that exact function rather than restating its rule.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import cigraphify


class _FakeCompleted:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout
        self.stderr = ""
        self.returncode = 0


def _env(tmp_path: Path) -> dict:
    return {"HOME": str(tmp_path / "home")}


def test_no_new_savings_row_fails_loudly(tmp_path, monkeypatch):
    """The vacuous-corpus case: graphify ran, printed something, but filed no receipt
    (every query came back `unmeasurable`). This must never read as success."""
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(cigraphify, "_sh", lambda *a, **k: _FakeCompleted("NODE x\n"))
    monkeypatch.setattr(cigraphify, "_savings_rows", lambda p: [])

    with pytest.raises(cigraphify.Fail, match="no savings row"):
        cigraphify.check_bare_graphify_is_intercepted(project, _env(tmp_path))


def _rows_before_then_after(*rows: dict):
    """`_savings_rows` is read twice — once for the before-snapshot, once after the
    query — so a mock must return an empty ledger the first time and the new row(s)
    the second, exactly like a real ledger gaining a row mid-check."""
    calls = {"n": 0}

    def _fake(_project):
        calls["n"] += 1
        return [] if calls["n"] == 1 else list(rows)

    return _fake


def test_zero_saving_row_fails_loudly(tmp_path, monkeypatch):
    """A degenerate receipt (raw_alternative == actual) claims nothing — must not pass
    either, even though a row technically exists."""
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(cigraphify, "_sh", lambda *a, **k: _FakeCompleted("NODE x\n"))
    monkeypatch.setattr(cigraphify, "_savings_rows", _rows_before_then_after(
        {"tool": "graphify", "raw_alternative": 50, "actual": 50}))

    with pytest.raises(cigraphify.Fail, match="no saving"):
        cigraphify.check_bare_graphify_is_intercepted(project, _env(tmp_path))


def test_a_genuine_saving_passes(tmp_path, monkeypatch):
    """The control case: a real receipt with a positive saving is accepted, so the two
    failure tests above are pinning the corpus-sizing rule and not a broken check."""
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(cigraphify, "_sh", lambda *a, **k: _FakeCompleted("NODE x\n"))
    monkeypatch.setattr(cigraphify, "_savings_rows", _rows_before_then_after(
        {"tool": "graphify", "raw_alternative": 500, "actual": 50}))

    result = cigraphify.check_bare_graphify_is_intercepted(project, _env(tmp_path))
    assert "450" in result


def test_no_stdout_fails_loudly(tmp_path, monkeypatch):
    """A shim that swallows the real binary's output entirely (a passthrough break)
    must not be waved through just because a savings row happens to exist from a
    stale prior run."""
    project = tmp_path / "proj"
    project.mkdir()
    monkeypatch.setattr(cigraphify, "_sh", lambda *a, **k: _FakeCompleted(""))
    monkeypatch.setattr(cigraphify, "_savings_rows", lambda p: [])

    with pytest.raises(cigraphify.Fail, match="no stdout"):
        cigraphify.check_bare_graphify_is_intercepted(project, _env(tmp_path))
