"""`cage insights adoption` — do the agents you wired actually **use** the tools you
gave them? (proposal `work/archive/v0.40-insights-adoption.proposal.md`)

The differentiating question no cost dashboard answers: same workspace, same install,
three agents — which of them reached for the tool unprompted? Cage can answer it only
because the **usage breadcrumb** (`usagelog.py`) exists independently of receipts, so
*"ran and cage filed nothing"* is distinguishable from *"never ran"*.

**The whole value of this view is the boundary between three different unknowns**, and
blurring any two makes it worse than nothing:

1. **never invoked** — no evidence of an invocation at all;
2. **invoked, no saving captured** — a usage row whose recorded ``outcome`` is not
   ``receipt`` (a capture/parse gap, already a *field*, never re-derived here);
3. **invoked, but cage cannot say by whom** — a savings row with no joinable agent.

So the view is **two halves that are never blended into one number**:

- **A · invocations + outcomes** — from usage rows. Exact, no join, but **agent-blind**:
  a usage row is ``ts · op · args_hash · exit · ms · outcome · route`` and carries **no
  agent field**. Half A therefore never names an agent.
- **B · per-agent attribution** — from savings rows that carry a *joinable link* to a
  call, whose ``agent`` is the answer. A shim/native savings row stamps an **empty
  session on purpose** (`graphifymeter`: the shim runs as a subprocess and genuinely
  cannot know which agent spawned it), so those rows are **agent-unknown by
  construction** — reported as such, never folded into an "other" bucket and never
  attributed by timestamp proximity.

**"Never invoked" is never asserted, and it has two strengths.** *No evidence of
invocation* is only sound when **every** savings row found an agent; with even one
agent-unknown row on the table, that row could belong to any agent, so the most that can
honestly be said is *no savings row was attributed to them*. The view picks between the
two (`NO_EVIDENCE` / `NOT_ATTRIBUTED`) rather than printing the strong claim loosely —
saying "copilot never invoked it" beside a pile of unattributable rows would blend
unknowns 1 and 3, which is the precise failure this module exists to prevent.

**Empty half B renders, it is never suppressed** (the decision this view had to make):
if every invocation came through the shim, the honest output is the B heading plus an
explicit refusal naming the count and the cause. Suppressing it would make *"cage cannot
attribute these"* indistinguishable from *"cage has no per-agent answer at all"* — which
is precisely the conflation the view exists to prevent.

**No currency anywhere in this view.** Usage rows are diagnostic-only: never priced,
never read by a derived *money* view — an invariant pinned byte-identically by
`tests/test_graphify_usage.py`. This view **counts** them and prints no dollar figure at
all, so that invariant is intact and stays intact; the next reader should not mistake a
count for a lapse. Nothing here calls `convert`/`receiptprice`/`prices`.

**Surface is deliberately not a dimension** (K4, [finding](work/regression/2026-08-01-finding-surface-attribution-is-agent-dependent.md)):
Claude Code's CLI and its VS Code extension share one store with no distinguishing
marker, so a `--by surface` split here would invent a fact. The view answers *which
agent*, which is derivable, and declines the surface question by not asking it.
"""
from __future__ import annotations

from pathlib import Path

from cage import agents as _agents
from cage import ledger, paths, usagelog
from cage.usagelog import OUTCOMES

# The one tool with a usage breadcrumb today. Half A is scoped to it by the substrate,
# not by choice — `usagelog` writes `state/graphify-usage.jsonl` and nothing else does.
# A second interceptor gains a breadcrumb ⇒ this becomes a loop, and the heading follows.
USAGE_TOOL = "graphify"

# How a savings row reached an agent. Both are exact joins into `calls`; they are named
# per row rather than merged, so a reader can see which link carried the attribution.
VIA_CALL = "call"        # the row links a call id → that call's agent
VIA_SESSION = "session"  # the row carries a session id some call also carries

# Why a savings row has no agent. Split because they are different facts with different
# fixes — one is structural and permanent, the other is a capture gap worth chasing.
NO_LINK = "no-link"      # neither call nor session: the shim cannot know its caller
UNJOINED = "unjoined"    # a link is present but nothing in `calls` carries it
AMBIGUOUS = "ambiguous"  # the session resolves, but to MORE THAN ONE agent

# What an agent's absence from half B is allowed to mean. The strong claim requires that
# EVERY savings row found an agent — otherwise an unattributed row could be theirs.
NO_EVIDENCE = "no-evidence"          # sound: nothing is left unattributed
NOT_ATTRIBUTED = "not-attributed"    # the weaker, confounded claim

# `schema.make_call`'s default agent — the library metering adapter, never an agent
# surface, so it can never be "an agent that hasn't adopted the tool".
LIB_AGENT = "lib"


def _is_legacy_human(r: dict) -> bool:
    """A pre-0.36 Tier-1 row (`report._is_legacy_human`'s predicate). The human axis was
    amputated in v0.36; such a row is not a *tool* adoption fact, so it is excluded here
    exactly as the money views exclude it."""
    return r.get("tool") == "human" or r.get("unit") == "minutes"


def _tally() -> dict:
    return {o: 0 for o in OUTCOMES}


def _usage_half(root: Path, since: str | None) -> dict:
    """Half A — invocation totals and outcomes, straight off the usage breadcrumb.

    The per-outcome counts come from the recorded ``outcome`` field, never re-derived:
    "ran and cage missed it" is already a written verdict (`usagelog.OUTCOMES`), and
    re-deriving it from the receipts would be a second, disagreeing answer."""
    present = paths.Footprint(root).usage_log.exists()
    rows = ledger.since(usagelog.read(root), since)
    outcomes, by_op, by_route = _tally(), {}, {}
    for r in rows:
        o = r.get("outcome", "")
        if o in outcomes:
            outcomes[o] += 1
        for bucket, key in ((by_op, r.get("op") or "—"),
                            (by_route, r.get("route") or "—")):
            grp = bucket.setdefault(key, {"runs": 0, "outcomes": _tally()})
            grp["runs"] += 1
            if o in grp["outcomes"]:
                grp["outcomes"][o] += 1
    def _flat(bucket: dict, field: str) -> list[dict]:
        return [{field: k, "runs": v["runs"], "outcomes": v["outcomes"]}
                for k, v in sorted(bucket.items(), key=lambda kv: (-kv[1]["runs"], kv[0]))]
    return {"tool": USAGE_TOOL, "present": present, "runs": len(rows),
            "outcomes": outcomes, "by_op": _flat(by_op, "op"),
            "by_route": _flat(by_route, "route"),
            "by_agent": _attested(root, rows)}


def _attested(root: Path, rows: list[dict]) -> dict:
    """Half A's **agent** breakdown — the one thing the usage breadcrumb alone cannot
    give, supplied by the opt-in L1 hooks ([attest.py](attest.py)).

    A usage row is `ts · op · args_hash · exit · ms · outcome · route` and carries no
    agent field, which is why half A has always been *exact but agent-blind*. A hook
    runs **inside** the agent, so an attestation states the agent as a fact; the join is
    on `args_hash`, an exact key both sides already record. **Not proximity, not the
    most recent agent, not a guess.**

    Three honesty rules, none of them optional:

    · **Absent ⇒ absent.** No attestations (the hookless default) returns
      ``{"present": False}`` and the renderer emits nothing at all — so L1 being off
      leaves this view byte-identical, which is the floor's whole promise.
    · **A hash two agents attested is `unattested`, never a pick** — identical queries
      from two agents are indistinguishable (`attest.tool_agents` enforces it).
    · **`unattested` is never read as "no agent"**: hooks are CLI-only, so a VS Code
      run leaves no attestation while being a perfectly real invocation.
    """
    from cage import attest
    claims = attest.tool_agents(root, USAGE_TOOL)
    if not claims:
        return {"present": False, "agents": [], "unattested": len(rows)}
    tally: dict[str, int] = {}
    unattested = 0
    for r in rows:
        agent = claims.get(r.get("args_hash") or "", attest.UNKNOWN)
        if agent:
            tally[agent] = tally.get(agent, 0) + 1
        else:
            unattested += 1
    agents = [{"agent": a, "runs": n} for a, n in
              sorted(tally.items(), key=lambda kv: (-kv[1], kv[0]))]
    return {"present": True, "agents": agents, "unattested": unattested}


def _agent_half(root: Path, since: str | None) -> dict:
    """Half B — per-agent attribution, from savings rows that join to a call.

    Two exact join paths, tried in order and **named on the row** so neither is passed
    off as the other: a linked receipt's ``call`` id resolves to that call's agent
    directly; otherwise a non-empty ``session`` resolves through the calls that share it.
    A row reaching neither is agent-unknown, with the *reason* recorded — never guessed
    at from a timestamp, and never bucketed as "other"."""
    all_calls = ledger.calls(root)          # unfiltered: an in-window row may link an older call
    by_id, by_session, seen = {}, {}, set()
    for c in all_calls:
        surface = _agents.row_surface(c.get("agent")) or ""
        if cid := c.get("id"):
            by_id[cid] = surface
        # Only NAMED agents join the session set: an unstamped call is an unknown, not a
        # competing agent, and letting it in would make an otherwise clean session look
        # ambiguous and lose a real attribution.
        if (sess := c.get("session")) and surface:
            by_session.setdefault(sess, set()).add(surface)
        # `lib` is `make_call`'s default for a library-metered call — a metering adapter,
        # not an agent that could adopt anything. Every other name (including a retired
        # agent still in the ledger) counts: dropping it would hide a real row.
        if surface and surface != LIB_AGENT:
            seen.add(surface)

    # `read_kind`'s `since` skips whole MONTH shards before loading; it is a read
    # optimisation, not a row filter. Half A row-filters with `ledger.since(...)`,
    # so without this one `--since` answered two different questions in one table.
    # Same double-filter roi/report/chats already do.
    rows = [r for r in ledger.since(ledger.receipts(root, since=since), since)
            if not _is_legacy_human(r)]
    attributed: dict[tuple[str, str], dict] = {}
    unknown: dict[tuple[str, str], int] = {}
    for r in rows:
        tool = r.get("tool", "") or "—"
        agent, via = "", ""
        if (cid := r.get("call")) and by_id.get(cid):
            agent, via = by_id[cid], VIA_CALL
        elif (sess := r.get("session")) and (found := by_session.get(sess)):
            # A session with more than one agent cannot pick one — that is genuinely
            # ambiguous, so it stays unknown rather than resolving to an arbitrary name.
            if len(found) == 1:
                agent, via = next(iter(found)), VIA_SESSION
        if agent:
            grp = attributed.setdefault((agent, tool), {"rows": 0, "via": set()})
            grp["rows"] += 1
            grp["via"].add(via)
        else:
            # Three distinct facts, never merged: nothing to join on · a link that
            # matches nothing · a link that matches too much. Calling the third a
            # "capture gap worth chasing" was a FALSE FACT — nothing was missed, the
            # session genuinely belongs to more than one agent and cage refuses to pick.
            if not (r.get("call") or r.get("session")):
                reason = NO_LINK
            elif len(by_session.get(r.get("session", ""), ())) > 1:
                reason = AMBIGUOUS
            else:
                reason = UNJOINED
            unknown[(tool, reason)] = unknown.get((tool, reason), 0) + 1

    seen_agents = sorted(seen)
    with_savings = {a for a, _t in attributed}
    attributed_n = sum(g["rows"] for g in attributed.values())
    return {
        "rows": len(rows),
        "attributed": attributed_n,
        # Which claim the no-agent list supports. The strong one holds ONLY when every
        # savings row found an agent; one unattributed row could belong to any of them.
        "no_evidence_claim": (NO_EVIDENCE if attributed_n == len(rows)
                              else NOT_ATTRIBUTED),
        "agents": [{"agent": a, "tool": t, "rows": g["rows"], "via": sorted(g["via"])}
                   for (a, t), g in sorted(attributed.items(),
                                           key=lambda kv: (kv[0][0], kv[0][1]))],
        "unknown": [{"tool": t, "reason": why, "rows": n}
                    for (t, why), n in sorted(unknown.items())],
        # Absence of evidence, never proof of non-use — the phrasing is load-bearing.
        "no_evidence": [a for a in seen_agents if a not in with_savings],
        "agents_with_calls": seen_agents,
    }


def summarize(root: Path, since: str | None = None) -> dict:
    """The one data structure both renderers consume (the same-numbers-by-construction
    rule). Deterministic: no clock, no random — ordering is by count then name."""
    return {"since": since, "usage": _usage_half(root, since),
            "attribution": _agent_half(root, since)}


# ── rendering ────────────────────────────────────────────────────────────────

_HEAD = [o.replace("-", " ") for o in OUTCOMES]

_EMPTY = """No tool invocations and no savings receipts recorded yet.

next: cage import        pull every agent's usage into the ledger
      cage doctor        check the graphify interceptor is wired and live"""

_UNKNOWN_TEXT = {
    NO_LINK: ("carry no call and no session\n"
              "    — the interceptor runs as a subprocess and cannot know which agent "
              "spawned it\n    (structural, not a capture gap)"),
    UNJOINED: ("carry a link no call in the ledger matches\n"
               "    — the tool's run was captured but the agent turn behind it was not\n"
               "    (a capture gap worth chasing)"),
    AMBIGUOUS: ("carry a session more than one agent's calls share\n"
                "    — nothing is missing; cage will not resolve it to an arbitrary "
                "name\n    (not a capture gap — there is no single right answer)"),
}

# The two phrasings for "this agent has no attributable savings row". They are NOT
# interchangeable, and picking the wrong one is the exact conflation this view exists to
# prevent: the strong claim is only sound when **every** savings row found an agent. With
# even one unattributed row on the table, that row could belong to any agent, so the most
# that can be said is "none was attributed to them" — never "no evidence it ran".
_NO_EVIDENCE = ("· no evidence of invocation: {agents}\n"
                "    — calls in this window, zero savings rows, and every savings row "
                "that exists\n    was attributed. Absence of evidence, not proof of "
                "non-use: a run cage never\n    saw looks identical to one that never "
                "happened.")
_NOT_ATTRIBUTED = ("· no savings row attributed to: {agents}\n"
                   "    — this is NOT evidence they never invoked the tool: {n:,} row(s) "
                   "above are\n    agent-unknown and could belong to any of them.")


def _outcome_table(title: str, field: str, groups: list[dict]) -> str:
    from cage import render
    rows = [[g[field], f"{g['runs']:,}", *(f"{g['outcomes'][o]:,}" for o in OUTCOMES)]
            for g in groups]
    rights = set(range(1, len(OUTCOMES) + 2))
    return render.table([title, "runs", *_HEAD], rows, rights=rights)


def render_adoption(data: dict) -> str:
    """The two halves, visibly separate, with every unknown named. Counts only — this
    renderer never formats a dollar figure, and there is none in the payload to format."""
    from cage.display import Footer
    u, a = data["usage"], data["attribution"]
    if not u["runs"] and not a["rows"]:
        return _EMPTY
    win = f" (since {data['since']})" if data["since"] else ""
    out = [f"Adoption — which tools your agents actually invoke{win}",
           "  counts only; usage rows are diagnostic and are never priced", ""]

    # ── A · invocations ───────────────────────────────────────────────────────
    out.append(f"A · invocations — {u['tool']} usage breadcrumb (exact, agent-blind)")
    out.append("")
    if not u["runs"]:
        out.append(f"  no {u['tool']} runs recorded" +
                   ("" if u["present"] else " — no usage breadcrumb on disk yet") +
                   ("" if not data["since"] else " in this window"))
    else:
        out.append(_outcome_table("op", "op", u["by_op"]))
        out.append("")
        out.append(_outcome_table("route", "route", u["by_route"]))
        # The agent breakdown exists ONLY when the opt-in L1 hooks attested it. With no
        # attestations the block is absent entirely rather than empty — half A is
        # honestly agent-blind without them, and an empty table would suggest otherwise.
        if u["by_agent"]["present"]:
            from cage import render
            out.append("")
            out.append("  by agent — attested by an L1 hook (stamped, not inferred)")
            out.append(render.table(
                ["agent", "runs"],
                [[g["agent"], f"{g['runs']:,}"] for g in u["by_agent"]["agents"]],
                rights={1}))
    out.append("")

    # ── B · per-agent attribution ─────────────────────────────────────────────
    out.append("B · per-agent attribution — savings rows joined to a call's agent")
    out.append("")
    if not a["rows"]:
        out.append("  no savings rows in this window — nothing to attribute")
    elif not a["agents"]:
        # The stated decision: render the refusal, never an empty table and never nothing.
        out.append(f"  per-agent attribution unavailable — none of the {a['rows']:,} "
                   f"savings rows\n  carry a link cage can resolve to an agent "
                   f"(see the breakdown below)")
    else:
        from cage import render
        rows = [[g["agent"], g["tool"], f"{g['rows']:,}", "+".join(g["via"])]
                for g in a["agents"]]
        out.append(render.table(["agent", "tool", "rows", "joined via"], rows,
                                rights={2}))

    foot = Footer()
    if u["by_agent"]["present"]:
        # Every attested number carries its limit. Hooks are CLI-only, so a run made
        # from a VS Code session is real, invisible here, and must not be read as an
        # agent that did nothing — the ADOPT half-B problem, one layer up.
        from cage import attest
        foot.caveat(f"· agent breakdown: {attest.LIMIT}")
        if (n := u["by_agent"]["unattested"]):
            foot.gap(f"· {n:,} run(s) have no attestation — either made before hooks "
                     f"were wired, from a VS Code session, or attested by more than "
                     f"one agent.\n    Not evidence that no agent ran them.")
    if a["rows"]:
        pct = round(100.0 * a["attributed"] / a["rows"])
        foot.caveat(f"· coverage: {a['attributed']:,} of {a['rows']:,} savings rows "
                    f"({pct}%) are agent-attributable")
    for grp in a["unknown"]:
        foot.gap(f"· agent-unknown: {grp['rows']:,} {grp['tool']} row(s) "
                 f"{_UNKNOWN_TEXT[grp['reason']]}")
    if a["no_evidence"]:
        # Which claim is honest depends on whether anything is left unattributed —
        # see `_NO_EVIDENCE` / `_NOT_ATTRIBUTED`. Never assert the strong one loosely.
        unattributed = a["rows"] - a["attributed"]
        template = (_NO_EVIDENCE if a["no_evidence_claim"] == NO_EVIDENCE
                    else _NOT_ATTRIBUTED)
        foot.gap(template.format(agents=", ".join(a["no_evidence"]), n=unattributed))
    if (block := foot.render()):
        out.append("")
        out.append(block)
    return "\n".join(out)


def render_csv(data: dict) -> str:
    """CSV over the same `summarize()` payload as the text view (one structure, two
    renderers — they cannot disagree). The halves stay distinguishable in a flat table
    through the ``section``/``dimension`` columns; a cell that does not apply to a row is
    **empty**, never a zero, so a spreadsheet can't read "not applicable" as "none". No
    money column exists here by construction. Column contract: docs/FORMULAS.md §2.12."""
    from cage import csvout
    head = ["section", "dimension", "key", "agent", "tool", "rows", "joined_via",
            "reason", *[o.replace("-", "_") for o in OUTCOMES]]
    u, a = data["usage"], data["attribution"]
    rows: list[list] = []

    def _usage_row(dim: str, key: str, runs: int, outcomes: dict) -> list:
        return ["usage", dim, key, None, u["tool"], runs, None, None,
                *[outcomes[o] for o in OUTCOMES]]

    rows.append(_usage_row("total", "all", u["runs"], u["outcomes"]))
    rows += [_usage_row("op", g["op"], g["runs"], g["outcomes"]) for g in u["by_op"]]
    rows += [_usage_row("route", g["route"], g["runs"], g["outcomes"])
             for g in u["by_route"]]
    blanks = [None] * len(OUTCOMES)
    # Half A's attested agent split. Present only when L1 hooks attested something, so a
    # hookless project's CSV is byte-identical to before. `unattested` keeps its own row
    # with the reason spelled out — CSV never gates, and a dropped caveat here would let
    # a spreadsheet read "the rest belong to nobody".
    if u["by_agent"]["present"]:
        rows += [["usage", "agent", g["agent"], g["agent"], u["tool"], g["runs"],
                  "attest", None, *blanks] for g in u["by_agent"]["agents"]]
        rows.append(["usage", "agent-unattested", "", None, u["tool"],
                     u["by_agent"]["unattested"], None,
                     "no attestation (pre-hooks, VS Code session, or claimed by >1 agent)",
                     *blanks])
    rows += [["attribution", "agent", g["agent"], g["agent"], g["tool"], g["rows"],
              "+".join(g["via"]), None, *blanks] for g in a["agents"]]
    rows += [["attribution", "agent-unknown", "", None, g["tool"], g["rows"], None,
              g["reason"], *blanks] for g in a["unknown"]]
    rows += [["attribution", a["no_evidence_claim"], ag, ag, None, 0, None,
              a["no_evidence_claim"], *blanks] for ag in a["no_evidence"]]
    return csvout.table(head, rows)
