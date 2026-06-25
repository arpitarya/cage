"""The differentiator: marginal attribution + the counterfactual matrix (§4.2, §4.4)."""
from __future__ import annotations

import pytest

from cage import attribution, demo, matrix, policy


def test_attrib_reproduces_plan_marginals(seeded):
    root, _ = seeded
    data = attribution.attribute(root, demo.TASK, policy.load(None))
    saved = {s["tool"]: s["saved_tokens"] for s in data["steps"]}
    assert saved == {"graphify": 27000, "fux": 6400, "compressor": 8000}
    assert data["total_saved_tokens"] == 41400
    # 41,400 input tokens at Sonnet $3/M = $0.1242 (plan §4.4 total).
    assert data["total_saved_usd"] == pytest.approx(0.1242, abs=1e-6)


def test_attrib_orders_by_pipeline(seeded):
    root, _ = seeded
    data = attribution.attribute(root, demo.TASK, policy.load(None))
    assert [s["tool"] for s in data["steps"]] == ["graphify", "fux", "compressor"]


def test_matrix_endpoints_match_plan(seeded):
    root, _ = seeded
    data = matrix.matrix(root, demo.TASK, policy.load(None))
    assert len(data["rows"]) == 8  # 2^3 permutations
    costs = {tuple(sorted(t for t, on in r["on"].items() if on)): r for r in data["rows"]}
    all_off = costs[()]
    all_on = costs[("compressor", "fux", "graphify")]
    assert all_off["input_tok"] == 50000
    assert all_off["cost_usd"] == pytest.approx(0.1725, abs=1e-6)
    assert all_on["input_tok"] == 8600
    assert all_on["cost_usd"] == pytest.approx(0.0483, abs=1e-6)


def test_matrix_only_recorded_config_is_measured(seeded):
    root, _ = seeded
    data = matrix.matrix(root, demo.TASK, policy.load(None))
    measured = [r for r in data["rows"] if r["source"] == "measured"]
    assert len(measured) == 1  # only the all-on config was actually run
    assert all(measured[0]["on"].values())


def test_aggregates_duplicate_tool_receipts(proj):
    from cage import metering as meter
    cid = meter.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                            tokens_in=100, tokens_out=10, task="dup", root=proj)
    meter.record_receipt(tool="fux", raw_alternative=500, actual=100, call=cid,
                         task="dup", root=proj)
    meter.record_receipt(tool="fux", raw_alternative=300, actual=50, call=cid,
                         task="dup", method="estimated", root=proj)
    data = attribution.attribute(proj, "dup", policy.load(None))
    (step,) = data["steps"]
    assert step["saved_tokens"] == 650  # 400 + 250 summed
    assert step["method"] == "estimated"  # least-trusted method wins
