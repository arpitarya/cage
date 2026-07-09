"""`cage human` — Tier-1 agent-vs-human rollup (design §4.1, §5b.1).

Joins human receipts (the avoided-labor alternative, priced by `human.py`) with the
agent's measured call cost + active time per task. Reports saved **$ and hours** as
co-equal metrics; saved-time can go negative when the agent ran longer than the human
estimate (§5b.1 honesty check). Quality-honest: a redone task is not a saving.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import human, ledger, policy, prices, render, tasks


def _active_minutes(runs: list[dict]) -> float:
    """Agent supervision time per task: call-span wall-clock, floored by Σ latency."""
    lat = sum(c.get("latency_ms", 0) for c in runs) / 60000.0
    stamps = sorted(t for c in runs if (t := _parse(c.get("ts"))))
    wall = (stamps[-1] - stamps[0]).total_seconds() / 60.0 if len(stamps) > 1 else 0.0
    return max(wall, lat)


def _parse(ts):
    try:
        return _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def rollup(root: Path, pol: dict, since: str | None = None,
           agent: str | None = None, task: str | None = None) -> dict:
    calls = ledger.calls(root)
    rcpts = [r for r in ledger.since(ledger.receipts(root, since=since), since) if r.get("tool") == "human"]
    if task:
        rcpts = [r for r in rcpts if r.get("task") == task]
    by_call = {c["id"]: c for c in calls}
    outcomes = {t: row.get("outcome") for t, row in tasks.read(root).items()}
    rate, source = policy.human_rate_source(pol)
    agents: dict[str, dict] = {}
    for r in rcpts:
        call = by_call.get(r.get("call"), {})
        name = (r.get("meta") or {}).get("agent") or call.get("agent") or "lib"
        if agent and name != agent:
            continue
        if outcomes.get(r.get("task")) == "redo":  # botched task is not a saving (§4.1)
            continue
        runs = [c for c in calls if c.get("task") == r.get("task")]
        usd, _, conf = human.human_alternative_usd(r, pol)
        a = agents.setdefault(name, {"tasks": 0, "human_usd": 0.0, "agent_usd": 0.0,
                                     "human_min": 0.0, "agent_min": 0.0, "conf_sum": 0.0})
        a["tasks"] += 1
        a["human_usd"] += usd
        # Repriced from tokens × policy like report/budget — the stored est_cost_usd
        # is 0.0 for transcript-sourced calls (the agent side read as free without it).
        a["agent_usd"] += sum(prices.call_usd(pol, c) for c in runs)
        a["human_min"] += human.human_minutes(r, pol)
        a["agent_min"] += _active_minutes(runs)
        a["conf_sum"] += conf
    return {"since": since, "task": task, "rate": rate, "source": source,
            "agents": _finalize(agents)}


def _finalize(agents: dict) -> dict:
    for a in agents.values():
        a["saved_usd"] = round(a["human_usd"] - a["agent_usd"], 6)
        a["saved_min"] = round(a["human_min"] - a["agent_min"], 4)  # may be negative
        a["conf"] = round(a["conf_sum"] / a["tasks"], 4) if a["tasks"] else 0.0
        for k in ("human_usd", "agent_usd"):
            a[k] = round(a[k], 6)
    return agents


def render_human(data: dict) -> str:
    if not data["agents"]:
        return "cage: no human receipts yet — record one with `cage human-record`."
    rows, tot = [], {"tasks": 0, "human_usd": 0.0, "agent_usd": 0.0, "saved_usd": 0.0,
                     "saved_min": 0.0, "conf_sum": 0.0}
    for name, a in sorted(data["agents"].items(), key=lambda kv: -kv[1]["saved_usd"]):
        rows.append([name, str(a["tasks"]), render.usd(a["human_usd"]), render.usd(a["agent_usd"]),
                     render.usd(a["saved_usd"]), f"{a['saved_min'] / 60:.1f}", f"{a['conf']:.2f}",
                     "estimated"])
        for k in ("tasks", "human_usd", "agent_usd", "saved_usd", "saved_min"):
            tot[k] += a[k]
        tot["conf_sum"] += a["conf"] * a["tasks"]
    n = tot["tasks"]
    rows.append(["TOTAL", str(n), render.usd(tot["human_usd"]), render.usd(tot["agent_usd"]),
                 render.usd(tot["saved_usd"]), f"{tot['saved_min'] / 60:.1f}",
                 f"{tot['conf_sum'] / n:.2f}" if n else "—", ""])
    head = ["agent", "tasks", "human $", "agent $", "saved $", "saved hrs", "conf", "method"]
    win = f" · since {data['since']}" if data["since"] else ""
    title = (f"Agent vs human · {n} tasks{win} · "
             f"rate source: {data['source']} (${data['rate']:.0f}/hr)")
    return f"{title}\n\n" + render.table(head, rows, rights={1, 2, 3, 4, 5, 6})
