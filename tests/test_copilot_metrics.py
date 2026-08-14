"""COPILOT-METRICS — the `.cage/ledger/copilot/` per-chat metrics ledger.

Capture-only: a new row shape (`schema.make_copilot_metric`) fed by five on-disk
Copilot stores, collapsed last-write-wins at read (`ledger.copilot_metrics`), and read
by NO derived view in this build. What this file pins, following
`docs/copilot-metrics-ledger.handoff.md` §9:

1. The substrate — enum validation, omit-at-zero, None-sentinel credits/session_credits/
   nano_aiu, and the `model_totals` field-level whitelist.
2. Each of the five parsers records exactly what its store shape carries, verbatim.
3. Counts-never-content on the two content-adjacent stores (debuglog, otel) — a prompt
   body in the fixture must never reach a written row or the raw shard bytes.
4. Re-import is idempotent; a grown source appends a fresh row and the collapse read
   resolves to the latest/largest.
5. No derived view moves by one byte whether the `copilot/` tree exists or not.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from cage import cli, doctorcmd, importcmd, ledger, paths, schema, transcript

PROMPT_BODY_SENTINEL = "please refactor the auth module to use JWT tokens instead"


# ── 1 · substrate ────────────────────────────────────────────────────────────

def test_make_copilot_metric_validates_source():
    with pytest.raises(ValueError):
        schema.make_copilot_metric(source="bogus", session="s1")


def test_make_copilot_metric_omit_at_zero():
    row = schema.make_copilot_metric(source="chat", session="s1", metric_id="cm_x")
    for k in ("tokens_in", "tokens_out", "cached_in", "elapsed_ms", "waiting_ms",
              "ttft_ms", "surface", "request", "call", "model", "model_totals",
              "credits", "session_credits", "nano_aiu", "project"):
        assert k not in row


def test_make_copilot_metric_none_sentinel_credits_never_omit_at_default():
    """`credits`/`session_credits`/`nano_aiu` are None-sentinel — a recorded 0.0 must
    survive, distinct from an omitted (never-recorded) figure (the `make_call.credits`
    law, generalized)."""
    zero = schema.make_copilot_metric(source="cli", session="s1", credits=0.0,
                                      session_credits=0.0, nano_aiu=0.0,
                                      metric_id="cm_zero")
    assert zero["credits"] == 0.0 and zero["session_credits"] == 0.0 and zero["nano_aiu"] == 0.0
    absent = schema.make_copilot_metric(source="cli", session="s1", metric_id="cm_absent")
    assert "credits" not in absent and "session_credits" not in absent and "nano_aiu" not in absent


def test_make_copilot_metric_model_totals_whitelist():
    """`make_copilot_metric` accepts already-canonical `{model, tokens_in, cached_in,
    tokens_out}` entries (the parser does the store-key rename before calling it — the
    same layering `make_call` uses); only those four keys survive per entry — an
    unexpected key must never ride along into the ledger."""
    row = schema.make_copilot_metric(
        source="chat", session="s1", metric_id="cm_mt",
        model_totals=[{"model": "gpt-4", "tokens_in": 10, "cached_in": 2,
                       "tokens_out": 5, "userRequest": PROMPT_BODY_SENTINEL,
                       "extraneous": "drop-me"}])
    assert row["model_totals"] == [{"model": "gpt-4", "tokens_in": 10,
                                    "cached_in": 2, "tokens_out": 5}]
    assert PROMPT_BODY_SENTINEL not in json.dumps(row)


def test_copilot_model_totals_helper_renames_store_keys(tmp_path):
    """The renaming itself — `transcript._copilot_model_totals` mapping the STORE's raw
    `inputTokens`/`cachedTokens`/`outputTokens` into the canonical shape — is exercised
    end-to-end via `parse_copilot_vscode_metrics` (below) and `parse_copilot_cli_metrics`;
    this pins the helper directly for both its chatSessions and CLI shapes."""
    chat_totals, chat_cached = transcript._copilot_model_totals(
        {"modelTotals": [{"model": "gpt-4", "inputTokens": 10, "cachedTokens": 2,
                          "outputTokens": 5}]})
    assert chat_totals == [{"model": "gpt-4", "tokens_in": 10, "cached_in": 2,
                            "tokens_out": 5}]
    assert chat_cached == 2
    cli_totals, cli_cached = transcript._copilot_model_totals(
        {"gpt-4": {"usage": {"inputTokens": 500, "outputTokens": 200,
                             "cacheReadTokens": 50}}}, from_metrics=True)
    assert cli_totals == [{"model": "gpt-4", "tokens_in": 500, "cached_in": 50,
                           "tokens_out": 200}]
    assert cli_cached == 50


# ── fixture builders ─────────────────────────────────────────────────────────

def _vscode_store(path: Path, session: str, *reqs: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"kind": 0, "v": {"sessionId": session}}),
             json.dumps({"kind": 2, "k": ["requests"], "v": list(reqs)})]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _req(rid: str, **extra) -> dict:
    req = {"requestId": rid, "timestamp": 1755000000000, "modelId": "copilot/auto",
          "agent": {"extensionId": {"value": "github.copilot-chat"}},
          "promptTokens": 100, "completionTokens": 50}
    req.update(extra)
    return req


def _cli_events(path: Path, *shutdowns: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"type": "session.shutdown", "timestamp": ts, "data": data})
             for ts, data in shutdowns]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sidecar_line(**kw) -> dict:
    row = {"turnId": "t1", "model": "gpt-4o", "inputTokens": 200, "outputTokens": 80,
          "cacheReadTokens": 40, "totalNanoAiu": 250000000, "ts": "2026-08-13T00:00:00Z"}
    row.update(kw)
    return row


def _debuglog_line(**kw) -> dict:
    row = {"type": "llm_request", "spanId": "span1", "ts": "2026-08-13T00:00:00Z",
          "attrs": {"model": "gpt-4o", "inputTokens": 300, "outputTokens": 120,
                    "ttft": 450, "userRequest": PROMPT_BODY_SENTINEL,
                    "inputMessages": [PROMPT_BODY_SENTINEL]}}
    row.update(kw)
    return row


def _otel_db(path: Path, *, with_attributes_sentinel: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE spans (span_id TEXT, conversation_id TEXT, "
               "chat_session_id TEXT, request_model TEXT, response_model TEXT, "
               "input_tokens INTEGER, output_tokens INTEGER, cached_tokens INTEGER, "
               "reasoning_tokens INTEGER, ttft_ms INTEGER, start_time_ms INTEGER, "
               "end_time_ms INTEGER, operation_name TEXT)")
    con.execute("INSERT INTO spans VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ("span1", "conv1", None, "gpt-4o", "gpt-4o-2026", 400, 150, 60, 0,
                220, 1755000000000, 1755000001000, "chat"))
    if with_attributes_sentinel:
        con.execute("CREATE TABLE span_attributes (span_id TEXT, key TEXT, value TEXT)")
        con.execute("INSERT INTO span_attributes VALUES (?,?,?)",
                   ("span1", "otel.captureContent", PROMPT_BODY_SENTINEL))
    con.commit()
    con.close()


# ── 2 · vscode chatSessions parser ──────────────────────────────────────────

def test_vscode_metrics_parser_exact_row(tmp_path):
    p = tmp_path / "chatSessions" / "sess.jsonl"
    _vscode_store(p, "sess", _req(
        "req1", copilotCredits=0.33, sessionCopilotCredits=1.5,
        elapsedMs=2000, timeSpentWaiting=100,
        modelTotals=[{"model": "gpt-4", "inputTokens": 90, "cachedTokens": 10,
                     "outputTokens": 45}]))
    rows = transcript.parse_copilot_vscode_metrics(p, session="sess")
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "chat" and r["surface"] == "vscode" and r["session"] == "sess"
    assert r["request"] == "req1" and r["model"] == "copilot/auto"
    assert r["tokens_in"] == 100 and r["tokens_out"] == 50
    assert r["cached_in"] == 10  # summed from modelTotals, not the request-level fields
    assert r["model_totals"] == [{"model": "gpt-4", "tokens_in": 90,
                                  "cached_in": 10, "tokens_out": 45}]
    assert r["credits"] == 0.33 and r["session_credits"] == 1.5
    assert r["elapsed_ms"] == 2000 and r["waiting_ms"] == 100
    assert r["id"].startswith("cm_")


def test_vscode_metrics_zero_signal_request_yields_no_row(tmp_path):
    p = tmp_path / "chatSessions" / "sess.jsonl"
    _vscode_store(p, "sess", _req("req1", promptTokens=0, completionTokens=0))
    assert transcript.parse_copilot_vscode_metrics(p, session="sess") == []


def test_vscode_metrics_foreign_chat_provider_excluded(tmp_path):
    p = tmp_path / "chatSessions" / "sess.jsonl"
    _vscode_store(p, "sess", _req(
        "req1", agent={"extensionId": {"value": "some.other-chat-extension"}}))
    assert transcript.parse_copilot_vscode_metrics(p, session="sess") == []


def test_vscode_refactor_pins_the_format_verified_calls_fixture(tmp_path):
    """`_vscode_chat_requests` is a pure extraction — the real store fixture's CALLS
    output must stay byte-identical (COPILOT-METRICS handoff §4.4). Planted at its real
    relative layout (`test_fixture_corpus.py`'s technique) because the parser checks
    that layout before trusting the sidecar `workspace.json` for `project`."""
    import shutil
    fixdir = Path(__file__).parent / "fixtures" / "transcripts" / "copilot" / "vscode"
    expected = json.loads((fixdir / "expected.json").read_text(encoding="utf-8"))
    log = tmp_path / expected["plant"]
    log.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixdir / expected["log"], log)
    for rel, src in (expected.get("sidecars") or {}).items():
        side = tmp_path / rel
        side.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixdir / src, side)
    rows = transcript.parse_copilot_vscode_calls(log, session=log.stem)
    assert rows == expected["rows"]


# ── 3 · cli events.jsonl parser ─────────────────────────────────────────────

def test_cli_metrics_parser_cumulative_float_credits_survive(tmp_path):
    p = tmp_path / "session-state" / "sessA" / "events.jsonl"
    _cli_events(p, ("2026-08-13T00:00:00Z", {
        "modelMetrics": {"gpt-4": {"usage": {"inputTokens": 500, "outputTokens": 200,
                                             "cacheReadTokens": 50}}},
        "totalPremiumRequests": 0.33, "totalNanoAiu": 330000000}))
    rows = transcript.parse_copilot_cli_metrics(p, session="sessA")
    # Two rows per shutdown since METRICS-PRIMARY P0a: the verbatim cumulative `cli` row
    # this test owns, plus its point-in-time `cli-delta` twin (pinned in
    # tests/test_metrics_rescan.py). The verbatim contract below is unchanged.
    assert [r["source"] for r in rows] == ["cli", "cli-delta"]
    r = next(x for x in rows if x["source"] == "cli")
    assert r["surface"] == "cli" and r["session"] == "sessA"
    assert r["credits"] == 0.33          # never floored by int()
    assert r["nano_aiu"] == 330000000.0
    assert r["model_totals"] == [{"model": "gpt-4", "tokens_in": 500,
                                  "cached_in": 50, "tokens_out": 200}]
    assert r["tokens_in"] == 500 and r["tokens_out"] == 200 and r["cached_in"] == 50


def test_cli_metrics_no_request_or_call_grain():
    """CLI rows describe the whole session's cumulative state — `request`/`call` stay
    unstamped (omitted), which is exactly what makes every shutdown of a session
    collapse to the SAME `ledger.copilot_metrics` key."""
    row = schema.make_copilot_metric(source="cli", session="s1", surface="cli",
                                     credits=0.1, metric_id="cm_x")
    assert "request" not in row and "call" not in row


# ── 4 · sidecar / debuglog / otel (gated stores) ────────────────────────────

def test_sidecar_metrics_parser_records_real_routed_model(tmp_path):
    p = tmp_path / "agentHostUsage" / "sanitized-session-1.jsonl"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps(_sidecar_line()) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_sidecar_metrics(p, session=p.stem)
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "sidecar" and r["session"] == "sanitized-session-1"
    assert r["call"] == "t1" and r["model"] == "gpt-4o"
    assert r["tokens_in"] == 200 and r["tokens_out"] == 80 and r["cached_in"] == 40
    assert r["nano_aiu"] == 250000000.0
    assert "credits" not in r  # never derived from nano_aiu at capture


def test_debuglog_metrics_parser_whitelist_excludes_prompt_body(tmp_path):
    p = (tmp_path / "workspaceStorage" / "hash1" / "GitHub.copilot-chat" / "debug-logs"
        / "sessionXYZ" / "main.jsonl")
    p.parent.mkdir(parents=True)
    lines = [json.dumps(_debuglog_line()),
            json.dumps({"type": "some_other_span", "spanId": "span2"})]  # non-llm_request, skipped
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_debuglog_metrics(p)
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "debuglog" and r["session"] == "sessionXYZ"
    assert r["call"] == "span1" and r["model"] == "gpt-4o"
    assert r["tokens_in"] == 300 and r["tokens_out"] == 120 and r["ttft_ms"] == 450
    assert "cached_in" not in r  # the store's own serializer omits it
    assert PROMPT_BODY_SENTINEL not in json.dumps(r)


def test_otel_metrics_parser_reads_denormalized_columns_only(tmp_path):
    db = tmp_path / "globalStorage" / "github.copilot-chat" / "agent-traces.db"
    _otel_db(db, with_attributes_sentinel=True)
    rows = transcript.parse_copilot_otel_metrics(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["source"] == "otel" and r["session"] == "conv1" and r["call"] == "span1"
    assert r["model"] == "gpt-4o-2026"  # COALESCE(response_model, request_model)
    assert r["tokens_in"] == 400 and r["tokens_out"] == 150 and r["cached_in"] == 60
    assert r["ttft_ms"] == 220
    assert PROMPT_BODY_SENTINEL not in json.dumps(r)  # span_attributes never queried


def test_otel_metrics_parser_fails_open_on_schema_surprise(tmp_path):
    db = tmp_path / "agent-traces.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE spans (nothing_like_the_real_schema TEXT)")
    con.commit()
    con.close()
    assert transcript.parse_copilot_otel_metrics(db) == []


def test_otel_metrics_parser_missing_db_returns_empty(tmp_path):
    assert transcript.parse_copilot_otel_metrics(tmp_path / "nope.db") == []


# ── 5 · ledger reader: collapse + since ─────────────────────────────────────

def test_copilot_metrics_collapse_keeps_latest_largest_row(proj):
    root = proj
    old = schema.make_copilot_metric(source="chat", session="s1", surface="vscode",
                                     request="r1", tokens_in=10, tokens_out=5,
                                     ts="2026-08-01T00:00:00Z", metric_id="cm_old")
    new = schema.make_copilot_metric(source="chat", session="s1", surface="vscode",
                                     request="r1", tokens_in=50, tokens_out=20,
                                     ts="2026-08-01T00:05:00Z", metric_id="cm_new")
    ledger.append_row(root, "copilot", old)
    ledger.append_row(root, "copilot", new)
    collapsed = ledger.copilot_metrics(root)
    assert len(collapsed) == 1
    assert collapsed[0]["id"] == "cm_new"


def test_copilot_metrics_distinct_call_grain_keys_never_collapse(proj):
    root = proj
    a = schema.make_copilot_metric(source="sidecar", session="s1", call="turnA",
                                   tokens_in=10, ts="2026-08-01T00:00:00Z",
                                   metric_id="cm_a")
    b = schema.make_copilot_metric(source="sidecar", session="s1", call="turnB",
                                   tokens_in=20, ts="2026-08-01T00:01:00Z",
                                   metric_id="cm_b")
    ledger.append_row(root, "copilot", a)
    ledger.append_row(root, "copilot", b)
    assert {r["id"] for r in ledger.copilot_metrics(root)} == {"cm_a", "cm_b"}


def test_copilot_metrics_since_skips_old_months(proj):
    """``since`` is a relative window (`7d`/`24h`/`2w`), like every other view's --since —
    not an absolute date."""
    root = proj
    ledger.append_row(root, "copilot", schema.make_copilot_metric(
        source="cli", session="old", credits=0.1, ts="2020-01-01T00:00:00Z",
        metric_id="cm_old_month"))
    ledger.append_row(root, "copilot", schema.make_copilot_metric(
        source="cli", session="new", credits=0.2,  # ts omitted → defaults to now()
        metric_id="cm_new_month"))
    all_rows = ledger.copilot_metrics(root)
    assert {r["id"] for r in all_rows} == {"cm_old_month", "cm_new_month"}
    recent = ledger.copilot_metrics(root, since="30d")
    assert {r["id"] for r in recent} == {"cm_new_month"}
    # raw feeds the import seen-set and must never apply a window
    assert {r["id"] for r in ledger.copilot_metrics_raw(root)} == {"cm_old_month", "cm_new_month"}


# ── 6 · _is_chat_session_file dispatch for the new roots ───────────────────

@pytest.mark.parametrize("dirname", ["chatSessions", "emptyWindowChatSessions",
                                     "transferredChatSessions"])
def test_is_chat_session_file_true_for_all_three_roots(tmp_path, dirname):
    f = tmp_path / dirname / "sess.jsonl"
    assert importcmd._is_chat_session_file(f) is True


def test_is_chat_session_file_false_for_cli_events(tmp_path):
    f = tmp_path / "session-state" / "sessA" / "events.jsonl"
    assert importcmd._is_chat_session_file(f) is False


@pytest.mark.parametrize("dirname", ["emptyWindowChatSessions", "transferredChatSessions"])
def test_parse_copilot_any_dispatches_new_roots_to_vscode_parser(tmp_path, dirname):
    """Without `_is_chat_session_file`, a file here mis-dispatches to the CLI events
    parser (parent dir name != "chatSessions" literally) and never records a call."""
    p = tmp_path / dirname / "sess.jsonl"
    _vscode_store(p, "sess", _req("req1"))
    rows = importcmd._parse_copilot_any(p)
    assert len(rows) == 1 and rows[0]["surface"] == "vscode"
    metric_rows = importcmd._parse_copilot_metrics_any(p)
    assert len(metric_rows) == 1 and metric_rows[0]["source"] == "chat"


# ── 7 · ingest: idempotency + no-rescan reuse ───────────────────────────────

def test_ingest_copilot_metrics_idempotent(proj):
    root = proj
    p = root / "chatSessions" / "sess.jsonl"
    _vscode_store(p, "sess", _req("req1", copilotCredits=0.5))
    parse = lambda f: transcript.parse_copilot_vscode_metrics(f, session="sess")
    first = importcmd._ingest_copilot_metrics(root, [p], parse, src=p.parent)
    second = importcmd._ingest_copilot_metrics(root, [p], parse, src=p.parent)
    assert first == 1
    assert second == 0
    assert len(ledger.copilot_metrics_raw(root)) == 1


def test_ingest_copilot_metrics_never_touches_call_seen_set(proj):
    """Metrics rows must never enter the call-id `seen` set or a call view — they are
    not calls (handoff §4.5, §6)."""
    root = proj
    p = root / "chatSessions" / "sess.jsonl"
    _vscode_store(p, "sess", _req("req1"))
    parse = lambda f: transcript.parse_copilot_vscode_metrics(f, session="sess")
    importcmd._ingest_copilot_metrics(root, [p], parse, src=p.parent)
    assert ledger.calls(root) == []


# ── 8 · full import-flow idempotency (real sweep, two runs) ────────────────

def test_import_copilot_full_sweep_idempotent(proj, monkeypatch):
    """`cage import --agent copilot` twice on a scratch ledger — second run appends 0
    copilot-metrics rows (handoff §6 acceptance)."""
    from cage import clicmds
    from srcseed import mkcage
    home = proj / "copilot-home"
    vscode_home = proj / "vscode-user"
    monkeypatch.setenv("COPILOT_HOME", str(home))
    monkeypatch.setenv("CAGE_VSCODE_USER", str(vscode_home))
    mkcage(proj)
    monkeypatch.chdir(proj)
    _vscode_store(vscode_home / "workspaceStorage" / "hash1" / "chatSessions" / "sess.jsonl",
                 "sess", _req("req1", copilotCredits=0.44))
    _cli_events(home / "session-state" / "sessA" / "events.jsonl",
               ("2026-08-13T00:00:00Z", {
                   "modelMetrics": {"gpt-4": {"usage": {"inputTokens": 100,
                                                        "outputTokens": 40}}},
                   "totalPremiumRequests": 0.1}))

    args = type("A", (), {"agent": "copilot", "since": None, "path": None,
                          "project": None, "ledger": None, "quiet": True,
                          "no_import": False, "rescan_graphify": False})()
    assert clicmds.cmd_import(args) == 0
    first = ledger.copilot_metrics_raw(proj)
    assert len(first) == 3  # one chat row, one verbatim cli row, one cli-delta twin
    assert clicmds.cmd_import(args) == 0
    second = ledger.copilot_metrics_raw(proj)
    assert len(second) == 3  # idempotent — zero new rows


# ── 9 · counts-never-content on the written shard bytes ─────────────────────

def test_written_shard_bytes_never_carry_the_prompt_body(proj):
    """The content-whitelist assertion, on the SERIALIZED bytes — not just the parsed
    row — for both content-adjacent stores (debuglog, otel)."""
    root = proj
    dbg = root / "debug-logs" / "sessionXYZ" / "main.jsonl"
    dbg.parent.mkdir(parents=True)
    dbg.write_text(json.dumps(_debuglog_line()) + "\n", encoding="utf-8")
    otel_db = root / "agent-traces.db"
    _otel_db(otel_db, with_attributes_sentinel=True)

    importcmd._ingest_copilot_metrics(
        root, [dbg], transcript.parse_copilot_debuglog_metrics, src=dbg.parent)
    importcmd._ingest_copilot_metrics(
        root, [otel_db], transcript.parse_copilot_otel_metrics, src=otel_db)

    shard_bytes = b"".join(sh.read_bytes() for sh in paths.Footprint(root).copilot_shards())
    assert PROMPT_BODY_SENTINEL.encode("utf-8") not in shard_bytes
    assert len(ledger.copilot_metrics_raw(root)) == 2


# ── 10 · byte-identity: no derived view moves ───────────────────────────────

def _render(argv: list[str], capsys) -> str:
    assert cli.main([*argv, "--no-import"]) == 0
    return capsys.readouterr().out


def test_report_and_chats_byte_identical_with_copilot_tree_present_or_absent(proj, capsys):
    from cage import demo
    demo.seed(proj)
    # A populated copilot/ tree, present:
    ledger.append_row(proj, "copilot", schema.make_copilot_metric(
        source="chat", session="demo-sess", surface="vscode", request="r1",
        tokens_in=999, tokens_out=999, credits=9.99, ts="2026-08-13T00:00:00Z",
        metric_id="cm_present"))
    before = {" ".join(v): _render(v, capsys)
             for v in (["insights", "chats"], ["insights", "chats"])}
    for sh in paths.Footprint(proj).copilot_shards():
        sh.unlink()
    after = {" ".join(v): _render(v, capsys)
            for v in (["insights", "chats"], ["insights", "chats"])}
    assert before == after


# ── 11 · doctor advisory ─────────────────────────────────────────────────────

def test_doctor_copilot_metrics_advisory_renders_per_source(proj):
    root = proj
    ledger.append_row(root, "copilot", schema.make_copilot_metric(
        source="chat", session="s1", tokens_in=10, ts="2026-08-13T00:00:00Z",
        metric_id="cm_1"))
    level, detail = doctorcmd._copilot_metrics(root)
    assert level == "ok"
    assert "chat: 1 row(s)" in detail
    for tag, gate in doctorcmd._COPILOT_METRIC_GATES.items():
        assert f"{tag}: none yet" in detail and gate in detail


def test_doctor_copilot_metrics_never_fails_or_warns_on_empty_ledger(proj):
    level, _detail = doctorcmd._copilot_metrics(proj)
    assert level == "ok"


def test_doctor_run_includes_copilot_metrics_check(proj):
    from cage import initcmd
    initcmd.run(proj)
    names = {c["name"] for c in doctorcmd.run(proj)["checks"]}
    assert "copilot-metrics" in names
