"""Sortable, prefixed ids for ledger rows (stdlib only, ≤50 lines)."""
from __future__ import annotations

import secrets
import time


def new_id(prefix: str) -> str:
    """A time-sortable id: ``<prefix>_<11 hex of ms><4 hex random>``.

    Lexicographic order tracks creation order (ms is fixed-width through year
    ~5000), so the append-only log stays sortable without a separate sequence.
    """
    ms = int(time.time() * 1000)
    return f"{prefix}_{ms:011x}{secrets.randbelow(0x10000):04x}"
