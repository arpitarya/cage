"""GFX-COV/P1 — copilot **VS Code** transcript-side graphify detection.

This store was skipped outright through v0.46 on the "F2" claim that it carried the
command but no tool result. The 2026-08-07 field probe measured that claim false
(`docs/research/2026-08-07-graphify-store-evidence.md`, 157 real files / 1,132
`run_in_terminal` parts): the store persists ``commandLine.original``, ``cwd.path`` and
the output via `resultDetails` or `terminalCommandOutput`.

The route REUSES the claude counterfactual/id/deferral (`graphifytx._file_query` /
`_file_report_read`), so it must inherit their guarantees — the two ADR-0005 acceptance
tests are re-asserted here, as they are for copilot-CLI.

Fixtures live in `tests/fixtures/transcripts/graphify/copilot-vscode/` and carry the
**real** part shapes; only the repo root placeholder is rewritten per test.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import graphifymeter, graphifytx, ledger
from cage.constants import (GRAPHIFY_RECEIPT_CONFIDENCE,
                            GRAPHIFY_REPORT_READ_CONFIDENCE)

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts" / "graphify" / "copilot-vscode"
PLACEHOLDER = "/tmp/gfxrepo"
# The graphify answer text the fixtures carry — cited files must exist for a counterfactual.
CITED = ("cage/ledger.py", "cage/graphifytx.py")


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    for rel in CITED:                       # the corpus the counterfactual is sized against
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x = 1\n" * 400)
    return tmp_path


def _plant(name: str, proj: Path) -> Path:
    """Copy a fixture into a real `workspaceStorage/<hash>/chatSessions/` layout with the
    placeholder repo root rewritten to this test's tmp dir."""
    raw = (FIXTURES / name).read_text(encoding="utf-8").replace(PLACEHOLDER, str(proj))
    dst = proj / "vscode-user" / "workspaceStorage" / "hash1" / "chatSessions"
    dst.mkdir(parents=True, exist_ok=True)
    out = dst / (json.loads(raw.splitlines()[0])["v"]["sessionId"] + ".jsonl")
    out.write_text(raw)
    return out


def _gfx_ids(root: Path) -> set:
    return {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}


def _receipts(root: Path) -> list[dict]:
    return [r for r in ledger.receipts(root) if r.get("tool") == "graphify"]


def _detect(proj: Path, path: Path, session: str = "s") -> dict:
    return graphifytx.detect_and_file_copilot_vscode(
        proj, path, session=session, existing_ids=_gfx_ids(proj))


def _fixture_lines(proj: Path) -> list[dict]:
    """The real capture's records, repo root rewritten, ready to mutate per test."""
    raw = (FIXTURES / "chatSession-graphify.jsonl").read_text(encoding="utf-8")
    return [json.loads(x) for x in raw.replace(PLACEHOLDER, str(proj)).splitlines()]


def _terminal_part(proj: Path) -> dict:
    part = _fixture_lines(proj)[2]["v"][0]["response"][0]
    assert part["toolId"] == "run_in_terminal"
    return part


def _graph(proj: Path) -> None:
    """A graphify-out/ the report-read counterfactual can size itself against."""
    out = proj / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps(
        {"nodes": [{"source_file": rel} for rel in CITED]}))
    (out / "GRAPH_REPORT.md").write_text("# summary\n" * 20)


# ── detection ────────────────────────────────────────────────────────────────

def test_terminal_graphify_query_files_one_modeled_receipt(proj):
    counts = _detect(proj, _plant("chatSession-graphify.jsonl", proj))
    assert counts["query"] == 1
    rc = [r for r in _receipts(proj) if r["op"] == "query"]
    assert len(rc) == 1
    assert rc[0]["method"] == "modeled"          # never `measured` — method law
    assert rc[0]["confidence"] == GRAPHIFY_RECEIPT_CONFIDENCE and rc[0]["saved"] > 0


def test_report_read_files_from_a_readFile_part(proj):
    """`copilot_readFile` carries the path in `invocationMessage.uris[].path` and needs
    no result text — its `actual` is the report on disk. The repo root is recovered from
    the absolute path itself (a readFile part carries no cwd).

    Its own fixture, not the query one: the real captured session contained no report
    read, and folding a synthetic part into a real capture would launder invention into
    a fixture labelled real."""
    _graph(proj)
    counts = _detect(proj, _plant("chatSession-report-read.jsonl", proj))
    assert counts["report_read"] == 1
    rr = [r for r in _receipts(proj) if r["op"] == "report-read"]
    assert len(rr) == 1
    assert rr[0]["confidence"] == GRAPHIFY_REPORT_READ_CONFIDENCE
    assert rr[0]["confidence"] < GRAPHIFY_RECEIPT_CONFIDENCE   # weaker inference, apart


def test_the_session_id_comes_from_the_store_not_the_filename(proj):
    """`kind:0 v.sessionId` is authoritative — a receipt's per-session attribution must
    not depend on what the caller happened to pass."""
    path = _plant("chatSession-graphify.jsonl", proj)
    _detect(proj, path, session="whatever-the-caller-said")
    declared = json.loads(path.read_text().splitlines()[0])["v"]["sessionId"]
    assert [r["session"] for r in _receipts(proj) if r["op"] == "query"] == [declared]


def test_all_three_part_carriers_are_walked(proj):
    """Tool parts reach a reader three ways in this store; walking only one would see a
    fraction of the runs and read as "graphify was never used"."""
    part = _terminal_part(proj)

    def carriers(sid):
        req = {"requestId": "r0", "response": [part]}
        return [
            [{"kind": 0, "v": {"sessionId": sid, "requests": [req]}}],            # kind:0 snapshot
            [{"kind": 0, "v": {"sessionId": sid, "requests": []}},
             {"kind": 2, "k": ["requests"], "v": [req]}],                          # requests append
            [{"kind": 0, "v": {"sessionId": sid, "requests": []}},
             {"kind": 2, "k": ["requests", 0, "response"], "v": [part]}],          # response append
        ]

    for i in range(3):
        p = proj / f"carrier{i}.jsonl"
        p.write_text("\n".join(json.dumps(x) for x in carriers(f"c{i}")[i]) + "\n")
        assert _detect(proj, p, session=f"c{i}")["query"] == 1, f"carrier {i} was not walked"


def test_the_real_agent_command_shape_is_a_cd_prefix(proj):
    """**The field run's finding.** A real Copilot agent does not emit a bare
    `graphify query …` — it emits `cd <repo> && graphify query …`, because
    `run_in_terminal` reuses one shell across calls. The synthetic fixture this route was
    first written against had no `&&`, so nothing exercised the segment split until a real
    capture landed (2026-08-08). `graphify_ops` anchors on command position **per segment**,
    which is why it works — but it was working by luck of design, not by test."""
    assert _terminal_part(proj)["toolSpecificData"]["commandLine"]["original"].startswith("cd ")
    assert _detect(proj, _plant("chatSession-graphify.jsonl", proj))["query"] == 1
    # and the same shape must still reject a non-invocation in the second segment
    for cmd in (f"cd {proj} && grep -rn graphify cage/",
                f"cd {proj} && echo graphify query x"):
        p = _one_terminal(proj, f"neg{abs(hash(cmd))}.jsonl", result=None,
                          buffer="NODE ledger [src=cage/ledger.py loc=L1 community=0]\n")
        lines = [json.loads(x) for x in p.read_text().splitlines()]
        lines[0]["v"]["requests"][0]["response"][0]["toolSpecificData"]["commandLine"] = {
            "original": cmd, "toolEdited": cmd}
        p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
        assert _detect(proj, p)["query"] == 0, cmd


def test_the_real_capture_uses_the_fallback_output_carrier(proj):
    """Also from the field run: the real part carried **no `resultDetails`** — 89% of real
    parts don't. So the carrier that actually ran in the field is the ANSI-stripped UI
    buffer, not the preferred one. Pinned so a future change cannot quietly make
    `resultDetails` mandatory and silently drop most real runs."""
    assert "resultDetails" not in _terminal_part(proj)
    assert _detect(proj, _plant("chatSession-graphify.jsonl", proj))["query"] == 1


# ── false-positive and honesty guards ───────────────────────────────────────

def test_negative_fixture_files_nothing(proj):
    """`grep graphify`, `echo graphify`, a piped `grep` — none is a graphify invocation
    (command-position anchoring, GC2). Nor is a real graphify run whose part carries **no
    output carrier at all** (121/1,132 real parts look like that)."""
    counts = _detect(proj, _plant("chatSession-negative.jsonl", proj))
    assert counts["query"] == 0 and counts["report_read"] == 0
    assert _receipts(proj) == []


def test_a_failed_command_files_nothing(proj):
    """`terminalCommandState.exitCode != 0` — the output is an error message, not an
    answer, so it sizes no counterfactual. Never a partial saving."""
    counts = _detect(proj, _plant("chatSession-failed.jsonl", proj))
    assert counts["query"] == 0 and _receipts(proj) == []
    assert counts["skipped"] == 1            # skipped loudly, not silently ignored


def test_a_missing_terminal_state_files_nothing(proj):
    """No recorded state ⇒ cage cannot say the command completed ⇒ unmeasurable.
    53 real parts carry `terminalCommandState: None`."""
    lines = _fixture_lines(proj)
    lines[2]["v"][0]["response"][0]["toolSpecificData"]["terminalCommandState"] = None
    p = proj / "nostate.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert _detect(proj, p)["query"] == 0
    assert [r for r in _receipts(proj) if r["op"] == "query"] == []


def test_no_marker_string_is_matched_so_lint_output_is_not_a_false_positive(proj):
    """The regression the evidence bought: all 23 `truncat` hits across 1,132 real parts
    were rust clippy's `cast_possible_truncation` lint, not a VS Code marker. A substring
    guard would have refused a perfectly good receipt."""
    lines = _fixture_lines(proj)
    part = lines[2]["v"][0]["response"][0]
    poison = ("warning: casting `usize` to `u32` may truncate the value\n"
              "  = note: `-D clippy::cast-possible-truncation` implied by `-D warnings`\n")
    part["toolSpecificData"]["terminalCommandOutput"]["text"] += poison
    p = proj / "lint.jsonl"
    p.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert _detect(proj, p)["query"] == 1


# ── carrier precedence (P0 verdict A) ───────────────────────────────────────

def _one_terminal(proj: Path, name: str, *, result: str | None, buffer: str | None) -> Path:
    data = {"kind": "terminal",
            "commandLine": {"original": 'graphify query "q"', "toolEdited": ""},
            "cwd": {"$mid": 1, "path": str(proj), "scheme": "file"},
            "terminalCommandState": {"exitCode": 0, "timestamp": 1, "duration": 1}}
    if buffer is not None:
        data["terminalCommandOutput"] = {"text": buffer, "lineCount": len(buffer.splitlines())}
    part = {"kind": "toolInvocationSerialized", "toolId": "run_in_terminal",
            "toolCallId": "t1", "isComplete": True, "toolSpecificData": data}
    if result is not None:
        part["resultDetails"] = {"input": "", "isError": False,
                                 "output": [{"type": "text", "isText": True, "value": result}]}
    p = proj / name
    p.write_text(json.dumps({"kind": 0, "v": {"sessionId": name, "requests": [
        {"requestId": "r", "response": [part]}]}}) + "\n")
    return p


def test_result_details_wins_over_the_ui_buffer(proj):
    """Verdict A: `resultDetails` is the model-facing result (the analogue of claude's
    `tool_result`); the UI buffer is the fallback. They differ by ~20% on real parts, so
    which one sizes `actual` is a real choice and is pinned here."""
    long_ = "NODE ledger [src=cage/ledger.py loc=L1 community=0]\n" * 4
    short = "NODE ledger [src=cage/ledger.py loc=L1 community=0]\n"
    both = _one_terminal(proj, "both.jsonl", result=short, buffer=long_)
    _detect(proj, both)
    from_result = [r for r in _receipts(proj) if r["op"] == "query"][0]["actual"]
    assert from_result == graphifymeter.toks(short)     # the model-facing carrier won


def test_the_ui_buffer_is_used_when_result_details_is_absent_and_is_ansi_stripped(proj):
    """89% of real parts have only the UI buffer, and 197 of them carry escape sequences —
    counting those as answer tokens would understate the saving."""
    plain = "NODE ledger [src=cage/ledger.py loc=L1 community=0]\n"
    painted = "\x1b[32mNODE\x1b[0m ledger [src=cage/ledger.py loc=L1 community=0]\n"
    _detect(proj, _one_terminal(proj, "buf.jsonl", result=None, buffer=painted))
    assert [r for r in _receipts(proj) if r["op"] == "query"][0]["actual"] == \
        graphifymeter.toks(plain)


# ── ADR 0005 acceptance tests, extended to copilot VS Code ──────────────────

def test_same_query_two_sessions_two_receipts(proj):
    for sess in ("A", "B"):
        p = _one_terminal(proj, f"{sess}.jsonl", result=None,
                          buffer="NODE ledger [src=cage/ledger.py loc=L1 community=0]\n")
        _detect(proj, p, session=sess)
    assert len([r for r in _receipts(proj) if r["op"] == "query"]) == 2   # per-session


def test_shim_then_vscode_store_files_exactly_one_receipt(proj, monkeypatch):
    """Cross-route dedupe: the shim files live (session-empty id), and the store route
    recomputes that id and defers. `content_signature` is route-independent, so this holds
    for VS Code exactly as it does for claude and copilot-CLI."""
    monkeypatch.chdir(proj)
    answer = "NODE ledger [src=cage/ledger.py loc=L1 community=0]\n"
    shim = proj / "graphify"
    shim.write_text("#!/usr/bin/env python3\nimport sys\n" f"sys.stdout.write({answer!r})\n")
    shim.chmod(0o755)
    graphifymeter.run(proj, [str(shim), "query", "q"], task="proj")
    assert len(_receipts(proj)) == 1
    counts = _detect(proj, _one_terminal(proj, "s.jsonl", result=None, buffer=answer))
    assert counts["deferred"] == 1
    assert len(_receipts(proj)) == 1        # converged across routes — never doubled


# ── determinism, idempotency, PII ───────────────────────────────────────────

def test_detection_is_deterministic_and_idempotent(proj):
    _graph(proj)
    path = _plant("chatSession-graphify.jsonl", proj)
    _detect(proj, path)
    first = sorted(json.dumps(r, sort_keys=True) for r in _receipts(proj))
    _detect(proj, path)                      # re-import: same store, same policy
    assert sorted(json.dumps(r, sort_keys=True) for r in _receipts(proj)) == first


def test_no_content_byte_from_the_store_reaches_the_ledger(proj):
    """Counts-never-content: the command text and the answer text are hashed, never
    written. Greps every ledger byte for every content string in the fixture."""
    _graph(proj)
    path = _plant("chatSession-graphify.jsonl", proj)
    _detect(proj, path)
    needles = {"how does the ledger append rows", "append_row", "_shard_for",
               "read_kind", "Running command in terminal"}
    blob = b"".join(p.read_bytes() for p in (proj / ".cage").rglob("*") if p.is_file())
    text = blob.decode("utf-8", errors="ignore")
    assert [n for n in needles if n in text] == []


# ── end to end, through the real import path ────────────────────────────────

def test_import_copilot_files_receipts_from_the_vscode_store(proj, monkeypatch):
    """The store is no longer skipped by `_detect_graphify_copilot` — the whole point."""
    from cage import clicmds
    from tests.srcseed import mkcage
    mkcage(proj)
    _graph(proj)
    _plant("chatSession-graphify.jsonl", proj)
    _plant("chatSession-report-read.jsonl", proj)      # both routes, one real sweep
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(proj / f"home-{env.lower()}"))
    monkeypatch.setenv("CAGE_VSCODE_USER", str(proj / "vscode-user"))
    monkeypatch.chdir(proj)          # the project `.cage/` is the resolved sink
    args = type("A", (), {"agent": "copilot", "since": None, "path": None, "project": None,
                          "ledger": None, "quiet": True, "no_import": False,
                          "rescan_graphify": False})()
    assert clicmds.cmd_import(args) == 0
    ops = sorted(r["op"] for r in _receipts(proj))
    assert ops == ["query", "report-read"]
    before = len(_receipts(proj))
    assert clicmds.cmd_import(args) == 0
    assert len(_receipts(proj)) == before    # idempotent across a real re-import
