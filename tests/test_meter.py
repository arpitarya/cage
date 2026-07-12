"""The library adapter: record_call / record_receipt / meter()."""
from __future__ import annotations

import pytest

from cage import ledger, metering as meter


def test_record_call_computes_cost_from_policy(proj):
    cid = meter.record_call(route="code-edit", provider="anthropic",
                            model="claude-sonnet-4-6", tokens_in=8600, tokens_out=1500,
                            task="t", root=proj)
    assert cid.startswith("c_")
    (call,) = ledger.calls(proj)
    assert call["est_cost_usd"] == pytest.approx(0.0483, abs=1e-6)
    assert call["task"] == "t"


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
    # `cage meter -- <cmd>` — argparse REMAINDER keeps the `--`; run() must strip
    # it like graphifymeter does, and still propagate the child's exit code.
    import sys

    from cage import metercmd

    ok = [sys.executable, "-c", "raise SystemExit(0)"]
    fail = [sys.executable, "-c", "raise SystemExit(3)"]
    assert metercmd.run(proj, ["--", *ok]) == 0
    assert metercmd.run(proj, ["--", *fail]) == 3
    assert metercmd.run(proj, ["--"]) == 2  # separator alone = nothing to run
