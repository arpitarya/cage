"""Transcript metering: Claude Code + Codex parsing, idempotent recording."""
from __future__ import annotations

import json

from cage import hooks, ledger, transcript


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


def test_append_new_is_idempotent(tmp_path):
    tp = tmp_path / "s.jsonl"
    tp.write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")
    rows = transcript.parse_calls(tp)
    assert hooks.append_new(tmp_path, rows) == 1
    assert hooks.append_new(tmp_path, transcript.parse_calls(tp)) == 0  # same uuid → skipped
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
    assert hooks.append_new(tmp_path, r1) == 1
    assert hooks.append_new(tmp_path, r2) == 0  # re-import dedupes (no random id)
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


def test_parse_codex_finds_nested_usage(tmp_path):
    tp = tmp_path / "rollout-x.jsonl"
    tp.write_text(json.dumps({"type": "event", "payload": {
        "usage": {"input_tokens": 200, "output_tokens": 80}}}) + "\n", encoding="utf-8")
    rows = transcript.parse_codex_calls(tp, session="abc")
    assert len(rows) == 1
    assert rows[0]["tokens_in"] == 200 and rows[0]["tokens_out"] == 80
    assert rows[0]["agent"] == "codex" and rows[0]["provider"] == "openai"


def _codex_token_count_line(inp, out, ts=""):
    rec = {"type": "event_msg", "payload": {"type": "token_count", "info": {
        "last_token_usage": {"input_tokens": inp, "output_tokens": out}}}}
    if ts:
        rec["timestamp"] = ts
    return json.dumps(rec)


def test_codex_ids_never_collide_across_sessions(tmp_path):
    # Every rollout stem starts with "rollout-", so a session *prefix* in the id was one
    # shared namespace: identical line indexes in two sessions produced identical ids and
    # append_new silently dropped the second session's calls (41% of real rows in the
    # 2026-07 manual validation). Ids must differ across sessions at the same line index.
    a = tmp_path / "rollout-2026-06-01T00-00-00-aaa.jsonl"
    b = tmp_path / "rollout-2026-06-02T00-00-00-bbb.jsonl"
    line = _codex_token_count_line(100, 10)
    a.write_text(line + "\n", encoding="utf-8")
    b.write_text(line + "\n", encoding="utf-8")
    ida = transcript.parse_codex_calls(a)[0]["id"]
    idb = transcript.parse_codex_calls(b)[0]["id"]
    assert ida != idb
    # …and stay deterministic per (session, line) so re-imports still dedupe.
    assert transcript.parse_codex_calls(a)[0]["id"] == ida


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


def test_codex_ts_comes_from_the_event_not_import_time(tmp_path):
    # A May rollout imported in July must not land in the July shard: the row ts is the
    # token_count event's own timestamp. A line with no timestamp still gets a
    # write-time stamp (fail-open, never an empty ts).
    tp = tmp_path / "rollout-2026-05-01T00-00-00-ccc.jsonl"
    tp.write_text(_codex_token_count_line(100, 10, ts="2026-05-01T00:00:05Z") + "\n"
                  + _codex_token_count_line(50, 5) + "\n", encoding="utf-8")
    rows = transcript.parse_codex_calls(tp)
    assert rows[0]["ts"] == "2026-05-01T00:00:05Z"
    assert rows[1]["ts"]  # no event timestamp → write-time stamp, still present


def test_session_end_hook_records(tmp_path, monkeypatch):
    import io
    (tmp_path / ".cage").mkdir()  # a project root — a no-project cwd captures globally now
    tp = tmp_path / "t.jsonl"
    tp.write_text(_claude_line("u9", 300, 100) + "\n", encoding="utf-8")
    payload = json.dumps({"transcript_path": str(tp), "cwd": str(tmp_path),
                          "session_id": "sess"})
    monkeypatch.setattr("sys.stdin", io.StringIO(payload))
    assert hooks.session_end() == 0
    (call,) = ledger.calls(tmp_path)
    assert call["tokens_in"] == 300


def test_stop_hook_records_per_turn_and_is_idempotent(tmp_path, monkeypatch):
    # Stop is the real-time path: it captures the turn the moment it ends, and
    # re-firing on the next turn never double-records the earlier one (uuid dedup).
    import io
    # isolate other-agent homes so the Stop sweep finds no real machine logs
    for env in ("CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR", "CLAUDE_CONFIG_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"empty-{env.lower()}"))
    (tmp_path / ".cage").mkdir()  # a project root — a no-project cwd captures globally now
    tp = tmp_path / "live.jsonl"

    def fire():
        payload = json.dumps({"transcript_path": str(tp), "cwd": str(tmp_path),
                              "session_id": "sess"})
        monkeypatch.setattr("sys.stdin", io.StringIO(payload))
        assert hooks.stop() == 0

    tp.write_text(_claude_line("t1", 100, 40) + "\n", encoding="utf-8")
    fire()
    assert len(ledger.calls(tmp_path)) == 1          # turn 1 recorded immediately
    tp.write_text(_claude_line("t1", 100, 40) + "\n"
                  + _claude_line("t2", 200, 60) + "\n", encoding="utf-8")
    fire()
    calls = ledger.calls(tmp_path)
    assert len(calls) == 2                            # only the new turn added
    assert {c["tokens_in"] for c in calls} == {100, 200}
