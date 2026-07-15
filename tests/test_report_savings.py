"""`report` spent-and-saved columns + the bare-`cage` headline banner (§6 handoff).

The §4.4 demo seed (one call, three token-savings receipts) gives exact numbers:
  spent  = (8600·$3 + 1500·$15)/1e6           = $0.0483
  saved  = (27000 + 6400 + 8000)·$3/1e6       = $0.1242   (graphify+fux+compressor)
  net    = saved − spent                       = $0.0759
"""
from __future__ import annotations

import pytest

from cage import cli, demo, display, humanview, metering as meter, policy, report

DEMO_SPENT = 0.0483
DEMO_SAVED = 0.1242
DEMO_NET = 0.0759

USD = display.Display(usd=True)  # the $ view — tokens are the render default


def _pol():
    return policy.load(None)


# ── §6.3 — savings columns + exact numbers on --by task ──────────────────────

def test_report_by_task_savings_numbers(seeded):
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    g = rep["groups"]["fix-handover-bug"]
    assert g["saved_usd"] == pytest.approx(DEMO_SAVED, abs=1e-6)
    assert g["net_usd"] == pytest.approx(DEMO_NET, abs=1e-6)
    assert rep["total"]["saved_usd"] == pytest.approx(DEMO_SAVED, abs=1e-6)
    assert rep["total"]["net_usd"] == pytest.approx(DEMO_NET, abs=1e-6)


def test_report_by_task_render_shows_signed_net(seeded):
    root, _ = seeded
    out = report.render_report(report.summarize(root, _pol(), dim="task"), disp=USD)
    assert "saved" in out and "net" in out
    assert "$0.1242" in out          # saved column
    assert "+$0.0759" in out         # net carries an explicit sign


def test_report_tokens_default_no_dollars(seeded):
    """Tokens are the default view (plan Phase 2.5): no $ anywhere, saved tok
    gated in, dollars appear only under --usd/[display]."""
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    out = report.render_report(rep)
    assert "$" not in out
    assert "saved tok" in out and "41,400" in out  # token savings still shown
    assert "usd" not in out.splitlines()[0]
    usd_out = report.render_report(rep, disp=USD)
    assert usd_out.splitlines()[0].endswith("· usd")
    assert "$0.1242" in usd_out


# ── §6.4 — --by agent attributes via the call; no-call → "—", still in total ─

def test_report_by_agent_attributes_and_dash_bucket(proj):
    pol = _pol()
    call_id = meter.record_call(route="r", provider="anthropic",
                                model="claude-sonnet-4-6", tokens_in=1000,
                                tokens_out=0, agent="claude-code", root=proj)
    # usd-unit receipts: real dollars regardless of the call (no token pricing needed).
    meter.record_receipt(tool="graphify", raw_alternative=10.0, actual=0.0,
                         unit="usd", call=call_id, root=proj)
    meter.record_receipt(tool="compressor", raw_alternative=5.0, actual=0.0,
                         unit="usd", call="", root=proj)  # no call → "—"
    rep = report.summarize(proj, pol, dim="agent")
    assert rep["groups"]["claude-code"]["saved_usd"] == pytest.approx(10.0, abs=1e-6)
    assert rep["groups"]["—"]["saved_usd"] == pytest.approx(5.0, abs=1e-6)
    assert rep["total"]["saved_usd"] == pytest.approx(15.0, abs=1e-6)  # both counted


# ── §6.5 — human receipts excluded from report, but visible in `cage human` ──

def test_human_receipt_excluded_from_report_but_shown_in_human(seeded):
    root, _ = seeded
    pol = _pol()
    meter.record_human(task=demo.TASK, minutes=60, agent="claude-code", root=root)
    rep = report.summarize(root, pol, dim="task")
    assert rep["total"]["saved_usd"] == pytest.approx(DEMO_SAVED, abs=1e-6)  # unmoved
    human = humanview.rollup(root, pol)
    assert human["agents"]["claude-code"]["tasks"] == 1  # but it does show here


# ── §6.2 / §6.6 — non-attributing dims are untouched (byte-identical, no keys) ─

@pytest.mark.parametrize("dim", ["route", "model", "provider", "day"])
def test_report_other_dims_have_no_savings(seeded, dim):
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim=dim)
    assert "saved_usd" not in rep["total"] and "net_usd" not in rep["total"]
    for g in rep["groups"].values():
        assert "saved_usd" not in g and "net_usd" not in g
    header = report.render_report(rep).splitlines()[2]  # title, blank, then columns
    assert "saved" not in header and "net" not in header and "cost" not in header
    usd_header = report.render_report(rep, disp=USD).splitlines()[2]
    assert "saved" not in usd_header and "net" not in usd_header and "cost" in usd_header


def test_report_json_keys_only_for_attributing_dims(seeded):
    root, _ = seeded
    task = report.summarize(root, _pol(), dim="task")
    model = report.summarize(root, _pol(), dim="model")
    assert {"saved_usd", "net_usd"} <= set(task["total"])
    assert "saved_usd" not in model["total"]


# ── §6.9 — determinism: same ledger ⇒ byte-identical render ───────────────────

def test_report_render_is_deterministic(seeded):
    root, _ = seeded
    a = report.render_report(report.summarize(root, _pol(), dim="task"))
    b = report.render_report(report.summarize(root, _pol(), dim="task"))
    assert a == b


# ── §6.7 — bare `cage` banner / --json dict / empty nudge ─────────────────────

def test_bare_cage_prints_banner(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    meter._policy_for.cache_clear()
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "tokens" in out and "calls" in out and "drill:" in out
    assert "$" not in out  # tokens are the default headline (handoff §10)
    assert cli.main(["--usd"]) == 0
    out = capsys.readouterr().out
    assert "spent" in out and "saved" in out and "net" in out
    assert "$0.0483" in out and "$0.1242" in out and "+$0.0759" in out
    assert "drill:" in out


def test_bare_cage_json_emits_headline_dict(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    meter._policy_for.cache_clear()
    assert cli.main(["--json"]) == 0
    import json
    o = json.loads(capsys.readouterr().out)
    assert o["spent_usd"] == pytest.approx(DEMO_SPENT, abs=1e-6)
    assert o["saved_usd"] == pytest.approx(DEMO_SAVED, abs=1e-6)
    assert o["net_usd"] == pytest.approx(DEMO_NET, abs=1e-6)


def test_bare_cage_empty_ledger_nudges(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "No calls recorded yet" in out
    assert "cage import" in out and "cage doctor" in out  # next steps (spec R5)
    assert "spent" not in out  # a nudge, not a banner of zeros


# ── §6.8 — --help / --version still work after required=False ─────────────────

@pytest.mark.parametrize("flag", ["--help", "--version"])
def test_global_flags_still_exit_zero(flag):
    with pytest.raises(SystemExit) as e:
        cli.main([flag])
    assert e.value.code == 0
