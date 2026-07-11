"""`cage calibration` — do `cage estimate`'s bands actually land? (roadmap P3)

The estimator never self-reports confidence; this view **measures** it: over
closed tasks that carry a recorded estimate (`est_tokens` + band bounds,
stamped by `cage estimate --record` *before* the task ran), compare the
estimate to the measured actual:

- **ratio distribution** — actual_tokens / est_tokens per task (median + IQR);
  1.0 means estimates are centered, >1 means tasks run over estimate.
- **in-band hit-rate** — share of tasks whose actual fell inside the recorded
  ``est_tokens_q1``–``est_tokens_q3`` band *as it was at estimate time* (a
  recomputed band over grown history would be a different band — that's why
  the bounds are stamped, plan §3.4).

Both figures are **measured** — recorded estimates against recorded actuals,
an observed frequency, no reconstruction. Open tasks are not scored (no error);
zero-actual tasks (no calls joined) and legacy estimates missing band bounds
are skipped with a visible count, never silently dropped.

`--human` (plan §4.10) applies the same measured-hit-rate pattern to the
turn-gap heuristic: over tasks carrying BOTH attested minutes (`human-record` /
`cage outcome --minutes`) and derived turn-gap minutes, report the
derived/attested ratio distribution — the measured accuracy of the derivation.
Below `MIN_ESTIMATE_N` such tasks the view refuses; the heuristic never
self-reports confidence.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from cage import attention, taskgroup
from cage.constants import MIN_ESTIMATE_N


def summarize(root: Path, pol: dict) -> dict:
    actuals = {s["task"]: s for s in taskgroup.stats(root, pol)}  # closed tasks only
    scored, skipped = [], {"open": 0, "zero-actual": 0, "no-band": 0}
    for tid, trow in sorted(taskgroup.closed_tasks(root).items()):
        est = trow.get("est_tokens")
        if est is None:
            continue  # never estimated — not part of calibration at all
        q1, q3 = trow.get("est_tokens_q1"), trow.get("est_tokens_q3")
        actual = actuals.get(tid, {}).get("tokens", 0)
        if actual <= 0:
            skipped["zero-actual"] += 1
            continue
        if not est or q1 is None or q3 is None:
            skipped["no-band"] += 1
            continue
        scored.append({"task": tid, "est": est, "actual": actual,
                       "ratio": round(actual / est, 4),
                       "in_band": q1 <= actual <= q3})
    skipped["open"] = sum(1 for _ in tasks_open_with_estimates(root))
    n = len(scored)
    d = {"n": n, "skipped": skipped, "tasks": scored, "method": "measured"}
    if n:
        ratios = [s["ratio"] for s in scored]
        d["ratio"] = {"median": round(statistics.median(ratios), 4),
                      "q1": round(min(ratios) if n < 2 else
                                  statistics.quantiles(ratios, n=4, method="inclusive")[0], 4),
                      "q3": round(max(ratios) if n < 2 else
                                  statistics.quantiles(ratios, n=4, method="inclusive")[2], 4)}
        hits = sum(1 for s in scored if s["in_band"])
        d["hit_rate"] = round(hits / n, 4)
        d["hits"] = hits
    return d


def tasks_open_with_estimates(root: Path):
    """Open (no outcome) task rows carrying a recorded estimate — counted as
    skipped so a pending estimate is visible, never an error."""
    from cage import tasks
    for tid, trow in sorted(tasks.read(root).items()):
        if not trow.get("outcome") and trow.get("est_tokens") is not None:
            yield tid, trow


def summarize_human(root: Path, pol: dict) -> dict:
    """`cage calibration --human` — measured accuracy of the turn-gap heuristic.

    Scores every task with BOTH attested and derived minutes: ratio =
    derived / attested (1.0 ⇒ the heuristic matches what a person attested; >1 ⇒
    it over-counts). Ratios are read-time derives of recorded signals — the same
    ledger + policy always scores the same. Below `MIN_ESTIMATE_N` such tasks the
    view refuses (a ratio distribution over noise is worse than none)."""
    attested = attention.attested_by_task(root, pol)
    derived = attention.derived_by_task(root, pol)
    scored = [{"task": t, "attested_min": attested[t]["minutes"], "derived_min": derived[t],
               "ratio": round(derived[t] / attested[t]["minutes"], 4)}
              for t in sorted(attested)
              if attested[t]["minutes"] > 0 and t in derived]
    n = len(scored)
    d = {"n": n, "min_n": MIN_ESTIMATE_N, "tasks": scored, "method": "measured",
         "cap_minutes": attention.idle_cap_minutes(pol), "label": attention.LABEL}
    if n < MIN_ESTIMATE_N:
        d["ok"] = False
        d["reason"] = (f"insufficient data (n={n} < {MIN_ESTIMATE_N} tasks with both "
                       "attested and derived minutes) — refusing to score the "
                       "heuristic over noise")
        return d
    d["ok"] = True
    ratios = [s["ratio"] for s in scored]
    q = statistics.quantiles(ratios, n=4, method="inclusive") if n >= 2 else None
    d["ratio"] = {"median": round(statistics.median(ratios), 4),
                  "q1": round(q[0] if q else min(ratios), 4),
                  "q3": round(q[2] if q else max(ratios), 4)}
    return d


def render_calibration_human(d: dict) -> str:
    if not d["ok"]:
        return ("Calibration · derived attention vs attested minutes\n\n"
                f"{d['reason']}\n"
                "attest more tasks (`cage outcome <task> --minutes N` or "
                "`cage human-record --task T --minutes N`) on work whose calls carry "
                "turn-gap data (gap_ms), then re-run.")
    r = d["ratio"]
    return "\n".join([
        "Calibration · derived attention vs attested minutes",
        "",
        f"  n = {d['n']} tasks with both attested and derived minutes",
        f"  derived/attested ratio: median {r['median']:g} · IQR {r['q1']:g}–{r['q3']:g}",
        f"  heuristic: {d['label']} · cap {d['cap_minutes']:g} min",
        f"  method: {d['method']} — observed accuracy of recorded gaps vs attested minutes",
        "",
        "1.0 means the turn-gap derivation matches what people attested; the heuristic",
        "never self-reports confidence — this measured ratio is its accuracy.",
    ])


def render_calibration(d: dict) -> str:
    skip = d["skipped"]
    skipline = (f"  skipped: {skip['open']} open · {skip['zero-actual']} zero-actual · "
                f"{skip['no-band']} without band bounds")
    if not d["n"]:
        return ("Calibration · no closed tasks with recorded estimates yet\n\n"
                "record one before starting a task: `cage estimate --record <task>`;\n"
                "close it with `cage outcome <task>` — then this view measures the hit-rate.\n"
                + skipline)
    r = d["ratio"]
    pct = f"{d['hit_rate'] * 100:.0f}%"
    return "\n".join([
        "Calibration · recorded estimates vs measured actuals (tokens)",
        "",
        f"  n = {d['n']} closed tasks with estimates",
        f"  actual/estimate ratio: median {r['median']:g} · IQR {r['q1']:g}–{r['q3']:g}",
        f"  in-band hit-rate: {pct} ({d['hits']}/{d['n']} inside the recorded IQR band)",
        f"  method: {d['method']} — observed frequency, recorded estimates vs recorded actuals",
        skipline,
        "",
        f"estimates landed in-band {pct} of the time (n={d['n']}) — that measured rate",
        "is the estimator's confidence level; it never self-reports one.",
    ])
