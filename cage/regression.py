"""`cage insights regression` — alert when cost-per-call drifts up (plan §8.3).

A deterministic threshold on the ledger: split calls into a recent window and the
baseline before it, compare mean cost per call, and flag drift past a tolerance —
the signal that a prompt edit broke prefix-cache hits or a route silently fell back
to a pricier model.
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, paths, policy, prices, render


def detect(root: Path, since: str = "7d", tolerance: float = 0.2,
           pol: dict | None = None) -> dict:
    # Costs are repriced from tokens × policy at derive time (`prices.call_usd`) —
    # transcript-sourced calls store est_cost_usd=0.0, so summing the stored field
    # reads a token-only ledger as $0 drift. A failed policy load degrades to the
    # stored figures (call_usd's own fallback), never raises off the read path.
    if pol is None:
        try:
            pol = policy.load(paths.Footprint(root).policy)
        except Exception:  # noqa: BLE001 — library default; CLI passes a checked pol
            pol = {}
    calls = ledger.calls(root)
    cut = ledger.since_cutoff(since)
    recent, base = [], []
    for c in calls:
        t = ledger._ts(c)
        (recent if (t and cut and t >= cut) else base).append(c)

    def mean(rows: list[dict]) -> float:
        return sum(prices.call_usd(pol, r) for r in rows) / len(rows) if rows else 0.0

    rm, bm = mean(recent), mean(base)
    drift = (rm - bm) / bm if bm else 0.0
    return {"since": since, "tolerance": tolerance, "recent_n": len(recent),
            "base_n": len(base), "recent_mean": round(rm, 6), "base_mean": round(bm, 6),
            "drift": round(drift, 4), "regressed": bool(bm and drift > tolerance)}


def render_regression(r: dict) -> str:
    if not r["base_n"] or not r["recent_n"]:
        return "cage: not enough history on both sides of the window to compare yet."
    arrow = "↑" if r["drift"] > 0 else "↓"
    verdict = (f"⚠ REGRESSION: cost/call up {r['drift'] * 100:.0f}% "
               f"(tolerance {r['tolerance'] * 100:.0f}%)") if r["regressed"] \
        else f"✔ stable ({arrow}{abs(r['drift']) * 100:.0f}% within tolerance)"
    rows = [["baseline", str(r["base_n"]), render.usd(r["base_mean"])],
            [f"recent (since {r['since']})", str(r["recent_n"]), render.usd(r["recent_mean"])]]
    return ("Cost-per-call drift\n\n"
            + render.table(["window", "calls", "mean/call"], rows, rights={1, 2})
            + f"\n\n  {verdict}")
