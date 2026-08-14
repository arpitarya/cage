"""L1 agent attestations — `state/attest.jsonl`: the one thing a hook knows and no
pull-based capture can ever learn.

**Stamped, never inferred.** A hook runs *inside* the agent, so it can state which
agent fired it as a fact. Everything else cage knows about agency is a join: a call
row's `agent` comes from *which log file it was parsed out of*, and a savings row from
the graphify interceptor has no agent at all, because the interceptor is a subprocess
that genuinely cannot know its caller ([adoption.py](adoption.py) `NO_LINK`). An
attestation is the only row in the ledger that carries an agent because the agent said
so.

**What it is allowed to fix, and what it is not.** The join key is
`usagelog.args_hash` — the same sha1-of-argv the usage breadcrumb already records — so
an attested tool row resolved **half A of `cage insights adoption`** — a view deleted
in SURFACE-CUT (v0.52), so this store is currently **written by every wired hook and
read by nothing** (work/OPEN-WORK.md, UNREAD-FACTS). Historically it is exact but
agent-blind, into *which* agent invoked the tool. It does **not** resolve half B: a
graphify savings row's id folds in an *answer* hash that no attestation can reconstruct,
so `NO_LINK` stays structurally true and is not quietly narrowed. Overstating this would
re-blend the two unknowns that view exists to separate.

**Two rules the reader must not relax:**

- **A hash claimed by more than one agent is `unknown`, never a pick.** Two agents
  running the identical query is indistinguishable from one, so the honest answer is
  that cage cannot say — the same rule `adoption` already applies to a shared session.
- **Attestation is CLI-only.** Hooks do not fire under a VS Code extension, so a
  VS Code session produces no attestations at all and silently reads as *"that agent
  never invoked it"* unless the limit travels with the number. `LIMIT` is that
  sentence; every surface that renders an attested fact must print it.

Counts-never-content: a command line is **hashed** (it can contain a query, a path, a
prompt), never stored. Fail-open: a write error is swallowed and traced under
`CAGE_DEBUG`, never raised into an agent's turn. Lives in `state/`, so like every other
`state/` file it cannot move a reported number — its former reader prints no
currency, and no money view reads this at all.
"""
from __future__ import annotations

import datetime as _dt
import json
import shlex
from pathlib import Path

from cage import debuglog, paths, usagelog

# The row kinds. Closed on purpose: a new kind is a substrate decision, not a field.
SESSION = "session"   # an agent opened/closed a session
TOOL = "tool"         # an agent invoked a metered tool, by exact args_hash

# Tools whose invocation an attestation may name. Closed, and deliberately the same
# single entry `adoption.USAGE_TOOL` is scoped to — the join is only meaningful where a
# usage breadcrumb exists to join *to*. A second interceptor gains a breadcrumb ⇒ it is
# added here in the same change, never before.
TOOLS = ("graphify",)

# The limit that travels with every attested fact. Hooks are CLI-only — they do not fire
# under a VS Code extension — so an agent used exclusively in VS Code produces no
# attestations and must never be rendered as one that never invoked the tool.
LIMIT = ("attested for CLI sessions only — hooks do not fire under a VS Code "
         "extension, so a VS Code session leaves no attestation")

# What `agent_for` returns when the evidence does not single out one agent.
UNKNOWN = ""


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def _append(root: Path, row: dict) -> bool:
    """Append one row. Fail-open — an attestation is a diagnostic breadcrumb and must
    never be the reason an agent's turn fails."""
    try:
        path = paths.Footprint(root).attest_log
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        return True
    except OSError as exc:
        debuglog.exception(root, "attest.append", exc)
        return False


def record_session(root: Path, *, agent: str, session: str = "", event: str = "") -> bool:
    """Attest that ``agent`` opened or closed a session. ``session`` may be empty (Kiro
    has no session-start trigger and its per-turn hook carries no session id) — the row
    is still worth writing as proof the hook fired at all."""
    if not agent:
        return False
    row = {"kind": SESSION, "agent": agent, "ts": _now()}
    if session:
        row["session"] = session
    if event:
        row["event"] = event
    return _append(root, row)


def record_tool(root: Path, *, agent: str, command) -> bool:
    """Attest that ``agent`` invoked a metered tool, keyed by the argv hash.

    ``command`` is a string or argv list and is **hashed, never stored** — it routinely
    carries the user's query. A command that names no tool in :data:`TOOLS` records
    nothing at all: cage does not keep a log of everything an agent runs.
    """
    argv = _argv(command)
    tool = _tool_of(argv)
    if not agent or not tool:
        return False
    return _append(root, {"kind": TOOL, "agent": agent, "tool": tool,
                          "args_hash": usagelog.args_hash(argv[1:]), "ts": _now()})


def _argv(command) -> list[str]:
    if isinstance(command, (list, tuple)):
        return [str(a) for a in command]
    try:
        return shlex.split(str(command or ""))
    except ValueError:          # unbalanced quotes — not a command cage can read
        return []


def _tool_of(argv: list[str]) -> str:
    """The attestable tool this command invokes, or ``""``.

    Matches the **executable's stem** against :data:`TOOLS`, so `/usr/local/bin/graphify`
    and a bare `graphify` are the same tool — and a command that merely *mentions* one
    (`echo graphify`, `grep graphify src/`) is not, because only argv[0] is consulted.
    """
    if not argv:
        return ""
    stem = Path(argv[0]).name
    for suffix in (".cmd", ".exe", ".bat"):
        if stem.lower().endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem if stem in TOOLS else ""


def read(root: Path) -> list[dict]:
    """Every attestation row. Tolerates a truncated tail, like every other cage read."""
    path = paths.Footprint(root).attest_log
    out: list[dict] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue            # a torn last write, not a reason to lose the rest
        if isinstance(row, dict):
            out.append(row)
    return out


def tool_agents(root: Path, tool: str) -> dict[str, str]:
    """``{args_hash: agent}`` for one tool — the exact join into the usage breadcrumb.

    **A hash two agents both attested resolves to** :data:`UNKNOWN`, never to one of
    them: identical queries from two agents are indistinguishable, so "cage cannot say"
    is the only true answer. Same rule `adoption` applies to a shared session.
    """
    claims: dict[str, set[str]] = {}
    for row in read(root):
        if row.get("kind") != TOOL or row.get("tool") != tool:
            continue
        ah, agent = row.get("args_hash") or "", row.get("agent") or ""
        if ah and agent:
            claims.setdefault(ah, set()).add(agent)
    return {ah: (next(iter(a)) if len(a) == 1 else UNKNOWN) for ah, a in claims.items()}


def agents_seen(root: Path) -> set[str]:
    """Every agent that has attested anything here — the set a view may honestly say
    *"cage has hook evidence for"*. An agent absent from it has no attestations, which
    (see :data:`LIMIT`) is not the same as having invoked nothing."""
    return {r.get("agent") for r in read(root) if r.get("agent")} - {None, ""}
