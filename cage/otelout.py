"""`cage data export --otel` — the ledger as OpenTelemetry GenAI-conformant JSON
(work/archive/v0.39-otel-export.handoff.md). One-way REPORTING, exactly like `--csv`: never an
import source, never combined with `--study` (the fleet bundle stays jsonl).

**The GenAI semantic conventions are pre-stable, and the pin says exactly what it
pins.** On main-repo release **v1.42.0 (2026-06-12)** every `gen_ai.*` convention was
deprecated in `open-telemetry/semantic-conventions` and moved to the dedicated
`open-telemetry/semantic-conventions-genai`, which as of 2026-08-11 carries **no tagged
release** and is still `Status: Development` throughout. So `OTEL_SEMCONV_VERSION` names
the *last main-repo release that defined these names* — a checkable claim — and the repo
and maturity are stamped beside it rather than a version number nobody could verify
(OTEL-SEMCONV-PIN; the pin's trigger is the GenAI repo cutting its first tag). That
discipline exists because the convention collides with cage's determinism law — same
ledger + policy ⇒ same output — so cage never silently follows upstream: the target is
pinned in one place and stamped in every emitted document's `cage.meta` block, exactly
like `[meta] prices_version`. A spec bump is a deliberate, changelog'd change.

**Calls → `gen_ai.*` attributes**, only the ones the convention defines and cage can
back with an honest value:

- `gen_ai.provider.name` = the call's `provider`, `gen_ai.request.model` = its `model`
  — always present, required substrate fields. It was `gen_ai.system` until 2026-08-11;
  that spelling was **renamed in semconv v1.37.0**, five releases before the version
  this export pins, so cage was emitting a deprecated attribute while claiming a target
  that had already dropped it. Emitting both names during a transition was rejected —
  a consumer that sums rather than coalesces would double-count.
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
`cage.*` keys. `cage.saved` is always GROSS (`savings.GROSS_NOTE`) — the avoided
read cost, never netted against the cost of using the tool. There is **no
`cage.saved_usd`**: it priced through the `receiptprice`/`convert` ladder, which went
with the money subsystem (USAGE-ONLY, ADR 0011). `cage.unit` still names the receipt's
own unit, so a consumer reads the figure in the unit it was recorded in and cage
converts nothing. `cage.method` always survives so a `modeled`/`estimated` number can
never arrive at a vendor looking measured. Legacy Tier-1 human-axis rows (`tool="human"` / `unit="minutes"`, axis
removed v0.36) are excluded the same way `report.py` excludes them, and counted in
`cage.meta.legacy_human_excluded`.

Deterministic: `--since`-filtered ledger order (same as every other export path),
stable per-row key order, LF pinned, no clock, no randomness.
"""
from __future__ import annotations

from cage.constants import (OTEL_SEMCONV_SOURCE, OTEL_SEMCONV_STATUS,
                            OTEL_SEMCONV_VERSION, OTEL_SEMCONV_VERSION_MEANS)


def _is_legacy_human(r: dict) -> bool:
    """A pre-0.36 Tier-1 row (`report._is_legacy_human`'s predicate, restated here
    rather than importing a private name across modules): the removed human axis's
    tool, or its removed unit. Excluded, never priced — no USD route survives it."""
    return r.get("tool") == "human" or r.get("unit") == "minutes"


def _call_span(call: dict) -> dict:
    span = {
        "cage.id": call.get("id", ""),
        "cage.ts": call.get("ts", ""),
        # `gen_ai.provider.name`, NOT `gen_ai.system` — renamed in semconv **v1.37.0**,
        # five releases before the version this export pins, so emitting the old spelling
        # was claiming a target that had already removed it. Renamed 2026-08-11
        # (OTEL-SEMCONV-PIN). Emitting BOTH names was considered and rejected: a consumer
        # that sums rather than coalesces would double-count, and cage would be shipping
        # a shape no version of the spec defines.
        "gen_ai.provider.name": call.get("provider", ""),
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


def _savings_row(r: dict) -> dict:
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
    return row


def render(calls: list[dict], receipts: list[dict], all_calls: list[dict], pol: dict) -> str:
    """One deterministic JSON document: `cage.meta` (semconv pin) + `calls`
    (`gen_ai.*` spans) + `cage.savings` (cage-namespaced receipts).

    ``all_calls`` and ``pol`` are accepted and unused. They fed the receipt pricing
    ladder, which is gone (USAGE-ONLY, ADR 0011); the parameters stay so every caller's
    signature is unchanged and a `--since`-narrowed export keeps the same shape."""
    import json

    legacy = [r for r in receipts if _is_legacy_human(r)]
    priced_receipts = [r for r in receipts if not _is_legacy_human(r)]
    doc = {
        "cage.meta": {
            "semconv": OTEL_SEMCONV_VERSION,
            "semconv_means": OTEL_SEMCONV_VERSION_MEANS,
            "semconv_source": OTEL_SEMCONV_SOURCE,
            "semconv_status": OTEL_SEMCONV_STATUS,
            "legacy_human_excluded": len(legacy),
        },
        "calls": [_call_span(c) for c in calls],
        "cage.savings": [_savings_row(r) for r in priced_receipts],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
