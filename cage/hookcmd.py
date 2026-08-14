"""`cage hook <event>` — the ONE entrypoint every agent's L1 hook calls.

L1 is **opt-in** (`cage setup --hooks`) and exists for the three things pull-based
capture structurally cannot do. It is deliberately *not* built for real-time capture:
capture already works with no hooks at all, and a layer that duplicated it would be a
double-write risk for no gain ([test_floor.py](../tests/test_floor.py) is the standing
proof that adding this layer moves no number).

  1. **Agent identity** — a hook runs inside the agent, so `--agent` is a *fact*
     ([attest.py](attest.py)). Every subcommand requires it and none infers it.
  2. **Auto task-close** — `session-end` closes the tasks this session opened, which
     unblocks `compare` / `estimate` / `calibration` in one stroke; they are starved
     for exactly one reason, that nobody runs `cage task outcome`.
L1 bought a third thing until USAGE-ONLY (ADR 0011): **budget enforcement**, the one
path in cage that could stop a call *before* it happened. It went with the money
subsystem — a ceiling needs a currency — taking the `budget` event, the `BLOCK` exit
code and the only non-zero exit this entrypoint had.

**Fail-open is absolute here, and now unconditionally.** A hook runs in the agent's
turn, so any internal failure exits **0** and is traced under `CAGE_DEBUG` — a broken
cage must never break someone's session. **Every event exits 0**; there is no longer any
exception to that rule.

**Auto-close never claims success.** `tasks.record(outcome=...)` and the outcome store
(`outcomes.py`, `.cage/outcomes.json`, ok|redo) are *different axes*: closing a task
makes it eligible for comparison, while ok/redo is a judgement only a human or an
explicit `cage task outcome` can make. So the session-end hook writes ``outcome =
"auto"`` — closed for `compare`/`estimate`/`calibration`, and **invisible to the outcome
store**, which holds only rows that say ok or redo. A hook that stamped `ok` would
silently inflate the success rate of every session that merely *ended*.

**CLI-only.** Hooks do not fire under a VS Code extension, so everything above applies
to CLI sessions only (`attest.LIMIT`) — a caveat that must travel with every number
built on it, never be discovered later.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import attest, debuglog

# Every event this entrypoint accepts. Closed — the wiring writes exactly these, and
# `wiringscan` checks them against the live parser, so an unlisted one is a dead verb.
EVENTS = ("session-start", "session-end", "tool")

# `tasks.jsonl` outcome for a hook-closed task. NOT "ok": see the module docstring.
AUTO = "auto"


def _root() -> Path:
    from cage import paths
    return paths.resolve_root()


def _sweep(root: Path, *, force: bool = False) -> None:
    """The same all-agent pull sweep every other capture trigger runs — never a
    separate hook-only write path, so hook capture and pull capture cannot produce two
    rows for one turn (ids dedupe in `hooks.append_new`; proven in test_hooks_layer).

    ``force`` skips the read throttle and is set by `_session_end` **only** — see there.
    `_session_start` stays throttled deliberately: it has no deadline, a session's calls
    do not exist yet, and the next read or the session's own end will sweep anyway. Do
    not "fix" the divergence by forcing both; the throttle is what keeps a warm ledger
    from being re-scanned on every turn."""
    from cage import importcmd
    importcmd.ensure_captured(root, force=force)


def _open_tasks(root: Path, session: str) -> list[str]:
    """Tasks with a call in this session and no outcome yet.

    The join is the **session id the hook was handed** — an exact key, never the most
    recent task or the closest timestamp. With no session id (Kiro hands none), this
    returns nothing and the caller declines rather than guessing.
    """
    if not session:
        return []
    # P5: `calls` is the only kind carrying a `task`, and claude/copilot stopped writing
    # it. An open task is therefore only findable for a consumer/custom/kiro row — stated
    # in TASK-GRAIN-SPINE, and NOT patched with a timestamp-proximity guess. The caller
    # already declines rather than guessing when this returns nothing, so the degradation
    # is a narrower true answer, never a wrong one.
    from cage import ledger, tasks
    closed = {tid for tid, row in tasks.read(root).items() if row.get("outcome")}
    seen: list[str] = []
    for c in ledger.calls(root):
        tid = c.get("task") or ""
        if tid and c.get("session") == session and tid not in closed and tid not in seen:
            seen.append(tid)
    return seen


def run(args) -> int:
    """Dispatch one hook event. **Always 0** — the budget block was the only non-zero
    exit and it went with the money subsystem (USAGE-ONLY, ADR 0011)."""
    event = getattr(args, "event", "")
    agent = getattr(args, "agent", "") or ""
    try:
        root = _root()
    except Exception as exc:  # noqa: BLE001 — no root, no hook; never break the turn
        debuglog.exception(Path.cwd(), f"hook.{event}: root", exc)
        return 0
    if not agent:
        # Identity is the entire point of this layer; without it there is nothing
        # honest to record. Say so on stderr (the agent sees it) and exit 0 anyway.
        print("cage hook: --agent is required (identity is stamped, never inferred)",
              file=sys.stderr)
        return 0
    try:
        if event == "session-start":
            return _session_start(root, args, agent)
        if event == "session-end":
            return _session_end(root, args, agent)
        if event == "tool":
            return _tool(root, args, agent)
        debuglog.event(root, event="hook", agent=agent, produced=False,
                       skip_reason=f"unknown-event:{event}")
    except Exception as exc:  # noqa: BLE001 — fail-open: a hook never breaks a turn
        debuglog.exception(root, f"hook.{event}", exc)
    return 0


def _session_start(root: Path, args, agent: str) -> int:
    attest.record_session(root, agent=agent, session=_session(args), event="start")
    _sweep(root)
    return 0


def _session_end(root: Path, args, agent: str) -> int:
    """Attest, sweep, then close what this session opened — in that order, because the
    sweep is what makes the session's calls (and therefore its tasks) visible at all."""
    session = _session(args)
    attest.record_session(root, agent=agent, session=session, event="end")
    # FORCED, unlike `_session_start`. `_open_tasks` two lines down can only see tasks
    # whose calls are already in the ledger, and a session ends exactly once — a
    # throttled no-op here has no later trigger to make up for it, so any read in the
    # preceding throttle window left this session's tasks silently un-closable.
    _sweep(root, force=True)
    from cage import tasks
    closed = []
    for tid in _open_tasks(root, session):
        # `outcome="auto"` — closed for cost comparison, NOT a success claim, and the
        # quality store is deliberately not written (module docstring).
        if tasks.record(root, tid, outcome=AUTO):
            closed.append(tid)
    if closed:
        print(f"· cage: auto-closed {len(closed)} task(s) at session end "
              f"(outcome 'auto' — not a success claim)", file=sys.stderr)
    elif session:
        debuglog.event(root, event="hook", agent=agent, produced=False,
                       skip_reason="no-open-task-in-session")
    else:
        # Kiro's per-turn hook carries no session id, so there is no exact key to close
        # on. Declining is the contract (`agents` parity note), not a silent no-op.
        debuglog.event(root, event="hook", agent=agent, produced=False,
                       skip_reason="no-session-id-declined-autoclose")
    return 0


def _tool(root: Path, args, agent: str) -> int:
    """Attest one tool invocation. The command comes from `--command` or, when the host
    passes its hook payload on stdin (Claude Code does), from that JSON — **hashed
    either way, stored never**."""
    tool_input = _payload().get("tool_input")
    from_stdin = tool_input.get("command") if isinstance(tool_input, dict) else None
    command = getattr(args, "command", "") or from_stdin or ""
    attest.record_tool(root, agent=agent, command=command)
    return 0


_PAYLOAD: dict | None = None


def _payload() -> dict:
    """The host's hook payload, read from stdin **at most once** (stdin is a stream;
    two readers would race for the same bytes). Anything unexpected reads as empty —
    a hook that cannot parse its own input records nothing rather than guessing."""
    global _PAYLOAD
    if _PAYLOAD is None:
        _PAYLOAD = {}
        try:
            if sys.stdin is not None and not sys.stdin.isatty():
                data = json.loads(sys.stdin.read() or "{}")
                if isinstance(data, dict):
                    _PAYLOAD = data
        except Exception:  # noqa: BLE001 — never break a turn over an unreadable payload
            _PAYLOAD = {}
    return _PAYLOAD


def _session(args) -> str:
    """The session id, from the flag first and the host payload second. **Only an
    exact id closes a task** — with neither, `_open_tasks` returns nothing and
    `session-end` declines rather than closing the most recent task by proximity."""
    return (getattr(args, "session", "") or ""
            or str(_payload().get("session_id") or ""))
