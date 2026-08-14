"""A pre-v0.36 ledger must still read — the removal regression that would escape.

v0.36 removed the Tier-1 agent-vs-human axis *including its substrate*: `gap_ms`
left `CALL_FIELDS`, `"minutes"` left `UNITS`. Ledgers are **append-only and are
never rewritten**, so every one of those rows is still on disk on every upgraded
machine. This module builds such a ledger by hand — writing the removed field and
the removed unit as raw JSON, the way v0.35 wrote them — and drives every read
surface over it.

Two distinct properties, both load-bearing:

1. **Nothing crashes.** An unknown extra key (`gap_ms`) and an unknown unit
   (`minutes`) are tolerated by every reader.
2. **Nothing lies.** A legacy `tool="human"` / `unit="minutes"` receipt is
   EXCLUDED from money totals *and counted in a visible footnote* — the decision
   the removal made, rendered rather than silently applied. Skipping such a row
   from a total without saying so is the failure this file exists to prevent.
"""
from __future__ import annotations

import json

import pytest

from cage import attribution, cli, display, ledger, paths, policy, report, schema

_M = dict(route="chat", provider="anthropic", model="claude-sonnet-4-6",
          agent="claude-code")


@pytest.fixture
def legacy(tmp_path, monkeypatch):
    """A v0.35-shaped ledger: calls carrying `gap_ms`, plus a `unit="minutes"`
    human receipt and a `unit="usd"` one — both of the removed axis."""
    root = tmp_path / "proj"
    foot = paths.Footprint(root)
    foot.ledger.mkdir(parents=True, exist_ok=True)

    for i, gap in enumerate((37_000, 1_200_000)):
        c = schema.make_call(tokens_in=10_000, tokens_out=1_000, task="t-legacy",
                             session="s-legacy", ts=f"2026-06-1{i}T10:00:00Z",
                             call_id=f"c_legacy{i}", **_M)
        c["gap_ms"] = gap          # the removed field, exactly as v0.35 wrote it
        assert ledger.append_row(root, "calls", c)
        # The metric twin. `ledger.spend` supersedes a `calls` row for any agent with a
        # metric spine (USAGE-ONLY, ADR 0011), and these rows are `agent="claude-code"`,
        # so a calls-only legacy fixture would read as ZERO here. That is the real
        # behaviour for a pre-metrics claude ledger and it is pinned on its own below
        # (`test_a_spined_agents_calls_are_superseded_with_no_twin`); this fixture is
        # about the removed HUMAN axis, so it dual-writes to isolate that question.
        assert ledger.append_row(root, "claude", schema.make_claude_metric(
            session="s-legacy", source="request", request=f"r{i}",
            provider="anthropic", model="claude-sonnet-4-6",
            tokens_in=10_000, tokens_out=1_000, ts=f"2026-06-1{i}T10:00:00Z"))

    # A real (still-supported) token receipt, so the money views have something
    # to actually total — the legacy rows must not disturb it.
    live = schema.make_receipt(tool="graphify", raw_alternative=8_000, actual=1_000,
                               call="c_legacy0", task="t-legacy",
                               ts="2026-06-10T11:00:00Z", method="modeled")
    assert ledger.append_row(root, "receipts", live)

    # Three legacy shapes, deliberately NOT all the same: `tool="human"` covers the
    # `cage human record` rows, but `record_receipt` took an arbitrary unit, so a
    # third-party tool could write `unit="minutes"` under its OWN name. A filter
    # that only tested the tool would price that one at the (now absent) human rate.
    for rid, tool, unit, raw in (("r_legacy_min", "human", "minutes", 90.0),
                                 ("r_legacy_usd", "human", "usd", 120.0),
                                 ("r_legacy_3p", "timesaver", "minutes", 45.0)):
        r = schema.make_receipt(tool=tool, raw_alternative=raw, actual=0.0,
                                task="t-legacy", ts="2026-06-10T12:00:00Z",
                                method="estimated")
        r["unit"] = unit           # "minutes" is no longer constructible
        r["id"] = rid
        assert ledger.append_row(root, "receipts", r)

    monkeypatch.chdir(root)
    return root


def _pol():
    return policy.load(None)


# ── 1. the rows survive a round-trip verbatim (append-only means never rewritten) ─

def test_legacy_rows_read_back_byte_identical(legacy):
    calls = ledger.calls(legacy)
    assert [c["gap_ms"] for c in calls] == [37_000, 1_200_000]
    units = {r["id"]: r.get("unit") for r in ledger.receipts(legacy)}
    assert units["r_legacy_min"] == "minutes"  # a removed unit is still readable
    raw = (legacy / ".cage" / "ledger").glob("receipts-*.jsonl")
    assert any('"unit": "minutes"' in json.dumps(json.loads(ln))
               for f in raw for ln in f.read_text().splitlines() if ln.strip())


# ── 2. every read surface tolerates them ──────────────────────────────────────

@pytest.mark.parametrize("dim", ["route", "model", "agent", "task", "day", "provider"])
def test_report_reads_every_dimension(legacy, dim):
    rep = report.summarize(legacy, _pol(), dim=dim)
    assert rep["total"]["calls"] == 2


def test_derived_views_do_not_raise(legacy):
    pol = _pol()
    assert attribution.attribute(legacy, "t-legacy", pol)["steps"]
    assert report.summarize(legacy, pol, dim="agent")["total"]["calls"] == 2
    assert report.overview(legacy, pol)["tokens"] > 0


def test_a_spined_agents_calls_are_superseded_with_no_twin(tmp_path):
    """The user-visible consequence of retiring the cutover, pinned rather than
    discovered: a claude/copilot `calls` row with NO metric twin resolves to nothing.

    Pre-metrics history (claude `calls` rows older than the metric routes) therefore
    reads as zero in every derived view. The rows are never deleted — the ledger is
    append-only and `join_table` still resolves a receipt's `call` id against them — but
    they are no longer a spend source. That was the decision USAGE-ONLY made (the
    corrected metric rows are the basis; the inflated `calls` history is not)."""
    root = tmp_path / "p"
    paths.Footprint(root).ledger.mkdir(parents=True, exist_ok=True)
    assert ledger.append_row(root, "calls", schema.make_call(
        tokens_in=99_000, tokens_out=9_000, call_id="c_orphan", **_M))
    assert ledger.spend(root) == []
    assert len(ledger.calls(root)) == 1, "the row itself is never deleted"


@pytest.mark.parametrize("argv", [
    ["report"], ["report", "--by", "task", "--csv"],
    ["insights", "attrib"], ["insights", "compare"], ["insights", "calibration"],
    ["insights", "why", "c_legacy0"], ["insights", "chats"],
    ["data", "export", "--no-import", "--csv", "calls"],
])
def test_cli_read_surfaces_exit_zero(legacy, argv, monkeypatch):
    monkeypatch.setenv("CAGE_CAPTURE", "0")
    assert cli.main([*argv, *(["--no-import"] if argv[0] != "data" else [])]) == 0


# ── 3. excluded from money — and SAID so, never silently ──────────────────────

def test_legacy_receipts_never_enter_a_money_total(legacy):
    pol = _pol()
    rep = report.summarize(legacy, pol, dim="task")
    # Only the graphify receipt's 7,000 saved tokens count; 90 minutes and $120
    # of removed-axis "savings" contribute nothing.
    assert rep["total"]["saved_tokens"] == 7_000
    steps = attribution.attribute(legacy, "t-legacy", pol)["steps"]
    assert [s["tool"] for s in steps] == ["graphify"]


def test_the_exclusion_is_counted_and_footnoted(legacy):
    """The decision, made visible. Three legacy rows in, three named in the footer."""
    rep = report.summarize(legacy, _pol(), dim="task")
    assert rep["legacy_human"] == 3
    text = report.render_report(rep, disp=display.Display())
    assert "3 legacy human-axis receipt(s) excluded" in text
    assert "removed in v0.36" in text and "cage query savings-axis" in text


def test_a_clean_ledger_says_nothing(tmp_path):
    """The footnote is evidence-driven: no legacy rows ⇒ not one extra byte."""
    root = tmp_path / "clean"
    assert ledger.append_row(root, "calls", schema.make_call(
        tokens_in=10, tokens_out=1, task="t", ts="2026-06-10T10:00:00Z",
        call_id="c_clean", **_M))
    rep = report.summarize(root, policy.load(None), dim="task")
    assert rep["legacy_human"] == 0
    assert "legacy human-axis" not in report.render_report(
        rep, disp=display.Display())


# ── 4. the substrate really is gone (a write can never re-create these rows) ───

def test_minutes_is_no_longer_a_constructible_unit():
    assert "minutes" not in schema.UNITS
    with pytest.raises(ValueError):
        schema.make_receipt(tool="human", raw_alternative=90, actual=0, unit="minutes")


def test_gap_ms_is_no_longer_a_call_field():
    assert "gap_ms" not in schema.CALL_FIELDS
    assert "gap_ms" not in schema.CREDIT_FIELDS
    assert "gap_ms" not in schema.make_call(tokens_in=1, tokens_out=1, **_M)


# ── 5. provenance origin="human" is a DIFFERENT axis and is untouched ─────────

def test_provenance_human_origin_still_works(tmp_path):
    """The trap this removal had to avoid: `origin="human"` is authorship, not
    cost. Its enum, its constructor, and its trust ladder all stay."""
    from cage import constants
    assert "human" in schema.ORIGINS
    row = schema.make_provenance(sha="a" * 40, files=["a.py"], lines_added=3,
                                 lines_removed=1, method="heuristic", origin="human")
    assert row["origin"] == "human" and row["method"] == "heuristic"
    assert set(constants.PROVENANCE_METHOD_TRUST) == set(schema.PROV_METHODS)
