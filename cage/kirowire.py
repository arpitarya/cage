"""Wire Cage into Kiro: the MCP read server (`.kiro/settings/mcp.json`).

Hook wiring and the steering pointer were removed with the hook machinery —
capture is **pull-based** (`cage import --agent kiro` over
`kiro.kiroagent/dev_data/tokens_generated.jsonl`, plus the CLI store; that log is
coarse and there is no higher-fidelity fallback left — `proxy.py`/`metercmd.py` were
deleted in SURFACE-CUT, v0.50). `install` still
*heals*: a cage-owned `.kiro/hooks/cage.kiro.hook` written by a previous
version is deleted.

**Portability — resolved by going PATH-FREE (v0.41, was the ONE exception).** Kiro
spawns MCP servers from its *install directory* (not the workspace;
kirodotdev/Kiro #6525) and substitutes no variables in `command` (#5659), so
`.cage/bin/cage-run` and `${workspaceFolder}` both provably break — which is why
this file carried the wiring machine's absolute cage path and had to be
gitignored. **A third form has neither problem:** `python3 -m cage mcp` contains
no path at all, relative or absolute. It resolves through PATH like any
interpreter, so the file is byte-identical on every machine and **committed** like
the other two agents' — a teammate's clone gets working MCP.

**The honest trade, named in `cage doctor` rather than buried:** the path-free form
depends on *which* `python3` resolves. If cage lives in a virtualenv that
interpreter is not in, the server silently fails to start — the exact failure class
this project has already paid for twice. So `doctor`'s `kiro-mcp` check resolves
that interpreter and asks it to import cage, and names the fix when it cannot.

**Windows is a stated limit, not a silent one.** `python3` is not reliably on PATH
there (the python.org installer ships `py.exe`, not `python3.exe`), and a *committed*
file can carry only one spelling — so the default is `python3` and Windows machines
are told, by doctor, to run `cage setup --python-launcher`, which writes the `py -3`
form for that machine. That entry *is* machine-specific: a mixed-OS team gitignores
this one file, which is strictly better than every machine gitignoring it.
"""
from __future__ import annotations

from pathlib import Path

from cage import cfgio, runshim


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


# The committed default: no path of any kind, so the bytes are identical on every
# machine. `PATH_FREE` is the one enumeration — the writer, the migration check and
# doctor's `kiro-mcp` probe all read it, so none can drift from the others.
PATH_FREE = {"command": "python3", "args": ["-m", "cage", "mcp"], "disabled": False}
# Launcher mode on Windows, where `python3` is not reliably on PATH. Machine-specific
# by nature (see the docstring) — chosen only when the caller asks for it.
PATH_FREE_WIN = {"command": "py", "args": ["-3", "-m", "cage", "mcp"], "disabled": False}


# ── L1 hooks (opt-in, `cage setup --hooks`) ──────────────────────────────────────────
# **Kiro's hook file is ONE HOOK PER FILE** — `{name, version, description, when: {type},
# then: {type, command}}`, not a `hooks[]` container like the other two. The file is
# wholly cage's, so enabling writes it and disabling deletes it.
#
# **Kiro has no session-start trigger.** The single `agentStop` hook fires per turn and
# carries no session id, so it is wired to `session-end`, which:
#   · attests the agent (identity — the part that works), and
#   · **declines to auto-close a task**, because with no session id there is no exact
#     key and closing "the most recent open task" would be attribution by proximity,
#     which this project forbids everywhere else.
# That gap is stated in `agents.HOOK_GAPS` and printed, never left to be discovered.
#
# The command uses `runshim.selflocating_command` — Kiro documents neither the hook cwd
# nor a workspace variable, so the committed one-liner locates the repo root via git and
# exits 0 when either the repo or the shim is missing (fail-open, machine-independent).
#
# That one-liner is **POSIX shell**, and Kiro's hook schema has no interpreter field, so
# on a Windows host with no POSIX shell this hook does not run. It is **named, not
# twinned** (`agents.HOOK_SHELL_LIMIT`): this file is committed and byte-compared before
# writing, so a per-OS command would churn a committed diff on every `cage setup` in a
# mixed-OS team — the same trade already settled for Kiro's path-free MCP entry. Capture
# is unaffected; L1 is not for capture.
_HOOK_REL = ".kiro/hooks/cage.kiro.hook"


def _hook_document() -> dict:
    return {
        "name": "cage",
        "version": "1",
        "description": ("Cage: attest which agent ran this turn and capture token "
                        "usage. Fail-open — never blocks the turn."),
        "when": {"type": "agentStop"},
        "then": {"type": "command",
                 "command": runshim.selflocating_command(
                     "hook session-end --agent kiro")},
    }


def _wire_hooks(root: Path, enable: bool) -> int:
    """Write or delete `.kiro/hooks/cage.kiro.hook`. The file is entirely cage's (one
    hook per file), so there is nothing foreign to preserve. Byte-compared before
    writing so `cage setup` twice produces no diff."""
    path = root / ".kiro" / "hooks" / "cage.kiro.hook"
    if not enable:
        path.unlink(missing_ok=True)
        return 0
    cfgio.save_json(path, _hook_document())
    return 1


def hook_status(root: Path) -> int:
    """1 when cage's L1 hook is wired here, else 0 (hookless is the default)."""
    return 1 if (root / ".kiro" / "hooks" / "cage.kiro.hook").exists() else 0


def install(root: Path, *, python_launcher: bool = False, hooks: bool = False) -> dict:
    import os
    mcp = root / ".kiro" / "settings" / "mcp.json"
    data = cfgio.load_json(mcp)
    # Path-free by default (module docstring) — committed, byte-identical everywhere.
    # Launcher mode on Windows is the ONLY branch that varies by machine, and only
    # because `python3` does not resolve there; POSIX launcher mode is already the
    # default form, so the two modes converge rather than fork.
    server = dict(PATH_FREE_WIN if (python_launcher and os.name == "nt") else PATH_FREE)
    prev = data.setdefault("mcpServers", {}).get("cage") or {}
    migrated = bool(prev) and prev.get("command") not in (PATH_FREE["command"],
                                                          PATH_FREE_WIN["command"])
    data["mcpServers"]["cage"] = server
    cfgio.save_json(mcp, data)
    out = {"mcp": str(mcp)}
    if migrated:
        out["migrated"] = (f"kiro MCP {prev.get('command')!r} → path-free "
                           f"`{server['command']} -m cage mcp` (now committable)")
    if hooks:
        _wire_hooks(root, True)
        out["hooks"] = (f"wired 1 L1 hook ({_HOOK_REL}, agentStop) — "
                        "identity only; no session id, so no auto task-close")
    elif _strip_legacy_hook(root):
        # Hookless is the default: this is BOTH the `--hooks` off-switch and the
        # pre-v0.36 heal — the file is wholly cage's either way.
        out["hooks-removed"] = "removed 1 cage hook file"
    return out


def status(root: Path) -> bool:
    mcp = root / ".kiro" / "settings" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("mcpServers", {})
