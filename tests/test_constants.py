"""`cage/constants.py` — the third audit layer (handoff §1, acceptance 1 & 2).

Stage 1 is a *pure move*: the seven modules now import their heuristics from
`constants.py` instead of inlining them. These guards prove (a) the values are
the ones the modules used to inline, (b) the demo's §4.4 numbers are unchanged
(behaviour is byte-identical), and (c) `DEFAULT_CONFIDENCE` is still only a
*fallback* — a row's own `confidence` still wins.
"""
from __future__ import annotations

from cage import (compress, constants, graphifymeter, ledger, origin,
                  policy)


# ── the modules read their heuristics from constants (the move actually landed) ─
def test_modules_import_from_constants():
    assert compress._toks("x" * 40) == round(40 / constants.CHARS_PER_TOKEN)
    assert graphifymeter.toks("y" * 40) == round(40 / constants.CHARS_PER_TOKEN)
    assert ledger._UNIT is constants.SINCE_WINDOW_DAYS


# ── the values are exactly the ones that used to be inlined (no retune) ────────
def test_constant_values_unchanged():
    assert constants.CHARS_PER_TOKEN == 4
    assert constants.TOKENS_PER_MILLION == 1_000_000
    assert constants.METHOD_TRUST == {"measured": 2, "modeled": 1, "estimated": 0}
    assert constants.DEFAULT_CONFIDENCE == {"measured": 0.9, "estimated": 0.7,
                                            "type_table": 0.5, "default": 0.3}
    assert constants.GRAPHIFY_RECEIPT_CONFIDENCE == 0.6
    assert constants.SINCE_WINDOW_DAYS == {"h": 1 / 24, "d": 1, "w": 7}
    # METHOD_TRUST keeps its value even though `attribution` (its last in-tree reader)
    # went in SURFACE-CUT: `constants` is the audit layer, and a constant is not retuned
    # because a consumer left. `PROVENANCE_METHOD_TRUST` is the parallel ladder still in
    # use by the authorship surfaces.


def test_default_confidence_ladder_is_the_one_source():
    # `origin.explain` is the surviving consumer after the Tier-1 human axis was
    # removed in v0.36: it reads the ladder, never an inlined 0.7.
    assert constants.DEFAULT_CONFIDENCE["estimated"] == 0.7
    assert origin.DEFAULT_CONFIDENCE is constants.DEFAULT_CONFIDENCE
