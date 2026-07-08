"""`cage estimate` — a pre-task cost band from matching closed tasks (roadmap P3).

Not a prediction model: the band is the **median + IQR of what matching closed
tasks actually cost** (via `taskgroup.stats` — measured totals), tagged
``modeled`` because applying history to a task that hasn't run is a
reconstruction, never an invoice. Matching is exact-key only (``--scope`` /
``--label`` / ``--agent``) — no similarity scoring, no ML (cage law).

Below ``constants.MIN_ESTIMATE_N`` matching tasks the command refuses with the
reason — a band over noise is worse than no band. Deterministic: same ledger ⇒
same estimate; no clocks in the math.

``--record <task>`` stamps the estimate onto that **open** task row as additive
fields — ``est_tokens`` / ``est_usd`` / ``est_n`` plus the band bounds
``est_tokens_q1`` / ``est_tokens_q3`` (needed so `cage calibration` can score
in-band hits against the band *as it was at estimate time*; recomputing later
over grown history would score a different band). Bounds are recorded for
tokens only — tokens are the ground-truth quantity; USD re-prices as policy
changes. The write is fail-open (`tasks.record`); recording onto an
already-closed task is refused at the CLI boundary — a retroactive estimate is
exactly what calibration must never count.

The estimator never self-reports confidence: the empirical confidence level is
`cage calibration`'s measured hit-rate over closed tasks with estimates.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from cage import render, taskgroup, tasks
from cage.constants import MIN_ESTIMATE_N


def _dist(vals: list[float]) -> dict:
    if len(vals) < 2:  # unreachable at MIN_ESTIMATE_N ≥ 2; guards a lowered constant
        return {"median": vals[0], "q1": vals[0], "q3": vals[0]}
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"median": med, "q1": q1, "q3": q3}


def band(root: Path, pol: dict, *, scope: str | None = None, label: str | None = None,
         agent: str | None = None) -> dict:
    """The estimate payload: matching closed tasks → token/USD band, or a refusal."""
    rows = taskgroup.stats(root, pol)
    keys = {"scope": scope or "", "label": label or "", "agent": agent or ""}
    if scope:
        rows = [r for r in rows if r["scope"] == scope]
    if label:
        rows = [r for r in rows if r["label"] == label]
    if agent:
        rows = [r for r in rows if agent in r["agents"]]
    n = len(rows)
    if n < MIN_ESTIMATE_N:
        return {"ok": False, "n": n, "keys": keys, "min_n": MIN_ESTIMATE_N,
                "reason": (f"insufficient history (n={n} < {MIN_ESTIMATE_N} matching "
                           "closed tasks) — refusing to print a band over noise")}
    return {"ok": True, "n": n, "keys": keys, "min_n": MIN_ESTIMATE_N,
            "method": "modeled",
            "tokens": _dist([float(r["tokens"]) for r in rows]),
            "usd": _dist([r["usd"] for r in rows])}


def record(root: Path, task_id: str, est: dict) -> bool:
    """Stamp an ``ok`` estimate onto the open task row (fail-open, last-write-wins).
    The caller (CLI) has already refused closed tasks and non-ok estimates."""
    return tasks.record(root, task_id, snapshot=False,
                        est_tokens=est["tokens"]["median"],
                        est_tokens_q1=est["tokens"]["q1"],
                        est_tokens_q3=est["tokens"]["q3"],
                        est_usd=est["usd"]["median"],
                        est_n=est["n"])


def _keyline(keys: dict) -> str:
    shown = [f"{k}={v}" for k, v in keys.items() if v]
    return " · ".join(shown) if shown else "all closed tasks (no key filter)"


def render_estimate(d: dict, recorded: str = "") -> str:
    head = f"Estimate · {_keyline(d['keys'])}"
    if not d["ok"]:
        return (f"{head}\n\n{d['reason']}\n"
                "close more matching tasks (`cage outcome <task>`) or widen the keys.")
    t, u = d["tokens"], d["usd"]
    lines = [head, "",
             f"  n = {d['n']} matching closed tasks",
             f"  tokens: median {t['median']:,.0f} · IQR {t['q1']:,.0f}–{t['q3']:,.0f}",
             f"  usd:    median {render.usd(u['median'])} · IQR "
             f"{render.usd(u['q1'])}–{render.usd(u['q3'])}",
             f"  method: {d['method']} — history applied to an unrun task, never an invoice",
             "  confidence: none self-reported — `cage calibration` measures the hit-rate"]
    if recorded:
        lines.append(f"  ✔ recorded onto open task {recorded!r} (est_tokens/est_usd/est_n + band)")
    return "\n".join(lines)
