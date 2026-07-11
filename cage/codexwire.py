"""Wire Cage into Codex CLI: project Stop + SessionStart hooks + the MCP read server.

Codex CLI reads a project-level `.codex/hooks.json` using the *same* schema and the
*same* lifecycle events as Claude Code's hooks, so capture is symmetric with Claude:

- **Stop** (turn-scoped) is the **real-time** path — it fires when Codex finishes each
  turn and re-imports the rollouts Codex writes to `~/.codex/sessions`, so the current
  session's spend lands as it happens (not only when the next session starts).
- **SessionStart** backfills the previous session on startup — the safety net for
  whatever Stop missed (e.g. a hard kill).

Both run the same idempotent command (`cage import --agent codex --since 7d`), deduped
by call id, so firing on every turn never double-counts.

The MCP read server lives in the global `~/.codex/config.toml` (`tomllib` is read-only,
so the `[mcp_servers.cage]` block is appended as guarded text). Both edits are idempotent.

**Portability (plan §5):** `.codex/hooks.json` is project-committed, so it must never
carry the wiring machine's absolute cage path. Codex documents that hook commands run
with the **session cwd** — possibly a subdirectory, NOT guaranteed to be the repo root
— and its docs explicitly recommend resolving from the git root rather than using a
repo-relative path. So the committed command is the self-locating shim one-liner
(`runshim.selflocating_command`): `git rev-parse --show-toplevel` → exec the committed
`.cage/bin/cage-run` → exit 0 if either is missing (fail-open, identical bytes on
every machine). `~/.codex/config.toml` is user-level — per-machine by nature, the
resolved absolute path stays the robust choice there (unchanged).
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths, runshim

_MARKER = "[mcp_servers.cage]"

# Codex's hooks import Codex only — each agent captures its own data; no cross-agent
# sweep. Self-locating shim form: portable across clones (see the module docstring).
def BACKFILL() -> str:  # noqa: N802 — callable-named for the wiring it feeds
    return runshim.selflocating_command("import --agent codex --since 7d")


def _toml_safe_bin() -> str:
    """`cage_bin()` for a TOML basic string — backslashes are escapes there, so a
    Windows path is written with forward slashes (Windows execs both forms)."""
    return paths.cage_bin().replace("\\", "/")


def _mcp_block() -> str:
    return f'\n[mcp_servers.cage]\ncommand = "{_toml_safe_bin()}"\nargs = ["mcp"]\n'


# Stop = real-time per-turn capture; SessionStart = startup backfill safety net.
# Same import command on both — dedup by call id makes running both safe.
CAPTURE_EVENTS = ("Stop", "SessionStart")


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
        block = _mcp_block()
        cfg.write_text(text.rstrip() + "\n" + block if text else block.lstrip(),
                       encoding="utf-8")
    elif '\ncommand = "cage"\n' in text:  # heal a stale bare-`cage` MCP command
        cfg.write_text(text.replace('\ncommand = "cage"\n',
                                    f'\ncommand = "{_toml_safe_bin()}"\n'), encoding="utf-8")
    return str(cfg)


def _install_hook(root: Path | None) -> tuple[str | None, int]:
    if root is None:
        return None, 0
    path = _hooks_path(root)
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    hooks = data.setdefault("hooks", {})
    cmd = BACKFILL()
    migrated = 0
    for event in CAPTURE_EVENTS:
        entries = hooks.setdefault(event, [])
        # Drop every cage-import entry (a stale per-agent/absolute-path import or a
        # prior sweep), keep foreign hooks, then add exactly one current per-agent
        # import. Idempotent; a dropped non-current form counts as migrated.
        for e in entries:
            old = [h.get("command", "") for h in e.get("hooks", [])
                   if paths.is_cage_import_command(h.get("command", ""))]
            migrated += sum(1 for c in old if c != cmd)
            e["hooks"] = [h for h in e.get("hooks", [])
                          if not paths.is_cage_import_command(h.get("command", ""))]
        entries[:] = [e for e in entries if e.get("hooks")]
        entries.append({"hooks": [{"type": "command", "command": cmd}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(path), migrated


def install(root: Path | None = None) -> dict:
    out = {"config": _install_mcp(root)}
    hook, migrated = _install_hook(root)
    if hook:
        out["hooks"] = hook
    if migrated:
        out["migrated"] = f"migrated {migrated} legacy entr{'y' if migrated == 1 else 'ies'} → shim"
    return out


def _event_has(root: Path | None, event: str) -> bool:
    """Is the import command wired into ``event`` of this project's hooks.json?"""
    if root is None:
        return False
    path = _hooks_path(root)
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return False
    return _has(data.get("hooks", {}).get(event, []), BACKFILL())


def backfill_status(root: Path | None) -> bool:
    """Is the SessionStart-backfill capture path wired for this project?"""
    return _event_has(root, "SessionStart")


def realtime_status(root: Path | None) -> bool:
    """Is the real-time per-turn Stop hook wired for this project?"""
    return _event_has(root, "Stop")


def status(root: Path | None = None) -> bool:
    cfg = _config(root)
    mcp = cfg.exists() and _MARKER in cfg.read_text(encoding="utf-8")
    return mcp or backfill_status(root)
