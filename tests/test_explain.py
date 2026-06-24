"""`cage query` — the deterministic explainer (handoff §2, acceptance 3 & 4).

Guards cage law: no network/LLM on the path, numbers are *live* (track the policy
rate, not a literal), and `--json` carries the same fields as the text render.
"""
from __future__ import annotations

import json

import pytest

from cage import cli, explain, metering, policy


# ── no network/LLM on the query path (mirrors fux's no-LLM guard) ──────────────
def test_query_makes_no_network_call(proj, monkeypatch, capsys):
    import socket

    def _boom(*a, **k):  # any socket construction would mean a network reach
        raise AssertionError("cage query opened a socket — must be $0/offline")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "how is human cost calculated"]) == 0
    assert "human-cost" in capsys.readouterr().out


# ── live numbers: the printed rate tracks CAGE_HUMAN_RATE, proving interpolation ─
def test_printed_rate_tracks_env_override(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    monkeypatch.setenv("CAGE_HUMAN_RATE", "250")
    metering._policy_for.cache_clear()
    assert cli.main(["query", "how do you cost a human"]) == 0
    out = capsys.readouterr().out
    assert "$250/hr" in out and "source: env" in out
    assert "$80/hr" not in out  # the policy default must NOT be hard-coded


def test_live_rate_in_payload(monkeypatch):
    pol = policy.load(None)
    e = explain._BY_ID["human-cost"]
    assert "$80/hr" in explain.payload(e, pol)["formula"]   # policy default
    monkeypatch.setenv("CAGE_HUMAN_RATE", "175")
    assert "$175/hr" in explain.payload(e, pol)["formula"]  # re-priced in place


# ── --json carries the same content as the text render ─────────────────────────
def test_json_has_same_fields_as_text(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "cost", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"id", "kind", "keywords", "summary", "formula", "code_refs",
                          "method_note", "plan_ref"}
    assert data["id"] == "cost"
    assert data["kind"] == "calculation"
    pol = policy.load(None)
    text = explain.render(explain._BY_ID["cost"], pol)
    assert data["formula"].splitlines()[0] in text  # same interpolated formula


# ── --list shows every seeded topic, one line each ─────────────────────────────
def test_list_covers_every_topic(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "--list"]) == 0
    out = capsys.readouterr().out
    for e in explain.REGISTRY:
        assert e.id in out


# ── an unmatched query suggests closest ids and never fabricates an answer ─────
def test_unmatched_suggests_not_guesses(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    rc = cli.main(["query", "what is the airspeed velocity of a swallow"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "no explainer matched" in out and "Closest topics" in out


# ── exact-id and natural-language both resolve deterministically ───────────────
@pytest.mark.parametrize("q,expected", [
    ("cost", "cost"),
    ("human-cost", "human-cost"),
    ("how is human cost calculated", "human-cost"),
    ("how do you cost a human", "human-cost"),
    ("how is the value getting calculated", "cost"),
    ("counterfactual permutation table", "matrix"),
    ("what are the method tags", "method-tags"),
    ("am i over budget", "budget"),
    ("how does cage work", "overview"),
])
def test_match_is_deterministic(q, expected):
    hits = explain.match(q)
    assert hits and hits[0].id == expected
    assert explain.match(q)[0].id == expected  # stable across calls


# ── concept layer ───────────────────────────────────────────────────────────────
def test_every_concept_entry_has_code_refs_and_plan_ref():
    for e in explain.REGISTRY:
        if e.kind == "concept":
            assert e.code_refs, f"{e.id} has no code_refs"
            assert e.plan_ref, f"{e.id} has no plan_ref"


def test_calculation_entries_unchanged_kind():
    calc_ids = {"cost", "saved", "marginal-attribution", "matrix", "human-cost",
                "time-saved", "roi", "token-heuristic", "confidence", "method-tags",
                "trend", "budget"}
    for e in explain.REGISTRY:
        if e.id in calc_ids:
            assert e.kind == "calculation"
    assert {e.id for e in explain.REGISTRY if e.kind == "calculation"} == calc_ids


def test_query_no_network_call_on_concept_topic(proj, monkeypatch, capsys):
    import socket

    def _boom(*a, **k):
        raise AssertionError("cage query opened a socket — must be $0/offline")

    monkeypatch.setattr(socket, "socket", _boom)
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "how does cage work"]) == 0
    assert "overview" in capsys.readouterr().out


def test_concept_json_payload_shape(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "data-flow", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "data-flow"
    assert data["kind"] == "concept"
    for key in ("id", "kind", "summary", "formula", "code_refs", "plan_ref"):
        assert key in data


def test_data_flow_prints_live_ledger_paths(proj, monkeypatch, capsys):
    """The ledger filenames in `cage query data-flow` come from `paths.Footprint`."""
    from cage import paths

    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "data-flow"]) == 0
    out = capsys.readouterr().out
    foot = paths.Footprint(proj)
    assert str(foot.calls) in out
    assert str(foot.receipts) in out
    assert str(foot.tasks) in out


def test_attribution_order_is_live_to_policy(proj, monkeypatch, capsys):
    """Reordering policy [tools].order changes the printed pipeline order."""
    cage_dir = proj / ".cage"
    cage_dir.mkdir()
    (cage_dir / "policy.toml").write_text(
        '[tools]\norder = ["cache", "fux", "graphify"]\n', encoding="utf-8"
    )
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "attribution"]) == 0
    out = capsys.readouterr().out
    assert "cache → fux → graphify" in out


def test_list_groups_by_kind(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "--list"]) == 0
    out = capsys.readouterr().out
    assert "calculation:" in out and "concept:" in out
    assert out.index("calculation:") < out.index("concept:")


def test_list_kind_filter(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "--list", "--kind", "concept"]) == 0
    out = capsys.readouterr().out
    assert "concept:" in out and "calculation:" not in out
    for e in explain.REGISTRY:
        line = f"  {e.id:<22} "
        if e.kind == "concept":
            assert line in out
        else:
            assert line not in out
