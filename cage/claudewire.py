"""Wire Cage into Claude Code: Stop/SessionStart/SessionEnd hooks + the MCP server.

Hooks go in the project `.claude/settings.json`. Three complementary capture paths,
all idempotent (`cage import` dedupes by turn uuid), so running them together never
double-counts:

- **Stop** (`cage hook-stop`) is the **real-time** path: it fires when Claude finishes
  each turn and imports that turn's tokens immediately — no wait for session end.
- **SessionStart** backfills the previous Claude session (`cage import-claude
  --project .`), then prints the spend banner (`cage hook-session-start`). Claude only —
  each agent captures its own data via its own wire file; this never imports another
  agent's logs.
- **SessionEnd** (`cage hook-session-end`) stays wired too, but it is best-effort:
  Claude Code only fires it on certain clean terminations, never on a kill/crash/idle.

The MCP read server goes in the project `.mcp.json`. All edits are idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths

# Commands are built with the *resolved* cage path (paths.cage_bin) — a bare `cage`
# fails in GUI-launched agents whose PATH omits ~/.local/bin. SessionStart runs in
# order: backfill the previous Claude session, *then* print the banner.
def BACKFILL() -> str:  # noqa: N802 — kept callable-named for the wiring it feeds
    return f"{paths.cage_bin()} import-claude --project ."


def BANNER() -> str:  # noqa: N802
    return f"{paths.cage_bin()} hook-session-start"


# Stop = real-time per-turn capture; SessionEnd = clean-exit backstop; PostToolUse =
# provenance edit buffer. All additive and idempotent (deduped by command/uuid).
def _simple() -> dict:
    c = paths.cage_bin()
    return {"Stop": f"{c} hook-stop",
            "SessionEnd": f"{c} hook-session-end",
            "PostToolUse": f"{c} hook-post-tool-use"}


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


def _is_stale_import(command: str, current: str) -> bool:
    """A superseded cage import-backfill command (e.g. the old `import-claude --project .`
    before the all-agent heartbeat) — a cage command containing `import` that isn't the
    current backfill. Dropped on re-wire so the slot doesn't accumulate stale forms."""
    return (paths.reresolve_cage_command(command) is not None
            and " import" in command and command != current)


def _wire_session_start(entries: list) -> None:
    """Ensure the all-agent backfill precedes the banner, idempotently. Drops any
    superseded import command, prepends the current backfill, appends the banner."""
    bf = BACKFILL()
    for e in entries:
        e["hooks"] = [h for h in e.get("hooks", [])
                      if not _is_stale_import(h.get("command", ""), bf)]
    entries[:] = [e for e in entries if e.get("hooks")]
    if not _has(entries, bf):
        entries.insert(0, _entry(bf))
    if not _has(entries, BANNER()):
        entries.append(_entry(BANNER()))


def _heal(hooks: dict) -> None:
    """Rewrite any stale cage hook command (bare `cage …`) to the resolved path, and
    drop duplicate cage entries so re-running setup never accumulates them."""
    for event, entries in hooks.items():
        seen: set[str] = set()
        kept = []
        for e in entries:
            new = []
            for h in e.get("hooks", []):
                fixed = paths.reresolve_cage_command(h.get("command", ""))
                if fixed is not None:
                    if fixed in seen:
                        continue
                    seen.add(fixed)
                    h["command"] = fixed
                new.append(h)
            if new or not e.get("hooks"):
                e["hooks"] = new
                kept.append(e)
        hooks[event] = kept


def install(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    data = _load(settings)
    hooks = data.setdefault("hooks", {})
    _heal(hooks)
    _wire_session_start(hooks.setdefault("SessionStart", []))
    for event, command in _simple().items():
        entries = hooks.setdefault(event, [])
        if not _has(entries, command):
            entries.append(_entry(command))
    _save(settings, data)

    mcp = root / ".mcp.json"
    mdata = _load(mcp)
    mdata.setdefault("mcpServers", {})["cage"] = {"command": paths.cage_bin(), "args": ["mcp"]}
    _save(mcp, mdata)
    return {"settings": str(settings), "mcp": str(mcp)}


def _session_start(root: Path) -> list:
    return _load(root / ".claude" / "settings.json").get("hooks", {}).get("SessionStart", [])


def backfill_status(root: Path) -> bool:
    """Is the reliable SessionStart-backfill capture path wired?"""
    return _has(_session_start(root), BACKFILL())


def realtime_status(root: Path) -> bool:
    """Is the real-time per-turn Stop hook wired?"""
    events = _load(root / ".claude" / "settings.json").get("hooks", {})
    return _has(events.get("Stop", []), _simple()["Stop"])


def status(root: Path) -> bool:
    events = _load(root / ".claude" / "settings.json").get("hooks", {})
    start = events.get("SessionStart", [])
    return (_has(start, BACKFILL()) or _has(start, BANNER())
            or any(_has(events.get(e, []), c) for e, c in _simple().items()))
