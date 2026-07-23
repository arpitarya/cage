"""Wire Cage into GitHub Copilot CLI: lifecycle hooks + the MCP read server + pointer.

Copilot CLI persists a per-session usage log (`~/.copilot/session-state/*/events.jsonl`)
and supports lifecycle hooks, so it imports **its own** usage (`cage import --agent
copilot`) on these events:

- **agentStop** — fires when the agent finishes a run.
- **sessionStart** — backfills the *previous* session (see the timing note below).
- **sessionEnd** — best-effort clean-exit catch.

**Hook location is the *user-level* `~/.copilot/hooks/cage.json` (`$COPILOT_HOME/hooks`),
not the repo `.github/hooks/` — verified empirically (Copilot CLI 1.0.65): a repo-level
hook does not fire for the local CLI even when committed, while the user-level hook
fires reliably.** It's global, so the command guards on a `.cage` being present (via the
no-op in `importcmd.run`) — it imports only in cage-enabled repos, scoped to cwd.

**Timing:** Copilot writes its `session.shutdown` (the usage) as the *last* event, AFTER
every hook fires — so a session's own tokens aren't on disk when its hooks run. Copilot
captures them on the **next** session (the `sessionStart`/`agentStop` import picks up the
prior session's shutdown) — the standard backfill pattern, no cross-agent sweep needed.
The MCP read server goes in `.vscode/mcp.json` and a "consult Cage for spend" pointer in
`.github/copilot-instructions.md` (shared text in `pointers.py`). All idempotent.

**Portability (plan §5):** `.vscode/mcp.json` is project-committed, so it references
the committed shim via `${workspaceFolder}/.cage/bin/cage-run` — VS Code documents
predefined-variable substitution in MCP server config, and documents stdio-server cwd
as defaulting to the workspace folder (code.visualstudio.com MCP config reference).
The user-level `~/.copilot/hooks/cage.json` stays on the *resolved* absolute cage path
(a bare `cage` fails under the extension's PATH — that constraint is unchanged): it is
per-machine by nature and never cloned, so absolute is the robust choice there.

One wire file per agent (mirrors claudewire/codexwire/kirowire) — a new agent gets its
own `<agent>wire.py`.
"""
from __future__ import annotations

from pathlib import Path

from cage import cfgio, paths, pointers, runshim, wiringscan


def _is_ours(command: str) -> bool:
    """A cage entry this hook slot owns: a live `import …` (collapse the superseded
    form) **or** any cage command whose verb the parser rejects. Before the union, a
    dead-verb entry matched neither test, so `_wire_hooks` kept it *and* appended a
    correct one — leaving the dead command still firing on every event."""
    return (paths.is_cage_import_command(command)
            or wiringscan.is_dead_cage_command(command))

# Copilot CLI hooks: {"version":1,"hooks":{<event>:[{"type":"command","bash":…}]}};
# each entry carries both bash + powershell for cross-OS.
REALTIME_EVENT = "agentStop"
HOOK_EVENTS = (REALTIME_EVENT, "sessionStart", "sessionEnd")


def _import_cmd(python_launcher: bool = False) -> tuple[str, str]:
    """(bash, powershell) hook commands — Copilot only, no sweep. Launcher mode
    (docs/restricted-environments.md) goes straight to the interpreter, nothing
    exe-shaped; the hook entry carries both shells so each gets its own form."""
    if python_launcher:
        tail = "-m cage import --agent copilot --since 7d"
        return f"python3 {tail}", f"py -3 {tail}"
    cmd = f"{paths.quoted_cage_bin()} import --agent copilot --since 7d"
    return cmd, cmd


def _hook_path(root: Path | None = None) -> Path:
    # User-level (not repo .github/hooks): the only location the local CLI fires from.
    return paths.copilot_home() / "hooks" / "cage.json"


def _wire_hooks(root: Path, python_launcher: bool = False) -> str:
    """Wire the Copilot self-import into its agentStop/sessionStart/sessionEnd hooks."""
    path = _hook_path(root)
    data = cfgio.load_json(path) if path.exists() else {}
    data.setdefault("version", 1)
    hooks = data.setdefault("hooks", {})
    bash, ps = _import_cmd(python_launcher)
    entry = {"type": "command", "bash": bash, "powershell": ps, "cwd": ".", "timeoutSec": 30}
    for event in HOOK_EVENTS:
        arr = hooks.setdefault(event, [])
        # drop any cage-import entry (stale form / prior all-agent sweep), keep foreign
        # hooks, then add exactly one current Copilot self-import
        arr[:] = [h for h in arr if not _is_ours(h.get("bash", ""))]
        arr.append(entry)
    cfgio.save_json(path, data)
    return str(path)


def _migrate_repo_hook(root: Path) -> None:
    """Strip cage-import entries from a stale repo-level `.github/hooks/cage.json` (the
    old, non-firing location) so re-running setup migrates cleanly to the user-level
    hook. Removes the file if cage owned it entirely; preserves any foreign hooks."""
    legacy = root / ".github" / "hooks" / "cage.json"
    if not legacy.exists():
        return
    data = cfgio.load_json(legacy)
    hooks = data.get("hooks", {})
    for event in list(hooks):
        hooks[event] = [h for h in hooks[event]
                        if not _is_ours(h.get("bash", ""))]
        if not hooks[event]:
            del hooks[event]
    if hooks:
        cfgio.save_json(legacy, data)
    else:
        legacy.unlink(missing_ok=True)


def install(root: Path, *, python_launcher: bool = False) -> dict:
    instr = root / ".github" / "copilot-instructions.md"
    cfgio.upsert_block(instr, pointers.START, pointers.END, pointers.POINTER,
                       default="# Copilot instructions\n")
    mcp = root / ".vscode" / "mcp.json"
    data = cfgio.load_json(mcp)
    # Documented VS Code variable substitution — committed file, no absolute path.
    portable = f"${{workspaceFolder}}/{runshim.SHIM_REL}"
    old = data.get("servers", {}).get("cage", {}).get("command")
    data.setdefault("servers", {})["cage"] = {"type": "stdio", "command": portable,
                                              "args": ["mcp"]}
    cfgio.save_json(mcp, data)
    _migrate_repo_hook(root)
    out = {"instructions": str(instr), "mcp": str(mcp),
           "hooks": _wire_hooks(root, python_launcher)}
    if old is not None and old != portable:
        out["migrated"] = "migrated 1 legacy entry → shim"
    return out


def _event_wired(root: Path, event: str) -> bool:
    path = _hook_path(root)
    if not path.exists():
        return False
    arr = cfgio.load_json(path).get("hooks", {}).get(event, [])
    # Mode-aware: status reads this project's persisted wiring mode so a
    # launcher-mode hook reports wired (and a stale other-mode one doesn't).
    from cage import policy
    launcher = policy.python_launcher(policy.load(paths.Footprint(root).policy))
    return any(h.get("bash") == _import_cmd(launcher)[0] for h in arr)


def backfill_status(root: Path) -> bool:
    """Is the import wired into Copilot's sessionStart hook for this project?"""
    return _event_wired(root, "sessionStart")


def realtime_status(root: Path) -> bool:
    """Is the import wired into Copilot's real-time agentStop hook for this project?"""
    return _event_wired(root, REALTIME_EVENT)


def status(root: Path) -> bool:
    p = root / ".github" / "copilot-instructions.md"
    return p.exists() and pointers.START in p.read_text(encoding="utf-8")
