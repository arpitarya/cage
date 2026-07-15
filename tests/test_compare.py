"""`cage insights compare` + `cage/taskgroup.py` — measured stack comparison (roadmap P2).

Exact-number assertions over a hand-computed seeded ledger. Bundled policy
prices claude-opus-4-8 at $5 in / $25 out per MTok, so a task with 12,000 in +
500 out costs $0.0725 — every figure below derives from that row.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import clicmds, compare, ledger, policy, schema, taskgroup, tasks
from cage.constants import MIN_COMPARE_N
from cage.errors import CageError

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")


def _call(root, tid, tin, tout, ts, session=None):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=tin, tokens_out=tout, task=tid,
        session=session or (f"s-{tid}" if tid else ""), ts=ts, **_MODEL))


def _receipt(root, tid, tool, ts):
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=1000, actual=100, task=tid, ts=ts))


def _close(root, tid, ts, label=""):
    tasks.record(root, tid, outcome="ok", ts=ts, snapshot=False,
                 **({"label": label} if label else {}))


@pytest.fixture
def seeded(proj):
    """5 agent-only (totals 10.5k–14.5k tok) · 5 graphify (4.5k–6.5k, labelled
    `bugfix`, one spanning two month-shards) · 2 fux+graphify (refused) · one
    session-fallback call · one human receipt · one open task."""
    root = proj
    # agent-only: single 10k..14k-in call each; the median task (plain-2) is
    # split across two direct calls + one session-fallback call (task="") that
    # lands inside its window — total still 12,000 in + 500 out.
    for i, tin in enumerate((10_000, 11_000, 13_000, 14_000)):
        tid = f"plain-{(0, 1, 3, 4)[i]}"
        _call(root, tid, tin, 500, f"2026-06-1{i}T10:00:00Z")
        _close(root, tid, f"2026-06-1{i}T18:00:00Z")
    _call(root, "plain-2", 5_500, 250, "2026-06-05T10:00:00Z")
    _call(root, "plain-2", 5_500, 250, "2026-06-05T12:00:00Z")
    _call(root, "", 1_000, 0, "2026-06-05T11:00:00Z", session="s-plain-2")  # fallback join
    _close(root, "plain-2", "2026-06-05T18:00:00Z")
    _receipt(root, "plain-0", "human", "2026-06-10T10:00:00Z")  # Tier-1 anchor ≠ stack tool

    # graphify: totals 4.5k..6.5k; the median task (graph-2) spans June + July shards.
    for i, tin in enumerate((4_000, 4_500, 5_500, 6_000)):
        tid = f"graph-{(0, 1, 3, 4)[i]}"
        _call(root, tid, tin, 500, f"2026-06-2{i}T10:00:00Z")
        _receipt(root, tid, "graphify", f"2026-06-2{i}T10:00:00Z")
        _close(root, tid, f"2026-06-2{i}T18:00:00Z", label="bugfix")
    _call(root, "graph-2", 3_000, 250, "2026-06-28T10:00:00Z")
    _call(root, "graph-2", 2_000, 250, "2026-07-02T10:00:00Z")  # cross-month shard
    _receipt(root, "graph-2", "graphify", "2026-06-28T10:00:00Z")
    _close(root, "graph-2", "2026-07-02T18:00:00Z", label="bugfix")

    # two-task group → refused, never numbered
    for i, tin in enumerate((3_000, 3_200)):
        tid = f"both-{i}"
        _call(root, tid, tin, 500, f"2026-06-0{i + 1}T10:00:00Z")
        _receipt(root, tid, "graphify", f"2026-06-0{i + 1}T10:00:00Z")
        _receipt(root, tid, "fux", f"2026-06-0{i + 1}T10:00:00Z")
        _close(root, tid, f"2026-06-0{i + 1}T18:00:00Z")

    _call(root, "open-1", 99_000, 500, "2026-06-30T10:00:00Z")  # never closed → excluded
    return root, policy.load(None)


def _group(d, stack):
    return next(g for g in d["groups"] if g["stack"] == stack)


def test_group_medians_exact(seeded):
    root, pol = seeded
    d = compare.summarize(root, pol)
    plain = _group(d, "agent-only")
    assert plain["n"] == 5 and plain["ok"]
    assert plain["tokens"] == {"median": 12_500.0, "q1": 11_500.0, "q3": 13_500.0}
    assert plain["usd"] == {"median": 0.0725, "q1": 0.0675, "q3": 0.0775}
    graph = _group(d, "graphify")
    assert graph["n"] == 5  # includes the cross-month task — shards concatenated
    assert graph["tokens"]["median"] == 5_500.0
    assert graph["usd"] == {"median": 0.0375, "q1": 0.035, "q3": 0.04}


def test_small_group_refused_never_numbered(seeded):
    root, pol = seeded
    d = compare.summarize(root, pol)
    both = _group(d, "fux+graphify")
    assert both["ok"] is False
    assert both["reason"] == f"insufficient data (n=2 < {MIN_COMPARE_N})"
    assert "tokens" not in both and "usd" not in both
    assert all(dl["stack"] != "fux+graphify" for dl in d["deltas"])  # no delta either
    assert "insufficient data (n=2 < 5)" in compare.render_compare(d)


def test_delta_estimated_with_caveat(seeded):
    root, pol = seeded
    d = compare.summarize(root, pol)
    (dl,) = d["deltas"]
    assert dl == {"stack": "graphify", "baseline": "agent-only",
                  "d_median_tokens": -7_000.0, "d_median_usd": -0.035,
                  "method": "estimated"}
    text = compare.render_compare(d)
    assert "-7,000 tok · -$0.0350 per task (median, estimated)" in text
    assert "not a controlled experiment" in text  # the observational caveat, always


def test_open_task_excluded(seeded):
    root, pol = seeded
    assert all(s["task"] != "open-1" for s in taskgroup.stats(root, pol))


def test_human_receipt_not_a_stack_tool(seeded):
    root, pol = seeded
    stats = {s["task"]: s for s in taskgroup.stats(root, pol)}
    assert stats["plain-0"]["stack"] == "agent-only"


def test_session_fallback_join_is_windowed(seeded):
    root, pol = seeded
    stats = {s["task"]: s for s in taskgroup.stats(root, pol)}
    assert stats["plain-2"]["tokens"] == 12_500  # 11,500 direct + 1,000 adopted
    assert stats["plain-2"]["calls"] == 3


def test_by_label_grouping_and_filter(seeded):
    root, pol = seeded
    d = compare.summarize(root, pol, by=("stack", "label"))
    keys = {(g["stack"], g["label"]) for g in d["groups"]}
    assert ("graphify", "bugfix") in keys and ("agent-only", "") in keys
    assert d["deltas"] == []  # labels differ → no shared-key baseline, honestly no delta
    filtered = compare.summarize(root, pol, label="bugfix")
    assert [g["stack"] for g in filtered["groups"]] == ["graphify"]


def test_truncated_tail_tolerated(seeded):
    root, pol = seeded
    before = compare.summarize(root, pol)
    shard = sorted(root.joinpath(".cage", "ledger").glob("calls-2026-07.jsonl"))[0]
    with shard.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "c_torn", "ts": "2026-07-0')  # crash mid-append
    assert compare.summarize(root, pol) == before


def test_deterministic_byte_identical(seeded):
    root, pol = seeded
    a = compare.render_compare(compare.summarize(root, pol))
    b = compare.render_compare(compare.summarize(root, pol))
    assert a == b


def test_no_closed_tasks_explains(proj):
    text = compare.render_compare(compare.summarize(proj, policy.load(None)))
    assert "No closed tasks to compare" in text and "cage human outcome" in text


def test_cli_json_envelope(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    args = SimpleNamespace(json=True, by="stack", scope=None, label=None)
    assert clicmds.cmd_compare(args) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "cage.v1" and payload["command"] == "compare"
    assert payload["data"]["min_n"] == MIN_COMPARE_N


def test_outcome_label_guard(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    (proj / ".cage").mkdir(exist_ok=True)
    ok = SimpleNamespace(task="t1", redo=False, label="bugfix")
    assert clicmds.cmd_outcome(ok) == 0
    assert "label: bugfix" in capsys.readouterr().out
    assert tasks.read(proj)["t1"]["label"] == "bugfix"
    for bad in ("two words", "a/b/path", "-leading", "x" * 33):
        with pytest.raises(CageError, match="label must be one short token"):
            clicmds.cmd_outcome(SimpleNamespace(task="t1", redo=False, label=bad))
