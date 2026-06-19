"""Stage-1 converter: the single unit→USD dispatch (design §2.3, criterion 2a)."""
from __future__ import annotations

import pytest

from cage import attribution, convert, policy, roi, schema


def _call():
    return {"provider": "anthropic", "model": "claude-opus-4-8"}


def test_saved_usd_dispatches_by_unit():
    pol = policy.load(None)
    call = _call()
    # 1M input tokens on Opus ($3/M) == $3.00; a $3 usd receipt == $3.00; equal value.
    tokens = schema.make_receipt(tool="t", raw_alternative=1_000_000, actual=0, unit="tokens")
    usd = schema.make_receipt(tool="t", raw_alternative=3.0, actual=0.0, unit="usd")
    assert convert.saved_usd(tokens, call, pol) == pytest.approx(3.0, abs=1e-6)
    assert convert.saved_usd(usd, call, pol) == pytest.approx(3.0, abs=1e-6)


def test_saved_usd_zero_for_non_money_units():
    pol = policy.load(None)
    for unit in ("ms", "gco2"):
        r = schema.make_receipt(tool="t", raw_alternative=100, actual=0, unit=unit)
        assert convert.saved_usd(r, _call(), pol) == 0.0


def test_roi_and_attribution_byte_identical_after_refactor(seeded):
    """Pure refactor: routing through convert.saved_usd must not move a number."""
    root, _ = seeded
    pol = policy.load(None)
    # roi: graphify saved 27,000 tokens @ $3/M == $0.081 (the pre-refactor value).
    data = roi.by_tool(root, pol)
    assert data["tools"]["graphify"]["saved_usd"] == pytest.approx(27000 * 3 / 1e6, abs=1e-9)
    # attribution: §4.4 worked totals unchanged (27000 + 6400 + 8000 tokens saved).
    from cage import demo
    attr = attribution.attribute(root, demo.TASK, pol)
    assert attr["total_saved_tokens"] == 41400.0
    assert attr["total_saved_usd"] == pytest.approx(41400 * 3 / 1e6, abs=1e-9)
