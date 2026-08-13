"""CLAUDE-METRICS — the `.cage/ledger/claude/` per-chat metrics ledger.

Capture-only: a new row shape (`schema.make_claude_metric`) fed by the ONE Claude
Code transcript store, correctly folded at capture (THE DEDUP LAW + subagent-to-parent
joining), collapsed last-write-wins at read (`ledger.claude_metrics`), and read by NO
derived view in this build. What this file pins, following
`docs/claude-metrics-ledger.handoff.md` §9:

1. The substrate — omit-at-zero, no-credits-field, `model_totals` field-level whitelist.
2. THE DEDUP LAW: duplicate assistant rows per `(requestId, message.id)` fold to one,
   last occurrence wins; `raw_rows` vs `requests` is the inflation evidence.
3. Subagent transcripts join their PARENT chat via the row's own `sessionId` and split
   into `sidechain_tokens_in/out`.
4. The session-fileset regroup: a sweep that only saw a subagent file still re-reads
   the whole session, so the emitted row is never a partial total.
5. `parse_calls`/`_usage_to_row` (the calls path) are BYTE-IDENTICAL — this build
   dodges CLAUDE-DEDUP/CLAUDE-SUBAGENT-KEY, it does not fix them.
6. Re-import is idempotent; a grown chat appends a fresh row and the collapse read
   resolves to the latest.
7. No derived view moves by one byte whether the `claude/` tree exists or not.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import cli, doctorcmd, importcmd, ledger, schema, transcript

PROMPT_BODY_SENTINEL = "please refactor the auth module to use JWT tokens instead"


# ── fixture builders ─────────────────────────────────────────────────────────

def _usage_row(*, uuid: str, request_id: str = "req1", message_id: str = "msg1",
               session: str = "sess1", ts: str = "2026-08-13T00:00:00Z",
               cwd: str = "/home/user/proj", model: str = "claude-x",
               is_sidechain: bool = False, output_tokens: int = 100,
               input_tokens: int = 5, cache_read: int = 0, cache_write: int = 0,
               ttl_5m: int = 0, ttl_1h: int = 0, thinking: int = 0,
               web_search: int = 0, web_fetch: int = 0, extra_content=None) -> dict:
    usage = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    if cache_read:
        usage["cache_read_input_tokens"] = cache_read
    if cache_write:
        usage["cache_creation_input_tokens"] = cache_write
    if ttl_5m or ttl_1h:
        usage["cache_creation"] = {"ephemeral_5m_input_tokens": ttl_5m,
                                   "ephemeral_1h_input_tokens": ttl_1h}
    if thinking:
        usage["output_tokens_details"] = {"thinking_tokens": thinking}
    if web_search or web_fetch:
        usage["server_tool_use"] = {"web_search_requests": web_search,
                                    "web_fetch_requests": web_fetch}
    rec = {"type": "assistant", "uuid": uuid, "requestId": request_id,
          "sessionId": session, "timestamp": ts, "cwd": cwd,
          "isSidechain": is_sidechain,
          "message": {"id": message_id, "model": model, "usage": usage,
                      "content": extra_content or [PROMPT_BODY_SENTINEL]}}
    return rec


def _write_jsonl(path: Path, *recs: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")


def _session_with_subagent(tmp_path: Path, *, session: str = "sess1"):
    """A realistic `<slug>/<sessionId>.jsonl` + `<slug>/<sessionId>/subagents/
    agent-x1.jsonl` layout (research doc's live-probed shape)."""
    slug_dir = tmp_path / "claude-projects" / "-home-user-proj"
    main = slug_dir / f"{session}.jsonl"
    _write_jsonl(main, _usage_row(uuid="u1", request_id="reqA", message_id="msgA",
                                  session=session, output_tokens=50))
    sub = slug_dir / session / "subagents" / "agent-x1.jsonl"
    _write_jsonl(sub, _usage_row(uuid="u2", request_id="reqB", message_id="msgB",
                                 session=session, model="claude-haiku",
                                 is_sidechain=True, output_tokens=51975,
                                 input_tokens=1))
    return main, sub


# ── 1 · substrate ────────────────────────────────────────────────────────────

def test_make_claude_metric_omit_at_zero():
    row = schema.make_claude_metric(session="s1", metric_id="clm_x")
    for k in ("surface", "tokens_in", "tokens_out", "cached_in", "cache_write_in",
              "ttl_5m", "ttl_1h", "thinking", "web_search", "web_fetch", "requests",
              "raw_rows", "sidechain_tokens_in", "sidechain_tokens_out",
              "model_totals", "project"):
        assert k not in row


def test_make_claude_metric_no_credits_field_ever():
    """No credit unit exists for Claude Code anywhere on disk (research doc's firm
    no) — unlike `make_call`/`make_copilot_metric`, there is no None-sentinel here
    because there is nothing a sentinel could ever distinguish."""
    row = schema.make_claude_metric(session="s1", metric_id="clm_x", tokens_in=10)
    assert "credits" not in row
    assert "credits" not in schema.CLAUDE_METRIC_FIELDS


def test_make_claude_metric_fixed_agent_and_source():
    row = schema.make_claude_metric(session="s1", metric_id="clm_x")
    assert row["agent"] == "claude-code"
    assert row["source"] == "transcript"


def test_make_claude_metric_model_totals_whitelist():
    row = schema.make_claude_metric(
        session="s1", metric_id="clm_mt",
        model_totals=[{"model": "claude-x", "tokens_in": 10, "tokens_out": 5,
                       "cached_in": 2, "cache_write_in": 1,
                       "userRequest": PROMPT_BODY_SENTINEL, "extraneous": "drop-me"}])
    assert row["model_totals"] == [{"model": "claude-x", "tokens_in": 10,
                                    "tokens_out": 5, "cached_in": 2,
                                    "cache_write_in": 1}]
    assert PROMPT_BODY_SENTINEL not in json.dumps(row)


def test_make_claude_metric_default_id_is_clm_prefixed():
    row = schema.make_claude_metric(session="s1")
    assert row["id"].startswith("clm_")


# ── 2 · THE DEDUP LAW ────────────────────────────────────────────────────────

def test_dedup_law_folds_duplicate_rows_last_wins(tmp_path):
    """Three duplicate assistant rows for the SAME (requestId, message.id) — distinct
    uuid, differing output_tokens — fold to ONE surviving request. `raw_rows=3`,
    `requests=1`, and the LAST row's output_tokens wins (ccusage #888: latest ==
    final)."""
    main = tmp_path / "sess1.jsonl"
    _write_jsonl(main,
                _usage_row(uuid="u1", request_id="req1", message_id="msg1",
                          output_tokens=100),
                _usage_row(uuid="u2", request_id="req1", message_id="msg1",
                          output_tokens=150),
                _usage_row(uuid="u3", request_id="req1", message_id="msg1",
                          output_tokens=550))
    rows = transcript.parse_claude_chat_metrics([main])
    assert len(rows) == 1
    r = rows[0]
    assert r["raw_rows"] == 3
    assert r["requests"] == 1
    assert r["tokens_out"] == 550


def test_dedup_law_legacy_rows_without_requestid_key_on_uuid(tmp_path):
    """Rows carrying neither `requestId` nor `message.id` can't be folded — each keys
    on its own `uuid`, so no fold is possible (or needed): every legacy row survives
    as its own request."""
    main = tmp_path / "sess1.jsonl"
    _write_jsonl(main,
                _usage_row(uuid="u1", request_id="", message_id="", output_tokens=10),
                _usage_row(uuid="u2", request_id="", message_id="", output_tokens=20))
    rows = transcript.parse_claude_chat_metrics([main])
    assert len(rows) == 1
    r = rows[0]
    assert r["raw_rows"] == 2
    assert r["requests"] == 2
    assert r["tokens_out"] == 30


def test_dedup_law_counts_never_content():
    """The parser reads envelope + `message.usage` only — `message.content` (which
    carries the prompt body sentinel in every fixture row here) never reaches a
    written row or the serialized bytes."""
    row = _usage_row(uuid="u1")
    assert PROMPT_BODY_SENTINEL in json.dumps(row)  # sanity: the fixture DOES carry it
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    main = tmp / "sess1.jsonl"
    _write_jsonl(main, row)
    rows = transcript.parse_claude_chat_metrics([main])
    assert PROMPT_BODY_SENTINEL not in json.dumps(rows)


# ── 3 · subagent join ────────────────────────────────────────────────────────

def test_subagent_rows_join_parent_chat_via_own_sessionid(tmp_path):
    main, sub = _session_with_subagent(tmp_path)
    rows = transcript.parse_claude_chat_metrics([main, sub])
    assert len(rows) == 1
    r = rows[0]
    assert r["session"] == "sess1"
    assert r["requests"] == 2
    assert r["sidechain_tokens_out"] == 51975
    assert r["sidechain_tokens_in"] == 1
    assert r["tokens_out"] == 50 + 51975


def test_non_sidechain_rows_never_add_to_sidechain_totals(tmp_path):
    main = tmp_path / "sess1.jsonl"
    _write_jsonl(main, _usage_row(uuid="u1", is_sidechain=False, output_tokens=42))
    rows = transcript.parse_claude_chat_metrics([main])
    assert "sidechain_tokens_in" not in rows[0]
    assert "sidechain_tokens_out" not in rows[0]


def test_resume_drift_emits_more_than_one_chat_key(tmp_path):
    """A fileset whose rows disagree with the intended session id (resume drift) is
    correct behavior, not a bug: >1 chat key emitted."""
    main = tmp_path / "sess1.jsonl"
    _write_jsonl(main,
                _usage_row(uuid="u1", session="sess1", output_tokens=10),
                _usage_row(uuid="u2", session="sess2", output_tokens=20))
    rows = transcript.parse_claude_chat_metrics([main])
    assert {r["session"] for r in rows} == {"sess1", "sess2"}


# ── 4 · session-fileset regroup ──────────────────────────────────────────────

def test_fileset_regroup_subagent_only_change_pulls_in_main(tmp_path):
    main, sub = _session_with_subagent(tmp_path)
    filesets = importcmd._claude_session_filesets([sub])  # ONLY the subagent changed
    assert len(filesets) == 1
    assert filesets[0] == [main, sub]


def test_fileset_regroup_main_only_change_pulls_in_subagents(tmp_path):
    main, sub = _session_with_subagent(tmp_path)
    filesets = importcmd._claude_session_filesets([main])  # ONLY main changed
    assert len(filesets) == 1
    assert filesets[0] == [main, sub]


def test_fileset_regroup_orphan_subagent_keeps_fileset_without_missing_main(tmp_path):
    """A main file that doesn't exist (subagent orphan) keeps the fileset without it
    — the fold still keys on the row's own `sessionId`."""
    slug_dir = tmp_path / "claude-projects" / "-home-user-proj"
    sub = slug_dir / "sessX" / "subagents" / "agent-y1.jsonl"
    _write_jsonl(sub, _usage_row(uuid="u1", session="sessX", is_sidechain=True,
                                output_tokens=99))
    filesets = importcmd._claude_session_filesets([sub])
    assert len(filesets) == 1
    assert filesets[0] == [sub]
    rows = transcript.parse_claude_chat_metrics(filesets[0], session_hint="sessX")
    assert len(rows) == 1 and rows[0]["session"] == "sessX"


def test_fileset_regroup_distinct_sessions_never_merge(tmp_path):
    slug_dir = tmp_path / "claude-projects" / "-home-user-proj"
    m1 = slug_dir / "sessA.jsonl"
    m2 = slug_dir / "sessB.jsonl"
    _write_jsonl(m1, _usage_row(uuid="u1", session="sessA"))
    _write_jsonl(m2, _usage_row(uuid="u2", session="sessB"))
    filesets = importcmd._claude_session_filesets([m1, m2])
    assert sorted(fs[0].stem for fs in filesets) == ["sessA", "sessB"]


# ── 5 · calls-path byte-identity pin (do-not-touch) ─────────────────────────

def test_calls_path_byte_identical_on_dedup_fixture(tmp_path):
    """CLAUDE-DEDUP/CLAUDE-SUBAGENT-KEY are calls-path defects this build must NOT
    fix — `parse_calls` output on the same fixture stays byte-identical (still
    inflated, still uuid-keyed): pins the do-not-touch rule."""
    main = tmp_path / "sess1.jsonl"
    recs = [_usage_row(uuid="u1", request_id="req1", message_id="msg1",
                       output_tokens=100),
           _usage_row(uuid="u2", request_id="req1", message_id="msg1",
                     output_tokens=150)]
    _write_jsonl(main, *recs)
    call_rows = transcript.parse_calls(main, session="sess1")
    # Still uuid-keyed, still one call row per duplicate — the pre-existing (buggy)
    # behavior, unchanged by this build.
    assert len(call_rows) == 2
    assert {r["tokens_out"] for r in call_rows} == {100, 150}


def test_subagent_rows_still_land_under_filename_stem_in_calls_path(tmp_path):
    """CLAUDE-SUBAGENT-KEY stays open: `parse_calls` still keys a subagent file's rows
    by the FILENAME stem, never the row's own `sessionId` — unchanged by this build."""
    _, sub = _session_with_subagent(tmp_path)
    call_rows = transcript.parse_calls(sub, session=sub.stem)
    assert call_rows[0]["session"] == "agent-x1"  # NOT "sess1" — the known defect


# ── 6 · ledger reader: collapse + since ─────────────────────────────────────

def test_claude_metrics_collapse_keeps_latest_largest_row(proj):
    root = proj
    old = schema.make_claude_metric(session="s1", tokens_in=10, tokens_out=5,
                                    requests=1, ts="2026-08-01T00:00:00Z",
                                    metric_id="clm_old")
    new = schema.make_claude_metric(session="s1", tokens_in=50, tokens_out=20,
                                    requests=2, ts="2026-08-01T00:05:00Z",
                                    metric_id="clm_new")
    ledger.append_row(root, "claude", old)
    ledger.append_row(root, "claude", new)
    collapsed = ledger.claude_metrics(root)
    assert len(collapsed) == 1
    assert collapsed[0]["id"] == "clm_new"


def test_claude_metrics_never_sums_growth_rows(proj):
    root = proj
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="s1", tokens_in=10, requests=1, ts="2026-08-01T00:00:00Z",
        metric_id="clm_a"))
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="s1", tokens_in=30, requests=2, ts="2026-08-01T00:05:00Z",
        metric_id="clm_b"))
    collapsed = ledger.claude_metrics(root)
    assert len(collapsed) == 1
    assert collapsed[0]["tokens_in"] == 30  # NOT 40 — never summed


def test_claude_metrics_since_skips_old_months(proj):
    root = proj
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="old", tokens_in=5, ts="2020-01-01T00:00:00Z",
        metric_id="clm_old_month"))
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="new", tokens_in=5,  # ts omitted → defaults to now()
        metric_id="clm_new_month"))
    all_rows = ledger.claude_metrics(root)
    assert {r["id"] for r in all_rows} == {"clm_old_month", "clm_new_month"}
    recent = ledger.claude_metrics(root, since="30d")
    assert {r["id"] for r in recent} == {"clm_new_month"}
    # raw feeds the import seen-set and must never apply a window
    assert {r["id"] for r in ledger.claude_metrics_raw(root)} == {"clm_old_month", "clm_new_month"}


def test_metric_id_folds_values_not_timestamp():
    """Growing a chat's totals mints a NEW id; an unchanged re-parse of the SAME rows
    (even at a different wall-clock ts) mints the SAME id — the fold key excludes
    `ts`."""
    import tempfile
    tmp = Path(tempfile.mkdtemp())
    main = tmp / "sess1.jsonl"
    _write_jsonl(main, _usage_row(uuid="u1", output_tokens=100))
    first = transcript.parse_claude_chat_metrics([main])[0]
    second = transcript.parse_claude_chat_metrics([main])[0]
    assert first["id"] == second["id"]

    _write_jsonl(main, _usage_row(uuid="u1", output_tokens=100),
                _usage_row(uuid="u2", request_id="req2", message_id="msg2",
                          output_tokens=200))
    grown = transcript.parse_claude_chat_metrics([main])[0]
    assert grown["id"] != first["id"]


# ── 7 · ingest: idempotency + no-rescan reuse ───────────────────────────────

def test_ingest_claude_metrics_idempotent(proj):
    root = proj
    main, sub = _session_with_subagent(root)
    first = importcmd._ingest_claude_metrics(root, [sub])  # only subagent "changed"
    second = importcmd._ingest_claude_metrics(root, [sub])
    assert first == 1
    assert second == 0
    assert len(ledger.claude_metrics_raw(root)) == 1


def test_ingest_claude_metrics_never_touches_call_seen_set(proj):
    root = proj
    main, _sub = _session_with_subagent(root)
    importcmd._ingest_claude_metrics(root, [main])
    assert ledger.calls(root) == []


def test_ingest_claude_metrics_grown_chat_appends_fresh_row(proj):
    root = proj
    main = root / "sess1.jsonl"
    _write_jsonl(main, _usage_row(uuid="u1", output_tokens=100))
    importcmd._ingest_claude_metrics(root, [main])
    assert len(ledger.claude_metrics_raw(root)) == 1
    _write_jsonl(main, _usage_row(uuid="u1", output_tokens=100),
                _usage_row(uuid="u2", request_id="req2", message_id="msg2",
                          output_tokens=50))
    importcmd._ingest_claude_metrics(root, [main])
    assert len(ledger.claude_metrics_raw(root)) == 2
    collapsed = ledger.claude_metrics(root)
    assert len(collapsed) == 1
    assert collapsed[0]["tokens_out"] == 150


# ── 8 · full import-flow idempotency (real sweep, two runs) ────────────────

def test_import_claude_full_sweep_idempotent(proj, monkeypatch):
    """`cage import --agent claude` twice on a scratch ledger — second run appends 0
    claude-metrics rows (handoff §6 acceptance), and the FULL fileset regroup fires
    even though only the subagent file is "new" on disk from the cursor's view."""
    from cage import clicmds
    from srcseed import mkcage
    claude_home = proj / "claude-home"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_home))
    mkcage(proj)
    monkeypatch.chdir(proj)
    slug_dir = claude_home / "projects" / "-home-user-proj"
    _write_jsonl(slug_dir / "sess1.jsonl",
                _usage_row(uuid="u1", request_id="reqA", message_id="msgA",
                          session="sess1", output_tokens=50))
    _write_jsonl(slug_dir / "sess1" / "subagents" / "agent-x1.jsonl",
                _usage_row(uuid="u2", request_id="reqB", message_id="msgB",
                          session="sess1", is_sidechain=True, output_tokens=51975,
                          model="claude-haiku"))

    args = type("A", (), {"agent": "claude", "since": None, "path": None,
                          "project": None, "ledger": None, "quiet": True,
                          "no_import": False, "rescan_graphify": False})()
    assert clicmds.cmd_import(args) == 0
    first = ledger.claude_metrics_raw(proj)
    assert len(first) == 1
    assert first[0]["requests"] == 2  # main + subagent joined
    assert clicmds.cmd_import(args) == 0
    second = ledger.claude_metrics_raw(proj)
    assert len(second) == 1  # idempotent — zero new rows


# ── 9 · counts-never-content on the written shard bytes ─────────────────────

def test_written_shard_bytes_never_carry_the_prompt_body(proj):
    root = proj
    main, sub = _session_with_subagent(root)
    importcmd._ingest_claude_metrics(root, [main, sub])
    from cage import paths
    shard_bytes = b"".join(sh.read_bytes() for sh in paths.Footprint(root).claude_shards())
    assert PROMPT_BODY_SENTINEL.encode("utf-8") not in shard_bytes
    assert len(ledger.claude_metrics_raw(root)) == 1


# ── 10 · byte-identity: no derived view moves ───────────────────────────────

def _render(argv: list[str], capsys) -> str:
    assert cli.main([*argv, "--no-import"]) == 0
    return capsys.readouterr().out


def test_report_and_chats_byte_identical_with_claude_tree_present_or_absent(proj, capsys):
    from cage import demo, paths
    demo.seed(proj)
    ledger.append_row(proj, "claude", schema.make_claude_metric(
        session="demo-sess", tokens_in=999, tokens_out=999, requests=5,
        ts="2026-08-13T00:00:00Z", metric_id="clm_present"))
    before = {" ".join(v): _render(v, capsys)
             for v in (["report", "--by", "agent"], ["insights", "chats"])}
    for sh in paths.Footprint(proj).claude_shards():
        sh.unlink()
    after = {" ".join(v): _render(v, capsys)
            for v in (["report", "--by", "agent"], ["insights", "chats"])}
    assert before == after


# ── 11 · doctor advisory ─────────────────────────────────────────────────────

def test_doctor_claude_metrics_advisory_renders_counts(proj):
    root = proj
    ledger.append_row(root, "claude", schema.make_claude_metric(
        session="s1", tokens_in=10, requests=1, ts="2026-08-13T00:00:00Z",
        metric_id="clm_1"))
    level, detail = doctorcmd._claude_metrics(root)
    assert level == "ok"
    assert "1 raw row(s), 1 chat(s)" in detail


def test_doctor_claude_metrics_never_fails_or_warns_on_empty_ledger(proj):
    level, _detail = doctorcmd._claude_metrics(proj)
    assert level == "ok"


def test_doctor_run_includes_claude_metrics_check(proj):
    from cage import initcmd
    initcmd.run(proj)
    names = {c["name"] for c in doctorcmd.run(proj)["checks"]}
    assert "claude-metrics" in names
