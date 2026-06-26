"""Wire Cage into Kiro: Agent Hooks + the MCP read server + the steering pointer.

Kiro persists a (coarse) per-call usage log (`kiro.kiroagent/dev_data/
tokens_generated.jsonl`) and supports Agent Hooks, so it imports **its own** usage
(`cage import --agent kiro`) via `.kiro/hooks/cage.kiro.hook` (v1 JSON:
`{"version":"v1","hooks":[…]}`):

- **Stop** — the real-time per-turn path (`cage-meter`).
- **SessionStart** — startup backfill safety net (`cage-backfill`).

Kiro only — each agent captures its own data; no cross-agent sweep. The MCP read server
goes in `.kiro/settings/mcp.json` and a "consult Cage for spend" pointer in
`.kiro/steering/cage.md` (shared text in `pointers.py`). The proxy stays the
higher-fidelity fallback where Kiro's log is too thin. Commands use the *resolved* cage
path (a bare `cage` fails under the Kiro IDE's PATH). All idempotent.

One wire file per agent (mirrors claudewire/codexwire/copilotwire) — a new agent gets
its own `<agent>wire.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import cfgio, paths, pointers


def _import_cmd() -> str:
    return f"{paths.cage_bin()} import --agent kiro"  # Kiro only — no cross-agent sweep


def _hooks_spec() -> tuple[dict, ...]:
    cmd = _import_cmd()
    return (
        {"name": "cage-meter", "trigger": "Stop",
         "action": {"type": "command", "command": cmd}, "timeout": 30, "enabled": True},
        {"name": "cage-backfill", "trigger": "SessionStart",
         "action": {"type": "command", "command": cmd}, "timeout": 30, "enabled": True},
    )


def _hook_path(root: Path) -> Path:
    return root / ".kiro" / "hooks" / "cage.kiro.hook"


def _wire_hooks(root: Path) -> str:
    """Wire the Kiro `Stop` (real-time) + `SessionStart` (backfill) Agent Hooks, both
    importing Kiro's own log. Drops any stale cage-import hook (an old all-agent sweep
    or a prior bin path) and re-adds the current spec — idempotent."""
    path = _hook_path(root)
    data = cfgio.load_json(path) if path.exists() else {}
    data.setdefault("version", "v1")
    hooks = data.setdefault("hooks", [])
    hooks[:] = [h for h in hooks  # drop cage-import hooks (any stale form); keep foreign
                if not paths.is_cage_import_command(h.get("action", {}).get("command", ""))]
    hooks.extend(dict(h) for h in _hooks_spec())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(path)


def install(root: Path) -> dict:
    steering = root / ".kiro" / "steering" / "cage.md"
    cfgio.upsert_block(steering, pointers.START, pointers.END, pointers.POINTER,
                       default="# Cage\n")
    mcp = root / ".kiro" / "settings" / "mcp.json"
    data = cfgio.load_json(mcp)
    data.setdefault("mcpServers", {})["cage"] = {"command": paths.cage_bin(), "args": ["mcp"],
                                                 "disabled": False}
    cfgio.save_json(mcp, data)
    return {"steering": str(steering), "mcp": str(mcp), "hooks": _wire_hooks(root)}


def _trigger_wired(root: Path, trigger: str) -> bool:
    path = _hook_path(root)
    if not path.exists():
        return False
    try:
        data = cfgio.load_json(path)
    except ValueError:
        return False
    return any(h.get("trigger") == trigger and h.get("action", {}).get("command") == _import_cmd()
               for h in data.get("hooks", []))


def backfill_status(root: Path) -> bool:
    """Is the Kiro SessionStart-backfill Agent Hook wired for this project?"""
    return _trigger_wired(root, "SessionStart")


def realtime_status(root: Path) -> bool:
    """Is the Kiro real-time capture Agent Hook (Stop trigger) wired for this project?"""
    return _trigger_wired(root, "Stop")


def status(root: Path) -> bool:
    mcp = root / ".kiro" / "settings" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("mcpServers", {})
