"""§8 ledger features + Tier-0 savings emitters."""
from __future__ import annotations

import json

import pytest

from cage import (compress, forecast, metering, policy, quality, recommend,
                  regression, responsecache)


def _call(root, task, cost, ts):
    metering.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=1000, tokens_out=100, est_cost_usd=cost, task=task,
                         ts=ts, root=root)


def test_quality_cost_per_successful_task(proj):
    _call(proj, "t1", 0.10, "2026-06-14T00:00:00Z")
    _call(proj, "t2", 0.30, "2026-06-14T00:00:01Z")
    quality.record_outcome(proj, "t1", ok=True)
    quality.record_outcome(proj, "t2", ok=False)        # redo → not a success
    s = quality.summarize(proj)
    assert s["tasks"] == 2 and s["ok"] == 1 and s["redo"] == 1
    # total $0.40 charged against the 1 successful task — the false-economy guard.
    assert s["per_success"] == pytest.approx(0.40, abs=1e-6)


def test_regression_flags_drift(proj):
    for i in range(3):
        _call(proj, f"old{i}", 0.01, "2000-01-01T00:00:00Z")   # cheap baseline
    for i in range(3):
        _call(proj, f"new{i}", 0.05, "2099-01-01T00:00:00Z")   # pricey recent
    r = regression.detect(proj, since="7d", tolerance=0.2)
    assert r["regressed"] is True and r["drift"] > 0.2


def test_recommend_enables_net_positive_tools(seeded):
    root, _ = seeded
    rec = recommend.recommend(root, policy.load(None))
    assert set(rec["enable"]) == {"graphify", "fux", "compressor"}
    assert rec["skip"] == []


def test_forecast_projects_and_checks_ceiling(proj):
    pol = policy.load(None)
    pol["budgets"] = {"daily_usd": 0.001, "session_usd": None, "on_exceed": "warn"}
    _call(proj, "t", 1.0, "2026-06-14T00:00:00Z")
    f = forecast.project(proj, pol)
    assert f["projected_month_usd"] == pytest.approx(30.0, abs=1e-6)
    assert f["blows_budget"] is True and f["blows_on_day"] is not None


def test_compress_shrinks_and_makes_receipt():
    blob = json.dumps({"rows": [{"x": i, "note": "y" * 400} for i in range(100)]})
    out, raw, act = compress.compress(blob)
    assert act < raw                                   # genuinely smaller
    r = compress.receipt(blob, task="t")
    assert r["tool"] == "compressor" and r["saved"] == raw - act


def test_response_cache_hit_eliminates_call(proj):
    responsecache.store(proj, "what is 2+2", "4", call_tokens=5000)
    assert responsecache.lookup(proj, "what is 2+2")["value"] == "4"
    assert responsecache.lookup(proj, "different") is None
    r = responsecache.hit_receipt(5000, task="t")
    assert r["actual"] == 0 and r["saved"] == 5000 and r["tool"] == "response-cache"
