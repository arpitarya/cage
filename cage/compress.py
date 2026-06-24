"""Tier-0 structural compression of tool output → a `compressor` receipt (plan §6).

Deterministic, no model: minify JSON and cap long arrays/strings (reversibly
annotated), or collapse whitespace for free text. The point is not the bytes — it
is the **savings receipt** a tool files so `cage attrib` can credit the compressor.
The learned Tier-2 compressor is a pluggable adapter over this same receipt shape.
"""
from __future__ import annotations

import json

from cage import schema
from cage.constants import CHARS_PER_TOKEN


def _toks(text: str) -> int:
    return max(0, round(len(text) / CHARS_PER_TOKEN))  # deterministic heuristic


def _shrink(obj, max_items: int, max_str: int):
    if isinstance(obj, dict):
        return {k: _shrink(v, max_items, max_str) for k, v in obj.items()}
    if isinstance(obj, list):
        head = [_shrink(x, max_items, max_str) for x in obj[:max_items]]
        if len(obj) > max_items:
            head.append(f"…+{len(obj) - max_items} more")
        return head
    if isinstance(obj, str) and len(obj) > max_str:
        return obj[:max_str] + f"…(+{len(obj) - max_str} chars)"
    return obj


def compress(text: str, *, max_items: int = 20, max_str: int = 200) -> tuple[str, int, int]:
    """Return (compressed_text, raw_tokens, actual_tokens)."""
    raw = _toks(text)
    try:
        out = json.dumps(_shrink(json.loads(text), max_items, max_str),
                         separators=(",", ":"), ensure_ascii=False)
    except ValueError:
        out = " ".join(text.split())
    return out, raw, _toks(out)


def receipt(text: str, *, call: str = "", task: str = "", method: str = "measured",
            **kw) -> dict:
    _out, raw, act = compress(text, **kw)
    return schema.make_receipt(tool="compressor", raw_alternative=raw, actual=act,
                               call=call, task=task, method=method)
