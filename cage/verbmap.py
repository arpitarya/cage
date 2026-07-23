"""The Phase-3 CLI reorganization map — the single source of truth for the
error-with-directions handler (`cli.main`) AND the generated CHANGELOG mapping
table (`tools/docgen --target verbmap`). Never hand-duplicate this dict.

Each key is an old *top-level* verb that no longer exists; the value is the new
invocation tail (what follows `cage `). Typing the old verb prints
``error: '<old>' is now 'cage <new>'`` and exits 1 — a direction, never a silent
alias, for one release (plan Phase 3 §4). `human` is deliberately absent: it is
now a group name, so bare `cage human` prints group help (its old rollup moved to
`cage human show`). `mcp`/`debug`/`demo` are absent too: they stay callable as
top-level verbs, merely hidden from `cage --help`.
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
    "matrix": "insights matrix",
    "roi": "insights roi",
    "verdict": "insights verdict",
    "budget": "insights budget",
    "compare": "insights compare",
    "estimate": "insights estimate",
    "calibration": "insights calibration",
    "trend": "insights trend",
    "why": "insights why",
    "forecast": "insights forecast",
    "regression": "insights regression",
    "recommend": "insights recommend",
    # → human
    "human-record": "human record",
    "outcome": "human outcome",
    "quality": "human quality",
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
}


def direction(old: str) -> str:
    """The one-line error body for a removed verb (`cli.main` prefixes ``error: ``)."""
    return f"'{old}' is now 'cage {REMOVED[old]}'"
