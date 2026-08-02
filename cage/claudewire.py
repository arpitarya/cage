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


# ── L1 hooks (opt-in, `cage setup --hooks`) ──────────────────────────────────────────
# Claude Code is the only host of the three where cage has itself written and tested
# every event L1 needs, so it is the only one with the full capability set
# (`agents.HOOK_EVENTS`). The committed command references the shim through the same
# documented `${CLAUDE_PROJECT_DIR:-.}` expansion the MCP entry uses — a hook file is a
# committed file, so the no-absolute-path rule binds it identically.
#
# `session_id` and the Bash command arrive on **stdin** as the host's hook payload
# (`hookcmd._payload`), so the wired command carries no per-session interpolation and
# stays byte-identical on every machine and in every session.
_HOOK_EVENTS = (
    ("SessionStart", "session-start", ""),
    ("SessionEnd", "session-end", ""),
    # PreToolUse on Bash: the only verified point where cage can (a) see which agent ran
    # which command — the attestation `adoption`'s half A needs — and (b) BLOCK a paid
    # call before it happens, which is `budget.check`'s first real caller.
    ("PreToolUse", "tool", "Bash"),
    ("PreToolUse", "budget", "Bash"),
)


def _cage_entry(command: str) -> bool:
    return paths.cage_command_tail(command) is not None


def _hook_command(sub: str) -> str:
    return f"${{CLAUDE_PROJECT_DIR:-.}}/{runshim.SHIM_REL} hook {sub} --agent claude"


def _wire_hooks(root: Path, enable: bool) -> int:
    """Install (or remove) cage's hook entries in `.claude/settings.json`.

    Foreign hooks are never touched — this file is shared with whatever else the team
    put there. Rewrites only when the bytes actually change, so `cage setup` twice
    produces no diff. Returns the number of cage entries now wired.
    """
    settings = root / ".claude" / "settings.json"
    data = _load(settings)
    before = json.dumps(data, indent=2, sort_keys=True)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
    # Always strip cage's own entries first: that makes the write idempotent AND makes
    # `--hooks` a two-way switch rather than an append that accumulates duplicates.
    for event, entries in list(hooks.items()):
        kept = []
        for e in entries if isinstance(entries, list) else []:
            cmds = [h for h in e.get("hooks", []) if not _cage_entry(h.get("command", ""))]
            if cmds:
                kept.append({**e, "hooks": cmds})
            elif not e.get("hooks"):
                kept.append(e)
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
    wired = 0
    if enable:
        for event, sub, matcher in _HOOK_EVENTS:
            entry = {"type": "command", "command": _hook_command(sub)}
            bucket = hooks.setdefault(event, [])
            slot = next((e for e in bucket if e.get("matcher", "") == matcher), None)
            if slot is None:
                slot = {"hooks": []} if not matcher else {"matcher": matcher, "hooks": []}
                bucket.append(slot)
            slot.setdefault("hooks", []).append(entry)
            wired += 1
    # Drop an emptied `hooks` table rather than leaving `"hooks": {}` behind: unwiring
    # must return the file to what it was, or every off-switch shows up as a diff.
    if hooks:
        data["hooks"] = hooks
    else:
        data.pop("hooks", None)
    if json.dumps(data, indent=2, sort_keys=True) != before:
        if data:
            _save(settings, data)
        else:
            # Nothing of anyone's left — cage is the only party that could have reduced
            # it to `{}`, and an empty settings file is a diff with no meaning.
            settings.unlink(missing_ok=True)
    return wired


def install(root: Path, *, python_launcher: bool = False, hooks: bool = False) -> dict:
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
    out = {"mcp": str(mcp)}
    if migrated:
        out["migrated"] = "migrated 1 legacy entry → shim"
    if hooks:
        # `_wire_hooks` strips cage's own entries before writing, so it subsumes the
        # heal — running the stale-strip as well would delete what we just wired and
        # report it as removed.
        n = _wire_hooks(root, True)
        out["hooks"] = f"wired {n} L1 hook entr{'y' if n == 1 else 'ies'}"
    elif (stripped := _strip_stale_hooks(root)):
        # Hookless is the default, so this is BOTH the pre-v0.36 migration and the
        # `--hooks` off-switch: whichever wrote them, cage's entries go.
        out["hooks-removed"] = f"removed {stripped} cage hook entr{'y' if stripped == 1 else 'ies'}"
    return out


def hook_status(root: Path) -> int:
    """How many cage L1 hook entries are wired here (0 = hookless, the default)."""
    settings = _load(root / ".claude" / "settings.json")
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0
    return sum(1 for entries in hooks.values() if isinstance(entries, list)
               for e in entries for h in e.get("hooks", [])
               if _cage_entry(h.get("command", "")))


def status(root: Path) -> bool:
    mcp = _load(root / ".mcp.json")
    return "cage" in mcp.get("mcpServers", {})
