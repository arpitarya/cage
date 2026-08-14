"""`cage demo` — seed the plan's §4.4 worked example so the thesis is runnable.

One agent task ("explain why handover does X, then fix it") whose context
decomposes into three disjoint slices, each shrunk by a different deterministic
tool. After seeding, the ledger holds the plan's worked example
against a real ledger — proof the attribution engine works, not just an assertion.
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, metering, schema

TASK = "fix-handover-bug"
# (tool, slice without it, slice with it, how the alternative is known)
_SLICES = [
    ("graphify", 30000, 3000, "modeled"),    # code understanding
    ("fux", 8000, 1600, "modeled"),          # rule / intent lookup
    ("compressor", 10000, 2000, "measured"),  # tool outputs (logs/JSON)
]
_BASE = 2000   # sys+user prompt, always present
_OUT = 1500    # output held constant

# The worked example is RECORDED HISTORY, so it carries a fixed instant rather than
# `now()`: §4.4's tables are fixed numbers, and a seeder stamped with the wall clock was
# never reproducible in the sense the rest of cage is.
#
# **THE SEEDER DUAL-WRITES, and it must.** `ledger.spend` supersedes a `calls` row for
# any agent that has a metric spine, and this row is stamped `agent="claude-code"` —
# which has one. A calls-only seed therefore resolves to NOTHING and `cage demo` prints
# empty tables, breaking the standing invariant that it reproduces §4.4.
#
# A pinned pre-cutover instant used to hide this (METRICS-PRIMARY, v0.50); USAGE-ONLY
# retired the cutover, so the row is superseded for all of history and the protection is
# gone. Writing both rows is the honest fix rather than a second dodge: it is exactly
# what real capture does for claude (dual-write, CLAUDE.md), so the demo now exercises
# the same resolution path a real ledger does instead of a special case that only
# survives because of where a boundary happens to sit.
#
# The `calls` row is still required — it is the id namespace the savings receipts
# reference (`call=<c_ id>`), which is what a call→receipt join uses.
_TS = "2026-06-01T12:00:00Z"


def seed(root: Path) -> str:
    # Idempotent: `cage demo` is the "prove the thesis" seeder — re-running it must not
    # stack a second worked example onto the same ledger (that doubled the deriveds attrib`'s
    # §4.4 totals). If the demo task is already present, return its call id and append
    # nothing, so the tables keep reproducing §4.4 exactly however many times it runs.
    existing = [c for c in ledger.calls(root) if c.get("task") == TASK]
    if existing:
        return existing[0].get("id", "")
    actual_in = _BASE + sum(w for _, _, w, _ in _SLICES)
    # Sonnet ($3/M in, $15/M out) — the rates the plan §4.4 numbers were computed at.
    call_id = metering.record_call(
        route="code-edit", provider="anthropic", model="claude-sonnet-4-6",
        tokens_in=actual_in, tokens_out=_OUT, task=TASK, agent="claude-code",
        session="demo", root=root, ts=_TS)
    # The metric twin — the row `ledger.spend` actually reads for a claude-agent chat.
    # Same tokens, same instant: the two rows describe ONE piece of traffic, exactly as a
    # real dual-write capture records it.
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="demo", source="request", request="demo-r1",
        provider="anthropic", model="claude-sonnet-4-6",
        tokens_in=actual_in, tokens_out=_OUT, ts=_TS))
    for tool, without, with_, method in _SLICES:
        metering.record_receipt(tool=tool, raw_alternative=without, actual=with_,
                                call=call_id, task=TASK, method=method, root=root,
                                ts=_TS)
    return call_id
