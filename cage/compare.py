"""`cage compare` — measured comparison of closed tasks grouped by stack (roadmap P2).

The question attribution can't answer: not "what does graphify *model* as saved"
but "did tasks that ran with graphify **measurably** cost less than tasks that
didn't". Group totals are *measured* (recorded tokens, derive-time repricing);
the **delta between groups is `estimated`** — the tasks differ, nothing was
randomized, so it is an observed difference, never a causal claim. The caveat
renders on every output; `method` stays sacred.

Min-n gate: a group below `constants.MIN_COMPARE_N` renders
``insufficient data (n=X < N)`` and joins no delta — the command explains, it
never numbers (a wrong comparison is worse than none).

Deltas are taken against the ``agent-only`` group of the same non-stack keys
(the natural baseline); when it is absent or below min-n, no delta is printed
and the output says why. Median/IQR use the inclusive-quartile method
(`statistics.quantiles(..., method="inclusive")`) — deterministic, stdlib.
"""
from __future__ import annotations

import statistics
from pathlib import Path

from cage import render, taskgroup
from cage.constants import MIN_COMPARE_N

CAVEAT = ("observed difference across different tasks — not a controlled experiment; "
          "stacks are per-task observed receipt sets, not configured pipelines")


def _dist(vals: list[float]) -> dict:
    if len(vals) < 2:  # unreachable at MIN_COMPARE_N ≥ 2; guards a lowered constant
        return {"median": vals[0], "q1": vals[0], "q3": vals[0]}
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"median": med, "q1": q1, "q3": q3}


def summarize(root: Path, pol: dict, *, by: tuple[str, ...] = ("stack",),
              scope: str | None = None, label: str | None = None) -> dict:
    """The deterministic data payload behind the table (and ``--json``)."""
    grouped = taskgroup.group(taskgroup.stats(root, pol), by, scope=scope, label=label)
    keys = tuple(k for k in taskgroup.GROUP_KEYS if k in by or k == "stack")
    groups = []
    for gkey, rows in grouped.items():
        g = dict(zip(keys, gkey))
        g["n"] = len(rows)
        if len(rows) < MIN_COMPARE_N:
            g["ok"] = False
            g["reason"] = f"insufficient data (n={len(rows)} < {MIN_COMPARE_N})"
        else:
            g["ok"] = True
            g["tokens"] = _dist([float(r["tokens"]) for r in rows])
            g["usd"] = _dist([r["usd"] for r in rows])
        groups.append(g)

    # deltas: each eligible stack vs the eligible agent-only group sharing every
    # non-stack key; tagged estimated — an observation, never an invoice.
    deltas = []
    eligible = [g for g in groups if g["ok"]]
    non_stack = [k for k in keys if k != "stack"]
    for g in eligible:
        if g["stack"] == taskgroup.AGENT_ONLY:
            continue
        base = next((b for b in eligible if b["stack"] == taskgroup.AGENT_ONLY
                     and all(b[k] == g[k] for k in non_stack)), None)
        if base is None:
            continue
        deltas.append({**{k: g[k] for k in non_stack},
                       "stack": g["stack"], "baseline": taskgroup.AGENT_ONLY,
                       "d_median_tokens": g["tokens"]["median"] - base["tokens"]["median"],
                       "d_median_usd": round(g["usd"]["median"] - base["usd"]["median"], 6),
                       "method": "estimated"})
    return {"by": list(keys), "min_n": MIN_COMPARE_N, "groups": groups,
            "deltas": deltas, "caveat": CAVEAT}


def _tok(x: float) -> str:
    return f"{x:,.0f}"


def render_compare(d: dict) -> str:
    if not d["groups"]:
        return ("No closed tasks to compare — close tasks with `cage outcome <task>` "
                "(optionally `--label <word>`), then re-run `cage compare`.")
    keys = d["by"]
    headers = [*keys, "n", "median tok", "IQR tok", "median $", "IQR $"]
    rows = []
    for g in d["groups"]:
        head = [str(g[k]) or "—" for k in keys]
        if g["ok"]:
            rows.append([*head, str(g["n"]),
                         _tok(g["tokens"]["median"]),
                         f"{_tok(g['tokens']['q1'])}–{_tok(g['tokens']['q3'])}",
                         render.usd(g["usd"]["median"]),
                         f"{render.usd(g['usd']['q1'])}–{render.usd(g['usd']['q3'])}"])
        else:
            rows.append([*head, str(g["n"]), g["reason"], "", "", ""])
    out = ["Stack comparison · closed tasks · measured group totals "
           "(tokens = in+out per task)", "",
           render.table(headers, rows, rights={len(keys), len(keys) + 1,
                                               len(keys) + 2, len(keys) + 3, len(keys) + 4})]
    if d["deltas"]:
        out.append("")
        for dl in d["deltas"]:
            extra = "".join(f" · {k}={dl[k]}" for k in keys if k != "stack" and dl.get(k))
            out.append(f"Δ {dl['stack']} vs {dl['baseline']}{extra}: "
                       f"{dl['d_median_tokens']:+,.0f} tok · "
                       f"{render.signed_usd(dl['d_median_usd'])} per task (median, {dl['method']})")
        out.append(f"  ⚠ {d['caveat']}")
    else:
        eligible = [g for g in d["groups"] if g["ok"]]
        why = ("no eligible agent-only baseline group"
               if not any(g["stack"] == taskgroup.AGENT_ONLY for g in eligible)
               else "no eligible non-baseline group")
        out.append("")
        out.append(f"no delta: {why} (each side needs n ≥ {d['min_n']}).")
    return "\n".join(out)
