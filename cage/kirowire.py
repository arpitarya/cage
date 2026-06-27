"""Wire Cage into Kiro: an Agent Hook + the MCP read server + the steering pointer.

Kiro persists a (coarse) per-call usage log (`kiro.kiroagent/dev_data/
tokens_generated.jsonl`) and supports Agent Hooks, so it imports **its own** usage
(`cage import --agent kiro`) via `.kiro/hooks/cage.kiro.hook`.

Kiro's hook file is **one hook per file** — the file *is* the hook object
(`{name, version, description, when:{type}, then:{type, command}}`), not a
`{"version":…,"hooks":[…]}` container. The only trigger we can use is
**`agentStop`** (Kiro has no session-start trigger — its events are agentStop /
promptSubmit / pre|postToolUse / file* / pre|postTaskExecution / manual). A single
`agentStop` hook is enough for both roles: each fire re-imports the *whole* log
(deduped by call id), so the next turn's `agentStop` backfills anything the prior
one missed — the same self-backfilling pattern Copilot uses.

Kiro only — each agent captures its own data; no cross-agent sweep. The MCP read server
goes in `.kiro/settings/mcp.json` and a "consult Cage for spend" pointer in
`.kiro/steering/cage.md` (shared text in `pointers.py`). The proxy stays the
higher-fidelity fallback where Kiro's log is too thin. The command uses the *resolved*
cage path (a bare `cage` fails under the Kiro IDE's PATH). All idempotent.

One wire file per agent (mirrors claudewire/codexwire/copilotwire) — a new agent gets
its own `<agent>wire.py`.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import cfgio, paths, pointers

_TRIGGER = "agentStop"  # Kiro's only fit-for-purpose trigger; no session-start exists


def _import_cmd() -> str:
    return f"{paths.cage_bin()} import --agent kiro"  # Kiro only — no cross-agent sweep


def _hook_spec() -> dict:
    """The single Kiro Agent Hook (one hook == one file). Fires when the agent finishes a
    turn; re-imports Kiro's whole usage log (deduped), so it is both the real-time and the
    backfill path."""
    return {
        "name": "cage-meter",
        "version": "1.0.0",
        "description": "Import Kiro LLM usage into the cage ledger after each agent turn",
        "when": {"type": _TRIGGER},
        "then": {"type": "runCommand", "command": _import_cmd()},
    }


def _hook_path(root: Path) -> Path:
    return root / ".kiro" / "hooks" / "cage.kiro.hook"


def _wire_hooks(root: Path) -> str:
    """Write the cage-owned `cage.kiro.hook` (one hook per file). The file belongs to cage
    entirely, so we overwrite it wholesale — that heals any stale form (the old
    `{"version":"v1","hooks":[…]}` container, a SessionStart hook Kiro never fires, or a
    prior bin path) — idempotent."""
    path = _hook_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(_hook_spec(), indent=2) + "\n", encoding="utf-8")
    return str(path)


def install(root: Path) -> dict:
    steering = root / ".kiro" / "steering" / "cage.md"
    cfgio.upsert_block(steering, pointers.START, pointers.END, pointers.POINTER,
                       default="# Cage\n")
    mcp = root / ".kiro" / "settings" / "mcp.json"
    data = cfgio.load_json(mcp)
    data.setdefault("mcpServers", {})["cage"] = {"command": paths.cage_bin(), "args": ["mcp"],
                                                 "disabled": False}
    cfgio.save_json(mcp, data)
    return {"steering": str(steering), "mcp": str(mcp), "hooks": _wire_hooks(root)}


def _hook_wired(root: Path) -> bool:
    path = _hook_path(root)
    if not path.exists():
        return False
    try:
        data = cfgio.load_json(path)
    except ValueError:
        return False
    return (data.get("when", {}).get("type") == _TRIGGER
            and data.get("then", {}).get("command") == _import_cmd())


def backfill_status(root: Path) -> bool:
    """Is Kiro's backfill path wired? Kiro has no session-start trigger; the `agentStop`
    hook re-imports the whole log each turn, so it *is* the backfill (next turn covers what
    the prior one missed)."""
    return _hook_wired(root)


def realtime_status(root: Path) -> bool:
    """Is Kiro's real-time capture Agent Hook (the `agentStop` trigger) wired?"""
    return _hook_wired(root)


def status(root: Path) -> bool:
    mcp = root / ".kiro" / "settings" / "mcp.json"
    return mcp.exists() and "cage" in cfgio.load_json(mcp).get("mcpServers", {})
