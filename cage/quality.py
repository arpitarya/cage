"""`cage human outcome` / `cage human quality` — quality-adjusted cost (plan §8.2).

Cost is dishonest alone — you can "save" by degrading answers and paying for the
human redo. Pair every task with the `quality.signal` (did it succeed without a
redo?) and report **cost per *successful* task** — the metric that stops false
economies. Outcomes live in `.cage/outcomes.json` (task → ok | redo).
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import ledger, paths, policy, prices, render


def _file(root: Path) -> Path:
    return paths.Footprint(root).base / "outcomes.json"


def _load(root: Path) -> dict:
    f = _file(root)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def record_outcome(root: Path, task: str, ok: bool) -> None:
    data = _load(root)
    data[task] = "ok" if ok else "redo"
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def summarize(root: Path, pol: dict | None = None) -> dict:
    # Repriced from tokens × policy at derive time, like report/budget — the stored
    # est_cost_usd is 0.0 for transcript-sourced calls. Failed load ⇒ stored figures.
    if pol is None:
        try:
            pol = policy.load(paths.Footprint(root).policy)
        except Exception:  # noqa: BLE001 — library default; CLI passes a checked pol
            pol = {}
    outcomes = _load(root)
    cost_by_task: dict[str, float] = {}
    for c in ledger.calls(root):
        t = c.get("task")
        if t:
            cost_by_task[t] = cost_by_task.get(t, 0.0) + prices.call_usd(pol, c)
    total = sum(cost_by_task.values())
    tasks = len(cost_by_task)
    ok = sum(1 for t in cost_by_task if outcomes.get(t) == "ok")
    redo = sum(1 for t in cost_by_task if outcomes.get(t) == "redo")
    return {"total_usd": round(total, 6), "tasks": tasks, "ok": ok, "redo": redo,
            "per_task": round(total / tasks, 6) if tasks else 0.0,
            "per_success": round(total / ok, 6) if ok else None}


def render_quality(s: dict) -> str:
    per_succ = render.usd(s["per_success"]) if s["per_success"] is not None else "— (no ok tasks)"
    rows = [
        ["tasks (with cost)", str(s["tasks"]), ""],
        ["succeeded / redone", f"{s['ok']} / {s['redo']}", ""],
        ["cost / task", render.usd(s["per_task"]), ""],
        ["cost / successful task", per_succ, "← the honest metric"],
    ]
    return "Quality-adjusted cost\n\n" + render.table(["metric", "value", ""], rows, rights={1})
