"""`cage report` — the ledger rollup: spend by agent / route / model / day (plan §7).

Any meter does this; it's the honest floor the rest of Cage builds on. Pure
aggregation over `calls.jsonl`, grouped on whichever dimension you ask for.
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, render

DIMENSIONS = ("route", "agent", "model", "provider", "day", "task")


def _key(call: dict, dim: str) -> str:
    if dim == "day":
        return (call.get("ts") or "")[:10] or "—"
    return str(call.get(dim) or "—")


def summarize(root: Path, dim: str = "route", since: str | None = None) -> dict:
    calls = ledger.since(ledger.calls(root), since)
    groups: dict[str, dict] = {}
    for c in calls:
        g = groups.setdefault(_key(c, dim), {"calls": 0, "tokens_in": 0,
                                             "tokens_out": 0, "cached_in": 0, "usd": 0.0})
        g["calls"] += 1
        g["tokens_in"] += c.get("tokens_in", 0)
        g["tokens_out"] += c.get("tokens_out", 0)
        g["cached_in"] += c.get("cached_in", 0)
        g["usd"] += c.get("est_cost_usd", 0.0)
    total = {"calls": sum(g["calls"] for g in groups.values()),
             "usd": sum(g["usd"] for g in groups.values()),
             "tokens_in": sum(g["tokens_in"] for g in groups.values()),
             "tokens_out": sum(g["tokens_out"] for g in groups.values())}
    return {"dim": dim, "since": since, "groups": groups, "total": total}


def render_report(rep: dict) -> str:
    if not rep["groups"]:
        return "cage: no calls recorded yet — meter some traffic first."
    rows = []
    for name, g in sorted(rep["groups"].items(), key=lambda kv: -kv[1]["usd"]):
        rows.append([name, render.tok(g["calls"]), render.tok(g["tokens_in"]),
                     render.tok(g["tokens_out"]), render.usd(g["usd"])])
    t = rep["total"]
    rows.append(["TOTAL", render.tok(t["calls"]), render.tok(t["tokens_in"]),
                 render.tok(t["tokens_out"]), render.usd(t["usd"])])
    head = [rep["dim"], "calls", "tok in", "tok out", "cost"]
    title = f"Ledger by {rep['dim']}" + (f" (since {rep['since']})" if rep["since"] else "")
    return f"{title}\n\n" + render.table(head, rows, rights={1, 2, 3, 4})
