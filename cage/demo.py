"""`cage demo` — seed the plan's §4.4 worked example so the thesis is runnable.

One agent task ("explain why handover does X, then fix it") whose context
decomposes into three disjoint slices, each shrunk by a different deterministic
tool. After seeding, `cage insights attrib` and `cage insights matrix` reproduce the plan's tables
against a real ledger — proof the attribution engine works, not just an assertion.
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, metering

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
# `now()`. Two reasons, and the second is the one that made this a bug:
#
#  1. Determinism. §4.4's tables are fixed numbers; a seeder whose rows are stamped with
#     the wall clock was never reproducible in the sense the rest of cage is.
#  2. METRICS-PRIMARY. `ledger.spend` supersedes a post-cutover `calls` row for any of the
#     three metric-ledger agents, and this row is stamped `agent="claude-code"`. Seeded at
#     `now()` it landed after `constants.SPEND_CUTOVER` and vanished from every derived
#     view — `cage demo` printed empty tables, breaking the standing invariant that it
#     must keep reproducing §4.4. A demo has no transcript store to capture from, so no
#     metric twin can ever exist for it; the fixed pre-cutover instant is what makes it
#     honest history rather than a row waiting to be superseded by nothing.
_TS = "2026-06-01T12:00:00Z"


def seed(root: Path) -> str:
    # Idempotent: `cage demo` is the "prove the thesis" seeder — re-running it must not
    # stack a second worked example onto the same ledger (that doubled `cage insights attrib`'s
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
    for tool, without, with_, method in _SLICES:
        metering.record_receipt(tool=tool, raw_alternative=without, actual=with_,
                                call=call_id, task=TASK, method=method, root=root,
                                ts=_TS)
    return call_id
