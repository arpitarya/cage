"""`cage data migrate-savings` (import-ledger plan §3, revised 2026-07-25) — the precision
contract: **NOT WRONG, NOT DUPLICATED**.

Copies historical `tool=="graphify"` receipts into `savings/graphify/` keeping their
original ids, never rewrites `receipts.jsonl`, and relies on `ledger.receipts()` being an
id-deduped union so a row in both stores counts exactly once. Tested here: byte-identical
money views before/after, dup-id-counts-once, idempotent re-apply, reconciliation refusal,
and the append-only guarantee.
"""
from __future__ import annotations

import contextlib
import io
from types import SimpleNamespace

from cage import cli, ledger, migratecmd, schema


def _root(tmp_path, monkeypatch):
    (tmp_path / ".cage").mkdir()
    # Drive ledger resolution through CAGE_BASE (== `Footprint(root).base`) so the CLI and
    # the direct `ledger.*(root)` calls read/write the SAME store; pin capture-on-read off
    # (the determinism-suite switch) so a read never sweeps real agent logs into the test.
    monkeypatch.setenv("CAGE_BASE", str(tmp_path / ".cage"))
    monkeypatch.setenv("CAGE_CAPTURE_ON_READ", "0")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _legacy_graphify(root, *, saved_from, ts):
    """Seed one legacy graphify receipt in receipts.jsonl (the pre-tree world)."""
    row = schema.make_receipt(tool="graphify", raw_alternative=saved_from, actual=0,
                              unit="tokens", method="modeled", confidence=0.6, ts=ts)
    assert ledger.append_row(root, "receipts", row)
    return row


def _receipts_bytes(root):
    """Bytes of every legacy receipts shard (month-partitioned) — the append-only file(s)
    that must be byte-identical after a migration."""
    led = root / ".cage" / "ledger"
    return {p.name: p.read_bytes() for p in sorted(led.glob("receipts*.jsonl"))}


def _run(root, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cli.main([*args])  # CAGE_BASE env drives resolution — no --ledger (which would re-base)
    return buf.getvalue()


def _money_views(root):
    return (_run(root, "insights", "attrib"),
            _run(root, "report"),
            _run(root, "insights", "roi"))


def test_dry_run_writes_nothing_and_reports_what_would_copy(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    _legacy_graphify(root, saved_from=2000, ts="2026-06-11T00:00:00Z")
    before_savings = ledger.savings(root)
    p, text = migratecmd.run_cli(root, do_apply=False)
    assert p["to_copy_count"] == 2 and p["to_copy_saved"] == 42000
    assert p["legacy_count"] == 2 and p["tree_count"] == 0
    assert "dry run" in text and "would copy" in text
    # dry-run mutated nothing
    assert ledger.savings(root) == before_savings
    assert not (root / ".cage" / "ledger" / "savings").exists()


def test_apply_copies_into_tree_keeps_ids_and_shards_by_ts(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    r1 = _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    r2 = _legacy_graphify(root, saved_from=2000, ts="2026-06-11T00:00:00Z")
    p = migratecmd.apply(root)
    assert p["copied"] == 2
    tree = ledger.savings(root)
    tree_ids = {r["id"] for r in tree}
    assert tree_ids == {r1["id"], r2["id"]}  # original ids kept
    # sharded by the row's own ts (own month)
    foot_savings = root / ".cage" / "ledger" / "savings" / "graphify"
    names = sorted(p.name for p in foot_savings.glob("*.jsonl"))
    assert names == ["savings-2026-05.jsonl", "savings-2026-06.jsonl"]


def test_receipts_jsonl_byte_identical_after_apply(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    _legacy_graphify(root, saved_from=2000, ts="2026-06-11T00:00:00Z")
    before = _receipts_bytes(root)
    migratecmd.apply(root)
    assert _receipts_bytes(root) == before  # never rewritten (append-only)


def test_money_views_byte_identical_before_and_after(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    _legacy_graphify(root, saved_from=2000, ts="2026-06-11T00:00:00Z")
    before = _money_views(root)
    migratecmd.apply(root)
    after = _money_views(root)
    assert after == before  # the migration changed no reported number


def test_duplicate_id_in_both_stores_counts_once(tmp_path, monkeypatch):
    # The union at the read side (tree wins) makes a row present in both stores count once.
    root = _root(tmp_path, monkeypatch)
    r = _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    migratecmd.apply(root)  # r is now in BOTH receipts.jsonl and savings/graphify/
    receipts = ledger.receipts(root)
    assert [x["id"] for x in receipts].count(r["id"]) == 1  # deduped
    assert sum(x.get("saved", 0) for x in receipts) == 40000  # not doubled


def test_second_apply_copies_zero_idempotent(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    assert migratecmd.apply(root)["copied"] == 1
    tree_after_first = sorted(r["id"] for r in ledger.savings(root))
    assert migratecmd.apply(root)["copied"] == 0  # nothing left to copy
    assert sorted(r["id"] for r in ledger.savings(root)) == tree_after_first  # unchanged


def test_half_completed_migration_reads_correct_totals(tmp_path, monkeypatch):
    # Simulate a crash mid-copy: only one of two legacy rows made it into the tree.
    root = _root(tmp_path, monkeypatch)
    r1 = _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    _legacy_graphify(root, saved_from=2000, ts="2026-06-11T00:00:00Z")
    # copy only r1 into the tree by hand (partial state)
    assert ledger.append_row(root, ("savings", "graphify"), dict(r1))
    receipts = ledger.receipts(root)
    # both rows read exactly once; nothing doubled by the partial copy
    assert [x["id"] for x in receipts].count(r1["id"]) == 1
    assert sum(x.get("saved", 0) for x in receipts) == 42000
    # a resuming --apply copies only the missing one
    assert migratecmd.apply(root)["copied"] == 1


def test_apply_refuses_on_reconciliation_conflict(tmp_path, monkeypatch):
    # A tree row with the SAME id but a DIFFERENT saved value = the stores disagree.
    from cage.errors import CageError
    import pytest
    root = _root(tmp_path, monkeypatch)
    r = _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    corrupt = {**r, "saved": 99999.0}  # same id, different money
    assert ledger.append_row(root, ("savings", "graphify"), corrupt)
    with pytest.raises(CageError, match="different `saved`"):
        migratecmd.apply(root)
    # refusal copied nothing new (the corrupt row is the only tree row)
    assert len(ledger.savings(root)) == 1


def test_cli_dry_run_and_apply_smoke(tmp_path, monkeypatch):
    root = _root(tmp_path, monkeypatch)
    _legacy_graphify(root, saved_from=40000, ts="2026-05-10T00:00:00Z")
    out = _run(root, "data", "migrate-savings")
    assert "dry run" in out and "would copy" in out
    assert ledger.savings(root) == []  # dry-run wrote nothing
    out2 = _run(root, "data", "migrate-savings", "--apply")
    assert "copied 1" in out2
    assert len(ledger.savings(root)) == 1
