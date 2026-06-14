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

_MAX_TOOLS = 12  # 2^12 = 4096 rows — a generous ceiling on a single task's stack


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


def matrix(root: Path, task: str, pol: dict) -> dict:
    calls = ledger.calls(root)
    rcpts = [r for r in ledger.by_task(ledger.receipts(root), task)
             if r.get("unit", "tokens") == "tokens"]
    tools = attribution.receipts_by_tool(rcpts, list(pol.get("tools", {}).get("order", [])))
    tools = tools[:_MAX_TOOLS]
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
    return {"task": task, "provider": provider, "model": model, "base_tokens": base,
            "output_tokens": out_tok, "tools": [a["tool"] for a in tools], "rows": rows}


def _output_cost(pol: dict, provider: str, model: str, out_tok: int) -> float:
    from cage import policy
    return out_tok * policy.price(pol, provider, model)["output"] / 1_000_000


def render_matrix(data: dict) -> str:
    if not data["tools"]:
        return f"cage: no token-saving receipts for task {data['task']!r}."
    tools, glyph = data["tools"], {True: "✓", False: "✗"}
    rows = [[*[glyph[r["on"][t]] for t in tools], render.tok(r["input_tok"]),
             render.usd(r["cost_usd"]), r["source"]] for r in data["rows"]]
    head = [*tools, "input tok", "cost", "source"]
    rights = {len(tools), len(tools) + 1}
    body = render.table(head, rows, rights=rights)
    best, worst = data["rows"][-1], data["rows"][0]
    delta = render.pct(worst["cost_usd"] - best["cost_usd"], worst["cost_usd"])
    where = f"{data['provider']}/{data['model']}" if data["model"] else "unpriced model"
    return (f"Counterfactual matrix · task {data['task']!r} · {where}\n"
            f"  base {render.tok(data['base_tokens'])} tok + output "
            f"{render.tok(data['output_tokens'])} tok held constant\n\n{body}\n\n"
            f"  full stack vs all-off: {delta} cheaper "
            f"({render.usd(worst['cost_usd'])} → {render.usd(best['cost_usd'])})")
