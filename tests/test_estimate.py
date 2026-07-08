"""`cage estimate` + `cage calibration` (roadmap P3) — exact-number assertions.

Same pricing ground as test_compare: bundled claude-opus-4-8 at $5/$25 per MTok.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from cage import calibration, clicmds, estimate, ledger, policy, schema, tasks
from cage.constants import MIN_ESTIMATE_N
from cage.errors import CageError

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")


def _run_task(root, tid, tin, ts, close=True, label="bugfix", agent_name="claude"):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=tin, tokens_out=500, task=tid, session=f"s-{tid}", ts=ts, **_MODEL))
    if close:
        tasks.record(root, tid, outcome="ok", ts=ts, snapshot=False, label=label,
                     agents=[agent_name])


@pytest.fixture
def seeded(proj):
    """5 closed `bugfix` tasks, totals 10.5k–14.5k tok → band median 12,500,
    IQR 11,500–13,500, USD median $0.0725."""
    for i, tin in enumerate((10_000, 11_000, 12_000, 13_000, 14_000)):
        _run_task(proj, f"hist-{i}", tin, f"2026-06-1{i}T10:00:00Z")
    return proj, policy.load(None)


def test_band_exact_and_modeled(seeded):
    root, pol = seeded
    d = estimate.band(root, pol, label="bugfix")
    assert d["ok"] and d["n"] == 5 and d["method"] == "modeled"
    assert d["tokens"] == {"median": 12_500.0, "q1": 11_500.0, "q3": 13_500.0}
    assert d["usd"] == {"median": 0.0725, "q1": 0.0675, "q3": 0.0775}
    text = estimate.render_estimate(d)
    assert "median 12,500 · IQR 11,500–13,500" in text
    assert "modeled" in text and "never an invoice" in text
    assert "none self-reported" in text  # the estimator never claims confidence


def test_refusal_below_min_n(seeded):
    root, pol = seeded
    d = estimate.band(root, pol, label="unseen")
    assert d["ok"] is False and d["n"] == 0
    assert f"n=0 < {MIN_ESTIMATE_N}" in d["reason"]
    assert "tokens" not in d  # refusal carries no numbers at all
    assert "refusing to print a band over noise" in estimate.render_estimate(d)


def test_agent_key_matches_task_agents(seeded):
    root, pol = seeded
    assert estimate.band(root, pol, agent="claude")["n"] == 5
    assert estimate.band(root, pol, agent="codex")["ok"] is False


def test_record_stamps_band_on_open_task(seeded):
    root, pol = seeded
    d = estimate.band(root, pol, label="bugfix")
    assert estimate.record(root, "new-task", d) is True
    row = tasks.read(root)["new-task"]
    assert row["est_tokens"] == 12_500.0 and row["est_usd"] == 0.0725
    assert row["est_n"] == 5
    assert (row["est_tokens_q1"], row["est_tokens_q3"]) == (11_500.0, 13_500.0)
    assert "outcome" not in row  # still open


def test_cli_record_refuses_closed_task_and_bad_band(seeded, monkeypatch):
    root, _ = seeded
    monkeypatch.chdir(root)
    with pytest.raises(CageError, match="already closed"):
        clicmds.cmd_estimate(SimpleNamespace(json=False, scope=None, label="bugfix",
                                             agent=None, record="hist-0"))
    with pytest.raises(CageError, match="cannot record"):
        clicmds.cmd_estimate(SimpleNamespace(json=False, scope=None, label="unseen",
                                             agent=None, record="new-task"))


def test_calibration_exact_hit_rate(seeded):
    root, pol = seeded
    d = estimate.band(root, pol, label="bugfix")
    estimate.record(root, "in-band", d)     # actual 12,600 → inside 11,500–13,500
    estimate.record(root, "over", d)        # actual 20,000 → outside
    estimate.record(root, "zero", d)        # closes with no calls → skipped, counted
    estimate.record(root, "open", d)        # never closes → skipped, counted
    _run_task(root, "in-band", 12_100, "2026-07-01T10:00:00Z")
    _run_task(root, "over", 19_500, "2026-07-02T10:00:00Z")
    tasks.record(root, "zero", outcome="ok", ts="2026-07-03T10:00:00Z", snapshot=False)
    c = calibration.summarize(root, pol)
    assert c["n"] == 2 and c["hits"] == 1 and c["hit_rate"] == 0.5
    assert c["method"] == "measured"
    assert [t["ratio"] for t in c["tasks"]] == [1.008, 1.6]
    assert c["skipped"] == {"open": 1, "zero-actual": 1, "no-band": 0}
    text = calibration.render_calibration(c)
    assert "in-band hit-rate: 50% (1/2" in text
    assert "estimates landed in-band 50% of the time (n=2)" in text
    assert "skipped: 1 open · 1 zero-actual · 0 without band bounds" in text


def test_legacy_estimate_without_band_skipped_not_scored(seeded):
    root, pol = seeded
    tasks.record(root, "legacy", est_tokens=12_500.0, est_usd=0.07, est_n=5,
                 snapshot=False)  # a pre-band row: point fields only
    _run_task(root, "legacy", 12_000, "2026-07-04T10:00:00Z")
    c = calibration.summarize(root, pol)
    assert c["n"] == 0 and c["skipped"]["no-band"] == 1


def test_calibration_empty_state_explains(proj):
    text = calibration.render_calibration(calibration.summarize(proj, policy.load(None)))
    assert "no closed tasks with recorded estimates yet" in text
    assert "cage estimate --record" in text


def test_deterministic(seeded):
    root, pol = seeded
    assert estimate.band(root, pol, label="bugfix") == estimate.band(root, pol, label="bugfix")
    assert calibration.summarize(root, pol) == calibration.summarize(root, pol)


def test_cli_json_envelopes(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    assert clicmds.cmd_estimate(SimpleNamespace(json=True, scope=None, label="bugfix",
                                                agent=None, record=None)) == 0
    est = json.loads(capsys.readouterr().out)
    assert est["schemaVersion"] == "cage.v1" and est["command"] == "estimate"
    assert est["data"]["method"] == "modeled"
    assert clicmds.cmd_calibration(SimpleNamespace(json=True)) == 0
    cal = json.loads(capsys.readouterr().out)
    assert cal["command"] == "calibration" and cal["data"]["method"] == "measured"