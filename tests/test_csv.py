"""CSV reporting surface (plan §3.9): golden byte-exact CSVs over the seeded demo
ledger, the one-structure-two-renderers same-numbers guarantee, method tags as
columns, refusals/caveats surviving into rows, RFC-4180 quoting, LF pinning,
raw-row export PII, typed flag-combination errors, and MCP parity."""
from __future__ import annotations

import csv as _csv
import io

import pytest

from cage import (attribution, calibration, cli, compare, csvout, exportcmd,
                  humanview, ledger, metering, policy, report, roi, schema,
                  study, tasks, trend)

POL = policy.load(None)

# ── goldens over the seeded §4.4 demo ledger (no volatile fields render) ──────

REPORT_GOLDEN = (
    "route,calls,tokens_in,tokens_out,cached_in,cost_usd,unpriced_calls,unpriced_tokens,method\n"
    "code-edit,1,8600,1500,0,0.0483,0,0,measured\n"
    "TOTAL,1,8600,1500,0,0.0483,0,0,measured\n")

REPORT_TASK_GOLDEN = (
    "task,calls,tokens_in,tokens_out,cached_in,cost_usd,saved_usd,net_usd,"
    "unpriced_calls,unpriced_tokens,method\n"
    "fix-handover-bug,1,8600,1500,0,0.0483,0.1242,0.0759,0,0,measured\n"
    "TOTAL,1,8600,1500,0,0.0483,0.1242,0.0759,0,0,measured\n")

ATTRIB_GOLDEN = (
    "tool,saved_tokens,saved_usd,method,confidence,priced_via\n"
    "graphify,27000,0.081,modeled,1,\n"
    "fux,6400,0.0192,modeled,1,\n"
    "compressor,8000,0.024,measured,1,\n"
    "TOTAL,41400,0.1242,,,\n")

ROI_GOLDEN = (
    "tool,receipts,saved_usd,own_cost_usd,net_usd,added_latency_ms,method,"
    "priced_via\n"
    "graphify,1,0.081,0,0.081,0,modeled,call\n"
    "compressor,1,0.024,0,0.024,0,measured,call\n"
    "fux,1,0.0192,0,0.0192,0,modeled,call\n")


def test_report_csv_golden(seeded):
    root, _ = seeded
    rep = report.summarize(root, POL, dim="route")
    assert report.render_csv(rep) == REPORT_GOLDEN


def test_report_csv_savings_dim_golden(seeded):
    root, _ = seeded
    rep = report.summarize(root, POL, dim="task")
    assert report.render_csv(rep) == REPORT_TASK_GOLDEN


def test_attrib_csv_golden(seeded):
    root, _ = seeded
    data = attribution.attribute(root, "fix-handover-bug", POL)
    assert attribution.render_csv(data) == ATTRIB_GOLDEN


def test_roi_csv_golden(seeded):
    root, _ = seeded
    data = roi.by_tool(root, POL)
    assert roi.render_csv(data) == ROI_GOLDEN


def test_csv_determinism_double_run(seeded):
    """Same ledger + same policy ⇒ byte-identical CSV on every view (flux law)."""
    root, _ = seeded
    renders = [
        lambda: report.render_csv(report.summarize(root, POL, dim="route")),
        lambda: attribution.render_csv(attribution.attribute(root, "fix-handover-bug", POL)),
        lambda: roi.render_csv(roi.by_tool(root, POL)),
        lambda: compare.render_csv(compare.summarize(root, POL)),
        lambda: calibration.render_csv(calibration.summarize(root, POL)),
        lambda: calibration.render_csv_human(calibration.summarize_human(root, POL)),
        lambda: humanview.render_csv(humanview.rollup(root, POL)),
        lambda: trend.render_csv(trend.series(root, POL)),
        lambda: study.render_csv(study.summarize(root, POL)),
    ]
    for fn in renders:
        first = fn()
        assert fn() == first
        assert "\r" not in first  # LF pinned regardless of OS
        assert first.endswith("\n")


# ── one structure feeds both renderers: text and CSV agree by construction ────

def test_text_and_csv_same_numbers(seeded):
    root, _ = seeded
    rep = report.summarize(root, POL, dim="route")
    text = report.render_report(rep)
    rows = list(_csv.reader(io.StringIO(report.render_csv(rep))))
    head, total = rows[0], rows[-1]
    usd = float(total[head.index("cost_usd")])
    assert usd == pytest.approx(rep["total"]["usd"], abs=1e-6)
    assert f"${usd:,.4f}" in text  # the text table prints the same figure

    data = attribution.attribute(root, "fix-handover-bug", POL)
    arows = list(_csv.reader(io.StringIO(attribution.render_csv(data))))
    saved = float(arows[-1][arows[0].index("saved_usd")])
    assert saved == pytest.approx(data["total_saved_usd"], abs=1e-9)
    assert f"${saved:,.4f}" in attribution.render_attrib(data)


def test_method_tag_column_on_every_view(seeded):
    """`method` is sacred: every view CSV carries it as a column."""
    root, _ = seeded
    headers = [
        report.render_csv(report.summarize(root, POL, dim="route")),
        attribution.render_csv(attribution.attribute(root, "fix-handover-bug", POL)),
        roi.render_csv(roi.by_tool(root, POL)),
        compare.render_csv(compare.summarize(root, POL)),
        calibration.render_csv(calibration.summarize(root, POL)),
        calibration.render_csv_human(calibration.summarize_human(root, POL)),
        humanview.render_csv(humanview.rollup(root, POL)),
        trend.render_csv(trend.series(root, POL)),
        study.render_csv(study.summarize(root, POL)),
    ]
    for out in headers:
        assert "method" in out.splitlines()[0].split(",")


def test_priced_via_column_where_text_footnotes(seeded):
    """The receipt-pricing rung is a CSV column wherever the text view footnotes
    it (roi + attrib, plan §4.5) — the spreadsheet sees the provenance too."""
    root, _ = seeded
    for out in (attribution.render_csv(attribution.attribute(root, "fix-handover-bug", POL)),
                roi.render_csv(roi.by_tool(root, POL))):
        assert "priced_via" in out.splitlines()[0].split(",")


def test_attrib_csv_keeps_estimated_tag(proj):
    """An `estimated` receipt must survive into the spreadsheet as `estimated`."""
    cid = metering.record_call(route="r", provider="anthropic",
                               model="claude-sonnet-4-6", tokens_in=100,
                               task="t-est", root=proj)
    metering.record_receipt(tool="guessy", raw_alternative=1000, actual=100,
                            call=cid, task="t-est", method="estimated", root=proj)
    out = attribution.render_csv(attribution.attribute(proj, "t-est", POL))
    row = next(r for r in _csv.reader(io.StringIO(out)) if r and r[0] == "guessy")
    assert row[3] == "estimated"


# ── compare / study / calibration: deltas tagged, refusals + caveats survive ──

def _seed_compare(root):
    for i in range(5):
        tid = f"plain-{i}"
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="anthropic", model="claude-opus-4-8",
            tokens_in=10000 + i * 1000, tokens_out=500, task=tid, session=f"s-{tid}",
            agent="claude-code", ts=f"2026-06-1{i}T10:00:00Z"))
        tasks.record(root, tid, outcome="ok", ts=f"2026-06-1{i}T18:00:00Z", snapshot=False)
    for i in range(5):
        tid = f"graph-{i}"
        c = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4-8",
                             tokens_in=4000 + i * 500, tokens_out=500, task=tid,
                             session=f"s-{tid}", agent="claude-code",
                             ts=f"2026-06-2{i}T10:00:00Z")
        ledger.append_row(root, "calls", c)
        ledger.append_row(root, "receipts", schema.make_receipt(
            tool="graphify", raw_alternative=1000, actual=100, task=tid,
            call=c["id"], ts=f"2026-06-2{i}T10:00:00Z"))
        tasks.record(root, tid, outcome="ok", ts=f"2026-06-2{i}T18:00:00Z", snapshot=False)


def test_compare_csv_delta_estimated_with_caveat(proj):
    _seed_compare(proj)
    d = compare.summarize(proj, POL)
    rows = list(_csv.reader(io.StringIO(compare.render_csv(d))))
    head = rows[0]
    kinds = {r[0] for r in rows[1:]}
    assert {"group", "delta"} <= kinds
    delta = next(r for r in rows[1:] if r[0] == "delta")
    assert delta[head.index("method")] == "estimated"
    assert "not a controlled experiment" in delta[head.index("note")]
    groups = [r for r in rows[1:] if r[0] == "group"]
    assert all(g[head.index("method")] == "measured" for g in groups)


def test_compare_csv_refusal_carries_no_numbers(proj):
    """Below min-n the CSV row explains, never numbers (same as the text view)."""
    tid = "lonely-0"
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=1000, tokens_out=100, task=tid, session=f"s-{tid}",
        ts="2026-06-01T10:00:00Z"))
    tasks.record(proj, tid, outcome="ok", ts="2026-06-01T18:00:00Z", snapshot=False)
    rows = list(_csv.reader(io.StringIO(compare.render_csv(compare.summarize(proj, POL)))))
    head, g = rows[0], rows[1]
    assert "insufficient data" in g[head.index("note")]
    assert g[head.index("median_tokens")] == "" and g[head.index("median_usd")] == ""


def test_study_csv_refused_delta_and_coverage(proj):
    from cage import machine
    machine.ensure(proj)
    study.start(proj, "baseline", ts="2026-06-01T00:00:00Z")
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=1000, tokens_out=100, session="s", ts="2026-06-02T10:00:00Z"))
    study.stop(proj, ts="2026-06-03T00:00:00Z")
    study.start(proj, "plugin", ts="2026-06-08T00:00:00Z")
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=500, tokens_out=50, session="s", ts="2026-06-09T10:00:00Z"))
    study.stop(proj, ts="2026-06-10T00:00:00Z")
    rows = list(_csv.reader(io.StringIO(study.render_csv(study.summarize(proj, POL)))))
    head = rows[0]
    kinds = [r[0] for r in rows[1:]]
    assert kinds.count("coverage") == 2 and "pooled" in kinds
    delta = next(r for r in rows[1:] if r[0] == "delta")
    assert "insufficient machines" in delta[head.index("note")]
    assert delta[head.index("d_usd_per_day")] == ""  # refused ⇒ no number


def test_calibration_csv_summary_and_tasks(proj):
    c = schema.make_call(route="chat", provider="anthropic", model="claude-opus-4-8",
                         tokens_in=1000, tokens_out=50, task="est-1", session="s-est-1",
                         ts="2026-06-01T10:00:00Z")
    ledger.append_row(proj, "calls", c)
    tasks.record(proj, "est-1", outcome="ok", ts="2026-06-01T18:00:00Z", snapshot=False,
                 est_tokens=1000, est_tokens_q1=900, est_tokens_q3=1100, est_usd=0.1,
                 est_n=5)
    d = calibration.summarize(proj, POL)
    rows = list(_csv.reader(io.StringIO(calibration.render_csv(d))))
    head = rows[0]
    task_row = next(r for r in rows[1:] if r[0] == "task")
    assert task_row[head.index("in_band")] == "true"  # 1050 inside 900–1100
    summary = next(r for r in rows[1:] if r[0] == "summary")
    assert summary[head.index("hit_rate")] == "1"
    assert summary[head.index("method")] == "measured"


def test_calibration_human_csv_refusal_note(proj):
    d = calibration.summarize_human(proj, POL)
    rows = list(_csv.reader(io.StringIO(calibration.render_csv_human(d))))
    head, summary = rows[0], rows[-1]
    assert "insufficient data" in summary[head.index("note")]
    assert summary[head.index("median_ratio")] == ""


def test_human_and_trend_csv_keep_sources_apart(proj):
    cid = metering.record_call(route="r", provider="anthropic",
                               model="claude-sonnet-4-6", tokens_in=100,
                               task="h-1", agent="claude-code", root=proj)
    metering.record_human(task="h-1", minutes=90, call=cid, agent="claude-code",
                          root=proj)
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8", tokens_in=10,
        tokens_out=1, session="s", agent="claude-code", gap_ms=120000,
        ts="2026-06-01T10:00:00Z"))
    for out in (humanview.render_csv(humanview.rollup(proj, POL)),
                trend.render_csv(trend.series(proj, POL))):
        rows = list(_csv.reader(io.StringIO(out)))
        head = rows[0]
        kinds = {r[0] for r in rows[1:]}
        assert {"attested", "derived"} <= kinds  # never blended into one number
        derived = next(r for r in rows[1:] if r[0] == "derived")
        assert derived[head.index("method")] == "estimated"
        assert "never summed" in derived[head.index("note")]


# ── UNPRICED visibility survives into the spreadsheet ─────────────────────────

def test_report_csv_unpriced_columns(proj):
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="mystery", model="who-knows", tokens_in=1000,
        tokens_out=200, session="s", ts="2026-06-01T10:00:00Z"))
    rep = report.summarize(proj, POL, dim="route")
    rows = list(_csv.reader(io.StringIO(report.render_csv(rep))))
    head, total = rows[0], rows[-1]
    assert total[head.index("unpriced_calls")] == "1"
    assert total[head.index("unpriced_tokens")] == "1200"


def test_compare_csv_unpriced_row(proj):
    _seed_compare(proj)
    ledger.append_row(proj, "calls", schema.make_call(
        route="chat", provider="mystery", model="who-knows", tokens_in=7,
        tokens_out=0, session="s-x", ts="2026-06-30T10:00:00Z"))
    rows = list(_csv.reader(io.StringIO(compare.render_csv(compare.summarize(proj, POL)))))
    unpriced = next(r for r in rows[1:] if r[0] == "unpriced")
    assert "UNPRICED" in unpriced[rows[0].index("note")]


# ── RFC-4180 + the no-commas-by-validation guarantee ──────────────────────────

def test_rfc4180_quoting_round_trips(proj):
    """A meta dict with commas/quotes must round-trip through the csv module."""
    meta = {"note a": 'x,"y', "n": 3}
    c = schema.make_call(route="r", provider="anthropic", model="claude-sonnet-4-6",
                         tokens_in=10, ts="2026-06-01T10:00:00Z", call_id="c_q1")
    ledger.append_row(proj, "calls", c)
    r = schema.make_receipt(tool="quoty", raw_alternative=10, actual=1, call="c_q1",
                            meta=meta, ts="2026-06-01T10:00:00Z")
    ledger.append_row(proj, "receipts", r)
    out = exportcmd._csv(ledger.receipts(proj), "receipts")
    rows = list(_csv.reader(io.StringIO(out)))
    cell = rows[1][rows[0].index("meta")]
    assert cell == csvout.cell(meta)  # quoting reversed exactly by the reader


def test_label_and_phase_commas_rejected(proj, monkeypatch, capsys):
    """Labels/phases are single validated tokens — a comma can't reach a CSV cell."""
    monkeypatch.chdir(proj)
    assert cli.main(["outcome", "t1", "--label", "a,b"]) == 1
    assert cli.main(["study", "start", "a,b"]) == 1
    err = capsys.readouterr().err
    assert "label must be one short token" in err
    assert "phase must be one short token" in err


# ── raw-row export: PII surface, field contracts, LF file writes ──────────────

PII_MARKERS = ("content stripped", '"prompt"', '"message"', "commit message")


def test_export_raw_csv_all_kinds_pii_clean(seeded, monkeypatch, capsys):
    root, _ = seeded
    tasks.record(root, "fix-handover-bug", outcome="ok", snapshot=False)
    monkeypatch.chdir(root)
    for kind in ("calls", "receipts", "tasks"):
        assert cli.main(["export", "--no-import", "--csv", kind]) == 0
        out = capsys.readouterr().out
        header = out.splitlines()[0]
        assert header == ",".join(exportcmd.RAW_CSV_FIELDS[kind])
        for marker in PII_MARKERS:
            assert marker not in out, f"PII marker {marker!r} in {kind} csv"
        assert "\r" not in out


def test_export_format_csv_equals_csv_calls(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    assert cli.main(["export", "--no-import", "--format", "csv"]) == 0
    legacy = capsys.readouterr().out
    assert cli.main(["export", "--no-import", "--csv", "calls"]) == 0
    assert capsys.readouterr().out == legacy


def test_export_csv_file_write_pins_lf(seeded, tmp_path, monkeypatch):
    root, _ = seeded
    monkeypatch.chdir(root)
    out = tmp_path / "calls.csv"
    assert cli.main(["export", "--no-import", "--csv", "calls", "-o", str(out)]) == 0
    raw = out.read_bytes()
    assert b"\r" not in raw and raw.endswith(b"\n")


def test_view_csv_file_write_pins_lf(seeded, tmp_path, monkeypatch):
    root, _ = seeded
    monkeypatch.chdir(root)
    out = tmp_path / "report.csv"
    assert cli.main(["report", "--csv", str(out)]) == 0
    raw = out.read_bytes()
    assert b"\r" not in raw
    assert raw.decode("utf-8") == REPORT_GOLDEN


# ── typed errors for bad flag combinations ────────────────────────────────────

@pytest.mark.parametrize("argv", [
    ["report", "--csv", "--json"],
    ["human", "--csv", "--html", "x.html"],
    ["study", "id", "--csv"],
    ["study", "start", "phase1", "--csv"],
    ["export", "--no-import", "--csv", "calls", "--format", "json"],
    ["export", "--no-import", "--csv", "receipts", "--agent", "claude"],
    ["export", "--no-import", "--csv", "tasks", "--project", "."],
    ["export", "--study", "--csv", "calls"],
])
def test_bad_flag_combinations_are_typed_errors(proj, monkeypatch, capsys, argv):
    monkeypatch.chdir(proj)
    assert cli.main(argv) == 1
    assert capsys.readouterr().err.startswith("error: ")


def test_cli_csv_views_exit_zero_and_match_library(seeded, monkeypatch, capsys):
    root, _ = seeded
    monkeypatch.chdir(root)
    metering._policy_for.cache_clear()
    for argv in (["report", "--csv"], ["attrib", "--csv"], ["roi", "--csv"],
                 ["compare", "--csv"], ["calibration", "--csv"],
                 ["calibration", "--human", "--csv"], ["human", "--csv"],
                 ["trend", "--csv"], ["study", "report", "--csv"]):
        assert cli.main(argv) == 0, argv
    # stdout is pure CSV data — the last command's output starts with its header
    assert capsys.readouterr().out.startswith("route,calls,")


# ── MCP parity: format=csv returns the same CSV the CLI emits ─────────────────

def test_mcp_format_csv_parity(seeded, monkeypatch):
    root, _ = seeded
    from cage import mcpserver
    monkeypatch.setenv("CAGE_BASE", str(root / ".cage"))
    assert mcpserver._call("cage_report", {"format": "csv"}) == REPORT_GOLDEN
    assert mcpserver._call("cage_attrib", {"format": "csv"}) == ATTRIB_GOLDEN
    assert mcpserver._call("cage_roi", {"format": "csv"}) == ROI_GOLDEN
    # default stays the text table
    assert mcpserver._call("cage_report", {}).startswith("Ledger by route")
    # every CSV-capable tool declares the param
    for tool in mcpserver.TOOLS:
        if tool["name"] in ("cage_report", "cage_attrib", "cage_roi"):
            assert "format" in tool["inputSchema"]["properties"]


# ── query + rendered skill assets carry the recipes ───────────────────────────

def test_query_csv_output_answers():
    from cage import explain
    hits = explain.match("csv-output")
    assert hits and hits[0].id == "csv-output"
    body = explain.render(hits[0], POL)
    assert "never an import source" in body and "merge-by-id" in body


def test_rendered_skills_teach_reporting_recipes():
    """All four hosts' rendered assets carry the recipes + summarization rules
    (edited via skillgen fragments only — --check guards hand-edit drift)."""
    from pathlib import Path
    repo = Path(__file__).resolve().parents[1]
    for rel in ("cage/data/skills/cage/SKILL.md",
                "cage/data/prompts/cage.prompt.md",
                "cage/data/steering/cage.md",
                "cage/data/skills/agents/cage/SKILL.md"):
        body = (repo / rel).read_text(encoding="utf-8")
        assert "Reporting recipes" in body, rel
        assert "cage report --csv --since 7d" in body, rel
        assert "verbatim" in body and "INSUFFICIENT DATA" in body, rel
        assert "never blur the two" in body, rel
