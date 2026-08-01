"""Wire Cage into GitHub Copilot: the MCP read server (`.vscode/mcp.json`).

Hook wiring and the instructions pointer were removed with the hook machinery —
capture is **pull-based** (`cage import --agent copilot` over
`~/.copilot/session-state/*/events.jsonl` and the VS Code `chatSessions/`
store), which needs no hooks. `install` still *heals*: a cage-owned
`~/.copilot/hooks/cage.json` written by a previous version is deleted (it is
entirely cage's file), and a stale repo-level `.github/hooks/cage.json` is
stripped of cage entries (foreign hooks preserved).

**Portability (plan §5):** `.vscode/mcp.json` is project-committed, so it
references the committed shim via `${workspaceFolder}/.cage/bin/cage-run` —
VS Code documents predefined-variable substitution in MCP server config.
"""
from __future__ import annotations

from pathlib import Path

from cage import cfgio, paths, runshim


def _strip_legacy_hooks(root: Path) -> int:
    """Remove hook wiring a previous version installed. The user-level
    `~/.copilot/hooks/cage.json` is wholly cage-owned → deleted if present.
    A repo-level `.github/hooks/cage.json` may carry foreign hooks → cage
    entries stripped, file removed only when nothing is left. Fail-open."""
    removed = 0
    user = paths.copilot_home() / "hooks" / "cage.json"
    try:
        if user.exists():
            user.unlink()
            removed += 1
    except OSError:
        pass
    legacy = root / ".github" / "hooks" / "cage.json"
    if legacy.exists():
        try:
            data = cfgio.load_json(legacy)
            hooks = data.get("hooks", {})
            for event in list(hooks):
                before = len(hooks[event])
                hooks[event] = [h for h in hooks[event]
                                if paths.cage_command_tail(h.get("bash", "")) is None]
                removed += before - len(hooks[event])
                if not hooks[event]:
                    del hooks[event]
            if hooks:
                cfgio.save_json(legacy, data)
            else:
                legacy.unlink(missing_ok=True)
        except (OSError, ValueError):
            pass
    return removed


def install(root: Path, *, python_launcher: bool = False) -> dict:
    del python_launcher  # committed file references the shim; the shim *is* the mode
    mcp = root / ".vscode" / "mcp.json"
    data = cfgio.load_json(mcp)
    # Documented VS Code variable substitution — committed file, no absolute path.
    portable = f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    old = data.get("servers", {}).get("cage", {}).get("command")
    data.setdefault("servers", {})["cage"] = {"type": "stdio", "command": portable,
                                              "args": ["mcp"]}
    cfgio.save_json(mcp, data)
    stripped = _strip_legacy_hooks(root)
    out = {"mcp": str(mcp)}
    if old is not None and old != portable:
        out["migrated"] = "migrated 1 legacy entry → shim"
    if stripped:
        out["hooks-removed"] = f"removed {stripped} stale cage hook entr{'y' if stripped == 1 else 'ies'}"
    return out


def status(root: Path) -> bool:
    mcp = root / ".vscode" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("servers", {})
