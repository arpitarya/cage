"""Tier-0 exact-match response cache → eliminated-call receipts (plan §4.5, §6).

A cache hit eliminates a call entirely: `actual: 0`, the full alternative cost
saved, `method: measured` — Cage's "4′33″" case, the highest-value receipt there
is. Keyed by a content hash of the prompt. Semantic matching is the opt-in
`[embeddings]` Tier-1 upgrade over this exact-match floor — never required.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cage import debuglog, paths, schema


def _file(root: Path) -> Path:
    return paths.Footprint(root).base / "cache" / "responses.json"


def key_for(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def _load(root: Path) -> dict:
    f = _file(root)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def lookup(root: Path, prompt: str) -> dict | None:
    """Return the cached `{value, tokens}` for a prompt, or None on a miss."""
    hit = _load(root).get(key_for(prompt))
    debuglog.event(root, event="receipt", tool="response-cache", produced=bool(hit),
                   skip_reason="" if hit else "cache-miss")
    return hit


def store(root: Path, prompt: str, value: str, call_tokens: int) -> None:
    """Cache a response and the call-token count its future reuse would save."""
    data = _load(root)
    data[key_for(prompt)] = {"value": value, "tokens": int(call_tokens)}
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def hit_receipt(call_tokens: int, *, call: str = "", task: str = "",
                root: Path | None = None) -> dict:
    """The receipt for an eliminated call (actual: 0, full alternative saved). ``root``
    is optional and logging-only (best-effort, `CAGE_DEBUG`-gated) — the caller pushes
    the returned dict itself, this function never touches the ledger."""
    produced = call_tokens > 0
    if root is not None:
        debuglog.event(root, event="receipt", tool="response-cache", produced=produced,
                       skip_reason="" if produced else "no-saving-to-claim")
    return schema.make_receipt(tool="response-cache", raw_alternative=int(call_tokens),
                               actual=0, call=call, task=task, method="measured")
