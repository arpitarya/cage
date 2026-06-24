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


def call_usd(pol: dict, call: dict) -> float:
    """Authoritative per-call cost for `report`/`budget` (derive-time, never stored).

    Recompute from tokens × policy when the model is priced (transcript-sourced
    calls carry counts but no `est_cost_usd`); else fall back to the stored
    `est_cost_usd` for providers cage can't tokenize (a search API that
    self-reports its cost).
    """
    p = policy.price(pol, call.get("provider", ""), call.get("model", ""))
    if p["input"] or p["output"] or p["cache_read"]:
        return call_cost_usd(pol, call.get("provider", ""), call.get("model", ""),
                             call.get("tokens_in", 0), call.get("tokens_out", 0),
                             call.get("cached_in", 0))
    return float(call.get("est_cost_usd", 0.0))
