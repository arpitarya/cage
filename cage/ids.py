"""Sortable, prefixed ids for ledger rows (stdlib only, ≤50 lines)."""
from __future__ import annotations

import secrets
import time


def new_id(prefix: str) -> str:
    """A time-sortable id: ``<prefix>_<11 hex of ms><8 hex random>``.

    Lexicographic order tracks creation order (ms is fixed-width through year
    ~5000), so the append-only log stays sortable without a separate sequence.

    **The random field is 32 bits, and the width is a correctness property.** The
    millisecond prefix is shared by every row minted in that millisecond, so the random
    field is the only thing separating them — and every merge path (`ledger.append_new`,
    `mergeutil.union_by_id`, `ledger.receipts`) treats an id as
    an *identity*, which turns a collision into a **silently dropped row** rather than a
    retry. At the original 16 bits that was measured at ~1 in 229 over 200k sequential
    ids and turned main red once (in the since-removed fleet-study suite, 37 calls
    where 38 were seeded):
    `work/regression/2026-08-02-finding-call-id-collisions.md`.

    A per-process counter is strictly stronger *within* a process and useless across
    them — two agents metering at once is the normal case here — so the width is the
    right single lever. Ids already written are never rewritten and keep their old
    16-bit risk; the two shapes coexist because **nothing parses an id**.
    """
    ms = int(time.time() * 1000)
    return f"{prefix}_{ms:011x}{secrets.randbelow(0x100000000):08x}"
