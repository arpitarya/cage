"""Tokens → estimated provider AI-credits — the single dispatch (mirrors `convert.saved_usd`).

Credits are **estimated**, never measured: post-2026 GitHub/Codex plans consume credits
as a function of tokens, so a per-model `[credits.<provider>."<model>"] per_mtok`
multiplier (policy — the economics layer) yields an estimate. Token-based providers ONLY;
a provider/model with no configured multiplier (Kiro's units-of-work `kiro`/`agent`, or
any unconfigured model) returns ``None`` — tokens shown, no fabricated credit number
(a wrong number is worse than no number). Unknown multiplier ⇒ ``None``, never a guess.

Match is **exact** (no family fallback): an estimate borrowed across models would be a
*different* wrong number, so a configured key must name the exact model id its agent
stamps. This is the one place tokens→credits semantics live (the `convert` analogue).
"""
from __future__ import annotations

from cage.constants import TOKENS_PER_MILLION


def per_mtok(pol: dict, provider: str, model: str) -> float | None:
    """The configured credits-per-million-token multiplier for ``(provider, model)``,
    or ``None`` when unconfigured. Exact key only (see module docstring)."""
    row = pol.get("credits", {}).get(provider, {}).get(model)
    if isinstance(row, dict) and isinstance(row.get("per_mtok"), (int, float)):
        return float(row["per_mtok"])
    return None


def tokens_to_credits(pol: dict, provider: str, model: str, tokens: int) -> float | None:
    """Estimated credits for ``tokens`` of ``(provider, model)``, or ``None`` when no
    multiplier is configured (tokens-only, no number). Mirrors ``convert.saved_usd``'s
    single-dispatch shape so credit semantics live in exactly one place."""
    mult = per_mtok(pol, provider, model)
    if mult is None:
        return None
    return round(tokens * mult / TOKENS_PER_MILLION, 4)
