"""Cost arithmetic — turn token counts + a price row into USD (plan §3.3, ≤50 lines)."""
from __future__ import annotations

from cage import policy
from cage.constants import TOKENS_PER_MILLION


def call_cost_usd(pol: dict, provider: str, model: str, tokens_in: int,
                  tokens_out: int, cached_in: int = 0) -> float:
    """Invoice-grade cost: cached input billed at `cache_read`, the rest at `input`.

    `cached_in` is the slice of `tokens_in` the provider served from prefix cache.
    """
    p = policy.price(pol, provider, model)
    full_in = max(0, tokens_in - cached_in)
    usd = (full_in * p["input"] + cached_in * p["cache_read"]
           + tokens_out * p["output"]) / TOKENS_PER_MILLION
    return round(usd, 6)


def input_cost_usd(pol: dict, provider: str, model: str, tokens_in: int) -> float:
    """Cost of an input-token count alone (for counterfactual matrix cells, §4.4)."""
    p = policy.price(pol, provider, model)
    return round(tokens_in * p["input"] / TOKENS_PER_MILLION, 6)


def call_usd_match(pol: dict, call: dict) -> tuple[float, str, str | None]:
    """Per-call cost plus *how* it priced:
    ``credits | exact | alias | family | self | none``.

    **The ONE pricing choke point** — `call_usd` wraps it, and every USD consumer in
    cage (report, budget, chats, compare, verdict, roi, netsaved, study, forecast,
    quality, freshness, doctor) reaches a dollar through one of the two. A rung added
    here is inherited everywhere, with no per-view fork; that is why the credit ladder
    lands here rather than in any view.

    Rung 1 (``credits``, `cage/creditprice.py`) wins when the row carries a **recorded
    billed credit** and a `[billing.<agent>] usd_per_credit` rate is configured — the
    provider's own computation beats cage's price table, and it prices `copilot/auto`,
    which no table row matches. It is `modeled`, never `measured`: the count is fact,
    the dollar is your configured rate.

    Otherwise: recompute from tokens × policy when the model has an exact, alias-routed,
    or family price row (transcript-sourced calls carry counts but no `est_cost_usd`);
    else fall back to the stored `est_cost_usd` for a provider cage can't tokenize
    (a search API that self-reports its cost) → ``self``. No price *and* no
    self-cost ⇒ a genuine $0 that must surface as ``none`` (UNPRICED), never hide
    in the totals.

    Returns ``(usd, match, matched_key)``; ``matched_key`` is the price row used
    for a ``family`` match (so the read surface can show "≈ priced by family") or
    the ``prov/model`` target for an ``alias`` route, and ``None`` for ``credits``
    (which resolves no model at all — that is the point of the rung).
    """
    from cage import creditprice
    credit_usd = creditprice.resolve(pol, call)
    if credit_usd is not None:
        return credit_usd, creditprice.MATCH, None
    provider, model = call.get("provider", ""), call.get("model", "")
    _, match, key = policy.price_match(pol, provider, model)
    if match != "none":
        usd = call_cost_usd(pol, provider, model, call.get("tokens_in", 0),
                            call.get("tokens_out", 0), call.get("cached_in", 0))
        return usd, match, key
    est = float(call.get("est_cost_usd", 0.0))
    return est, ("self" if est else "none"), None


def call_usd(pol: dict, call: dict) -> float:
    """Authoritative per-call cost for `report`/`budget` (derive-time, never stored).
    See :func:`call_usd_match` for the match-kind signal."""
    return call_usd_match(pol, call)[0]
