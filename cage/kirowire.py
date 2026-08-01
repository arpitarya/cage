"""Wire Cage into Kiro: the MCP read server (`.kiro/settings/mcp.json`).

Hook wiring and the steering pointer were removed with the hook machinery —
capture is **pull-based** (`cage import --agent kiro` over
`kiro.kiroagent/dev_data/tokens_generated.jsonl`; the proxy stays the
higher-fidelity fallback where Kiro's log is too thin). `install` still
*heals*: a cage-owned `.kiro/hooks/cage.kiro.hook` written by a previous
version is deleted.

**Portability — the ONE documented exception:** Kiro spawns MCP servers from
its *install directory* (not the workspace; kirodotdev/Kiro #6525) and supports
no variable substitution in `command` (open feature request #5659), so a
relative or variable-based reference provably breaks. The entry keeps the
*resolved* absolute cage path (a bare `cage` fails under the Kiro IDE's PATH) —
advise adding `.kiro/settings/mcp.json` to `.gitignore`; `cage doctor` says so
rather than this module silently shipping a broken relative path.
"""
from __future__ import annotations

from pathlib import Path

from cage import cfgio, paths


def _strip_legacy_hook(root: Path) -> int:
    """Delete the cage-owned `.kiro/hooks/cage.kiro.hook` a previous version
    wrote (one hook per file — the file is entirely cage's). Fail-open."""
    path = root / ".kiro" / "hooks" / "cage.kiro.hook"
    try:
        if path.exists():
            path.unlink()
            return 1
    except OSError:
        pass
    return 0


def install(root: Path, *, python_launcher: bool = False) -> dict:
    import os
    mcp = root / ".kiro" / "settings" / "mcp.json"
    data = cfgio.load_json(mcp)
    # Absolute by necessity (module docstring): Kiro spawns MCP servers from its
    # install dir with no workspace variable. Launcher mode (restricted
    # endpoints) swaps the exe for the interpreter; the file stays per-machine
    # (gitignore-advised), so the OS at write time picks the launcher name.
    if python_launcher:
        server = ({"command": "py", "args": ["-3", "-m", "cage", "mcp"], "disabled": False}
                  if os.name == "nt" else
                  {"command": "python3", "args": ["-m", "cage", "mcp"], "disabled": False})
    else:
        server = {"command": paths.cage_bin(), "args": ["mcp"], "disabled": False}
    data.setdefault("mcpServers", {})["cage"] = server
    cfgio.save_json(mcp, data)
    stripped = _strip_legacy_hook(root)
    out = {"mcp": str(mcp)}
    if stripped:
        out["hooks-removed"] = "removed 1 stale cage hook file"
    return out


def status(root: Path) -> bool:
    mcp = root / ".kiro" / "settings" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("mcpServers", {})
