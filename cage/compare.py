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

from cage import attention, ledger, prices, render, taskgroup
from cage.constants import MIN_COMPARE_N
from cage.report import unpriced_line

CAVEAT = ("observed difference across different tasks — not a controlled experiment; "
          "stacks are per-task observed receipt sets, not configured pipelines")


def _dist(vals: list[float]) -> dict:
    if len(vals) < 2:  # unreachable at MIN_COMPARE_N ≥ 2; guards a lowered constant
        return {"median": vals[0], "q1": vals[0], "q3": vals[0]}
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"median": med, "q1": q1, "q3": q3}


def summarize(root: Path, pol: dict, *, by: tuple[str, ...] = ("stack",),
              scope: str | None = None, label: str | None = None,
              agent_only: bool = False) -> dict:
    """The deterministic data payload behind the table (and ``--json``).

    Unless ``agent_only``, a ``total_cost`` block (plan §4.10) totals the filtered
    task set as agent $ + human attention minutes × rate — attested beats derived
    per task (never summed), tagged with the human component's method."""
    rows = taskgroup.stats(root, pol)
    if scope:
        rows = [r for r in rows if r["scope"] == scope]
    if label:
        rows = [r for r in rows if r["label"] == label]
    grouped = taskgroup.group(rows, by)
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
    d = {"by": list(keys), "min_n": MIN_COMPARE_N, "groups": groups,
         "deltas": deltas, "caveat": CAVEAT,
         "unpriced_detail": unpriced_detail(root, pol)}
    if not agent_only and rows:
        att = attention.resolve(root, pol, task_ids=[r["task"] for r in rows])
        d["total_cost"] = attention.total_cost(sum(r["usd"] for r in rows), att, pol)
    return d


def unpriced_detail(root: Path, pol: dict) -> dict:
    """Ledger-wide ``{prov/model: {calls, tokens}}`` of none-match calls — shared by
    the compare/study UNPRICED warning (an analyst must see the gap before
    publishing a total; the group numbers themselves stay as computed)."""
    detail: dict[str, dict] = {}
    for c in ledger.calls(root):
        if prices.call_usd_match(pol, c)[1] != "none":
            continue
        u = detail.setdefault(f"{c.get('provider') or '—'}/{c.get('model') or '—'}",
                              {"calls": 0, "tokens": 0})
        u["calls"] += 1
        u["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
    return dict(sorted(detail.items()))


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
    if "total_cost" in d:  # plan §4.10 — suppressed by --agent-only
        out += ["", attention.render_total_cost(d["total_cost"])]
    if d.get("unpriced_detail"):
        out += ["", unpriced_line(d["unpriced_detail"])]
    return "\n".join(out)
