"""Best-effort `task` correlation for import-sourced calls (import-ledger plan §4 /
Phase 4) — **gated, disabled by default, derive-time only**.

The raw agent logs carry no task id, so an imported call row lands with ``task=""``.
This pass correlates such a call to a *closed* task by exactly the `taskgroup`
session-window join (session match, then the task's call-span window, overlaps → the
lexicographically smallest task id), and tags the result with its OWN method/confidence
so it can never masquerade as ground truth: a correlated task is ``estimated`` at
`constants.TASK_CORRELATION_CONFIDENCE` — never ``measured``/``modeled``, never the
task-id join's certainty.

**Two guards, both load-bearing (handoff §3):**

1. *Disabled by default* — `policy.task_correlation_enabled` (env `CAGE_TASK_CORRELATION`
   / `[capture] task_correlation`, default **off**). The pass ships built + tested but
   inert until a maintainer has validated it against real correlated data. Recorded as
   an activation gate in the plan's decisions log.
2. *Blocking min-n* — below `constants.MIN_TASK_CORRELATION_N` correlated calls the pass
   returns **nothing** (a `refused` result), never a handful of noisy tags.

**Derive-time only.** This NEVER writes to the ledger: a heuristic task written into a
call row's ``task`` field would read as ground truth (the field has no in-row method
tag) and violate append-only + the method law. The correlation is returned as tagged
records for a caller to surface; no live view consumes it yet (it activates on flag).

Pure function of (calls, closed tasks) — no clocks, no random, so same ledger ⇒ same
correlation. Mirrors `taskgroup.join` exactly rather than re-deriving the window logic.
"""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from cage import constants, ledger, policy, taskgroup


class Correlation(NamedTuple):
    """One correlated call → task tag. ``method`` is always ``"estimated"`` and
    ``confidence`` the low correlation confidence — the tag can never read as certain."""
    call_id: str
    task: str
    session: str
    ts: str
    method: str
    confidence: float


class Result(NamedTuple):
    """The correlation outcome. ``enabled`` reflects the policy gate; ``blocked`` the
    min-n gate; ``reason`` is a human string when either short-circuits. ``correlations``
    is empty unless the pass both ran and cleared the gate."""
    enabled: bool
    blocked: bool
    reason: str
    correlations: list[Correlation]


def _correlate_rows(calls: list[dict], closed: dict[str, dict]) -> list[Correlation]:
    """The join itself, over rows in hand: reuse `taskgroup.join_rows` to adopt
    empty-task calls into the closed tasks by the session-window contract, then keep
    only the *adopted* calls (a call that already carried a task id is ground truth,
    not a correlation) and tag each ``estimated``. Deterministic: task ids and call ids
    walked in sorted order so overlaps and output order are stable every run."""
    if not closed:
        return []
    # Restrict the join's fallback windows to CLOSED tasks: build the join from calls
    # whose task id is a closed task (so `join_rows` derives windows from them), then
    # read back which empty-task calls got adopted.
    joined = taskgroup.join_rows(calls, [])
    out: list[Correlation] = []
    for tid in sorted(joined):
        if tid not in closed:
            continue
        for c in joined[tid]["calls"]:
            if c.get("task"):
                continue  # a task-id call is ground truth, not a correlation
            out.append(Correlation(
                call_id=c.get("id", ""), task=tid, session=c.get("session", ""),
                ts=c.get("ts", ""), method="estimated",
                confidence=constants.TASK_CORRELATION_CONFIDENCE))
    out.sort(key=lambda x: (x.call_id, x.task))
    return out


def correlate(root: Path, pol: dict | None = None) -> Result:
    """Correlate this ledger's import-sourced (empty-task) calls to closed tasks.

    Returns a :class:`Result`. Both guards apply: disabled by policy ⇒
    ``enabled=False`` (empty); below the blocking min-n ⇒ ``blocked=True`` (empty).
    Only when enabled AND at/above the gate does it return the tagged correlations."""
    pol = pol if pol is not None else policy.load(paths_policy(root))
    if not policy.task_correlation_enabled(pol):
        return Result(enabled=False, blocked=False,
                      reason=("task correlation is disabled — enable with "
                              "[capture] task_correlation = true / CAGE_TASK_CORRELATION=1 "
                              "(off until validated on real data)"),
                      correlations=[])
    closed = taskgroup.closed_tasks(root)
    # **P5 narrowed what this can see, and it says so rather than silently reading less.**
    # `calls` is the only kind that carries a `task`, and claude/copilot stopped writing it
    # — their metric rows have no task grain at all (TASK-GRAIN-SPINE). **KIRO-CALLS-LEG
    # then narrowed it once more** (2026-08-15): kiro's IDE rows moved to `ledger/kiro/`
    # too, so the correlation population is consumer rows, retired-agent history and
    # custom sources — no built-in agent is in it at all.
    # Deliberately NOT widened with a timestamp-proximity fallback: guessing which task a
    # call belonged to from how close its clock was is forbidden by house law, and this
    # module's whole reason for being gated is that a few heuristic joins are noise.
    found = _correlate_rows(ledger.calls(root), closed)
    if len(found) < constants.MIN_TASK_CORRELATION_N:
        return Result(enabled=True, blocked=True,
                      reason=(f"INSUFFICIENT DATA — {len(found)} correlated call(s), need "
                              f"{constants.MIN_TASK_CORRELATION_N} before tagging (a few "
                              "heuristic joins are noise, not attribution). Since v0.51 "
                              "only `calls` rows carry a task, and no built-in agent "
                              "writes them — see TASK-GRAIN-SPINE"),
                      correlations=[])
    return Result(enabled=True, blocked=False, reason="", correlations=found)


def paths_policy(root: Path) -> Path:
    from cage import paths
    return paths.Footprint(root).policy
