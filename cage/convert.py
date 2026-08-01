"""The single unit→USD dispatch for a savings receipt (design §2.3, decision A).

One place unit semantics live: `usd` passes through, `tokens` cost at the call's
model price, and `ms`/`gco2` are not money.

`minutes` was a unit through v0.35 (the Tier-1 human axis). It is gone from
``schema.UNITS``, so nothing can write one — but a legacy ledger still holds them
and is never rewritten. Such a row has no USD route left, so it is worth **$0
here and is EXCLUDED from money totals with a visible footnote** (`report.py`'s
``legacy_human`` count) — never silently folded into a total.

A call-less token receipt (graphify/fux shims) has no model of its own: with an
``idx`` (`receiptprice.build`, built once per view) it prices via the resolution
ladder (`receiptprice.resolve` — plan §4.5); without one, the legacy $0 holds.
Receipts with a resolvable call are byte-identical to the pre-ladder contract.
"""
from __future__ import annotations

from cage import prices


def saved_usd(receipt: dict, call: dict, pol: dict,
              idx: dict[str, list[dict]] | None = None) -> float:
    """USD value of a receipt's `saved`, dispatched on its unit."""
    unit = receipt.get("unit", "tokens")
    if unit == "usd":
        return float(receipt.get("saved", 0.0))
    if unit == "tokens":
        if call:  # linked — the untouched legacy path
            return prices.input_cost_usd(pol, call.get("provider", ""), call.get("model", ""),
                                         int(receipt.get("saved", 0.0)))
        if idx is not None:
            from cage import receiptprice  # lazy: only call-less token receipts
            res = receiptprice.resolve(receipt, idx, pol)
            return res[0] if res else 0.0
        return prices.input_cost_usd(pol, "", "", int(receipt.get("saved", 0.0)))
    # minutes (legacy Tier-1) / ms / gco2 are not money — never counted as savings $
    return 0.0
