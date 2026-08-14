"""Kiro's credits move into `ledger/kiro/` — P2 of the ledger restructure.

`credits-<month>.jsonl` was a **duplicate**: `ledger/kiro/`'s `cli-conv` rows already
carried these credits, from the same store, through the same shared reader, under the same
whitelist. P2 stops writing the top-level shard and makes `ledger.credits` read `cli-conv`
— re-applying the credits skip rule on the way — **and every existing shard, forever**.

The parity baseline is measured, not assumed:
[the P0 cross-check](../work/regression/2026-08-14-calls-vs-metric-crosscheck.md) found
3 credits rows / 3 `cli-conv` rows on a real store, same sessions, **identical**
`credits`/`context_pct`/`turns`, and a **zero** skip-rule delta across all 20
conversations. What that measurement cannot do is prove the rule still applies — n=20 on
one machine happens to contain no case where the two rules disagree. So the disagreeing
case is constructed here.

What must not change, and is asserted below:

  * the values `cage insights chats` renders (its only consumer, CHATS-CREDITS)
  * the credits **skip rule** — laxer `cli-conv` emission must not leak new rows through
  * `method="measured"` and `unit="credits"` — never priced, never a token
  * legacy shards keep reading, forever, and are never rewritten
"""
from __future__ import annotations

import json

import pytest

from cage import chats, ledger, paths, schema

TS = "2026-08-10T12:00:00Z"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    return root


def _conv(proj, session, *, credits=0.5, turns=2, context=1.5, ts=TS, model="auto"):
    """A `cli-conv` metric row — the live credits home."""
    row = schema.make_kiro_metric(source="cli-conv", session=session, surface="cli",
                                  model=model, credits=credits, context_pct=context,
                                  turns=turns, ts=ts, project="p")
    ledger.append_row(proj, "kiro", row)
    return row


def _legacy(proj, session, *, credits=0.5, turns=2, context=1.5, ts=TS):
    """A row in the retired top-level shard — what every real install already has."""
    row = schema.make_credit(session=session, agent="kiro", model="auto", surface="cli",
                             credits=credits, turns=turns, context_pct=context, ts=ts,
                             project="p")
    ledger.append_row(proj, "credits", row)
    return row


# ── the new home reads as credits ───────────────────────────────────────────────

def test_a_cli_conv_row_reads_as_a_credits_row(proj):
    _conv(proj, "s1", credits=0.25, turns=3, context=4.0)
    rows = ledger.credits(proj)
    assert len(rows) == 1
    r = rows[0]
    assert r["session"] == "s1" and r["agent"] == "kiro" and r["surface"] == "cli"
    assert r["credits"] == 0.25 and r["turns"] == 3 and r["context_pct"] == 4.0
    assert r["unit"] == "credits" and r["method"] == "measured"
    assert r["project"] == "p"


def test_the_projection_never_prices_and_never_becomes_a_token(proj):
    """ADR 0011 and the never-sum-across-units law, at the point the two kinds meet."""
    _conv(proj, "s1", credits=0.25)
    r = ledger.credits(proj)[0]
    assert not {k for k in r if "usd" in k or "cost" in k or "price" in k}
    assert "tokens_in" not in r and "tokens_out" not in r
    # …and it stays out of the token spine (10.3): a credits row in `spend()` would carry
    # credits with zero tokens, the exact lie `make_credit` exists to prevent.
    assert ledger.spend(proj) == []


def test_the_retired_shard_is_no_longer_written_by_an_import(proj):
    """Asserted at the reader, not by grepping the writer: `_ingest_credits` keeps its
    name and its return value, and the thing that must be true is that no credits row
    lands in the top-level shard."""
    _conv(proj, "s1")
    assert ledger.read_kind(proj, "credits") == []
    assert len(ledger.credits(proj)) == 1


# ── the skip rule, which the real store could not exercise ──────────────────────

def test_the_credits_skip_rule_survives_the_move(proj):
    """**The case the real store does not contain.** `cli-conv` emits whenever the store
    carried a `usage_info` list — *including one summing to a real 0.0* — because a
    store-verbatim kind records what the store said. A credits row has always required an
    actual usage signal. Without re-applying the rule, a conversation with no credits and
    no context would appear as a brand-new 0-credit chat row that never existed before."""
    _conv(proj, "silent", credits=0.0, context=0.0, turns=5)
    assert ledger.kiro_metrics(proj), "the cli-conv row itself is still recorded"
    assert ledger.credits(proj) == [], "…but it is not a credits row"


def test_a_context_only_conversation_still_counts(proj):
    """The rule is `credits <= 0 AND context <= 0` — either signal alone is enough. An
    `or` here would silently drop every conversation that burned context without billing."""
    _conv(proj, "ctx", credits=0.0, context=2.5)
    assert [r["session"] for r in ledger.credits(proj)] == ["ctx"]


def test_a_none_credit_is_no_signal_not_a_zero(proj):
    """`cli-conv` carries a None sentinel (no `usage_info` at all) that a credits row has
    no way to express. It must read as *no signal* for the skip test — and must never be
    rendered as a recorded 0.0, which is a different billing fact."""
    _conv(proj, "none", credits=None, context=0.0)
    assert ledger.credits(proj) == []
    _conv(proj, "none2", credits=None, context=3.0)
    assert [r["session"] for r in ledger.credits(proj)] == ["none2"]
    assert ledger.credits(proj)[0]["credits"] == 0.0


# ── both homes, forever ─────────────────────────────────────────────────────────

def test_legacy_shards_are_still_read(proj):
    """Every real install has rows here — 17 in the maintainer's own ledger. A one-way
    move would make a live agent's whole credit history vanish."""
    _legacy(proj, "old", credits=0.9)
    assert [r["session"] for r in ledger.credits(proj)] == ["old"]
    assert ledger.credits(proj)[0]["credits"] == 0.9


def test_a_legacy_row_keeps_its_own_recorded_method(proj):
    """Pre-USAGE-ONLY rows carry `method="estimated"`. They are history and are never
    rewritten or re-tagged — the retag applied forward, to new rows only."""
    row = schema.make_credit(session="old", credits=0.5, method="estimated", ts=TS)
    ledger.append_row(proj, "credits", row)
    assert ledger.credits(proj)[0]["method"] == "estimated"


def test_the_two_homes_union_without_double_counting(proj):
    """A session captured under both homes describes ONE conversation. Summing them would
    double its credits; the per-session collapse is what makes the union safe."""
    _legacy(proj, "s1", credits=0.5, turns=2)
    _conv(proj, "s1", credits=0.9, turns=4)
    rows = ledger.credits(proj)
    assert len(rows) == 1
    assert rows[0]["credits"] == 0.9, "the higher turn count wins, as it always did"


def test_the_higher_turn_count_wins_regardless_of_home(proj):
    """The collapse is by growth, not by which shard a row happens to sit in. A legacy row
    capturing a LATER state than the new one must still win."""
    _legacy(proj, "s1", credits=0.9, turns=7)
    _conv(proj, "s1", credits=0.1, turns=2)
    assert ledger.credits(proj)[0]["credits"] == 0.9


def test_a_tie_prefers_the_live_writer_by_intent_not_by_ascii(proj):
    """Before P2 the score was `(turns, id)`, so a tie between a `k_cred…` legacy row and
    a `km_…` projected one would have been decided by where `_` and `m` sit in ASCII. The
    score names the live source explicitly instead."""
    _legacy(proj, "s1", credits=0.5, turns=3)
    _conv(proj, "s1", credits=0.7, turns=3)
    assert ledger.credits(proj)[0]["credits"] == 0.7


def test_legacy_only_collapse_is_unchanged(proj):
    """The added score term must be a no-op when only legacy rows exist, or P2 would have
    quietly changed what every pre-v0.51 ledger reports."""
    for turns, cr in ((1, 0.1), (5, 0.5), (3, 0.3)):
        _legacy(proj, "s1", credits=cr, turns=turns)
    assert ledger.credits(proj)[0]["credits"] == 0.5


# ── the only consumer ───────────────────────────────────────────────────────────

def test_chats_renders_the_same_values_from_either_home(proj, tmp_path, monkeypatch):
    """CHATS-CREDITS is `ledger.credits`' only reader. The move must be invisible to it —
    same row, same bucket, same number, whichever shard the row came from."""
    from cage import policy
    pol = policy.load(paths.Footprint(proj).policy)

    _legacy(proj, "s1", credits=0.42, turns=2)
    before = chats.summarize(proj, pol)

    other = tmp_path / "other"
    (other / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(other / ".cage"))
    _conv(other, "s1", credits=0.42, turns=2)
    after = chats.summarize(other, pol)

    def cells(d):
        return [{k: r.get(k) for k in ("agent", "surface", "session", "credits",
                                       "calls", "tokens_in", "tokens_out")}
                for r in d["rows"]]
    assert cells(before) == cells(after)
    assert json.dumps(cells(after))  # a real row, not two empty lists agreeing


def test_a_credits_chat_never_gains_token_cells(proj):
    """The bucket discriminator. A credits row must never fold into a call chat's token
    sums — that is what keeps a credit and a token from ever being added."""
    from cage import policy
    _conv(proj, "s1", credits=0.42)
    rows = chats.summarize(proj, policy.load(paths.Footprint(proj).policy))["rows"]
    assert len(rows) == 1
    assert rows[0]["credits"] == 0.42
    assert rows[0]["tokens_in"] == 0 and rows[0]["calls"] == 0
