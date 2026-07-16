"""Deterministic seed ledgers behind the output-spec goldens (plan Phases 1+2+5.6).

One builder per spec scenario family (`docs/cli-output-spec.md`); every id and
timestamp is pinned so the rendered output is byte-stable — the golden tests
assert against `tests/fixtures/goldens/*.txt`, and `tools/docgen` regenerates
the spec's code blocks from those same fixture files (one artifact, docs and
tests cannot disagree).

Numbers are chosen to exercise every rule, not to be pretty: exact-priced
(anthropic), family-priced (copilot's dotted ids), UNPRICED (`copilot/auto`),
the kiro input-only log, linked + ladder-priced + refused receipts, signal
gating, and the negative-net case.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import ledger, paths, schema, tasks


def _ts(day: int, hh: int = 9, month: int = 7) -> str:
    return f"2026-{month:02d}-{day:02d}T{hh:02d}:00:00Z"


def _call(root: Path, cid: str, *, provider: str, model: str, agent: str,
          tin: int, tout: int, ts: str, task: str = "", session: str = "",
          machine: str = "") -> str:
    row = schema.make_call(route="chat", provider=provider, model=model,
                           tokens_in=tin, tokens_out=tout, agent=agent,
                           task=task, session=session, ts=ts, call_id=cid)
    if machine:
        row["machine"] = machine
    ledger.append(paths.Footprint(root).calls, row)
    return row["id"]


def _receipt(root: Path, rid: str, *, tool: str, raw: float, actual: float,
             ts: str, call: str = "", task: str = "", method: str = "modeled",
             unit: str = "tokens", meta: dict | None = None) -> str:
    row = schema.make_receipt(tool=tool, raw_alternative=raw, actual=actual,
                              call=call, task=task, unit=unit, method=method,
                              meta=meta, ts=ts)
    row["id"] = rid  # pin the one entropy source — goldens must be byte-stable
    ledger.append(paths.Footprint(root).receipts, row)
    return rid


def _task(root: Path, tid: str, *, outcome: str = "ok", label: str = "",
          ts: str = "", agents: list[str] | None = None) -> None:
    extra = {"label": label} if label else {}
    tasks.record(root, tid, outcome=outcome, agents=agents or ["claude"],
                 ts=ts or _ts(1), snapshot=False, **extra)


def set_last_import(root: Path, ts: str) -> None:
    """Pin the `_last_import` cursor (the staleness-gated advice line's input)."""
    f = paths.Footprint(root).state / "cursors.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    cur["_last_import"] = ts
    f.write_text(json.dumps(cur), encoding="utf-8")


def set_capture_gap(root: Path, agent: str = "codex") -> None:
    """Pin a triple-gated capture-health record for ``agent`` (home present, 0 files,
    never captured) so the report/doctor "installed but capturing nothing" ⚠ fires — the
    `_health` input `importcmd` records at import (docs/capture-health). ``~``-relative
    paths keep the golden byte-stable and OS-independent."""
    f = paths.Footprint(root).state / "cursors.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    cur.setdefault("_health", {})[agent] = {
        "home": True, "home_path": f"~/.{agent}", "src": f"~/.{agent}/sessions",
        "files": 0, "captured": False}
    f.write_text(json.dumps(cur), encoding="utf-8")


def wmh(root: Path) -> None:
    """The main report fixture (spec R1/R2/R4, P2): three agents, exact + family
    + UNPRICED pricing, linked + ladder + call-less receipts, kiro input-only."""
    # claude — exact-priced, task-joined (the ladder's task-model rung anchor)
    _call(root, "c_cl1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=500_000, tout=40_000, ts=_ts(2), task="t_docs",
          session="s_cl")
    _call(root, "c_cl2", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=412_400, tout=21_200, ts=_ts(3), task="t_docs",
          session="s_cl")
    # copilot — dotted id; the importer infers provider "anthropic" from the
    # model name (transcript._copilot_provider), so it family-prices onto the
    # anthropic row after route-prefix normalization
    _call(root, "c_cp1", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=1_000_000, tout=50_000, ts=_ts(2))
    _call(root, "c_cp2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=818_314, tout=31_556, ts=_ts(3))
    # copilot/auto — the router pseudo-model: loudly UNPRICED until routed
    _call(root, "c_au1", provider="", model="copilot/auto",
          agent="copilot", tin=100_000, tout=10_000, ts=_ts(4))
    _call(root, "c_au2", provider="", model="copilot/auto",
          agent="copilot", tin=49_697, tout=4_656, ts=_ts(4, 10))
    # kiro — generic model row, input-only log (tokens_out never recorded)
    _call(root, "c_k1", provider="kiro", model="agent",
          agent="kiro", tin=400_000, tout=0, ts=_ts(2))
    _call(root, "c_k2", provider="kiro", model="agent",
          agent="kiro", tin=299_122, tout=0, ts=_ts(3))
    # receipts: linked (priced at the call's model) …
    _receipt(root, "r_0001", tool="graphify", raw=180_000, actual=20_000,
             ts=_ts(2, 10), call="c_cl1", task="t_docs")
    _receipt(root, "r_0002", tool="graphify", raw=120_000, actual=20_000,
             ts=_ts(2, 11), call="c_cp1")
    # … and call-less (task-model rung; attributes to the 0-call "—" bucket,
    # which the text view drops while its saving stays in TOTAL)
    _receipt(root, "r_0003", tool="graphify", raw=60_000, actual=8_660,
             ts=_ts(3, 10), task="t_docs")


def spend_only(root: Path) -> None:
    """Spec R3: calls but zero receipts — the signal-gated spend-only table."""
    _call(root, "c_s1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=912_400, tout=61_200, ts=_ts(2))
    _call(root, "c_s2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=1_968_011, tout=96_212, ts=_ts(3))


def stale(root: Path) -> None:
    """Spec R6: a healthy table whose advice gate fires — ledger anchored 61 days
    past the bundled prices_date (data-relative, clock-free) plus a 3-day-old
    last-import cursor (the one documented clock carve-out)."""
    import datetime as _dt
    from cage import policy
    stamped = _dt.date.fromisoformat(str(policy.bundled_raw()["meta"]["prices_date"]))
    anchor = stamped + _dt.timedelta(days=61)
    ts = f"{anchor.isoformat()}T09:00:00Z"
    _call(root, "c_st1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=912_400, tout=61_200, ts=ts, task="t_r6")
    _receipt(root, "r_0601", tool="graphify", raw=100_000, actual=20_000,
             ts=ts, call="c_st1", task="t_r6")
    now = _dt.datetime.now(_dt.timezone.utc)
    set_last_import(root, (now - _dt.timedelta(days=3, hours=2))
                    .isoformat(timespec="seconds").replace("+00:00", "Z"))


def verdict_saving(root: Path) -> None:
    """Spec I2: graphify receipts across four ISO weeks, linked to priced calls,
    zero own cost — SAVING."""
    for i, day in enumerate((1, 8, 15, 22), 1):
        cid = f"c_v{i}"
        _call(root, cid, provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=100_000, tout=8_000, ts=_ts(day),
              task=f"t_v{i}", session="s_v")
        _receipt(root, f"r_01{i:02d}", tool="graphify", raw=90_000,
                 actual=10_000, ts=_ts(day, 10), call=cid, task=f"t_v{i}")
        _task(root, f"t_v{i}", outcome="ok", ts=_ts(day, 11))


def verdict_costing(root: Path) -> None:
    """Spec I3 + the named negative-net law: real receipts whose own tool cost
    exceeds the saving — the negative net renders, always."""
    for i, day in enumerate((1, 8), 1):
        cid = f"c_n{i}"
        _call(root, cid, provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=50_000, tout=4_000, ts=_ts(day),
              task=f"t_n{i}", session="s_n")
        _receipt(root, f"r_02{i:02d}", tool="graphify", raw=60_000,
                 actual=10_000, ts=_ts(day, 10), call=cid, task=f"t_n{i}",
                 meta={"tool_cost_usd": 0.40})
        _task(root, f"t_n{i}", outcome="ok", ts=_ts(day, 11))


def compare_estimate(root: Path) -> None:
    """Spec I5/I6: closed docfix tasks in three observed stacks (5 agent-only,
    5 agent+graphify, 2 agent+graphify+fux → below min-n), plus 3 refactor
    tasks (below MIN_ESTIMATE_N → the estimate refusal)."""
    day = 1
    for i in range(1, 6):  # agent-only
        tid = f"t_a{i}"
        _call(root, f"c_a{i}", provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=10_000 + i * 900, tout=1_500, ts=_ts(day, 8 + i),
              task=tid, session=f"s_a{i}")
        _task(root, tid, label="docfix", ts=_ts(day, 20))
    for i in range(1, 6):  # agent+graphify
        tid = f"t_g{i}"
        cid = f"c_g{i}"
        _call(root, cid, provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=4_000 + i * 600, tout=1_100, ts=_ts(day + 1, 8 + i),
              task=tid, session=f"s_g{i}")
        _receipt(root, f"r_03{i:02d}", tool="graphify", raw=15_000, actual=3_000,
                 ts=_ts(day + 1, 8 + i), call=cid, task=tid)
        _task(root, tid, label="docfix", ts=_ts(day + 1, 20))
    for i in range(1, 3):  # agent+graphify+fux — n=2 < MIN_COMPARE_N
        tid = f"t_f{i}"
        cid = f"c_f{i}"
        _call(root, cid, provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=3_500 + i * 400, tout=900, ts=_ts(day + 2, 8 + i),
              task=tid, session=f"s_f{i}")
        _receipt(root, f"r_04{i:02d}", tool="graphify", raw=12_000, actual=2_500,
                 ts=_ts(day + 2, 8 + i), call=cid, task=tid)
        _receipt(root, f"r_05{i:02d}", tool="fux", raw=6_000, actual=1_200,
                 ts=_ts(day + 2, 9 + i), call=cid, task=tid)
        _task(root, tid, label="docfix", ts=_ts(day + 2, 20))
    for i in range(1, 4):  # refactor — n=3 < MIN_ESTIMATE_N
        tid = f"t_r{i}"
        _call(root, f"c_r{i}", provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=20_000 + i * 1_000, tout=2_500, ts=_ts(day + 3, 8 + i),
              task=tid, session=f"s_r{i}")
        _task(root, tid, label="refactor", ts=_ts(day + 3, 20))


def matrix_task(root: Path) -> None:
    """Spec I7/I8: one task, one tool, a joined priced call — the 2¹ grid."""
    _call(root, "c_m1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=1_660, tout=0, ts=_ts(5), task="t_9f31",
          session="s_m")
    _receipt(root, "r_0701", tool="graphify", raw=22_171, actual=1_660,
             ts=_ts(5, 10), call="", task="t_9f31")


def matrix_unpriceable(root: Path) -> None:
    """Spec I8 (second block): a task-less, call-less receipt — the token grid
    still renders; only the cost column explains its absence."""
    _receipt(root, "r_0801", tool="graphify", raw=22_171, actual=1_660,
             ts=_ts(5, 10))


def fleet(root: Path, complete: int = 5) -> None:
    """Spec S3/S4: `complete` machines with both phases (5 days each), one
    missing the plugin phase, one enrolled with no rows. Markers are written
    directly (each machine resolves against its own clock)."""
    study_file = paths.Footprint(root).study
    mids = [f"m_{i:02d}aa{'0' * 12}"[:18] for i in range(1, complete + 3)]
    for n, mid in enumerate(mids):
        ledger.append(study_file, {"id": f"s_b{n:02d}", "ts": _ts(1, 6),
                                   "event": "start", "phase": "baseline",
                                   "machine": mid})
    for n, mid in enumerate(mids[:complete]):
        ledger.append(study_file, {"id": f"s_p{n:02d}", "ts": _ts(6, 6),
                                   "event": "start", "phase": "plugin",
                                   "machine": mid})
    for n, mid in enumerate(mids[:complete + 1]):  # the last machine: no rows at all
        for d in range(5):  # baseline days 1–5
            _call(root, f"c_b{n}{d}", provider="anthropic",
                  model="claude-sonnet-4-6", agent="claude",
                  tin=200_000 + n * 10_000, tout=20_000, ts=_ts(1 + d, 12),
                  machine=mid)
        if n >= complete:
            continue
        for d in range(5):  # plugin days 6–10 — lighter
            _call(root, f"c_p{n}{d}", provider="anthropic",
                  model="claude-sonnet-4-6", agent="claude",
                  tin=120_000 + n * 6_000, tout=14_000, ts=_ts(6 + d, 12),
                  machine=mid)
