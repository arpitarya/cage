"""The library adapter: record_call / record_receipt / meter()."""
from __future__ import annotations

import pytest

from cage import ledger, metering as meter




def test_explicit_cost_is_respected(proj):
    meter.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                      tokens_in=10, tokens_out=10, est_cost_usd=9.99, root=proj)
    assert ledger.calls(proj)[0]["est_cost_usd"] == 9.99


def test_meter_context_records_latency_and_usage(proj):
    with meter.meter("code-edit", task="t", root=proj) as m:
        m.usage(provider="anthropic", model="claude-opus-4-8",
                tokens_in=100, tokens_out=50)
    (call,) = ledger.calls(proj)
    assert call["ok"] is True
    assert call["latency_ms"] >= 0
    assert call["tokens_in"] == 100


def test_meter_marks_failure_and_reraises(proj):
    with pytest.raises(RuntimeError):
        with meter.meter("code-edit", root=proj) as m:
            m.usage(provider="anthropic", model="claude-opus-4-8",
                    tokens_in=1, tokens_out=0)
            raise RuntimeError("provider blew up")
    (call,) = ledger.calls(proj)
    assert call["ok"] is False


def test_meter_without_usage_records_nothing(proj):
    with meter.meter("code-edit", root=proj):
        pass  # never called .usage → no provider → no row
    assert ledger.calls(proj) == []


def test_metercmd_tolerates_dash_dash_separator(proj):
    # `cage data meter -- <cmd>` — argparse REMAINDER keeps the `--`; run() must strip
    # it like graphifymeter does, and still propagate the child's exit code.
    import sys

    from cage import metercmd

    ok = [sys.executable, "-c", "raise SystemExit(0)"]
    fail = [sys.executable, "-c", "raise SystemExit(3)"]
    assert metercmd.run(proj, ["--", *ok]) == 0
    assert metercmd.run(proj, ["--", *fail]) == 3
    assert metercmd.run(proj, ["--"]) == 2  # separator alone = nothing to run


def test_record_call_stores_a_supplied_figure_and_derives_none(tmp_path):
    """`est_cost_usd` is accepted and stored verbatim (a self-costing provider knows its
    own figure) but cage never computes one — there is no price table left to compute it
    from, and no view reads the field (USAGE-ONLY, ADR 0011)."""
    from cage import ledger, metering, paths
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    metering.record_call(route="r", provider="selfbill", model="custom",
                         tokens_in=1000, tokens_out=100, est_cost_usd=0.42,
                         root=tmp_path)
    metering.record_call(route="r", provider="anthropic", model="claude-sonnet-4-6",
                         tokens_in=1_000_000, tokens_out=0, root=tmp_path)
    supplied, derived = ledger.calls(tmp_path)
    assert supplied["est_cost_usd"] == 0.42
    assert derived["est_cost_usd"] == 0.0, "cage must not derive a cost"
