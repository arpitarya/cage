"""The dedicated savings tree (`savings/<tool>/savings-<month>.jsonl`, ADR-LAWS):
writer, per-source partition, the read union with legacy receipts, tool-token PII
safety, and the cleanup-never-touches-it invariant.
"""
from __future__ import annotations

import pytest

from cage import ledger, paths, savings, schema


def _root(tmp_path):
    (tmp_path / ".cage").mkdir()
    return tmp_path


def test_make_savings_derives_saved_and_omits_optionals():
    row = schema.make_savings(tool="graphify", raw_alternative=1000, actual=200,
                              op="explain", source_files=3)
    assert row["saved"] == 800                       # derived — can never disagree
    assert row["tool"] == "graphify" and row["op"] == "explain" and row["source_files"] == 3
    assert "import_id" not in row and "route_key" not in row  # additive, omitted when unset


def test_make_savings_rejects_unsafe_tool_name():
    for bad in ("../etc", "a/b", "Graphify", "", "tool name"):
        with pytest.raises(ValueError):
            schema.make_savings(tool=bad, raw_alternative=1, actual=0)


def test_record_explicitly_accepts_every_make_savings_keyword():
    """G-SAV: `record()`'s `**_ignore` (a fail-open shim-boundary catch-all) let a
    real keyword — `ts` — go silently missing instead of failing loudly. Guard the
    class of bug: every keyword `make_savings` accepts, other than `route_key`
    (which `record()` derives itself via `paths.routing_key`), must appear
    explicitly in `record()`'s own signature."""
    import inspect
    make_params = set(inspect.signature(schema.make_savings).parameters)
    record_params = set(inspect.signature(savings.record).parameters)
    assert (make_params - {"route_key"}) <= record_params


def test_record_writes_into_the_per_source_month_shard(tmp_path):
    root = _root(tmp_path)
    rid = savings.record(root, tool="graphify", raw_alternative=500, actual=100,
                         op="query", ts="2026-07-15T10:00:00Z", source_files=2)
    assert rid
    shard = paths.Footprint(root).savings_shard("graphify", "2026-07-15T10:00:00Z")
    assert shard.exists() and shard.name == "savings-2026-07.jsonl"
    assert shard.parent.name == "graphify"


def test_savings_reader_globs_the_whole_tree(tmp_path):
    root = _root(tmp_path)
    savings.record(root, tool="graphify", raw_alternative=500, actual=100,
                   ts="2026-07-01T00:00:00Z")
    savings.record(root, tool="graphify", raw_alternative=300, actual=50,
                   ts="2026-08-01T00:00:00Z")            # a second month → second shard
    savings.record(root, tool="compressor", raw_alternative=90, actual=10,
                   ts="2026-08-01T00:00:00Z")            # a sibling tool dir
    rows = ledger.savings(root)
    assert len(rows) == 3
    assert {r["tool"] for r in rows} == {"graphify", "compressor"}


def test_receipts_unions_tree_with_legacy_receipts(tmp_path):
    root = _root(tmp_path)
    # a legacy receipt in receipts.jsonl (old graphify rows live there)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=100, actual=20, ts="2026-06-01T00:00:00Z"))
    # a new one in the tree
    savings.record(root, tool="graphify", raw_alternative=500, actual=100,
                   ts="2026-07-01T00:00:00Z")
    union = ledger.receipts(root)
    assert len(union) == 2                                # both stores, no double count
    assert sum(r["saved"] for r in union) == 80 + 400


def test_cleanup_never_touches_the_savings_tree(tmp_path):
    # savings/ is ledger data (under ledger/), not state/ — the cleanup allowlist is
    # state-only by construction, so a saving can never be pruned. days=0 is the
    # maximally aggressive window: survival must come from `scan` never looking at
    # ledger/ at all, not from the row happening to be fresh.
    from cage import cleanup, policy
    root = _root(tmp_path)
    savings.record(root, tool="graphify", raw_alternative=500, actual=100,
                   ts="2026-07-01T00:00:00Z")
    before = ledger.savings(root)
    cleanup.prune(root, policy.load(None), days=0)
    assert ledger.savings(root) == before                # untouched

# ── the savings tree's derived reader changed (SURFACE-CUT, 2026-08-14) ───────
# `test_savings_surface_through_attribution` proved a savings-tree row is
# receipt-compatible by reading it back through `cage insights attrib`. That command is
# deleted. **`savings.py` itself is untouched and still load-bearing** — its surviving
# readers are `graphifychat` (→ `cage insights graphify`), `graphifymeter` and
# `graphifytx`, all of which read the same rows through `ledger.savings`. Every other
# test in this file (the union, the dedup, the cleanup guard) is unchanged.
