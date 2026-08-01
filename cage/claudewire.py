"""Wire Cage into Claude Code: the MCP read server (`.mcp.json`).

Hook wiring was removed with the hook machinery — capture is **pull-based**
(`cage import` / capture-on-read), which needs no hooks and works identically
under the CLI and the VS Code extension. `install` still *heals*: any stale
cage hook entries a previous version wrote into `.claude/settings.json` are
stripped (foreign hooks are never touched), so old wiring can't fire dead
`cage hook-*` verbs.

**Portability (plan §5):** `.mcp.json` is committed to git, so it never carries
the wiring machine's absolute cage path — the command references the committed
shim `.cage/bin/cage-run` (`cage/runshim.py`) via the documented
`${CLAUDE_PROJECT_DIR:-.}` env expansion (the `:-.` default is required: the
variable is set in the spawned server's env, not the config parser's).
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths, runshim


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


def _strip_stale_hooks(root: Path) -> int:
    """Remove every cage-owned hook entry from `.claude/settings.json` (previous
    versions wired Stop/SessionStart/SessionEnd/PostToolUse there). Foreign hooks
    are never touched; an empty `hooks` table is left as `{}` (harmless).
    Returns how many entries were removed. Fail-open: an unreadable file is
    left alone."""
    settings = root / ".claude" / "settings.json"
    if not settings.exists():
        return 0
    data = _load(settings)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    removed = 0
    for event, entries in list(hooks.items()):
        kept = []
        for e in entries:
            cmds = [h for h in e.get("hooks", [])
                    if paths.cage_command_tail(h.get("command", "")) is None]
            removed += len(e.get("hooks", [])) - len(cmds)
            if cmds:
                e["hooks"] = cmds
                kept.append(e)
        hooks[event] = kept
        if not kept:
            del hooks[event]
    if removed:
        _save(settings, data)
    return removed


def install(root: Path, *, python_launcher: bool = False) -> dict:
    # python_launcher is accepted for the uniform wire-module contract but unused:
    # the committed `.mcp.json` references the committed shim — the shim variant
    # (written by agents.install) *is* the mode.
    del python_launcher
    mcp = root / ".mcp.json"
    mdata = _load(mcp)
    # Documented `.mcp.json` env expansion; the `:-.` default is required (the var is
    # set in the *server's* env, not the config parser's — see the module docstring).
    portable = f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}"
    old = mdata.get("mcpServers", {}).get("cage", {}).get("command")
    migrated = 1 if (old is not None and old != portable) else 0
    mdata.setdefault("mcpServers", {})["cage"] = {"command": portable, "args": ["mcp"]}
    _save(mcp, mdata)
    stripped = _strip_stale_hooks(root)
    out = {"mcp": str(mcp)}
    if migrated:
        out["migrated"] = "migrated 1 legacy entry → shim"
    if stripped:
        out["hooks-removed"] = f"removed {stripped} stale cage hook entr{'y' if stripped == 1 else 'ies'}"
    return out


def status(root: Path) -> bool:
    mcp = _load(root / ".mcp.json")
    return "cage" in mcp.get("mcpServers", {})
