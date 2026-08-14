"""`ledger.spend()`, the one derive resolver — **partitioned by AGENT, not by time**.

The contract, in one line: an agent that has a metric ledger resolves from it for ALL of
history; an agent that has none resolves from `calls`; and **no row is counted twice**.

USAGE-ONLY (ADR 0011) retired the time-partitioned cutover this file was written for.
`constants.SPEND_CUTOVER` is gone, and with it the straddling-session case, the boundary
instant, and the `ts`-less-row default — none of which can arise when the partition key
is *whose* a row is rather than *when* it was.

What this file pins now:

1. The partition is by agent, and it is total: every row lands on exactly one side.
2. **The `calls` fallback is scoped, not deleted.** An agent with no metric ledger — the
   library adapter, the proxy, the retired `codex` agent, any `[sources.<name>]` custom
   tool — keeps resolving from `calls` forever. Deleting the loop (the tempting reading
   of "one basis") silently zeroes all of them.
3. **`SPEND_SOURCES` is a spine, not a sum.** Each metric kind deliberately holds several
   overlapping views of the same traffic; summing a kind double-counts. Only the listed
   source per agent may contribute.
4. A spine source must be POINT-IN-TIME, never cumulative — a rule found under the
   cutover that outlived it, because the overlap is between two views of the same
   traffic, which is a property of the stores rather than of the clock.
5. `since` is honored.
"""
from __future__ import annotations

import pytest

from cage import constants, ledger, schema

# Two arbitrary instants, kept only to prove the resolver ignores time entirely.
EARLY = "2026-08-13T23:59:59Z"
LATE = "2026-08-14T00:00:01Z"


# ── 1 · no cutover exists ────────────────────────────────────────────────────

def test_no_spend_cutover_constant_exists():
    """The boundary is gone, not renamed. Reintroducing a time-partitioned basis is an
    ADR 0011 reversal, not a refactor."""
    assert not hasattr(constants, "SPEND_CUTOVER")
    import inspect
    src = inspect.getsource(constants)
    assert "SPEND_CUTOVER = " not in src


# ── 2 · the partition: by agent, total, never doubled ────────────────────────

def _call(root, ts, **kw):
    row = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4",
                           tokens_in=kw.pop("tokens_in", 100),
                           tokens_out=kw.pop("tokens_out", 10),
                           agent=kw.pop("agent", "claude-code"), ts=ts, **kw)
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


def test_a_spined_agent_resolves_from_metrics_at_every_instant(proj):
    """Time is not a factor. Both calls rows are superseded because claude HAS a spine,
    whether they are older or newer than the metric row."""
    _call(proj, EARLY, tokens_in=100)
    _call(proj, LATE, tokens_in=999)
    _claude_metric(proj, EARLY, tokens_in=500)
    rows = ledger.spend(proj)
    assert [r["basis"] for r in rows] == ["metrics"]
    assert [r["tokens_in"] for r in rows] == [500]


def test_an_agent_with_no_spine_resolves_from_calls_at_every_instant(proj):
    """The scoped fallback. `lib` has no metric ledger and never will under this
    design, so its rows are not superseded by anything and must survive."""
    _call(proj, EARLY, agent="lib", tokens_in=100)
    _call(proj, LATE, agent="lib", tokens_in=999)
    rows = ledger.spend(proj)
    assert [r["basis"] for r in rows] == ["calls", "calls"]
    assert sorted(r["tokens_in"] for r in rows) == [100, 999]


def test_the_two_sides_compose_without_overlap(proj):
    """A ledger holding both kinds of agent yields each row exactly once."""
    _call(proj, EARLY, tokens_in=100)                  # claude — superseded
    _call(proj, EARLY, agent="lib", tokens_in=7)       # lib — kept
    _claude_metric(proj, LATE, tokens_in=500)          # claude — the spine
    rows = ledger.spend(proj)
    assert sorted(r["tokens_in"] for r in rows) == [7, 500]
    assert {r["basis"] for r in rows} == {"calls", "metrics"}


def test_no_row_is_ever_counted_twice(proj):
    """Every id appears at most once."""
    for ts in (EARLY, LATE):
        _call(proj, ts, session="s1")
        _claude_metric(proj, ts, session="s1", request=f"r{ts}")
    ids = [r.get("id") for r in ledger.spend(proj)]
    assert len(ids) == len(set(ids))


# ── 3 · SPEND_SOURCES is a spine, never a sum ────────────────────────────────

def test_every_agent_has_a_declared_spine_or_a_stated_absence():
    from cage import agents
    assert set(ledger.SPEND_SOURCES) == set(agents.SURFACES)
    # An agent listed with an EMPTY spine must say why — a bare `()` reads as an
    # oversight, and kiro's used to name a store that does not exist.
    for agent, sources in ledger.SPEND_SOURCES.items():
        if not sources:
            assert ledger.ABSENT_SPINES.get(agent), f"{agent} has no spine and no reason"


def test_a_non_spine_source_never_carries_money(proj):
    """Copilot's five stores describe the SAME requests at three grains. `chat` is the
    spine for vscode; a `sidecar` row covering that same request must be ignored, or a
    machine that opts into the gated store silently doubles its own spend."""
    for source, session in (("chat", "c1"), ("sidecar", "c1")):
        row = schema.make_copilot_metric(source=source, session=session, surface="vscode",
                                         model="gpt-4", tokens_in=100, tokens_out=10,
                                         ts=LATE)
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
        source="cli", session="c1", surface="cli", tokens_in=100, ts=LATE))
    ledger.append_row(proj, "kiro", schema.make_kiro_metric(
        source="cli-conv", session="k1", surface="cli", credits=0.5, ts=LATE))
    assert ledger.spend(proj) == []


def test_the_cli_delta_twin_is_the_copilot_cli_spine(proj):
    """`cli` and `cli-delta` describe the SAME shutdown. Exactly one may carry money."""
    for source in ("cli", "cli-delta"):
        ledger.append_row(proj, "copilot", schema.make_copilot_metric(
            source=source, session="c1", surface="cli", request="s000",
            tokens_in=100, tokens_out=10, ts=LATE))
    rows = ledger.spend(proj)
    assert len(rows) == 1
    assert sum(r["tokens_in"] for r in rows) == 100, "never the sum of the pair"


# ── 4 · a ts-less row is conservative, never dropped ─────────────────────────

def test_a_row_with_no_ts_still_resolves_by_agent(proj):
    """A `ts`-less row used to need a documented default side; with no time partition
    the question does not arise — the row resolves by whose it is, like every other."""
    for agent, kept in (("claude-code", False), ("lib", True)):
        row = schema.make_call(route="chat", provider="anthropic",
                               model="claude-opus-4", agent=agent, tokens_in=7)
        row.pop("ts", None)
        ledger.append_row(proj, "calls", row)
        got = [r for r in ledger.spend(proj) if r.get("agent") == agent]
        assert bool(got) is kept


# ── 5 · the normalized shape never invents a field ───────────────────────────

def test_normalization_is_additive_only(proj):
    """A field the metric kind does not carry stays absent — exactly as it would on a
    legacy call row — and is never synthesized to a zero."""
    _claude_metric(proj, LATE)
    row = ledger.spend(proj)[0]
    assert row["basis"] == "metrics"
    assert "provider" not in row, "claude metric rows carry no provider — do not invent one"
    assert row["route"] == "chat" and row["ok"] is True


def test_since_is_honored_on_both_halves(proj):
    _call(proj, "2026-01-02T00:00:00Z", agent="lib")   # no spine ⇒ kept, but old
    _claude_metric(proj, LATE)
    assert len(ledger.spend(proj)) == 2
    narrow = ledger.spend(proj, since="7d")
    assert all(r["basis"] == "metrics" for r in narrow), (
        "the old calls row should fall outside the window; the metric row is recent")


# ── 6 · an empty ledger is empty, not an error ───────────────────────────────

def test_empty_ledger_resolves_to_nothing(proj):
    assert ledger.spend(proj) == []

