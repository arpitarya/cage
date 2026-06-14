"""`cage forecast` — project monthly spend from the current trajectory (plan §8.5).

Takes the observed daily run-rate over the ledger's span and projects it to a
30-day month, then flags whether the daily budget ceiling implies a month-end blow
and on roughly which day. Deterministic — a straight extrapolation, tagged as such.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ledger, policy, render

_MONTH = 30


def _span_days(calls: list[dict]) -> int:
    days = {(c.get("ts") or "")[:10] for c in calls if c.get("ts")}
    days.discard("")
    if len(days) < 2:
        return 1
    lo, hi = min(days), max(days)
    try:
        return max(1, (_dt.date.fromisoformat(hi) - _dt.date.fromisoformat(lo)).days + 1)
    except ValueError:
        return 1


def project(root: Path, pol: dict) -> dict:
    calls = ledger.calls(root)
    total = sum(c.get("est_cost_usd", 0.0) for c in calls)
    span = _span_days(calls)
    per_day = total / span
    cap = policy.budgets(pol).get("daily_usd")
    monthly_cap = cap * _MONTH if cap else None
    projected = per_day * _MONTH
    blows = bool(monthly_cap and projected > monthly_cap)
    day_blown = int(monthly_cap / per_day) + 1 if (monthly_cap and per_day) else None
    return {"span_days": span, "total_usd": round(total, 6), "per_day": round(per_day, 6),
            "projected_month_usd": round(projected, 6), "daily_cap": cap,
            "monthly_cap": monthly_cap, "blows_budget": blows, "blows_on_day": day_blown}


def render_forecast(f: dict) -> str:
    if not f["total_usd"]:
        return "cage: no spend recorded yet — nothing to forecast."
    rows = [["observed", f"{f['span_days']}d", render.usd(f["total_usd"])],
            ["run-rate", "/day", render.usd(f["per_day"])],
            ["projected", "30d", render.usd(f["projected_month_usd"])]]
    body = render.table(["basis", "window", "usd"], rows, rights={2})
    if f["monthly_cap"]:
        if f["blows_budget"]:
            tail = (f"⚠ projects to blow the ${f['monthly_cap']:.2f} monthly ceiling "
                    f"~day {f['blows_on_day']} of 30")
        else:
            tail = f"✔ within the ${f['monthly_cap']:.2f} monthly ceiling"
    else:
        tail = "set budgets.daily_usd in policy.toml to get a ceiling check"
    return f"Spend forecast (linear extrapolation)\n\n{body}\n\n  {tail}"
