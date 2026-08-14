"""METRICS-PRIMARY P0 — `ledger.spend()`, the one derive resolver, and its cutover.

The contract, in one line: rows before `constants.SPEND_CUTOVER` resolve from `calls`,
rows at or after it resolve from the three per-agent metric ledgers, and **no row is
counted twice**.

What this file pins:

1. The cutover is a **literal**, not a clock — the determinism law depends on it.
2. The partition is exact and by the row's OWN `ts`: a session straddling the instant
   contributes to both sides, once each. The boundary itself is inclusive on the metrics
   side (`>= CUTOVER`), so no row can fall in a crack or be claimed twice.
3. **`SPEND_SOURCES` is a spine, not a sum.** Each metric kind deliberately holds several
   overlapping views of the same traffic; summing a kind double-counts. Only the listed
   source per agent may carry money.
4. A `ts`-less row resolves to the `calls` side (the conservative default).
5. `since` is honored on both halves.
"""
from __future__ import annotations

import re

import pytest

from cage import constants, ledger, schema


BEFORE = "2026-08-13T23:59:59Z"
AFTER = "2026-08-14T00:00:01Z"


# ── 1 · the cutover is a pinned literal ──────────────────────────────────────

def test_cutover_is_a_literal_utc_instant():
    """Not `now()`, not computed, and in the one UTC normal form every row is written
    in — a computed cutover would make yesterday's report irreproducible tomorrow."""
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", constants.SPEND_CUTOVER)
    assert constants.SPEND_CUTOVER == "2026-08-14T00:00:00Z"


def test_cutover_source_contains_no_clock_call():
    """The constant must never become a computed value — grep the declaration itself."""
    import inspect
    src = inspect.getsource(constants)
    decl = [ln for ln in src.splitlines() if ln.startswith("SPEND_CUTOVER")]
    assert decl and "now(" not in decl[0] and "utcnow" not in decl[0]


# ── 2 · the partition: exact, by the row's own ts, never doubled ─────────────

def _call(root, ts, **kw):
    row = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4",
                           tokens_in=kw.pop("tokens_in", 100),
                           tokens_out=kw.pop("tokens_out", 10),
                           agent="claude-code", ts=ts, **kw)
    ledger.append_row(root, "calls", row)
    return row


def _claude_metric(root, ts, request="", **kw):
    row = schema.make_claude_metric(session=kw.pop("session", "s1"), ts=ts,
                                    tokens_in=kw.pop("tokens_in", 500),
                                    tokens_out=kw.pop("tokens_out", 50), **kw)
    # P1's request-grain source; P0 pins the resolver against it before it is emitted.
    row["source"] = "request"
    row["request"] = request or f"req-{ts}"
    ledger.append_row(root, "claude", row)
    return row


def test_pre_cutover_resolves_from_calls_only(proj):
    _call(proj, BEFORE)
    _claude_metric(proj, BEFORE)  # a metric row BEFORE the cutover must be ignored
    rows = ledger.spend(proj)
    assert len(rows) == 1
    assert rows[0]["basis"] == "calls"


def test_post_cutover_resolves_from_metrics_only(proj):
    _call(proj, AFTER)  # a call row AFTER the cutover must be ignored
    _claude_metric(proj, AFTER)
    rows = ledger.spend(proj)
    assert len(rows) == 1
    assert rows[0]["basis"] == "metrics"


def test_a_session_straddling_the_cutover_is_counted_once_on_each_side(proj):
    """The risk the whole design turns on. One chat that began before the instant and
    grew after it must contribute its early spend from `calls` and its later spend from
    the metric ledger — never the same tokens twice, never a gap."""
    _call(proj, BEFORE, session="s1", tokens_in=100)
    _call(proj, AFTER, session="s1", tokens_in=999)          # ignored — post-cutover
    _claude_metric(proj, BEFORE, session="s1", tokens_in=888)  # ignored — pre-cutover
    _claude_metric(proj, AFTER, session="s1", tokens_in=500)
    rows = ledger.spend(proj)
    assert sorted(r["tokens_in"] for r in rows) == [100, 500]
    assert {r["basis"] for r in rows} == {"calls", "metrics"}


def test_the_boundary_instant_itself_belongs_to_the_metrics_side(proj):
    """`>= CUTOVER`, so a row stamped exactly at the instant lands on exactly one side."""
    _call(proj, constants.SPEND_CUTOVER)
    _claude_metric(proj, constants.SPEND_CUTOVER)
    rows = ledger.spend(proj)
    assert len(rows) == 1 and rows[0]["basis"] == "metrics"


def test_no_row_is_ever_counted_twice_across_the_boundary(proj):
    """The Definition-of-done assertion, stated directly: every id appears at most once."""
    for ts in (BEFORE, AFTER):
        _call(proj, ts, session="s1")
        _claude_metric(proj, ts, session="s1")
    ids = [r.get("id") for r in ledger.spend(proj)]
    assert len(ids) == len(set(ids))


# ── 3 · SPEND_SOURCES is a spine, never a sum ────────────────────────────────

def test_every_agent_has_a_declared_spine():
    from cage import agents
    assert set(ledger.SPEND_SOURCES) == set(agents.SURFACES)


def test_a_non_spine_source_never_carries_money(proj):
    """Copilot's five stores describe the SAME requests at three grains. `chat` is the
    spine for vscode; a `sidecar` row covering that same request must be ignored, or a
    machine that opts into the gated store silently doubles its own spend."""
    for source, session in (("chat", "c1"), ("sidecar", "c1")):
        row = schema.make_copilot_metric(source=source, session=session, surface="vscode",
                                         model="gpt-4", tokens_in=100, tokens_out=10,
                                         ts=AFTER)
        ledger.append_row(proj, "copilot", row)
    rows = ledger.spend(proj)
    assert len(rows) == 1, "only the spine source may contribute spend"


# ── 3b · a cumulative source may never be a spine ────────────────────────────

def test_no_spine_source_is_cumulative():
    """The rule found while building P0. A cutover partitions by each row's own `ts`, so
    a row carrying its conversation's whole life would land wholly on the metrics side
    while that conversation's earlier traffic is still counted on the `calls` side — a
    straddling conversation billed twice, invisibly, because both halves are individually
    correct. Every cumulative source is excluded and NAMED."""
    for agent, (source, _surface) in ledger.CUMULATIVE_SOURCES.items():
        assert source not in ledger.SPEND_SOURCES[agent], (
            f"{agent}/{source} is cumulative and must never be a spend spine")


def test_cumulative_sources_are_named_not_silently_dropped():
    """A dropped source that is not named reads as "that surface had no spend"."""
    assert set(ledger.CUMULATIVE_SOURCES) == {"copilot", "kiro"}
    for source, surface in ledger.CUMULATIVE_SOURCES.values():
        assert source and surface


def test_a_cumulative_row_contributes_no_spend(proj):
    """The verbatim cumulative rows are excluded, so neither resolves to spend on its
    own — the delta twin (copilot) and the credits mechanism (kiro) carry those surfaces."""
    ledger.append_row(proj, "copilot", schema.make_copilot_metric(
        source="cli", session="c1", surface="cli", tokens_in=100, ts=AFTER))
    ledger.append_row(proj, "kiro", schema.make_kiro_metric(
        source="cli-conv", session="k1", surface="cli", credits=0.5, ts=AFTER))
    assert ledger.spend(proj) == []


def test_the_cli_delta_twin_is_the_copilot_cli_spine(proj):
    """`cli` and `cli-delta` describe the SAME shutdown. Exactly one may carry money."""
    for source in ("cli", "cli-delta"):
        ledger.append_row(proj, "copilot", schema.make_copilot_metric(
            source=source, session="c1", surface="cli", request="s000",
            tokens_in=100, tokens_out=10, ts=AFTER))
    rows = ledger.spend(proj)
    assert len(rows) == 1
    assert sum(r["tokens_in"] for r in rows) == 100, "never the sum of the pair"


# ── 4 · a ts-less row is conservative, never dropped ─────────────────────────

def test_a_row_with_no_ts_resolves_to_the_calls_side(proj):
    row = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4",
                           agent="claude-code", tokens_in=7)
    row.pop("ts", None)
    ledger.append_row(proj, "calls", row)
    rows = ledger.spend(proj)
    assert len(rows) == 1 and rows[0]["basis"] == "calls"


# ── 5 · the normalized shape never invents a field ───────────────────────────

def test_normalization_is_additive_only(proj):
    """A field the metric kind does not carry stays absent — exactly as it would on a
    legacy call row — and is never synthesized to a zero."""
    _claude_metric(proj, AFTER)
    row = ledger.spend(proj)[0]
    assert row["basis"] == "metrics"
    assert "provider" not in row, "claude metric rows carry no provider — do not invent one"
    assert row["route"] == "chat" and row["ok"] is True


def test_since_is_honored_on_both_halves(proj):
    _call(proj, "2026-01-02T00:00:00Z")
    _claude_metric(proj, AFTER)
    assert len(ledger.spend(proj)) == 2
    narrow = ledger.spend(proj, since="7d")
    assert all(r["basis"] == "metrics" for r in narrow), (
        "the old calls row should fall outside the window; the metric row is recent")


# ── 6 · an empty ledger is empty, not an error ───────────────────────────────

def test_empty_ledger_resolves_to_nothing(proj):
    assert ledger.spend(proj) == []


# ── 7 · the money path: one choke point, no fork (P2) ────────────────────────

def test_a_metric_sourced_spend_row_prices_through_call_usd_match(proj):
    """The real P2. The handoff's §5.4 said "stamp `est_cost_usd` at capture" — but that
    field is only a LAST-RESORT fallback in `prices.call_usd_match` (for a provider cage
    cannot tokenize), and the transcript meter deliberately never sets it. What actually
    blocked pricing was `provider`: `policy.price_match` keys on `(provider, model)`, so a
    perfectly-counted metric row priced as `none`. Stamping the provider — the SAME
    derivation `parse_calls` already makes for this store — makes the row price through
    the one existing choke point with no per-view fork."""
    from cage import paths, policy, prices
    from srcseed import mkcage
    mkcage(proj)
    pol = policy.load(paths.Footprint(proj).policy)
    row = ledger._spend_row({
        "id": "clm_x", "ts": AFTER, "agent": "claude-code", "source": "request",
        "provider": "anthropic", "model": "claude-opus-4", "session": "s1",
        "tokens_in": 10000, "tokens_out": 500, "cached_in": 9000})
    usd, match, _matched = prices.call_usd_match(pol, row)
    assert match == "exact" and usd > 0


def test_a_spend_row_without_a_provider_prices_as_none_not_as_zero(proj):
    """Why the field is load-bearing, stated as a test so it cannot be dropped as
    redundant: without `provider` the row is not cheap, it is UNPRICED."""
    from cage import paths, policy, prices
    from srcseed import mkcage
    mkcage(proj)
    pol = policy.load(paths.Footprint(proj).policy)
    row = ledger._spend_row({"id": "clm_y", "ts": AFTER, "agent": "claude-code",
                             "source": "request", "model": "claude-opus-4",
                             "session": "s1", "tokens_in": 10000, "tokens_out": 500})
    _usd, match, _m = prices.call_usd_match(pol, row)
    assert match == "none"
