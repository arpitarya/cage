"""`cage data export --otel` — the ledger as OpenTelemetry GenAI-conformant JSON
(docs/archive/v0.39-otel-export.handoff.md). One-way REPORTING, exactly like `--csv`: never an
import source, never combined with `--study` (the fleet bundle stays jsonl).

**The GenAI semantic conventions are pre-stable.** As of the targeted version
(`constants.OTEL_SEMCONV_VERSION`, June 2026) the `gen_ai.*` attributes live in a
dedicated repo, carry no 1.0, and names can still change between releases. That
collides with cage's determinism law — same ledger + policy ⇒ same output — so cage
never silently follows upstream: the targeted version is pinned in one constant and
stamped in every emitted document's `cage.meta` block, exactly like `[meta]
prices_version`. A spec bump is a deliberate, changelog'd change.

**Calls → `gen_ai.*` attributes**, only the ones the convention defines and cage can
back with an honest value:

- `gen_ai.system` = the call's `provider`, `gen_ai.request.model` = its `model` —
  always present, required substrate fields.
- `gen_ai.usage.input_tokens` / `gen_ai.usage.output_tokens` = `tokens_in` /
  `tokens_out` — always present; a call row's whole point is a recorded count.
- `gen_ai.client.operation.duration` = `latency_ms / 1000` (seconds) — the one
  GenAI-defined name for call latency (a metric name in the convention, reused here
  as a flat attribute key since this export is a flat attribute map, not real OTLP
  metrics/spans — out of scope per the handoff). **Omitted, never zero**, when
  `latency_ms` is 0: several capture routes (the proxy, some shims) never stamp
  latency, and a fabricated `0` would read as a measured instant call.

**Receipts/savings have no GenAI equivalent — decision: cage-namespaced, never an
invented `gen_ai.*` name.** Each lands in a separate `cage.savings` array under
`cage.*` keys. `cage.saved` is always GROSS (`netsaved.GROSS_NOTE`) — the avoided
read cost, never netted against the cost of using the tool. `cage.saved_usd` prices
through the same resolution ladder every other view uses (`receiptprice`/`convert`)
and is **omitted, never zero**, when the ladder refuses (UNPRICED) or the unit isn't
money (`ms`/`gco2`) — never a fabricated dollar figure. `cage.method` always
survives so a `modeled`/`estimated` number can never arrive at a vendor looking
measured. Legacy Tier-1 human-axis rows (`tool="human"` / `unit="minutes"`, axis
removed v0.36) are excluded the same way `report.py` excludes them, and counted in
`cage.meta.legacy_human_excluded`.

Deterministic: `--since`-filtered ledger order (same as every other export path),
stable per-row key order, LF pinned, no clock, no randomness.
"""
from __future__ import annotations

from cage import convert, receiptprice
from cage.constants import OTEL_SEMCONV_STATUS, OTEL_SEMCONV_VERSION


def _is_legacy_human(r: dict) -> bool:
    """A pre-0.36 Tier-1 row (`report._is_legacy_human`'s predicate, restated here
    rather than importing a private name across modules): the removed human axis's
    tool, or its removed unit. Excluded, never priced — no USD route survives it."""
    return r.get("tool") == "human" or r.get("unit") == "minutes"


def _call_span(call: dict) -> dict:
    span = {
        "cage.id": call.get("id", ""),
        "cage.ts": call.get("ts", ""),
        "gen_ai.system": call.get("provider", ""),
        "gen_ai.request.model": call.get("model", ""),
        "gen_ai.usage.input_tokens": int(call.get("tokens_in", 0)),
        "gen_ai.usage.output_tokens": int(call.get("tokens_out", 0)),
    }
    latency_ms = int(call.get("latency_ms", 0))
    if latency_ms:
        span["gen_ai.client.operation.duration"] = round(latency_ms / 1000, 3)
    if call.get("task"):
        span["cage.task"] = call["task"]
    if call.get("agent"):
        span["cage.agent"] = call["agent"]
    return span


def _saved_usd(r: dict, calls_by_id: dict, idx: dict, pol: dict) -> float | None:
    """USD for one receipt's gross `saved`, or ``None`` when there is no honest
    figure — an UNPRICED ladder refusal, or a non-money unit (`ms`/`gco2`)."""
    unit = r.get("unit", "tokens")
    if unit == "usd":
        return float(r.get("saved", 0.0))
    if unit != "tokens":  # ms / gco2 — not money, never a fabricated $0
        return None
    if receiptprice.eligible(r, calls_by_id):
        res = receiptprice.resolve(r, idx, pol)
        return res[0] if res is not None else None  # None = UNPRICED, omit
    # The Optional variant: an unpriced model must OMIT the field, not export a
    # hard 0.0 that reads as "this saving was worth nothing".
    return convert.saved_usd_opt(r, calls_by_id.get(r.get("call"), {}), pol)


def _savings_row(r: dict, calls_by_id: dict, idx: dict, pol: dict) -> dict:
    row = {
        "cage.id": r.get("id", ""),
        "cage.ts": r.get("ts", ""),
        "cage.tool": r.get("tool", ""),
        "cage.unit": r.get("unit", "tokens"),
        "cage.saved": r.get("saved", 0.0),
        "cage.method": r.get("method", "modeled"),
        "cage.confidence": r.get("confidence", 0.0),
    }
    if r.get("task"):
        row["cage.task"] = r["task"]
    if r.get("call"):
        row["cage.call"] = r["call"]
    usd = _saved_usd(r, calls_by_id, idx, pol)
    if usd is not None:
        row["cage.saved_usd"] = round(usd, 6)
    return row


def render(calls: list[dict], receipts: list[dict], all_calls: list[dict], pol: dict) -> str:
    """One deterministic JSON document: `cage.meta` (semconv pin) + `calls`
    (`gen_ai.*` spans) + `cage.savings` (cage-namespaced receipts). ``all_calls`` is
    the *unfiltered* call set so the receipt pricing ladder (`receiptprice.build`)
    can resolve a call-less receipt's task-model rung even when `--since`/`--project`
    narrowed the emitted `calls` array."""
    import json

    calls_by_id = {c["id"]: c for c in all_calls}
    idx = receiptprice.build(all_calls, receipts)
    legacy = [r for r in receipts if _is_legacy_human(r)]
    priced_receipts = [r for r in receipts if not _is_legacy_human(r)]
    doc = {
        "cage.meta": {
            "semconv": OTEL_SEMCONV_VERSION,
            "semconv_status": OTEL_SEMCONV_STATUS,
            "legacy_human_excluded": len(legacy),
        },
        "calls": [_call_span(c) for c in calls],
        "cage.savings": [_savings_row(r, calls_by_id, idx, pol) for r in priced_receipts],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
