"""Substrate contract: ids, schema, prices, ledger, policy."""
from __future__ import annotations

import time

import pytest

from cage import ids, ledger, paths, policy, prices, schema


def test_ids_are_sortable_by_time():
    a = ids.new_id("c")
    time.sleep(0.002)
    b = ids.new_id("c")
    assert a.startswith("c_") and b.startswith("c_")
    assert a < b  # later id sorts after earlier one


def test_make_receipt_derives_saved():
    r = schema.make_receipt(tool="fux", raw_alternative=8000, actual=1600)
    assert r["saved"] == 6400
    assert r["id"].startswith("r_")


def test_make_receipt_rejects_bad_enums():
    with pytest.raises(ValueError):
        schema.make_receipt(tool="x", raw_alternative=1, actual=0, unit="bananas")
    with pytest.raises(ValueError):
        schema.make_receipt(tool="x", raw_alternative=1, actual=0, method="vibes")


def test_call_cost_matches_plan_worked_example():
    pol = policy.load(None)
    # §4.4 full-stack call: 8,600 in / 1,500 out on Sonnet ($3/$15) → $0.0483.
    cost = prices.call_cost_usd(pol, "anthropic", "claude-sonnet-4-6", 8600, 1500)
    assert cost == pytest.approx(0.0483, abs=1e-6)


def test_cache_read_is_cheaper_than_full_input():
    pol = policy.load(None)
    full = prices.call_cost_usd(pol, "anthropic", "claude-opus-4-8", 10000, 0, cached_in=0)
    cached = prices.call_cost_usd(pol, "anthropic", "claude-opus-4-8", 10000, 0, cached_in=8000)
    assert cached < full  # 8k tokens billed at the 90%-off cache_read rate


def test_unpriced_model_costs_zero():
    pol = policy.load(None)
    assert prices.call_cost_usd(pol, "nobody", "ghost", 1000, 1000) == 0.0


def test_ledger_append_read_roundtrip(proj):
    fp = paths.Footprint(proj)
    assert ledger.append(fp.calls, {"id": "c_1", "ts": "2026-06-14T00:00:00Z"})
    assert ledger.append(fp.calls, {"id": "c_2", "ts": "2026-06-14T00:00:01Z"})
    rows = ledger.calls(proj)
    assert [r["id"] for r in rows] == ["c_1", "c_2"]


def test_ledger_tolerates_truncated_tail(proj):
    fp = paths.Footprint(proj)
    ledger.append(fp.calls, {"id": "c_1"})
    with fp.calls.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "c_2", "ts": ')  # crash mid-append
    assert [r["id"] for r in ledger.calls(proj)] == ["c_1"]


def test_since_window_filters_old_rows():
    rows = [{"ts": "2000-01-01T00:00:00Z"}, {"ts": "2099-01-01T00:00:00Z"}]
    kept = ledger.since(rows, "7d")
    assert kept == [{"ts": "2099-01-01T00:00:00Z"}]
    assert ledger.since(rows, None) == rows  # no window = passthrough


def test_policy_project_overrides_bundled(proj):
    fp = paths.Footprint(proj)
    fp.base.mkdir(parents=True)
    fp.policy.write_text('[budgets]\nsession_usd = 9.5\n', encoding="utf-8")
    pol = policy.load(fp.policy)
    assert policy.budgets(pol)["session_usd"] == 9.5
    # bundled prices still present after the merge (Opus 4.8 = $5/M input, current rate)
    assert policy.price(pol, "anthropic", "claude-opus-4-8")["input"] == 5.00
    # OpenAI gpt-5 family present too (Codex / Copilot)
    assert policy.price(pol, "openai", "gpt-5")["output"] == 10.00
