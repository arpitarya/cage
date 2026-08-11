"""The copilot pricing ladder — rung 1, recorded credits × your configured rate
(COPILOT-CREDITS; verdict C of docs/archive/*copilot-pricing-basis.compare.md).

A copilot row's USD resolves by a four-rung ladder (rung 0 below), one rung per row,
best signal first — the exact shape `receiptprice` uses for call-less token receipts:

1. **credits × rate** — the row carries a recorded `credits` figure AND
   `[billing.<agent>] usd_per_credit` is set. This module.
2. **tokens × price-table** — the existing exact/alias/family matching, unchanged
   (`policy.price_match`). Reached whenever rung 1 has nothing to say.
3. **UNPRICED** — loud, counted, with runnable fix lines, exactly as today.

**Rung 0 — billed on another row** (`billed_with`, REV-CREDITS defect 2). Some providers
compute ONE billed figure over a GROUP of calls: a copilot-CLI `session.shutdown` reports
`totalPremiumRequests` across **every** model in it. That figure lands on one carrier row,
and every other row of the group carries a link to it. Such a row prices at **$0.00 on
the credits basis** — *priced, elsewhere, by name* — because rung 2 would otherwise bill
the same spend twice, once at GitHub's rate and once at cage's list rates. It reports the
**same** `credits` match kind as rung 1 rather than a fourth one, deliberately: the
shutdown priced on ONE basis, so every consumer that already excludes a credits-priced
row from token-derived reasoning (report's `cache_usd` split, the mixed-basis footnote,
`method_for`) inherits the right behaviour with no per-view fork. The carrier's id comes
back as the matched key, so the link is never invisible.

**Why rung 1 goes first.** Since 2026-06-01 Copilot bills usage-based AI Credits
"calculated based on token consumption … using the listed API rates for each model"
(github.blog) — so a recorded credit is *GitHub's own* tokens×rates computation, done
with information cage cannot see: what the virtual `copilot/auto` actually routed to,
and GitHub's current rates rather than cage's price table. It is the closest thing to
an invoice cage will ever get from Copilot, and it prices `copilot/auto` — the majority
of real VS Code traffic, and previously the whole UNPRICED hole — without a single
price-table row.

**Method law: rung 1 is `modeled`, never `measured`.** The credit *count* is a
recorded fact on the row; the *dollar* is that count times a rate you configured, so
the cell is an interpretation. Consumers see this as the `CREDITS` match kind, which
`report` footnotes with the mixed-basis split and CSV names in `priced_via`.

**Never derived from tokens, in either direction.** Absence stays absence (the standing
`prices.toml` rule) — a row without recorded credits falls through to rung 2 rather
than having a credit figure invented for it, and a recorded `0.0` is a real zero that
prices at $0.0000 rather than reading as absent. Derive-time only: no row is ever
rewritten, so setting the rate later re-prices all of history.
"""
from __future__ import annotations

from cage import policy

# TWO deliberately separate vocabularies — conflating them is how a rendering starts
# lying about a basis:
#
#   · MATCH is a *match kind*, and joins `policy.price_match`'s closed set
#     (exact | alias | family | self | none). It answers "how did this row resolve",
#     and `prices.call_usd_match` returns it.
#   · CREDITS / TOKENS are *pricing bases*, the `priced_via` CSV vocabulary from the
#     proposal. They answer "which rung of the ladder paid for this", and three
#     different match kinds (exact/alias/family) all collapse to the one basis TOKENS.
#
# So the mapping is many-to-one and lives in `via()`, never inlined per view.
MATCH = "credits"

CREDITS = "credits-rate"
TOKENS = "token-table"
# Not a rung: names an aggregate whose rows did not all price the same way, so a
# per-row column can stay honest about a group it cannot reduce to one basis.
MIXED = "mixed"


def via(match: str) -> str:
    """A `call_usd_match` match kind → its `priced_via` basis. ``""`` for a row that
    never priced (``none``), so an UNPRICED row claims no basis and `—` never has to
    enter CSV. A ``self``-costed row reports TOKENS: it is a recorded per-call cost,
    which is the token side of the ladder, not a credit."""
    if match == MATCH:
        return CREDITS
    return "" if match == "none" else TOKENS

# The one runnable fix line for "credits recorded, but no rate to price them at" —
# the second fix in report's ⚠ UNPRICED block, and the rate-unset advisory's tail.
# A cage.toml edit, not a command: there is deliberately no `cage prices` verb that
# writes a billing rate, because a plan's overage rate is not a vendor fact to sync.
RATE_HINT = ("set [billing.{agent}] usd_per_credit in .cage/cage.toml "
             "(`cage query copilot-credits`)")


def recorded(call: dict) -> float | None:
    """This row's recorded credit figure, or ``None`` when it carries none.

    The ONE reader of the `credits` field, so the absent-vs-recorded-zero distinction
    is enforced in a single place: a missing key and a non-numeric value are both
    ``None`` (absent — fall through the ladder), while ``0.0`` is a recorded zero and
    is returned as such. `bool` is rejected explicitly (an `int` subclass; a `True`
    credit is malformed, not the number 1)."""
    v = call.get("credits")
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return float(v)


def billed_elsewhere(call: dict) -> str:
    """The id of the row carrying this row's billing, or ``""`` when it bills for itself.

    The ONE reader of `billed_with`, for the same reason `recorded` is the one reader of
    `credits`: the *one basis per shutdown* rule (REV-CREDITS defect 2) has to mean the
    same thing everywhere it is consulted. A provider that computes a single billed
    figure over a group of calls has priced that group **once**; letting the group's
    other rows fall through to rung 2 would price the same spend a second time at cage's
    list rates. Non-string values are ``""`` — a malformed link suppresses nothing, which
    fails toward the pre-existing behaviour rather than toward a silent $0."""
    v = call.get("billed_with")
    return v if isinstance(v, str) else ""


def rate_for(pol: dict, call: dict) -> float | None:
    """The `[billing.<agent>] usd_per_credit` that applies to this row, or ``None``.

    Keyed on the row's own `agent`, not hardcoded to copilot: the mechanism is general
    (any agent whose store records a billed credit can be given a rate), and copilot is
    simply the only one that records one today. An agent-less row gets no rate."""
    agent = call.get("agent") or ""
    return policy.credit_rate(pol, agent) if agent else None


def resolve(pol: dict, call: dict) -> float | None:
    """Rung 1: ``credits × usd_per_credit`` in USD, or ``None`` when the rung does not
    apply — no recorded credits, or no configured rate for this row's agent.

    ``None`` means *fall through to rung 2*, and is deliberately distinct from a
    returned ``0.0`` (a genuine zero-cost row: a recorded zero credit, or a rate of
    zero). Rounded to the same 6dp every other USD figure in cage carries."""
    cred = recorded(call)
    if cred is None:
        return None
    rate = rate_for(pol, call)
    if rate is None:
        return None
    return round(cred * rate, 6)


def unrated(pol: dict, call: dict) -> bool:
    """True when this row has recorded credits that **cannot** be priced because no
    rate is configured — the population the rate-unset advisory counts, and the reason
    report's ⚠ block earns its second fix line. A row with no credits at all is not
    unrated; it is simply a rung-2 row."""
    return recorded(call) is not None and rate_for(pol, call) is None


def agents_needing_rate(calls) -> list[str]:
    """The sorted distinct agents among ``calls`` — used to build the fix line with a
    real agent name substituted (the fix-hint contract: never a `<placeholder>` the
    reader has to resolve). Callers pass the already-filtered unrated rows."""
    return sorted({c.get("agent") or "" for c in calls} - {""})


def rate_hint(agents) -> str:
    """The runnable fix line for a set of unrated agents — one line, real names."""
    names = list(agents) or ["copilot"]
    return RATE_HINT.format(agent=names[0]) if len(names) == 1 else \
        "set [billing.<agent>] usd_per_credit in .cage/cage.toml for: " + ", ".join(names)


def method_for(counts: dict) -> str:
    """The CSV `method` tag for an aggregate that priced ``counts`` rows per basis.

    **Method law, and the reason this is not a literal in any view.** A token-priced
    cell is `measured` — recorded tokens repriced at derive time, spend is never a
    projection. A credits-priced cell is `modeled`: the credit count is recorded fact,
    but the dollar is that count times a rate *you* configured, which cage cannot
    verify against an invoice. So any aggregate containing even one credits-priced row
    degrades to `modeled` — the weaker tag always wins, because a mixed cell that
    claimed `measured` would let a configured rate read as an invoice."""
    return "modeled" if counts.get(CREDITS) else "measured"


def basis_of(counts: dict) -> str:
    """The `priced_via` value for an aggregate, from its ``{CREDITS: n, TOKENS: n}``
    tally: the sole basis when only one priced its rows, ``MIXED`` when both did, and
    ``""`` when nothing priced (an UNPRICED-only group — the column stays empty rather
    than claiming a basis, and `—` never enters CSV)."""
    used = [k for k in (CREDITS, TOKENS) if counts.get(k)]
    if not used:
        return ""
    return used[0] if len(used) == 1 else MIXED


def split_footnote(agent: str, credits_calls: int, credits_total: float,
                   credits_usd: float, token_calls: int, token_usd: float) -> str:
    """The mixed-basis footnote: a total that sums two pricing bases must say so, with
    the split — the same discipline as the UNPRICED ⚠ (verdict C, rule 4: no cell ever
    blends the axes silently).

    **Scoped to ONE agent, and that is load-bearing.** The claim is "*this agent's* rows
    priced two ways", so both halves must count only that agent's calls. Tallying the
    token side view-wide made the footnote attribute another agent's spend to copilot's
    split — printed as `1 call(s) by token×table ($1.1579)` when that dollar was
    claude's. Two agents on two different bases is not a mixed basis; it is two agents.
    Emitted per agent whose own rows split, and only then."""
    from cage import render
    return (f"· {agent} priced on two bases: {credits_calls} call(s) by credits×rate "
            f"({fmt(credits_total)} cr → {render.usd(credits_usd)}), "
            f"{token_calls} call(s) by token×table ({render.usd(token_usd)}) "
            "— `cage query copilot-credits`")


def unrated_line(calls: int, total: float, agents) -> str:
    """The rate-unset advisory: credits were recorded but no rate exists to price them,
    so they render as a **count**, never a dollar. States the count, then the fix."""
    return (f"· {calls} call(s) carry recorded credits ({fmt(total)} cr) — not priced; "
            f"{rate_hint(agents)}")


def fmt(credits: float) -> str:
    """A credit figure for display — 2dp, the proposal's rendering.

    Display only: the ledger keeps the store's verbatim float (real values run to 6dp),
    so this never feeds arithmetic and a re-render can never drift the stored fact."""
    return f"{credits:.2f}"
