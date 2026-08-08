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


# ── GFX-COV/P3: the cursor-blind backfill (`cage import --rescan-graphify`) ──

def test_rescan_graphify_backfills_a_cursor_consumed_session(proj, monkeypatch):
    """The defect this flag exists for: the import cursor is keyed on (size, mtime) and
    skips an unchanged log — right for calls, wrong for savings. A route that ships AFTER
    a session was ingested can otherwise never see that session again, which is exactly
    how copilot VS Code and kiro stayed dark. A rescan walks the full match set."""
    from cage import clicmds, importcmd
    from tests.srcseed import mkcage
    mkcage(proj)
    (proj / "store.py").write_text("x = 1\n" * 400)
    answer = "NODE store [src=store.py loc=L1 community=0]\n"
    home = proj / "copilot-home"
    _write_events(home / "session-state" / "sess",
                  _events(str(proj), 'graphify query "x"', answer))
    for env in ("CLAUDE_CONFIG_DIR", "KIRO_DATA_DIR", "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(proj / f"home-{env.lower()}"))
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.chdir(proj)

    def run(rescan: bool) -> int:
        args = type("A", (), {"agent": "copilot", "since": None, "path": None,
                              "project": None, "ledger": None, "quiet": True,
                              "no_import": False, "rescan_graphify": rescan})()
        assert clicmds.cmd_import(args) == 0
        return len(_receipts(proj))

    assert run(False) == 1                     # first sweep files the receipt
    # Delete the receipt shards and re-import: the cursor now skips the file entirely,
    # so an ordinary sweep cannot refile it — the exact hole the flag closes.
    for shard in (proj / ".cage" / "ledger").rglob("savings-*.jsonl"):
        shard.unlink()
    assert _receipts(proj) == []
    assert run(False) == 0                     # cursor-blind: an ordinary sweep is blind
    assert run(True) == 1                      # the rescan reaches it
    assert run(True) == 1                      # and is idempotent


def test_rescan_graphify_reingests_no_call_rows(proj, monkeypatch):
    """Detection only: the flag must never turn into a second call-ingest path."""
    from cage import clicmds, ledger as _ledger
    from tests.srcseed import mkcage
    mkcage(proj)
    (proj / "store.py").write_text("x = 1\n" * 400)
    home = proj / "copilot-home"
    _write_events(home / "session-state" / "sess",
                  _events(str(proj), 'graphify query "x"',
                          "NODE store [src=store.py loc=L1 community=0]\n"))
    for env in ("CLAUDE_CONFIG_DIR", "KIRO_DATA_DIR", "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(proj / f"home-{env.lower()}"))
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.chdir(proj)
    base = type("A", (), {"agent": "copilot", "since": None, "path": None, "project": None,
                          "ledger": None, "quiet": True, "no_import": False,
                          "rescan_graphify": False})()
    clicmds.cmd_import(base)
    calls_before = [c["id"] for c in _ledger.calls(proj)]
    rescan = type("A", (), {**{k: getattr(base, k) for k in
                               ("agent", "since", "path", "project", "ledger", "quiet",
                                "no_import")}, "rescan_graphify": True})()
    clicmds.cmd_import(rescan)
    assert [c["id"] for c in _ledger.calls(proj)] == calls_before


# ── GFX-COV/P3: the coverage table is ONE table, and every gap is named ─────

def test_every_agent_surface_is_named_in_the_coverage_table():
    """A surface missing from the table is a silent zero — the failure this whole pair
    exists to end. Every agent in the product invariant must appear."""
    from cage import agents
    named = {row[0] for row in graphifytx.GRAPHIFY_COVERAGE}
    assert set(agents.SURFACES) <= named


def test_a_gap_is_worded_identically_in_doctor_and_the_explainer():
    """One table, two readers. If a future change re-derives either side, a gap starts
    being described two different ways and one of them goes stale silently."""
    from cage import doctorcmd, explain
    gap = next(row for row in graphifytx.GRAPHIFY_COVERAGE if not row[2])
    _, detail = doctorcmd._graphify_coverage()
    from cage import policy
    body = explain.render(explain.match("graphify-coverage")[0], policy.load(None))
    for text in (detail, body):
        assert gap[3].split(" — ")[0][:60] in text
