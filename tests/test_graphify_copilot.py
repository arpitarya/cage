"""F1 (OPEN-WORK) — copilot **CLI** transcript-side graphify detection.

Copilot's `~/.copilot/session-state/<id>/events.jsonl` pairs `tool.execution_start`
(`data.toolName=="bash"`, `data.arguments.command`) with `tool.execution_complete`
(`data.result.content`) by `toolCallId` — everything the claude detector needs. This
route REUSES the claude counterfactual/id/deferral (`graphifytx._file_query`), so it must
inherit its guarantees. The two ADR-0005 acceptance tests are re-asserted here for copilot:

  1. same query in TWO sessions ⇒ TWO receipts (per-session attribution);
  2. same query via shim + copilot transcript in ONE session ⇒ EXACTLY ONE receipt (deferral).

The copilot **VS Code** `chatSessions` store is NOT covered — command present, result
absent (F2), so it can size no counterfactual (usage row without a receipt).
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import graphifymeter, graphifytx, ledger
from cage.constants import GRAPHIFY_RECEIPT_CONFIDENCE


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    return tmp_path


def _events(cwd: str, command: str, result: str, tid: str = "call_1") -> list[dict]:
    """A copilot CLI events.jsonl sequence: session.start (carries cwd) + a bash
    tool.execution_start/complete pair (the real shape probed on a live machine)."""
    return [
        {"type": "session.start", "data": {"context": {"cwd": cwd}}},
        {"type": "tool.execution_start", "data": {
            "toolCallId": tid, "toolName": "bash", "arguments": {"command": command}}},
        {"type": "tool.execution_complete", "data": {
            "toolCallId": tid, "success": True, "result": {"content": result}}},
    ]


def _write_events(session_dir: Path, records: list[dict]) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    p = session_dir / "events.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return p


def _gfx_ids(root: Path) -> set:
    return {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}


def _receipts(root: Path) -> list[dict]:
    return [r for r in ledger.receipts(root) if r.get("tool") == "graphify"]


# ── detection ────────────────────────────────────────────────────────────────

def test_copilot_bash_query_files_one_modeled_receipt(proj):
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    ev = _write_events(proj / "sess-A", _events(str(proj), 'graphify query "how storage works"', answer))
    counts = graphifytx.detect_and_file_copilot(proj, ev, session="sess-A", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 1
    rc = _receipts(proj)
    assert len(rc) == 1
    assert rc[0]["method"] == "modeled" and rc[0]["op"] == "query"
    assert rc[0]["confidence"] == GRAPHIFY_RECEIPT_CONFIDENCE and rc[0]["saved"] > 0
    # counts-never-content: neither the query nor the answer text lands on the row
    assert "storage" not in json.dumps(rc[0])


def test_copilot_grep_graphify_is_not_an_invocation(proj):
    """False-positive guard, mirrored from claude: `grep graphify` is command word grep."""
    (proj / "store.py").write_text("x = 1\n" * 400)
    ev = _write_events(proj / "s", _events(str(proj), 'grep -r graphify .', "some matches\n"))
    counts = graphifytx.detect_and_file_copilot(proj, ev, session="s", existing_ids=_gfx_ids(proj))
    assert counts["query"] == 0 and _receipts(proj) == []


def test_copilot_reimport_is_idempotent(proj):
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    ev = _write_events(proj / "sess", _events(str(proj), 'graphify query "x"', answer))
    graphifytx.detect_and_file_copilot(proj, ev, session="sess", existing_ids=_gfx_ids(proj))
    graphifytx.detect_and_file_copilot(proj, ev, session="sess", existing_ids=_gfx_ids(proj))
    assert len(_receipts(proj)) == 1        # union_by_id collapses the re-import


# ── ADR 0005 acceptance tests, extended to copilot ───────────────────────────

def test_copilot_same_query_two_sessions_two_receipts(proj):
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    ids = _gfx_ids(proj)
    for sess in ("sess-A", "sess-B"):
        ev = _write_events(proj / sess, _events(str(proj), 'graphify query "x"', answer))
        graphifytx.detect_and_file_copilot(proj, ev, session=sess, existing_ids=ids)
    assert len(_receipts(proj)) == 2        # per-session attribution preserved


def test_copilot_shim_then_transcript_one_receipt(proj, monkeypatch):
    """The shim files live (session-empty); the copilot transcript of the SAME query in
    one session recomputes the shim's id and defers — exactly one receipt. Cross-route
    convergence holds for copilot because `content_signature` is route-independent."""
    monkeypatch.chdir(proj)
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    shim = proj / "graphify"
    shim.write_text("#!/usr/bin/env python3\nimport sys\n"
                    f"sys.stdout.write({answer!r})\n")
    shim.chmod(0o755)
    graphifymeter.run(proj, [str(shim), "query", "x"], task="proj")
    assert len(_receipts(proj)) == 1        # shim filed one (session-empty)
    ev = _write_events(proj / "sess", _events(str(proj), 'graphify query "x"', answer))
    counts = graphifytx.detect_and_file_copilot(proj, ev, session="sess", existing_ids=_gfx_ids(proj))
    assert counts["deferred"] == 1
    assert len(_receipts(proj)) == 1        # still exactly one — converged across routes
