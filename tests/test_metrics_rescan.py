"""METRICS-CURSOR-BLIND — `cage import --rescan-metrics`, the per-agent metrics backfill.

The defect this closes, measured at the METRICS-PRIMARY P0 gate (2026-08-14): the three
metric kinds ride the calls sweep's **cursor-filtered** file list, so every store file
ingested before those routes shipped is dropped by `_scan` as `cursor-unchanged` and its
metric rows are never written — permanently. On the maintainer's machine that was 102
copilot rows and 56 kiro rows on disk with zero captured.

What this file pins:

1. The blindness is real — a store already at high-water yields no metric rows on a plain
   re-sweep — and `--rescan-metrics` recovers exactly those rows.
2. **The rescan advances no cursor.** The safety half: handed a store's full match set,
   the metric legs must not stamp the *calls* cursor, or a backfill of one kind would
   make another kind's rows permanently invisible. `--since` is the sharp case.
3. Re-running the rescan is idempotent (row-id dedupe, not the cursor).
4. The summary line always states the outcome, **including when it is zero** — a
   silently-skipped store and an empty one are the confusion the flag exists to end.
5. Without the flag, capture is byte-identical to before.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import importcmd, ledger, paths

from srcseed import mkcage


def _args(**over):
    """The `cage import` arg shape, with both rescan flags defaulted off."""
    base = {"agent": "all", "since": None, "path": None, "project": None,
            "ledger": None, "quiet": True, "no_import": False,
            "rescan_graphify": False, "rescan_metrics": False}
    base.update(over)
    return type("A", (), base)()


def _vscode_store(path: Path, session: str, *reqs: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"kind": 0, "v": {"sessionId": session}}),
             json.dumps({"kind": 2, "k": ["requests"], "v": list(reqs)})]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _req(rid: str, **extra) -> dict:
    req = {"requestId": rid, "timestamp": 1755000000000, "modelId": "copilot/auto",
           "agent": {"extensionId": {"value": "github.copilot-chat"}},
           "promptTokens": 100, "completionTokens": 50}
    req.update(extra)
    return req


def _cli_events(path: Path, *shutdowns: tuple) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"type": "session.shutdown", "timestamp": ts, "data": data})
             for ts, data in shutdowns]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.fixture
def copilot_proj(proj, monkeypatch):
    """A scaffolded project with both always-on Copilot stores seeded."""
    home = proj / "copilot-home"
    vscode_home = proj / "vscode-user"
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.setenv("CAGE_VSCODE_USER", str(vscode_home))
    mkcage(proj)
    monkeypatch.chdir(proj)
    _vscode_store(vscode_home / "workspaceStorage" / "h1" / "chatSessions" / "sess.jsonl",
                  "sess", _req("req1", copilotCredits=0.44))
    _cli_events(home / "session-state" / "sessA" / "events.jsonl",
                ("2026-08-13T00:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 100,
                                                       "outputTokens": 40}}},
                  "totalPremiumRequests": 0.1}))
    return proj


def _drop_metric_shards(root: Path) -> int:
    """Delete the copilot metric shards — the stand-in for "the route shipped AFTER these
    stores were ingested". Nothing else is touched, so the calls cursor stays at
    high-water exactly as it would on a real upgrade."""
    shards = list(paths.Footprint(root).copilot_shards())
    for sh in shards:
        sh.unlink()
    return len(shards)


# ── 1 · the blindness, and the recovery ──────────────────────────────────────

def test_plain_resweep_is_cursor_blind_and_rescan_recovers(copilot_proj):
    """The whole defect in one test: after the stores are at high-water, a plain sweep
    can never re-derive their metric rows — and `--rescan-metrics` can."""
    root = copilot_proj
    importcmd.run(root, "all", _args())
    seeded = len(ledger.copilot_metrics_raw(root))
    assert seeded == 3, (
        "fixture yields one chat row, one verbatim cli row, and its cli-delta twin")

    # The stores are now cursor-pinned. Simulate the metric route shipping afterwards.
    assert _drop_metric_shards(root)
    assert ledger.copilot_metrics_raw(root) == []

    importcmd.run(root, "all", _args())
    assert ledger.copilot_metrics_raw(root) == [], (
        "a plain re-sweep must still be blind — if this passes rows, the fixture no "
        "longer reproduces METRICS-CURSOR-BLIND and the test below proves nothing")

    importcmd.run(root, "all", _args(rescan_metrics=True))
    assert len(ledger.copilot_metrics_raw(root)) == seeded


# ── 2 · the safety half: a rescan advances no cursor ─────────────────────────

def test_rescan_never_advances_the_calls_cursor(copilot_proj):
    """The load-bearing half of `metrics_scan_set`. A `--since` window hides a store from
    the calls leg; the rescan still parses it for metrics, and must NOT stamp the cursor
    — otherwise the later unfiltered sweep would skip it and those calls would be lost
    for good. A backfill of one kind must never blind another."""
    root = copilot_proj
    # Age both stores far outside any --since window the rescan run will use.
    old = 1_600_000_000  # 2020
    for f in root.rglob("*.jsonl"):
        if ".cage" not in f.parts:
            import os
            os.utime(f, (old, old))

    importcmd.run(root, "all", _args(since="1d", rescan_metrics=True))
    assert len(ledger.copilot_metrics_raw(root)) == 3, "rescan ignores --since by design"
    assert ledger.calls(root) == [], "--since should have hidden the stores from the calls leg"

    # The cursor must be untouched, so an unfiltered sweep still sees the calls.
    importcmd.run(root, "all", _args())
    assert ledger.calls(root), (
        "the rescan stamped the calls cursor — those calls are now permanently invisible")


# ── 3 · idempotency comes from row ids, not the cursor ───────────────────────

def test_rescan_twice_appends_nothing_the_second_time(copilot_proj):
    root = copilot_proj
    importcmd.run(root, "all", _args(rescan_metrics=True))
    first = len(ledger.copilot_metrics_raw(root))
    importcmd.run(root, "all", _args(rescan_metrics=True))
    assert len(ledger.copilot_metrics_raw(root)) == first


# ── 4 · the summary line always states the outcome ───────────────────────────

def test_summary_line_reports_what_was_backfilled(copilot_proj):
    root = copilot_proj
    importcmd.run(root, "all", _args())
    _drop_metric_shards(root)
    lines = importcmd.run(root, "all", _args(rescan_metrics=True))
    line = next(ln for ln in lines if "rescan-metrics" in ln)
    assert "recorded 3 new metric row(s)" in line
    assert "copilot +3" in line


def test_summary_line_says_zero_out_loud(copilot_proj):
    """A rescan that finds nothing must SAY so — looking like a no-op that ran is the
    exact confusion METRICS-CURSOR-BLIND was hidden behind."""
    root = copilot_proj
    importcmd.run(root, "all", _args(rescan_metrics=True))
    lines = importcmd.run(root, "all", _args(rescan_metrics=True))
    line = next(ln for ln in lines if "rescan-metrics" in ln)
    assert "no new metric rows" in line
    assert "copilot +0" in line


def test_no_summary_line_without_the_flag(copilot_proj):
    lines = importcmd.run(copilot_proj, "all", _args())
    assert not [ln for ln in lines if "rescan-metrics" in ln]


# ── 5 · the flag is opt-in: absent attr never trips it ───────────────────────

def test_capture_on_read_sweep_args_never_rescan():
    """`_SweepArgs` carries no `rescan_metrics`, so the capture-on-read path must resolve
    it as off through `getattr`'s default — a read that silently rescanned would make a
    derived number depend on when it was read."""
    assert getattr(importcmd._SweepArgs, "rescan_metrics", False) is False
    files = [Path("a.jsonl")]
    cursor = {"x": 1}
    got, cur = importcmd.metrics_scan_set(importcmd._SweepArgs(), Path("/nope"), "*",
                                          files, cursor)
    assert got is files and cur is cursor


# ── 6 · the cli-delta twin (METRICS-PRIMARY P0a) ─────────────────────────────

def test_cli_delta_rows_are_per_shutdown_deltas_not_cumulative(copilot_proj, monkeypatch):
    """Copilot's CLI store writes CUMULATIVE per-shutdown totals. The `cli` row keeps them
    verbatim; the `cli-delta` twin carries the per-shutdown delta, so the deltas SUM to
    the final cumulative and no shutdown is counted twice."""
    from cage import transcript
    home = copilot_proj / "copilot-home"
    ev = home / "session-state" / "sessB" / "events.jsonl"
    _cli_events(ev,
                ("2026-08-14T00:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 100,
                                                       "outputTokens": 10}}}}),
                ("2026-08-14T01:00:00Z",  # cumulative: includes the first shutdown
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 250,
                                                       "outputTokens": 25}}}}))
    rows = transcript.parse_copilot_cli_metrics(ev, "sessB")
    cum = [r for r in rows if r["source"] == "cli"]
    delta = [r for r in rows if r["source"] == "cli-delta"]
    assert [r["tokens_in"] for r in cum] == [100, 250], "verbatim capture is untouched"
    assert [r["tokens_in"] for r in delta] == [100, 150], "the twin is per-shutdown"
    assert sum(r["tokens_in"] for r in delta) == cum[-1]["tokens_in"], (
        "deltas must sum to the final cumulative — no undercount, no double-count")


def test_cli_delta_treats_a_counter_reset_as_the_delta(copilot_proj):
    """A cumulative counter that goes DOWN means the store reset, not that GitHub issued a
    refund. The new value IS the delta — clamping to 0 would discard real spend, the exact
    defect `parse_copilot_cli_calls` already documents."""
    from cage import transcript
    ev = copilot_proj / "copilot-home" / "session-state" / "sessC" / "events.jsonl"
    _cli_events(ev,
                ("2026-08-14T00:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 500,
                                                       "outputTokens": 50}}}}),
                ("2026-08-14T01:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 80,
                                                       "outputTokens": 8}}}}))
    delta = [r for r in transcript.parse_copilot_cli_metrics(ev, "sessC")
             if r["source"] == "cli-delta"]
    assert [r["tokens_in"] for r in delta] == [500, 80]


def test_cli_delta_rows_do_not_collapse_into_one(copilot_proj):
    """Each delta is per shutdown, so each needs its own collapse key — `request` carries
    the ordinal. Without it `ledger.copilot_metrics` would keep only the largest."""
    from cage import ledger, transcript
    ev = copilot_proj / "copilot-home" / "session-state" / "sessD" / "events.jsonl"
    _cli_events(ev,
                ("2026-08-14T00:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 100,
                                                       "outputTokens": 10}}}}),
                ("2026-08-14T01:00:00Z",
                 {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 250,
                                                       "outputTokens": 25}}}}))
    for r in transcript.parse_copilot_cli_metrics(ev, "sessD"):
        ledger.append_row(copilot_proj, "copilot", r)
    kept = [r for r in ledger.copilot_metrics(copilot_proj) if r["source"] == "cli-delta"]
    assert len(kept) == 2
    assert sorted(r["request"] for r in kept) == ["s000", "s001"]


def test_a_shutdown_that_added_nothing_emits_no_delta_row(copilot_proj):
    from cage import transcript
    ev = copilot_proj / "copilot-home" / "session-state" / "sessE" / "events.jsonl"
    payload = {"modelMetrics": {"gpt-4": {"usage": {"inputTokens": 100,
                                                    "outputTokens": 10}}}}
    _cli_events(ev, ("2026-08-14T00:00:00Z", payload),
                ("2026-08-14T01:00:00Z", payload))  # identical cumulative — nothing new
    delta = [r for r in transcript.parse_copilot_cli_metrics(ev, "sessE")
             if r["source"] == "cli-delta"]
    assert len(delta) == 1
