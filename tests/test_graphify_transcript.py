"""GC2 + GC3 (graphify-capture plan) — transcript-side detection and cross-route dedupe.

GC2: at import, detect graphify use in claude transcripts — Bash `graphify query|path|
explain` (any invocation form; `grep graphify` must NOT match) and Reads of
`graphify-out/GRAPH_REPORT.md`/`wiki/**` (the invocation-less saving, filed as a distinct
lower-confidence `report-read` receipt).

GC3 (ADR 0005) — the two binding acceptance tests, both must pass:
  1. same query in TWO sessions  ⇒ TWO receipts (per-session attribution preserved);
  2. same query via shim + transcript in ONE session ⇒ EXACTLY ONE receipt (deferral).
Content-only ids fail (1); naive session ids fail (2).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import graphifymeter, graphifytx, ledger, savings
from cage.constants import (GRAPHIFY_RECEIPT_CONFIDENCE,
                            GRAPHIFY_REPORT_READ_CONFIDENCE)


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    return tmp_path


def _write_transcript(path: Path, records: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")


def _bash_query(cwd: str, command: str, result: str, tid: str = "toolu_1") -> list[dict]:
    """An assistant Bash tool_use + the following user tool_result — the real claude
    transcript shape (content stripped elsewhere, but tool bodies are present: GC0)."""
    return [
        {"type": "assistant", "cwd": cwd, "uuid": "a1", "message": {"role": "assistant",
         "content": [{"type": "tool_use", "id": tid, "name": "Bash",
                      "input": {"command": command}}]}},
        {"type": "user", "cwd": cwd, "message": {"role": "user",
         "content": [{"type": "tool_result", "tool_use_id": tid, "content": result}]}},
    ]


def _gfx_ids(root: Path) -> set:
    return {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}


def _graphify_receipts(root: Path) -> list[dict]:
    return [r for r in ledger.receipts(root) if r.get("tool") == "graphify"]


# ── GC2: detection ──────────────────────────────────────────────────────────

def test_bash_query_files_one_modeled_receipt(proj):
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    tp = proj / "sess-A.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'graphify query "how does storage work"', answer))
    counts = graphifytx.detect_and_file(proj, tp, session="sess-A", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 1
    rc = _graphify_receipts(proj)
    assert len(rc) == 1
    assert rc[0]["method"] == "modeled"
    assert rc[0]["confidence"] == GRAPHIFY_RECEIPT_CONFIDENCE
    assert rc[0]["op"] == "query" and rc[0]["saved"] > 0
    # counts-never-content: neither the query text nor the answer text is on the row
    assert "storage" not in json.dumps(rc[0])


def test_grep_graphify_is_not_a_graphify_invocation(proj):
    # the false-positive case: `grep graphify` — command word is grep, not graphify
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    tp = proj / "sess.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'grep graphify *.py', answer))
    counts = graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 0
    assert _graphify_receipts(proj) == []


def test_graphify_ops_anchoring():
    # unit-level anchoring: only a command-position graphify counts
    assert graphifytx.graphify_ops('graphify query "x"') == [("query", ["graphify", "query", "x"])]
    assert graphifytx.graphify_ops('/venv/bin/graphify explain foo')[0][0] == "explain"
    assert graphifytx.graphify_ops('grep graphify file') == []
    assert graphifytx.graphify_ops('echo "run graphify query"') == []
    assert graphifytx.graphify_ops('cat x | grep graphify') == []


def test_path_op_cites_no_files_so_no_receipt(proj):
    tp = proj / "sess.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'graphify path A B', "A --rel--> B\n"))
    counts = graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 0 and _graphify_receipts(proj) == []


def test_parse_miss_files_no_receipt(proj):
    # a query whose answer cites nothing resolvable → unmeasurable, no receipt
    tp = proj / "sess.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'graphify query "x"', "no citations\n"))
    counts = graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 0 and _graphify_receipts(proj) == []


def test_report_read_files_distinct_lower_confidence_receipt(proj):
    # graph.json maps two source files; the agent read GRAPH_REPORT.md instead of them
    out = proj / "graphify-out"
    out.mkdir()
    (proj / "a.py").write_text("y = 2\n" * 300)
    (proj / "b.py").write_text("z = 3\n" * 300)
    (out / "graph.json").write_text(json.dumps({"nodes": [
        {"source_file": "a.py"}, {"source_file": "b.py"}]}))
    (out / "GRAPH_REPORT.md").write_text("# summary\n" * 20)
    tp = proj / "sess.jsonl"
    _write_transcript(tp, [
        {"type": "assistant", "cwd": str(proj), "message": {"content": [
            {"type": "tool_use", "id": "t1", "name": "Read",
             "input": {"file_path": str(proj / "graphify-out" / "GRAPH_REPORT.md")}}]}}])
    counts = graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["report_read"] == 1
    rc = _graphify_receipts(proj)
    assert len(rc) == 1
    assert rc[0]["op"] == "report-read"
    assert rc[0]["confidence"] == GRAPHIFY_REPORT_READ_CONFIDENCE
    assert rc[0]["confidence"] < GRAPHIFY_RECEIPT_CONFIDENCE  # weaker inference
    fn = graphifytx.report_read_footnote(rc)
    assert fn  # footnoted apart from query receipts
    assert "UNVALIDATED" in fn  # G.1: the 0.3 confidence is labelled a placeholder


# ── GC3: dedupe (ADR 0005 acceptance tests) ─────────────────────────────────

def test_same_query_two_sessions_two_receipts(proj):
    """Acceptance test 1: per-session attribution — content-only ids would collapse
    these to one; the session-inclusive id keeps them two, one per session."""
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    ids = _gfx_ids(proj)
    for sess in ("sess-A", "sess-B"):
        tp = proj / f"{sess}.jsonl"
        _write_transcript(tp, _bash_query(str(proj), 'graphify query "x"', answer))
        graphifytx.detect_and_file(proj, tp, session=sess, existing_ids=ids)
    assert len(_graphify_receipts(proj)) == 2


def test_shim_then_transcript_one_session_one_receipt(proj, monkeypatch):
    """Acceptance test 2: the shim files live (session-empty), then the transcript import
    of the SAME query in one session defers to it — exactly one receipt."""
    monkeypatch.chdir(proj)
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    # shim route: run graphify through the meter (a stand-in that prints the answer)
    shim = proj / "graphify"
    shim.write_text("#!/usr/bin/env python3\nimport sys\n"
                    f"sys.stdout.write({answer!r})\n")
    shim.chmod(0o755)
    graphifymeter.run(proj, [str(shim), "query", "x"], task="proj")
    assert len(_graphify_receipts(proj)) == 1        # shim filed one (session-empty)
    # transcript route: the same query, same session, now imported
    tp = proj / "sess.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'graphify query "x"', answer))
    counts = graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["deferred"] == 1
    assert len(_graphify_receipts(proj)) == 1        # still exactly one — converged


def test_reimport_is_idempotent(proj):
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    tp = proj / "sess.jsonl"
    _write_transcript(tp, _bash_query(str(proj), 'graphify query "x"', answer))
    graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    graphifytx.detect_and_file(proj, tp, session="sess", existing_ids=_gfx_ids(proj))
    assert len(_graphify_receipts(proj)) == 1        # union_by_id collapses re-imports


def test_deterministic_ids(proj):
    a = graphifymeter.receipt_id("s", "query", "h1", "h2")
    b = graphifymeter.receipt_id("s", "query", "h1", "h2")
    assert a == b and a.startswith("s_")
    assert graphifymeter.receipt_id("t", "query", "h1", "h2") != a  # session matters
