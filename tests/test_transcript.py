"""Transcript metering: Claude Code + Copilot parsing, idempotent recording."""
from __future__ import annotations

import json

from cage import ledger, transcript


def _claude_line(uuid: str, tin: int, tout: int, cached: int = 0) -> str:
    return json.dumps({"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout,
                                             "cache_read_input_tokens": cached}}})


def test_parse_claude_transcript(tmp_path):
    tp = tmp_path / "session.jsonl"
    tp.write_text(_claude_line("u1", 100, 50, cached=20) + "\n"
                  + json.dumps({"type": "user", "message": {}}) + "\n"
                  + _claude_line("u2", 200, 60) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp, session="s")
    assert len(rows) == 2
    assert rows[0]["tokens_in"] == 120 and rows[0]["cached_in"] == 20
    assert rows[0]["agent"] == "claude-code" and rows[0]["tokens_out"] == 50


def _claude_line_cache_make(uuid, tin, tout, cache_read, cache_make):
    return json.dumps({"type": "assistant", "uuid": uuid, "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout,
                                             "cache_read_input_tokens": cache_read,
                                             "cache_creation_input_tokens": cache_make}}})


def test_claude_splits_cache_write_without_changing_tokens_in(tmp_path):
    # Phase 1 (plan §2.1): cache_creation is split into `cache_write_in`, but tokens_in
    # semantics are unchanged (still inp + cache_read + cache_make). surface stays "".
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line_cache_make("u1", 100, 50, cache_read=20, cache_make=30) + "\n",
                  encoding="utf-8")
    (row,) = transcript.parse_calls(tp, session="s")
    assert row["tokens_in"] == 150 and row["cached_in"] == 20  # unchanged semantics
    assert row["cache_write_in"] == 30                          # split out, additive
    assert "surface" not in row                                 # claude: shared store, omitted


def test_no_cache_make_omits_cache_write_in(tmp_path):
    # Additive-optional: a turn with no cache creation is byte-identical to the legacy row.
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    (row,) = transcript.parse_calls(tp, session="s")
    assert "cache_write_in" not in row and "surface" not in row and "premium" not in row


def test_copilot_cli_surface_and_premium():
    # copilot CLI rows carry surface="cli"; `totalPremiumRequests` lands on the first row.
    import tempfile
    from pathlib import Path as _P
    d = _P(tempfile.mkdtemp())
    ev = d / "sess" / "events.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text(json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T10:00:00Z",
                              "data": {"totalPremiumRequests": 3, "modelMetrics": {
                                  "gpt-5": {"usage": {"inputTokens": 100, "outputTokens": 5}},
                                  "claude-sonnet-5": {"usage": {"inputTokens": 200, "outputTokens": 7}}}}})
                  + "\n", encoding="utf-8")
    rows = sorted(transcript.parse_copilot_calls(ev, session="sess"), key=lambda r: r["id"])
    assert all(r["surface"] == "cli" for r in rows)
    assert sum(r.get("premium", 0) for r in rows) == 3  # session total, counted once


def _copilot_shutdown(cum_in: int, cum_out: int, cum_cached: int = 0, premium: int = 0,
                      ts: str = "2026-06-14T10:00:00Z", model: str = "claude-haiku-4.5") -> str:
    """One `session.shutdown` line whose modelMetrics are CUMULATIVE (Copilot's real shape)."""
    return json.dumps({"type": "session.shutdown", "timestamp": ts,
                       "data": {"totalPremiumRequests": premium, "modelMetrics": {
                           model: {"usage": {"inputTokens": cum_in, "outputTokens": cum_out,
                                             "cacheReadTokens": cum_cached}}}}})


def test_copilot_two_shutdowns_sum_to_cumulative(tmp_path):
    # (a) A resumed session with two cumulative shutdowns yields delta rows that SUM to
    # the last cumulative — no undercount. Real V3 numbers (session 8073abba).
    ev = tmp_path / "8073abba-9855-414b" / "events.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text(_copilot_shutdown(70071, 643, 51260, premium=1) + "\n"
                  + _copilot_shutdown(107581, 830, 86521, premium=2) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev)
    assert len(rows) == 2
    assert sum(r["tokens_in"] for r in rows) == 107581   # not 70071 (the pre-fix undercount)
    assert sum(r["tokens_out"] for r in rows) == 830
    assert sum(r["cached_in"] for r in rows) == 86521
    ids = {r["id"] for r in rows}
    sid = "8073abba-9855-414b".replace("-", "")[:12]
    assert f"c_cop{sid}000" in ids                       # ordinal 0 keeps the legacy id
    assert f"c_cop{sid}000s001" in ids                   # ordinal 1 is a distinct delta row


def test_copilot_reimport_adds_zero(tmp_path):
    # (b) Re-importing the same grown file adds nothing — deterministic ids dedupe.
    ev = tmp_path / "sess" / "events.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text(_copilot_shutdown(70071, 643, 51260) + "\n"
                  + _copilot_shutdown(107581, 830, 86521) + "\n", encoding="utf-8")
    assert ledger.append_new(tmp_path, transcript.parse_copilot_calls(ev)) == 2
    assert ledger.append_new(tmp_path, transcript.parse_copilot_calls(ev)) == 0
    assert sum(c["tokens_in"] for c in ledger.calls(tmp_path)) == 107581


def test_copilot_legacy_session_self_heals(tmp_path):
    # (c) THE SELF-HEAL CASE. A ledger already holds the ordinal-0 row written by the
    # pre-fix parser (byte-identical: a 1-shutdown file's row == the legacy row). Growing
    # the file to two shutdowns and re-importing must dedupe ordinal 0 and append ONLY the
    # ordinal-1 delta — reaching the exact cumulative with NO double count.
    d = tmp_path / "sess"
    d.mkdir()
    ev = d / "events.jsonl"
    ev.write_text(_copilot_shutdown(70071, 643, 51260) + "\n", encoding="utf-8")  # legacy state
    assert ledger.append_new(tmp_path, transcript.parse_copilot_calls(ev)) == 1
    assert sum(c["tokens_in"] for c in ledger.calls(tmp_path)) == 70071
    # session resumes; a second cumulative shutdown is appended to the same file
    ev.write_text(_copilot_shutdown(70071, 643, 51260) + "\n"
                  + _copilot_shutdown(107581, 830, 86521) + "\n", encoding="utf-8")
    assert ledger.append_new(tmp_path, transcript.parse_copilot_calls(ev)) == 1  # only the delta
    assert sum(c["tokens_in"] for c in ledger.calls(tmp_path)) == 107581          # exact, no 70071×2
    assert ledger.append_new(tmp_path, transcript.parse_copilot_calls(ev)) == 0  # idempotent


def test_copilot_premium_delta_not_multi_counted(tmp_path):
    # (d) `totalPremiumRequests` is cumulative too — the per-shutdown delta is stamped, so
    # the recorded premium sums to the last cumulative, never premium_1 + premium_2.
    ev = tmp_path / "sess" / "events.jsonl"
    ev.parent.mkdir(parents=True)
    ev.write_text(_copilot_shutdown(70071, 643, premium=2) + "\n"
                  + _copilot_shutdown(107581, 830, premium=5) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_calls(ev)
    assert sum(r.get("premium", 0) for r in rows) == 5   # last cumulative, not 2 + 5 = 7


def _kiro_cli_db(tmp_path, conversations):
    """Build a minimal kiro-cli SQLite store. `conversations` = list of
    (key/cwd, conversation_id, value_dict, created_at, updated_at)."""
    import sqlite3
    db = tmp_path / "data.sqlite3"
    con = sqlite3.connect(db)
    con.execute("CREATE TABLE conversations_v2 (key TEXT, conversation_id TEXT, "
                "value TEXT, created_at INTEGER, updated_at INTEGER)")
    con.execute("CREATE TABLE auth_kv (k TEXT, v TEXT)")  # the sensitive sibling table
    con.execute("INSERT INTO auth_kv VALUES ('token', 'SECRET-AUTH-DO-NOT-LEAK')")
    for key, cid, val, ca, ua in conversations:
        con.execute("INSERT INTO conversations_v2 VALUES (?,?,?,?,?)",
                    (key, cid, json.dumps(val), ca, ua))
    con.commit()
    con.close()
    return db


def _kiro_conv(turns: int, credits: list, model="claude-haiku-4.5", secret="SECRET-PROMPT"):
    """A conversation value dict with `turns` history entries carrying embedded prompt/
    response text (the content the parser must never read) plus the usage metadata."""
    return {
        "conversation_id": "ignored",
        "model_info": {"model_id": model, "model_name": model},
        "user_turn_metadata": {"usage_info": [{"value": c, "unit": "credit"} for c in credits]},
        "history": [{"user": {"content": secret + f"-USER-{i}"},
                     "assistant": {"content": secret + f"-ASSISTANT-{i}"},
                     "request_metadata": {"request_id": f"req{i}", "context_usage_percentage": 1.5 + i}}
                    for i in range(turns)],
        "next_message": secret + "-NEXT", "transcript": secret + "-TRANSCRIPT",
    }


def test_kiro_cli_credits_are_not_call_rows(tmp_path):
    # Kiro CLI records no tokens — the parser yields a distinct CREDITS row, never a
    # call row with tokens_in=0 (which would poison every average).
    db = _kiro_cli_db(tmp_path, [("/w", "c1-2-3-4", _kiro_conv(2, [0.06, 0.10]), 1000, 2000)])
    rows = transcript.parse_kiro_cli_credits(db)
    assert len(rows) == 1
    r = rows[0]
    assert r["unit"] == "credits" and "tokens_in" not in r and "tokens_out" not in r
    assert abs(r["credits"] - 0.16) < 1e-9 and r["turns"] == 2
    assert r["method"] == "estimated"          # a proxy, never measured
    assert r["model"] == "claude-haiku-4.5" and r["surface"] == "cli"
    assert r["session"] == "c1-2-3-4"


def test_kiro_cli_parser_never_leaks_content(tmp_path):
    # THE COUNTS-NEVER-CONTENT GUARD (§3.3). Content and metadata share the row; assert
    # no prompt/response/auth text can reach any credits row.
    db = _kiro_cli_db(tmp_path, [("/w", "cA", _kiro_conv(3, [0.05], secret="TOPSECRET"), 1, 9)])
    rows = transcript.parse_kiro_cli_credits(db)
    blob = json.dumps(rows)
    assert "TOPSECRET" not in blob            # no prompt/response body
    assert "SECRET-AUTH-DO-NOT-LEAK" not in blob  # auth_kv never read
    assert "TRANSCRIPT" not in blob and "NEXT" not in blob


def test_kiro_cli_parser_is_read_only(tmp_path):
    # The store is opened read-only — the DB bytes are unchanged after parsing.
    db = _kiro_cli_db(tmp_path, [("/w", "cA", _kiro_conv(2, [0.05]), 1, 9)])
    before = db.read_bytes()
    transcript.parse_kiro_cli_credits(db)
    assert db.read_bytes() == before


def test_kiro_cli_credits_resume_no_double_count(tmp_path):
    from cage import ledger, schema
    # A conversation captured at 2 turns, then resumed to 4 turns. Append-only: both rows
    # land, but `ledger.credits` keeps the latest per session — never summed.
    (tmp_path / "a").mkdir(exist_ok=True)
    (tmp_path / "b").mkdir(exist_ok=True)
    db2 = _kiro_cli_db(tmp_path / "a", [("/w", "cX", _kiro_conv(2, [0.06]), 1, 2)])
    r2 = transcript.parse_kiro_cli_credits(db2)
    for row in r2:
        ledger.append_row(tmp_path, "credits", row)
    # re-import unchanged → same id, no new distinct row
    assert {x["id"] for x in transcript.parse_kiro_cli_credits(db2)} == {x["id"] for x in r2}
    db4 = _kiro_cli_db(tmp_path / "b", [("/w", "cX", _kiro_conv(4, [0.06, 0.11]), 1, 5)])
    for row in transcript.parse_kiro_cli_credits(db4):
        ledger.append_row(tmp_path, "credits", row)
    latest = ledger.credits(tmp_path)
    assert len(latest) == 1                       # one row per session
    assert abs(latest[0]["credits"] - 0.17) < 1e-9  # the 4-turn total, not 0.06 + 0.17
    assert latest[0]["turns"] == 4


def test_kiro_cli_parser_missing_db_is_empty(tmp_path):
    assert transcript.parse_kiro_cli_credits(tmp_path / "nope.sqlite3") == []


def test_kiro_surface_is_ide(tmp_path):
    log = tmp_path / "tokens_generated.jsonl"
    log.write_text(json.dumps({"model": "agent", "provider": "kiro",
                               "promptTokens": 50, "generatedTokens": 0}) + "\n", encoding="utf-8")
    (row,) = transcript.parse_kiro_calls(log)
    assert row["surface"] == "ide"


def test_append_new_is_idempotent(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp)
    assert ledger.append_new(tmp_path, rows) == 1
    assert ledger.append_new(tmp_path, transcript.parse_calls(tp)) == 0  # same uuid → skipped
    assert len(ledger.calls(tmp_path)) == 1


def _claude_line_no_uuid(tin: int, tout: int, cached: int = 0) -> str:
    """A usage-bearing assistant turn with *no* `uuid` — empirically never observed in
    real Claude transcripts (0/29,714), so this exercises the defensive deterministic-id
    path that pre-change minted a random id and re-imported as a duplicate."""
    return json.dumps({"type": "assistant", "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout,
                                             "cache_read_input_tokens": cached}}})


def test_uuid_present_rows_byte_identical(tmp_path):
    # The deterministic-id change must not perturb the uuid-present contract: a turn
    # with a uuid renders exactly as before (`c_` + first 15 hex of the dashless uuid).
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("abc-def-0123456789", 100, 50, cached=20) + "\n",
                  encoding="utf-8")
    (row,) = transcript.parse_calls(tp, session="s")
    assert row["id"] == "c_" + "abcdef0123456789".replace("-", "")[:15]


def test_no_uuid_id_is_deterministic_and_dedupes(tmp_path):
    # Same uuid-less turn parsed twice ⇒ identical id ⇒ append_new dedupes on re-import.
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line_no_uuid(100, 50, cached=20) + "\n", encoding="utf-8")
    r1 = transcript.parse_calls(tp, session="s")
    r2 = transcript.parse_calls(tp, session="s")
    assert r1[0]["id"] == r2[0]["id"]          # stable across re-parse
    assert r1[0]["id"].startswith("c_") and len(r1[0]["id"]) == 17  # c_ + 15 hex
    assert ledger.append_new(tmp_path, r1) == 1
    assert ledger.append_new(tmp_path, r2) == 0  # re-import dedupes (no random id)
    assert len(ledger.calls(tmp_path)) == 1


def test_no_uuid_id_varies_with_content(tmp_path):
    # Distinct turns get distinct ids (the composite key spans tokens + ts), so two
    # genuinely-different uuid-less turns are not collapsed into one.
    a = transcript.parse_calls(_w(tmp_path / "a.jsonl",
                                   _claude_line_no_uuid(100, 50)), session="s")
    b = transcript.parse_calls(_w(tmp_path / "b.jsonl",
                                   _claude_line_no_uuid(200, 50)), session="s")
    assert a[0]["id"] != b[0]["id"]


def _w(path, text):
    path.write_text(text + "\n", encoding="utf-8")
    return path


def _chat_session_request(rid, prompt, completion, ext="github.copilot-chat", ts=1783447814720):
    return {"requestId": rid, "timestamp": ts, "modelId": "copilot/auto",
            "agent": {"extensionId": {"value": ext}},
            "promptTokens": prompt, "completionTokens": completion,
            "result": {"metadata": {"promptTokens": prompt, "outputTokens": completion}}}


def test_copilot_vscode_chat_sessions_parse_and_rewrite_merge(tmp_path):
    # The VS Code chat-session store rewrites the requests array as the session grows:
    # requests merge last-write-wins by requestId, so a grown file re-parses to one row
    # per request (deterministic requestId-derived ids → re-imports dedupe).
    tp = tmp_path / "abc.jsonl"
    lines = [
        json.dumps({"kind": 0, "v": {"version": 3, "sessionId": "sess-1"}}),
        json.dumps({"kind": 1, "k": ["customTitle"], "v": "content — never read"}),
        json.dumps({"kind": 2, "k": ["requests"], "v": [_chat_session_request("r1", 100, 5)]}),
        json.dumps({"kind": 2, "k": ["requests"],
                    "v": [_chat_session_request("r1", 100, 9),        # rewrite of r1
                          _chat_session_request("r2", 200, 7),
                          _chat_session_request("r3", 300, 1, ext="some.other-chat")]}),
    ]
    tp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = transcript.parse_copilot_vscode_calls(tp)
    assert len(rows) == 2                                  # r3 is another provider's
    by_in = {r["tokens_in"]: r for r in rows}
    assert by_in[100]["tokens_out"] == 9                   # last write won
    assert by_in[200]["tokens_out"] == 7
    assert all(r["session"] == "sess-1" and r["agent"] == "copilot" for r in rows)
    assert rows[0]["ts"] == "2026-07-07T18:10:14.720Z"     # epoch ms → ISO Z
    assert transcript.parse_copilot_vscode_calls(tp)[0]["id"] == rows[0]["id"]  # deterministic


# NB: the SessionEnd / Stop hook entry points were removed with the hook machinery;
# capture is pull-based now. The equivalent "parse a live transcript → record calls,
# idempotently" behavior is covered end-to-end through `importcmd.run` in
# tests/test_import_unified.py (the universal sweep), and the id-dedupe backstop by
# `test_append_new_is_idempotent` above.
