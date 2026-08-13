"""REPORT-CREDITS — `cage report` folds in `ledger.credits` (kiro-CLI conversations,
no call, no tokens) as its own column, on the `agent` and default `route` dims.

Token/calls cells for a credits-only group render `—` in text / empty in CSV — the
absence-vs-measured-zero rule every credits figure in cage carries — never a
fabricated `0`. The rare mixed case (a group whose calls and credits rows share one
bucket) sums both sides into the cost cell rather than silently dropping the rated
credits dollar, and names the split.
"""
from __future__ import annotations

import pytest

from cage import display, ledger, paths, policy, report, schema

USD = display.Display(usd=True)


def _pol(billing: dict | None = None):
    pol = policy.load(None)
    if billing:
        pol = {**pol, "billing": billing}
    return pol


def _call(root, *, agent="claude-code", tin=100, tout=10, session="c1",
         ts="2026-07-01T09:00:00Z"):
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="anthropic",
                                   model="claude-sonnet-4-6", tokens_in=tin,
                                   tokens_out=tout, agent=agent, session=session, ts=ts))


def _credit(root, *, session, agent="kiro", credits=4.0, turns=3,
           ts="2026-07-01T10:00:00Z"):
    ledger.append_row(root, "credits", schema.make_credit(
        session=session, credits=credits, agent=agent, turns=turns, ts=ts))


# ── the credits-only row: N/A tokens, filled credits ────────────────────────────

def test_credits_only_agent_renders_dash_tokens_and_filled_credits(proj):
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol(), dim="agent")
    g = rep["groups"]["kiro"]
    assert g["calls"] == 0 and g["credits"] == pytest.approx(4.0)
    out = report.render_report(rep)
    lines = {l.split()[0]: l for l in out.splitlines() if l.startswith("kiro")}
    row = lines["kiro"].split()
    assert row[1:4] == ["—", "—", "—"]      # calls, tok in, tok out
    assert row[4] == "4.00"                 # credits


def test_credits_column_absent_when_no_credits_recorded(proj):
    """Byte-identical to pre-feature behavior when nothing recorded a credit —
    the column must not appear (no golden re-bless for an unrelated ledger)."""
    _call(proj)
    out = report.render_report(report.summarize(proj, _pol(), dim="agent"))
    assert "credits" not in out.splitlines()[2]  # header row


def test_credits_column_absent_on_unrelated_dims(proj):
    """Only `route` and `agent` fold in credits — model/provider/day/task stay
    untouched (a credits row doesn't carry those fields cleanly)."""
    _call(proj)
    _credit(proj, session="s1")
    for dim in ("model", "provider", "day"):
        rep = report.summarize(proj, _pol(), dim=dim)
        assert rep["total"]["credits"] is None
        assert "credits" not in report.render_report(rep).splitlines()[2]


def test_default_route_view_gets_a_synthetic_credits_bucket(proj):
    _call(proj)
    _credit(proj, session="s1", credits=2.5)
    rep = report.summarize(proj, _pol(), dim="route")
    assert set(rep["groups"]) == {"chat", "credits"}
    assert rep["groups"]["credits"]["credits"] == pytest.approx(2.5)
    assert rep["groups"]["credits"]["calls"] == 0
    out = report.render_report(rep)
    assert "credits" in [l.split()[0] for l in out.splitlines() if l and l[0].isalpha()]


def test_a_real_recorded_zero_renders_as_a_real_zero_not_a_dash(proj):
    _credit(proj, session="s1", credits=0.0)
    rep = report.summarize(proj, _pol(), dim="agent")
    assert rep["groups"]["kiro"]["credits"] == 0.0
    out = report.render_report(rep)
    row = next(l for l in out.splitlines() if l.startswith("kiro"))
    assert "0.00" in row.split()


# ── rate ladder: unset / configured / zero ──────────────────────────────────────

def test_cost_cell_dash_when_rate_unset(proj):
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol(), dim="agent")
    out = report.render_report(rep, disp=USD)
    row = next(l for l in out.splitlines() if l.startswith("kiro"))
    assert row.rstrip().endswith("—")
    assert "not priced" in out and "conversation" in out
    assert "set [billing.kiro] usd_per_credit" in out


def test_cost_cell_prices_via_configured_rate(proj):
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol({"kiro": {"usd_per_credit": 0.05}}), dim="agent")
    g = rep["groups"]["kiro"]
    assert g["credits_usd"] == pytest.approx(0.20)
    assert g["credits_rated"] is True
    out = report.render_report(rep, disp=USD)
    row = next(l for l in out.splitlines() if l.startswith("kiro"))
    assert "$0.2000" in row


def test_cost_cell_prices_a_configured_zero_rate_as_a_real_zero(proj):
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol({"kiro": {"usd_per_credit": 0.0}}), dim="agent")
    out = report.render_report(rep, disp=USD)
    row = next(l for l in out.splitlines() if l.startswith("kiro"))
    assert "$0.0000" in row
    assert "not priced" not in out  # a configured zero IS a price, not an unrated gap


# ── the total never silently drops a rated credits dollar ───────────────────────

def test_total_cost_sums_token_and_credits_rated_dollars(proj):
    """The regression this feature almost shipped with: the TOTAL row's cost cell
    dropped a rated credits dollar entirely when any other group had real calls."""
    _call(proj, tin=100, tout=10)  # ≈ $0.00045 at bundled claude-sonnet-4-6 rates
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol({"kiro": {"usd_per_credit": 0.05}}), dim="agent")
    t = rep["total"]
    assert t["usd"] > 0 and t["credits_usd"] == pytest.approx(0.20)
    out = report.render_report(rep, disp=USD)
    total_row = next(l for l in out.splitlines() if l.startswith("TOTAL"))
    expected = t["usd"] + t["credits_usd"]
    assert report.render.usd(expected) in total_row
    assert "total spans two pricing bases" in out


def test_net_vs_spend_subtracts_the_full_spend_including_rated_credits(proj):
    """`net vs spend` must not overstate a saving by excluding a rated credits
    dollar the cost column already counts."""
    from cage import ledger as _ledger
    _call(proj, tin=100, tout=10, session="task-a")
    _credit(proj, session="s1", credits=4.0)
    rep = report.summarize(proj, _pol({"kiro": {"usd_per_credit": 0.05}}), dim="agent")
    t = rep["total"]
    assert t["net_usd"] == pytest.approx(t["saved_usd"] - t["usd"] - t["credits_usd"])


# ── CSV: empty, never a fabricated zero; method degrades to modeled ─────────────

def test_csv_leaves_credits_only_cells_empty_not_zero(proj):
    import csv as _csv
    import io
    _call(proj)
    _credit(proj, session="s1", credits=1.25)
    rows = list(_csv.DictReader(io.StringIO(
        report.render_csv(report.summarize(proj, _pol(), dim="agent")))))
    kiro = next(r for r in rows if r["agent"] == "kiro")
    for f in ("calls", "tokens_in", "tokens_out", "cached_in", "cost_usd"):
        assert kiro[f] == ""
    assert kiro["credits"] == "1.25"


def test_csv_method_degrades_to_modeled_when_credits_rated(proj):
    import csv as _csv
    import io
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rated = _pol({"kiro": {"usd_per_credit": 0.05}})
    rows = list(_csv.DictReader(io.StringIO(
        report.render_csv(report.summarize(proj, rated, dim="agent")))))
    assert all(r["method"] == "modeled" for r in rows)


def test_csv_stays_measured_when_credits_unrated(proj):
    import csv as _csv
    import io
    _call(proj)
    _credit(proj, session="s1", credits=4.0)
    rows = list(_csv.DictReader(io.StringIO(
        report.render_csv(report.summarize(proj, _pol(), dim="agent")))))
    assert all(r["method"] == "measured" for r in rows)


def test_csv_omits_credits_column_when_absent(proj):
    _call(proj)
    out = report.render_csv(report.summarize(proj, _pol(), dim="agent"))
    assert "credits" not in out.splitlines()[0].split(",")


# ── the mixed case: a group with both calls and credits ─────────────────────────

def test_a_group_with_both_calls_and_credits_sums_its_own_cost_cell(proj):
    """The rare case: an agent's real calls and its credits rows share one bucket
    (e.g. a machine ledger where both routes land). The row's own cost cell sums
    both bases rather than dropping the credits side."""
    _call(proj, agent="kiro", tin=1000, tout=100, session="ide-session")
    _credit(proj, session="cli-session", credits=4.0)
    rep = report.summarize(proj, _pol({"kiro": {"usd_per_credit": 0.05}}), dim="agent")
    g = rep["groups"]["kiro"]
    assert g["calls"] == 1 and g["credits"] == pytest.approx(4.0)
    out = report.render_report(rep, disp=USD)
    row = next(l for l in out.splitlines() if l.startswith("kiro"))
    # real token counts render (not dashed — this group DOES have a call)
    assert "1,000" in row or "1000" in row.replace(",", "")
    expected = report.render.usd(g["usd"] + g["credits_usd"])
    assert expected in row


# ── --since / --scope / --project pass through like calls ───────────────────────

def test_since_filters_credit_rows_by_ts(proj):
    _credit(proj, session="old", credits=1.0, ts="2020-01-01T00:00:00Z")
    _credit(proj, session="new", credits=1.0)  # default ts 2026-07-01
    rep = report.summarize(proj, _pol(), dim="agent", since="100d")
    assert rep["groups"]["kiro"]["credits"] == pytest.approx(1.0)


def test_determinism(proj):
    _call(proj)
    _credit(proj, session="s1", credits=3.3)
    rep = report.summarize(proj, _pol(), dim="agent")
    assert rep == report.summarize(proj, _pol(), dim="agent")
    assert (report.render_report(rep) ==
            report.render_report(report.summarize(proj, _pol(), dim="agent")))
