"""`cage human show` — Tier-1 agent-vs-human rollup (design §4.1, §5b.1).

Joins human receipts (the avoided-labor alternative, priced by `human.py`) with the
agent's measured call cost + active time per task. Reports saved **$ and hours** as
co-equal metrics; saved-time can go negative when the agent ran longer than the human
estimate (§5b.1 honesty check). Quality-honest: a redone task is not a saving.

Below the attested table, a separate **derived attention** block (plan §4.10)
shows the passive turn-gap minutes per agent — `attention.py` math, always
`estimated`, labelled `derived (turn-gaps, capped)`. The two sources render on
separate lines and are **never blended into one number**.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import attention, human, ledger, policy, prices, render, tasks


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
    # Derived attention (plan §4.10) — the passive turn-gap axis, a separate block
    # from the attested table above: never blended, attention.py owns the math.
    gap_calls = ledger.since(calls, since)
    if task:
        gap_calls = [c for c in gap_calls if c.get("task") == task]
    if agent:
        gap_calls = [c for c in gap_calls if (c.get("agent") or "lib") == agent]
    return {"since": since, "task": task, "rate": rate, "source": source,
            "agents": _finalize(agents),
            "derived": attention.by_agent(gap_calls, pol),
            "idle_cap": attention.idle_cap_minutes(pol)}


def _finalize(agents: dict) -> dict:
    for a in agents.values():
        a["saved_usd"] = round(a["human_usd"] - a["agent_usd"], 6)
        a["saved_min"] = round(a["human_min"] - a["agent_min"], 4)  # may be negative
        a["conf"] = round(a["conf_sum"] / a["tasks"], 4) if a["tasks"] else 0.0
        for k in ("human_usd", "agent_usd"):
            a[k] = round(a[k], 6)
    return agents


def _render_derived(data: dict) -> str:
    """The derived-attention block — a separate section under the attested table
    (never blended into it). Absent gap data renders as an explicit absence line:
    only logs with per-turn timestamps carry `gap_ms` (Claude today)."""
    derived = data.get("derived") or {}
    if not derived:
        return ("derived attention: no turn-gap data (gap_ms) in scope — only logs "
                "with per-turn timestamps carry it (claude today; codex/copilot/kiro "
                "logs lack the signal).")
    head = ["agent", "sessions", "calls", "attn min", "attn hrs"]
    rows = [[name, str(a["sessions"]), str(a["calls"]), f"{a['minutes']:g}",
             f"{a['minutes'] / 60:.1f}"] for name, a in derived.items()]
    title = (f"derived attention · {attention.LABEL} · cap {data['idle_cap']:g} min "
             f"· {attention.METHOD} — reference only, never summed with attested")
    return f"{title}\n\n" + render.table(head, rows, rights={1, 2, 3, 4})


def render_csv(data: dict) -> str:
    """CSV over the same `rollup()` payload as the text view (one structure, two
    renderers). The two sources stay typed apart by ``kind`` — ``attested`` rows
    (the receipt-priced table + its TOTAL) vs ``derived`` rows (the turn-gap
    block) — never blended into one number, exactly like the text sections; the
    derived rows carry the `derived (turn-gaps, capped)` label in ``note``. Both
    are ``estimated`` (human cost law). Column contract in docs/csv-output.md."""
    from cage import attention, csvout
    head = ["kind", "agent", "tasks", "human_usd", "agent_usd", "saved_usd",
            "saved_minutes", "confidence", "sessions", "calls",
            "attention_minutes", "method", "note"]
    rows = []
    tot = {"tasks": 0, "human_usd": 0.0, "agent_usd": 0.0, "saved_usd": 0.0,
           "saved_min": 0.0, "conf_sum": 0.0}
    for name, a in sorted(data["agents"].items(), key=lambda kv: -kv[1]["saved_usd"]):
        rows.append(["attested", name, a["tasks"], a["human_usd"], a["agent_usd"],
                     a["saved_usd"], a["saved_min"], a["conf"], None, None, None,
                     "estimated", ""])
        for k in ("tasks", "human_usd", "agent_usd", "saved_usd", "saved_min"):
            tot[k] += a[k]
        tot["conf_sum"] += a["conf"] * a["tasks"]
    if data["agents"]:
        n = tot["tasks"]
        rows.append(["attested", "TOTAL", n, round(tot["human_usd"], 6),
                     round(tot["agent_usd"], 6), round(tot["saved_usd"], 6),
                     round(tot["saved_min"], 4),
                     round(tot["conf_sum"] / n, 4) if n else None,
                     None, None, None, "estimated", ""])
    note = f"{attention.LABEL} · cap {data['idle_cap']:g} min — never summed with attested"
    for name, a in (data.get("derived") or {}).items():
        rows.append(["derived", name, None, None, None, None, None, None,
                     a["sessions"], a["calls"], a["minutes"], attention.METHOD, note])
    return csvout.table(head, rows)


def render_human(data: dict) -> str:
    if not data["agents"]:
        return (f"cage: no human receipts yet — record one with `{render.cmd('human record')}` "
                f"(or `{render.cmd('human outcome')} <task> --minutes N`).\n\n" + _render_derived(data))
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
    return (f"{title}\n\n" + render.table(head, rows, rights={1, 2, 3, 4, 5, 6})
            + "\n\n" + _render_derived(data))
