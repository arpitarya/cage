"""Local staleness signals — what is left of them after USAGE-ONLY (ADR 0011).

This module carried **four** signals through v0.50, three of which were pricing:

1. *sync drift* — the project's `[meta] prices_version` older than the bundle's;
2. *bundle age* — the bundle's own `prices_date` older than `stale_days`;
3. *UNPRICED presence* — calls and call-less token receipts billing $0;
4. **policy-defaults drift** — the project's `[meta] policy_version` older than the
   bundle's (plan §3.10).

The money subsystem's deletion took 1–3 with it: there is no price table, no rate card,
no `prices.toml` staleness to report, and no priced/unpriced distinction left to make.
**Signal 4 survives unchanged** and is the module's whole surface now.

It is deliberately *not* folded into `policysync` — the caller relationship runs the
other way (`policy_line` defers to `policysync.sync_recommendation` for the wording, one
home for the string), and a view importing `freshness` for a drift line should not have
to import the module that performs the sync.

Print-only, exactly as before: a freshness line never gates, blocks, or exits non-zero.
It also never changes a derived number — policy drift cannot, because `policy.load`
already merges the bundled defaults in — which is why this line surfaces on diagnostics
and write-path events (doctor, the post-commit hook) and never in a view's footer.
"""
from __future__ import annotations

from pathlib import Path

from cage import paths, policy


def policy_line(root: Path) -> str | None:
    """Verbatim :func:`policysync.sync_recommendation` (plan §3.10) — one wording, one
    home. No project policy file ⇒ the bundle applies directly and nothing can be
    stale."""
    from cage import policysync  # deferred: CLI-layer module, keep import light
    foot = paths.Footprint(root)
    if not foot.policy.exists():
        return None
    meta = policy.load_project_raw(foot.policy).get("meta", {})
    return policysync.sync_recommendation(meta)


def freshness(root: Path, pol: dict, *, include_policy: bool = False) -> list[str]:
    """Zero-or-more actionable lines, ``[]`` when clean.

    ``pol`` is accepted and unused — it fed the price-age signal. The signature keeps
    both parameters so callers are unchanged across the money deletion; only
    ``include_policy=True`` can produce a line at all now."""
    out: list[str] = []
    if include_policy and (p := policy_line(root)) is not None:
        out.append(p)
    return out
