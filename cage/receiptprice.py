"""The pricing ladder for call-less token receipts (plan §4.5; shipped v0.23).

A tool receipt with `unit="tokens"` but no linked call (graphify/fux shims — the
saved tokens belong to future calls the shim can't know) has no model to price
at, so it rendered $0. This module is the ONE place that resolves a pricing
model for such a receipt, by a deterministic ladder:

1. **price_at** — explicit policy routing: `[tools.<tool>] price_at =
   "provider/model"`, validated against `policy.price_match` at use time. A
   dangling route (no price row resolves) is UNPRICED, never a fall-through to
   rung 2 — the dangling-alias rule: an explicit-but-broken route must surface,
   not be papered over by a heuristic.
2. **task-model** — the dominant model of the calls joined to the receipt's
   `task` (task-id calls plus `taskgroup`'s session-window adoptions — receipts
   carry no `session` field, so the task join IS the session fallback).
   Dominant = max summed `tokens_in` per `(provider, model)`; ties break by
   call count, then lexicographic `provider/model` — a total order, so same
   ledger + policy ⇒ same winner, always.
3. **refusal** — no rung matches ⇒ ``None``, exactly the legacy $0, surfaced
   in the UNPRICED ⚠ summary. A wrong number is worse than none.

Derive-time only: no receipt row is ever written or rewritten, so a later
policy fix re-prices history. The resolved USD inherits the receipt's own
`method` (never upgraded); the rung is footnoted in text views and a column in
CSV. Receipts *with* a resolvable call id never enter the ladder — their path
(`convert.saved_usd` at the linked call's model) is untouched.
"""
from __future__ import annotations

from cage import policy, prices, taskgroup

# Rung labels — footnoted in text views, a `priced_via` column in CSV.
PRICE_AT = "price_at"
TASK_MODEL = "task-model"
LINKED = "call"  # not a ladder rung: the untouched linked-call path, named for CSV

UNPRICED_HINT = ("run: cage prices route-tool <tool> --to <provider>/<model>"
                 "  (or run in a metered session)")


def eligible(receipt: dict, calls_by_id: dict) -> bool:
    """Whether a receipt enters the ladder: token unit AND no *resolvable* call.

    The single entry condition every consumer uses. An unresolvable call id (an
    imported fleet bundle missing that call) counts as call-less — the ladder
    improves on the silent $0 it priced at before.
    """
    return (receipt.get("unit", "tokens") == "tokens"
            and receipt.get("call", "") not in calls_by_id)


def build(calls: list[dict], receipts: list[dict]) -> dict[str, list[dict]]:
    """The pre-built ``{task_id: [calls]}`` join, built ONCE per view — consumers
    thread it down instead of re-scanning the ledger per receipt. Reuses
    `taskgroup.join_rows` (the documented task-id + session-window precedence)."""
    return {tid: j["calls"] for tid, j in taskgroup.join_rows(calls, receipts).items()}


def routes(pol: dict) -> dict[str, str]:
    """The configured `[tools.<tool>] price_at` routes: ``{tool: "prov/model"}``.
    Read surface for `prices list`/doctor (dangling-route warnings)."""
    out = {}
    for tool, entry in pol.get("tools", {}).items():
        if isinstance(entry, dict) and isinstance(entry.get("price_at"), str) and entry["price_at"]:
            out[tool] = entry["price_at"]
    return dict(sorted(out.items()))


def dangling_routes(pol: dict) -> dict[str, str]:
    """The `price_at` routes whose target resolves no price row — each prices
    nothing (rung 1 refuses rather than falls through), so warn loudly."""
    out = {}
    for tool, target in routes(pol).items():
        prov, _, model = target.partition("/")
        if policy.price_match(pol, prov, model)[1] == "none":
            out[tool] = target
    return out


def dominant_model(calls: list[dict]) -> tuple[str, str] | None:
    """The dominant `(provider, model)` of a call set — max summed `tokens_in`,
    ties by call count, then lexicographic `provider/model` (total order)."""
    tally: dict[tuple[str, str], list[int]] = {}
    for c in calls:
        key = (c.get("provider", ""), c.get("model", ""))
        t = tally.setdefault(key, [0, 0])
        t[0] += c.get("tokens_in", 0)
        t[1] += 1
    if not tally:
        return None
    return min(tally, key=lambda k: (-tally[k][0], -tally[k][1], f"{k[0]}/{k[1]}"))


def resolve(receipt: dict, idx: dict[str, list[dict]], pol: dict) -> tuple[float, str, str] | None:
    """Price a call-less token receipt: ``(usd, rung, "provider/model")`` or
    ``None`` (unpriced — rung 3's refusal). USD keeps the receipt's `method`;
    this function resolves a model, never a provenance."""
    target = routes(pol).get(receipt.get("tool", ""))
    if target is not None:
        prov, _, model = target.partition("/")
        if policy.price_match(pol, prov, model)[1] == "none":
            return None  # dangling explicit route — refuse, never fall through
        usd = prices.input_cost_usd(pol, prov, model, int(receipt.get("saved", 0.0)))
        return (usd, PRICE_AT, target)
    dom = dominant_model(idx.get(receipt.get("task", ""), []))
    if dom is not None:
        prov, model = dom
        if policy.price_match(pol, prov, model)[1] != "none":
            usd = prices.input_cost_usd(pol, prov, model, int(receipt.get("saved", 0.0)))
            return (usd, TASK_MODEL, f"{prov}/{model}")
    return None


def footnote(rung: str, tool: str, model_key: str) -> str:
    """The one footnote phrasing every text view prints for a ladder-priced row."""
    if rung == PRICE_AT:
        return f"≈ {tool} priced via [tools.{tool}] price_at ({model_key})"
    return f"≈ {tool} priced at task model ({model_key})"


def unpriced_receipts_line(unpriced: dict) -> str:
    """The receipts twin of `report.unpriced_line` — printed by roi and report
    whenever tool receipts refused to price (rung 3): the analyst sees the gap.
    ``unpriced`` is ``{"receipts": n, "tokens": n, "tools": [names]}``; every
    hint is a **runnable command** with the real tool name substituted (the
    fix-hint contract — never a hand-edit instruction). Multi-line: headline,
    then one ``run:`` line per affected tool, indented two spaces."""
    from cage import render
    head = (f"⚠ {unpriced['receipts']} tool receipt(s) ({render.tok(unpriced['tokens'])} "
            f"tokens saved) UNPRICED — totals understated:")
    hints = [f"  {UNPRICED_HINT.replace('<tool>', t)}"
             for t in unpriced.get("tools", []) or ["<tool>"]]
    return "\n".join([head, *hints])
