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


def matrix(root: Path, task: str, pol: dict, scope: str | None = None) -> dict:
    calls = ledger.by_scope(ledger.spend(root), scope)
    rcpts = [r for r in ledger.by_scope(ledger.by_task(ledger.receipts(root), task), scope)
             if r.get("unit", "tokens") == "tokens" and r.get("tool") != "human"]
    # `tool="human"` is a legacy Tier-1 row (the axis was removed in v0.36); it is a
    # different unit of meaning, never a token-saving tool — old ledgers keep the filter.
    tools = attribution.receipts_by_tool(rcpts, list(pol.get("tools", {}).get("order", [])))
    tools = tools[:MAX_MATRIX_TOOLS]
    provider, model = attribution.task_model(calls, task)
    if not model:
        # Ladder consumer (plan §4.5 rider): with no task join, a unanimous
        # `[tools.<tool>] price_at` route across the present tools names the
        # costing model — cells stay modeled; a split route stays unpriced.
        from cage import receiptprice
        routes = receiptprice.routes(pol)
        targets = {routes.get(a["tool"]) for a in tools}
        if len(targets) == 1 and (t := targets.pop()):
            rp, _, rm = t.partition("/")
            if policy_match(pol, rp, rm):
                provider, model = rp, rm
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
           "output_tokens": out_tok, "tools": [a["tool"] for a in tools], "rows": rows,
           "priceable": policy_match(pol, provider, model)}
    return out


def policy_match(pol: dict, provider: str, model: str) -> bool:
    """Whether ``provider/model`` resolves any price row — the cost column's
    availability test (an unpriced model must render `—`-honest absence, never a
    `$0.0000` grid)."""
    from cage import policy
    return bool(model) and policy.price_match(pol, provider, model)[1] != "none"


def _output_cost(pol: dict, provider: str, model: str, out_tok: int) -> float:
    from cage import policy
    return out_tok * policy.price(pol, provider, model)["output"] / TOKENS_PER_MILLION


def render_matrix(data: dict, usd: bool = False) -> str:
    """The permutation grid (spec I7–I8): the **token grid always renders** —
    only the dollar interpretation can be absent. ``usd`` (the `--usd` flag /
    `[display] usd`) adds the cost column when a model prices, else appends the
    one-line unavailability + its runnable fix. The old whole-view refusal is
    gone (plan Phase 2.5)."""
    if not data["tools"]:
        return f"cage: no token-saving receipts for task {data['task']!r}."
    tools, glyph = data["tools"], {True: "✓", False: "✗"}
    show_cost = usd and data.get("priceable", bool(data["model"]))
    head = [*tools, "input tok", *(("cost",) if show_cost else ()), "source"]
    rows = []
    for r in data["rows"]:
        rows.append([*[glyph[r["on"][t]] for t in tools], render.tok(r["input_tok"]),
                     *((render.usd(r["cost_usd"]),) if show_cost else ()), r["source"]])
    rights = {len(tools), len(tools) + 1} if show_cost else {len(tools)}
    body = render.table(head, rows, rights=rights)
    best, worst = data["rows"][-1], data["rows"][0]
    if show_cost:
        foot = (f"full stack vs all-off: ✓ cheaper "
                f"({render.usd(worst['cost_usd'])} → {render.usd(best['cost_usd'])})")
    else:
        foot = (f"full stack vs all-off: ✓ smaller "
                f"({render.tok(worst['input_tok'])} → {render.tok(best['input_tok'])} tok)")
    if usd and not show_cost:
        if data["model"]:
            reason = f"{data['provider']}/{data['model']} has no price row"
            from cage import pricescmd
            fix = pricescmd.fix_line(data["provider"], data["model"])
        else:
            reason = "no priceable model (no task join, no route)"
            fix = f"cage prices route-tool {tools[0]} --to <provider>/<model>"
        foot += (f"\n· cost column unavailable — {reason}\n  fix: {fix}")
    title = f"Counterfactual matrix · task {data['task']}"
    if show_cost:
        title += f" · base model {data['provider']}/{data['model']}"
    return f"{title}\n\n{body}\n\n{foot}"
