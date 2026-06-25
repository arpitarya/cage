"""The counterfactual permutation table (plan §4.4) — what every stack would cost.

For a task whose token-saving tools each shrank one slice of context, enumerate
the 2ⁿ on/off permutations: input tokens = base + Σ(actual if on else raw_alternative),
costed at the task's model. Only the configuration actually recorded is `measured`;
every reconstructed cell is `modeled` (or `estimated` if it leans on an estimated
receipt). No projection masquerades as an invoice (plan §4.1).
"""
from __future__ import annotations

from itertools import product
from pathlib import Path

from cage import attribution, ledger, prices, render
from cage.constants import MAX_MATRIX_TOOLS, TOKENS_PER_MILLION


def _trust_of_off_set(off_tools: list[dict]) -> str:
    """A reconstructed cell is `modeled` at best — never `measured` (it wasn't run).

    A receipt's own `method` only *downgrades* the cell: if any tool it leans on
    knows its alternative by estimate, the whole cell is `estimated` (plan §4.1).
    """
    if not off_tools:
        return "measured"
    if any(a["method"] == "estimated" for a in off_tools):
        return "estimated"
    return "modeled"


def matrix(root: Path, task: str, pol: dict, human: bool = False,
           scope: str | None = None) -> dict:
    calls = ledger.by_scope(ledger.calls(root), scope)
    rcpts = [r for r in ledger.by_scope(ledger.by_task(ledger.receipts(root), task), scope)
             if r.get("unit", "tokens") == "tokens" and r.get("tool") != "human"]
    tools = attribution.receipts_by_tool(rcpts, list(pol.get("tools", {}).get("order", [])))
    tools = tools[:MAX_MATRIX_TOOLS]
    provider, model = attribution.task_model(calls, task)
    runs = [c for c in calls if c.get("task") == task]
    out_tok = max((c.get("tokens_out", 0) for c in runs), default=0)
    actual_in = sum(a["actual"] for a in tools)
    measured_in = max((c.get("tokens_in", 0) for c in runs), default=int(actual_in))
    base = max(0, measured_in - int(actual_in))

    rows = []
    for combo in product((False, True), repeat=len(tools)):
        on_tools = [a for a, on in zip(tools, combo) if on]
        off_tools = [a for a, on in zip(tools, combo) if not on]
        input_tok = base + sum(a["actual"] for a in on_tools) \
            + sum(a["raw_alternative"] for a in off_tools)
        cost = prices.input_cost_usd(pol, provider, model, int(input_tok)) \
            + prices.input_cost_usd(pol, provider, model, 0) \
            + _output_cost(pol, provider, model, out_tok)
        source = "measured" if not off_tools else _trust_of_off_set(off_tools)
        rows.append({"on": {a["tool"]: on for a, on in zip(tools, combo)},
                     "input_tok": int(input_tok), "cost_usd": round(cost, 6),
                     "source": source})
    rows.sort(key=lambda r: r["input_tok"], reverse=True)
    out = {"task": task, "provider": provider, "model": model, "base_tokens": base,
           "output_tokens": out_tok, "tools": [a["tool"] for a in tools], "rows": rows}
    if human:
        out["human"] = _human_anchor(root, task, pol, scope)
    return out


def _human_anchor(root: Path, task: str, pol: dict, scope: str | None = None) -> dict | None:
    """The Tier-1 human alternative for the task: total USD + worst-case method."""
    from cage import human as human_mod
    hr = [r for r in ledger.by_scope(ledger.by_task(ledger.receipts(root), task), scope)
          if r.get("tool") == "human"]
    if not hr:
        return None
    usd, method = 0.0, "measured"
    for r in hr:
        u, m, _ = human_mod.human_alternative_usd(r, pol)
        usd += u
        if m == "estimated":
            method = "estimated"
    return {"usd": round(usd, 6), "method": method}


def _output_cost(pol: dict, provider: str, model: str, out_tok: int) -> float:
    from cage import policy
    return out_tok * policy.price(pol, provider, model)["output"] / TOKENS_PER_MILLION


def render_matrix(data: dict) -> str:
    if not data["tools"]:
        return f"cage: no token-saving receipts for task {data['task']!r}."
    tools, glyph = data["tools"], {True: "✓", False: "✗"}
    anchor = data.get("human")
    head = [*tools, "input tok", "cost", "source"]
    if anchor:
        head += ["vs human $", "vs human %"]
    rows = []
    if anchor:  # Tier-1 anchor first — the most expensive row (no agent at all)
        rows.append([*["—" for _ in tools], "—", render.usd(anchor["usd"]),
                     anchor["method"], "—", "—"])
    for r in data["rows"]:
        row = [*[glyph[r["on"][t]] for t in tools], render.tok(r["input_tok"]),
               render.usd(r["cost_usd"]), r["source"]]
        if anchor:
            row += [render.usd(anchor["usd"] - r["cost_usd"]),
                    render.pct(anchor["usd"] - r["cost_usd"], anchor["usd"])]
        rows.append(row)
    rights = {len(tools), len(tools) + 1}
    if anchor:
        rights |= {len(tools) + 3, len(tools) + 4}
    body = render.table(head, rows, rights=rights)
    best, worst = data["rows"][-1], data["rows"][0]
    delta = render.pct(worst["cost_usd"] - best["cost_usd"], worst["cost_usd"])
    where = f"{data['provider']}/{data['model']}" if data["model"] else "unpriced model"
    foot = (f"  full stack vs all-off: {delta} cheaper "
            f"({render.usd(worst['cost_usd'])} → {render.usd(best['cost_usd'])})")
    if anchor:
        foot += (f"\n  human anchor: {render.usd(anchor['usd'])} ({anchor['method']}) — "
                 f"full stack saves {render.pct(anchor['usd'] - best['cost_usd'], anchor['usd'])} vs a person")
    return (f"Counterfactual matrix · task {data['task']!r} · {where}\n"
            f"  base {render.tok(data['base_tokens'])} tok + output "
            f"{render.tok(data['output_tokens'])} tok held constant\n\n{body}\n\n{foot}")
