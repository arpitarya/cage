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

from cage import policy, prices


def saved_usd_opt(receipt: dict, call: dict, pol: dict,
                  idx: dict[str, list[dict]] | None = None) -> float | None:
    """USD value of a receipt's `saved`, or **None when there is no honest figure**.

    The Optional twin of :func:`saved_usd`, and the home of a distinction the plain
    version structurally cannot make: `policy.price` returns a **zero** price row for a
    model it cannot price, so `prices.input_cost_usd` yields a hard `0.0` that is
    indistinguishable from a saving genuinely worth nothing. Summed into a total that is
    harmless; *exported as a field* it is a fabricated dollar figure.

    None means one of three things, all of them "cage has no dollar here": a non-money
    unit (ms/gCO₂/legacy minutes), an unpriced `(provider, model)`, or an UNPRICED
    verdict from the `receiptprice` ladder. `0.0` means a real, priced zero.

    It lives **here**, at the one place unit semantics are dispatched, and not in the
    consumer that noticed the problem — a second copy of this ladder is exactly how the
    credits rung drifted once already."""
    unit = receipt.get("unit", "tokens")
    if unit == "usd":
        return float(receipt.get("saved", 0.0))
    if unit != "tokens":
        return None          # ms / gco2 / legacy minutes are not money at all
    saved = int(receipt.get("saved", 0.0))
    if call:  # linked
        provider, model = call.get("provider", ""), call.get("model", "")
        if policy.price_match(pol, provider, model)[1] == "none":
            return None      # UNPRICED — the zero below would be a fabrication
        return prices.input_cost_usd(pol, provider, model, saved)
    if idx is not None:
        from cage import receiptprice  # lazy: only call-less token receipts
        res = receiptprice.resolve(receipt, idx, pol)
        return res[0] if res else None
    return None              # no call and no index: nothing to price against


def saved_usd(receipt: dict, call: dict, pol: dict,
              idx: dict[str, list[dict]] | None = None) -> float:
    """USD value of a receipt's `saved`, dispatched on its unit; `0.0` when unpriceable.

    The summing path, unchanged: every aggregate caller wants a number it can add, and
    a zero contributes nothing to a total. A caller that must distinguish *unpriced*
    from *zero* — anything that emits the figure as a field — uses
    :func:`saved_usd_opt` instead."""
    return saved_usd_opt(receipt, call, pol, idx) or 0.0
