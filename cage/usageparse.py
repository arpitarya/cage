"""Extract token usage from an Anthropic/OpenAI response body (plan §5, ≤60 lines).

Handles both a buffered JSON response and a Server-Sent-Events stream, for either
protocol — so the proxy meters whatever speaks the wire format, naming nothing.
Returns ``(model, tokens_in, tokens_out, cached_in)``; zeros if nothing parseable.
"""
from __future__ import annotations

import json


def _sse_objects(text: str):
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("data:"):
            payload = line[5:].strip()
            if payload and payload != "[DONE]":
                try:
                    yield json.loads(payload)
                except ValueError:
                    continue


def _from_anthropic_usage(u: dict) -> tuple[int, int, int]:
    inp = int(u.get("input_tokens", 0) or 0)
    cache_read = int(u.get("cache_read_input_tokens", 0) or 0)
    cache_make = int(u.get("cache_creation_input_tokens", 0) or 0)
    out = int(u.get("output_tokens", 0) or 0)
    return inp + cache_read + cache_make, out, cache_read


def extract(body: bytes, path: str) -> tuple[str, int, int, int]:
    text = body.decode("utf-8", "replace")
    try:                                  # non-streaming JSON response
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and "usage" in doc:
        return _from_doc(doc, path)
    # Streaming SSE: merge input from the opening frame, output from the last.
    model, tin, tout, cached = "", 0, 0, 0
    for obj in _sse_objects(text):
        model = model or _model(obj) or _model(obj.get("message", {}))
        u = obj.get("usage") or obj.get("message", {}).get("usage")
        if not u:
            continue
        if "input_tokens" in u or "prompt_tokens" in u:
            tin, _o, cached = _ingest(u, path, tin, cached)
        out = u.get("output_tokens", u.get("completion_tokens"))
        if out:
            tout = int(out)
    return model, tin, tout, cached


def _from_doc(doc: dict, path: str) -> tuple[str, int, int, int]:
    u = doc["usage"]
    if "/messages" in path or "input_tokens" in u:
        tin, tout, cached = _from_anthropic_usage(u)
    else:
        tin, tout, cached = int(u.get("prompt_tokens", 0)), int(u.get("completion_tokens", 0)), 0
    return _model(doc), tin, tout, cached


def _ingest(u, path, tin, cached):
    if "input_tokens" in u:
        a, _o, c = _from_anthropic_usage(u)
        return a, _o, c
    return int(u.get("prompt_tokens", tin)), 0, cached


def _model(obj) -> str:
    m = obj.get("model") if isinstance(obj, dict) else None
    return m if isinstance(m, str) else ""
