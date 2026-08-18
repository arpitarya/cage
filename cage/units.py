"""**The per-agent unit policy** — which agent records which unit, and why the others
are absent (USAGE-ONLY, ADR 0011).

Cage measures two units after the money subsystem's deletion, and **neither is universal
across the three agents**. That asymmetry is a set of vendor facts, not a capture gap,
and this module is the ONE place they are stated — so a view renders a *reason* where a
unit does not exist, never a `0`.

    agent     tokens   credits
    claude    ✓        —  no credit unit exists on disk for Claude Code
    copilot   ✓        ✓
    kiro      —*       ✓  (spend/report total excludes kiro entirely; its CLI's token
                           columns are still null. * `insights chats` shows real, if
                           coarse, per-chat IDE token counts read directly off a separate
                           log — LEDGER-READ-SURFACE, 2026-08-15 — but that read never
                           joins this table's `tokens` column or any cross-agent total.)

**Why the two absences must never render identically.** One is a vendor law (Claude Code
has no credit concept at all) and one is a schema fact on this machine (the day
kiro-cli's own `request_metadata` token slots stop being NULL, `cli-turn` rows record
them with zero code change — the upgrade-watch, already armed). Rendering both as a
bare `—` invites a future agent to "fix" the permanent one, or to read the fixable one
as permanent. Each carries its own sentence.

**A `0` is never an acceptable stand-in for either.** `0 credits` asserts a measurement
that was never taken; `—` plus a reason asserts only what is true. This is the same
`—`-is-never-0 rule `chats.py` already applies to `agent%`.

**THE CROSS-AGENT LAW: credits are never summed or ranked across agents.** Copilot's
credit is GitHub's own tokens×rates computation over a request; Kiro's is an AWS credit.
They share a *column name* and nothing else — there is no conversion between them and
cage will not invent one. :func:`summable` enforces it in code rather than by convention,
because the column name is the whole of the temptation.

Tokens are likewise not cross-vendor comparable in any economic sense (a copilot vscode
row carries no `cached_in` at all — 0 of 57 rows when measured on 2026-08-14), but they
*are* one physical unit, so a total is arithmetically sound and is permitted. The line is
drawn where the arithmetic breaks, not where the interpretation gets hard.
"""
from __future__ import annotations

from collections.abc import Iterable

TOKENS = "tokens"
CREDITS = "credits"
UNITS = (TOKENS, CREDITS)

#: ``agent → {unit: reason it is absent}``. A unit **missing from an agent's entry means
#: the agent HAS it** — absence-of-absence, so adding an agent with both units needs no
#: row here at all. Reasons are whole sentences: they are rendered verbatim to users.
ABSENT: dict[str, dict[str, str]] = {
    "claude": {CREDITS: "Claude Code records no credit unit on disk"},
    # Widened in P2 (v0.51), then narrowed again by LEDGER-READ-SURFACE (2026-08-15):
    # `insights chats` now reads `ledger.kiro_metrics()` directly and shows real, if
    # coarse, per-chat IDE token counts (`tokens_generated.jsonl` — the only IDE store
    # any probed install has; `devdata.sqlite` remains absent everywhere). This entry
    # is about a DIFFERENT surface: the cross-agent spend/report total, which still
    # excludes kiro entirely (`ledger.spend()`'s `SPEND_SOURCES["kiro"] = ()`,
    # ADR-KIRO) — that invariant is untouched. `chats.py`'s `_unit_absence_notes` only
    # renders this sentence when every kiro row on screen is credits-shaped, so it
    # never sits beside a row it contradicts; the sentence itself must still be true
    # on ITS OWN surface (the spend total) even though the chats view has since grown
    # a second, narrower read surface this sentence is not describing.
    "kiro": {TOKENS: "Kiro contributes no tokens to any spend/report total — its CLI's "
                     "token columns are still null (2.16.0), and IDE token counts, "
                     "where present, are shown per-chat by `insights chats` reading a "
                     "separate log, never through this total"},
}


def absent_reason(agent: str, unit: str) -> str | None:
    """Why ``agent`` has no ``unit``, or ``None`` when it does have it.

    A caller renders the reason beside a `—`; it must never substitute a `0`."""
    return ABSENT.get(agent, {}).get(unit)


def has(agent: str, unit: str) -> bool:
    """Does ``agent`` record ``unit`` at all? An unknown agent is assumed to have every
    unit — cage does not claim an absence it has not established."""
    return absent_reason(agent, unit) is None


def summable(unit: str, agents: Iterable[str]) -> bool:
    """May a single total be formed for ``unit`` across ``agents``?

    ``True`` for tokens always (one physical unit). For **credits**, true only when at
    most one distinct agent is present — see the cross-agent law above. Empty/blank
    agent names are ignored so an unattributed row cannot silently make a set look
    multi-agent (or single-agent)."""
    if unit != CREDITS:
        return True
    return len({a for a in agents if a}) <= 1


def cross_agent_note(agents: Iterable[str]) -> str:
    """The one phrasing for a refused cross-agent credit total. One home, like
    `savings.GROSS_NOTE` — a re-worded refusal reads as a different rule."""
    names = " · ".join(sorted({a for a in agents if a}))
    return ("· credits are NOT summed across agents — copilot credits are GitHub's "
            "tokens×rates figure, kiro credits are AWS credits; different units "
            f"({names}). Shown per agent.")
