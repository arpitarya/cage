"""`cage insights verdict <tool>` — the one-line answer, composed from views that already
exist (roadmap P4).

A **pure composer**: every number below is pulled from `attribution` / `roi` /
`trend` / `regression` / `quality` (or is plain arithmetic over their outputs —
the break-even and per-month scaling). It computes **no new statistics**; if an
input is unavailable it says INSUFFICIENT DATA for that line — and for the
verdict itself when the core input (the tool's receipts, via roi) is missing —
never an approximation. Every input renders with its own method tag; the
headline net is tagged **modeled** because it inherits the receipts' modeled
savings (an invoice-grade verdict would need a controlled experiment — see
`cage insights compare` for the observational version).

Verdict rule (deterministic): net = roi saved − roi own-cost over the window.
net > 0 ⇒ SAVING · net < 0 ⇒ COSTING · no receipts ⇒ INSUFFICIENT DATA. The
≈$/month figure scales net by the tool's receipt time-span (row timestamps, no
clock) and renders only when the span covers ≥ 7 days — a projection from less
is noise, so the line says so instead.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import attention, ledger, prices, quality, regression, render, roi, trend
from cage.constants import METHOD_TRUST

_MIN_SPAN_DAYS = 7  # below this the $/mo projection line refuses (noise, not signal)


def _worst_method(rcpts: list[dict]) -> str:
    """The least-trusted method among the tool's receipts — the same honest
    worst-case rule attribution uses per row (a lookup, not a statistic)."""
    methods = [r.get("method", "estimated") for r in rcpts]
    return min(methods, key=lambda m: METHOD_TRUST.get(m, 0)) if methods else ""


def _span_days(rcpts: list[dict]) -> float:
    ts = sorted(r["ts"] for r in rcpts if r.get("ts"))
    if len(ts) < 2:
        return 0.0
    try:
        lo = _dt.datetime.fromisoformat(ts[0].replace("Z", "+00:00"))
        hi = _dt.datetime.fromisoformat(ts[-1].replace("Z", "+00:00"))
        return max(0.0, (hi - lo).total_seconds() / 86_400)
    except ValueError:
        return 0.0


def compose(root: Path, pol: dict, tool: str, since: str | None = None,
            agent_only: bool = False) -> dict:
    """Pull each existing view once; return the verdict + its tagged inputs.

    Unless ``agent_only``, a ``total_cost`` block (plan §4.10) adds the
    ledger-wide window total: agent $ + human attention minutes × rate — pulled
    from `attention.py` (attested beats derived per task, never summed), tagged
    with the human component's method. Composition only, no new statistics."""
    from cage import attribution  # local: avoids importing the whole chain at module load

    rcpts = [r for r in ledger.since(ledger.receipts(root, since=since), since)
             if r.get("tool") == tool]
    d: dict = {"tool": tool, "since": since, "inputs": {}}
    if not agent_only:
        window = ledger.since(ledger.calls(root, since=since), since)
        agent_usd = sum(prices.call_usd(pol, c) for c in window)
        d["total_cost"] = attention.total_cost(
            agent_usd, attention.resolve(root, pol, since=since), pol)

    # roi — the core input: saved vs own cost (net decides the verdict)
    t = roi.by_tool(root, pol, since)["tools"].get(tool)
    if t:
        net = round(t["saved_usd"] - t["cost_usd"], 6)
        d["inputs"]["roi"] = {"available": True, "saved_usd": round(t["saved_usd"], 6),
                              "cost_usd": round(t["cost_usd"], 6), "net_usd": net,
                              "receipts": t["receipts"], "added_ms": t["added_ms"],
                              "method": _worst_method(rcpts),
                              "priced_via": t.get("priced_via", [])}
    else:
        d["inputs"]["roi"] = {"available": False, "reason": "no receipts for this tool"}

    # attribution — the tool's marginal saving on its most recent task
    latest = max((r for r in rcpts if r.get("task")), key=lambda r: r.get("ts", ""),
                 default=None)
    step = None
    if latest:
        a = attribution.attribute(root, latest["task"], pol)
        step = next((s for s in a["steps"] if s["tool"] == tool), None)
    if step:
        d["inputs"]["attribution"] = {"available": True, "task": latest["task"],
                                      "saved_tokens": step["saved_tokens"],
                                      "saved_usd": step["saved_usd"],
                                      "method": step["method"],
                                      "priced_via": step.get("priced_via", ""),
                                      "priced_model": step.get("priced_model", "")}
    else:
        d["inputs"]["attribution"] = {"available": False,
                                      "reason": "no task-linked receipt to attribute"}

    # trend — ledger-wide agent-vs-human direction (context, clearly labelled)
    buckets = trend.series(root, pol, by="week", since=since)["buckets"]
    if len(buckets) >= 2:
        keys = sorted(buckets)
        prev, last = buckets[keys[-2]]["saved_usd"], buckets[keys[-1]]["saved_usd"]
        d["inputs"]["trend"] = {"available": True, "direction":
                                "rising" if last > prev else ("falling" if last < prev
                                                              else "flat"),
                                "last": last, "prev": prev, "method": "estimated"}
    else:
        d["inputs"]["trend"] = {"available": False,
                                "reason": "fewer than 2 weekly buckets on the human axis"}

    # regression — ledger-wide cost-per-call drift
    rg = regression.detect(root, pol=pol)
    if rg["base_n"] and rg["recent_n"]:
        d["inputs"]["regression"] = {"available": True, "drift": rg["drift"],
                                     "regressed": rg["regressed"], "method": "measured"}
    else:
        d["inputs"]["regression"] = {"available": False,
                                     "reason": "not enough history on both sides of the window"}

    # quality — redo rate over recorded outcomes
    q = quality.summarize(root, pol=pol)
    if q["ok"] or q["redo"]:
        d["inputs"]["quality"] = {"available": True, "ok": q["ok"], "redo": q["redo"],
                                  "method": "measured"}
    else:
        d["inputs"]["quality"] = {"available": False, "reason": "no task outcomes recorded"}

    # verdict + break-even + $/mo — arithmetic over the inputs above, nothing new
    r = d["inputs"]["roi"]
    if not r["available"] or not r["receipts"]:
        d["verdict"] = "INSUFFICIENT DATA"
        return d
    net = r["net_usd"]
    d["verdict"] = "SAVING" if net > 0 else ("COSTING" if net < 0 else "BREAK-EVEN")
    d["net_usd"] = net
    d["method"] = "modeled"  # inherits the receipts' modeled savings — never an invoice
    d["net_per_receipt"] = round(net / r["receipts"], 6)
    span = _span_days(rcpts)
    d["span_days"] = round(span, 2)
    if span >= _MIN_SPAN_DAYS:
        d["net_per_month"] = round(net / span * 30, 4)
    return d


def _line(name: str, i: dict, body: str) -> str:
    if not i["available"]:
        return f"  · {name}: INSUFFICIENT DATA — {i['reason']}"
    return f"  · {name}: {body} ({i['method']})"


def render_verdict(d: dict) -> str:
    tool = d["tool"]
    if d["verdict"] == "INSUFFICIENT DATA":
        head = (f"VERDICT: INSUFFICIENT DATA — no receipts recorded for {tool!r}"
                + (f" since {d['since']}" if d["since"] else "")
                + ".\n\nA verdict composes recorded receipts; teach the tool to emit them"
                  " (`cage query receipts`), then re-run.")
        if "total_cost" in d:  # plan §4.10 — suppressed by --agent-only
            head += "\n\n" + attention.render_total_cost(d["total_cost"])
        return head
    if "net_per_month" in d:
        amount = f"≈ {render.usd(abs(d['net_per_month']))}/mo net"
    else:
        amount = (f"{render.usd(abs(d['net_usd']))} net over its receipts "
                  f"(span {d['span_days']:g}d < {_MIN_SPAN_DAYS}d — too short for a "
                  "monthly projection)")
    lines = [f"VERDICT: {tool} is {d['verdict']} {amount} ({d['method']})", "",
             "inputs (each with its own method tag):"]
    i = d["inputs"]
    a = i["attribution"]
    attrib_body = ""
    if a["available"]:
        attrib_body = (f"task {a.get('task', '')!r}: "
                       f"{a.get('saved_tokens', 0):,.0f} tok · "
                       f"{render.usd(a.get('saved_usd', 0.0))}")
        if a.get("priced_via"):  # the ladder rung that priced it, named (plan §4.5)
            attrib_body += f" · priced via {a['priced_via']}"
            if a.get("priced_model"):
                attrib_body += f" ({a['priced_model']})"
    lines.append(_line("marginal saving (attrib)", a, attrib_body))
    r = i["roi"]
    roi_body = ""
    if r["available"]:
        roi_body = (f"saved {render.usd(r.get('saved_usd', 0.0))} − own cost "
                    f"{render.usd(r.get('cost_usd', 0.0))} = net "
                    f"{render.signed_usd(r.get('net_usd', 0.0))} over "
                    f"{r.get('receipts', 0)} receipt(s)")
        rungs = [v for v in r.get("priced_via", []) if v != "call"]
        if rungs:  # only ladder paths are worth naming; linked pricing is the norm
            roi_body += f" · priced via {'+'.join(rungs)}"
    lines.append(_line("roi", r, roi_body))
    t = i["trend"]
    lines.append(_line("trend (agent-vs-human, ledger-wide)", t,
                       f"saved $ {t.get('direction', '')} week-over-week"
                       if t["available"] else ""))
    g = i["regression"]
    lines.append(_line("cost drift (regression)", g,
                       (f"⚠ cost/call up {g.get('drift', 0) * 100:.0f}%" if g.get("regressed")
                        else f"stable ({g.get('drift', 0) * 100:+.0f}%)")
                       if g["available"] else ""))
    q = i["quality"]
    lines.append(_line("redo-rate (quality)", q,
                       f"{q.get('redo', 0)}/{q.get('ok', 0) + q.get('redo', 0)} "
                       "tasks redone" if q["available"] else ""))
    per = d["net_per_receipt"]
    lines.append(f"  · break-even: each receipt nets {render.signed_usd(per)} on average — "
                 + ("net-positive from the first receipt (derived from roi)" if per > 0
                    else "no receipt volume reaches break-even at current costs "
                         "(derived from roi)"))
    if "total_cost" in d:  # plan §4.10 — suppressed by --agent-only
        lines += ["", attention.render_total_cost(d["total_cost"])]
    lines += ["", "verdict composes existing views only — it computes no new statistics;",
              "a missing input reads INSUFFICIENT DATA, never an approximation."]
    return "\n".join(lines)
