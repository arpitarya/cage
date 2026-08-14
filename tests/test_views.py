"""Read views: report, provenance, and the CLI dispatch.

The `budget` and `roi` halves went with the money subsystem (USAGE-ONLY, ADR 0011).
"""
from __future__ import annotations

from cage import cli, metering as meter, policy, provenance, report


def test_report_groups_and_totals(seeded):
    root, _ = seeded
    rep = report.summarize(root, policy.load(None), dim="route")
    assert rep["total"]["calls"] == 1
    assert rep["total"]["tokens_in"] == 8600
    # `route` collapses to "chat" for any agent with a metric spine: the metric stores
    # carry no route field, so `_spend_row` defaults it rather than inventing one. The
    # demo's `calls` row said "code-edit"; that row is superseded (USAGE-ONLY).
    assert "chat" in rep["groups"]


def test_report_counts_tokens_per_agent(proj):
    """An agent with no metric spine keeps resolving from `calls` (USAGE-ONLY): the
    library/proxy rows this pins are exactly the ones a metric-only `spend()` would
    have silently zeroed."""
    from cage import ledger, paths, schema
    calls_path = paths.Footprint(proj).calls
    ledger.append(calls_path, schema.make_call(
        route="chat", provider="anthropic", model="claude-sonnet-4-6",
        tokens_in=1_000_000, tokens_out=0, agent="orff",
        ts="2026-06-01T12:00:00Z"))
    ledger.append(calls_path, schema.make_call(
        route="search", provider="parallel", model="search",
        tokens_in=7, tokens_out=3, agent="lib"))
    rep = report.summarize(proj, policy.load(None), dim="agent")
    assert rep["groups"]["orff"]["tokens_in"] == 1_000_000
    assert rep["groups"]["lib"]["tokens_out"] == 3


def test_provenance_links_call_to_receipts(seeded):
    root, call_id = seeded
    data = provenance.explain(root, call_id)
    assert data["call"]["id"] == call_id
    assert {r["tool"] for r in data["receipts"]} == {"graphify", "fux", "compressor"}


def test_cli_demo_then_views_exit_zero(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    assert cli.main(["demo"]) == 0
    assert cli.main(["insights", "attrib"]) == 0
    assert cli.main(["report", "--by", "model"]) == 0
    assert cli.main(["report", "--json"]) == 0
    out = capsys.readouterr().out
    assert "graphify" in out


def test_cli_why_unknown_call(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    assert cli.main(["insights", "why", "c_nope"]) == 0
    assert "no call" in capsys.readouterr().out
