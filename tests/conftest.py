"""Shared fixtures — an isolated project root with the demo ledger seeded."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cage import demo, metering


@pytest.fixture(autouse=True)
def _bare_cage_in_hooks(monkeypatch, tmp_path):
    """Pin `paths.cage_bin` to bare ``cage`` for tests. Production resolves it to the
    absolute path (so GUI agents' hooks find it); tests assert the stable bare command.

    Also redirect the global ledger (`paths.global_home`) off the real ``~/.cage`` to a
    throwaway per-test dir via ``CAGE_HOME``, so a no-project read/capture (which now falls
    back to the global ledger, ADR-LAWS Law 2) can never see or pollute the developer's real
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
    # Same reasoning one step further: the authorship pass resolves its repo from the
    # CWD, which under pytest is cage's own checkout — so an unrelated import test would
    # shell `git log` at the developer's real repo and parse every transcript it swept
    # against it. Pin it OFF for the suite; `tests/test_authorship_capture.py` opts back
    # in with its own throwaway repo, exactly like the capture-on-read tests do.
    monkeypatch.setenv("CAGE_AUTHORSHIP", "0")
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
    for var, sub in (("CLAUDE_CONFIG_DIR", "claude-home"),
                     ("COPILOT_HOME", "copilot-home"), ("KIRO_HOME", "kiro-home")):
        monkeypatch.setenv(var, str(tmp_path / sub))
    # `cage --ledger` sets `CAGE_BASE` via os.environ (process-scoped in production); clear
    # it per test so a `--ledger` test can't re-base a later test's Footprint.
    monkeypatch.delenv("CAGE_BASE", raising=False)
    # Strip every PATH entry holding a `graphify` — the same reason the agent homes are
    # redirected above, one step sharper. `agents.install` now heals the PATH-WINNING
    # interceptor when it sits in a cage-managed root (B-fix-2), and the developer's own
    # machine has exactly that, in a DIFFERENT repo. Without this, any test that calls
    # `agents.install` would rewrite another project's shim from inside the suite. Tests
    # that need a graphify on PATH build their own (tests/test_pathshim.py).
    monkeypatch.setenv("PATH", os.pathsep.join(
        d for d in os.environ.get("PATH", "").split(os.pathsep)
        if d and not (Path(d) / "graphify").exists()))


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


def metric_twin(root, row: dict) -> None:
    """Append the per-agent **metric twin** of a `calls` row, as real capture does.

    Since USAGE-ONLY (ADR 0011) `ledger.spend` supersedes a `calls` row for any agent
    that HAS a metric ledger — claude and copilot — and partitions by agent rather than
    by time, so there is no instant a calls-only fixture survives at. A test that seeds
    only `calls` for those agents is therefore seeding an empty ledger, and every
    assertion over it would silently pin nothing.

    Real capture dual-writes both rows for exactly this reason (CLAUDE.md, *Adapters*),
    so a fixture that does the same is not a workaround — it is the shape of the data.
    Agents with no spine (`lib`, the proxy, `codex`, custom `[sources.<name>]` tools)
    need no twin: their `calls` rows are never superseded.

    Idempotent per (session, request); safe to call after every `append_row`.
    """
    from cage import agents, ledger, schema
    surface = agents.row_surface(row.get("agent")) or ""
    common = dict(session=row.get("session", ""), model=row.get("model", ""),
                  provider=row.get("provider", ""),
                  tokens_in=row.get("tokens_in", 0),
                  tokens_out=row.get("tokens_out", 0),
                  cached_in=row.get("cached_in", 0), ts=row.get("ts"))
    twin = None
    if surface == "claude":
        twin = schema.make_claude_metric(
            source="request", request=row.get("id", ""),
            surface=row.get("surface", ""),
            cache_write_in=row.get("cache_write_in", 0), **common)
    elif surface == "copilot":
        twin = schema.make_copilot_metric(
            source="chat", surface=row.get("surface") or "vscode",
            request=row.get("id", ""),
            **({"credits": row["credits"]} if row.get("credits") is not None else {}),
            **common)
    if twin is None:
        return
    # Carry the grouping axes the metric constructors do not all model but derived views
    # bucket by — `project`, `task`, `scope`. (`machine` was here for the fleet study
    # until v0.51; the study and the field went together in STUDY-CUT.) A twin missing an
    # axis lands in the wrong bucket, not in none, which is the harder failure to spot.
    for axis in ("project", "task", "scope"):
        if row.get(axis):
            twin[axis] = row[axis]
    ledger.append_row(root, surface, twin)
