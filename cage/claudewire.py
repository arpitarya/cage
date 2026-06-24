"""Wire Cage into Claude Code: SessionStart/SessionEnd hooks + the MCP server.

Hooks go in the project `.claude/settings.json` (SessionEnd reads the transcript →
records calls; SessionStart prints the spend banner). The MCP read server goes in
the project `.mcp.json`. Both edits are idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

_HOOK = {"SessionStart": "cage hook-session-start", "SessionEnd": "cage hook-session-end",
        "PostToolUse": "cage hook-post-tool-use"}


def _load(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def _save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _has(entries: list, command: str) -> bool:
    return any(h.get("command") == command
              for e in entries for h in e.get("hooks", []))


def install(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    data = _load(settings)
    hooks = data.setdefault("hooks", {})
    for event, command in _HOOK.items():
        entries = hooks.setdefault(event, [])
        if not _has(entries, command):
            entries.append({"hooks": [{"type": "command", "command": command}]})
    _save(settings, data)

    mcp = root / ".mcp.json"
    mdata = _load(mcp)
    mdata.setdefault("mcpServers", {})["cage"] = {"command": "cage", "args": ["mcp"]}
    _save(mcp, mdata)
    return {"settings": str(settings), "mcp": str(mcp)}


def status(root: Path) -> bool:
    data = _load(root / ".claude" / "settings.json")
    events = data.get("hooks", {})
    return any(_has(events.get(e, []), c) for e, c in _HOOK.items())
