"""Tier-0 savings emitters.

The §8 ledger features this file also covered — `quality`, `regression`, `recommend`,
`forecast` — were all cost views and went with the money subsystem (USAGE-ONLY,
ADR 0011). What survives here is the savings *emitters*, which are token-denominated
and were never priced at this layer.
"""
from __future__ import annotations

import json

from cage import compress, responsecache


def test_compress_shrinks_and_makes_receipt():
    blob = json.dumps({"rows": [{"x": i, "note": "y" * 400} for i in range(100)]})
    out, raw, act = compress.compress(blob)
    assert act < raw                                   # genuinely smaller
    r = compress.receipt(blob, task="t")
    assert r["tool"] == "compressor" and r["saved"] == raw - act


def test_response_cache_hit_eliminates_call(proj):
    responsecache.store(proj, "what is 2+2", "4", call_tokens=5000)
    assert responsecache.lookup(proj, "what is 2+2")["value"] == "4"
    assert responsecache.lookup(proj, "different") is None
    r = responsecache.hit_receipt(5000, task="t")
    assert r["actual"] == 0 and r["saved"] == 5000 and r["tool"] == "response-cache"
