"""Multi-agent integration orchestrator (plan §5, §6, §9.5-6).

One ledger contract, four surfaces. Cage targets the wire protocol, so the *meter*
is universal (proxy / transcript) and the *read* surface is universal (MCP) — these
installers only wire each agent's idiomatic config to those two universals:

  claude  → SessionStart/SessionEnd hooks (transcript metering) + .mcp.json
  codex   → ~/.codex/config.toml MCP server   (metering via proxy / rollout import)
  copilot → .github/copilot-instructions.md + .vscode/mcp.json   (metering via proxy)
  kiro    → .kiro/steering/cage.md + .kiro/settings/mcp.json      (metering via proxy)
"""
from __future__ import annotations

from pathlib import Path

from cage import claudewire, codexwire, pointers

SURFACES = ("claude", "codex", "copilot", "kiro")


def install(root: Path, surfaces: tuple[str, ...] | None = None) -> dict:
    picked = surfaces or SURFACES
    out: dict[str, dict] = {}
    if "claude" in picked:
        out["claude"] = claudewire.install(root)
    if "codex" in picked:
        out["codex"] = codexwire.install(root)
    if "copilot" in picked:
        out["copilot"] = pointers.copilot(root)
    if "kiro" in picked:
        out["kiro"] = pointers.kiro(root)
    return out


def status(root: Path) -> dict:
    return {"claude": claudewire.status(root), "codex": codexwire.status(),
            "copilot": pointers.copilot_status(root), "kiro": pointers.kiro_status(root)}
