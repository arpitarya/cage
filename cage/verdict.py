"""`cage insights verdict <tool>` — the one-line answer, composed from views that already
exist (roadmap P4).

A **pure composer**: every number below is pulled from `attribution` / `roi` /
`regression` / `quality` (or is plain arithmetic over their outputs —
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

**NET-2 — the gross qualifier (net-savings handoff, 2026-08-01).** `roi saved` is
*gross*: it excludes the cost of **using** the tool. graphify is AST-only and declares
`tool_cost_usd = 0`, so the rule above collapsed to `net = gross` and printed a bare
**SAVING** on sessions that measurably cost more
([finding](../work/regression/2026-08-01-finding-saved-is-gross.md)). The exclusion is
**one-directional**, and the refusal rule follows from that asymmetry rather than from
taste:

- the excluded term (cost of use) is **≥ 0**, so a negative net can only get *more*
  negative — **COSTING is still safe to assert** with the term missing;
- a positive net can be wiped out by it — so with no cost-of-use figure, a positive net
  is reported as **`SAVING (GROSS)`** (and a zero as `BREAK-EVEN (GROSS)`), naming what
  is excluded and pointing at `cage insights compare`, the measured alternative.

A distinct verdict rather than INSUFFICIENT DATA because gross is a genuinely computed
number — the defect was the *label*, not the arithmetic, and discarding the figure would
hide the comparison the finding exists to make visible.

**NET-3 — the task-level net.** `netsaved.by_tool` is composed here like every other
input (this module still computes no new statistics). Its net is subtracted into the
headline **only when it covers every receipt in the window** (`complete`); a partial
coverage renders beside gross and leaves the verdict at `(GROSS)` — netting a
window-wide total by a subset's cost would be the same over-claim in the other
direction.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ledger, netsaved, quality, regression, render, roi
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


def compose(root: Path, pol: dict, tool: str, since: str | None = None) -> dict:
    """Pull each existing view once; return the verdict + its tagged inputs."""
    from cage import attribution  # local: avoids importing the whole chain at module load

    rcpts = [r for r in ledger.since(ledger.receipts(root, since=since), since)
             if r.get("tool") == tool]
    d: dict = {"tool": tool, "since": since, "inputs": {}}

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

    # net of use (NET-3) — composed like every other input: `netsaved` owns the
    # attributable-cost rule and its own refusal; verdict only reads the payload.
    d["inputs"]["net_of_use"] = netsaved.by_tool(root, pol, tool, since)

    # forward model (graphify-capture GC5c) — composed, not computed here: the history
    # band and the day-one ceiling are `graphifymodel` views, each already `modeled` and
    # self-refusing. Only for graphify, and the ceiling is available even with zero
    # history (the "worth installing here" number), so it is added before the refusal.
    if tool == "graphify":
        from cage import graphifymodel
        d["forward"] = {"history": graphifymodel.history_band(root, pol),
                        "ceiling": graphifymodel.repo_ceiling(root)}

    # verdict + break-even + $/mo — arithmetic over the inputs above, nothing new
    r = d["inputs"]["roi"]
    if not r["available"] or not r["receipts"]:
        d["verdict"] = "INSUFFICIENT DATA"
        return d
    net = r["net_usd"]
    # NET-2/NET-3: subtract the cost of use only when it covers the whole window;
    # otherwise the verdict wears the (GROSS) qualifier and refuses to net.
    use = d["inputs"]["net_of_use"]
    d["gross_of_use"] = not (use.get("available") and use.get("complete"))
    if not d["gross_of_use"]:
        net = round(net - use["attributable_usd"], 6)
        d["cost_of_use_usd"] = use["attributable_usd"]
    d["verdict"] = "SAVING" if net > 0 else ("COSTING" if net < 0 else "BREAK-EVEN")
    if d["gross_of_use"] and net >= 0:
        # A negative net is safe with the term missing (it can only grow more
        # negative); a non-negative one is not — name the exclusion in the verdict.
        d["verdict"] += " (GROSS)"
    d["net_usd"] = net
    d["method"] = "modeled"  # inherits the receipts' modeled savings — never an invoice
    d["net_per_receipt"] = round(net / r["receipts"], 6)
    span = _span_days(rcpts)
    d["span_days"] = round(span, 2)
    if span >= _MIN_SPAN_DAYS:
        d["net_per_month"] = round(net / span * 30, 4)
    return d


def _gross_warning(tool: str, use: dict) -> str:
    """NET-2 — the exclusion, named at the headline where the claim is made. Says which
    of the two reasons applies (no figure at all vs. a figure that covers only part of
    the window), and points at the measured alternative rather than at nothing."""
    if use.get("available"):
        why = (f"only {use['covered_receipts']}/{use['total_receipts']} receipt(s) "
               "could be joined — too partial to net a window-wide total")
    else:
        why = use.get("reason", "no cost-of-use figure is available")
    return (f"  ⚠ GROSS — the cost of USING {tool} is NOT subtracted (the invoking "
            f"turn,\n    the context it injected): {why}.\n"
            "    The omitted term is ≥ 0, so the true net is at most this figure.\n"
            "    `cage insights compare` measures the on/off difference; "
            "`cage query gross-vs-net`.")


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
        if "forward" in d:  # GC5: the day-one ceiling is useful even with zero history
            head += "\n\n" + _render_forward(d["forward"], history=False)
        return head
    if "net_per_month" in d:
        amount = f"≈ {render.usd(abs(d['net_per_month']))}/mo net"
    else:
        amount = (f"{render.usd(abs(d['net_usd']))} net over its receipts "
                  f"(span {d['span_days']:g}d < {_MIN_SPAN_DAYS}d — too short for a "
                  "monthly projection)")
    lines = [f"VERDICT: {tool} is {d['verdict']} {amount} ({d['method']})"]
    if d.get("gross_of_use"):  # NET-2 — the exclusion, stated at the headline
        lines += ["", _gross_warning(tool, d["inputs"]["net_of_use"])]
    lines += ["", "inputs (each with its own method tag):"]
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
        roi_body = (f"gross {render.usd(r.get('saved_usd', 0.0))} − own cost "
                    f"{render.usd(r.get('cost_usd', 0.0))} = net "
                    f"{render.signed_usd(r.get('net_usd', 0.0))} over "
                    f"{r.get('receipts', 0)} receipt(s)")
        rungs = [v for v in r.get("priced_via", []) if v != "call"]
        if rungs:  # only ladder paths are worth naming; linked pricing is the norm
            roi_body += f" · priced via {'+'.join(rungs)}"
    lines.append(_line("roi", r, roi_body))
    # NET-3 — beside gross, never instead of it; modeled, at its own lower confidence.
    u = i["net_of_use"]
    lines.append(_line("net of use (task-level)", u,
                       (netsaved.render_net(u) + f" · confidence {u['confidence']}")
                       if u.get("available") else ""))
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
    basis = "gross of use" if d.get("gross_of_use") else "net of use"
    lines.append(f"  · break-even: each receipt nets {render.signed_usd(per)} on average "
                 f"({basis}) — "
                 + ("net-positive from the first receipt (derived from roi)" if per > 0
                    else "no receipt volume reaches break-even at current costs "
                         "(derived from roi)"))
    if "forward" in d:  # GC5 — the modeled forward view, clearly apart from measured net
        lines += ["", _render_forward(d["forward"], history=True)]
    lines += ["", "verdict composes existing views only — it computes no new statistics;",
              "a missing input reads INSUFFICIENT DATA, never an approximation."]
    return "\n".join(lines)


def _render_forward(fwd: dict, *, history: bool) -> str:
    """The GC5 forward-model block: the day-one ceiling always, the history band only when
    there is history to show. Composed from `graphifymodel`'s own renderers so the wording
    lives in one place; every line is `modeled`, a band, never a measured total."""
    from cage import graphifymodel
    parts = ["forward model (modeled — a bound/band, never a measured total):",
             graphifymodel.render_repo_ceiling(fwd["ceiling"])]
    if history:
        parts.append(graphifymodel.render_history_band(fwd["history"]))
    return "\n".join(parts)
