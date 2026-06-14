"""`cage recommend` — the cheapest-path recommender (plan §8.4).

Turns the ROI table from a report into a policy suggestion: enable every tool whose
recorded net saving (saved $ − its own cost) is positive, skip any that costs more
than it saves (a false economy — e.g. an ML compressor whose latency/cost outweighs
its trim). Deterministic, straight off the receipts.
"""
from __future__ import annotations

from pathlib import Path

from cage import render, roi


def recommend(root: Path, pol: dict, since: str | None = None) -> dict:
    tools = roi.by_tool(root, pol, since=since)["tools"]
    ranked = []
    for name, t in tools.items():
        net = t["saved_usd"] - t["cost_usd"]
        ranked.append({"tool": name, "net_usd": round(net, 6),
                       "saved_usd": round(t["saved_usd"], 6),
                       "verdict": "enable" if net > 0 else "skip"})
    ranked.sort(key=lambda r: -r["net_usd"])
    return {"since": since, "tools": ranked,
            "enable": [r["tool"] for r in ranked if r["verdict"] == "enable"],
            "skip": [r["tool"] for r in ranked if r["verdict"] == "skip"]}


def render_recommend(rec: dict) -> str:
    if not rec["tools"]:
        return "cage: no receipts yet — nothing to recommend. Meter some traffic first."
    rows = [[r["tool"], render.usd(r["saved_usd"]), render.usd(r["net_usd"]),
             ("✔ enable" if r["verdict"] == "enable" else "· skip")] for r in rec["tools"]]
    body = render.table(["tool", "saved", "net", "verdict"], rows, rights={1, 2})
    line = "  → enable: " + (", ".join(rec["enable"]) or "(none)")
    if rec["skip"]:
        line += "   ·   skip: " + ", ".join(rec["skip"])
    return f"Cheapest-path recommendation\n\n{body}\n\n{line}"
