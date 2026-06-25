"""Multi-agent integration orchestrator (plan §5, §6, §9.5-6).

One ledger contract, four surfaces. Cage targets the wire protocol, so the *meter*
is universal (proxy / transcript) and the *read* surface is universal (MCP) — these
installers only wire each agent's idiomatic config to those two universals:

  claude  → SessionStart-backfill + SessionEnd hooks (transcript metering) + .mcp.json
  codex   → .codex/hooks.json SessionStart-backfill + ~/.codex/config.toml MCP server
  copilot → .github/copilot-instructions.md + .vscode/mcp.json   (metering via proxy)
  kiro    → .kiro/steering/cage.md + .kiro/settings/mcp.json      (metering via proxy)

The reliable capture path is **SessionStart-backfill**: import the previous session's
on-disk transcript on the next start (Claude/Codex both persist one). It is the default
for the two log-bearing agents; copilot/kiro have no transcript, so their path is the
proxy. SessionEnd stays wired but is best-effort (deduped by id, so both is safe).
"""
from __future__ import annotations

from pathlib import Path

from cage import claudewire, codexwire, gitcommithook, pointers

SURFACES = ("claude", "codex", "copilot", "kiro")


def install(root: Path, surfaces: tuple[str, ...] | None = None) -> dict:
    picked = surfaces or SURFACES
    out: dict[str, dict] = {}
    if "claude" in picked:
        out["claude"] = claudewire.install(root)
        gh = gitcommithook.install(root)  # PostToolUse capture buffer → sha resolution (plan §3.5)
        if gh["installed"]:
            out["claude"]["git-hooks"] = ", ".join(gh["installed"])
    if "codex" in picked:
        out["codex"] = codexwire.install(root)
    if "copilot" in picked:
        out["copilot"] = pointers.copilot(root)
    if "kiro" in picked:
        out["kiro"] = pointers.kiro(root)
    return out


def status(root: Path) -> dict:
    return {"claude": claudewire.status(root), "codex": codexwire.status(root),
            "copilot": pointers.copilot_status(root), "kiro": pointers.kiro_status(root)}


def backfill_status(root: Path) -> dict:
    """Per-log-bearing-agent: is the reliable SessionStart-backfill capture wired?"""
    return {"claude": claudewire.backfill_status(root),
            "codex": codexwire.backfill_status(root)}
