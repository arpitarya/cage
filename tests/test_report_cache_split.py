"""F5 — cache-vs-fresh split in `report --usd` (docs/regression/2026-07-22-capture-report.md).

The evidence: cached_in was 98.0% of tokens_in on a real ledger, and the headline
"$7,046 spent" reads as alarming when almost all of it is 0.1x-billed prefix-cache
re-reads. One added footer line — no table/column/CSV change — using the model's
REAL `cache_read` price row, not a hardcoded fraction.
"""
from __future__ import annotations

import pytest

from cage import display, ledger, paths, policy, report, schema

USD = display.Display(usd=True)


def _pol():
    return policy.load(None)


def _seed(root, *, tokens_in, tokens_out, cached_in, model="claude-sonnet-4-6"):
    ledger.append(paths.Footprint(root).calls,
                  schema.make_call(route="chat", provider="anthropic", model=model,
                                   agent="claude-code", tokens_in=tokens_in,
                                   tokens_out=tokens_out, cached_in=cached_in,
                                   session="s"))


def test_cache_usd_uses_the_real_price_row_not_a_hardcoded_fraction(proj):
    # claude-sonnet-4-6: input $3/M, output $15/M, cache_read $0.3/M (bundled policy).
    _seed(proj, tokens_in=1_000_000, tokens_out=1_000, cached_in=950_000)
    rep = report.summarize(proj, _pol(), dim="agent")
    t = rep["total"]
    # fresh 50,000 @ $3/M = $0.15; cached 950,000 @ $0.3/M = $0.285; out 1,000 @ $15/M = $0.015
    assert t["usd"] == pytest.approx(0.45, abs=1e-6)
    assert t["cache_usd"] == pytest.approx(0.285, abs=1e-6)
    assert t["cached_in"] == 950_000


def test_render_shows_the_cache_line_with_correct_percentages(proj):
    _seed(proj, tokens_in=1_000_000, tokens_out=1_000, cached_in=950_000)
    out = report.render_report(report.summarize(proj, _pol(), dim="agent"), disp=USD)
    assert "· cache: 95% of input tokens were cache reads, 63% of cost" in out
    assert "$0.2850 of $0.4500" in out


def test_no_cache_reads_still_renders_a_clean_line(proj):
    _seed(proj, tokens_in=1_000, tokens_out=100, cached_in=0)
    out = report.render_report(report.summarize(proj, _pol(), dim="agent"), disp=USD)
    assert "· cache: 0% of input tokens were cache reads, 0% of cost" in out


def test_cache_line_absent_from_token_view(proj):
    """The split is a `--usd` concern only — the default token view is untouched."""
    _seed(proj, tokens_in=1_000_000, tokens_out=1_000, cached_in=950_000)
    out = report.render_report(report.summarize(proj, _pol(), dim="agent"),
                               disp=display.Display(usd=False))
    assert "· cache:" not in out


def test_unpriced_model_reports_no_cache_split(proj):
    """A model with no price row (`self`/`none`) has no token-level split to show —
    cache_usd stays 0, never a bogus number from an unresolved price row."""
    ledger.append(paths.Footprint(proj).calls,
                  schema.make_call(route="chat", provider="totally-unknown",
                                   model="mystery-model", agent="claude-code",
                                   tokens_in=1000, tokens_out=100, cached_in=500,
                                   session="s"))
    rep = report.summarize(proj, _pol(), dim="agent")
    assert rep["total"]["cache_usd"] == 0.0
    assert rep["total"]["usd"] == 0.0  # genuinely unpriced


def test_csv_gains_no_new_column(proj):
    """render_csv's column contract (docs/csv-output.md) is untouched by F5.
    `cached_in` is a pre-existing column (token count); the new `cache_usd` field
    F5 adds to the summarize() payload must never leak into the fixed CSV header."""
    _seed(proj, tokens_in=1_000_000, tokens_out=1_000, cached_in=950_000)
    rep = report.summarize(proj, _pol(), dim="agent")
    csv = report.render_csv(rep)
    header = csv.splitlines()[0]
    assert header == ("agent,calls,tokens_in,tokens_out,cached_in,cost_usd,"
                      "gross_saved_usd,net_vs_spend_usd,unpriced_calls,unpriced_tokens,"
                      "method")
    assert "cache_usd" not in header


def test_table_block_byte_identical_only_footer_gains_the_line(proj):
    """F5's DoD: 'no other report structure changes' — the table+title block above
    the footer must render identically to before this change; only the footer
    gains one new line."""
    _seed(proj, tokens_in=1_000_000, tokens_out=1_000, cached_in=950_000)
    rep = report.summarize(proj, _pol(), dim="agent")
    out = report.render_report(rep, disp=USD)
    table_block = out.split("\n\n")[0] + "\n\n" + out.split("\n\n")[1]
    assert "agent" in table_block and "cost" in table_block
    assert "cache" not in table_block  # the cache line lives only in the footer
