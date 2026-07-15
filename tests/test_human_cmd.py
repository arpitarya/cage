"""Stage-4 read surfaces: cage human / matrix --human / trend (criteria 3,4,5,6,9)."""
from __future__ import annotations

import pytest

from cage import (cli, demo, humanview, matrix, metering, policy, schema, trend)


# ── criterion 4 — matrix without --human is byte-identical to today
def test_matrix_no_human_flag_identical_to_demo(seeded):
    root, _ = seeded
    pol = policy.load(None)
    metering.record_human(task=demo.TASK, task_type="feature", root=root)  # add a human receipt
    plain = matrix.render_matrix(matrix.matrix(root, demo.TASK, pol))
    assert "human" not in plain  # the human receipt never leaks into the tool matrix
    assert "vs human" not in plain


# ── criterion 4 — anchor is the most expensive row; vs-human consistent
def test_matrix_human_anchor_is_most_expensive(seeded):
    root, _ = seeded
    pol = policy.load(None)
    metering.record_human(task=demo.TASK, task_type="feature", root=root)
    data = matrix.matrix(root, demo.TASK, pol, human=True)
    assert data["human"]["usd"] == 180.0  # 120 min @ $90
    # every agent row costs less than the human anchor
    assert all(r["cost_usd"] < data["human"]["usd"] for r in data["rows"])


# ── criterion 3 — cage human totals reconcile; --json == table numbers
def test_human_totals_reconcile(seeded):
    root, _ = seeded
    pol = policy.load(None)
    metering.record_human(task=demo.TASK, task_type="feature", agent="claude-code", root=root)
    data = humanview.rollup(root, pol)
    a = data["agents"]["claude-code"]
    assert a["saved_usd"] == pytest.approx(a["human_usd"] - a["agent_usd"], abs=1e-6)


# ── criterion 5 — no minutes/type/usd → global default, estimated, low confidence
def test_human_record_default_fallback(proj):
    metering._policy_for.cache_clear()
    rid = metering.record_human(task="t-default", root=proj)
    assert rid  # recorded
    from cage import human, ledger
    rc = [r for r in ledger.receipts(proj) if r["tool"] == "human"][0]
    usd, method, conf = human.human_alternative_usd(rc, policy.load(None))
    assert (usd, method, conf) == (80.0, "estimated", 0.3)  # 60 min @ $80
    assert method != "measured"


# ── criterion 6 — re-recording the same (task, call) is idempotent (no double count)
def test_human_record_idempotent(proj):
    metering._policy_for.cache_clear()
    first = metering.record_human(task="t1", call="c_1", minutes=90, root=proj)
    again = metering.record_human(task="t1", call="c_1", minutes=90, root=proj)
    assert first and not again  # second is a no-op
    from cage import ledger
    humans = [r for r in ledger.receipts(proj) if r["tool"] == "human"]
    assert len(humans) == 1


# ── criterion 9 — negative time saved when the agent ran longer than the human estimate
def test_negative_time_saved_embarrasses_the_agent(proj):
    metering._policy_for.cache_clear()
    # a 5-minute human bugfix the agent thrashed on for an hour (wall-clock span)
    metering.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=10, tokens_out=10, task="thrash", agent="claude",
                         ts="2026-06-19T10:00:00Z", root=proj)
    metering.record_call(route="r", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=10, tokens_out=10, task="thrash", agent="claude",
                         ts="2026-06-19T11:00:00Z", root=proj)  # 60 min later
    metering.record_human(task="thrash", minutes=5, agent="claude", root=proj)
    data = humanview.rollup(proj, policy.load(None))
    assert data["agents"]["claude"]["saved_min"] < 0  # human 5 min − agent ~60 min


# ── CLI smoke: the three new subcommands dispatch and exit 0
def test_cli_human_trend_dispatch(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["demo"]) == 0
    assert cli.main(["human", "record", "--task", demo.TASK, "--type", "feature"]) == 0
    assert cli.main(["human", "show"]) == 0
    assert cli.main(["human", "show", "--json"]) == 0
    assert cli.main(["insights", "trend", "--by", "month"]) == 0
    assert cli.main(["insights", "matrix", "--human"]) == 0
    out = capsys.readouterr().out
    assert "rate source" in out
