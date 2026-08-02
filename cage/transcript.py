"""Parse a Claude Code transcript JSONL into call rows (plan §5, §9.5).

Claude Code can't be metered with the library adapter — you can't edit its request
code. But it *writes* a transcript whose every assistant turn already records
`message.usage`. Reading that file is metering **off the request path**: $0,
deterministic, and it works for the API and subscription paths alike (no proxy).

Each turn's `uuid` becomes the call id, so re-parsing the same transcript on a
later import never double-records (idempotent — dedupe in `ledger.append_new`).

"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sqlite3
from pathlib import Path

from cage import schema


def _composite_id(agent: str, session: str, model: str, tokens_in: int,
                  tokens_out: int, cached_in: int, ts: str | None) -> str:
    """A *deterministic* call id for a usage row that carries no stable source id
    (a Claude turn with no `uuid`). Folded into `call_id` so `make_call`/`CALL_FIELDS`
    are unchanged; same `(agent, session, model, tokens_in, tokens_out, cached_in, ts)`
    ⇒ same id, so re-parsing the same transcript dedupes in `ledger.append_new` instead
    of minting a fresh random id each run. Same `c_`+15-char shape as the uuid path.

    Empirically defensive: no usage-bearing Claude turn observed lacks a `uuid`; this
    closes the one path where `make_call` would otherwise fall back to a random id."""
    key = "|".join(str(x) for x in (agent, session, model, tokens_in, tokens_out,
                                    cached_in, ts or ""))
    return "c_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:15]


def _usage_to_row(msg: dict, session: str, uuid: str, ts: str | None,
                  project: str = "") -> dict | None:
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
    # of a uuid-less turn no longer double-record.
    call_id = ("c_" + uuid.replace("-", "")[:15] if uuid
               else _composite_id("claude-code", session, model, tokens_in, out,
                                  cache_read, ts))
    return schema.make_call(
        route="chat", provider="anthropic", model=model,
        tokens_in=tokens_in, tokens_out=out, cached_in=cache_read,
        cache_write_in=cache_make,   # split out of tokens_in (semantics unchanged, §2.1)
        session=session, agent="claude-code", ts=ts, project=project,
        call_id=call_id)  # surface="" — CLI/extension share one store


def parse_calls(transcript_path: Path, session: str = "",
                root: Path | None = None, pol: dict | None = None) -> list[dict]:
    """One call row per assistant turn that carries usage. Tolerant of bad lines.

    ``root``/``pol`` are accepted and unused — they fed the turn-gap capture that
    the Tier-1 human axis needed (removed in v0.36); keeping the signature spares
    every caller a churn edit."""
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
        # `project` is the working-dir basename Claude stamps on each record (`cwd`) —
        # a derived attribution axis (plan §3.7). Basename only (counts-never-content
        # PII guard); absent on records without a cwd ⇒ "" (legacy contract).
        cwd = rec.get("cwd") or ""
        row = _usage_to_row(rec.get("message") or {}, session,
                            rec.get("uuid", ""), rec.get("timestamp"),
                            project=Path(cwd).name if cwd else "")
        if row:
            rows.append(row)
    return rows


def session_name_claude(transcript_path: Path) -> str:
    """The human-readable session name for a Claude transcript — the `summary` record's
    text (`{"type":"summary","summary":"…"}`, previously unused by the parser). Parse-only
    and additive: it reads the same file `parse_calls` does, extracts NOTHING but the
    title, and never touches a call row (the name lives only in `imports.jsonl`, plan §4).
    Returns the LAST summary seen (a session can be re-summarized), or ``""`` when the
    store carries none — the caller falls back to the cwd basename (`project`). Fail-open:
    a bad/unreadable transcript yields ``""``, never an exception into capture."""
    if not transcript_path.exists():
        return ""
    name = ""
    try:
        for line in transcript_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "summary":
                s = rec.get("summary")
                if isinstance(s, str) and s:
                    name = s  # last-write-wins: a later summary supersedes an earlier one
    except OSError:
        return ""
    return name


def session_name_copilot_vscode(chat_session_path: Path) -> str:
    """The session name for a Copilot VS Code chat session, resolved against VS Code's own
    chat-session store (verified against the real store, 2026-07-25 — the plan's earlier
    "title on the kind:0 record" was only partly right).

    Precedence, last-write-wins within a class:
      1. the user-set ``customTitle`` — either a ``{"kind":1,"k":["customTitle"],"v":"…"}``
         patch record or ``kind:0``'s folded ``v.customTitle``;
      2. else the first request's auto ``generatedTitle``
         (``kind:2 k:["requests"]`` → ``v[].response[].generatedTitle``);
      3. else ``""`` (a genuinely untitled session — never fabricated).

    Parse-only/additive and counts-never-content: only the title string is read; prompts,
    responses, and tool bodies in the same file are never touched, and the name lands only
    in `imports.jsonl`, never on a call row. Fail-open ⇒ ``""``."""
    if not chat_session_path.exists():
        return ""
    custom = ""
    generated = ""
    try:
        for line in chat_session_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            kind, k, v = rec.get("kind"), rec.get("k"), rec.get("v")
            if k == ["customTitle"] and isinstance(v, str) and v:
                custom = v  # last-write-wins patch record
            elif kind == 0 and isinstance(v, dict):
                ct = v.get("customTitle")
                if isinstance(ct, str) and ct:
                    custom = ct
            if not generated and kind == 2 and k == ["requests"] and isinstance(v, list):
                generated = _first_generated_title(v)
    except OSError:
        return ""
    return custom or generated


def _first_generated_title(requests: list) -> str:
    """The first request's auto `generatedTitle` (nested under its `response` blocks) —
    the VS Code auto-title fallback when no user `customTitle` is set. ``""`` if none."""
    for req in requests:
        resp = req.get("response") if isinstance(req, dict) else None
        if isinstance(resp, list):
            for blk in resp:
                if isinstance(blk, dict):
                    gt = blk.get("generatedTitle")
                    if isinstance(gt, str) and gt:
                        return gt
    return ""


_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def parse_provenance(transcript_path: Path, session: str = "") -> list[dict]:
    """File paths an Edit/Write/MultiEdit/NotebookEdit `tool_use` block touched,
    walking the same transcript `parse_calls` reads. Lower trust than an in-process
    line count — the caller tags these `method="transcript"` and resolves them against
    `HEAD`, since the transcript alone can't say which commit an edit landed in.

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
    """One call row per model **per shutdown** in a Copilot CLI session's
    `session.shutdown.modelMetrics` (provider inferred from the model name). Aggregate
    per session, not per turn — Copilot only finalizes usage at shutdown;
    `assistant.turn_end` carries no tokens.

    **Cumulative-shutdown fix (capture-precision §3.1).** A resumed session
    (`copilot --continue`, or a VS Code chat spanning restarts) writes a *second*
    `session.shutdown` whose `modelMetrics` are **cumulative** — they already include the
    first shutdown's tokens. The id encodes the shutdown **ordinal**, and each row stores
    the per-shutdown **delta** (`cumulative_n − cumulative_{n-1}` per model), so:

    - the two rows *sum* to the true cumulative (no undercount);
    - **ordinal 0 is byte-identical to the pre-fix scheme** — same id
      (`c_cop{sid[:12]}{i:03d}`, no suffix), and delta-from-nothing == the raw value — so a
      *legacy* ledger self-heals on re-import: ord 0 dedupes against the row already there
      and only the new ord≥1 delta rows append. A fresh id for ord 0 would double-count it.

    Append-only and idempotent: `ledger.append_new` dedupes on the deterministic id, so a
    re-import adds zero rows. `totalPremiumRequests` is likewise cumulative, so its
    per-shutdown delta is stamped on the shutdown's first model row — never multi-counted.
    Fail-open per line."""
    if not events_path.exists():
        return []
    session = session or events_path.parent.name  # session-state/<id>/events.jsonl
    sid = session.replace("-", "")
    rows: list[dict] = []
    prev: dict[str, tuple[int, int, int]] = {}  # model -> (cum_in, cum_out, cum_cached)
    prev_prem = 0
    ordinal = 0  # index among shutdowns that carry a modelMetrics map
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
        # `totalPremiumRequests` is a cumulative session-level billing signal
        # (import-ledger plan §2.1 — archived; PLAN.md has no §2.1);
        # stamp only its per-shutdown delta, on the first model row, so it never multi-counts.
        cum_prem = _first_int(data, ("totalPremiumRequests", "total_premium_requests"))
        prem_delta = cum_prem - prev_prem
        prev_prem = cum_prem
        suffix = "" if ordinal == 0 else f"s{ordinal:03d}"  # ord 0 → legacy id, byte-identical
        for i, (model, m) in enumerate(metrics.items()):
            if not isinstance(m, dict):
                continue
            u = m.get("usage") if isinstance(m.get("usage"), dict) else m  # tokens nest here
            cin = _first_int(u, _COPILOT_IN_KEYS)   # cumulative, already includes cache r+w
            cout = _first_int(u, _COPILOT_OUT_KEYS)
            ccached = _first_int(u, _COPILOT_CACHE_KEYS)
            pin, pout, pcached = prev.get(model, (0, 0, 0))
            din, dout, dcached = cin - pin, cout - pout, ccached - pcached
            prev[model] = (cin, cout, ccached)
            if not (din or dout):   # this shutdown added nothing for this model
                continue
            rows.append(schema.make_call(
                route="chat", provider=_copilot_provider(model), model=model,
                tokens_in=din, tokens_out=dout, cached_in=dcached,
                session=session, agent="copilot", ts=ts, surface="cli",
                premium=prem_delta if i == 0 else 0,
                call_id=f"c_cop{sid[:12]}{i:03d}{suffix}"))
        ordinal += 1
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
            ts=_epoch_ms_iso(req.get("timestamp")), surface="vscode",
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
            session=session, agent="kiro", surface="ide", call_id=f"c_kiro{i:05d}{h}"))
    return rows


# The Kiro CLI store is a SQLite DB, `conversations_v2(key=cwd, conversation_id,
# value TEXT, created_at, updated_at)`. `value` is the whole conversation JSON — token
# fields (`request_metadata.{total_tokens,uncached_input_tokens,output_tokens,…}`) are
# NULL even with an explicit model (§0 probe), so usage is credits + context% only.
# These are the ONLY keys the parser is allowed to touch inside `value` — a closed
# whitelist of numeric/metadata fields. It NEVER reads `history[].user`,
# `history[].assistant`, `content`, `text`, `transcript`, `next_message`, or the
# `auth_kv` table: counts-never-content is hardest here because content and metadata
# share the row (capture-precision §3.3).
_KIRO_CLI_TS_KEYS = ("stream_end_timestamp_ms", "request_start_timestamp_ms")


def _norm_cwd_key(p: str) -> str:
    """Normalize a `conversations_v2.key` (or the workspace root it is matched against)
    for comparison. Verified against a real store on 2026-08-01: the key is the **absolute,
    symlink-resolved cwd** kiro-cli was launched in, with no trailing separator — a
    conversation started under ``/tmp/x`` is stored as ``/private/tmp/x`` on macOS, which
    is exactly the near-miss that would return zero rows and read as "no kiro usage".

    So: resolve symlinks, collapse any trailing separator, and apply `os.path.normcase`
    (a real case fold on Windows, a no-op on POSIX — the platform's own answer, never an
    invented one). `realpath` never raises for a path that doesn't exist here, so a key
    written on another machine simply normalizes to itself."""
    if not p:
        return ""
    return os.path.normcase(str(Path(os.path.realpath(p))))


def _under(key: str, root: str) -> bool:
    """Is ``key`` the workspace ``root`` **or a directory beneath it**? The tree, not the
    directory: kiro-cli keys each conversation by the cwd it ran in, and a conversation
    started in ``repo/sub`` is still ``repo``'s work. Prefix-matched on a separator
    boundary, so ``/w/cage`` never swallows ``/w/cage-lab``."""
    k, r = _norm_cwd_key(key), _norm_cwd_key(root)
    return bool(r) and (k == r or k.startswith(r.rstrip(os.sep) + os.sep))


def _kiro_cli_credit_row(conv_id: str, doc: dict, updated_at, key: str = "") -> dict | None:
    """Extract one credits row from a conversation JSON, reading only whitelisted
    numeric/metadata fields — never any message body. Returns None if there is no
    credit signal (nothing to record). Fail-open: the caller swallows exceptions.

    ``key`` is the store's cwd column; only its **basename** reaches the row (`project`),
    never the path — the same PII guard call rows carry."""
    history = doc.get("history")
    turns = len(history) if isinstance(history, list) else 0
    model = ""
    mi = doc.get("model_info")
    if isinstance(mi, dict):
        model = str(mi.get("model_id") or mi.get("model_name") or "")
    # credits: sum the conversation-level usage_info list (unit == "credit"); never a
    # per-turn attribution (usage_info does not align 1:1 with history turns — recording
    # a per-turn credit would be a guess wearing a number, capture-precision principle).
    credits = 0.0
    utm = doc.get("user_turn_metadata")
    usage = utm.get("usage_info") if isinstance(utm, dict) else None
    if isinstance(usage, list):
        for u in usage:
            if isinstance(u, dict) and str(u.get("unit", "")).startswith("credit"):
                v = u.get("value")
                if isinstance(v, (int, float)):
                    credits += float(v)
    # context %: the last non-null value across per-turn request_metadata (context grows).
    context_pct = 0.0
    if isinstance(history, list):
        for turn in history:
            rm = turn.get("request_metadata") if isinstance(turn, dict) else None
            if isinstance(rm, dict) and isinstance(rm.get("context_usage_percentage"), (int, float)):
                context_pct = float(rm["context_usage_percentage"])
    if credits <= 0 and context_pct <= 0:
        return None  # no usage signal at all — nothing honest to record
    ts = _epoch_ms_iso(updated_at)
    # Deterministic id folds in the turn count: a resumed (grown) conversation appends a
    # fresh row; an unchanged one dedupes. `ledger.credits` collapses last-per-session so
    # the grown total is never double-summed.
    cid = str(conv_id).replace("-", "")[:12]
    return schema.make_credit(
        session=str(conv_id), agent="kiro", model=model, surface="cli",
        credits=round(credits, 6), turns=turns, context_pct=context_pct,
        ts=ts, project=Path(key).name if key else "",
        credit_id=f"k_cred{cid}{turns:03d}")


def parse_kiro_cli_credits(db_path: Path, workspace: str = "") -> list[dict]:
    """Meter Kiro CLI from its SQLite store, **read-only**, yielding *credits* usage rows
    (not call rows — Kiro CLI records no token counts; capture-precision §3.2–§3.4).

    Opened `mode=ro&immutable=1` — cage never writes, never migrates, never locks the DB.
    Reads only the `conversations_v2` table (never `auth_kv`) and, within each row's
    `value` JSON, only the whitelisted numeric/metadata fields via `_kiro_cli_credit_row`
    — never a prompt or response body. Fail-open per conversation; a driver/permission
    error on the DB returns [].

    ``workspace`` scopes the read to one **directory tree** — that directory or anything
    beneath it (`_under`). Empty reads every conversation on the machine, which is right
    for exactly one caller: a sweep into the machine ledger. Reading unscoped from a
    *project* sweep is what double-counted kiro CLI across ledgers; `paths.kiro_cli_workspace`
    is the one place that choice is made. The match is done in Python, not SQL, so the
    normalization the key actually needs (`_norm_cwd_key`: symlinks, trailing separator,
    per-platform case) is expressible — a near-miss here returns zero rows, which is
    indistinguishable from "no kiro usage"."""
    if not db_path.exists():
        return []
    uri = f"file:{db_path}?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    con.row_factory = sqlite3.Row
    rows: list[dict] = []
    try:
        for r in con.execute("SELECT key, conversation_id, value, created_at, updated_at "
                             "FROM conversations_v2"):
            key = r["key"] or ""
            if workspace and not _under(key, workspace):
                continue
            try:
                doc = json.loads(r["value"]) if r["value"] else {}
            except (ValueError, TypeError):
                continue
            try:
                row = _kiro_cli_credit_row(r["conversation_id"], doc, r["updated_at"], key)
            except Exception:  # noqa: BLE001 — fail-open per conversation
                row = None
            if row is not None:
                rows.append(row)
    except sqlite3.Error:
        return rows
    finally:
        con.close()
    rows.sort(key=lambda x: x["id"])  # deterministic order
    return rows
