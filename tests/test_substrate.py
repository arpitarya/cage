"""Substrate contract: ids, schema, ledger, policy.

The `prices` section went with the money subsystem (USAGE-ONLY, ADR 0011).
"""
from __future__ import annotations

import time

import pytest

from cage import ids, ledger, paths, policy, schema


def test_ids_are_sortable_by_time():
    a = ids.new_id("c")
    time.sleep(0.002)
    b = ids.new_id("c")
    assert a.startswith("c_") and b.startswith("c_")
    assert a < b  # later id sorts after earlier one


# ── id entropy is a CONTRACT, not a statistic ─────────────────────────────────
#
# The random field is the only thing separating two rows minted in the same
# millisecond, and every merge path (`ledger.append_new` · `mergeutil.union_by_id` ·
# `ledger.receipts` · `study.import_bundles`) treats an id as an identity — so a
# collision is a **silently dropped row**, not a retry. At 16 bits it was measured at
# ~1 in 229 over 200k sequential ids and turned main red once (`test_study`, 37 vs 38):
# work/regression/2026-08-02-finding-call-id-collisions.md.
#
# Asserted as a contract rather than by generating ids and counting duplicates: a
# statistical test for a 1-in-4-billion event is either vacuous or flaky, and neither
# tells you the field got narrower.

def test_the_random_field_consumes_the_full_32_bit_space(monkeypatch):
    seen = []
    real = ids.secrets.randbelow
    monkeypatch.setattr(ids.secrets, "randbelow",
                        lambda n: seen.append(n) or real(n))
    ids.new_id("c")
    assert seen == [0x100000000], "the random field must span 32 bits, not fewer"


def test_id_shape_is_fixed_width_so_lexicographic_order_tracks_time():
    """11 hex of ms + 8 hex of randomness. The ms field is untouched by the widening —
    that is what keeps the append-only log sortable without a separate sequence."""
    i = ids.new_id("c")
    prefix, _, body = i.partition("_")
    assert prefix == "c" and len(body) == 19       # 11 (ms) + 8 (random)
    assert int(body, 16) >= 0                      # all hex, no separator inside
    assert len({len(ids.new_id("r")) for _ in range(50)}) == 1   # never varies


def test_a_narrower_legacy_id_still_reads_and_is_never_rewritten(tmp_path):
    """Old and new ids coexist because **nothing parses one** — they are opaque
    strings. A row already written keeps its 16-bit id and its 16-bit risk forever;
    that is the reason to widen now rather than later, not an argument to backfill."""
    old = "c_0197c6a1b2c0000"          # a pre-widening id: 15-char body, not 19
    row = schema.make_call(route="chat", provider="anthropic", model="m",
                           tokens_in=1, tokens_out=1, call_id=old)
    assert row["id"] == old
    assert ledger.append(paths.Footprint(tmp_path).calls, row)
    assert [r["id"] for r in ledger.calls(tmp_path)] == [old]


def test_make_receipt_derives_saved():
    r = schema.make_receipt(tool="fux", raw_alternative=8000, actual=1600)
    assert r["saved"] == 6400
    assert r["id"].startswith("r_")


def test_make_receipt_rejects_bad_enums():
    with pytest.raises(ValueError):
        schema.make_receipt(tool="x", raw_alternative=1, actual=0, unit="bananas")
    with pytest.raises(ValueError):
        schema.make_receipt(tool="x", raw_alternative=1, actual=0, method="vibes")


def test_ledger_append_read_roundtrip(proj):
    fp = paths.Footprint(proj)
    assert ledger.append(fp.calls, {"id": "c_1", "ts": "2026-06-14T00:00:00Z"})
    assert ledger.append(fp.calls, {"id": "c_2", "ts": "2026-06-14T00:00:01Z"})
    rows = ledger.calls(proj)
    assert [r["id"] for r in rows] == ["c_1", "c_2"]


def test_ledger_tolerates_truncated_tail(proj):
    fp = paths.Footprint(proj)
    ledger.append(fp.calls, {"id": "c_1"})
    with fp.calls.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "c_2", "ts": ')  # crash mid-append
    assert [r["id"] for r in ledger.calls(proj)] == ["c_1"]


def test_since_window_filters_old_rows():
    rows = [{"ts": "2000-01-01T00:00:00Z"}, {"ts": "2099-01-01T00:00:00Z"}]
    kept = ledger.since(rows, "7d")
    assert kept == [{"ts": "2099-01-01T00:00:00Z"}]
    assert ledger.since(rows, None) == rows  # no window = passthrough


def test_policy_project_overrides_bundled(proj):
    fp = paths.Footprint(proj)
    fp.base.mkdir(parents=True)
    fp.policy.write_text('[budgets]\nsession_usd = 9.5\n', encoding="utf-8")
    pol = policy.load(fp.policy)
    assert policy.budgets(pol)["session_usd"] == 9.5
    # A project value shadows the bundled default while un-shadowed bundled sections
    # stay live — the merge contract, now over one file (USAGE-ONLY, ADR 0011).
    assert policy.tool_order(pol) == policy.tool_order(policy.load(None))
