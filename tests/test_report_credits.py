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

USD = display.Display()


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
def test_csv_omits_credits_column_when_absent(proj):
    _call(proj)
    out = report.render_csv(report.summarize(proj, _pol(), dim="agent"))
    assert "credits" not in out.splitlines()[0].split(",")
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
