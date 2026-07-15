"""Task grouping — the shared key-matching core under `cage insights compare` (roadmap P2)
and `cage insights estimate`/`cage insights calibration` (P3).

Turns the ledger into per-closed-task facts: which tool stack was *observed* on
the task, and what the task *measurably* cost. Pure derive — no clocks, no
mutation; same ledger ⇒ same stats.

**Join precedence** (the documented contract):

1. *task-id join* — calls/receipts whose ``task`` equals the task row's id.
2. *session-window fallback* — a row with an **empty** ``task`` joins a task when
   its ``session`` is one of the task's sessions (the sessions of its task-id
   calls) and its ``ts`` falls inside the task's call span (inclusive). Needed
   because transcript-imported calls carry ``session`` but no task id. When two
   tasks' windows both match, the lexicographically smallest task id wins (a
   total, stable order — never dict order). A row carrying a *different* task id
   never joins.

**Stack signature** — the sorted set of ``tool`` values on the task's joined
receipts, ``"human"`` excluded (the Tier-1 anchor is an alternative-cost axis,
not a pipeline tool). Empty set ⇒ ``agent-only``. Signatures are per-task
*observed* receipt sets, not configured pipelines — a caveat every consumer
renders.

**Totals are measured** — tokens are the recorded ``tokens_in + tokens_out`` of
the joined calls; USD is recomputed per call at derive time via
`prices.call_usd` (the same authoritative path `report`/`budget` use).
"""
from __future__ import annotations

from pathlib import Path

from cage import ledger, prices, tasks

AGENT_ONLY = "agent-only"
GROUP_KEYS = ("stack", "scope", "label")


def closed_tasks(root: Path) -> dict[str, dict]:
    """Latest row per task id, filtered to *closed* tasks (an ``outcome`` recorded
    via `cage human outcome` / SessionEnd). Open tasks never enter a comparison."""
    return {tid: row for tid, row in tasks.read(root).items() if row.get("outcome")}


def _span(rows: list[dict]) -> tuple[str, str] | None:
    ts = sorted(r["ts"] for r in rows if r.get("ts"))
    return (ts[0], ts[-1]) if ts else None


def join(root: Path) -> dict[str, dict]:
    """``{task_id: {"calls": [...], "receipts": [...]}}`` per the join precedence."""
    return join_rows(ledger.calls(root), ledger.receipts(root))


def join_rows(calls: list[dict], receipts: list[dict]) -> dict[str, dict]:
    """The join over already-read rows — same contract as :func:`join`, for callers
    that hold the ledger in hand (receipt pricing builds it once per view, §4.5)."""
    out: dict[str, dict] = {}
    for c in calls:
        if c.get("task"):
            out.setdefault(c["task"], {"calls": [], "receipts": []})["calls"].append(c)
    for r in receipts:
        if r.get("task"):
            out.setdefault(r["task"], {"calls": [], "receipts": []})["receipts"].append(r)
    # session-window fallback — windows derived from the task-id calls only, task
    # ids walked in sorted order so an overlap resolves the same way every run.
    windows = []
    for tid in sorted(out):
        direct = out[tid]["calls"]
        sessions = {c["session"] for c in direct if c.get("session")}
        span = _span(direct)
        if sessions and span:
            windows.append((tid, sessions, span))

    def _adopt(row: dict) -> str | None:
        for tid, sessions, (lo, hi) in windows:
            if row.get("session") in sessions and lo <= row.get("ts", "") <= hi:
                return tid
        return None

    for c in calls:
        if not c.get("task") and (tid := _adopt(c)):
            out[tid]["calls"].append(c)
    for r in receipts:
        if not r.get("task") and (tid := _adopt(r)):
            out[tid]["receipts"].append(r)
    return out


def signature(receipts: list[dict]) -> str:
    """The observed stack: sorted joined receipt tools, ``human`` excluded;
    ``agent-only`` when no tool receipt joined."""
    tools = sorted({r.get("tool", "") for r in receipts} - {"", "human"})
    return "+".join(tools) if tools else AGENT_ONLY


def _task_scope(row: dict) -> str:
    """A task's scope: the single top-level changed dir of its git snapshot
    (`tasks.git_snapshot` ``dirs``), "" when multi-dir/absent — same resolution
    rule as `tasks.scope_for`, read from the recorded row instead of live git."""
    dirs = row.get("dirs") or []
    return dirs[0] if len(dirs) == 1 else ""


def stats(root: Path, pol: dict) -> list[dict]:
    """One measured stat row per closed task, in sorted task-id order:
    ``{task, stack, scope, label, calls, tokens, usd}``. Tasks whose joined call
    set is empty still appear (tokens/usd 0, calls 0) — consumers decide whether
    to exclude them, visibly."""
    joined = join(root)
    rows = []
    for tid, trow in sorted(closed_tasks(root).items()):
        j = joined.get(tid, {"calls": [], "receipts": []})
        rows.append({
            "task": tid,
            "stack": signature(j["receipts"]),
            "scope": _task_scope(trow),
            "label": trow.get("label", ""),
            "agents": sorted(trow.get("agents") or []),
            "calls": len(j["calls"]),
            "tokens": sum(c.get("tokens_in", 0) + c.get("tokens_out", 0) for c in j["calls"]),
            "usd": round(sum(prices.call_usd(pol, c) for c in j["calls"]), 6),
        })
    return rows


def group(rows: list[dict], by: tuple[str, ...] = ("stack",), *,
          scope: str | None = None, label: str | None = None) -> dict[tuple, list[dict]]:
    """Group stat rows by ``by`` keys (⊆ {stack, scope, label}; stack always
    included), after the optional scope/label filters. Keys sort deterministically."""
    keys = tuple(k for k in GROUP_KEYS if k in by or k == "stack")
    if scope:
        rows = [r for r in rows if r["scope"] == scope]
    if label:
        rows = [r for r in rows if r["label"] == label]
    out: dict[tuple, list[dict]] = {}
    for r in rows:
        out.setdefault(tuple(r[k] for k in keys), []).append(r)
    return dict(sorted(out.items()))
