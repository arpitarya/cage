"""Parse a Claude Code transcript JSONL into call rows (plan §5, §9.5).

Claude Code can't be metered with the library adapter — you can't edit its request
code. But it *writes* a transcript whose every assistant turn already records
`message.usage`. Reading that file is metering **off the request path**: $0,
deterministic, and it works for the API and subscription paths alike (no proxy).

Each turn's `uuid` becomes the call id, so re-parsing the same transcript on a
later SessionEnd never double-records (idempotent — see hooks.session_end).
"""
from __future__ import annotations

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


def parse_codex_calls(rollout_path: Path, session: str = "") -> list[dict]:
    """Best-effort metering of a Codex CLI rollout JSONL (provider=openai)."""
    if not rollout_path.exists():
        return []
    session = session or rollout_path.stem
    rows = []
    for i, line in enumerate(rollout_path.read_text(encoding="utf-8").splitlines()):
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        u = _find_usage(rec)
        if not u:
            continue
        inp = int(u.get("input_tokens", u.get("prompt_tokens", 0)) or 0)
        out = int(u.get("output_tokens", u.get("completion_tokens", 0)) or 0)
        if not (inp or out):
            continue
        rows.append(schema.make_call(
            route="chat", provider="openai", model=_model_of(rec), tokens_in=inp,
            tokens_out=out, session=session, agent="codex",
            call_id=f"c_codex{session[:8]}{i:05d}"))
    return rows


def _model_of(rec: dict) -> str:
    for k in ("model", "model_id", "slug"):
        if isinstance(rec.get(k), str):
            return rec[k]
    return ""
