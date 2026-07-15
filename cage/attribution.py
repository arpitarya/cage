"""Marginal attribution by fixed pipeline order (plan §4.2) — the differentiator.

Each receipt already reports its *marginal* saving given the tools upstream of it
in the canonical order, so the sum of marginals equals the total with no overlap.
This module orders a task's receipts by `policy.tools.order`, converts token
savings to USD at the task's model price, and tags each row's `method`.
"""
from __future__ import annotations

from pathlib import Path

from cage import convert, ledger, render
from cage.constants import METHOD_TRUST as _TRUST


def task_model(calls: list[dict], task: str) -> tuple[str, str]:
    """The (provider, model) the task actually ran on — its last recorded call."""
    runs = [c for c in calls if c.get("task") == task]
    if not runs:
        return ("", "")
    last = max(runs, key=lambda c: c.get("ts", ""))
    return (last.get("provider", ""), last.get("model", ""))


def receipts_by_tool(receipts: list[dict], order: list[str]) -> list[dict]:
    """Aggregate a task's receipts per tool, ordered by the canonical pipeline.

    Multiple receipts from one tool sum; the row carries the least-trusted method
    and lowest confidence among them (honest worst-case provenance).
    """
    agg: dict[str, dict] = {}
    for r in receipts:
        a = agg.setdefault(r["tool"], {"tool": r["tool"], "unit": r.get("unit", "tokens"),
                                       "raw_alternative": 0.0, "actual": 0.0, "saved": 0.0,
                                       "method": "measured", "confidence": 1.0})
        a["raw_alternative"] += r.get("raw_alternative", 0.0)
        a["actual"] += r.get("actual", 0.0)
        a["saved"] += r.get("saved", 0.0)
        if _TRUST.get(r.get("method"), 1) < _TRUST.get(a["method"], 1):
            a["method"] = r["method"]
        a["confidence"] = min(a["confidence"], r.get("confidence", 1.0))
    rank = {t: i for i, t in enumerate(order)}
    return sorted(agg.values(), key=lambda a: (rank.get(a["tool"], len(order)), a["tool"]))


def attribute(root: Path, task: str, pol: dict, scope: str | None = None,
              team: bool = False) -> dict:
    """Per-tool marginal savings for one task, in tokens and USD (the §4.2 table).

    With ``scope`` set, only rows in that top-level dir count (plan §3.6.2); ``None`` is
    the unfiltered, byte-identical default. With ``team``, rows come from the merged
    `refs/notes/cage-ledger` ref, falling back to local when it's empty (§3.6.3).

    A tool's call-less token receipts (no resolvable call row) price via the
    resolution ladder (`receiptprice`, plan §4.5) instead of the task model; the
    step's ``priced_via``/``priced_model`` carry the rung, footnoted by the render.
    Receipts with a resolvable call keep the task-model path, byte-identical."""
    from cage import receiptprice
    all_calls, all_receipts = ledger.calls(root), ledger.receipts(root)
    if team:
        from cage import ledgersync
        t = ledgersync.read_team(root)
        if t is not None:
            all_calls, all_receipts = t["calls"], t["receipts"]
    rcpts = [r for r in ledger.by_scope(ledger.by_task(all_receipts, task), scope)
             if r.get("tool") != "human"]
    rows = receipts_by_tool(rcpts, list(pol.get("tools", {}).get("order", [])))
    calls_by_id = {c.get("id"): c for c in all_calls}
    idx = receiptprice.build(all_calls, all_receipts)  # once per view (§4.5)
    ladder_saved = {}  # tool → summed saved tokens of its ladder-eligible receipts
    for r in rcpts:
        if receiptprice.eligible(r, calls_by_id):
            ladder_saved[r["tool"]] = ladder_saved.get(r["tool"], 0.0) + r.get("saved", 0.0)
    provider, model = task_model(ledger.by_scope(all_calls, scope), task)
    call = {"provider": provider, "model": model}
    steps, tot_tok, tot_usd = [], 0.0, 0.0
    for a in rows:
        saved_tok = a["saved"] if a["unit"] == "tokens" else 0.0
        on_ladder = ladder_saved.get(a["tool"], 0.0)
        saved_usd = convert.saved_usd({**a, "saved": a["saved"] - on_ladder}, call, pol)
        priced_via, priced_model = "", ""
        if on_ladder:
            res = receiptprice.resolve({"tool": a["tool"], "task": task,
                                        "saved": on_ladder}, idx, pol)
            if res is not None:
                saved_usd += res[0]
                priced_via, priced_model = res[1], res[2]
            else:
                priced_via = "unpriced"  # rung 3 — the refused portion stays $0, visibly
        tot_tok += saved_tok
        tot_usd += saved_usd
        steps.append({"tool": a["tool"], "unit": a["unit"], "saved_tokens": saved_tok,
                      "saved_usd": round(saved_usd, 6), "method": a["method"],
                      "confidence": a["confidence"], "priced_via": priced_via,
                      "priced_model": priced_model})
    return {"task": task, "provider": provider, "model": model, "steps": steps,
            "total_saved_tokens": tot_tok, "total_saved_usd": round(tot_usd, 6)}


def render_csv(data: dict) -> str:
    """CSV over the same `attribute()` payload as the text table (one structure,
    two renderers). Per-step method + confidence are columns — the worst-case
    provenance survives into the spreadsheet. Column contract in docs/csv-output.md."""
    from cage import csvout
    head = ["tool", "saved_tokens", "saved_usd", "method", "confidence", "priced_via"]
    rows = [[s["tool"], s["saved_tokens"], s["saved_usd"], s["method"], s["confidence"],
             s.get("priced_via", "")]
            for s in data["steps"]]
    if data["steps"]:
        rows.append(["TOTAL", data["total_saved_tokens"], data["total_saved_usd"],
                     "", "", ""])
    return csvout.table(head, rows)


def render_attrib(data: dict) -> str:
    from cage import receiptprice
    from cage.display import DASH
    if not data["steps"]:
        return f"cage: no receipts for task {data['task']!r}."
    # `—` is the only rendering of "couldn't price" (plan Phase 1.1): a rung-3
    # refusal keeps its measured tokens but never wears a $0.0000.
    rows = [[s["tool"], render.tok(s["saved_tokens"]),
             DASH if s.get("priced_via") == "unpriced" else render.usd(s["saved_usd"]),
             s["method"]] for s in data["steps"]]
    total_usd = render.usd(data["total_saved_usd"])
    if any(s.get("priced_via") == "unpriced" for s in data["steps"]):
        total_usd += " (+ unpriced)"
    rows.append(["TOTAL", render.tok(data["total_saved_tokens"]), total_usd, ""])
    body = render.table(["tool", "saved tok", "saved $", "method"], rows, rights={1, 2})
    where = f"{data['provider']}/{data['model']}" if data["model"] else "unpriced model"
    out = f"Marginal attribution · task {data['task']!r} · {where}\n\n{body}"
    notes = [receiptprice.footnote(s["priced_via"], s["tool"], s["priced_model"])
             for s in data["steps"]
             if s.get("priced_via") in (receiptprice.PRICE_AT, receiptprice.TASK_MODEL)]
    if notes:
        out += "\n" + "\n".join(f"  {n}" for n in notes)
    return out
