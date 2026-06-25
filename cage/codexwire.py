"""Wire Cage into Codex CLI: a project SessionStart hook + the MCP read server.

Codex CLI reads a project-level `.codex/hooks.json` using the *same* schema as Claude
Code's hooks (`{"SessionStart":[{"hooks":[{"type":"command","command":…}]}]}`), so the
reliable capture path is symmetric: a **SessionStart** hook backfills the previous
session by importing the rollouts Codex already writes to `~/.codex/sessions`
(`cage import --agent codex --since 7d`). Idempotent, fail-open, deduped by call id.

The MCP read server lives in the global `~/.codex/config.toml` (`tomllib` is read-only,
so the `[mcp_servers.cage]` block is appended as guarded text). Both edits are idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths

_BLOCK = '\n[mcp_servers.cage]\ncommand = "cage"\nargs = ["mcp"]\n'
_MARKER = "[mcp_servers.cage]"

# Codex sessions are global (not project-scoped like Claude's), so bound the scan; the
# import dedupes by id, so the window only caps cost, never correctness.
BACKFILL = "cage import --agent codex --since 7d"


def _config(root: Path | None) -> Path:
    return paths.codex_home() / "config.toml"


def _hooks_path(root: Path) -> Path:
    return root / ".codex" / "hooks.json"


def _has(entries: list, command: str) -> bool:
    return any(h.get("command") == command
              for e in entries for h in e.get("hooks", []))


def _install_mcp(root: Path | None) -> str:
    cfg = _config(root)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    if _MARKER not in text:
        cfg.write_text(text.rstrip() + "\n" + _BLOCK if text else _BLOCK.lstrip(),
                       encoding="utf-8")
    return str(cfg)


def _install_hook(root: Path | None) -> str | None:
    if root is None:
        return None
    path = _hooks_path(root)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    entries = data.setdefault("hooks", {}).setdefault("SessionStart", [])
    if not _has(entries, BACKFILL):
        entries.append({"hooks": [{"type": "command", "command": BACKFILL}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(path)


def install(root: Path | None = None) -> dict:
    out = {"config": _install_mcp(root)}
    hook = _install_hook(root)
    if hook:
        out["hooks"] = hook
    return out


def backfill_status(root: Path | None) -> bool:
    """Is the reliable SessionStart-backfill capture path wired for this project?"""
    if root is None:
        return False
    path = _hooks_path(root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return _has(data.get("hooks", {}).get("SessionStart", []), BACKFILL)


def status(root: Path | None = None) -> bool:
    cfg = _config(root)
    mcp = cfg.exists() and _MARKER in cfg.read_text(encoding="utf-8")
    return mcp or backfill_status(root)
