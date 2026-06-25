"""`cage roi` — saved $ per tool vs the tool's own cost + added latency (plan §7, §8).

ROI per tool, not just a total: a deterministic tool (fux, graphify) saves at $0
of its own cost; an optional ML tool may save more but adds latency. A tool's own
cost / added latency ride in its receipt `meta` (`tool_cost_usd`, `added_latency_ms`).
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, ledger, render


def by_tool(root: Path, pol: dict, since: str | None = None) -> dict:
    calls = {c["id"]: c for c in ledger.calls(root)}
    rcpts = ledger.since(ledger.receipts(root, since=since), since)
    tools: dict[str, dict] = {}
    for r in rcpts:
        if r.get("tool") == "human":  # Tier-1 baseline, not a within-agent tool (§4.4)
            continue
        t = tools.setdefault(r["tool"], {"receipts": 0, "saved_usd": 0.0,
                                         "cost_usd": 0.0, "added_ms": 0})
        t["receipts"] += 1
        t["saved_usd"] += convert.saved_usd(r, calls.get(r.get("call"), {}), pol)
        meta = r.get("meta") or {}
        t["cost_usd"] += float(meta.get("tool_cost_usd", 0.0))
        t["added_ms"] += int(meta.get("added_latency_ms", 0))
    return {"since": since, "tools": tools}


def render_roi(data: dict) -> str:
    if not data["tools"]:
        return "cage: no receipts recorded yet — teach your tools to emit them."
    rows = []
    for name, t in sorted(data["tools"].items(), key=lambda kv: -kv[1]["saved_usd"]):
        net = t["saved_usd"] - t["cost_usd"]
        rows.append([name, render.usd(t["saved_usd"]), render.usd(t["cost_usd"]),
                     render.usd(net), f"{t['added_ms']:,} ms"])
    title = "ROI by tool" + (f" (since {data['since']})" if data["since"] else "")
    return f"{title}\n\n" + render.table(
        ["tool", "saved", "own cost", "net", "added lat"], rows, rights={1, 2, 3, 4})
