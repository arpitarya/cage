"""**The per-agent unit policy** — which agent records which unit, and why the others
are absent (USAGE-ONLY, ADR 0011).

Cage measures two units after the money subsystem's deletion, and **neither is universal
across the three agents**. That asymmetry is a set of vendor facts, not a capture gap,
and this module is the ONE place they are stated — so a view renders a *reason* where a
unit does not exist, never a `0`.

    agent     tokens   credits
    claude    ✓        —  no credit unit exists on disk for Claude Code
    copilot   ✓        ✓
    kiro      —        ✓  (its IDE token store is absent; CLI spend is credits-only)

**Why the two absences must never render identically.** One is a vendor law (Claude Code
has no credit concept at all) and one is a missing store on this machine (a future Kiro
that ships `devdata.sqlite` flips it). Rendering both as a bare `—` invites a future
agent to "fix" the permanent one, or to read the fixable one as permanent. Each carries
its own sentence.

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
    # Widened in P2 (v0.51). It read "no IDE token store on this install", which named
    # ONE surface and one cause — and a reader could fairly conclude the CLI had tokens.
    # **Both** Kiro surfaces lack them, for two different vendor reasons, and the sentence
    # is rendered verbatim to users so it has to carry both: the IDE ships no token store
    # (`devdata.sqlite` is absent on every install probed; its `tokens_generated.jsonl`
    # twin is 0-output and unsummable), and the CLI's store HAS token columns that are
    # still NULL (kiro-cli 2.16.0). The second is an upgrade-watch, not a permanent
    # absence — which is exactly the distinction one clause could not make.
    "kiro": {TOKENS: "Kiro records no tokens on either surface — the IDE ships no token "
                     "store, and the CLI's token columns are still null (2.16.0). Its "
                     "usage is credits"},
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
