"""GC1 (graphify-capture plan) — the always-on graphify usage breadcrumb.

Two properties, both load-bearing:

1. **Every graphify run files a usage row** (shim route here; transcript route is
   covered in the GC2/GC3 tests) with `{op, args_hash, exit, ms, outcome}` — proving
   usage even when no receipt is filed (the F1 blind spot).
2. **Usage rows never perturb a derived money view** — report/attrib/roi are
   byte-identical whether or not the usage log exists. The row lives in `state/`,
   which no derived view reads; this asserts that invariant rather than trusting it.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import graphifymeter, paths, report, roi, usagelog
from cage.policy import load as load_policy


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    monkeypatch.delenv("CAGE_USAGE_LOG", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    # graphify runs in the repo root, so the shim's counterfactual resolves cited files
    # against cwd — mirror that (the GC2 transcript route resolves against explicit roots).
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _fake_graphify(tmp_path: Path, stdout: str, rc: int = 0) -> Path:
    """A stand-in `graphify` that prints a fixed answer — no real graphify needed to
    exercise the meter + usage-log path deterministically."""
    shim = tmp_path / "graphify"
    body = "#!/usr/bin/env python3\nimport sys\n"
    body += f"sys.stdout.write({stdout!r})\nsys.exit({rc})\n"
    shim.write_text(body)
    shim.chmod(0o755)
    return shim


def _usage_rows(root: Path) -> list[dict]:
    return usagelog.read(root)


def test_query_with_cited_file_files_receipt_and_usage_row(proj):
    # a source file the answer will cite, so the counterfactual resolves a real saving
    (proj / "store.py").write_text("x = 1\n" * 500)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    shim = _fake_graphify(proj, answer)
    rc = graphifymeter.run(proj, [str(shim), "query", "how"], task="t")
    assert rc == 0
    rows = _usage_rows(proj)
    assert len(rows) == 1
    r = rows[0]
    assert r["op"] == "query" and r["exit"] == 0 and r["outcome"] == "receipt"
    assert r["args_hash"] and "how" not in json.dumps(r)  # counts-never-content


def test_parse_miss_files_no_receipt_but_a_usage_row(proj):
    # an answer that cites nothing → no receipt, but usage is still visible
    shim = _fake_graphify(proj, "no citations here\n")
    graphifymeter.run(proj, [str(shim), "query", "how"], task="t")
    from cage import ledger
    assert ledger.receipts(proj) == []            # parse miss → no receipt (never fabricate)
    rows = _usage_rows(proj)
    assert len(rows) == 1 and rows[0]["outcome"] == "unmeasurable"


def test_empty_answer_is_outcome_empty(proj):
    shim = _fake_graphify(proj, "")
    graphifymeter.run(proj, [str(shim), "query", "how"], task="t")
    rows = _usage_rows(proj)
    assert len(rows) == 1 and rows[0]["outcome"] == "empty"


def test_non_measured_verb_records_non_measured(proj):
    shim = _fake_graphify(proj, "installed\n")
    graphifymeter.run(proj, [str(shim), "update", "."], task="t")
    rows = _usage_rows(proj)
    assert len(rows) == 1 and rows[0]["outcome"] == "non-measured"


def test_usage_rows_do_not_perturb_derived_views(proj):
    (proj / "store.py").write_text("x = 1\n" * 500)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    shim = _fake_graphify(proj, answer)
    graphifymeter.run(proj, [str(shim), "query", "how"], task="t")
    pol = load_policy(paths.Footprint(proj).policy)

    # snapshot the money views WITH the usage log present
    rep_with = report.render_report(report.summarize(proj, pol))
    roi_with = roi.by_tool(proj, pol)

    # delete the usage log entirely and re-derive — must be byte-identical
    paths.Footprint(proj).usage_log.unlink()
    rep_without = report.render_report(report.summarize(proj, pol))
    roi_without = roi.by_tool(proj, pol)

    assert rep_with == rep_without
    assert roi_with == roi_without


def test_summary_counts_match_rows(proj):
    (proj / "store.py").write_text("x = 1\n" * 500)
    ans = "NODE store [src=store.py loc=L1 community=0]\n"
    graphifymeter.run(proj, [str(_fake_graphify(proj, ans)), "query", "a"], task="t")
    graphifymeter.run(proj, [str(_fake_graphify(proj, "nope\n")), "query", "b"], task="t")
    s = usagelog.summary(proj)
    assert s["runs"] == 2
    assert s["outcomes"]["receipt"] == 1
    assert s["outcomes"]["unmeasurable"] == 1
