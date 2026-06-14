"""`cage demo` — seed the plan's §4.4 worked example so the thesis is runnable.

One agent task ("explain why handover does X, then fix it") whose context
decomposes into three disjoint slices, each shrunk by a different deterministic
tool. After seeding, `cage attrib` and `cage matrix` reproduce the plan's tables
against a real ledger — proof the attribution engine works, not just an assertion.
"""
from __future__ import annotations

from pathlib import Path

from cage import metering

TASK = "fix-handover-bug"
# (tool, slice without it, slice with it, how the alternative is known)
_SLICES = [
    ("graphify", 30000, 3000, "modeled"),    # code understanding
    ("fux", 8000, 1600, "modeled"),          # rule / intent lookup
    ("compressor", 10000, 2000, "measured"),  # tool outputs (logs/JSON)
]
_BASE = 2000   # sys+user prompt, always present
_OUT = 1500    # output held constant


def seed(root: Path) -> str:
    actual_in = _BASE + sum(w for _, _, w, _ in _SLICES)
    call_id = metering.record_call(
        route="code-edit", provider="anthropic", model="claude-opus-4-8",
        tokens_in=actual_in, tokens_out=_OUT, task=TASK, agent="claude-code",
        session="demo", root=root)
    for tool, without, with_, method in _SLICES:
        metering.record_receipt(tool=tool, raw_alternative=without, actual=with_,
                                call=call_id, task=TASK, method=method, root=root)
    return call_id
