"""The single unit→USD dispatch for a savings receipt (design §2.3, decision A).

One place unit semantics live: `usd` passes through, `tokens` cost at the call's
model price, `minutes` convert at the human rate, and `ms`/`gco2` are not money.
Adding `minutes` thus *removed* the branch that was duplicated in roi/attribution.

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
    if unit == "minutes":
        from cage import human  # lazy: only a minutes receipt reaches here
        return human.minutes_to_usd(receipt, pol)
    return 0.0  # ms / gco2 are not money — never counted as savings $
