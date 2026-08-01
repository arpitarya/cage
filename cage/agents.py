"""Multi-agent integration orchestrator (plan §5, §6, §9.5-6).

One ledger contract, three surfaces. Cage targets the wire protocol, so the *meter*
is universal (transcript import — pull-based, no hooks) and the *read* surface is
universal (MCP) — each agent has **its own wire file** that wires that agent's
idiomatic config to those universals:

  claude  → claudewire.py   (.mcp.json)
  copilot → copilotwire.py  (.vscode/mcp.json)
  kiro    → kirowire.py     (.kiro/settings/mcp.json)

**Convention: one `<agent>wire.py` per agent** — a new agent gets its own wire file
exposing `install` / `status`, and is added to `SURFACES` + the dispatch map below.
Hook wiring was removed with the hook machinery; each wire module's `install` heals
(strips/deletes) any hook artifacts a previous version wrote.

Codex support was removed completely (a product/scope call, not a capture-quality one
— see docs/archive/*-codex-removal.handoff.md); a pre-existing `.codex/hooks.json` on
an upgraded machine is now orphaned wiring, not a supported surface.
"""
from __future__ import annotations

from pathlib import Path

from cage import claudewire, copilotwire, kirowire, runshim

SURFACES = ("claude", "copilot", "kiro")

# The parser stamps a *format* agent on each ledger row (transcript.py) — identical to
# the surface name for copilot/kiro, but claude rows stamp ``claude-code``. This
# maps a ledger row's agent back to its SURFACES name, so a row-presence check (capture
# health's gate 3) matches the surface. Custom-tool rows stamp their own name (not a
# surface) and fall through unchanged — harmless (they never match a surface).
_ROW_AGENT_SURFACE = {"claude-code": "claude"}


def row_surface(row_agent: str | None) -> str | None:
    """The SURFACES name for a ledger row's ``agent`` field (``claude-code`` → ``claude``;
    everything else is identity). A custom-tool name passes through as itself."""
    return _ROW_AGENT_SURFACE.get(row_agent, row_agent)


# The wire module for each surface — add a row here when integrating a new agent.
_WIRE = {"claude": claudewire, "copilot": copilotwire, "kiro": kirowire}


def install(root: Path, surfaces: tuple[str, ...] | None = None) -> dict:
    from cage import paths, policy
    picked = surfaces or SURFACES
    # The wiring mode is project policy (`[wiring] python_launcher`, restricted
    # endpoints) — re-read on every install so a plain re-run of `cage setup`
    # preserves the persisted mode with no flag repeated.
    launcher = policy.python_launcher(policy.load(paths.Footprint(root).policy))
    # Every surface's committed wiring references the committed shim instead of an
    # absolute cage path (plan §5) — write it first so the references always resolve.
    runshim.write(root, python_launcher=launcher)
    out: dict[str, dict] = {}
    for name in (s for s in SURFACES if s in picked):
        out[name] = _WIRE[name].install(root, python_launcher=launcher)
    # Heal an already-installed graphify interceptor whose capability probe names a
    # verb removed in v0.28.0 (it would exec the real binary unmetered, silently —
    # the F1 root cause). Refresh-only: never scaffolds a shim into a project that
    # doesn't have one. Wired here, not in `adoptcmd.run`, so `cage setup --wire-only`
    # heals it too — the path a user re-runs when doctor reports it dead.
    from cage import adoptcmd
    if adoptcmd.refresh_shim(root):
        out.setdefault("graphify", {})["shim"] = "refreshed bin/graphify → current verb"
    # B-fix-2: the interceptor that actually RUNS is whichever `graphify` PATH resolves
    # first, and an adopt-era one can sit in a *different* project's bin/ — dead, silent,
    # and invisible to the root-scoped refresh above. Heal it only when it is dead AND
    # lives in a cage-managed root (`pathshim.healable`); outside one cage never writes,
    # because silently editing another project's files is the one thing this fix must not
    # become. Fail-open — a write path never raises on a diagnostic's account.
    try:
        from cage import pathshim
        ps = pathshim.classify(root)
        if ps.healable and ps.managed_root != str(root) \
                and adoptcmd.refresh_shim(Path(ps.managed_root)):
            out.setdefault("graphify", {})["path_shim"] = (
                f"refreshed {ps.winner} → current verb "
                "(PATH-winning interceptor, cage-managed root)")
    except Exception as exc:  # noqa: BLE001
        from cage import debuglog
        debuglog.exception(root, "agents.install: PATH-winning shim heal", exc)
    return out


def status(root: Path) -> dict:
    return {name: wire.status(root) for name, wire in _WIRE.items()}
