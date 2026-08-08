"""GFX-COV/P2 — kiro **CLI** graphify detection over the `conversations_v2` store.

Kiro had no graphify route at all before this: `import_kiro` reads the IDE token log
(no commands, no results), and the CLI store's credits parser is bound to a numeric-key
whitelist. Reading tool bodies out of that store is the ADR-0009 carve-out — transient,
hashes only.

Shapes are pinned against two live `execute_bash` runs (kiro-cli 2.16.0, 2026-08-07;
`docs/research/2026-08-07-graphify-store-evidence.md`), including the truncation marker
this route refuses on. Fixtures are the real `value`-JSON shape.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cage import graphifymeter, graphifytx, ledger, transcript
from cage.constants import (GRAPHIFY_RECEIPT_CONFIDENCE,
                            GRAPHIFY_REPORT_READ_CONFIDENCE)
from tests.gfxfixture import PLACEHOLDER, load_json

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts" / "graphify" / "kiro-cli"
CITED = ("cage/ledger.py", "cage/graphifytx.py")


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    for rel in CITED:
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n" * 400)
    return tmp_path


def _db(proj: Path, *fixtures: str, key: str | None = None) -> Path:
    """A real-shape kiro-CLI SQLite store carrying the named fixture conversations."""
    path = proj / "data.sqlite3"
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE IF NOT EXISTS conversations_v2 "
                "(key TEXT, conversation_id TEXT, value TEXT, created_at INT, updated_at INT)")
    for name in fixtures:
        doc = load_json(FIXTURES / name, proj)
        con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                    (key if key is not None else str(proj), doc["conversation_id"],
                     json.dumps(doc), 0, 0))
    con.commit()
    con.close()
    return path


def _gfx_ids(root: Path) -> set:
    return {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}


def _receipts(root: Path) -> list[dict]:
    return [r for r in ledger.receipts(root) if r.get("tool") == "graphify"]


def _detect(proj: Path, db: Path, workspace: str = "") -> dict:
    return graphifytx.detect_and_file_kiro_cli(proj, db, workspace=workspace,
                                               existing_ids=_gfx_ids(proj), pol=None)


def _graph(proj: Path) -> None:
    out = proj / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps(
        {"nodes": [{"source_file": rel} for rel in CITED]}))
    (out / "GRAPH_REPORT.md").write_text("# summary\n" * 20)


# ── detection ────────────────────────────────────────────────────────────────

def test_execute_bash_graphify_query_files_one_modeled_receipt(proj):
    counts = _detect(proj, _db(proj, "conversation-graphify.json"))
    assert counts["query"] == 1
    rc = _receipts(proj)
    assert len(rc) == 1
    assert rc[0]["method"] == "modeled" and rc[0]["op"] == "query"
    assert rc[0]["confidence"] == GRAPHIFY_RECEIPT_CONFIDENCE and rc[0]["saved"] > 0


def test_the_session_is_the_conversation_id(proj):
    db = _db(proj, "conversation-graphify.json")
    _detect(proj, db)
    want = json.loads((FIXTURES / "conversation-graphify.json").read_text())["conversation_id"]
    assert [r["session"] for r in _receipts(proj)] == [want]


def test_fs_read_of_the_report_files_a_report_read(proj):
    """A report-read needs no result body at all — so kiro's stdout cap cannot affect it.
    That is why this route survives the truncation finding intact."""
    _graph(proj)
    counts = _detect(proj, _db(proj, "conversation-report-read.json"))
    assert counts["report_read"] == 1
    rr = _receipts(proj)
    assert rr[0]["op"] == "report-read"
    assert rr[0]["confidence"] == GRAPHIFY_REPORT_READ_CONFIDENCE


# ── the truncation guard (the load-bearing finding) ─────────────────────────

def test_truncated_stdout_files_nothing(proj):
    """kiro caps stdout at ~2000 tokens and cuts mid-token. A truncated answer
    under-counts `actual`, which would *inflate* the saving — so it is unmeasurable."""
    counts = _detect(proj, _db(proj, "conversation-truncated.json"))
    assert counts["query"] == 0 and _receipts(proj) == []
    assert counts["skipped"] == 1        # refused loudly, not silently dropped


def test_the_truncation_marker_is_anchored_not_a_substring(proj):
    """The false positive the VS Code corpus actually produced: a command whose OWN
    output discusses truncation (rust clippy's `cast_possible_truncation`) must still
    file. Matching the marker as a substring anywhere would have refused this."""
    raw = load_json(FIXTURES / "conversation-graphify.json", proj)
    for entry in raw["history"]:
        content = (entry.get("user") or {}).get("content") or {}
        for res in (content.get("ToolUseResults") or {}).get("tool_use_results") or []:
            for blk in res["content"]:
                blk["Json"]["stdout"] = (
                    f"note: `-D clippy::cast-possible-truncation`\n"
                    f"{transcript.KIRO_CLI_TRUNCATION_MARKER} was not appended by kiro\n"
                    + blk["Json"]["stdout"])
    db = proj / "d.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE conversations_v2 "
                "(key TEXT, conversation_id TEXT, value TEXT, created_at INT, updated_at INT)")
    con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                (str(proj), raw["conversation_id"], json.dumps(raw), 0, 0))
    con.commit(); con.close()
    assert _detect(proj, db)["query"] == 1


def test_a_nonzero_exit_status_files_nothing(proj):
    raw = load_json(FIXTURES / "conversation-graphify.json", proj)
    for entry in raw["history"]:
        content = (entry.get("user") or {}).get("content") or {}
        for res in (content.get("ToolUseResults") or {}).get("tool_use_results") or []:
            for blk in res["content"]:
                blk["Json"]["exit_status"] = "1"
    db = proj / "d.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE conversations_v2 "
                "(key TEXT, conversation_id TEXT, value TEXT, created_at INT, updated_at INT)")
    con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                (str(proj), raw["conversation_id"], json.dumps(raw), 0, 0))
    con.commit(); con.close()
    assert _detect(proj, db)["query"] == 0 and _receipts(proj) == []


def test_a_tool_use_whose_turn_errored_before_the_result_files_nothing(proj):
    """Observed on a real probe run: the ToolUse persists, its result never lands
    (results are written into the NEXT history entry). Half a run is not a saving."""
    counts = _detect(proj, _db(proj, "conversation-no-result.json"))
    assert counts["query"] == 0 and _receipts(proj) == []


def test_false_positive_guards_hold_on_kiro(proj):
    counts = _detect(proj, _db(proj, "conversation-negative.json"))
    assert counts["query"] == 0 and _receipts(proj) == []


# ── scoping: the sink question stays answered by the credits leg (ADR 0006) ──

def test_workspace_scoping_excludes_another_projects_conversation(proj):
    """The route never re-decides which tree it reads — it takes the same `workspace`
    the credits sweep resolved. A conversation from elsewhere is not this project's."""
    db = _db(proj, "conversation-graphify.json", key="/somewhere/else")
    assert _detect(proj, db, workspace=str(proj))["query"] == 0
    assert _receipts(proj) == []
    assert _detect(proj, db, workspace="")["query"] == 1      # a machine sweep sees it


# ── ADR 0005 acceptance tests, extended to kiro CLI ─────────────────────────

def test_same_query_two_conversations_two_receipts(proj):
    db = proj / "d.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE conversations_v2 "
                "(key TEXT, conversation_id TEXT, value TEXT, created_at INT, updated_at INT)")
    for cid in ("conv-A", "conv-B"):
        doc = load_json(FIXTURES / "conversation-graphify.json", proj)
        doc["conversation_id"] = cid
        con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                    (str(proj), cid, json.dumps(doc), 0, 0))
    con.commit(); con.close()
    assert _detect(proj, db)["query"] == 2
    assert len(_receipts(proj)) == 2       # per-session attribution preserved


def test_shim_then_kiro_store_files_exactly_one_receipt(proj, monkeypatch):
    """Cross-route dedupe on kiro: the shim files live (session-empty id) and the store
    route recomputes that id and defers. `content_signature` is route-independent."""
    monkeypatch.chdir(proj)
    doc = load_json(FIXTURES / "conversation-graphify.json", proj)
    answer = next(blk["Json"]["stdout"]
                  for e in doc["history"]
                  for res in ((e.get("user") or {}).get("content") or {})
                  .get("ToolUseResults", {}).get("tool_use_results", [])
                  for blk in res["content"])
    shim = proj / "graphify"
    shim.write_text("#!/usr/bin/env python3\nimport sys\n" f"sys.stdout.write({answer!r})\n")
    shim.chmod(0o755)
    graphifymeter.run(proj, [str(shim), "query", "how does the ledger append rows"],
                      task="proj")
    assert len(_receipts(proj)) == 1
    counts = _detect(proj, _db(proj, "conversation-graphify.json"))
    assert counts["deferred"] == 1
    assert len(_receipts(proj)) == 1       # converged across routes


# ── determinism, idempotency, PII (the ADR-0009 boundary, as a test) ────────

def test_detection_is_deterministic_and_idempotent(proj):
    _graph(proj)
    db = _db(proj, "conversation-graphify.json", "conversation-report-read.json")
    _detect(proj, db)
    first = sorted(json.dumps(r, sort_keys=True) for r in _receipts(proj))
    _detect(proj, db)
    assert sorted(json.dumps(r, sort_keys=True) for r in _receipts(proj)) == first


def test_no_tool_body_byte_reaches_the_ledger(proj):
    """ADR 0009's invariant, asserted rather than asserted-in-prose: the carve-out widens
    what may be READ, never what may be WRITTEN."""
    _graph(proj)
    _detect(proj, _db(proj, "conversation-graphify.json", "conversation-report-read.json"))
    needles = {"how does the ledger append rows", "append_row", "_shard_for", "read_kind",
               "content stripped", "execute_bash"}
    blob = b"".join(p.read_bytes() for p in (proj / ".cage").rglob("*") if p.is_file())
    assert [n for n in needles if n in blob.decode("utf-8", errors="ignore")] == []


def test_the_credits_parser_is_unchanged_by_the_carve_out(proj):
    """The whitelist still binds every function that WRITES a row from this store."""
    rows = transcript.parse_kiro_cli_credits(_db(proj, "conversation-graphify.json"),
                                             workspace=str(proj))
    for r in rows:
        blob = json.dumps(r)
        assert "graphify query" not in blob and "append_row" not in blob


def test_the_store_is_opened_read_only(proj):
    """cage never writes, migrates or locks a kiro DB — same discipline as the credits
    parser. Asserted by making the file itself unwritable."""
    db = _db(proj, "conversation-graphify.json")
    db.chmod(0o444)
    try:
        assert _detect(proj, db)["query"] == 1
    finally:
        db.chmod(0o644)


# ── end to end, through the real import path ────────────────────────────────

def test_import_files_kiro_cli_receipts_into_the_sweeps_own_sink(proj, monkeypatch):
    from cage import clicmds, paths, policy, metering
    from tests.srcseed import mkcage
    mkcage(proj)
    _graph(proj)
    _db(proj, "conversation-graphify.json", "conversation-report-read.json")
    fp = paths.Footprint(proj)
    fp.policy.write_text(fp.policy.read_text(encoding="utf-8") + f'''
[sources.kirocli]
paths = ["{proj / "data.sqlite3"}"]
format = "kiro-cli"
''', encoding="utf-8")
    metering._policy_for.cache_clear()
    monkeypatch.chdir(proj)
    args = type("A", (), {"agent": "all", "since": None, "path": None, "project": None,
                          "ledger": None, "quiet": True, "no_import": False,
                          "rescan_graphify": False})()
    assert clicmds.cmd_import(args) == 0
    assert sorted(r["op"] for r in _receipts(proj)) == ["query", "report-read"]
    before = len(_receipts(proj))
    assert clicmds.cmd_import(args) == 0
    assert len(_receipts(proj)) == before       # idempotent across a real re-import
    assert policy  # (imported for the fixture's config write)
