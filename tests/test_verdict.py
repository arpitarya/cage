"""`cage insights verdict <tool>` (roadmap P4) — a pure composer, tested for honesty:
its numbers must equal the underlying views' numbers exactly, every input must
carry a method tag, and a missing input must read INSUFFICIENT DATA."""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import clicmds, ledger, policy, quality, roi, schema, verdict

_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")


def _receipt(root, tool, saved_tokens, ts, task="", call="", tool_cost=0.0):
    meta = {"tool_cost_usd": tool_cost} if tool_cost else {}
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=saved_tokens + 100, actual=100, task=task,
        call=call, ts=ts, meta=meta))


def _call(root, task, ts) -> str:
    row = schema.make_call(tokens_in=1_000, tokens_out=100, task=task,
                           session=f"s-{task}", ts=ts, **_MODEL)
    ledger.append_row(root, "calls", row)
    return row["id"]  # receipts link to the call so saved tokens price at its model


def _seed_saving(root):
    """graphify: 8 token receipts over 8 days, $0 own cost → clearly net-positive.
    Bundled opus prices $5/MTok input, so 10,000 saved tokens = $0.05 per receipt."""
    for i in range(8):
        cid = _call(root, f"t-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(root, "graphify", 10_000, f"2026-06-1{i}T10:00:00Z",
                 task=f"t-{i}", call=cid)


def _seed_costing(root):
    """pricey-ml: saves $0.005/receipt but bills $0.50/receipt of its own cost."""
    for i in range(8):
        cid = _call(root, f"c-{i}", f"2026-06-1{i}T10:00:00Z")
        _receipt(root, "pricey-ml", 1_000, f"2026-06-1{i}T10:00:00Z",
                 task=f"c-{i}", call=cid, tool_cost=0.5)


def test_saving_verdict(proj):
    pol = policy.load(None)
    _seed_saving(proj)
    d = verdict.compose(proj, pol, "graphify")
    assert d["verdict"] == "SAVING" and d["method"] == "modeled"
    # composer honesty: the net equals roi's numbers exactly — nothing recomputed
    t = roi.by_tool(proj, pol, None)["tools"]["graphify"]
    assert d["net_usd"] == round(t["saved_usd"] - t["cost_usd"], 6)
    assert d["inputs"]["roi"]["receipts"] == t["receipts"] == 8
    assert d["span_days"] == 7.0 and "net_per_month" in d
    assert d["net_per_month"] == round(d["net_usd"] / 7 * 30, 4)
    text = verdict.render_verdict(d)
    assert text.startswith("VERDICT: graphify is SAVING ≈ $")
    assert "/mo net (modeled)" in text
    assert "net-positive from the first receipt" in text


def test_costing_verdict(proj):
    pol = policy.load(None)
    _seed_costing(proj)
    d = verdict.compose(proj, pol, "pricey-ml")
    assert d["verdict"] == "COSTING" and d["net_usd"] < 0
    text = verdict.render_verdict(d)
    assert "pricey-ml is COSTING" in text
    assert "no receipt volume reaches break-even" in text


def test_insufficient_data_verdict(proj):
    d = verdict.compose(proj, policy.load(None), "graphify")
    assert d["verdict"] == "INSUFFICIENT DATA"
    assert "net_usd" not in d  # no number invented alongside the refusal
    assert "no receipts recorded for 'graphify'" in verdict.render_verdict(d)


def test_every_available_input_carries_a_method_tag(proj):
    pol = policy.load(None)
    _seed_saving(proj)
    quality.record_outcome(proj, "t-0", ok=True)
    d = verdict.compose(proj, pol, "graphify")
    for name, i in d["inputs"].items():
        if i["available"]:
            assert i["method"], f"input {name} has no method tag"
        else:
            assert i["reason"], f"unavailable input {name} has no reason"
    text = verdict.render_verdict(d)
    assert "(modeled)" in text and "(measured)" in text  # tags visibly rendered
    assert "INSUFFICIENT DATA" in text  # the trend line, honestly missing


def test_short_span_refuses_monthly_projection(proj):
    pol = policy.load(None)
    cid = _call(proj, "t-0", "2026-06-10T10:00:00Z")
    for i in range(6):  # 6 receipts all within one day — span < 7d
        _receipt(proj, "graphify", 10_000, f"2026-06-10T1{i}:00:00Z",
                 task="t-0", call=cid)
    d = verdict.compose(proj, pol, "graphify")
    assert d["verdict"] == "SAVING" and "net_per_month" not in d
    assert "too short for a monthly projection" in verdict.render_verdict(d)


def test_deterministic_and_json_envelope(proj, monkeypatch, capsys):
    pol = policy.load(None)
    _seed_saving(proj)
    assert verdict.render_verdict(verdict.compose(proj, pol, "graphify")) == \
        verdict.render_verdict(verdict.compose(proj, pol, "graphify"))
    monkeypatch.chdir(proj)
    (proj / ".cage").mkdir(exist_ok=True)
    assert clicmds.cmd_verdict(SimpleNamespace(json=True, tool="graphify", since=None)) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["schemaVersion"] == "cage.v1" and payload["command"] == "verdict"
    assert payload["data"]["verdict"] == "SAVING"
