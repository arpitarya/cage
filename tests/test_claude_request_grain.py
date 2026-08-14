"""METRICS-PRIMARY P1 — the claude **request-grain** metric row.

One `source="request"` row per folded `(requestId, message.id)`, emitted from the SAME
fold the chat grain uses (`transcript._fold_claude_records`). It exists because
`ledger.spend` needs a point-in-time row carrying a single model; the chat-grain row is a
whole-life total holding a `model_totals` list and structurally cannot be one.

**This is where CLAUDE-DEDUP and CLAUDE-SUBAGENT-KEY are closed** — in the new ledger,
not in `parse_calls`, which stays untouched so the pre-cutover history it wrote remains
exactly as recorded. Both defects are asserted here against the same fixtures that
demonstrate them in `parse_calls`, so the *difference* is the evidence.

What this file pins:

1. One row per API response, not per assistant row — the ~2× drop, measured against
   `parse_calls` on the same transcript rather than asserted in the abstract.
2. Subagent requests join their parent chat by the record's own `sessionId`.
3. Every row carries a single `model` — the thing the money path needs.
4. The two grains are projections of ONE fold and never disagree.
5. Counts-never-content survives the new grain.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from cage import ledger, schema, transcript


PROMPT_BODY = "please refactor the auth module to use JWT tokens instead"


def _assistant(uuid, *, request, msg_id, session, model="claude-opus-4",
               tin=100, tout=20, cache_read=0, cache_write=0, sidechain=False,
               ts="2026-08-14T00:00:00Z", cwd="/tmp/demo"):
    """One assistant transcript row. A real API response writes SEVERAL of these — one per
    content block — each with a distinct uuid, the same requestId + message.id, and a FULL
    copy of `usage`. That duplication is CLAUDE-DEDUP."""
    return {"type": "assistant", "uuid": uuid, "requestId": request,
            "sessionId": session, "timestamp": ts, "cwd": cwd,
            "isSidechain": sidechain,
            "message": {"id": msg_id, "model": model,
                        "content": [{"type": "text", "text": PROMPT_BODY}],
                        "usage": {"input_tokens": tin, "output_tokens": tout,
                                  "cache_read_input_tokens": cache_read,
                                  "cache_creation_input_tokens": cache_write}}}


def _write(path: Path, *recs):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(r) for r in recs) + "\n", encoding="utf-8")
    return path


def _req_rows(rows):
    return [r for r in rows if r.get("source") == "request"]


# ── 1 · CLAUDE-DEDUP is closed, and the drop is measured ─────────────────────

def test_one_row_per_api_response_not_per_assistant_row(tmp_path):
    """Three assistant rows, one API response ⇒ exactly one request-grain row."""
    main = _write(tmp_path / "sess1.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess1"),
                  _assistant("u2", request="req_A", msg_id="msg_A", session="sess1"),
                  _assistant("u3", request="req_A", msg_id="msg_A", session="sess1"))
    rows = _req_rows(transcript.parse_claude_chat_metrics([main]))
    assert len(rows) == 1
    assert rows[0]["tokens_in"] == 100 and rows[0]["tokens_out"] == 20


def test_the_token_drop_against_parse_calls_is_asserted_not_incidental(tmp_path):
    """The handoff's explicit requirement: assert the ~2× drop rather than let it happen
    quietly. `parse_calls` keys on `uuid` and counts all three duplicates; the request
    grain counts the one response they describe."""
    main = _write(tmp_path / "sess2.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess2"),
                  _assistant("u2", request="req_A", msg_id="msg_A", session="sess2"),
                  _assistant("u3", request="req_A", msg_id="msg_A", session="sess2"))
    legacy = transcript.parse_calls(main, session="sess2")
    legacy_out = sum(c.get("tokens_out", 0) for c in legacy)
    grain = _req_rows(transcript.parse_claude_chat_metrics([main]))
    grain_out = sum(r.get("tokens_out", 0) for r in grain)
    assert legacy_out == 3 * grain_out, (
        f"the inflation must be visible and exact: parse_calls={legacy_out}, "
        f"request grain={grain_out}")


def test_distinct_requests_stay_distinct(tmp_path):
    main = _write(tmp_path / "sess3.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess3"),
                  _assistant("u2", request="req_B", msg_id="msg_B", session="sess3"))
    assert len(_req_rows(transcript.parse_claude_chat_metrics([main]))) == 2


def test_a_row_with_no_requestid_falls_back_to_a_stable_grain_key(tmp_path):
    """Legacy rows carry no `requestId`. The fold falls back to message.id, then uuid —
    and the emitted row must never end up with an EMPTY grain key while the fold
    considered it distinct, or two distinct requests would collapse at read time."""
    main = _write(tmp_path / "sess4.jsonl",
                  _assistant("u1", request="", msg_id="msg_A", session="sess4"),
                  _assistant("u2", request="", msg_id="msg_B", session="sess4"))
    rows = _req_rows(transcript.parse_claude_chat_metrics([main]))
    assert len(rows) == 2
    assert all(r.get("request") for r in rows)
    assert len({r["request"] for r in rows}) == 2


# ── 2 · CLAUDE-SUBAGENT-KEY is closed ────────────────────────────────────────

def test_subagent_requests_join_the_parent_chat_by_their_own_sessionid(tmp_path):
    """A subagent transcript is session-keyed by FILENAME in `parse_calls`, so its spend
    lands in a phantom chat. Here every row reads its own `sessionId`."""
    main = _write(tmp_path / "parent.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="parent"))
    sub = _write(tmp_path / "parent" / "subagents" / "agent-xyz.jsonl",
                 _assistant("u2", request="req_B", msg_id="msg_B", session="parent",
                            sidechain=True))
    rows = _req_rows(transcript.parse_claude_chat_metrics([main, sub]))
    assert len(rows) == 2
    assert {r["session"] for r in rows} == {"parent"}, "no phantom chat"
    side = [r for r in rows if r.get("sidechain_tokens_in")]
    assert len(side) == 1, "the subagent's own row is still marked as sidechain"


# ── 3 · every row carries one model — what the money path needs ──────────────

def test_every_request_row_carries_a_single_model(tmp_path):
    main = _write(tmp_path / "sess5.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess5",
                             model="claude-opus-4"),
                  _assistant("u2", request="req_B", msg_id="msg_B", session="sess5",
                             model="claude-haiku-4.5"))
    rows = _req_rows(transcript.parse_claude_chat_metrics([main]))
    assert {r["model"] for r in rows} == {"claude-opus-4", "claude-haiku-4.5"}


def test_the_chat_grain_still_has_no_single_model(tmp_path):
    """Stated as a contrast, because it is the whole reason P1 exists: a chat-grain row
    holds a model_totals LIST and cannot price as one call."""
    main = _write(tmp_path / "sess6.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess6"))
    chat = [r for r in transcript.parse_claude_chat_metrics([main])
            if r["source"] == "transcript"][0]
    assert "model" not in chat and "model_totals" in chat


# ── 4 · one fold, two projections — they can never disagree ──────────────────

def test_the_two_grains_agree_on_totals(tmp_path):
    """The reason `_fold_claude_records` was extracted rather than duplicated: the request
    rows must sum to exactly what the chat row reports for the same traffic."""
    main = _write(tmp_path / "sess7.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess7",
                             tin=100, tout=20, cache_read=5, cache_write=7),
                  _assistant("u1b", request="req_A", msg_id="msg_A", session="sess7",
                             tin=100, tout=20, cache_read=5, cache_write=7),
                  _assistant("u2", request="req_B", msg_id="msg_B", session="sess7",
                             tin=300, tout=40, cache_read=9, cache_write=1))
    rows = transcript.parse_claude_chat_metrics([main])
    chat = [r for r in rows if r["source"] == "transcript"][0]
    reqs = _req_rows(rows)
    for field in ("tokens_in", "tokens_out", "cached_in", "cache_write_in"):
        assert sum(r.get(field, 0) for r in reqs) == chat.get(field, 0), field
    assert len(reqs) == chat["requests"]


def test_there_is_exactly_one_fold_in_the_module():
    """A second fold would let the grains drift. `_fold_claude_records` is the only place
    the dedup key is built."""
    import inspect
    src = inspect.getsource(transcript)
    assert src.count("folded[fold_key] = rec") == 1


# ── 5 · the read side resolves the new grain ─────────────────────────────────

def test_claude_request_metrics_collapses_per_session_and_request(proj):
    """A re-capture of the same request must not stack; a grown one wins."""
    for tokens in (100, 250):
        ledger.append_row(proj, "claude", schema.make_claude_metric(
            source="request", session="s1", request="req_A", model="claude-opus-4",
            tokens_in=tokens, ts="2026-08-14T00:00:00Z",
            metric_id=f"clm_{tokens}"))
    kept = ledger.claude_request_metrics(proj)
    assert len(kept) == 1 and kept[0]["tokens_in"] == 250


def test_the_chat_reader_and_the_request_reader_are_separate(proj):
    """`claude_metrics` collapses per SESSION — correct for chat grain, catastrophic for
    request grain, where it would keep one request per chat and discard the rest."""
    for req in ("req_A", "req_B"):
        ledger.append_row(proj, "claude", schema.make_claude_metric(
            source="request", session="s1", request=req, tokens_in=100,
            ts="2026-08-14T00:00:00Z", metric_id=f"clm_{req}"))
    assert len(ledger.claude_request_metrics(proj)) == 2
    assert ledger.claude_metrics(proj) == [], "request rows are not chat rows"


# ── 6 · the substrate stays closed and counts-only ───────────────────────────

def test_source_is_a_closed_enum():
    with pytest.raises(ValueError):
        schema.make_claude_metric(session="s1", source="bogus")


def test_request_rows_never_carry_the_prompt_body(tmp_path, proj):
    main = _write(tmp_path / "sess8.jsonl",
                  _assistant("u1", request="req_A", msg_id="msg_A", session="sess8"))
    for r in _req_rows(transcript.parse_claude_chat_metrics([main])):
        ledger.append_row(proj, "claude", r)
    from cage import paths
    blob = b"".join(sh.read_bytes() for sh in paths.Footprint(proj).claude_shards())
    assert PROMPT_BODY.encode("utf-8") not in blob
