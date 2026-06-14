"""The substrate contract — call-record and receipt row factories (plan §3.1–3.2).

Rows are plain JSON dicts (append-only, diffable, stdlib-parseable). These
factories stamp ids/timestamps and validate the closed enums so a malformed row
never reaches the log. Prompt *bodies* are never a field — counts only (plan §10).
"""
from __future__ import annotations

import datetime as _dt

from cage import ids

UNITS = ("tokens", "usd", "ms", "gco2")
METHODS = ("measured", "modeled", "estimated")

CALL_FIELDS = ("id", "ts", "session", "task", "agent", "route", "provider", "model",
               "tokens_in", "tokens_out", "cached_in", "est_cost_usd",
               "latency_ms", "ok", "retries")
RECEIPT_FIELDS = ("id", "ts", "call", "task", "tool", "unit", "raw_alternative",
                  "actual", "saved", "method", "confidence", "meta")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_call(*, route: str, provider: str, model: str, tokens_in: int = 0,
              tokens_out: int = 0, cached_in: int = 0, est_cost_usd: float = 0.0,
              session: str = "", task: str = "", agent: str = "lib",
              latency_ms: int = 0, ok: bool = True, retries: int = 0,
              ts: str | None = None, call_id: str | None = None) -> dict:
    """One ground-truth call row. `cached_in` ⊆ `tokens_in` (billed at discount).

    `call_id` may be supplied for idempotent sources (a transcript turn's uuid) so
    re-parsing the same transcript never double-records the call.
    """
    return {"id": call_id or ids.new_id("c"), "ts": ts or _now(), "session": session, "task": task,
            "agent": agent, "route": route, "provider": provider, "model": model,
            "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
            "cached_in": int(cached_in), "est_cost_usd": round(float(est_cost_usd), 6),
            "latency_ms": int(latency_ms), "ok": bool(ok), "retries": int(retries)}


def make_receipt(*, tool: str, raw_alternative: float, actual: float,
                 call: str = "", task: str = "", unit: str = "tokens",
                 method: str = "modeled", confidence: float = 1.0,
                 meta: dict | None = None, ts: str | None = None) -> dict:
    """One savings receipt. `saved` is derived so it can never disagree (plan §3.2)."""
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} not in {UNITS}")
    if method not in METHODS:
        raise ValueError(f"method {method!r} not in {METHODS}")
    return {"id": ids.new_id("r"), "ts": ts or _now(), "call": call, "task": task,
            "tool": tool, "unit": unit, "raw_alternative": float(raw_alternative),
            "actual": float(actual), "saved": float(raw_alternative) - float(actual),
            "method": method, "confidence": float(confidence), "meta": meta or {}}
