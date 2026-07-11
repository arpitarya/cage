"""Multi-agent integration orchestrator (plan §5, §6, §9.5-6).

One ledger contract, four surfaces. Cage targets the wire protocol, so the *meter*
is universal (transcript import) and the *read* surface is universal (MCP) — each agent
has **its own wire file** that wires that agent's idiomatic config to those universals:

  claude  → claudewire.py   (.claude/settings.json hooks + .mcp.json)
  codex   → codexwire.py    (.codex/hooks.json + ~/.codex/config.toml MCP server)
  copilot → copilotwire.py  (~/.copilot/hooks/cage.json + .vscode/mcp.json + instructions)
  kiro    → kirowire.py     (.kiro/hooks/cage.kiro.hook + .kiro/settings/mcp.json + steering)

**Convention: one `<agent>wire.py` per agent** — a new agent gets its own wire file
exposing `install` / `status` / `backfill_status` / `realtime_status`, and is added to
`SURFACES` + the dispatch maps below. Each agent's hook imports **only its own** on-disk
log (`cage import --agent <itself>`) — cage never sweeps another agent's data from a hook.
"""
from __future__ import annotations

from pathlib import Path

from cage import claudewire, codexwire, copilotwire, gitcommithook, kirowire, runshim

SURFACES = ("claude", "codex", "copilot", "kiro")

# The wire module for each surface — add a row here when integrating a new agent.
_WIRE = {"claude": claudewire, "codex": codexwire,
         "copilot": copilotwire, "kiro": kirowire}


def install(root: Path, surfaces: tuple[str, ...] | None = None) -> dict:
    picked = surfaces or SURFACES
    # Every surface's committed wiring references the committed shim instead of an
    # absolute cage path (plan §5) — write it first so the references always resolve.
    runshim.write(root)
    out: dict[str, dict] = {}
    for name in (s for s in SURFACES if s in picked):
        out[name] = _WIRE[name].install(root)
    if "claude" in out:
        gh = gitcommithook.install(root)  # PostToolUse capture buffer → sha resolution (plan §3.5)
        if gh["installed"]:
            out["claude"]["git-hooks"] = ", ".join(gh["installed"])
    return out


def status(root: Path) -> dict:
    return {name: wire.status(root) for name, wire in _WIRE.items()}


def backfill_status(root: Path) -> dict:
    """Per-agent: is a SessionStart-backfill capture hook wired? All four support one."""
    return {name: wire.backfill_status(root) for name, wire in _WIRE.items()}


def realtime_status(root: Path) -> dict:
    """Per-agent: is a real-time per-turn hook wired? Claude/Codex/Kiro fire `Stop`,
    Copilot fires `agentStop` — all four have one."""
    return {name: wire.realtime_status(root) for name, wire in _WIRE.items()}
