"""The pricing ladder for call-less token receipts (plan §4.5, receiptprice.py).

Goldens per rung + tie-breaks, the dangling-route refusal, the fleet-merge case,
linked-receipt byte-identity, and determinism double-runs — exact numbers, never
approximate: 10,000 saved tokens price at $0.03 (sonnet, $3/M in) or $0.05
(opus, $5/M in) from the bundled table.
"""
from __future__ import annotations

import copy

from cage import (attribution, doctorcmd, explain, metering, policy, pricescmd,
                  receiptprice, report, roi, verdict)

POL = policy.load(None)
SONNET = "anthropic/claude-sonnet-4-6"   # $3/M input in the bundled table
OPUS = "anthropic/claude-opus-4-6"       # $5/M input in the bundled table


def _pol_with_route(target=SONNET, tool="graphify"):
    pol = copy.deepcopy(POL)
    pol.setdefault("tools", {})[tool] = {"price_at": target}
    return pol


def _callless_receipt(root, task="t-alpha", tool="graphify", saved=10_000):
    return metering.record_receipt(tool=tool, raw_alternative=saved + 1_000,
                                   actual=1_000, task=task, method="modeled",
                                   confidence=0.7, root=root)


def _call(root, task="t-alpha", model="claude-opus-4-6", tokens_in=6_000, **kw):
    return metering.record_call(route="api", provider="anthropic", model=model,
                                tokens_in=tokens_in, tokens_out=500, task=task,
                                session="s1", root=root, **kw)


# ── rung 1: [tools.<tool>] price_at ─────────────────────────────────────────────
def test_rung1_price_at_prices_and_footnotes(proj):
    _callless_receipt(proj)
    data = roi.by_tool(proj, _pol_with_route())
    t = data["tools"]["graphify"]
    assert t["saved_usd"] == 0.03                       # 10k × $3/M
    assert t["priced_via"] == ["price_at"]
    text = roi.render_roi(data)
    assert f"≈ graphify priced via [tools.graphify] price_at ({SONNET})" in text
    assert "UNPRICED" not in text


def test_rung1_beats_rung2(proj):
    _call(proj)                                          # task model would say opus
    _callless_receipt(proj)
    t = roi.by_tool(proj, _pol_with_route())["tools"]["graphify"]
    assert t["saved_usd"] == 0.03                        # explicit routing wins
    assert t["priced_via"] == ["price_at"]


# ── rung 2: dominant task model ─────────────────────────────────────────────────
def test_rung2_task_model_prices_and_footnotes(proj):
    _call(proj)
    _callless_receipt(proj)
    data = roi.by_tool(proj, POL)
    t = data["tools"]["graphify"]
    assert t["saved_usd"] == 0.05                        # 10k × $5/M (opus)
    assert t["priced_via"] == ["task-model"]
    assert f"≈ graphify priced at task model ({OPUS})" in roi.render_roi(data)


def test_rung2_dominant_by_tokens_in(proj):
    _call(proj, model="claude-opus-4-6", tokens_in=6_000)
    _call(proj, model="claude-sonnet-4-6", tokens_in=4_000)
    _call(proj, model="claude-sonnet-4-6", tokens_in=1_000)  # more calls, fewer tokens
    _callless_receipt(proj)
    t = roi.by_tool(proj, POL)["tools"]["graphify"]
    assert t["saved_usd"] == 0.05                        # opus dominates on tokens_in


def test_rung2_tie_breaks_by_call_count_then_lexicographic():
    a = {"provider": "anthropic", "model": "claude-opus-4-6", "tokens_in": 5_000}
    b1 = {"provider": "anthropic", "model": "claude-sonnet-4-6", "tokens_in": 2_500}
    b2 = {"provider": "anthropic", "model": "claude-sonnet-4-6", "tokens_in": 2_500}
    # tokens tied 5k–5k → sonnet wins on call count (2 vs 1)
    assert receiptprice.dominant_model([a, b1, b2]) == ("anthropic", "claude-sonnet-4-6")
    # tokens AND call count tied → lexicographic provider/model (a total order)
    c = {"provider": "anthropic", "model": "claude-sonnet-4-6", "tokens_in": 5_000}
    assert receiptprice.dominant_model([a, c]) == ("anthropic", "claude-opus-4-6")


def test_rung2_unpriced_dominant_model_refuses(proj):
    _call(proj, model="mystery-9000")                    # no price row, no family
    _callless_receipt(proj)
    t = roi.by_tool(proj, POL)["tools"]["graphify"]
    assert t["saved_usd"] == 0.0
    assert t["priced_via"] == ["unpriced"]               # never a silent $0-at-zeros


# ── rung 3: refusal, loudly ─────────────────────────────────────────────────────
def test_rung3_refuses_with_hint(proj):
    _callless_receipt(proj)                              # zero-call task, no route
    data = roi.by_tool(proj, POL)
    assert data["tools"]["graphify"]["saved_usd"] == 0.0
    assert data["unpriced_receipts"] == {"receipts": 1, "tokens": 10_000,
                                         "tools": ["graphify"]}
    text = roi.render_roi(data)
    assert "⚠ 1 tool receipt(s) (10,000 tokens saved) UNPRICED — totals understated:" in text
    # the fix hint is a runnable command with the real tool name substituted
    assert ("run: cage prices route-tool graphify --to <provider>/<model>"
            "  (or run in a metered session)") in text


def test_dangling_price_at_never_falls_through(proj):
    _call(proj)                                          # rung 2 WOULD price at opus
    _callless_receipt(proj)
    t = roi.by_tool(proj, _pol_with_route("anthropic/mystery-9000"))["tools"]["graphify"]
    assert t["saved_usd"] == 0.0                         # explicit-but-broken refuses
    assert t["priced_via"] == ["unpriced"]


def test_dangling_price_at_warned_in_prices_list_and_doctor(proj):
    (proj / ".cage").mkdir()
    (proj / ".cage" / "policy.toml").write_text(
        '[tools.graphify]\nprice_at = "anthropic/mystery-9000"\n', encoding="utf-8")
    d = pricescmd.list_view(proj)
    assert d["tool_routes"] == [{"tool": "graphify", "to": "anthropic/mystery-9000",
                                 "broken": True}]
    assert "⚠ dangling" in pricescmd.render_list(d)
    status, msg = doctorcmd._pricing(proj)
    assert "dangling tool route(s)" in msg and "[tools.graphify]" in msg


# ── fleet merge: an unresolvable call id enters the ladder (§8) ────────────────
def test_unresolvable_call_id_enters_ladder(proj):
    _call(proj)
    metering.record_receipt(tool="graphify", raw_alternative=11_000, actual=1_000,
                            call="c_gone_in_the_merge", task="t-alpha",
                            method="modeled", root=proj)
    t = roi.by_tool(proj, POL)["tools"]["graphify"]
    assert t["saved_usd"] == 0.05                        # improved, not silently $0
    assert t["priced_via"] == ["task-model"]


# ── report / overview reconcile with roi ───────────────────────────────────────
def test_report_saved_reconciles_and_warns(proj):
    _callless_receipt(proj, task="t-alpha")
    _call(proj)
    rep = report.summarize(proj, POL, dim="task")
    assert rep["total"]["saved_usd"] == 0.05             # same ladder, same number
    assert rep["unpriced_receipts"] == {"receipts": 0, "tokens": 0, "tools": []}
    # a refused receipt surfaces in the report warning too, with the runnable fix
    _callless_receipt(proj, task="t-orphan", tool="fux")
    rep = report.summarize(proj, POL, dim="task")
    assert rep["unpriced_receipts"] == {"receipts": 1, "tokens": 10_000, "tools": ["fux"]}
    text = report.render_report(rep)
    assert "tokens saved) UNPRICED — totals understated:" in text
    assert "run: cage prices route-tool fux --to <provider>/<model>" in text


def test_overview_saved_includes_ladder(proj):
    _call(proj)
    _callless_receipt(proj)
    assert report.overview(proj, POL)["saved_usd"] == 0.05


# ── attribution: ladder portion only; linked stays task-model ──────────────────
def test_attrib_prices_callless_portion_and_footnotes(proj):
    cid = _call(proj, task="t1")
    metering.record_receipt(tool="graphify", raw_alternative=11_000, actual=1_000,
                            call=cid, task="t1", method="modeled", root=proj)
    _callless_receipt(proj, task="t1", tool="fux", saved=10_000)
    data = attribution.attribute(proj, "t1", POL)
    steps = {s["tool"]: s for s in data["steps"]}
    assert steps["graphify"]["priced_via"] == ""         # linked — legacy, no footnote
    assert steps["graphify"]["saved_usd"] == 0.05        # task model (opus), as before
    assert steps["fux"]["priced_via"] == "task-model"
    assert steps["fux"]["priced_model"] == OPUS
    assert steps["fux"]["saved_usd"] == 0.05
    text = attribution.render_attrib(data)
    assert f"≈ fux priced at task model ({OPUS})" in text
    assert "≈ graphify" not in text


def test_attrib_csv_carries_rung_column(proj):
    _call(proj, task="t1")
    _callless_receipt(proj, task="t1", tool="fux")
    csv = attribution.render_csv(attribution.attribute(proj, "t1", POL))
    assert csv.splitlines()[0].endswith(",priced_via")
    assert ",task-model" in csv


# ── verdict names the rung ─────────────────────────────────────────────────────
def test_verdict_names_the_rung(proj):
    _call(proj)
    _callless_receipt(proj)
    d = verdict.compose(proj, POL, "graphify")
    assert d["inputs"]["roi"]["priced_via"] == ["task-model"]
    text = verdict.render_verdict(d)
    assert "priced via task-model" in text


# ── the law: linked receipts and legacy output byte-identical ──────────────────
def test_linked_only_ledger_has_no_ladder_marks(seeded):
    root, _ = seeded                                     # the §4.4 demo: all linked
    data = roi.by_tool(root, POL)
    text = roi.render_roi(data)
    assert "≈" not in text and "UNPRICED" not in text
    assert all(t["priced_via"] == ["call"] for t in data["tools"].values())
    rep = report.render_report(report.summarize(root, POL, dim="task"))
    assert "UNPRICED" not in rep


# ── determinism: same ledger + policy ⇒ byte-identical, twice ──────────────────
def test_ladder_views_deterministic_double_run(proj):
    _call(proj, model="claude-opus-4-6", tokens_in=5_000)
    _call(proj, model="claude-sonnet-4-6", tokens_in=5_000)  # exercises tie-break too
    _callless_receipt(proj)
    _callless_receipt(proj, task="t-orphan", tool="fux")     # and the refusal path
    a = (roi.render_roi(roi.by_tool(proj, POL)),
         report.render_report(report.summarize(proj, POL, dim="task")),
         attribution.render_attrib(attribution.attribute(proj, "t-alpha", POL)))
    b = (roi.render_roi(roi.by_tool(proj, POL)),
         report.render_report(report.summarize(proj, POL, dim="task")),
         attribution.render_attrib(attribution.attribute(proj, "t-alpha", POL)))
    assert a == b


# ── cage query receipt-pricing: live values, never literals ────────────────────
def test_query_receipt_pricing_interpolates_live_routes():
    e = next(e for e in explain.REGISTRY if e.id == "receipt-pricing")
    assert "none configured" in explain.render(e, POL)
    routed = explain.render(e, _pol_with_route())
    assert f"graphify → {SONNET}" in routed


# ── the fix-hint contract: the printed hint is a runnable command ───────────────
def test_printed_hint_is_runnable_end_to_end(proj, monkeypatch, capsys):
    """Copy the ⚠ line's command, substitute only the <provider>/<model>
    placeholder (cage never guesses a model), run it → rung-1 dollars."""
    from cage import cli
    monkeypatch.chdir(proj)
    (proj / ".cage").mkdir()
    _callless_receipt(proj)
    text = roi.render_roi(roi.by_tool(proj, POL))
    line = next(ln for ln in text.splitlines() if "run: cage prices route-tool" in ln)
    cmd = line.split("run: cage ", 1)[1].split("  (")[0]
    assert cmd == "prices route-tool graphify --to <provider>/<model>"
    assert cli.main(cmd.replace("<provider>/<model>", SONNET).split()) == 0
    capsys.readouterr()
    pol = policy.load(proj / ".cage" / "policy.toml")
    t = roi.by_tool(proj, pol)["tools"]["graphify"]
    assert t["saved_usd"] == 0.03 and t["priced_via"] == ["price_at"]
    # --remove returns the receipt to UNPRICED (rung 3), the loud state
    assert cli.main(["prices", "route-tool", "graphify", "--remove"]) == 0
    capsys.readouterr()
    pol = policy.load(proj / ".cage" / "policy.toml")
    assert roi.by_tool(proj, pol)["tools"]["graphify"]["priced_via"] == ["unpriced"]


def test_bundled_policy_ships_no_routes():
    """Routes are user intent — the bundle must never carry one (handoff §3)."""
    assert receiptprice.routes(policy.bundled_raw()) == {}
