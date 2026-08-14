"""`ledger/consumer/` — the consumer's own directory, and the dual-write that fills it.

P1 of the ledger restructure. It **reverses** [ADR-CONSUMERS](../docs/adr/0006_consumer.md)'s
*"consumers … are never given a metric ledger"*, and the reversal is recorded there.

Why this file has to exist rather than leaning on a real-ledger check: the P0 cross-check
found **zero** consumer rows in the maintainer's real `~/.cage`
([snapshot](../work/regression/2026-08-14-calls-vs-metric-crosscheck.md)). There is no
production data to regress against, and `record_call` is fail-open by law — break it and
nothing raises, nothing logs, and no existing test notices. Every claim below is therefore
asserted, not observed.

The three that matter, in order of what they cost if wrong:

  1. **No row is counted twice.** The `calls` row is still written; if `spend()` returned
     both halves every consumer's usage would double.
  2. **No historical row is lost.** A pre-P1 `lib` row has no twin and must keep
     resolving. Suppressing by agent name instead of by id would zero it silently.
  3. **A consumer's request path never sees an error**, whatever happens in here.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cage import ledger, metering, paths, schema

TS = "2026-08-10T12:00:00Z"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    return root


# ── the shape ───────────────────────────────────────────────────────────────────

def test_the_directory_is_the_same_mechanism_every_other_producer_uses(proj):
    foot = paths.Footprint(proj)
    assert foot.consumer_dir == foot.ledger / "consumer"
    assert foot.consumer_shard(TS).name == "calls-2026-08.jsonl"
    # Routed through `shard()` like the agent kinds, so `append_row` needs no special case.
    assert foot.shard("consumer", TS) == foot.consumer_shard(TS)


def test_the_shard_name_comes_from_the_row_never_a_clock(proj):
    """The determinism law. A write-time clock would put a backdated row in the wrong
    month and make the same input produce different files on different days."""
    foot = paths.Footprint(proj)
    assert foot.consumer_shard("2026-02-01T00:00:00Z").name == "calls-2026-02.jsonl"
    # An unparseable ts falls back to the legacy unpartitioned name rather than guessing,
    # so a malformed row still lands somewhere readable.
    assert foot.consumer_shard("").name == "calls.jsonl"


def test_the_source_enum_is_closed():
    assert schema.CONSUMER_METRIC_SOURCES == ("call",)
    with pytest.raises(ValueError):
        schema.make_consumer_metric(route="chat", source="chat")


def test_the_kind_carries_no_currency_and_no_credits():
    """ADR 0011: cage measures usage, never cost. The `calls` twin keeps its legacy
    `est_cost_usd` under the append-only law; a kind minted in 2026 does not get one.
    No `credits` either — a credit is a vendor's billing computation and there is no
    vendor behind a library caller, so absent-vs-zero could never mean anything."""
    row = schema.make_consumer_metric(route="chat", provider="p", model="m",
                                      tokens_in=10, tokens_out=1)
    assert not {k for k in row if "usd" in k or "cost" in k or k == "credits"}
    assert not {k for k in schema.CONSUMER_METRIC_FIELDS
                if "usd" in k or "cost" in k or k == "credits"}


def test_counts_are_omit_at_zero_but_a_failure_is_never_omitted():
    """`ok` inverts the house idiom on purpose: the default is True, so omitting at the
    default would silently render a failed call as a success."""
    quiet = schema.make_consumer_metric(route="chat")
    assert "tokens_in" not in quiet and "ok" not in quiet
    assert schema.make_consumer_metric(route="chat", ok=False)["ok"] is False


# ── the dual write ──────────────────────────────────────────────────────────────

def test_record_call_writes_both_rows_and_links_them(proj):
    call_id = metering.record_call(route="chat", provider="anthropic", model="m",
                                   tokens_in=100, tokens_out=10, root=proj)
    assert call_id.startswith("c_")
    calls = ledger.calls(proj)
    twins = ledger.consumer_metrics(proj)
    assert len(calls) == 1 and len(twins) == 1
    assert twins[0]["call"] == call_id           # the link spend() suppresses on
    assert twins[0]["id"].startswith("csm_")
    assert twins[0]["tokens_in"] == 100 and twins[0]["tokens_out"] == 10
    assert twins[0]["ts"] == calls[0]["ts"]      # same event, same timestamp


def test_a_cage_meter_consumer_still_works_end_to_end(proj):
    """The acceptance criterion, exercised through the public API rather than
    `record_call` — `cage.meter` is the only capture path a user writes code for, and
    AlphaForge Anton is a live one."""
    with metering.meter("chat", task="t1", root=proj) as rec:
        rec.usage(provider="anthropic", model="m", tokens_in=50, tokens_out=5)
    twins = ledger.consumer_metrics(proj)
    assert len(twins) == 1
    assert twins[0]["tokens_in"] == 50 and twins[0]["agent"] == "lib"
    assert twins[0]["task"] == "t1"


def test_the_caller_agent_name_is_carried_not_flattened(proj):
    """`lib` is a default, not the only value — a proxy row or a named application may
    stamp its own. Flattening them all to `lib` would erase the distinction ADR-CONSUMERS'
    trigger 3 exists to detect."""
    metering.record_call(route="chat", provider="p", model="m", agent="anton",
                         tokens_in=10, root=proj)
    assert ledger.consumer_metrics(proj)[0]["agent"] == "anton"


# ── the two properties that cost real data if wrong ─────────────────────────────

def test_spend_counts_the_dual_written_call_exactly_once(proj):
    metering.record_call(route="chat", provider="anthropic", model="m",
                         tokens_in=100, tokens_out=10, root=proj)
    rows = ledger.spend(proj)
    assert len(rows) == 1, "the calls row and its twin must not both resolve"
    assert rows[0]["basis"] == "metrics"
    assert sum(r.get("tokens_in", 0) for r in rows) == 100


def test_a_pre_p1_consumer_row_with_no_twin_still_resolves(proj):
    """Property 2. Written directly to `calls`, the way every `lib` row on disk before
    v0.51 was. It has no twin and never will; an agent-name suppression test would drop
    it, and `spend()` would silently under-report a live integration's whole history."""
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="m", agent="lib",
        tokens_in=777, tokens_out=7, ts=TS))
    rows = ledger.spend(proj)
    assert [r["basis"] for r in rows] == ["calls"]
    assert rows[0]["tokens_in"] == 777


def test_history_and_new_traffic_coexist_without_double_counting(proj):
    """Both properties at once — the state every real ledger will be in the moment P1
    ships: old untwinned rows plus new dual-written ones."""
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="m", agent="lib",
        tokens_in=777, tokens_out=7, ts=TS))
    metering.record_call(route="chat", provider="anthropic", model="m",
                         tokens_in=100, tokens_out=10, root=proj)
    rows = ledger.spend(proj)
    assert len(rows) == 2
    assert sum(r.get("tokens_in", 0) for r in rows) == 877
    assert sorted(r["basis"] for r in rows) == ["calls", "metrics"]


def test_a_retired_agents_rows_are_never_touched(proj):
    """Codex — 373 rows in one real ledger. No metric ledger exists or ever will, and P1
    must not migrate, re-home or suppress a single one of them."""
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="openai", model="gpt-5-codex", agent="codex",
        tokens_in=500, tokens_out=50, ts=TS))
    metering.record_call(route="chat", provider="anthropic", model="m",
                         tokens_in=1, root=proj)
    codex = [r for r in ledger.spend(proj) if r.get("agent") == "codex"]
    assert len(codex) == 1 and codex[0]["basis"] == "calls"
    assert not ledger.consumer_metrics(proj)[0].get("agent") == "codex"


def test_join_table_still_resolves_a_receipts_call_id(proj):
    """The `calls` row is kept for exactly this: a receipt is written against a `calls`
    id, and `join_table` is where that id is looked up. Suppressing the row in `spend()`
    must not make it unfindable here, or a linked saving silently leaves its agent."""
    call_id = metering.record_call(route="chat", provider="anthropic", model="m",
                                   tokens_in=100, root=proj)
    assert call_id in {r.get("id") for r in ledger.join_table(proj)}


def test_join_table_still_counts_each_id_once(proj):
    metering.record_call(route="chat", provider="anthropic", model="m",
                         tokens_in=100, root=proj)
    ids = [r.get("id") for r in ledger.join_table(proj)]
    assert len(ids) == len(set(ids))


# ── fail-open, absolutely ───────────────────────────────────────────────────────

def test_a_broken_twin_write_never_reaches_the_caller(proj, monkeypatch):
    """ADR-CONSUMERS makes never-raising-into-a-request an INVARIANT. The twin is new
    code on that path, so it gets the same guarantee: the call row is still written and
    its id still returned."""
    def boom(*a, **k):
        raise RuntimeError("disk on fire")
    monkeypatch.setattr(schema, "make_consumer_metric", boom)
    call_id = metering.record_call(route="chat", provider="anthropic", model="m",
                                   tokens_in=100, root=proj)
    assert call_id.startswith("c_")
    assert len(ledger.calls(proj)) == 1
    assert ledger.consumer_metrics(proj) == []


def test_a_twin_with_no_call_link_suppresses_nothing(proj):
    """The dual-write's other half can fail too. An unlinked twin must not suppress an
    arbitrary row — `consumer_twin_calls` only ever holds ids that were actually claimed."""
    ledger.append_row(proj, "consumer", schema.make_consumer_metric(
        route="chat", provider="p", model="m", tokens_in=5, ts=TS))
    assert ledger.consumer_twin_calls(proj) == set()
    assert len(ledger.spend(proj)) == 1          # the twin itself, and nothing suppressed


def test_reading_an_absent_consumer_tree_is_empty_not_an_error(proj):
    assert ledger.consumer_metrics(proj) == []
    assert ledger.consumer_metrics_raw(proj) == []
    assert ledger.consumer_twin_calls(proj) == set()


def test_rollback_is_deleting_one_call_site(proj):
    """Dual-write is the rollback plan, stated as a test: the `calls` row alone still
    carries the whole fact, so withdrawing this kind loses nothing."""
    metering.record_call(route="chat", provider="anthropic", model="m",
                         tokens_in=100, tokens_out=10, root=proj)
    call = ledger.calls(proj)[0]
    assert call["tokens_in"] == 100 and call["tokens_out"] == 10
    assert call["agent"] == "lib" and call["route"] == "chat"


# ── partitioning ────────────────────────────────────────────────────────────────

def test_rows_land_in_their_own_months_and_read_back_together(proj):
    for ts in ("2026-06-01T00:00:00Z", "2026-07-01T00:00:00Z", "2026-08-01T00:00:00Z"):
        ledger.append_row(proj, "consumer", schema.make_consumer_metric(
            route="chat", provider="p", model="m", tokens_in=1, ts=ts))
    foot = paths.Footprint(proj)
    assert len(foot.consumer_shards()) == 3
    assert len(ledger.consumer_metrics(proj)) == 3


def test_since_skips_a_month_that_is_entirely_below_the_cutoff(proj):
    """`since` is a WINDOW spec (`30d`), never a date — an unparseable value yields no
    cutoff and silently returns everything, so the timestamps here are built relative to
    now rather than hard-coded. A fixed pair would stop exercising the skip the moment
    the calendar moved past it, and would keep passing while covering nothing."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    for when in (now, now - dt.timedelta(days=200)):
        ledger.append_row(proj, "consumer", schema.make_consumer_metric(
            route="chat", provider="p", model="m", tokens_in=1,
            ts=when.strftime("%Y-%m-%dT%H:%M:%SZ")))
    assert len(ledger.consumer_metrics(proj)) == 2
    assert len(ledger.consumer_metrics(proj, since="30d")) == 1


def test_there_is_no_last_write_wins_collapse(proj):
    """Deliberate. The agent kinds collapse because a chat grows and is re-captured; a
    consumer row is a point-in-time fact about one response that is never re-captured, so
    a collapse would guard an event that cannot happen — and the obvious key (`session`)
    would silently keep one call per session."""
    for _ in range(3):
        ledger.append_row(proj, "consumer", schema.make_consumer_metric(
            route="chat", provider="p", model="m", session="s1", tokens_in=10, ts=TS))
    assert len(ledger.consumer_metrics(proj)) == 3
    assert sum(r["tokens_in"] for r in ledger.spend(proj)) == 30
