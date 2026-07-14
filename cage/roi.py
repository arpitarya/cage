"""`cage roi` — saved $ per tool vs the tool's own cost + added latency (plan §7, §8).

ROI per tool, not just a total: a deterministic tool (fux, graphify) saves at $0
of its own cost; an optional ML tool may save more but adds latency. A tool's own
cost / added latency ride in its receipt `meta` (`tool_cost_usd`, `added_latency_ms`).

Call-less token receipts price via the resolution ladder (`receiptprice`, plan
§4.5): each row's `priced_via` names every path its receipts priced through
(`call` = linked, `price_at`/`task-model` = ladder rungs, `unpriced` = refused),
footnoted in text and a column in CSV. Unpriceable tool receipts surface in the
UNPRICED ⚠ line — a $0 must never be silent.
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, ledger, receiptprice, render
from cage.constants import METHOD_TRUST as _TRUST


def by_tool(root: Path, pol: dict, since: str | None = None) -> dict:
    all_calls = ledger.calls(root)
    calls = {c["id"]: c for c in all_calls}
    rcpts = ledger.since(ledger.receipts(root, since=since), since)
    idx = receiptprice.build(all_calls, rcpts)  # once per view, never per receipt
    tools: dict[str, dict] = {}
    unpriced = {"receipts": 0, "tokens": 0, "tools": set()}
    for r in rcpts:
        if r.get("tool") == "human":  # Tier-1 baseline, not a within-agent tool (§4.4)
            continue
        t = tools.setdefault(r["tool"], {"receipts": 0, "saved_usd": 0.0,
                                         "cost_usd": 0.0, "added_ms": 0,
                                         "method": "measured", "priced_via": set(),
                                         "rung_models": set(),
                                         "unpriced_receipts": 0,
                                         "unpriced_saved_tokens": 0})
        t["receipts"] += 1
        if receiptprice.eligible(r, calls):
            res = receiptprice.resolve(r, idx, pol)
            if res is not None:
                usd, rung, model_key = res
                t["saved_usd"] += usd
                t["priced_via"].add(rung)
                t["rung_models"].add((rung, model_key))
            else:  # rung 3 — refused, loudly
                t["priced_via"].add("unpriced")
                t["unpriced_receipts"] += 1
                t["unpriced_saved_tokens"] += int(r.get("saved", 0.0))
                unpriced["receipts"] += 1
                unpriced["tokens"] += int(r.get("saved", 0.0))
                unpriced["tools"].add(r["tool"])
        else:
            t["saved_usd"] += convert.saved_usd(r, calls.get(r.get("call"), {}), pol)
            if r.get("unit", "tokens") == "tokens":
                t["priced_via"].add(receiptprice.LINKED)
        meta = r.get("meta") or {}
        t["cost_usd"] += float(meta.get("tool_cost_usd", 0.0))
        t["added_ms"] += int(meta.get("added_latency_ms", 0))
        # least-trusted receipt tags the row (worst-case provenance, like attrib)
        if _TRUST.get(r.get("method"), 1) < _TRUST.get(t["method"], 1):
            t["method"] = r.get("method")
    for t in tools.values():  # sets → sorted lists: one JSON-safe structure, two renderers
        t["priced_via"] = sorted(t["priced_via"])
        t["rung_models"] = sorted(t["rung_models"])
    unpriced["tools"] = sorted(unpriced["tools"])
    return {"since": since, "tools": tools, "unpriced_receipts": unpriced}


def render_csv(data: dict) -> str:
    """CSV over the same `by_tool()` payload as the text table (one structure, two
    renderers). `method` = the least-trusted receipt behind the row (worst-case
    provenance); `priced_via` = every pricing path the row's token receipts took.
    Column contract in docs/csv-output.md."""
    from cage import csvout
    head = ["tool", "receipts", "saved_usd", "own_cost_usd", "net_usd",
            "added_latency_ms", "method", "priced_via"]
    rows = [[name, t["receipts"], round(t["saved_usd"], 6), round(t["cost_usd"], 6),
             round(t["saved_usd"] - t["cost_usd"], 6), t["added_ms"], t["method"],
             "+".join(t["priced_via"])]
            for name, t in sorted(data["tools"].items(), key=lambda kv: -kv[1]["saved_usd"])]
    return csvout.table(head, rows)


def render_roi(data: dict) -> str:
    if not data["tools"]:
        return "cage: no receipts recorded yet — teach your tools to emit them."
    rows = []
    notes = []
    for name, t in sorted(data["tools"].items(), key=lambda kv: -kv[1]["saved_usd"]):
        net = t["saved_usd"] - t["cost_usd"]
        rows.append([name, render.usd(t["saved_usd"]), render.usd(t["cost_usd"]),
                     render.usd(net), f"{t['added_ms']:,} ms"])
        notes += [receiptprice.footnote(rung, name, key) for rung, key in t["rung_models"]]
    title = "ROI by tool" + (f" (since {data['since']})" if data["since"] else "")
    out = f"{title}\n\n" + render.table(
        ["tool", "saved", "own cost", "net", "added lat"], rows, rights={1, 2, 3, 4})
    if notes:
        out += "\n" + "\n".join(f"  {n}" for n in notes)
    if data.get("unpriced_receipts", {}).get("receipts"):
        block = receiptprice.unpriced_receipts_line(data["unpriced_receipts"])
        out += "\n" + "\n".join(f"  {ln}" for ln in block.splitlines())
    return out
