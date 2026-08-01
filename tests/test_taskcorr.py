"""Phase 4: best-effort `task` correlation (import-ledger plan §4) — gated,
disabled-by-default, derive-time, its own method/confidence, blocking min-n gate,
overlap → smallest task id, and never mutates the ledger.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from cage import constants, ledger, schema, taskcorr, tasks


def _root(tmp_path):
    (tmp_path / ".cage").mkdir()
    return tmp_path


def _closed_task(root, tid, ts):
    tasks.record(root, tid, outcome="done", ts=ts, snapshot=False)


def _call(root, cid, session, ts, task=""):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=10, tokens_out=5, session=session, task=task, ts=ts, call_id=cid))


def _seed_correlatable(root, n_empty):
    """One closed task T1 whose task-id calls span session s1 10:00–10:10, plus
    ``n_empty`` empty-task calls in-window on s1 that should correlate."""
    _closed_task(root, "T1", "2026-06-14T10:00:00Z")
    _call(root, "c_anchor0", "s1", "2026-06-14T10:00:00Z", task="T1")   # window start
    _call(root, "c_anchor9", "s1", "2026-06-14T10:10:00Z", task="T1")   # window end
    for i in range(n_empty):
        _call(root, f"c_e{i}", "s1", f"2026-06-14T10:0{i+1}:00Z")       # in-window, empty task


def test_disabled_by_default_returns_nothing(tmp_path):
    from cage import policy
    root = _root(tmp_path)
    _seed_correlatable(root, 6)
    res = taskcorr.correlate(root, policy.load(None))
    assert res.enabled is False and res.correlations == []
    assert "disabled" in res.reason


def test_enabled_below_min_n_blocks(tmp_path, monkeypatch):
    from cage import policy
    monkeypatch.setenv("CAGE_TASK_CORRELATION", "1")
    root = _root(tmp_path)
    _seed_correlatable(root, constants.MIN_TASK_CORRELATION_N - 1)  # one short of the gate
    res = taskcorr.correlate(root, policy.load(None))
    assert res.enabled is True and res.blocked is True and res.correlations == []
    assert "INSUFFICIENT DATA" in res.reason


def test_enabled_at_gate_correlates_with_estimated_tag(tmp_path, monkeypatch):
    from cage import policy
    monkeypatch.setenv("CAGE_TASK_CORRELATION", "1")
    root = _root(tmp_path)
    _seed_correlatable(root, constants.MIN_TASK_CORRELATION_N)      # exactly the gate
    res = taskcorr.correlate(root, policy.load(None))
    assert res.enabled and not res.blocked
    assert len(res.correlations) == constants.MIN_TASK_CORRELATION_N
    for c in res.correlations:
        assert c.task == "T1" and c.session == "s1"
        assert c.method == "estimated"   # never measured/modeled — it's a heuristic
        assert c.confidence == constants.TASK_CORRELATION_CONFIDENCE
    # the anchoring task-id calls are ground truth, never re-emitted as correlations
    assert not any(c.call_id.startswith("c_anchor") for c in res.correlations)


def test_overlap_resolves_to_smallest_task_id(tmp_path, monkeypatch):
    # Two closed tasks whose windows both cover the call → the lexicographically smallest
    # task id wins (a total, stable order — mirrors taskgroup's contract).
    from cage import policy
    monkeypatch.setenv("CAGE_TASK_CORRELATION", "1")
    root = _root(tmp_path)
    for tid in ("T_b", "T_a"):
        _closed_task(root, tid, "2026-06-14T10:00:00Z")
        _call(root, f"c_anchor_{tid}", "s1", "2026-06-14T10:00:00Z", task=tid)
    for i in range(constants.MIN_TASK_CORRELATION_N):
        _call(root, f"c_e{i}", "s1", "2026-06-14T10:00:00Z")  # in both windows
    res = taskcorr.correlate(root, policy.load(None))
    assert res.correlations and all(c.task == "T_a" for c in res.correlations)  # smallest id


def test_correlation_never_mutates_the_ledger(tmp_path, monkeypatch):
    from cage import policy
    monkeypatch.setenv("CAGE_TASK_CORRELATION", "1")
    root = _root(tmp_path)
    _seed_correlatable(root, constants.MIN_TASK_CORRELATION_N)
    before = [dict(c) for c in ledger.calls(root)]
    taskcorr.correlate(root, policy.load(None))
    after = ledger.calls(root)
    assert after == before  # derive-time only — the empty `task` fields stay empty
    assert all(not c.get("task") for c in after if c["id"].startswith("c_e"))


def test_is_deterministic(tmp_path, monkeypatch):
    from cage import policy
    monkeypatch.setenv("CAGE_TASK_CORRELATION", "1")
    root = _root(tmp_path)
    _seed_correlatable(root, constants.MIN_TASK_CORRELATION_N)
    a = taskcorr.correlate(root, policy.load(None)).correlations
    b = taskcorr.correlate(root, policy.load(None)).correlations
    assert a == b  # same ledger ⇒ same correlation, in the same order
