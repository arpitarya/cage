"""Wire Cage into Claude Code: SessionStart/SessionEnd hooks + the MCP server.

Hooks go in the project `.claude/settings.json`. SessionStart is the **reliable
default** capture path: it first backfills the previous session by importing the
on-disk transcript (`cage import-claude --project .`), then prints the spend banner
(`cage hook-session-start`) — so the banner reflects the just-backfilled spend.
SessionEnd (`cage hook-session-end`) stays wired too, but it is best-effort: Claude
Code only fires it on certain clean terminations, never on a kill/crash/idle. Both
running is safe — `cage import` dedupes by call id. The MCP read server goes in the
project `.mcp.json`. All edits are idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

# SessionStart runs in order: backfill the previous session, *then* print the banner.
BACKFILL = "cage import-claude --project ."
BANNER = "cage hook-session-start"
# Best-effort, additive — kept wired so a clean exit still records in real time.
_SIMPLE = {"SessionEnd": "cage hook-session-end",
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


def _entry(command: str) -> dict:
    return {"hooks": [{"type": "command", "command": command}]}


def _wire_session_start(entries: list) -> None:
    """Ensure backfill precedes the banner, idempotently. Backfill is prepended so it
    runs first; the banner is appended. Re-running adds nothing (deduped by command)."""
    if not _has(entries, BACKFILL):
        entries.insert(0, _entry(BACKFILL))
    if not _has(entries, BANNER):
        entries.append(_entry(BANNER))


def install(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    data = _load(settings)
    hooks = data.setdefault("hooks", {})
    _wire_session_start(hooks.setdefault("SessionStart", []))
    for event, command in _SIMPLE.items():
        entries = hooks.setdefault(event, [])
        if not _has(entries, command):
            entries.append(_entry(command))
    _save(settings, data)

    mcp = root / ".mcp.json"
    mdata = _load(mcp)
    mdata.setdefault("mcpServers", {})["cage"] = {"command": "cage", "args": ["mcp"]}
    _save(mcp, mdata)
    return {"settings": str(settings), "mcp": str(mcp)}


def _session_start(root: Path) -> list:
    return _load(root / ".claude" / "settings.json").get("hooks", {}).get("SessionStart", [])


def backfill_status(root: Path) -> bool:
    """Is the reliable SessionStart-backfill capture path wired?"""
    return _has(_session_start(root), BACKFILL)


def status(root: Path) -> bool:
    events = _load(root / ".claude" / "settings.json").get("hooks", {})
    start = events.get("SessionStart", [])
    return (_has(start, BACKFILL) or _has(start, BANNER)
            or any(_has(events.get(e, []), c) for e, c in _SIMPLE.items()))
