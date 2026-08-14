"""The CLI reorganization map — the single source of truth for the
error-with-directions handler (`cli.main`). Never hand-duplicate this dict.

Each key is an old *top-level* verb that no longer exists; the value is the new
invocation tail (what follows `cage `). Typing the old verb prints
``error: '<old>' is now 'cage <new>'`` and exits 1 — a direction, never a silent
alias, for one release (plan Phase 3 §4). `mcp`/`debug`/`demo` are absent: they
stay callable as top-level verbs, merely hidden from `cage --help`.

A few entries carry a hand-written body instead of a tail (``_BODIES``) because
one old verb maps to more than one outcome — `human` is the case: two of its
four subcommands MOVED (`outcome`/`quality` → `cage task …`) while the other two
were REMOVED with the Tier-1 human axis in v0.36. A single "is now" line would be
a lie in half the cases, so it gets a sentence.
"""
from __future__ import annotations

# old top-level verb → new command tail (after `cage `). Order is display order
# for the CHANGELOG table: grouped by destination, groups then removals.
REMOVED: dict[str, str] = {
    # merged / renamed singletons
    "init": "setup",
    "import-claude": "import --agent claude",
    # → insights
    "attrib": "insights attrib",
    "compare": "insights compare",
    "estimate": "insights estimate",
    "calibration": "insights calibration",
    "why": "insights why",
    # The money subsystem, removed outright in USAGE-ONLY (ADR 0011) — cage measures
    # usage, not cost. An empty tail means "removed, no replacement": `direction()`
    # explains from `_BODIES` below and `wiringscan.heal_tail` never rewrites to it.
    # These were `insights <verb>` for one release before removal, so BOTH spellings
    # are still out there in wired artifacts and shell history.
    "matrix": "",
    "roi": "",
    "verdict": "",
    "budget": "",
    "forecast": "",
    "regression": "",
    "recommend": "",
    "prices": "",
    "quality": "",
    # → task (v0.36: the `human` group is gone; these two were never the human axis)
    "outcome": "task outcome",
    # the Tier-1 agent-vs-human axis, removed outright in v0.36 (see _BODIES)
    "human": "",
    "human-record": "",
    "trend": "",
    # → authorship
    "origin": "authorship origin",
    "verify": "authorship verify",
    "notes-sync": "authorship notes-sync",
    "ledger-sync": "authorship ledger-sync",
    # → data
    "export": "data export",
    "cleanup": "data cleanup",
    "watch": "data watch",
    "serve": "data serve",
    "proxy": "data proxy",
    "meter": "data meter",
    "graphify": "data graphify",
    # hook machinery removed (capture is pull-based): no replacement command —
    # an empty tail means "removed outright"; direction() explains, heal never
    # rewrites to it (wiringscan.heal_tail skips empty fixes).
    "hook-session-start": "",
    "hook-stop": "",
    "hook-session-end": "",
    "hook-post-tool-use": "",
    "hook-post-commit": "",
    "hook-prepare-commit-msg": "",
}


# Verbs whose removal needs a sentence, not a tail. Checked before the generic
# empty-tail message so each removal explains its own reason.
_MONEY_REMOVED = (
    "was removed in v0.51 with the whole money subsystem — cage measures token and "
    "credit USAGE, not cost. There is no replacement command: no price table, no "
    "budget, no ROI, no dollar anywhere (`cage query gross-vs-net`). Nearest usable "
    "views: `cage report` (tokens/credits by any dimension), `cage insights attrib` "
    "(per-tool gross token savings), `cage insights chats` (per conversation)")

_BODIES: dict[str, str] = {
    **{v: f"'{v}' {_MONEY_REMOVED}" for v in
       ("matrix", "roi", "verdict", "budget", "forecast", "regression", "recommend",
        "prices")},
    "quality": ("'quality' was removed in v0.51 — it reported cost per successful "
                "task, and cage no longer measures cost. The OUTCOME half survives: "
                "`cage task outcome <task>` still records ok/redo, and "
                "`cage insights compare` / `calibration` still read it"),
    "human": ("'human' was removed in v0.36 — the agent-vs-human cost axis is gone. "
              "Its two non-human subcommands moved: `cage task outcome`, "
              "`cage task quality` (`cage query savings-axis`)"),
    "human-record": ("'human-record' was removed in v0.36 with the agent-vs-human "
                     "cost axis (`cage query savings-axis`)"),
    "trend": ("'trend' was removed in v0.36 — it charted the agent-vs-human axis, "
              "which is gone (`cage query savings-axis`)"),
}


def direction(old: str) -> str:
    """The one-line error body for a removed verb (`cli.main` prefixes ``error: ``)."""
    if old in _BODIES:
        return _BODIES[old]
    new = REMOVED[old]
    if not new:
        return (f"'{old}' was removed — hooks are gone; capture is pull-based "
                f"(`cage import`). Re-run `cage setup` to clean stale wiring.")
    return f"'{old}' is now 'cage {new}'"
