"""The differentiator: marginal attribution (§4.2).

The counterfactual-matrix half of this file went with `matrix.py` (USAGE-ONLY,
ADR 0011) — it costed permutations, which is the one thing cage no longer does.
The marginal token arithmetic it decorated is unchanged and is pinned below.
"""
from __future__ import annotations

from cage import attribution, demo, policy


def test_attrib_reproduces_plan_marginals(seeded):
    root, _ = seeded
    data = attribution.attribute(root, demo.TASK, policy.load(None))
    saved = {s["tool"]: s["saved_tokens"] for s in data["steps"]}
    assert saved == {"graphify": 27000, "fux": 6400, "compressor": 8000}
    assert data["total_saved_tokens"] == 41400


def test_attrib_orders_by_pipeline(seeded):
    root, _ = seeded
    data = attribution.attribute(root, demo.TASK, policy.load(None))
    assert [s["tool"] for s in data["steps"]] == ["graphify", "fux", "compressor"]


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
