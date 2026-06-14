"""Read views: report, budget, roi, provenance, and the CLI dispatch."""
from __future__ import annotations

import pytest

from cage import budget, cli, metering as meter, policy, provenance, report, roi


def test_report_groups_and_totals(seeded):
    root, _ = seeded
    rep = report.summarize(root, dim="route")
    assert rep["total"]["calls"] == 1
    assert rep["total"]["usd"] == pytest.approx(0.0483, abs=1e-6)
    assert "code-edit" in rep["groups"]


def test_budget_flags_over_ceiling(proj):
    pol = policy.load(None)
    pol["budgets"] = {"daily_usd": 0.01, "session_usd": None, "on_exceed": "block"}
    meter.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                      tokens_in=100000, tokens_out=0, root=proj)
    verdict = budget.check(proj, pol)
    assert verdict["over"] is True
    assert verdict["proceed"] is False  # block mode stops the call


def test_budget_warn_mode_still_proceeds(proj):
    pol = policy.load(None)
    pol["budgets"] = {"daily_usd": 0.0001, "session_usd": None, "on_exceed": "warn"}
    meter.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                      tokens_in=100000, tokens_out=0, root=proj)
    verdict = budget.check(proj, pol)
    assert verdict["over"] is True and verdict["proceed"] is True


def test_roi_converts_token_savings_to_usd(seeded):
    root, _ = seeded
    data = roi.by_tool(root, policy.load(None))
    assert data["tools"]["graphify"]["saved_usd"] == pytest.approx(27000 * 3 / 1e6, abs=1e-6)


def test_provenance_links_call_to_receipts(seeded):
    root, call_id = seeded
    data = provenance.explain(root, call_id)
    assert data["call"]["id"] == call_id
    assert {r["tool"] for r in data["receipts"]} == {"graphify", "fux", "compressor"}


def test_cli_demo_then_views_exit_zero(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    assert cli.main(["demo"]) == 0
    assert cli.main(["attrib"]) == 0
    assert cli.main(["matrix"]) == 0
    assert cli.main(["report", "--by", "model"]) == 0
    assert cli.main(["report", "--json"]) == 0
    out = capsys.readouterr().out
    assert "graphify" in out


def test_cli_why_unknown_call(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    assert cli.main(["why", "c_nope"]) == 0
    assert "no call" in capsys.readouterr().out
