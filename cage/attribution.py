"""Marginal attribution by fixed pipeline order (plan §4.2) — the differentiator.

Each receipt already reports its *marginal* saving given the tools upstream of it
in the canonical order, so the sum of marginals equals the total with no overlap.
This module orders a task's receipts by `policy.tools.order` and tags each row's
`method`. Savings are **token-denominated** — the USD conversion and the call-less
receipt pricing ladder went with the money subsystem (USAGE-ONLY, ADR 0011); the
marginal arithmetic they decorated is unchanged.

**Every figure here is GROSS** (`savings.GROSS_NOTE`): the avoided read cost, with the
cost of *using* each tool excluded. Marginality is about overlap *between* tools, not
about a tool's own cost of use — a marginal saving can be large and the tool still make
the task more expensive; cage reports gross only and says so (`savings.GROSS_NOTE`).
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, render
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

    `pol` is still read for `[tools] order` — the pipeline order marginality depends
    on — but no longer for prices."""
    all_calls, all_receipts = ledger.join_table(root), ledger.receipts(root)
    if team:
        from cage import ledgersync
        t = ledgersync.read_team(root)
        if t is not None:
            all_calls, all_receipts = t["calls"], t["receipts"]
    rcpts = [r for r in ledger.by_scope(ledger.by_task(all_receipts, task), scope)
             if r.get("tool") != "human" and r.get("unit") != "minutes"]
    rows = receipts_by_tool(rcpts, list(pol.get("tools", {}).get("order", [])))
    provider, model = task_model(ledger.by_scope(all_calls, scope), task)
    steps, tot_tok = [], 0.0
    for a in rows:
        # A non-token unit (`ms`/`gco2`) contributes no tokens and is still listed with
        # its own unit — cage converts nothing between units, in either direction.
        saved_tok = a["saved"] if a["unit"] == "tokens" else 0.0
        tot_tok += saved_tok
        steps.append({"tool": a["tool"], "unit": a["unit"], "saved_tokens": saved_tok,
                      "method": a["method"], "confidence": a["confidence"]})
    return {"task": task, "provider": provider, "model": model, "steps": steps,
            "total_saved_tokens": tot_tok}


def render_csv(data: dict) -> str:
    """CSV over the same `attribute()` payload as the text table (one structure,
    two renderers). Per-step method + confidence are columns — the worst-case
    provenance survives into the spreadsheet. Column contract: `csvout.py` +
    `cage query csv-output` (CLAUDE.md, CSV output / plan §3.9)."""
    from cage import csvout
    head = ["tool", "unit", "gross_saved_tokens", "method", "confidence"]
    rows = [[s["tool"], s["unit"], s["saved_tokens"], s["method"], s["confidence"]]
            for s in data["steps"]]
    if data["steps"]:
        rows.append(["TOTAL", "tokens", data["total_saved_tokens"], "", ""])
    return csvout.table(head, rows)


def render_attrib(data: dict) -> str:
    from cage import savings
    if not data["steps"]:
        return f"cage: no receipts for task {data['task']!r}."
    rows = [[s["tool"], s["unit"], render.tok(s["saved_tokens"]), s["method"]]
            for s in data["steps"]]
    rows.append(["TOTAL", "tokens", render.tok(data["total_saved_tokens"]), ""])
    body = render.table(["tool", "unit", "gross tok", "method"], rows, rights={2})
    where = f"{data['provider']}/{data['model']}" if data["model"] else "model unknown"
    out = f"Marginal attribution · task {data['task']!r} · {where}\n\n{body}"
    return out + "\n" + savings.GROSS_NOTE  # the gross exclusion, one shared phrasing
