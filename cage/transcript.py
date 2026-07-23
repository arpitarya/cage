"""Parse a Claude Code transcript JSONL into call rows (plan §5, §9.5).

Claude Code can't be metered with the library adapter — you can't edit its request
code. But it *writes* a transcript whose every assistant turn already records
`message.usage`. Reading that file is metering **off the request path**: $0,
deterministic, and it works for the API and subscription paths alike (no proxy).

Each turn's `uuid` becomes the call id, so re-parsing the same transcript on a
later SessionEnd never double-records (idempotent — see hooks.session_end).

**`gap_ms` availability per agent (plan §4.10 — the derived human-attention axis).**
Where a log carries real per-turn timestamps for both the human turn and the
preceding assistant turn, the parser stamps an additive optional `gap_ms` on the
call row (the wall-clock between the previous assistant turn's end and the human
user turn that led to this call). Where it doesn't, the field is **absent — never
fabricated** (an absent `gap_ms` is the legacy row contract):

- **claude** (`parse_calls`) — YES. Every transcript record carries `timestamp`;
  human user turns are distinguishable from tool-result / meta records.
- **copilot** (`parse_copilot_calls` / `parse_copilot_vscode_calls`) — NO. The CLI
  log aggregates usage once at `session.shutdown`; the VS Code store stamps one
  epoch-ms per *request* with no assistant-end timestamp to gap against. No field.
- **kiro** (`parse_kiro_calls`) — NO. `tokens_generated.jsonl` carries no
  timestamps at all. No field.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

from cage import schema


def _composite_id(agent: str, session: str, model: str, tokens_in: int,
                  tokens_out: int, cached_in: int, ts: str | None) -> str:
    """A *deterministic* call id for a usage row that carries no stable source id
    (a Claude turn with no `uuid`). Folded into `call_id` so `make_call`/`CALL_FIELDS`
    are unchanged; same `(agent, session, model, tokens_in, tokens_out, cached_in, ts)`
    ⇒ same id, so re-parsing the same transcript dedupes in `hooks.append_new` instead
    of minting a fresh random id each run. Same `c_`+15-char shape as the uuid path.

    Empirically defensive: no usage-bearing Claude turn observed lacks a `uuid`; this
    closes the one path where `make_call` would otherwise fall back to a random id."""
    key = "|".join(str(x) for x in (agent, session, model, tokens_in, tokens_out,
                                    cached_in, ts or ""))
    return "c_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:15]


def _usage_to_row(msg: dict, session: str, uuid: str, ts: str | None,
                  project: str = "", gap_ms: int | None = None) -> dict | None:
    usage = msg.get("usage") or {}
    out = int(usage.get("output_tokens", 0) or 0)
    inp = int(usage.get("input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_make = int(usage.get("cache_creation_input_tokens", 0) or 0)
    if not (out or inp or cache_read or cache_make):
        return None
    tokens_in = inp + cache_read + cache_make
    model = msg.get("model", "") or ""
    # uuid-present rows render byte-identical to the pre-change contract; only the
    # no-uuid path changes (random id → deterministic composite id), so re-imports
    # of a uuid-less turn no longer double-record. `gap_ms` never enters either id.
    call_id = ("c_" + uuid.replace("-", "")[:15] if uuid
               else _composite_id("claude-code", session, model, tokens_in, out,
                                  cache_read, ts))
    return schema.make_call(
        route="chat", provider="anthropic", model=model,
        tokens_in=tokens_in, tokens_out=out, cached_in=cache_read,
        session=session, agent="claude-code", ts=ts, project=project,
        gap_ms=gap_ms, call_id=call_id)


def _parse_ts(ts) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError, TypeError):
        return None


def _human_user_turn(rec: dict) -> bool:
    """True for a transcript record that is a *human* user turn — the attention
    signal behind `gap_ms`. Tool results also arrive as `type: "user"` records
    (their content is a list of `tool_result` blocks), and meta/sidechain records
    are machine turns; counting any of those as human attention would fabricate
    minutes, so all are excluded. Content is inspected for its block *types* only —
    counts-never-content holds (nothing readable is retained)."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return False
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result"
                       for b in content)
    return True


def parse_calls(transcript_path: Path, session: str = "") -> list[dict]:
    """One call row per assistant turn that carries usage. Tolerant of bad lines.

    `gap_ms` (plan §4.10): the first call row after each human user turn carries the
    wall-clock gap between the previous assistant turn's timestamp and that user
    turn's timestamp — the passive human-attention signal. Stamped only when both
    timestamps exist and parse and the gap is non-negative (an out-of-order clock is
    dropped, never clamped into fake attention); every other row omits the field."""
    if not transcript_path.exists():
        return []
    session = session or transcript_path.stem
    rows = []
    prev_asst_ts: _dt.datetime | None = None   # end of the last assistant turn seen
    pending_gap_ms: int | None = None          # computed at the human turn, spent on the next call
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if _human_user_turn(rec):
            user_ts = _parse_ts(rec.get("timestamp"))
            if user_ts is not None and prev_asst_ts is not None:
                gap = int((user_ts - prev_asst_ts).total_seconds() * 1000)
                if gap >= 0:
                    pending_gap_ms = gap
            continue
        if rec.get("type") != "assistant":
            continue
        # `project` is the working-dir basename Claude stamps on each record (`cwd`) —
        # a derived attribution axis (plan §3.7). Basename only (counts-never-content
        # PII guard); absent on records without a cwd ⇒ "" (legacy contract).
        cwd = rec.get("cwd") or ""
        project = Path(cwd).name if cwd else ""
        row = _usage_to_row(rec.get("message") or {}, session,
                            rec.get("uuid", ""), rec.get("timestamp"), project=project,
                            gap_ms=pending_gap_ms)
        prev_asst_ts = _parse_ts(rec.get("timestamp")) or prev_asst_ts
        if row:
            pending_gap_ms = None  # spent on this call — one gap, one row
            rows.append(row)
    return rows


_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def parse_provenance(transcript_path: Path, session: str = "") -> list[dict]:
    """File paths an Edit/Write/MultiEdit/NotebookEdit `tool_use` block touched,
    walking the same transcript `parse_calls` reads. Lower trust than the live
    `PostToolUse` hook (no in-process line counts) — the caller (`hooks.session_end`)
    tags these `method="transcript"` and resolves them against `HEAD` at session end,
    since the transcript alone can't say which commit an edit landed in.

    v2: archiving the transcript itself (beyond reading it once, here) is out of
    scope — cage never copies or retains transcript content.
    """
    if not transcript_path.exists():
        return []
    session = session or transcript_path.stem
    files: list[str] = []
    for line in transcript_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") != "assistant":
            continue
        for block in (rec.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            if block.get("name") not in _EDIT_TOOLS:
                continue
            inp = block.get("input") or {}
            fp = inp.get("file_path") or inp.get("notebook_path")
            if fp:
                files.append(fp)
    return [{"session": session, "file": f} for f in dict.fromkeys(files)]  # de-dup, order kept


# Copilot CLI persists a per-session usage log at
# ~/.copilot/session-state/<id>/events.jsonl; the `session.shutdown` event carries a
# `modelMetrics` map keyed by model. Each value nests tokens under a `usage` object —
# verified against Copilot CLI 1.0.65:
#   "claude-haiku-4.5": {"usage": {"inputTokens": 15553, "outputTokens": 92,
#                                  "cacheReadTokens": 10015, "cacheWriteTokens": 5529}}
# `inputTokens` is the TOTAL input (uncached + cache read + cache write), so it is NOT
# summed with the cache figures — cacheReadTokens is recorded as the cached_in slice.
# Keys matched by shape (snake + camel) for robustness across versions.
_COPILOT_IN_KEYS = ("inputTokens", "input_tokens", "promptTokens", "prompt_tokens",
                    "inputTokenCount", "promptTokenCount")
_COPILOT_OUT_KEYS = ("outputTokens", "output_tokens", "completionTokens",
                     "completion_tokens", "outputTokenCount", "completionTokenCount")
_COPILOT_CACHE_KEYS = ("cacheReadTokens", "cache_read_tokens", "cacheReadInputTokens",
                       "cache_read_input_tokens", "cachedTokens", "cached_tokens")


def _first_int(d: dict, keys: tuple[str, ...]) -> int:
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)):
            return int(v)
    return 0


def _copilot_provider(model: str) -> str:
    m = (model or "").lower()
    if m.startswith(("gpt", "o1", "o3", "o4", "text-", "davinci")):
        return "openai"
    if "claude" in m:
        return "anthropic"
    if "gemini" in m:
        return "google"
    return ""


def parse_copilot_calls(events_path: Path, session: str = "") -> list[dict]:
    """One call row per model in a Copilot CLI session's `session.shutdown.modelMetrics`
    (provider inferred from the model name). Aggregate per session, not per turn —
    Copilot only finalizes usage at shutdown; `assistant.turn_end` carries no tokens.
    Idempotent: the call id is derived from the session id, so re-importing the same
    session (e.g. on every sessionEnd hook) never double-records. Fail-open per line."""
    if not events_path.exists():
        return []
    session = session or events_path.parent.name  # session-state/<id>/events.jsonl
    rows: list[dict] = []
    for line in events_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") != "session.shutdown":
            continue
        data = rec.get("data") or {}
        metrics = data.get("modelMetrics")
        ts = rec.get("timestamp")
        if not isinstance(metrics, dict):
            continue
        for i, (model, m) in enumerate(metrics.items()):
            if not isinstance(m, dict):
                continue
            u = m.get("usage") if isinstance(m.get("usage"), dict) else m  # tokens nest here
            inp = _first_int(u, _COPILOT_IN_KEYS)   # already includes cache read+write
            out = _first_int(u, _COPILOT_OUT_KEYS)
            cached = _first_int(u, _COPILOT_CACHE_KEYS)
            if not (inp or out):
                continue
            sid = session.replace("-", "")
            rows.append(schema.make_call(
                route="chat", provider=_copilot_provider(model), model=model,
                tokens_in=inp, tokens_out=out, cached_in=cached,
                session=session, agent="copilot", ts=ts,
                call_id=f"c_cop{sid[:12]}{i:03d}"))
    return rows


def _copilot_chat_extension(req: dict) -> bool:
    """True when a chat-session request was answered by the Copilot Chat extension —
    other chat providers sharing VS Code's store must never be attributed to copilot."""
    ext = (req.get("agent") or {}).get("extensionId")
    if isinstance(ext, dict):
        ext = ext.get("_lower") or ext.get("value") or ""
    return "copilot" in str(ext).lower()


def _epoch_ms_iso(ms) -> str | None:
    try:
        dt = _dt.datetime.fromtimestamp(int(ms) / 1000.0, tz=_dt.timezone.utc)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def parse_copilot_vscode_calls(chat_session_path: Path, session: str = "") -> list[dict]:
    """Meter the Copilot VS Code *extension* from VS Code's own chat-session store
    (`<vscode-user>/workspaceStorage/<hash>/chatSessions/<session>.jsonl`).

    The extension's `GitHub.copilot-chat/transcripts/` event stream never carries a
    usage event (no `session.shutdown`, even after quitting VS Code — pinned against
    copilot-chat 0.54.0 / VS Code 1.126, 2026-07); the per-request token counts live
    here instead: `kind:2, k:["requests"]` lines whose `v` items carry `requestId`,
    `timestamp` (epoch ms), `modelId`, `promptTokens`, `completionTokens`. The store
    rewrites the requests array as the session grows, so requests are merged
    last-write-wins by `requestId` — re-imports and rewrites never double-record
    (the call id is derived from the requestId). Counts-never-content: titles,
    prompts, and response bodies in the same file are never read into a row.
    `modelId` is often the virtual `copilot/auto`, which no price row matches — such
    rows cost $0 and `cage doctor` flags them UNPRICED (a wrong number is worse)."""
    if not chat_session_path.exists():
        return []
    session = session or chat_session_path.stem
    reqs: dict[str, dict] = {}
    for line in chat_session_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("kind") == 0 and isinstance(rec.get("v"), dict):
            session = rec["v"].get("sessionId") or session
        if rec.get("kind") != 2 or rec.get("k") != ["requests"]:
            continue
        for req in rec.get("v") or []:
            if isinstance(req, dict) and req.get("requestId"):
                reqs[req["requestId"]] = req  # last write wins
    rows: list[dict] = []
    for rid, req in reqs.items():
        if not _copilot_chat_extension(req):
            continue
        md = (req.get("result") or {}).get("metadata") or {}
        inp = _first_int(req, _COPILOT_IN_KEYS) or _first_int(md, _COPILOT_IN_KEYS)
        out = _first_int(req, _COPILOT_OUT_KEYS) or _first_int(md, _COPILOT_OUT_KEYS)
        if not (inp or out):
            continue
        model = req.get("modelId") or ""
        rid_hash = hashlib.sha1(rid.encode("utf-8")).hexdigest()[:12]
        rows.append(schema.make_call(
            route="chat", provider=_copilot_provider(model), model=model,
            tokens_in=inp, tokens_out=out, session=session, agent="copilot",
            ts=_epoch_ms_iso(req.get("timestamp")),
            call_id=f"c_cop{rid_hash}"))
    return rows


def parse_kiro_calls(token_log: Path, session: str = "") -> list[dict]:
    """Meter Kiro from its append-only usage log `dev_data/tokens_generated.jsonl` —
    one JSON object per LLM call: `{model, provider, promptTokens, generatedTokens}`.

    Coarse by Kiro's own design: prompt tokens are reliable, output tokens are often 0,
    and the model is frequently the generic `"agent"` (Kiro doesn't surface the real
    Claude model id). The lines carry no id, so we derive a stable one from line index +
    content hash — re-importing the same append-only file never double-records, and an
    appended line gets a fresh id. Fail-open per line."""
    if not token_log.exists():
        return []
    session = session or "kiro"
    rows: list[dict] = []
    for i, line in enumerate(token_log.read_text(encoding="utf-8").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        inp = int(rec.get("promptTokens", 0) or 0)
        out = int(rec.get("generatedTokens", 0) or 0)
        if not (inp or out):
            continue
        h = hashlib.sha1(line.encode("utf-8")).hexdigest()[:8]
        rows.append(schema.make_call(
            route="chat", provider=rec.get("provider", "kiro") or "kiro",
            model=rec.get("model", "") or "", tokens_in=inp, tokens_out=out,
            session=session, agent="kiro", call_id=f"c_kiro{i:05d}{h}"))
    return rows
