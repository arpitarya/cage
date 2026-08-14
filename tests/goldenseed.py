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

from cage import ledger, originrecord, paths, schema, tasks


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
    _metric_twin(root, row)
    return row["id"]


def _metric_twin(root: Path, row: dict) -> None:
    """Append the per-agent metric twin, exactly as real capture dual-writes it.

    `ledger.spend` supersedes a `calls` row for any agent that HAS a metric ledger
    (USAGE-ONLY, ADR 0011), partitioning by agent rather than by time — so a calls-only
    golden seed renders an EMPTY table for claude and copilot. Agents with no spine
    (`lib`, `codex`, kiro) need no twin: their rows are never superseded (kiro's are
    suppressed outright, `ledger.ABSENT_SPINES`)."""
    from cage import agents as _ag
    surface = _ag.row_surface(row.get("agent")) or ""
    common = dict(session=row.get("session", ""), model=row.get("model", ""),
                  provider=row.get("provider", ""), tokens_in=row.get("tokens_in", 0),
                  tokens_out=row.get("tokens_out", 0),
                  cached_in=row.get("cached_in", 0), ts=row.get("ts"))
    twin = None
    if surface == "claude":
        twin = schema.make_claude_metric(
            source="request", request=row.get("id", ""),
            surface=row.get("surface", ""),
            cache_write_in=row.get("cache_write_in", 0),
            metric_id=f"clm_{row.get('id', '')}", **common)
    elif surface == "copilot":
        twin = schema.make_copilot_metric(
            source="chat", surface=row.get("surface") or "vscode",
            request=row.get("id", ""),
            metric_id=f"cpm_{row.get('id', '')}", **common)
    if twin is None:
        return
    # Carry the axes the metric constructors do not model but the derived views group
    # by — the fleet study buckets per MACHINE, and a twin without one lands unphased.
    for axis in ("machine", "project", "task", "scope"):
        if row.get(axis):
            twin[axis] = row[axis]
    ledger.append_row(root, surface, twin)


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


def set_capture_gap(root: Path, agent: str = "kiro") -> None:
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
    """Spec R6: a healthy table whose advice gate fires — a 3-day-old last-import
    cursor (the one documented clock carve-out).

    The 61-days-past-`prices_date` anchor this used to compute is gone with the price
    file (USAGE-ONLY, ADR 0011); the import-age advice is what remains, and it needs no
    price stamp. A fixed instant keeps the golden clock-free."""
    import datetime as _dt
    ts = "2026-07-02T09:00:00Z"
    # `ledger.spend` reads the metric twin `_call` writes; `ledger.join_table` still
    # resolves the receipt's `call="c_st1"`, so the saving stays attributed to its agent.
    _call(root, "c_st1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude-code", tin=912_400, tout=61_200, ts=ts, task="t_r6",
          session="s_r6")
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






def _usage_row(root: Path, *, op: str, outcome: str, route: str, ts: str) -> None:
    """One graphify usage breadcrumb, written directly so its `ts` is pinned —
    `usagelog.record` stamps the wall clock, which a golden cannot have."""
    f = paths.Footprint(root).usage_log
    f.parent.mkdir(parents=True, exist_ok=True)
    with f.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"ts": ts, "op": op, "args_hash": "a1b2c3d4e5f60718",
                             "exit": 0, "ms": 42, "outcome": outcome,
                             "route": route}) + "\n")


def _savings_row(root: Path, sid: str, *, tool: str, ts: str, session: str = "",
                 call: str = "") -> None:
    """One row in the dedicated savings tree. `session`/`call` are the two join links
    `insights adoption` resolves; both empty is exactly what the interceptor writes."""
    row = schema.make_savings(tool=tool, raw_alternative=22_171, actual=1_660,
                              op="query", session=session, ts=ts, savings_id=sid)
    if call:
        row["call"] = call
    ledger.append_row(root, ("savings", tool), row)


def adoption_mixed(root: Path) -> None:
    """Spec I9a: both adoption halves populated — graphify invoked through the shim and
    the transcript route, one shim run that parsed nothing (`unmeasurable`), one agent
    attributable by session, one shim row agent-unknown by construction, and two wired
    agents with no evidence of invocation."""
    _call(root, "c_a1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude-code", tin=912_400, tout=61_200, ts=_ts(2), session="s_ad1")
    _call(root, "c_a2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=196_801, tout=9_621, ts=_ts(3), session="s_ad2")
    _call(root, "c_a3", provider="anthropic", model="claude-sonnet-4-6",
          agent="kiro", tin=12_000, tout=800, ts=_ts(3), session="s_ad3")
    for n, (op, outcome, route) in enumerate((
            ("query", "receipt", "transcript"), ("query", "receipt", "shim"),
            ("query", "unmeasurable", "shim"), ("explain", "receipt", "shim"),
            ("update", "non-measured", "shim"))):
        _usage_row(root, op=op, outcome=outcome, route=route, ts=_ts(4, 9 + n))
    _savings_row(root, "s_ad01", tool="graphify", ts=_ts(4, 9), session="s_ad1")
    _savings_row(root, "s_ad02", tool="graphify", ts=_ts(4, 10), session="s_ad1")
    _savings_row(root, "s_ad03", tool="graphify", ts=_ts(4, 11))  # the shim: no link
    _savings_row(root, "s_ad04", tool="fux", ts=_ts(4, 12), call="c_a1")


def adoption_shim_only(root: Path) -> None:
    """Spec I9b: every invocation came through the shim, so **nothing** is
    agent-attributable — the half-B refusal path, which renders rather than vanishing."""
    _call(root, "c_b1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude-code", tin=912_400, tout=61_200, ts=_ts(2), session="s_bd1")
    _usage_row(root, op="query", outcome="receipt", route="shim", ts=_ts(4, 9))
    _usage_row(root, op="query", outcome="unmeasurable", route="shim", ts=_ts(4, 10))
    _savings_row(root, "s_bd01", tool="graphify", ts=_ts(4, 9))
    _savings_row(root, "s_bd02", tool="graphify", ts=_ts(4, 10))


def adoption_attributed(root: Path) -> None:
    """Spec I9d: every savings row joins to an agent, so the STRONG claim — *no evidence
    of invocation* — is supportable for the two agents with none. Nothing is left
    unattributed that could belong to them."""
    _call(root, "c_c1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude-code", tin=912_400, tout=61_200, ts=_ts(2), session="s_cd1")
    _call(root, "c_c2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=196_801, tout=9_621, ts=_ts(3), session="s_cd2")
    _call(root, "c_c3", provider="anthropic", model="claude-sonnet-4-6",
          agent="kiro", tin=12_000, tout=800, ts=_ts(3), session="s_cd3")
    _usage_row(root, op="query", outcome="receipt", route="transcript", ts=_ts(4, 9))
    _usage_row(root, op="query", outcome="receipt", route="transcript", ts=_ts(4, 10))
    _savings_row(root, "s_cd01", tool="graphify", ts=_ts(4, 9), session="s_cd1")
    _savings_row(root, "s_cd02", tool="graphify", ts=_ts(4, 10), session="s_cd1")


def _chat_name(root: Path, *, agent: str, session: str, name: str, ts: str) -> None:
    """One `imports.jsonl` title row — written pre-mapped to the SURFACES agent name,
    the way a real import sweep writes it (`importcmd._write_manifest`)."""
    from cage import manifest
    manifest.record_import(
        root, import_id=manifest.new_import_id(), agent=agent, surface="",
        session=session, session_uid=manifest.new_session_uid(), source_path="",
        files_scanned=1, rows_appended=1, tokens_in=0, tokens_out=0, cached_in=0,
        ts=ts, session_name=name)


def chats_titled(root: Path) -> None:
    """Spec I10a: two titled chats (claude, copilot-vscode) — the full-support case.

    Also the `agent%` contract in ONE table: the claude chat has landed-code evidence
    and renders a number; the copilot chat structurally cannot be line-matched and
    renders `—` with its reason. A golden where every cell refuses would pin the
    refusal and leave the number itself uncontracted."""
    _call(root, "c_ct1", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude", tin=900_000, tout=60_000, ts=_ts(2), session="s_ct1")
    _chat_name(root, agent="claude", session="s_ct1", name="fix the flaky test",
              ts=_ts(2, 9, 30))
    originrecord.record_transcript(root, sha="9f3c1ab", files=["cage/report.py"],
                                   agent="claude-code", session_id="s_ct1",
                                   lines_added=104, lines_removed=12, suggested=71,
                                   kept=68, kept_modified=3, agent_lines=68,
                                   residual_lines=42)
    _call(root, "c_ct2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=196_801, tout=9_621, ts=_ts(3), session="s_ct2")
    _chat_name(root, agent="copilot", session="s_ct2", name="refactor the parser",
              ts=_ts(3, 9, 30))


def chats_untitled(root: Path) -> None:
    """Spec I10b: kiro-IDE (no session identity — collapses to one row) beside an
    untitled copilot-CLI chat. Both fall back honestly to their session id, never a
    fabricated name."""
    row = schema.make_call(route="chat", provider="kiro", model="agent",
                           tokens_in=12_000, tokens_out=0, agent="kiro",
                           session="kiro", surface="ide", ts=_ts(2), call_id="c_cu1")
    ledger.append(paths.Footprint(root).calls, row)
    _call(root, "c_cu2", provider="anthropic", model="copilot/claude-sonnet-4.6",
          agent="copilot", tin=50_000, tout=4_000, ts=_ts(3), session="s_cu2")


def chats_truncated(root: Path) -> None:
    """Spec I10d: 23 chats — exercises the top-20 default cut + `--all`."""
    for i in range(23):
        _call(root, f"c_tr{i:02d}", provider="anthropic", model="claude-sonnet-4-6",
              agent="claude", tin=100_000 - i * 1_000, tout=5_000,
              ts=_ts(2, 9 + (i % 10)), session=f"s_tr{i:02d}")


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


# ── agent-vs-human v2: the commit surfaces (HR1 P3) ──────────────────────────
#
# These seeds build a REAL git repo, because the views read one. Every input that
# feeds a commit sha is pinned — content, author, committer, both timestamps, and
# `core.autocrlf=false` (a Windows checkout would otherwise rewrite the blobs and
# change the shas) — so the goldens stay byte-stable on every OS.

_GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}


def _git(repo: Path, *args: str, when: str = "") -> str:
    import os
    import subprocess
    env = {**os.environ, **_GIT_ENV}
    if when:
        env["GIT_AUTHOR_DATE"] = env["GIT_COMMITTER_DATE"] = when
    return subprocess.run(("git", "-C", str(repo), *args), capture_output=True,
                          text=True, check=True, env=env).stdout.strip()


def git_repo(root: Path) -> None:
    """An empty, deterministic repo at ``root`` (the golden runner's project dir)."""
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.name", "t")
    _git(root, "config", "user.email", "t@example.invalid")
    _git(root, "config", "commit.gpgsign", "false")
    _git(root, "config", "core.autocrlf", "false")


def _commit(root: Path, files: dict, when: str) -> str:
    for rel, body in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "c", when=when)
    # FULL sha — what cage records since 2026-08-11 (`commitjoin.prefix_match`);
    # the rendered tables abbreviate for display (`constants.SHORT_SHA_DISPLAY`).
    return _git(root, "rev-parse", "HEAD")


_AGENT_SRC = ("def resolve(name):\n"
              "    table = {'alpha': 1, 'beta': 2}\n"
              "    return table.get(name)\n")
_HUMAN_SRC = ("def tweaked_by_a_person(name):\n"
              "    return resolve(name) or 0\n")
_GENERATED = '{"nodes": ["a generated blob no agent proposed"], "edges": []}\n'


def commits_mixed(root: Path) -> None:
    """Three commits exercising every state the list view has to render:

    c1  seed             — no calls, no authorship          → unattributed, `—` tokens
    c2  agent + human + a generated file                    → all four buckets
    c3  a later commit, no ledger signal                    → unattributed
    """
    git_repo(root)
    _commit(root, {"seed.txt": "the very first line of this repo\n"},
            "2026-07-01T09:00:00+00:00")
    c2 = _commit(root, {"mod.py": _AGENT_SRC + _HUMAN_SRC, "generated.json": _GENERATED},
                 "2026-07-01T10:00:00+00:00")
    _commit(root, {"after.txt": "a later change nobody metered\n"},
            "2026-07-01T11:30:00+00:00")
    # `project` is what confirms a call belongs to THIS repo (an unstamped call is
    # *unconfirmable*, not adopted — `commitjoin`), so these are written directly
    # rather than through `_call`, which predates that axis.
    for i, ts in enumerate(("2026-07-01T09:20:00Z", "2026-07-01T09:50:00Z")):
        ledger.append(paths.Footprint(root).calls, schema.make_call(
            route="chat", provider="anthropic", model="claude-sonnet-4-6",
            tokens_in=12000, tokens_out=900, cached_in=4000, cache_write_in=500,
            agent="claude-code", session="s_hr1", project=root.name, ts=ts,
            call_id=f"c_hr{i}"))
    from cage import originrecord
    originrecord.record_transcript(root, sha=c2, files=["mod.py"], agent="claude-code",
                                   lines_added=5, lines_removed=0, session_id="s_hr1",
                                   suggested=4, kept=3, kept_modified=1, agent_lines=3)


def commits_bare(root: Path) -> None:
    """A repo with commits and an entirely empty ledger — every row refuses."""
    git_repo(root)
    _commit(root, {"only.txt": "one commit, nothing metered at all\n"},
            "2026-07-01T09:00:00+00:00")
