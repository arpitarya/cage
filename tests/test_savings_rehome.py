"""Savings lift from `ledger/savings/<tool>/` to `ledger/<tool>/` — P4.

Every producer now owns exactly one directory under `ledger/`. Savings tools were the one
kind living a level deeper than everything else, and **all four moved together** (10.6):
graphify, fux, compress, responsecache. A graphify-only move would have left one row kind
in two shapes permanently — the inconsistency this program exists to remove.

Two things make this phase riskier than its diff:

  * **A savings row is unrecoverable.** Nothing reconstructs it, unlike a cursor or a
    debug-log row, which is why `test_cleanup.py` pins its survival at `days=0`. The move
    stays **inside `ledger/`**, so `cleanup.NEVER`'s umbrella still covers it — but that is
    a property to assert, not to assume.
  * **`ledger/` is now a flat namespace shared by agents, consumers and tools** (10.5). A
    tool named `claude` would land two row kinds in one directory, and every reader of
    either would silently see the other's rows. `paths.reserve_tool_name` refuses at
    **write time** with a named error rather than renaming, suffixing, or hoping.
"""
from __future__ import annotations

import pytest

from cage import ledger, paths, savings, schema

JUL = "2026-07-15T00:00:00Z"
AUG = "2026-08-15T00:00:00Z"


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    monkeypatch.delenv("CAGE_LEDGER", raising=False)
    return root


def _legacy(proj, tool, ts, saved=100.0):
    """A row in the pre-P4 tree — what every real install already has."""
    sh = paths.Footprint(proj).savings_dir / tool / f"savings-{ts[:7]}.jsonl"
    sh.parent.mkdir(parents=True, exist_ok=True)
    ledger.append(sh, schema.make_savings(tool=tool, raw_alternative=saved + 10,
                                          actual=10.0, ts=ts))


# ── the new shape ───────────────────────────────────────────────────────────────

def test_a_new_row_lands_one_level_up(proj):
    savings.record(proj, tool="graphify", raw_alternative=500, actual=100, ts=JUL)
    foot = paths.Footprint(proj)
    assert (foot.ledger / "graphify" / "savings-2026-07.jsonl").exists()
    assert not (foot.savings_dir / "graphify").exists()


def test_every_savings_source_moved_not_just_graphify(proj):
    """10.6. One row kind must not live in two shapes permanently."""
    for tool in paths.SAVINGS_TOOLS:
        savings.record(proj, tool=tool, raw_alternative=100, actual=10, ts=JUL)
    foot = paths.Footprint(proj)
    for tool in paths.SAVINGS_TOOLS:
        assert (foot.ledger / tool / "savings-2026-07.jsonl").exists(), tool
    assert {r["tool"] for r in ledger.savings(proj)} == set(paths.SAVINGS_TOOLS)


def test_the_shard_name_still_comes_from_the_row(proj):
    foot = paths.Footprint(proj)
    assert foot.savings_shard("graphify", JUL).name == "savings-2026-07.jsonl"
    assert foot.savings_shard("graphify", "").name == "savings.jsonl"
    assert foot.tool_dir("graphify") == foot.ledger / "graphify"


# ── both trees, forever ─────────────────────────────────────────────────────────

def test_the_legacy_tree_is_still_read(proj):
    """A savings row is unrecoverable. A one-way move would delete measured evidence."""
    _legacy(proj, "graphify", JUL, saved=42.0)
    rows = ledger.savings(proj)
    assert len(rows) == 1 and rows[0]["saved"] == 42.0


def test_both_trees_union_and_nothing_is_double_counted(proj):
    _legacy(proj, "graphify", JUL, saved=42.0)
    savings.record(proj, tool="graphify", raw_alternative=110, actual=10, ts=AUG)
    rows = ledger.savings(proj)
    assert len(rows) == 2
    assert sorted(r["saved"] for r in rows) == [42.0, 100.0]
    assert len({r["id"] for r in rows}) == 2


def test_the_legacy_tree_is_never_written_to_again(proj):
    _legacy(proj, "graphify", JUL)
    sh = paths.Footprint(proj).savings_dir / "graphify" / "savings-2026-07.jsonl"
    before = sh.read_bytes()
    for _ in range(3):
        savings.record(proj, tool="graphify", raw_alternative=100, actual=10, ts=AUG)
    assert sh.read_bytes() == before


def test_read_order_is_deterministic(proj):
    _legacy(proj, "graphify", JUL)
    savings.record(proj, tool="graphify", raw_alternative=100, actual=10, ts=AUG)
    assert [r["id"] for r in ledger.savings(proj)] == [r["id"] for r in ledger.savings(proj)]


# ── 10.5 · the reserved namespace ───────────────────────────────────────────────

@pytest.mark.parametrize("name", ["claude", "copilot", "kiro", "consumer", "provenance",
                                  "savings", "calls", "credits", "receipts", "tasks"])
def test_a_tool_may_not_take_a_reserved_directory_name(name):
    """Refused with a **named error**, never renamed or suffixed. A collision is a design
    mistake in whatever declared the name; a write path that quietly disambiguated would
    bury it, and the rows would land somewhere plausible-looking forever."""
    with pytest.raises(ValueError, match="reserved ledger directory"):
        paths.reserve_tool_name(name)


def test_a_reserved_name_cannot_reach_disk_through_the_writer(proj):
    """The guard is at WRITE time, and `savings.record` is fail-open — so a refused name
    returns `""` and writes nothing, rather than raising into the tool being metered.
    A bad *name* must not break the *tool*."""
    assert savings.record(proj, tool="claude", raw_alternative=100, actual=10,
                          ts=JUL) == ""
    assert not (paths.Footprint(proj).ledger / "claude").exists()


def test_an_ordinary_tool_name_passes_through(proj):
    assert paths.reserve_tool_name("graphify") == "graphify"
    assert paths.reserve_tool_name("some-third-party_tool") == "some-third-party_tool"


def test_a_reserved_dir_is_never_read_as_savings(proj):
    """The read filter and the write guard share ONE table, so they cannot disagree about
    what a tool directory is. Here: a per-agent dir that happens to hold a file matching
    the savings glob must not be mistaken for a tool's."""
    foot = paths.Footprint(proj)
    (foot.ledger / "claude").mkdir(parents=True, exist_ok=True)
    (foot.ledger / "claude" / "savings-2026-07.jsonl").write_text(
        '{"id":"s_bogus","tool":"graphify","saved":9999.0}\n', encoding="utf-8")
    assert ledger.savings(proj) == []


def test_an_unknown_third_party_tool_is_read_back(proj):
    """**The bug the first implementation had.** Enumerating known tool names made any
    third-party tool's rows write-only — on disk, returned by no view, nothing failing.
    fux's zero-dep shim is a real instance of exactly this caller."""
    assert savings.record(proj, tool="somenewtool", raw_alternative=100, actual=10,
                          ts=JUL)
    rows = ledger.savings(proj)
    assert [r["tool"] for r in rows] == ["somenewtool"]


# ── the views must not move ─────────────────────────────────────────────────────

def test_receipts_still_unions_the_tree_with_legacy_receipts(proj):
    ledger.append_row(proj, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=100, actual=20, ts="2026-06-01T00:00:00Z"))
    savings.record(proj, tool="graphify", raw_alternative=500, actual=100, ts=JUL)
    assert len(ledger.receipts(proj)) == 2


def test_insights_graphify_renders_the_same_values_from_either_tree(proj, tmp_path,
                                                                   monkeypatch):
    """`graphifychat` joins `ledger.savings(tool="graphify")` by `session` alone, and that
    join is untouched — so the same rows in either tree must produce the same view."""
    from cage import graphifychat, policy
    pol = policy.load(paths.Footprint(proj).policy)

    _legacy(proj, "graphify", JUL, saved=90.0)
    before = graphifychat.summarize(proj, pol)

    other = tmp_path / "other"
    (other / ".cage").mkdir(parents=True)
    monkeypatch.setenv("CAGE_BASE", str(other / ".cage"))
    savings.record(other, tool="graphify", raw_alternative=100, actual=10, ts=JUL)
    after = graphifychat.summarize(other, pol)

    def cells(d):
        return [{k: r.get(k) for k in ("session", "saved", "tokens", "without")}
                for r in d["rows"]]
    assert cells(before) == cells(after)
