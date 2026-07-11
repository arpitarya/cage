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

**Portability (plan §5):** both files this module writes are committed to git, so
neither may carry the wiring machine's absolute cage path — commands reference the
committed shim `.cage/bin/cage-run` (`cage/runshim.py`) instead. Per-host mechanism,
verified against the Claude Code docs (hooks.md / mcp.md, 2026-07):

- hooks: `"$CLAUDE_PROJECT_DIR/.cage/bin/cage-run"` — `${CLAUDE_PROJECT_DIR}` is a
  documented hook path placeholder (hook cwd is only "Claude Code's working
  directory", NOT guaranteed to be the project root — the placeholder is the
  reliable form). Shell-form commands run via `sh`, so the quoting is POSIX.
- `.mcp.json`: `${CLAUDE_PROJECT_DIR:-.}/.cage/bin/cage-run` — env expansion in
  `command` is documented, and the docs *require* the `:-.` default here because
  the variable is set in the spawned server's env, not the config parser's.

A bare `cage` (the pre-shim reason for absolute paths) still fails in GUI-launched
agents whose PATH omits ~/.local/bin — the shim carries that resolution at runtime
now, identically on every clone. `_heal` migrates legacy absolute/bare entries to
the shim form on re-setup and reports the count.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths, runshim


def _shim() -> str:
    # Quoted whole: $CLAUDE_PROJECT_DIR may expand to a path with spaces.
    return f'"$CLAUDE_PROJECT_DIR/{runshim.SHIM_REL}"'


# SessionStart runs in order: backfill the previous Claude session, *then* print
# the banner.
def BACKFILL() -> str:  # noqa: N802 — kept callable-named for the wiring it feeds
    return f"{_shim()} import-claude --project ."


def BANNER() -> str:  # noqa: N802
    return f"{_shim()} hook-session-start"


# Stop = real-time per-turn capture; SessionEnd = clean-exit backstop; PostToolUse =
# provenance edit buffer. All additive and idempotent (deduped by command/uuid).
def _simple() -> dict:
    c = _shim()
    return {"Stop": f"{c} hook-stop",
            "SessionEnd": f"{c} hook-session-end",
            "PostToolUse": f"{c} hook-post-tool-use"}


def _reref(command: str) -> str | None:
    """A cage command (binary or shim form) rewritten to the current shim reference,
    preserving the subcommand; None for a foreign hook. Idempotent on the current
    form — healing a healed file changes nothing."""
    tail = paths.cage_command_tail(command)
    if tail is None:
        return None
    return f"{_shim()} {tail}".rstrip()


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
    """A superseded cage import-backfill command (an absolute-path legacy form, or the
    old `import-claude --project .` before the all-agent heartbeat) — a cage command
    containing `import` that isn't the current backfill. Dropped on re-wire so the
    slot doesn't accumulate stale forms."""
    return (paths.cage_command_tail(command) is not None
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


def _heal(hooks: dict) -> int:
    """Rewrite any legacy cage hook command (bare `cage …` or a machine-absolute
    path) to the committed shim reference, and drop duplicate cage entries so
    re-running setup never accumulates them. Returns how many commands were
    migrated (0 on an already-portable file — setup twice stays byte-identical).
    Foreign (non-cage) hooks are never touched."""
    migrated = 0
    for event, entries in hooks.items():
        seen: set[str] = set()
        kept = []
        for e in entries:
            new = []
            for h in e.get("hooks", []):
                fixed = _reref(h.get("command", ""))
                if fixed is not None:
                    if fixed in seen:
                        continue
                    seen.add(fixed)
                    if fixed != h.get("command"):
                        migrated += 1
                    h["command"] = fixed
                new.append(h)
            if new or not e.get("hooks"):
                e["hooks"] = new
                kept.append(e)
        hooks[event] = kept
    return migrated


def install(root: Path) -> dict:
    settings = root / ".claude" / "settings.json"
    data = _load(settings)
    hooks = data.setdefault("hooks", {})
    migrated = _heal(hooks)
    _wire_session_start(hooks.setdefault("SessionStart", []))
    for event, command in _simple().items():
        entries = hooks.setdefault(event, [])
        if not _has(entries, command):
            entries.append(_entry(command))
    _save(settings, data)

    mcp = root / ".mcp.json"
    mdata = _load(mcp)
    # Documented `.mcp.json` env expansion; the `:-.` default is required (the var is
    # set in the *server's* env, not the config parser's — see the module docstring).
    portable = f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL}"
    old = mdata.get("mcpServers", {}).get("cage", {}).get("command")
    if old is not None and old != portable:
        migrated += 1
    mdata.setdefault("mcpServers", {})["cage"] = {"command": portable, "args": ["mcp"]}
    _save(mcp, mdata)
    out = {"settings": str(settings), "mcp": str(mcp)}
    if migrated:
        out["migrated"] = f"migrated {migrated} legacy entr{'y' if migrated == 1 else 'ies'} → shim"
    return out


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
