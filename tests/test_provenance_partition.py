"""`provenance.jsonl` becomes `ledger/provenance/provenance-<month>.jsonl` — P3c.

**This reverses an explicit in-code decision.** `paths.shard()` stated outright:
*"`provenance` is intentionally never partitioned (buffer)"* — the reasoning being that
the local file is a buffer whose canonical home is `refs/notes/cage-provenance`. That was
true and insufficient: **nothing prunes the buffer.** `cleanup.NEVER` covers `ledger/` and
no cleanup class touches this file, so the "buffer" grew without bound and every read
scanned all of it. The reversal is recorded in `paths.py`, not deleted.

**What makes this migration different from P3a's** — and why it gets its own file: a
manifest reader that misses rows loses *labels*, visibly. A provenance reader that misses
rows loses **counts**, and `agent%` reads counts rather than re-deriving them (no matcher,
no git at render time). So a shard-spanning bug does not raise, does not warn, and does not
show up as an error — **it shows up as a different percentage.** Every reader is asserted
individually here, because a union that happens to work through one of them proves nothing
about the other three.

The four readers, and the fifth that is easiest to miss:

  1. `ledger.provenance` — the shared one
  2. `originrecord.read_all` / `for_sha`
  3. `chats.py`'s `agent%` column
  4. `doctorbundle` — reads the path **directly** and would under-report in a diagnostic
  5. `notessync` — merges by row id; a partial read re-pushes or silently drops rows in
     `refs/notes/cage-provenance`
"""
from __future__ import annotations

import pytest

from cage import chats, doctorbundle, ledger, notessync, originrecord, paths, policy, schema

JUN = "2026-06-15T00:00:00Z"
JUL = "2026-07-15T00:00:00Z"
AUG = "2026-08-15T00:00:00Z"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    return root


def _row(sha, ts, *, agent="claude", session="s1", agent_lines=0, residual_lines=None):
    extra = {} if residual_lines is None else {"residual_lines": residual_lines}
    return schema.make_provenance(sha=sha, files=["a.py"], agent=agent,
                                  lines_added=10, lines_removed=1, method="transcript",
                                  origin="agent", confidence=0.8, session_id=session,
                                  agent_lines=agent_lines, ts=ts, **extra)


def _sharded(proj, sha, ts, **kw):
    ledger.append_row(proj, "provenance", _row(sha, ts, **kw))


def _legacy(proj, sha, ts, **kw):
    """A row in the pre-P3c unpartitioned file — what every real install already has."""
    ledger.append(paths.Footprint(proj).provenance_legacy, _row(sha, ts, **kw))


# ── the partition itself ────────────────────────────────────────────────────────

def test_a_row_lands_in_the_month_of_its_own_ts(proj):
    """The determinism law. A write-time clock would put a backdated capture in the wrong
    month and make the same input produce different files on different days — and
    authorship capture is *routinely* backdated: it attributes commits, not the present."""
    for ts in (JUN, JUL, AUG):
        _sharded(proj, f"sha{ts[:7]}", ts)
    names = sorted(p.name for p in paths.Footprint(proj).provenance_dir.iterdir())
    assert names == ["provenance-2026-06.jsonl", "provenance-2026-07.jsonl",
                     "provenance-2026-08.jsonl"]


def test_an_unparseable_ts_falls_back_rather_than_being_dropped(proj):
    foot = paths.Footprint(proj)
    assert foot.provenance_shard("").name == "provenance.jsonl"
    assert foot.provenance_shard("not-a-date").name == "provenance.jsonl"


def test_the_directory_mechanism_is_used_not_a_flat_shard(proj):
    """`savings_dir`/`copilot_dir` style — the precedent `paths.py` calls "smallest diff,
    precedent already tested" — so the tree sits under `ledger/provenance/` rather than
    scattering `provenance-*.jsonl` beside `calls-*.jsonl`."""
    foot = paths.Footprint(proj)
    assert foot.provenance_dir == foot.ledger / "provenance"
    assert foot.provenance_shard(AUG).parent == foot.provenance_dir
    assert foot.shard("provenance", AUG) == foot.provenance_shard(AUG)


# ── all five readers span shards ────────────────────────────────────────────────

def test_reader_1_ledger_provenance_unions_both_homes(proj):
    _legacy(proj, "old", JUN)
    _sharded(proj, "new", AUG)
    assert [r["sha"] for r in ledger.provenance(proj)] == ["old", "new"]


def test_reader_2_originrecord_spans_shards(proj):
    _legacy(proj, "old", JUN)
    _sharded(proj, "new", AUG)
    assert len(originrecord.read_all(proj)) == 2
    assert [r["sha"] for r in originrecord.for_sha(proj, "old")] == ["old"]


def test_reader_3_chats_agent_pct_spans_shards(proj):
    """`agent%` **reads** counts and never re-derives them, so a missed shard is not an
    error — it is a wrong percentage. That is the whole reason this reader is listed."""
    from tests.conftest import metric_twin
    call = schema.make_call(route="chat", provider="anthropic", model="m",
                            agent="claude-code", session="s1", tokens_in=10, ts=AUG)
    ledger.append_row(proj, "calls", call)
    metric_twin(proj, call)
    _legacy(proj, "old", JUN, agent_lines=30, residual_lines=10)
    _sharded(proj, "new", AUG, agent_lines=30, residual_lines=30)
    rows = chats.summarize(proj, policy.load(paths.Footprint(proj).policy))["rows"]
    # 60 agent lines of 100 evidenced. Reading only ONE home would give 75% or 50%.
    assert rows[0]["agent_pct"] == pytest.approx(60.0)


def test_reader_4_doctorbundle_counts_every_shard(proj):
    """It reads the path **directly** rather than through `ledger.provenance`, which is
    exactly why it is the easy miss — and under-reporting in a *diagnostic* bundle is the
    worst place to do it, since the bundle's whole job is being trustworthy."""
    _legacy(proj, "old", JUN)
    for ts in (JUL, AUG):
        _sharded(proj, f"s{ts[:7]}", ts)
    foot = paths.Footprint(proj)
    text = doctorbundle._footprint_text(proj, foot.base.parent, "test")
    assert "3 row(s)" in text, text
    assert "provenance ×3" in text, "the bundle must say how many shards it summed"


def test_reader_5_notes_sync_pushes_the_same_row_set(proj, monkeypatch):
    """`notessync` merges by row **id**. A partial read either re-pushes rows the note
    already has or silently drops rows it does not — and `refs/notes/cage-provenance` is
    the CANONICAL store, so a drop there is not recoverable from the buffer forever."""
    _legacy(proj, "old", JUN)
    _sharded(proj, "new", AUG)
    # `plan()` is the pure, read-only merge — the exact row set a push would write.
    planned = notessync.plan(proj)
    assert set(planned) == {"old", "new"}, "a shard was missed before anything was pushed"
    assert [r["sha"] for r in planned["old"]["merged"]] == ["old"]
    assert [r["sha"] for r in planned["new"]["merged"]] == ["new"]
    # A dev machine dry-runs by default and must still SEE both shas — CI is the sole
    # writer (`CAGE_NOTES_WRITE=1`), and this asserts the default stays a dry run.
    monkeypatch.delenv("CAGE_NOTES_WRITE", raising=False)
    res = notessync.sync(proj)
    assert res["wrote"] is False
    assert set(res["shas"]) == {"old", "new"}


# ── the legacy file is untouchable ──────────────────────────────────────────────

def test_the_legacy_file_is_never_written_to_again(proj):
    foot = paths.Footprint(proj)
    _legacy(proj, "old", JUN)
    before = foot.provenance_legacy.read_bytes()
    for ts in (JUL, AUG):
        _sharded(proj, f"s{ts[:7]}", ts)
    assert foot.provenance_legacy.read_bytes() == before


def test_a_frozen_row_is_never_backfilled(proj):
    """`residual_lines`' absent-vs-recorded-`0` distinction is the **version gate** for
    `agent%`: absent means the row predates the count, a recorded `0` means everything
    matchable matched. Rewriting an old row to add the key would destroy that
    distinction — silently, and irreversibly."""
    foot = paths.Footprint(proj)
    ledger.append(foot.provenance_legacy, _row("old", JUN))   # no residual_lines
    _sharded(proj, "new", AUG, agent_lines=5, residual_lines=0)
    rows = {r["sha"]: r for r in ledger.provenance(proj)}
    assert "residual_lines" not in rows["old"]
    assert rows["new"]["residual_lines"] == 0


def test_read_order_is_deterministic_oldest_first(proj):
    for ts in (AUG, JUN, JUL):
        _sharded(proj, f"s{ts[:7]}", ts)
    _legacy(proj, "legacy", JUN)
    order = [r["sha"] for r in ledger.provenance(proj)]
    assert order == ["legacy", "s2026-06", "s2026-07", "s2026-08"]
    assert order == [r["sha"] for r in ledger.provenance(proj)]   # stable across reads


# ── the bounded re-scan the reversal was taken for ──────────────────────────────

def test_since_skips_a_month_entirely_below_the_cutoff(proj):
    """The *point* of the reversal: a bounded re-scan instead of an end-to-end walk of an
    unbounded file."""
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    for when in (now, now - dt.timedelta(days=200)):
        _sharded(proj, f"s{when:%Y%m}", when.strftime("%Y-%m-%dT%H:%M:%SZ"))
    assert len(ledger.provenance(proj)) == 2
    assert len(ledger.provenance(proj, since="30d")) == 1


def test_since_never_skips_the_legacy_file(proj):
    """It carries no month in its name, so `_month_entirely_below` returns False and it is
    always read. That is the safe direction — read too much, never too little — and it
    matters because the legacy file holds the OLDEST rows, which is exactly what a naive
    "no month ⇒ skip" would have thrown away."""
    _legacy(proj, "old", "2020-01-01T00:00:00Z")
    assert [r["sha"] for r in ledger.provenance(proj, since="1d")] == ["old"]


# ── counts-never-content survives the move ──────────────────────────────────────

def test_the_shard_holds_counts_and_never_a_path_body(proj):
    _sharded(proj, "sha1", AUG, agent_lines=7)
    blob = paths.Footprint(proj).provenance_shard(AUG).read_text(encoding="utf-8")
    assert '"agent_lines": 7' in blob or '"agent_lines":7' in blob
    assert "line_hash" not in blob and "content" not in blob
