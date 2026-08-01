"""Gross vs **net** savings — what a tool avoided, minus what it cost to *use*
(net-savings handoff, [finding](../docs/regression/2026-08-01-finding-saved-is-gross.md)).

Every `saved` in the ledger is a **per-query counterfactual**: *the files this answer
cites would have cost N tokens; the answer cost M.* It does not subtract the cost of
**using** the tool — the turn that invoked it, the round-trip, the context a hook
injected. So cage can truthfully print "27,658 tokens saved" for a session that cost
more than its unassisted twin. Nothing is miscomputed; the label is narrower than it
reads. This module owns both halves of the fix:

- **the vocabulary** (`GROSS_NOTE`) — the ONE phrasing every view prints for that
  exclusion, so report/attrib/roi/verdict cannot drift apart;
- **the task-level net** (:func:`by_tool`) — `net = gross − attributable cost of use`.

**The attributable-cost rule (the one decision this module makes).** A savings receipt
is *call-less* — the graphify/fux shims file a `task` but never a `call` (that is why
`receiptprice`'s ladder exists), so per-query netting is **impossible** and is not
attempted. Instead, per task:

    attributable = Σ prices.call_usd(c) for the DISTINCT calls joined to the receipt's
                   task whose `ts` lies within ±NET_ATTRIB_WINDOW_S of ANY of that
                   tool's receipts on that task
    net          = gross − attributable

Why the window and not the other two candidates:

- *the whole task* would charge the tool for every turn of work it merely assisted —
  net would be hugely negative for any real task and would measure task size, not tool
  cost;
- *only turns containing a tool-use block* is the sharpest rule but is **not
  computable**: a ledger call carries tokens, model and session — nothing marks it as
  carrying a tool-use block. Building it means stamping `call` at capture time, a
  different change (handoff §"Hard constraint").

The window is therefore the honest computable middle, and it is a **lower bound**: a
re-read provoked by a thin answer, three turns later, is not counted.

**Coverage refuses rather than approximates.** A task whose receipts join **no**
in-window call is UNCOVERED — its net is unavailable, never reported as equal to gross.
That is structural: since `attributable ≥ 1 call ⇒ attributable > 0` whenever the model
is priced, `net == gross` cannot be produced by a failed join.

**Method law.** Gross is `modeled` (a counterfactual). The subtrahend is `measured`
(recorded tokens repriced at derive time through the same `prices.call_usd` that
`report`/`budget` use). The result is `modeled` at `NET_SAVED_CONFIDENCE` — its own,
lower confidence, because it stacks a time-window join on top of gross's
counterfactual. Net is **never** `measured`.

Determinism: same ledger + same policy ⇒ same numbers. No clock is read; every
comparison is between two recorded row timestamps.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import convert, ledger, prices, receiptprice
from cage.constants import NET_ATTRIB_WINDOW_S, NET_SAVED_CONFIDENCE

#: The ONE phrasing of the gross exclusion. Every view that prints a `saved`/`gross`
#: figure prints this same line — a relabel that lives in one place cannot drift.
GROSS_NOTE = (
    "· saved is GROSS — avoided read cost; it excludes the cost of USING the tool\n"
    "  (the invoking turn, the injected context). `cage query gross-vs-net`")


def _epoch(ts: str) -> float | None:
    """A row timestamp as seconds, or ``None`` when unparseable. A naive stamp is read
    as UTC so a naive/aware mix can never silently shift a window by the local offset."""
    try:
        d = _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=_dt.timezone.utc)
    return d.timestamp()


def _gross_usd(rcpts: list[dict], calls_by_id: dict, idx: dict, pol: dict) -> float:
    """The gross USD of a receipt set — the SAME two routes `roi`/`report` use (linked
    call via `convert.saved_usd`, call-less via the `receiptprice` ladder). A rung-3
    refusal contributes $0 here and is counted by the caller, never invented."""
    total = 0.0
    for r in rcpts:
        if receiptprice.eligible(r, calls_by_id):
            res = receiptprice.resolve(r, idx, pol)
            total += res[0] if res is not None else 0.0
        else:
            total += convert.saved_usd(r, calls_by_id.get(r.get("call"), {}), pol)
    return total


def by_tool(root: Path, pol: dict, tool: str, since: str | None = None, *,
            calls: list[dict] | None = None,
            receipts: list[dict] | None = None) -> dict:
    """Task-level gross/net for ``tool`` over the window.

    ``calls``/``receipts`` let a caller that already holds the ledger thread it down
    (one read per view, never per tool). Returns a payload that always states its own
    coverage: ``complete`` is True only when every one of the tool's in-window receipts
    landed on a covered task — the gate `verdict` uses before it will subtract at all.
    """
    all_calls = ledger.calls(root) if calls is None else calls
    all_receipts = ledger.receipts(root) if receipts is None else receipts
    rows = [r for r in ledger.since(all_receipts, since)
            if r.get("tool") == tool and r.get("unit") != "minutes"]
    base = {"tool": tool, "since": since, "window_s": NET_ATTRIB_WINDOW_S,
            "method": "modeled", "confidence": NET_SAVED_CONFIDENCE,
            "total_receipts": len(rows), "covered_receipts": 0, "tasks": [],
            "gross_usd": 0.0, "attributable_usd": 0.0, "net_usd": 0.0,
            "attributable_calls": 0, "complete": False}
    if not rows:
        return {**base, "available": False,
                "reason": f"no {tool} receipts in this window"}


    from cage import taskgroup
    joined = taskgroup.join_rows(all_calls, all_receipts)
    calls_by_id = {c.get("id"): c for c in all_calls}
    idx = receiptprice.build(all_calls, all_receipts)

    by_task: dict[str, list[dict]] = {}
    taskless = 0
    for r in rows:
        if r.get("task"):
            by_task.setdefault(r["task"], []).append(r)
        else:
            taskless += 1

    out: list[dict] = []
    for tid in sorted(by_task):
        group = by_task[tid]
        stamps = [e for e in (_epoch(r.get("ts", "")) for r in group) if e is not None]
        task_calls = joined.get(tid, {}).get("calls", [])
        hit: dict[str, dict] = {}
        for c in task_calls:
            ce = _epoch(c.get("ts", ""))
            if ce is None:
                continue
            if any(abs(ce - s) <= NET_ATTRIB_WINDOW_S for s in stamps):
                hit[c.get("id") or f"_{len(hit)}"] = c  # union: adjacency, never a count
        gross = _gross_usd(group, calls_by_id, idx, pol)
        gross_tok = sum(int(r.get("saved", 0.0)) for r in group
                        if r.get("unit", "tokens") == "tokens")
        if not hit:
            # UNCOVERED — no in-window call to charge. Refuse; never net = gross.
            out.append({"task": tid, "covered": False, "receipts": len(group),
                        "gross_usd": round(gross, 6), "gross_tokens": gross_tok,
                        "attributable_usd": 0.0, "attributable_calls": 0,
                        "net_usd": None,
                        "reason": ("no task-linked call within "
                                   f"±{NET_ATTRIB_WINDOW_S}s of a receipt"
                                   if task_calls else "no calls joined to this task")})
            continue
        cost = round(sum(prices.call_usd(pol, c) for c in hit.values()), 6)
        out.append({"task": tid, "covered": True, "receipts": len(group),
                    "gross_usd": round(gross, 6), "gross_tokens": gross_tok,
                    "attributable_usd": cost, "attributable_calls": len(hit),
                    "net_usd": round(gross - cost, 6), "reason": ""})

    covered = [t for t in out if t["covered"]]
    d = {**base, "tasks": out,
         "covered_receipts": sum(t["receipts"] for t in covered),
         "gross_usd": round(sum(t["gross_usd"] for t in covered), 6),
         "attributable_usd": round(sum(t["attributable_usd"] for t in covered), 6),
         "attributable_calls": sum(t["attributable_calls"] for t in covered),
         "covered_tasks": len(covered), "total_tasks": len(out),
         "taskless_receipts": taskless}
    d["net_usd"] = round(d["gross_usd"] - d["attributable_usd"], 6)
    d["complete"] = bool(covered) and d["covered_receipts"] == len(rows)
    if not covered:
        # A bare clause, not a sentence: every caller frames it differently, and a
        # doubled "the cost of using X could not be joined — the cost of using X …"
        # is exactly the kind of restated prose the output law forbids.
        return {**d, "available": False,
                "reason": (f"{tool}'s receipts carry no task" if taskless == len(rows)
                           else "no task-linked call fell within "
                                f"±{NET_ATTRIB_WINDOW_S}s of a receipt")}
    return {**d, "available": True, "reason": ""}


def render_net(d: dict) -> str:
    """The one-line net-of-use body for a `verdict` input line. Never renders a bare
    number: it always carries the coverage it was computed over, because a net over
    2 of 9 receipts and a net over all 9 are different claims."""
    from cage import render
    cov = (f"{d['covered_receipts']}/{d['total_receipts']} receipt(s) on "
           f"{d.get('covered_tasks', 0)} task(s), {d['attributable_calls']} call(s) "
           f"within ±{d['window_s']}s")
    return (f"gross {render.usd(d['gross_usd'])} − cost of use "
            f"{render.usd(d['attributable_usd'])} = net "
            f"{render.signed_usd(d['net_usd'])}  [{cov}]"
            + ("" if d.get("complete") else " — PARTIAL coverage"))
