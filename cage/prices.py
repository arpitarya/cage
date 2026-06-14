"""Cost arithmetic — turn token counts + a price row into USD (plan §3.3, ≤50 lines)."""
from __future__ import annotations

from cage import policy


def call_cost_usd(pol: dict, provider: str, model: str, tokens_in: int,
                  tokens_out: int, cached_in: int = 0) -> float:
    """Invoice-grade cost: cached input billed at `cache_read`, the rest at `input`.

    `cached_in` is the slice of `tokens_in` the provider served from prefix cache.
    """
    p = policy.price(pol, provider, model)
    full_in = max(0, tokens_in - cached_in)
    usd = (full_in * p["input"] + cached_in * p["cache_read"]
           + tokens_out * p["output"]) / 1_000_000
    return round(usd, 6)


def input_cost_usd(pol: dict, provider: str, model: str, tokens_in: int) -> float:
    """Cost of an input-token count alone (for counterfactual matrix cells, §4.4)."""
    p = policy.price(pol, provider, model)
    return round(tokens_in * p["input"] / 1_000_000, 6)
