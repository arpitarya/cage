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
import os
import re
from pathlib import Path

from cage import paths, runshim, wiringscan


def _is_ours(command: str) -> bool:
    """A cage entry this slot owns: a live `import …` (collapse the superseded form
    into the current one) **or** any cage command whose verb the parser rejects (heal
    a v0.28-orphaned `import-codex`). The union is what preserves that healing now
    that `is_cage_import_command` matches the verb exactly instead of the substring
    `" import"` — see tests/test_wiringscan.py."""
    return (paths.is_cage_import_command(command)
            or wiringscan.is_dead_cage_command(command))


_MARKER = "[mcp_servers.cage]"
# The whole cage-written MCP block, for in-place mode/path healing — cage always
# writes exactly this shape, so the match never spans a foreign table.
_BLOCK_RE = re.compile(r'\[mcp_servers\.cage\]\ncommand = "[^"\n]*"\nargs = \[[^\]\n]*\]\n')

# Codex's hooks import Codex only — each agent captures its own data; no cross-agent
# sweep. Self-locating shim form: portable across clones (see the module docstring).
def BACKFILL() -> str:  # noqa: N802 — callable-named for the wiring it feeds
    return runshim.selflocating_command("import --agent codex --since 7d")


def _toml_safe_bin() -> str:
    """`cage_bin()` for a TOML basic string — backslashes are escapes there, so a
    Windows path is written with forward slashes (Windows execs both forms)."""
    return paths.cage_bin().replace("\\", "/")


def _mcp_block(python_launcher: bool = False) -> str:
    if python_launcher:
        # Interpreter-only (docs/restricted-environments.md). This file is
        # user-level (~/.codex) — per-machine by nature, so the OS at write time
        # picks the right launcher name.
        cmd, args = (("py", '"-3", "-m", "cage", "mcp"') if os.name == "nt"
                     else ("python3", '"-m", "cage", "mcp"'))
        return f'\n[mcp_servers.cage]\ncommand = "{cmd}"\nargs = [{args}]\n'
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


def _install_mcp(root: Path | None, python_launcher: bool = False) -> str:
    cfg = _config(root)
    cfg.parent.mkdir(parents=True, exist_ok=True)
    text = cfg.read_text(encoding="utf-8") if cfg.exists() else ""
    block = _mcp_block(python_launcher)
    if _MARKER not in text:
        cfg.write_text(text.rstrip() + "\n" + block if text else block.lstrip(),
                       encoding="utf-8")
    elif block.lstrip("\n") not in text:
        # Heal in place: a stale bare-`cage`, a moved binary, or the other wiring
        # mode's block — replace just the cage-written block, foreign tables kept.
        healed, n = _BLOCK_RE.subn(lambda _m: block.lstrip("\n"), text, count=1)
        if n:
            cfg.write_text(healed, encoding="utf-8")
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
        # prior sweep) **and every dead-verb cage entry** (the v0.9 `import-codex`
        # form, which the exact-verb import rule no longer matches), keep foreign
        # hooks, then add exactly one current per-agent import. Idempotent; a dropped
        # non-current form counts as migrated.
        for e in entries:
            old = [h.get("command", "") for h in e.get("hooks", [])
                   if _is_ours(h.get("command", ""))]
            migrated += sum(1 for c in old if c != cmd)
            e["hooks"] = [h for h in e.get("hooks", [])
                          if not _is_ours(h.get("command", ""))]
        entries[:] = [e for e in entries if e.get("hooks")]
        entries.append({"hooks": [{"type": "command", "command": cmd}]})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return str(path), migrated


def install(root: Path | None = None, *, python_launcher: bool = False) -> dict:
    out = {"config": _install_mcp(root, python_launcher)}
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
