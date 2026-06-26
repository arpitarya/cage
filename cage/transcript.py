"""Parse a Claude Code transcript JSONL into call rows (plan §5, §9.5).

Claude Code can't be metered with the library adapter — you can't edit its request
code. But it *writes* a transcript whose every assistant turn already records
`message.usage`. Reading that file is metering **off the request path**: $0,
deterministic, and it works for the API and subscription paths alike (no proxy).

Each turn's `uuid` becomes the call id, so re-parsing the same transcript on a
later SessionEnd never double-records (idempotent — see hooks.session_end).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cage import schema


def _usage_to_row(msg: dict, session: str, uuid: str, ts: str | None) -> dict | None:
    usage = msg.get("usage") or {}
    out = int(usage.get("output_tokens", 0) or 0)
    inp = int(usage.get("input_tokens", 0) or 0)
    cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
    cache_make = int(usage.get("cache_creation_input_tokens", 0) or 0)
    if not (out or inp or cache_read or cache_make):
        return None
    tokens_in = inp + cache_read + cache_make
    return schema.make_call(
        route="chat", provider="anthropic", model=msg.get("model", "") or "",
        tokens_in=tokens_in, tokens_out=out, cached_in=cache_read,
        session=session, agent="claude-code", ts=ts,
        call_id="c_" + uuid.replace("-", "")[:15] if uuid else None)


def parse_calls(transcript_path: Path, session: str = "") -> list[dict]:
    """One call row per assistant turn that carries usage. Tolerant of bad lines."""
    if not transcript_path.exists():
        return []
    session = session or transcript_path.stem
    rows = []
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
        row = _usage_to_row(rec.get("message") or {}, session,
                            rec.get("uuid", ""), rec.get("timestamp"))
        if row:
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


def _find_usage(obj) -> dict | None:
    """Depth-first search for the first dict carrying token-usage keys (Codex's
    rollout schema shifts between versions, so we match by shape not by path)."""
    if isinstance(obj, dict):
        keys = obj.keys()
        if ({"input_tokens", "output_tokens"} <= keys
                or {"prompt_tokens", "completion_tokens"} <= keys):
            return obj
        for v in obj.values():
            if (hit := _find_usage(v)) is not None:
                return hit
    elif isinstance(obj, list):
        for v in obj:
            if (hit := _find_usage(v)) is not None:
                return hit
    return None


def _codex_usage(rec: dict) -> dict | None:
    """Per-turn usage from a Codex `token_count` event. Prefer `last_token_usage`
    (this turn's delta) over `total_token_usage` (the running cumulative) — summing the
    cumulative across every event would massively over-count. Falls back to the generic
    shape-matcher for older/synthetic rollout shapes."""
    payload = rec.get("payload")
    info = payload.get("info") if isinstance(payload, dict) else None
    if isinstance(info, dict):
        for k in ("last_token_usage", "total_token_usage"):
            if isinstance(info.get(k), dict):
                return info[k]
    return _find_usage(rec)


def _codex_model(rec: dict) -> str:
    """The model id Codex stamps on a `turn_context`/`session_meta` record (top-level or
    under `payload`) — the `token_count` events that carry usage don't repeat it."""
    for obj in (rec, rec.get("payload") if isinstance(rec.get("payload"), dict) else {}):
        m = _model_of(obj) if isinstance(obj, dict) else ""
        if m:
            return m
    return ""


def parse_codex_calls(rollout_path: Path, session: str = "") -> list[dict]:
    """Best-effort metering of a Codex CLI rollout JSONL (provider=openai). The model is
    declared once in a `turn_context` record and carried forward to the usage events."""
    if not rollout_path.exists():
        return []
    session = session or rollout_path.stem
    rows: list[dict] = []
    model = ""
    for i, line in enumerate(rollout_path.read_text(encoding="utf-8").splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if m := _codex_model(rec):
            model = m
        u = _codex_usage(rec)
        if not u:
            continue
        inp = int(u.get("input_tokens", u.get("prompt_tokens", 0)) or 0)
        out = int(u.get("output_tokens", u.get("completion_tokens", 0)) or 0)
        cached = int(u.get("cached_input_tokens", u.get("cache_read_input_tokens", 0)) or 0)
        if not (inp or out):
            continue
        rows.append(schema.make_call(
            route="chat", provider="openai", model=model, tokens_in=inp,
            tokens_out=out, cached_in=cached, session=session, agent="codex",
            call_id=f"c_codex{session[:8]}{i:05d}"))
    return rows


def _model_of(rec: dict) -> str:
    for k in ("model", "model_id", "slug"):
        if isinstance(rec.get(k), str):
            return rec[k]
    return ""


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
