"""Derived human-attention minutes (plan §4.10): gap_ms capture, capped
derivation, attested-beats-derived precedence, calibration, and the total-cost
views — every number exact, every derive deterministic."""
from __future__ import annotations

import json

import pytest

from cage import (attention, calibration, cli, compare, hooks, humanview, ledger,
                  metering, policy, schema, tasks, transcript, trend, verdict)

POL = {"human": {"rate_usd_per_hr": 60.0}}  # $1/min — makes USD arithmetic readable
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")


def _call(root, tid, gap_ms=None, ts="2026-06-14T10:00:00Z", session=""):
    row = schema.make_call(tokens_in=1000, tokens_out=100, task=tid,
                           session=session or f"s-{tid}", ts=ts, gap_ms=gap_ms, **M)
    assert ledger.append_row(root, "calls", row)
    return row


# ── capture: gap_ms parsing from a Claude transcript ─────────────────────────

def _rec(kind: str, ts: str, usage: bool = True, uuid: str = "", **extra) -> str:
    msg = {"role": kind, "content": "[stripped]"}
    if kind == "assistant":
        msg = {"role": "assistant", "model": "claude-opus-4-8"}
        if usage:
            msg["usage"] = {"input_tokens": 10, "output_tokens": 5}
    rec = {"type": kind, "timestamp": ts, "message": msg, **extra}
    if uuid:
        rec["uuid"] = uuid
    return json.dumps(rec)


def test_gap_stamped_between_assistant_end_and_next_human_turn(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text("\n".join([
        _rec("user", "2026-06-14T10:00:00Z"),
        _rec("assistant", "2026-06-14T10:00:05Z", uuid="a1"),   # first call: no gap
        _rec("user", "2026-06-14T10:01:35Z"),                    # 90s after a1
        _rec("assistant", "2026-06-14T10:01:40Z", uuid="a2"),
    ]) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert "gap_ms" not in rows[0]          # no previous assistant turn — absent, not 0
    assert rows[1]["gap_ms"] == 90_000


def test_tool_result_meta_and_sidechain_user_turns_never_gap(tmp_path):
    tool_result = json.dumps({"type": "user", "timestamp": "2026-06-14T10:03:00Z",
                              "message": {"role": "user", "content":
                                          [{"type": "tool_result", "content": "x"}]}})
    meta = _rec("user", "2026-06-14T10:03:10Z", isMeta=True)
    side = _rec("user", "2026-06-14T10:03:20Z", isSidechain=True)
    tp = tmp_path / "s.jsonl"
    tp.write_text("\n".join([
        _rec("assistant", "2026-06-14T10:00:00Z", uuid="a1"),
        tool_result, meta, side,
        _rec("assistant", "2026-06-14T10:04:00Z", uuid="a2"),   # agentic loop, no human turn
    ]) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert all("gap_ms" not in r for r in rows)


def test_out_of_order_clock_drops_the_gap_never_fabricates(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text("\n".join([
        _rec("assistant", "2026-06-14T10:05:00Z", uuid="a1"),
        _rec("user", "2026-06-14T10:04:00Z"),                    # before the assistant end
        _rec("assistant", "2026-06-14T10:06:00Z", uuid="a2"),
    ]) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert all("gap_ms" not in r for r in rows)


def test_gap_spent_on_first_call_only(tmp_path):
    # One human turn, then a multi-call agentic loop: only the first call carries the gap.
    tp = tmp_path / "s.jsonl"
    tp.write_text("\n".join([
        _rec("assistant", "2026-06-14T10:00:00Z", uuid="a1"),
        _rec("user", "2026-06-14T10:00:30Z"),
        _rec("assistant", "2026-06-14T10:00:40Z", uuid="a2"),
        _rec("assistant", "2026-06-14T10:00:50Z", uuid="a3"),
    ]) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert rows[1]["gap_ms"] == 30_000 and "gap_ms" not in rows[2]


def test_gap_never_enters_the_composite_id(tmp_path):
    # Two uuid-less transcripts, identical but for a preceding exchange that adds a
    # gap: the usage turn's composite id must be identical (gap_ms is not id input).
    plain = tmp_path / "a.jsonl"
    plain.write_text(_rec("assistant", "2026-06-14T10:02:00Z", uuid="") + "\n",
                     encoding="utf-8")
    gapped = tmp_path / "b.jsonl"
    gapped.write_text("\n".join([
        _rec("assistant", "2026-06-14T10:00:00Z", usage=False, uuid="x"),
        _rec("user", "2026-06-14T10:01:00Z"),
        _rec("assistant", "2026-06-14T10:02:00Z", uuid=""),
    ]) + "\n", encoding="utf-8")
    (a,) = transcript.parse_calls(plain, session="same")
    rows = transcript.parse_calls(gapped, session="same")
    b = rows[-1]
    assert b["gap_ms"] == 60_000 and "gap_ms" not in a
    assert a["id"] == b["id"]


def test_reimport_with_gap_ms_is_idempotent(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text("\n".join([
        _rec("assistant", "2026-06-14T10:00:00Z", uuid="a1"),
        _rec("user", "2026-06-14T10:00:30Z"),
        _rec("assistant", "2026-06-14T10:00:40Z", uuid="a2"),
    ]) + "\n", encoding="utf-8")
    assert hooks.append_new(tmp_path, transcript.parse_calls(tp, session="s")) == 2
    assert hooks.append_new(tmp_path, transcript.parse_calls(tp, session="s")) == 0
    calls = ledger.calls(tmp_path)
    assert len(calls) == 2
    assert sum(1 for c in calls if c.get("gap_ms") == 30_000) == 1


# ── derivation: exact capped minutes, policy-tunable cap ─────────────────────

def test_capped_minutes_exact_with_cap_boundary(proj):
    _call(proj, "t", gap_ms=60_000)        # 1 min
    _call(proj, "t", gap_ms=600_000)       # exactly the 10-min cap
    _call(proj, "t", gap_ms=1_200_000)     # 20 min → capped to 10
    _call(proj, "t")                       # legacy row, no field → 0
    assert attention.capped_minutes(ledger.calls(proj), POL) == 21.0


def test_idle_cap_is_policy_preferred_and_rederives(proj):
    _call(proj, "t", gap_ms=1_200_000)     # 20 min of raw gap
    assert attention.capped_minutes(ledger.calls(proj), POL) == 10.0   # constants fallback
    tighter = {"human": {"idle_cap_minutes": 2}}
    assert attention.idle_cap_minutes(tighter) == 2.0
    # same ledger, new policy ⇒ new derive — nothing rewritten
    assert attention.capped_minutes(ledger.calls(proj), tighter) == 2.0


def test_derived_by_task_sums_across_month_shards(proj):
    _call(proj, "xmonth", gap_ms=120_000, ts="2026-06-28T10:00:00Z")
    _call(proj, "xmonth", gap_ms=180_000, ts="2026-07-02T10:00:00Z")  # next shard
    assert attention.derived_by_task(proj, POL)["xmonth"] == 5.0


def test_derivation_is_deterministic(proj):
    _call(proj, "t", gap_ms=90_000)
    metering.record_human(task="t", minutes=30, root=proj)
    one = humanview.render_human(humanview.rollup(proj, POL))
    two = humanview.render_human(humanview.rollup(proj, POL))
    assert one == two


# ── precedence: attested beats derived, never summed ─────────────────────────

def test_attested_beats_derived_and_is_never_summed(proj):
    _call(proj, "t", gap_ms=300_000)                       # 5 derived minutes
    metering.record_human(task="t", minutes=30, root=proj)  # attested 30
    att = attention.resolve(proj, POL, task_ids=["t"])
    assert att["minutes"] == 30.0                          # attested wins outright
    assert att["attested_min"] == 30.0
    assert att["derived_min"] == 0.0                       # not double-counted
    assert att["derived_ref_min"] == 5.0                   # kept as reference only
    assert att["method"] == "estimated"


def test_derived_only_task_uses_derived_and_stays_estimated(proj):
    _call(proj, "t", gap_ms=300_000)
    att = attention.resolve(proj, POL, task_ids=["t"])
    assert att["minutes"] == 5.0 and att["sources"] == ["derived"]
    assert att["method"] == attention.METHOD == "estimated"
    assert attention.LABEL == "derived (turn-gaps, capped)"


def test_no_signal_resolves_to_explicit_absence(proj):
    _call(proj, "t")  # no gap_ms, no attested
    att = attention.resolve(proj, POL, task_ids=["t"])
    assert att["minutes"] == 0.0 and att["sources"] == [] and att["method"] == ""
    line = attention.render_total_cost(attention.total_cost(1.0, att, POL))
    assert "no attested minutes and no turn-gap data" in line


# ── outcome --minutes: the attestation friction-drop ─────────────────────────

def test_outcome_minutes_writes_the_attested_receipt(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    _call(proj, "t1")
    assert cli.main(["human", "outcome", "t1", "--minutes", "25"]) == 0
    humans = [r for r in ledger.receipts(proj) if r["tool"] == "human"]
    assert len(humans) == 1
    assert humans[0]["unit"] == "minutes" and humans[0]["raw_alternative"] == 25.0
    assert humans[0]["method"] == "estimated"
    assert cli.main(["human", "outcome", "t1", "--minutes", "25"]) == 0   # replay → no double count
    assert len([r for r in ledger.receipts(proj) if r["tool"] == "human"]) == 1
    assert "no double count" in capsys.readouterr().out


# ── views: human / trend separate the sources; compare/verdict total cost ────

def test_human_view_shows_derived_block_separately(proj):
    _call(proj, "t", gap_ms=120_000)
    metering.record_human(task="t", minutes=30, agent="claude-code", root=proj)
    text = humanview.render_human(humanview.rollup(proj, POL))
    assert "derived attention" in text and "never summed" in text
    assert "cap 10 min" in text and "estimated" in text


def test_human_view_absence_is_explicit_without_gap_data(proj):
    metering.record_human(task="t", minutes=30, agent="claude-code", root=proj)
    text = humanview.render_human(humanview.rollup(proj, POL))
    assert "no turn-gap data (gap_ms)" in text


def test_trend_renders_attention_as_its_own_section(proj):
    _call(proj, "t", gap_ms=300_000, ts="2026-06-14T10:00:00Z")
    data = trend.series(proj, POL, by="week")
    assert data["attention"] == {"2026-W24": 5.0}
    text = trend.render_trend(data)
    assert "derived attention" in text and "2026-W24  5 min" in text


def test_compare_total_cost_line_and_agent_only(proj):
    for i in range(5):
        tid = f"t{i}"
        _call(proj, tid, gap_ms=60_000, ts=f"2026-06-1{i}T10:00:00Z")
        tasks.record(proj, tid, outcome="ok", snapshot=False)
    d = compare.summarize(proj, POL)
    tc = d["total_cost"]
    assert tc["minutes"] == 5.0 and tc["human_usd"] == 5.0    # 5 min @ $60/hr
    assert tc["method"] == "estimated"
    assert "total cost: agent" in compare.render_compare(d)
    plain = compare.summarize(proj, POL, agent_only=True)
    assert "total_cost" not in plain
    assert "total cost" not in compare.render_compare(plain)


def test_study_report_total_cost_line_and_agent_only(proj):
    from cage import study
    study.start(proj, "baseline", ts="2026-06-01T00:00:00Z")
    _call(proj, "t", gap_ms=120_000, ts="2026-06-02T10:00:00Z")
    d = study.summarize(proj, POL)
    assert d["total_cost"]["minutes"] == 2.0
    assert "total cost: agent" in study.render_study(d)
    assert "total_cost" not in study.summarize(proj, POL, agent_only=True)


def test_verdict_total_cost_line_and_agent_only(proj):
    _call(proj, "t", gap_ms=120_000)
    d = verdict.compose(proj, POL, "ghost")
    assert d["total_cost"]["minutes"] == 2.0
    assert "total cost: agent" in verdict.render_verdict(d)
    d2 = verdict.compose(proj, POL, "ghost", agent_only=True)
    assert "total_cost" not in d2


# ── calibration --human: measured accuracy or refusal ────────────────────────

def test_calibration_human_refuses_below_min_n(proj):
    _call(proj, "t", gap_ms=300_000)
    metering.record_human(task="t", minutes=10, root=proj)
    d = calibration.summarize_human(proj, POL)
    assert d["ok"] is False and d["n"] == 1
    assert "insufficient data" in calibration.render_calibration_human(d)


def test_calibration_human_exact_ratio_distribution(proj):
    # 5 tasks, derived = 5 min each, attested 4/5/10/20/5 → ratios 1.25/1/0.5/0.25/1
    for i, attested in enumerate((4, 5, 10, 20, 5)):
        tid = f"t{i}"
        _call(proj, tid, gap_ms=300_000, ts=f"2026-06-1{i}T10:00:00Z")
        metering.record_human(task=tid, minutes=attested, root=proj)
    d = calibration.summarize_human(proj, POL)
    assert d["ok"] and d["n"] == 5 and d["method"] == "measured"
    assert d["ratio"]["median"] == 1.0
    assert d["ratio"] == {"median": 1.0, "q1": 0.5, "q3": 1.0}
    text = calibration.render_calibration_human(d)
    assert "median 1" in text and "measured" in text


# ── policy: bundled default keeps the constant live ──────────────────────────

def test_bundled_policy_leaves_idle_cap_to_the_constant():
    pol = policy.load(None)
    from cage.constants import IDLE_CAP_MINUTES
    assert attention.idle_cap_minutes(pol) == float(IDLE_CAP_MINUTES) == 10.0
