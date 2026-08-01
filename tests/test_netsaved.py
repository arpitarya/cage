"""Gross vs net savings (net-savings handoff — K / NET-2 / NET-3).

The finding this pins: `saved` is a per-query counterfactual that excludes the cost of
*using* the tool, so a $0-self-declared tool read as pure profit
(docs/regression/2026-08-01-finding-saved-is-gross.md). Three properties are asserted
here and must never regress:

1. the attributable-cost rule is the ±window union, and it never double-counts;
2. an uncovered task says **unavailable** — `net == gross` is structurally impossible;
3. `verdict` refuses to assert a bare SAVING when the cost of use is unknown, but still
   asserts COSTING (the excluded term is ≥ 0, so a negative net can only worsen).
"""
from __future__ import annotations

from cage import ledger, netsaved, policy, schema, verdict
from cage.constants import NET_ATTRIB_WINDOW_S

POL = policy.load(None)
_MODEL = dict(route="chat", provider="anthropic", model="claude-opus-4-8",
              agent="claude-code")


def _call(root, task, ts, tokens_in=100_000) -> str:
    row = schema.make_call(tokens_in=tokens_in, tokens_out=100, task=task,
                           session=f"s-{task}", ts=ts, **_MODEL)
    ledger.append_row(root, "calls", row)
    return row["id"]


def _receipt(root, ts, task="", tool="graphify", saved=10_000, call=""):
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=saved + 100, actual=100, task=task, call=call, ts=ts))


# ── the attributable-cost rule ────────────────────────────────────────────────

def test_only_calls_inside_the_window_are_charged(proj):
    """A call one second inside the window is cost-of-use; one second outside is the
    task's own work. The boundary is the whole rule — assert both sides of it."""
    _call(proj, "t1", "2026-06-10T10:00:00Z")                       # in  (Δ0s)
    _call(proj, "t1", f"2026-06-10T10:0{NET_ATTRIB_WINDOW_S // 60}:00Z")  # in (Δ120s)
    _call(proj, "t1", "2026-06-10T10:05:00Z")                       # out (Δ300s)
    _receipt(proj, "2026-06-10T10:00:00Z", task="t1")
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["available"] and d["complete"]
    assert d["attributable_calls"] == 2  # the third call is the task's own work
    assert d["window_s"] == NET_ATTRIB_WINDOW_S


def test_a_call_adjacent_to_two_receipts_is_charged_once(proj):
    """Union per task: the subtrahend must not scale with receipt volume, or a chatty
    tool would look expensive purely for filing more receipts."""
    _call(proj, "t1", "2026-06-10T10:00:30Z")
    for i in range(4):
        _receipt(proj, f"2026-06-10T10:00:0{i}Z", task="t1")
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["attributable_calls"] == 1 and d["total_receipts"] == 4


def test_uncovered_task_is_unavailable_never_equal_to_gross(proj):
    """The one outcome the finding forbids: a failed join rendering as `net = gross`."""
    _call(proj, "t1", "2026-06-10T18:00:00Z")  # same task, hours away
    _receipt(proj, "2026-06-10T10:00:00Z", task="t1")
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["available"] is False
    assert d["reason"] == "no task-linked call fell within ±120s of a receipt"
    assert d["tasks"][0]["covered"] is False and d["tasks"][0]["net_usd"] is None
    assert d["tasks"][0]["gross_usd"] > 0  # gross survives; only the net refuses


def test_taskless_receipts_cannot_be_netted(proj):
    """Per-query netting is impossible for a call-less, task-less shim push — the
    module must say so rather than invent a link."""
    _receipt(proj, "2026-06-10T10:00:00Z")  # no task, no call
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["available"] is False and "carry no task" in d["reason"]


def test_partial_coverage_is_reported_not_hidden(proj):
    _call(proj, "t1", "2026-06-10T10:00:10Z")
    _receipt(proj, "2026-06-10T10:00:00Z", task="t1")
    _receipt(proj, "2026-06-11T10:00:00Z", task="t2")  # no calls at all
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["available"] and d["complete"] is False
    assert d["covered_receipts"] == 1 and d["total_receipts"] == 2
    assert "PARTIAL coverage" in netsaved.render_net(d)


def test_net_is_modeled_at_its_own_lower_confidence(proj):
    from cage.constants import GRAPHIFY_RECEIPT_CONFIDENCE
    _call(proj, "t1", "2026-06-10T10:00:10Z")
    _receipt(proj, "2026-06-10T10:00:00Z", task="t1")
    d = netsaved.by_tool(proj, POL, "graphify")
    assert d["method"] == "modeled"  # never `measured` — it inherits gross's counterfactual
    assert d["confidence"] < GRAPHIFY_RECEIPT_CONFIDENCE


def test_determinism(proj):
    _call(proj, "t1", "2026-06-10T10:00:10Z")
    _receipt(proj, "2026-06-10T10:00:00Z", task="t1")
    assert netsaved.by_tool(proj, POL, "graphify") == netsaved.by_tool(proj, POL, "graphify")


# ── NET-2 · the verdict refusal ───────────────────────────────────────────────

def _seed_uncoverable(root, tool="graphify", n=4, saved=10_000):
    """Receipts a cost-of-use figure can never be built for (no task) — the graphify
    shim's real shape, and the state that produced the bare SAVING."""
    for i in range(n):
        _receipt(root, f"2026-06-1{i}T10:00:00Z", tool=tool, saved=saved)


def test_zero_own_cost_no_cost_of_use_is_not_a_bare_saving(proj):
    """The bug, reproduced: graphify pushes call-less, task-less receipts and declares
    $0 own cost, so `net = gross − 0` printed a bare SAVING on sessions that measurably
    cost more. The receipts still price (an explicit `price_at` route), so gross is a
    real positive number — the verdict must keep it and name what it excludes."""
    pol = {**POL, "tools": {**POL.get("tools", {}),
                            "graphify": {"price_at": "anthropic/claude-opus-4-8"}}}
    _seed_uncoverable(proj)
    d = verdict.compose(proj, pol, "graphify")
    assert d["inputs"]["roi"]["saved_usd"] > 0 and d["inputs"]["roi"]["cost_usd"] == 0.0
    assert d["verdict"] == "SAVING (GROSS)" and d["gross_of_use"] is True
    assert "cost_of_use_usd" not in d  # nothing subtracted, nothing invented
    text = verdict.render_verdict(d)
    assert "⚠ GROSS" in text and "cost of USING graphify is NOT subtracted" in text
    assert "cage insights compare" in text  # the measured alternative, named
    assert "net of use (task-level): INSUFFICIENT DATA" in text  # beside gross, refusing
    assert f"gross {'$%.4f' % d['inputs']['roi']['saved_usd']}" in text  # gross survives


def test_costing_is_still_asserted_without_a_cost_of_use_figure(proj):
    """The asymmetry that makes the refusal rule principled rather than blanket: the
    excluded term is ≥ 0, so a negative net can only get more negative."""
    for i in range(4):
        ledger.append_row(proj, "receipts", schema.make_receipt(
            tool="pricey-ml", raw_alternative=1_100, actual=100,
            ts=f"2026-06-1{i}T10:00:00Z", meta={"tool_cost_usd": 0.5}))
    d = verdict.compose(proj, POL, "pricey-ml")
    assert d["verdict"] == "COSTING"  # no "(GROSS)" — the omission cannot flip the sign
    assert "(GROSS)" not in verdict.render_verdict(d).splitlines()[0]


def test_verdict_still_computes_no_new_statistics(proj):
    """The composer property: every number in the payload comes from a composed view."""
    _seed_uncoverable(proj)
    d = verdict.compose(proj, POL, "graphify")
    u = d["inputs"]["net_of_use"]
    assert u["method"] == "modeled" and "available" in u
    r = d["inputs"]["roi"]
    if d.get("gross_of_use"):
        assert d["net_usd"] == r["net_usd"]  # nothing subtracted, nothing invented
