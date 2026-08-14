"""`report` used-and-saved columns + the bare-`cage` headline banner (§6 handoff).

The §4.4 demo seed (one call, three token-savings receipts) gives exact numbers:
  used   = 8600 in + 1500 out
  saved  = 27000 + 6400 + 8000 = 41,400 tokens  (graphify+fux+compressor), GROSS

The USD half of this file went with the money subsystem (USAGE-ONLY, ADR 0011); every
figure here is now a token count, and there is no `--usd` view to compare against.
"""
from __future__ import annotations

import pytest

from cage import cli, demo, display, ledger, metering as meter, policy, report, schema

DEMO_TOK_IN = 8600
DEMO_TOK_OUT = 1500
DEMO_SAVED_TOK = 41_400


def _pol():
    return policy.load(None)


# ── §6.3 — savings columns + exact numbers on --by task ──────────────────────

def test_report_by_task_savings_numbers(seeded):
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    g = rep["groups"]["fix-handover-bug"]
    assert g["saved_tokens"] == DEMO_SAVED_TOK
    assert rep["total"]["saved_tokens"] == DEMO_SAVED_TOK


def test_report_by_task_render_shows_gross_tokens_and_the_caveat(seeded):
    root, _ = seeded
    out = report.render_report(report.summarize(root, _pol(), dim="task"))
    assert "gross tok" in out and "41,400" in out
    # The gross exclusion is stated wherever the number renders — one phrasing, one
    # owner (`savings.GROSS_NOTE`), and there is no net to offer instead.
    assert "saved is GROSS" in out


# ── G4 — the graphify day-one repo ceiling in the report footer ──────────────

def _bounded_ceiling():
    return {"ok": True, "method": "modeled", "bounded": True, "files": 249,
            "corpus_tokens": 552159, "communities": 707, "ceiling_files": 22,
            "ceiling_tokens": 89853, "typical_tokens": 3007}


def test_ceiling_footer_line_shapes():
    from cage import graphifymodel
    assert graphifymodel.ceiling_footer_line({"ok": False}) == ""       # silent, no graph
    line = graphifymodel.ceiling_footer_line(_bounded_ceiling())
    assert "repo ceiling" in line and "modeled" in line
    assert "89,853" in line and "typical ≈ 3,007" in line               # bounded band
    unb = graphifymodel.ceiling_footer_line(
        {"ok": True, "bounded": False, "ceiling_tokens": 552159, "typical_tokens": 552159})
    assert "UNBOUNDED" in unb                                           # loud fallback


def test_report_footer_shows_ceiling_when_present(seeded):
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    with_c = report.render_report(rep, ceiling=_bounded_ceiling())
    without = report.render_report(rep, ceiling=None)
    assert "graphify repo ceiling" in with_c and "89,853" in with_c
    assert "graphify repo ceiling" not in without                       # silent by default
    # token-native: the ceiling shows even in the default (non-$) view
    assert "$" not in with_c.split("graphify repo ceiling")[1].split("\n")[0]


def test_report_csv_never_shows_ceiling(seeded):
    """G4 recommendation implemented: the ceiling is not a row-level fact — CSV omits it
    (render_csv takes no ceiling arg and is byte-identical regardless)."""
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    assert "ceiling" not in report.render_csv(rep).lower()


def test_report_tokens_default_no_dollars(seeded):
    """Tokens are the ONLY view (USAGE-ONLY, ADR 0011): no `$` anywhere, and no flag
    that could add one."""
    root, _ = seeded
    rep = report.summarize(root, _pol(), dim="task")
    out = report.render_report(rep)
    assert "$" not in out
    assert "gross tok" in out and "41,400" in out  # token savings still shown (K: gross)
    assert "usd" not in out.splitlines()[0]


# ── §6.4 — --by agent attributes via the call; no-call → "—", still in total ─

def test_report_by_agent_attributes_and_dash_bucket(proj):
    """A receipt linked to a call attributes to that call's agent; an unlinked one
    lands in `—` and is still counted in the total — the join, not the pricing, is
    what this pins, and the join is unchanged (USAGE-ONLY, ADR 0011)."""
    pol = _pol()
    call_id = meter.record_call(route="r", provider="anthropic",
                                model="claude-sonnet-4-6", tokens_in=1000,
                                tokens_out=0, agent="claude-code", root=proj,
                                ts="2026-06-01T12:00:00Z")
    meter.record_receipt(tool="graphify", raw_alternative=10_000, actual=0,
                         call=call_id, root=proj)
    meter.record_receipt(tool="compressor", raw_alternative=5_000, actual=0,
                         call="", root=proj)  # no call → "—"
    rep = report.summarize(proj, pol, dim="agent")
    assert rep["groups"]["claude-code"]["saved_tokens"] == 10_000
    assert rep["groups"]["—"]["saved_tokens"] == 5_000
    assert rep["total"]["saved_tokens"] == 15_000  # both counted


# ── §6.5 — a LEGACY human/minutes receipt is excluded AND visibly footnoted ───

def test_legacy_human_receipt_excluded_from_report_and_footnoted(seeded):
    """v0.36 removed the Tier-1 axis; ledgers are append-only, so a pre-0.36
    `tool="human"` row still arrives. It must not move a total — and must not
    vanish silently either (the removal decision, made visible)."""
    root, _ = seeded
    pol = _pol()
    row = schema.make_receipt(tool="human", raw_alternative=60.0, actual=0.0,
                              unit="usd", task=demo.TASK, method="estimated")
    row["unit"] = "minutes"  # the removed unit, as a v0.35 ledger holds it
    assert ledger.append_row(root, "receipts", row)
    rep = report.summarize(root, pol, dim="task")
    assert rep["total"]["saved_tokens"] == DEMO_SAVED_TOK  # unmoved
    assert rep["legacy_human"] == 1
    text = report.render_report(rep)
    assert "legacy human-axis receipt(s) excluded" in text


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


def test_report_json_keys_only_for_attributing_dims(seeded):
    root, _ = seeded
    task = report.summarize(root, _pol(), dim="task")
    model = report.summarize(root, _pol(), dim="model")
    assert "saved_tokens" in task["total"]
    assert "saved_tokens" not in model["total"]


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
    assert "gross saved" in out and "41,400" in out
    assert "$" not in out  # there is no dollar view to fall back to


def test_bare_cage_json_emits_headline_dict(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    meter._policy_for.cache_clear()
    assert cli.main(["--json"]) == 0
    import json
    o = json.loads(capsys.readouterr().out)
    assert o["tokens"] == DEMO_TOK_IN + DEMO_TOK_OUT
    assert o["saved_tokens"] == DEMO_SAVED_TOK
    assert "spent_usd" not in o and "net_usd" not in o


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
