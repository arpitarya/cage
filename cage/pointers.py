"""Wire Cage into Copilot + Kiro — instruction/steering pointers + MCP config.

Neither exposes a usage transcript, so metering is the proxy (`cage proxy` /
`cage meter -- <cmd>`); these writers add the *read* surface (the MCP server) and a
pointer telling the agent to consult Cage for spend. All edits are idempotent.
"""
from __future__ import annotations

from pathlib import Path

from cage import cfgio

START, END = "<!-- cage:start -->", "<!-- cage:end -->"
_POINTER = """## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).
- For spend / savings questions, prefer the `cage` MCP tools (`cage_report`,
  `cage_attrib`, `cage_budget`) over guessing.
- To meter this agent's own calls, run it under `cage meter -- <cmd>` or point its
  base URL at `cage proxy`.
- The ledger stores token *counts* only — never prompt bodies."""


def copilot(root: Path) -> dict:
    instr = root / ".github" / "copilot-instructions.md"
    cfgio.upsert_block(instr, START, END, _POINTER, default="# Copilot instructions\n")
    mcp = root / ".vscode" / "mcp.json"
    data = cfgio.load_json(mcp)
    data.setdefault("servers", {})["cage"] = {"type": "stdio", "command": "cage",
                                              "args": ["mcp"]}
    cfgio.save_json(mcp, data)
    return {"instructions": str(instr), "mcp": str(mcp)}


def kiro(root: Path) -> dict:
    steering = root / ".kiro" / "steering" / "cage.md"
    cfgio.upsert_block(steering, START, END, _POINTER, default="# Cage\n")
    mcp = root / ".kiro" / "settings" / "mcp.json"
    data = cfgio.load_json(mcp)
    data.setdefault("mcpServers", {})["cage"] = {"command": "cage", "args": ["mcp"],
                                                 "disabled": False}
    cfgio.save_json(mcp, data)
    return {"steering": str(steering), "mcp": str(mcp)}


def copilot_status(root: Path) -> bool:
    p = root / ".github" / "copilot-instructions.md"
    return p.exists() and START in p.read_text(encoding="utf-8")


def kiro_status(root: Path) -> bool:
    return (root / ".kiro" / "settings" / "mcp.json").exists() and "cage" in \
        cfgio.load_json(root / ".kiro" / "settings" / "mcp.json").get("mcpServers", {})
