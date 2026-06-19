"""The single unit→USD dispatch for a savings receipt (design §2.3, decision A).

One place unit semantics live: `usd` passes through, `tokens` cost at the call's
model price, `minutes` convert at the human rate, and `ms`/`gco2` are not money.
Adding `minutes` thus *removed* the branch that was duplicated in roi/attribution.
"""
from __future__ import annotations

from cage import prices


def saved_usd(receipt: dict, call: dict, pol: dict) -> float:
    """USD value of a receipt's `saved`, dispatched on its unit."""
    unit = receipt.get("unit", "tokens")
    if unit == "usd":
        return float(receipt.get("saved", 0.0))
    if unit == "tokens":
        return prices.input_cost_usd(pol, call.get("provider", ""), call.get("model", ""),
                                     int(receipt.get("saved", 0.0)))
    if unit == "minutes":
        from cage import human  # lazy: only a minutes receipt reaches here
        return human.minutes_to_usd(receipt, pol)
    return 0.0  # ms / gco2 are not money — never counted as savings $
