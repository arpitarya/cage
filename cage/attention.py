"""Derived human-attention minutes from recorded turn gaps (plan §4.10).

The **one** place turn-gap derivation lives — every consuming view (`human` /
`trend` / `compare` / `verdict` / `study report` / `calibration --human`) calls
in here; no view computes gaps itself.

The signal: `gap_ms` on a call row (stamped at import where a transcript carries
real per-turn timestamps — see `transcript.py`'s per-agent availability note) is
the wall-clock between the previous assistant turn's end and the human turn that
led to this call. Derivation is **read-time only**: minutes = Σ min(gap, idle
cap) over the rows in scope, with the cap resolved from policy
(`[human] idle_cap_minutes`, `constants.IDLE_CAP_MINUTES` fallback — the
`DEFAULT_CONFIDENCE` pattern). Changing the cap re-derives; the ledger is never
rewritten. Deterministic: same ledger + same policy ⇒ same minutes.

Method honesty (the law this module enforces for its consumers):

- derived minutes are always **`estimated`**, labelled ``LABEL``
  (`derived (turn-gaps, capped)`) — never anything else;
- **attested** minutes (a `tool="human"` receipt on the task, via `human-record`
  or `cage human outcome --minutes`) rank above derived: for a given task attested
  wins and derived is kept as *reference* — the two are **never summed**;
- an agent whose log carries no turn timestamps has no `gap_ms` and thus no
  derived minutes — absence stays explicit, nothing is fabricated.
"""
from __future__ import annotations

from pathlib import Path

from cage import human, ledger, policy, render
from cage.constants import IDLE_CAP_MINUTES

LABEL = "derived (turn-gaps, capped)"
METHOD = "estimated"  # derived minutes never render as anything else


def idle_cap_minutes(pol: dict) -> float:
    """The idle cap: policy `[human] idle_cap_minutes` wins; the constant is only
    the unset-key fallback (the DEFAULT_CONFIDENCE pattern)."""
    try:
        v = policy.human_rates(pol).get("idle_cap_minutes")
        return float(v) if v is not None else float(IDLE_CAP_MINUTES)
    except (TypeError, ValueError):
        return float(IDLE_CAP_MINUTES)


def minutes_of(call: dict, pol: dict) -> float:
    """Capped attention minutes of one call row — 0.0 when `gap_ms` is absent
    (the legacy contract / a timestamp-less agent), never a fabricated figure."""
    gap = call.get("gap_ms")
    if not isinstance(gap, (int, float)) or gap < 0:
        return 0.0
    return min(float(gap), idle_cap_minutes(pol) * 60_000.0) / 60_000.0


def capped_minutes(calls: list[dict], pol: dict) -> float:
    """Σ capped gap minutes over call rows (rows without `gap_ms` contribute 0)."""
    return round(sum(minutes_of(c, pol) for c in calls), 4)


def by_agent(calls: list[dict], pol: dict) -> dict[str, dict]:
    """Per-agent derived rollup: minutes + the sessions/calls that carried a gap."""
    out: dict[str, dict] = {}
    for c in calls:
        m = minutes_of(c, pol)
        if m <= 0 and "gap_ms" not in c:
            continue
        a = out.setdefault(c.get("agent") or "lib",
                           {"minutes": 0.0, "calls": 0, "sessions": set()})
        a["minutes"] += m
        a["calls"] += 1
        if c.get("session"):
            a["sessions"].add(c["session"])
    return {name: {"minutes": round(a["minutes"], 4), "calls": a["calls"],
                   "sessions": len(a["sessions"])}
            for name, a in sorted(out.items())}


def attested_by_task(root: Path, pol: dict) -> dict[str, dict]:
    """Attested minutes per task from `tool="human"` receipts (`human-record` /
    `cage human outcome --minutes`), resolved by the existing §3 precedence ladder —
    this module extends that ladder, it never bypasses it."""
    out: dict[str, dict] = {}
    for r in ledger.receipts(root):
        if r.get("tool") != "human" or not r.get("task"):
            continue
        t = out.setdefault(r["task"], {"minutes": 0.0, "method": "measured"})
        t["minutes"] += human.human_minutes(r, pol)
        if r.get("method") != "measured":  # one estimate taints the task's tag
            t["method"] = "estimated"
    return {k: {"minutes": round(v["minutes"], 4), "method": v["method"]}
            for k, v in out.items()}


def derived_by_task(root: Path, pol: dict) -> dict[str, float]:
    """Derived minutes per task over the joined calls (task-id join + the
    session-window fallback — the same `taskgroup.join` contract every
    cost-impact view uses). Tasks whose calls carry no `gap_ms` are absent."""
    from cage import taskgroup  # local: taskgroup → prices; keep import light
    out: dict[str, float] = {}
    for tid, j in taskgroup.join(root).items():
        m = capped_minutes(j["calls"], pol)
        if m > 0:
            out[tid] = m
    return out


def resolve(root: Path, pol: dict, *, task_ids: list[str] | None = None,
            since: str | None = None) -> dict:
    """The attested-beats-derived resolution over a scope of work.

    ``task_ids`` restricts to those tasks (the `cage insights compare` slice); otherwise
    the whole ledger windowed by ``since`` (the `verdict`/`study` slice), where
    task-less calls' gaps still count as derived. Per task: attested wins,
    derived becomes reference (``derived_ref_min``) — **never summed**.
    """
    attested = attested_by_task(root, pol)
    if task_ids is not None:
        wanted = set(task_ids)
        attested = {t: v for t, v in attested.items() if t in wanted}
        derived = {t: m for t, m in derived_by_task(root, pol).items() if t in wanted}
        loose_min = 0.0
    else:
        from cage import taskgroup  # local: taskgroup → prices; keep import light
        window = ledger.since(ledger.calls(root), since)
        in_window = {c.get("id") for c in window}
        derived, joined_ids = {}, set()
        for tid, j in taskgroup.join(root).items():
            joined_ids.update(c.get("id") for c in j["calls"])
            m = capped_minutes([c for c in j["calls"] if c.get("id") in in_window], pol)
            if m > 0:
                derived[tid] = m
        # gaps on calls no task adopted still count once, as task-less derived time
        loose_min = capped_minutes([c for c in window if c.get("id") not in joined_ids], pol)
        if since:
            windowed = {r.get("task") for r in ledger.since(ledger.receipts(root), since)
                        if r.get("tool") == "human"}
            attested = {t: v for t, v in attested.items() if t in windowed}
    attested_min = round(sum(v["minutes"] for v in attested.values()), 4)
    derived_only_min = round(sum(m for t, m in derived.items() if t not in attested), 4)
    derived_ref_min = round(sum(m for t, m in derived.items() if t in attested), 4)
    minutes = round(attested_min + derived_only_min + loose_min, 4)
    sources = []
    if attested:
        sources.append("attested")
    if derived_only_min or derived_ref_min or loose_min:
        sources.append("derived")
    method = ("measured" if attested and not derived_only_min and not loose_min
              and all(v["method"] == "measured" for v in attested.values())
              else "estimated")
    return {"minutes": minutes, "attested_min": attested_min,
            "derived_min": round(derived_only_min + loose_min, 4),
            "derived_ref_min": derived_ref_min,
            "attested_tasks": len(attested), "sources": sources,
            "method": method if sources else "",
            "cap_minutes": idle_cap_minutes(pol), "label": LABEL}


def total_cost(agent_usd: float, att: dict, pol: dict) -> dict:
    """Agent $ + human minutes × rate — the shared payload behind the
    compare/verdict/study total-cost line. The human component keeps its
    resolution detail so the render can tag it honestly."""
    rate, source = policy.human_rate_source(pol)
    human_usd = round(att["minutes"] / 60.0 * rate, 6)
    return {"agent_usd": round(agent_usd, 6), "human_usd": human_usd,
            "total_usd": round(agent_usd + human_usd, 6),
            "rate": rate, "rate_source": source, **att}


def render_total_cost(tc: dict) -> str:
    """The one line (plus its honesty tag) every consumer prints verbatim."""
    if not tc["sources"]:
        return (f"total cost: agent {render.usd(tc['agent_usd'])} + human — "
                "(no attested minutes and no turn-gap data in scope; only logs "
                "with per-turn timestamps carry gap_ms)")
    parts = []
    if "attested" in tc["sources"]:
        parts.append(f"attested {tc['attested_min']:g} min")
    if "derived" in tc["sources"]:
        parts.append(f"{LABEL} {tc['derived_min']:g} min")
    ref = (f" · derived ref on attested tasks: {tc['derived_ref_min']:g} min (not summed)"
           if tc["derived_ref_min"] else "")
    return (f"total cost: agent {render.usd(tc['agent_usd'])} + human "
            f"{tc['minutes']:g} min × ${tc['rate']:g}/hr = "
            f"{render.usd(tc['total_usd'])} ({tc['method']})\n"
            f"  human minutes: {' + '.join(parts)} — attested beats derived per task, "
            f"never summed{ref}")
