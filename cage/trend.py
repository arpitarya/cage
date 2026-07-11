"""`cage trend` — dates become a cost+time savings time-series (design §5b.4).

Pure derive over `ts` (no new entropy): bucket human receipts by ISO week or month,
join each to its agent calls, and report agent $ / human $ / saved $ / time saved per
bucket. Same two-clock model as `cage human` — saved time can go negative.

Derived attention (plan §4.10) renders as its own section below the table —
per-bucket turn-gap minutes via `attention.py`, always `estimated`, never
blended with the attested rows above it.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import attention, human, humanview, ledger, policy, prices, render


def _bucket(ts: str, by: str) -> str:
    try:
        d = _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return "—"
    if by == "month":
        return f"{d.year:04d}-{d.month:02d}"
    iso = d.isocalendar()
    return f"{iso[0]:04d}-W{iso[1]:02d}"


def series(root: Path, pol: dict, by: str = "week", since: str | None = None) -> dict:
    calls = ledger.calls(root)
    rcpts = [r for r in ledger.since(ledger.receipts(root, since=since), since) if r.get("tool") == "human"]
    buckets: dict[str, dict] = {}
    for r in rcpts:
        b = buckets.setdefault(_bucket(r.get("ts", ""), by),
                               {"tasks": 0, "agent_usd": 0.0, "human_usd": 0.0,
                                "human_min": 0.0, "agent_min": 0.0})
        runs = [c for c in calls if c.get("task") == r.get("task")]
        usd, _, _ = human.human_alternative_usd(r, pol)
        b["tasks"] += 1
        b["human_usd"] += usd
        # Repriced from tokens × policy like report/budget — the stored est_cost_usd
        # is 0.0 for transcript-sourced calls (the agent side read as free without it).
        b["agent_usd"] += sum(prices.call_usd(pol, c) for c in runs)
        b["human_min"] += human.human_minutes(r, pol)
        b["agent_min"] += humanview._active_minutes(runs)
    for b in buckets.values():
        b["saved_usd"] = round(b["human_usd"] - b["agent_usd"], 6)
        b["saved_min"] = round(b["human_min"] - b["agent_min"], 4)
        b["agent_usd"] = round(b["agent_usd"], 6)
        b["human_usd"] = round(b["human_usd"], 6)
    # Derived attention per bucket (plan §4.10) — a separate series, never folded
    # into the attested buckets above; attention.py owns the cap math.
    attn: dict[str, float] = {}
    for c in ledger.since(calls, since):
        m = attention.minutes_of(c, pol)
        if m > 0:
            k = _bucket(c.get("ts", ""), by)
            attn[k] = round(attn.get(k, 0.0) + m, 4)
    return {"by": by, "since": since, "buckets": buckets, "attention": attn,
            "idle_cap": attention.idle_cap_minutes(pol)}


def _render_attention(data: dict) -> str:
    """The derived-attention series — its own section, never a column blended into
    the attested table (the two sources must stay visually distinct)."""
    attn = data.get("attention") or {}
    if not attn:
        return ""
    lines = [f"derived attention · {attention.LABEL} · cap {data['idle_cap']:g} min "
             f"· {attention.METHOD} — never summed with the attested rows above:"]
    lines += [f"  {k}  {attn[k]:g} min ({attn[k] / 60:.1f} h)" for k in sorted(attn)]
    return "\n".join(lines)


def render_trend(data: dict, metric: str = "both") -> str:
    if not data["buckets"]:
        attn = _render_attention(data)
        return ("cage: no human receipts yet — nothing to trend."
                + (f"\n\n{attn}" if attn else ""))
    head = [data["by"]]
    if metric in ("cost", "both"):
        head += ["agent $", "human $", "$ saved"]
    if metric in ("time", "both"):
        head += ["time saved"]
    head += ["tasks"]
    rows = []
    for key in sorted(data["buckets"]):
        b = data["buckets"][key]
        row = [key]
        if metric in ("cost", "both"):
            row += [render.usd(b["agent_usd"]), render.usd(b["human_usd"]), render.usd(b["saved_usd"])]
        if metric in ("time", "both"):
            row += [f"{b['saved_min'] / 60:.1f} h"]
        row += [str(b["tasks"])]
        rows.append(row)
    rights = set(range(1, len(head)))
    win = f" · since {data['since']}" if data["since"] else ""
    out = (f"Savings trend · by {data['by']}{win}\n\n"
           + render.table(head, rows, rights=rights))
    attn = _render_attention(data)
    return out + (f"\n\n{attn}" if attn else "")
