"""Pricing freshness (plan §3.3) — three local signals, one implementation,
three render surfaces (post-commit / doctor / report footer). Goldens pin the
age wording exactly; the data-relative anchor is proven with fixed-`ts`
fixtures (a wall-clock leak would change the asserted N); the `[prices]`
scalar regression guards the hardened iteration sites."""
from __future__ import annotations

import datetime as dt

import pytest

from cage import (cli, freshness, hooks, ledger, paths, policy, pricescmd,
                  pricestoml, receiptprice, report, schema)

_META = {"meta": {"prices_version": "2026-01-01", "prices_date": "2026-01-01"}}


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage").mkdir()
    monkeypatch.chdir(proj)
    return proj


@pytest.fixture
def bundle_meta(monkeypatch):
    """Pin the bundled [meta] so age goldens never drift when the real bundle
    is re-researched."""
    monkeypatch.setattr("cage.policy.bundled_raw", lambda: dict(_META))


def _call(root, *, model="claude-opus-4-8", provider="anthropic",
          ts="2026-02-01T10:00:00Z", call_id="c1", tokens_in=1000):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider=provider, model=model, tokens_in=tokens_in,
        tokens_out=100, agent="claude-code", ts=ts, call_id=call_id))


# ── age signal (the one new wording — golden) ────────────────────────────────

def test_age_line_exact_wording(bundle_meta):
    line = freshness.age_line({}, dt.date(2026, 3, 2))  # 60 days past 2026-01-01
    assert line == "bundled prices are 60 days old — check for a newer cage release"


def test_age_line_fresh_and_boundary_are_silent(bundle_meta):
    assert freshness.age_line({}, dt.date(2026, 1, 20)) is None       # 19 days
    assert freshness.age_line({}, dt.date(2026, 2, 15)) is None       # exactly 45


def test_age_line_no_anchor_or_unparseable_meta(bundle_meta, monkeypatch):
    assert freshness.age_line({}, None) is None
    monkeypatch.setattr("cage.policy.bundled_raw", lambda: {"meta": {}})
    assert freshness.age_line({}, dt.date(2026, 9, 1)) is None
    monkeypatch.setattr("cage.policy.bundled_raw",
                        lambda: {"meta": {"prices_date": "not-a-date"}})
    assert freshness.age_line({}, dt.date(2026, 9, 1)) is None


def test_stale_days_policy_preferred_with_constant_fallback(bundle_meta):
    from cage.constants import PRICES_STALE_DAYS
    assert policy.prices_stale_days({}) == PRICES_STALE_DAYS
    assert policy.prices_stale_days({"prices": {"stale_days": 10}}) == 10
    assert policy.prices_stale_days({"prices": {"stale_days": "junk"}}) == PRICES_STALE_DAYS
    # override honored: 10-day threshold fires where the default 45 stays silent
    pol = {"prices": {"stale_days": 10}}
    assert freshness.age_line(pol, dt.date(2026, 1, 20)) is not None   # 19 > 10
    # 0 disables the signal entirely (the documented opt-out)
    assert freshness.age_line({"prices": {"stale_days": 0}}, dt.date(2027, 1, 1)) is None


# ── data-relative anchor (determinism law) ───────────────────────────────────

def test_age_is_data_relative_never_wall_clock(root, bundle_meta):
    # Newest ledger ts = 100 days past prices_date. Any wall-clock leak would
    # yield a different (ever-growing) N — the exact 100 pins the anchor.
    _call(root, ts="2026-03-01T10:00:00Z", call_id="c_old")
    _call(root, ts="2026-04-11T10:00:00Z", call_id="c_new")
    lines = freshness.freshness(root, {}, include_unpriced=False)
    assert lines == ["bundled prices are 100 days old — check for a newer cage release"]


def test_empty_ledger_age_is_doctor_only(root, bundle_meta):
    # No rows ⇒ no data-relative anchor ⇒ report path silent (handoff §8)…
    assert freshness.freshness(root, {}, include_unpriced=False) == []
    # …while a clock-allowed caller (doctor / post-commit) still ages the bundle.
    lines = freshness.freshness(root, {}, today=dt.date(2026, 3, 2),
                                include_unpriced=False)
    assert lines == ["bundled prices are 60 days old — check for a newer cage release"]


def test_newest_ts_helper():
    rows = [{"ts": "2026-06-01T10:00:00Z"}, {"ts": "2026-07-01T10:00:00Z"}, {"x": 1}]
    assert ledger.newest_ts(rows) == dt.datetime(2026, 7, 1, 10,
                                                 tzinfo=dt.timezone.utc)
    assert ledger.newest_ts([]) is None
    assert ledger.newest_ts([{"ts": "garbage"}]) is None


# ── sync signal (verbatim reuse of sync_recommendation) ──────────────────────

def test_sync_line_verbatim_and_pre_v019_policy(root):
    assert freshness.sync_line(root) is None  # no project policy ⇒ bundle applies
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    line = freshness.sync_line(root)
    assert line == pricescmd.sync_recommendation({"prices_version": "2020-01-01"})
    assert "cage prices sync" in line
    # pre-v0.19 project policy (no [meta] at all) reads as stale
    paths.Footprint(root).policy.write_text("[budgets]\nsession_usd = 1.0\n",
                                            encoding="utf-8")
    assert "unknown (pre-0.19)" in freshness.sync_line(root)


def test_sync_line_clean_after_restamp(root):
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    assert freshness.sync_line(root) is not None
    pricestoml.update_meta(root, dict(policy.bundled_raw().get("meta", {})))
    assert freshness.sync_line(root) is None


# ── UNPRICED signal (byte-equal reuse of the existing hints) ─────────────────

def test_unpriced_lines_reuse_existing_helpers(root):
    pol = policy.load(None)
    _call(root, provider="mistral", model="mystery-9", call_id="c_u",
          tokens_in=5000)
    lines = freshness.unpriced_lines(root, pol)
    assert lines == [report.unpriced_line(
        {"mistral/mystery-9": {"calls": 1, "tokens": 5100}})]
    # a call-less token receipt with no route → the receipts twin, byte-equal
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="fux", raw_alternative=10_000.0, actual=0.0, unit="tokens",
        method="modeled", task="t-x", ts="2026-02-01T11:00:00Z"))
    lines = freshness.unpriced_lines(root, pol)
    assert lines[1] == receiptprice.unpriced_receipts_line(
        {"receipts": 1, "tokens": 10_000, "tools": ["fux"]})


def test_freshness_clean_is_empty(root, bundle_meta):
    _call(root, ts="2026-01-10T10:00:00Z")  # 9 days past prices_date — fresh
    assert freshness.freshness(root, policy.load(None)) == []


# ── surface: post-commit (print-only, fail-open, cage:-prefixed) ─────────────

def test_post_commit_prints_prefixed_notes_and_exits_zero(root, capsys):
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    assert hooks.post_commit() == 0
    out = capsys.readouterr().out
    assert "cage: bundled prices are newer (" in out
    assert "cage prices sync" in out


def test_post_commit_silent_when_clean(root, bundle_meta, capsys, monkeypatch):
    # freeze the hook's clock inside the stale window so the age signal is clean
    class _D(dt.date):
        @classmethod
        def today(cls):
            return dt.date(2026, 1, 10)
    monkeypatch.setattr("datetime.date", _D)
    assert hooks.post_commit() == 0
    assert capsys.readouterr().out == ""


def test_post_commit_freshness_failure_swallowed_and_logged(root, monkeypatch, capsys):
    from cage import debuglog
    monkeypatch.setenv("CAGE_DEBUG", "1")

    def _boom(*_a, **_k):
        raise RuntimeError("forced failure (audit)")
    monkeypatch.setattr("cage.freshness.freshness", _boom)
    assert hooks.post_commit() == 0  # fail-open holds
    contexts = {e.get("context", "") for e in debuglog.tail(root, 0)
                if e.get("event") == "exception"}
    assert "hook.post_commit.freshness" in contexts  # …but never silent


# ── surface: report footer (actionable-only, deterministic, never in CSV) ────

def test_report_footer_data_relative_and_deterministic(root, bundle_meta):
    _call(root, ts="2026-04-11T10:00:00Z")  # 100 days past prices_date
    pol = policy.load(None)
    rep = report.summarize(root, pol)
    assert rep["freshness"] == [
        "bundled prices are 100 days old — check for a newer cage release"]
    text = report.render_report(rep)
    assert "· bundled prices are 100 days old — check for a newer cage release" in text
    assert report.render_report(report.summarize(root, pol)) == text  # byte-identical
    # handoff §10: the freshness note never enters CSV
    assert "days old" not in str(report.render_csv(rep))


def test_report_footer_absent_when_clean(root, bundle_meta):
    _call(root, ts="2026-01-10T10:00:00Z")  # 9 days — fresh
    rep = report.summarize(root, policy.load(None))
    assert rep["freshness"] == []
    assert "days old" not in report.render_report(rep)


def test_report_unpriced_not_duplicated_by_footer(root, bundle_meta):
    # report renders the UNPRICED ⚠ natively; the freshness footer must not
    # repeat it (include_unpriced=False on the report path)
    _call(root, provider="mistral", model="mystery-9", call_id="c_u",
          ts="2026-01-10T10:00:00Z")
    from cage import display
    rep = report.summarize(root, policy.load(None))
    text = report.render_report(rep, disp=display.Display(usd=True))
    assert text.count("UNPRICED") == 1
    # token default: the muted pointer speaks once instead of the ⚠ block
    token_text = report.render_report(rep)
    assert "UNPRICED" not in token_text
    assert token_text.count("unpriced — matters when you view $") == 1


# ── regression: a scalar under [prices] must not crash provider iteration ────

def test_prices_scalar_stale_days_does_not_crash_cli(root, capsys):
    pricestoml.update_meta(root, dict(policy.bundled_raw().get("meta", {})))
    p = paths.Footprint(root).policy
    p.write_text(p.read_text(encoding="utf-8") + "\n[prices]\nstale_days = 10\n",
                 encoding="utf-8")
    assert policy.prices_stale_days(policy.load(p)) == 10
    for argv in (["prices", "list"], ["prices", "sync"], ["report"]):
        assert cli.main(argv) == 0, f"cage {' '.join(argv)} crashed"
        capsys.readouterr()


# ── surface: doctor + query ──────────────────────────────────────────────────

def test_doctor_prices_age_levels(root, monkeypatch):
    from cage import doctorcmd
    monkeypatch.setattr("cage.policy.bundled_raw", lambda: dict(_META))
    checks = {c["name"]: c for c in doctorcmd.run(root)["checks"]}
    age = checks["prices-age"]
    assert age["level"] == "warn"  # 2026-01-01 bundle is stale by wall clock now
    assert "check for a newer cage release" in age["detail"]
    # stale_days = 0 ⇒ disabled, OK
    paths.Footprint(root).policy.write_text("[prices]\nstale_days = 0\n",
                                            encoding="utf-8")
    checks = {c["name"]: c for c in doctorcmd.run(root)["checks"]}
    assert checks["prices-age"]["level"] == "ok"
    assert "disabled" in checks["prices-age"]["detail"]


def test_query_prices_freshness_renders_live(root):
    from cage import explain
    (hit,) = explain.match("prices-freshness")
    assert hit.id == "prices-freshness"
    text = explain.render(hit, policy.load(None))
    assert "{" not in text.split("code:")[0]  # every placeholder filled
    from cage.constants import PRICES_STALE_DAYS
    assert f"now: {PRICES_STALE_DAYS}" in text
    stamp = str(policy.bundled_raw()["meta"]["prices_date"])
    assert stamp in text
