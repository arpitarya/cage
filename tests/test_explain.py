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
    assert cli.main(["query", "saved"]) == 0
    assert "saved" in capsys.readouterr().out


# ── live numbers: the printed pipeline order IS policy's, proving interpolation ──
def test_printed_order_tracks_policy(proj, monkeypatch, capsys):
    """A printed value is the LIVE policy value, not a frozen literal.

    Carried on the cleanup retention window since SURFACE-CUT deleted every entry that
    interpolated `{order}` — `[tools] order` drove marginal attribution, and with
    `attribution.py` gone `policy.tool_order` has no consumer left at all."""
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "cleanup"]) == 0
    out = capsys.readouterr().out
    assert str(policy.cleanup_days(policy.load(None))) in out


def test_live_order_in_payload():
    """A body interpolates the LIVE policy value, never a frozen literal —
    change the policy, the printed text changes with it."""
    pol = policy.load(None)
    e = explain._BY_ID["cleanup"]
    assert str(policy.cleanup_days(pol)) in explain.payload(e, pol)["formula"]
    edited = {**pol, "cleanup": {**pol.get("cleanup", {}), "days": 4242}}
    assert "4242" in explain.payload(e, edited)["formula"]


# ── --json carries the same content as the text render ─────────────────────────
def test_json_has_same_fields_as_text(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    metering._policy_for.cache_clear()
    assert cli.main(["query", "saved", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert set(data) == {"id", "kind", "keywords", "summary", "formula", "code_refs",
                          "method_note", "plan_ref"}
    assert data["id"] == "saved"
    assert data["kind"] == "calculation"
    pol = policy.load(None)
    text = explain.render(explain._BY_ID["saved"], pol)
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
    ("saved", "saved"),
    ("savings-axis", "savings-axis"),
    ("what happened to the human axis", "savings-axis"),
    ("what are the method tags", "method-tags"),
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
    # The money entries (cost/roi/budget/matrix/verdict-composition/pricing-match/
    # unpriced/repricing/receipt-pricing) went with the subsystem they explained
    # (USAGE-ONLY, ADR 0011).
    # SURFACE-CUT (v0.52) took `marginal-attribution`, `compare-delta`, `estimate-band`
    # and `calibration-hit-rate` — each explained a command that no longer exists.
    calc_ids = {"saved", "gross-vs-net", "token-heuristic",
                "confidence", "method-tags", "study-pairing", "policy-versioning"}
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
    # calls/receipts show the month-partitioned shard glob (calls-*.jsonl), not the
    # legacy unpartitioned filename which no longer exists on a fresh ledger.
    assert str(foot.ledger / "calls-*.jsonl") in out
    assert str(foot.ledger / "receipts-*.jsonl") in out
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
    # `[tools] order` no longer reaches any surface — `attribution.py` was its only
    # consumer and SURFACE-CUT deleted it, so there is nothing left to interpolate the
    # pipeline into. The setting is still parsed and still recorded in cage.toml;
    # work/OPEN-WORK.md carries the gap. Assert the absence rather than delete the test.
    assert not [e for e in explain.REGISTRY
               if "{order}" in ((e.formula or "") + (e.summary or ""))]


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




def test_cleanup_and_capture_entries_render_live(proj, monkeypatch):
    """The live-interpolation contract, on the entries that survived the money
    deletion: no `{placeholder}` may reach a rendered formula."""
    monkeypatch.chdir(proj)
    pol = policy.load(None)
    live_ids = {"policy-versioning", "cleanup", "import-before-export"}
    by_id = {e.id: e for e in explain.REGISTRY}
    assert live_ids <= set(by_id)
    for i in live_ids:
        text = explain.render(by_id[i], pol)
        assert "{" not in text.split("code:")[0], f"{i} left an unfilled placeholder"
    # the bundled policy_version is the bundle's own stamp, not a literal
    stamp = str(policy.bundled_raw()["meta"]["policy_version"])
    assert stamp in explain.render(by_id["policy-versioning"], pol)
