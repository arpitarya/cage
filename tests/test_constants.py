"""`cage/constants.py` — the third audit layer (handoff §1, acceptance 1 & 2).

Stage 1 is a *pure move*: the seven modules now import their heuristics from
`constants.py` instead of inlining them. These guards prove (a) the values are
the ones the modules used to inline, (b) the demo's §4.4 numbers are unchanged
(behaviour is byte-identical), and (c) `DEFAULT_CONFIDENCE` is still only a
*fallback* — policy `[human.confidence]` still wins.
"""
from __future__ import annotations

from cage import (attribution, compress, constants, graphifymeter, human,
                  ledger, matrix, policy)


# ── the modules read their heuristics from constants (the move actually landed) ─
def test_modules_import_from_constants():
    assert compress._toks("x" * 40) == round(40 / constants.CHARS_PER_TOKEN)
    assert graphifymeter.toks("y" * 40) == round(40 / constants.CHARS_PER_TOKEN)
    assert ledger._UNIT is constants.SINCE_WINDOW_DAYS
    assert attribution._TRUST is constants.METHOD_TRUST
    assert constants.MAX_MATRIX_TOOLS == 12 and matrix.MAX_MATRIX_TOOLS == 12


# ── the values are exactly the ones that used to be inlined (no retune) ────────
def test_constant_values_unchanged():
    assert constants.CHARS_PER_TOKEN == 4
    assert constants.TOKENS_PER_MILLION == 1_000_000
    assert constants.METHOD_TRUST == {"measured": 2, "modeled": 1, "estimated": 0}
    assert constants.DEFAULT_CONFIDENCE == {"measured": 0.9, "estimated": 0.7,
                                            "type_table": 0.5, "default": 0.3}
    assert constants.GRAPHIFY_RECEIPT_CONFIDENCE == 0.6
    assert constants.SINCE_WINDOW_DAYS == {"h": 1 / 24, "d": 1, "w": 7}


# ── the §4.4 demo numbers are byte-identical (behaviour is a no-op) ────────────
def test_demo_attribution_matches_plan(seeded):
    root, _ = seeded
    pol = policy.load(None)
    data = attribution.attribute(root, "fix-handover-bug", pol)
    by_tool = {s["tool"]: s for s in data["steps"]}
    assert by_tool["graphify"]["saved_tokens"] == 27000
    assert by_tool["graphify"]["saved_usd"] == 0.081
    assert data["total_saved_tokens"] == 41400
    assert data["total_saved_usd"] == 0.1242


def test_demo_matrix_full_stack_cell(seeded):
    root, _ = seeded
    pol = policy.load(None)
    data = matrix.matrix(root, "fix-handover-bug", pol)
    full_off = next(r for r in data["rows"] if not any(r["on"].values()))
    full_on = next(r for r in data["rows"] if all(r["on"].values()))
    assert full_off["input_tok"] == 50000 and full_off["cost_usd"] == 0.1725
    assert full_on["input_tok"] == 8600 and full_on["cost_usd"] == 0.0483
    assert full_on["source"] == "measured" and full_off["source"] == "modeled"


# ── DEFAULT_CONFIDENCE stays a fallback — policy [human.confidence] still wins ──
def test_default_confidence_is_a_fallback(monkeypatch):
    pol = policy.load(None)
    # policy.toml sets [human.confidence].default = 0.3 → it must win over the constant
    r = {"tool": "human", "unit": "tokens", "raw_alternative": 0, "actual": 0,
         "saved": 0, "method": "estimated", "meta": {}}
    assert human.human_alternative_usd(r, pol)[2] == 0.3

    # with the policy block stripped, the resolver falls back to the constant
    pol["human"] = {**pol["human"], "confidence": {}}
    assert human.human_alternative_usd(r, pol)[2] == constants.DEFAULT_CONFIDENCE["default"]
