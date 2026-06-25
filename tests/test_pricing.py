"""Family-prefix price fallback + the explicit-UNPRICED signal (no silent $0)."""
from __future__ import annotations

import pytest

from cage import policy, prices, report
from cage import metering as meter

# A minimal, explicit price table — independent of the bundled policy so the
# numbers below never drift if data/policy.toml is retuned.
POL = {"prices": {"anthropic": {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-sonnet-4-5": {"input": 3.3, "output": 16.5, "cache_read": 0.33},
    "claude-opus-4-8": {"input": 15.0, "output": 75.0, "cache_read": 1.5},
}}}


def test_exact_match_still_wins():
    row, match, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-6")
    assert match == "exact" and key == "claude-sonnet-4-6"
    assert row["input"] == 3.0


def test_dated_id_resolves_to_family_row():
    # A full dated Claude Code id with no exact row → its family row's numbers.
    row, match, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-5-20250929")
    assert match == "family" and key == "claude-sonnet-4-5"
    assert (row["input"], row["output"]) == (3.3, 16.5)
    # And the cost path uses those per-million numbers: 1M in = $3.30.
    assert prices.call_cost_usd(POL, "anthropic", "claude-sonnet-4-5-20250929",
                                1_000_000, 0) == pytest.approx(3.30, abs=1e-6)


def test_cross_family_never_borrows():
    # A dated opus id must NOT price off any sonnet row — brand+tier must agree.
    pol = {"prices": {"anthropic": {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3}}}}
    row, match, key = policy.price_match(pol, "anthropic", "claude-opus-4-1-20250805")
    assert match == "none" and key is None
    assert row == {"input": 0.0, "output": 0.0, "cache_read": 0.0}


def test_unknown_model_reports_unpriced_not_zero_dollars(proj):
    # A genuinely unknown model (no exact, no family, no self-cost) must surface as
    # UNPRICED in the report rather than disappear as a $0 line in the totals.
    meter.record_call(route="chat", provider="anthropic", model="claude-mystery-9",
                      tokens_in=1_000_000, tokens_out=0, est_cost_usd=0.0, root=proj)
    rep = report.summarize(proj, POL, dim="model")
    assert rep["total"]["usd"] == 0.0
    assert "anthropic/claude-mystery-9" in rep["unpriced"]
    assert "UNPRICED" in report.render_report(rep)


def test_family_priced_call_is_flagged_approximate(proj):
    meter.record_call(route="chat", provider="anthropic",
                      model="claude-sonnet-4-5-20250929",
                      tokens_in=1_000_000, tokens_out=0, est_cost_usd=0.0, root=proj)
    rep = report.summarize(proj, POL, dim="model")
    assert rep["total"]["usd"] == pytest.approx(3.30, abs=1e-6)  # priced by family
    assert rep["family"].get("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
    assert "priced by family" in report.render_report(rep)
    assert not rep["unpriced"]


def test_longest_prefix_tiebreak_is_deterministic():
    # claude-sonnet-4-5-x shares 4 segs with -4-5 but only 3 with -4-6 → longest wins.
    _, _, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-5-20250101")
    assert key == "claude-sonnet-4-5"
    # Equal-length tie → lexicographically smallest key, regardless of dict order.
    tie = {"prices": {"anthropic": {
        "claude-sonnet-4-6": {"input": 9.0, "output": 9.0, "cache_read": 0.0},
        "claude-sonnet-4-5": {"input": 1.0, "output": 1.0, "cache_read": 0.0}}}}
    rev = {"prices": {"anthropic": dict(reversed(list(tie["prices"]["anthropic"].items())))}}
    # "claude-sonnet-4" has 3 common segments with both → tie → "…-4-5" (lex-min).
    for p in (tie, rev):
        _, match, key = policy.price_match(p, "anthropic", "claude-sonnet-4")
        assert match == "family" and key == "claude-sonnet-4-5"
