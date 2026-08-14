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
import re
import sqlite3
from pathlib import Path, PurePosixPath

from cage import schema


def _composite_id(agent: str, session: str, model: str, tokens_in: int,
                  tokens_out: int, cached_in: int, ts: str | None) -> str:
    """A *deterministic* call id for a usage row that carries no stable source id
    (a Claude turn with no `uuid`). Folded into `call_id` so `make_call`/`CALL_FIELDS`
    are unchanged; same `(agent, session, model, tokens_in, tokens_out, cached_in, ts)`
    ⇒ same id, so re-parsing the same transcript dedupes in `ledger.append_new` instead
    of minting a fresh random id each run. Same `c_`+15-char shape as the uuid path —
    the two *deterministic* paths agree at 15; `ids.new_id`'s random path is
    deliberately wider (19), because entropy width is a correctness property there and
    is irrelevant here (these ids carry none — they are a hash of the turn).

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


# The whitelisted `message.usage` props CLAUDE-METRICS folds — every read here is
# envelope + usage only (counts-never-content); see `_fold_claude_chat`.

def _claude_chat_key(rec: dict, session_hint: str) -> str:
    return rec.get("sessionId") or session_hint


def _fold_claude_records(files: list[Path],
                         session_hint: str = "") -> tuple[dict[tuple, dict], dict[str, int]]:
    """THE DEDUP LAW's fold, and the ONE place it happens (METRICS-PRIMARY P1).

    Returns ``(folded, raw_rows)``: the surviving record per
    ``(chat_key, requestId, message.id)`` — last occurrence wins — and the pre-fold row
    count per chat, which is the inflation evidence CLAUDE-DEDUP measures.

    Extracted from `_fold_claude_chat` so the **chat grain** and the **request grain**
    are two projections of one fold rather than two folds. A second fold is the failure
    this extraction exists to prevent: the two grains would drift, and their totals — the
    same traffic counted two ways — would silently stop agreeing.

    Reads envelope + `message.usage` only (counts-never-content). Fail-open per file: a
    missing file is skipped, a bad line is skipped, an unreadable file yields nothing."""
    if not session_hint and files:
        f0 = files[0]
        session_hint = (f0.parent.parent.name if f0.parent.name == "subagents"
                        else f0.stem)
    folded: dict[tuple, dict] = {}
    raw_rows: dict[str, int] = {}
    for f in files:
        if not f.exists():
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") != "assistant":
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            if not usage:
                continue
            chat_key = _claude_chat_key(rec, session_hint)
            raw_rows[chat_key] = raw_rows.get(chat_key, 0) + 1
            req_id = rec.get("requestId") or ""
            msg_id = msg.get("id") or ""
            fold_key = ((chat_key, req_id, msg_id) if (req_id or msg_id)
                        else (chat_key, "uuid", rec.get("uuid", "")))
            folded[fold_key] = rec  # last occurrence wins — full row replaces prior
    return folded, raw_rows


def _fold_claude_chat(files: list[Path], session_hint: str = "") -> dict[str, dict]:
    """THE DEDUP LAW as code (CLAUDE-METRICS handoff §4.4) — one API response writes
    1–5 assistant rows (one per content block), each carrying a distinct `uuid` but the
    SAME `requestId` + `message.id` and a full copy of `usage`; naive per-row summation
    inflates output tokens ~2–3× (the CLAUDE-DEDUP defect this kind is built to dodge,
    not fix — `parse_calls` is untouched).

    Streams every file in ``files`` (the caller's session fileset — main first, then
    `subagents/*` sorted; `importcmd._claude_session_filesets` builds it). Two passes
    over the SAME parsed records, never two file reads:

    1. Fold: per `type=="assistant"` row with non-empty `message.usage`, key on
       `(chat_key, requestId, message.id)` — both id parts empty (legacy rows) falls
       back to `(chat_key, "uuid", uuid)` (no fold possible, none needed). **Last
       occurrence wins** — a later duplicate's row REPLACES the entry wholesale (ccusage
       #888: latest carries the final `output_tokens`). `chat_key` is the row's own
       `sessionId`, else ``session_hint`` (the fileset's intended session id, resolved
       by the caller even when the main file is missing — a subagent-only fileset) —
       resolved BEFORE folding so duplicates of one request can never fold under two
       different chat keys. `raw_rows` is counted here, per chat_key, over every
       occurrence seen (pre-fold) — the fold-vs-raw ratio on the emitted row IS the
       inflation evidence CLAUDE-DEDUP measures, captured correctly this time.
    2. Accumulate: the SURVIVING (deduped) rows are summed into one accumulator per
       chat_key — `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
       → `tokens_in`; `output_tokens` → `tokens_out`; `cache_read_input_tokens` →
       `cached_in`; `cache_creation_input_tokens` → `cache_write_in`;
       `cache_creation.ephemeral_5m_input_tokens`/`ephemeral_1h_input_tokens` →
       `ttl_5m`/`ttl_1h`; `output_tokens_details.thinking_tokens` → `thinking`;
       `server_tool_use.web_search_requests`/`web_fetch_requests` → `web_search`/
       `web_fetch`; `isSidechain` rows ALSO add their tokens to
       `sidechain_tokens_in`/`sidechain_tokens_out`; per-`message.model` sums →
       `model_totals`; `requests` counts surviving keys; `ts` = max row `timestamp`;
       `project` = basename of the last-seen `cwd` (counts-never-content: basename
       only, never a path).

    Reads NOTHING else — no `summary` titles, no content blocks, no `tool-results/`.
    Fail-open per file: a missing file is skipped, a bad line is skipped, an unreadable
    file yields no rows from it (never raises into capture). A fileset that emits >1
    chat_key (resume drift — a row's `sessionId` disagrees with the fileset's own
    intended session) is correct behavior, not a bug."""
    folded, raw_rows = _fold_claude_records(files, session_hint)
    chats: dict[str, dict] = {}
    for (chat_key, *_rest), rec in folded.items():
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        acc = chats.setdefault(chat_key, {
            "tokens_in": 0, "tokens_out": 0, "cached_in": 0, "cache_write_in": 0,
            "ttl_5m": 0, "ttl_1h": 0, "thinking": 0, "web_search": 0, "web_fetch": 0,
            "requests": 0, "sidechain_tokens_in": 0, "sidechain_tokens_out": 0,
            "model_totals": {}, "ts": None, "project": ""})
        inp = int(usage.get("input_tokens", 0) or 0)
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
        out = int(usage.get("output_tokens", 0) or 0)
        tin = inp + cache_read + cache_write
        acc["tokens_in"] += tin
        acc["tokens_out"] += out
        acc["cached_in"] += cache_read
        acc["cache_write_in"] += cache_write
        cc = usage.get("cache_creation") or {}
        if isinstance(cc, dict):
            acc["ttl_5m"] += int(cc.get("ephemeral_5m_input_tokens", 0) or 0)
            acc["ttl_1h"] += int(cc.get("ephemeral_1h_input_tokens", 0) or 0)
        otd = usage.get("output_tokens_details") or {}
        if isinstance(otd, dict):
            acc["thinking"] += int(otd.get("thinking_tokens", 0) or 0)
        stu = usage.get("server_tool_use") or {}
        if isinstance(stu, dict):
            acc["web_search"] += int(stu.get("web_search_requests", 0) or 0)
            acc["web_fetch"] += int(stu.get("web_fetch_requests", 0) or 0)
        if rec.get("isSidechain"):
            acc["sidechain_tokens_in"] += tin
            acc["sidechain_tokens_out"] += out
        model = msg.get("model", "") or ""
        if model:
            mt = acc["model_totals"].setdefault(
                model, {"tokens_in": 0, "tokens_out": 0, "cached_in": 0, "cache_write_in": 0})
            mt["tokens_in"] += tin
            mt["tokens_out"] += out
            mt["cached_in"] += cache_read
            mt["cache_write_in"] += cache_write
        acc["requests"] += 1
        ts = rec.get("timestamp")
        if ts and (acc["ts"] is None or ts > acc["ts"]):
            acc["ts"] = ts
        cwd = rec.get("cwd") or ""
        if cwd:
            acc["project"] = Path(cwd).name

    for chat_key, n in raw_rows.items():
        chats.setdefault(chat_key, {
            "tokens_in": 0, "tokens_out": 0, "cached_in": 0, "cache_write_in": 0,
            "ttl_5m": 0, "ttl_1h": 0, "thinking": 0, "web_search": 0, "web_fetch": 0,
            "requests": 0, "sidechain_tokens_in": 0, "sidechain_tokens_out": 0,
            "model_totals": {}, "ts": None, "project": ""})["raw_rows"] = n
    return chats


def parse_claude_chat_metrics(fileset: list[Path], session_hint: str = "") -> list[dict]:
    """`_fold_claude_chat` → one `make_claude_metric` row per chat key (CLAUDE-METRICS
    handoff §4.4). `metric_id` folds the chat's own recorded values (never `ts`, which
    is data-derived and would otherwise fork the id on nothing but wall-clock noise) into
    a sha1, so a grown chat (more tokens since the last capture) appends a FRESH row and
    an unchanged one dedupes — `ledger.claude_metrics` resolves the latest per session at
    read time (the `parse_copilot_*_metrics` id-fold precedent). Fail-open: `_fold_claude_chat`
    already tolerates a missing/unreadable/malformed file or line."""
    chats = _fold_claude_chat(fileset, session_hint=session_hint)
    rows: list[dict] = []
    for session, acc in chats.items():
        model_totals = [{"model": m, **v} for m, v in sorted(acc["model_totals"].items())]
        payload = json.dumps({
            "tokens_in": acc["tokens_in"], "tokens_out": acc["tokens_out"],
            "cached_in": acc["cached_in"], "cache_write_in": acc["cache_write_in"],
            "ttl_5m": acc["ttl_5m"], "ttl_1h": acc["ttl_1h"], "thinking": acc["thinking"],
            "web_search": acc["web_search"], "web_fetch": acc["web_fetch"],
            "requests": acc["requests"], "raw_rows": acc.get("raw_rows", 0),
            "sidechain_tokens_in": acc["sidechain_tokens_in"],
            "sidechain_tokens_out": acc["sidechain_tokens_out"],
            "model_totals": model_totals}, sort_keys=True, default=str)
        metric_id = "clm_" + hashlib.sha1(f"{session}|{payload}"
                                          .encode("utf-8")).hexdigest()[:16]
        rows.append(schema.make_claude_metric(
            session=session, project=acc["project"], model_totals=model_totals,
            tokens_in=acc["tokens_in"], tokens_out=acc["tokens_out"],
            cached_in=acc["cached_in"], cache_write_in=acc["cache_write_in"],
            ttl_5m=acc["ttl_5m"], ttl_1h=acc["ttl_1h"], thinking=acc["thinking"],
            web_search=acc["web_search"], web_fetch=acc["web_fetch"],
            requests=acc["requests"], raw_rows=acc.get("raw_rows", 0),
            sidechain_tokens_in=acc["sidechain_tokens_in"],
            sidechain_tokens_out=acc["sidechain_tokens_out"],
            ts=acc["ts"], metric_id=metric_id))
    rows.extend(_claude_request_rows(fileset, session_hint))
    return rows


def _claude_request_rows(fileset: list[Path], session_hint: str = "") -> list[dict]:
    """One `source="request"` row per folded `(requestId, message.id)` — the request grain
    `ledger.spend` resolves post-cutover (METRICS-PRIMARY P1).

    **This is where CLAUDE-DEDUP and CLAUDE-SUBAGENT-KEY are closed**, in the new ledger
    rather than in `parse_calls` (which is deliberately untouched, so the pre-cutover
    history it wrote stays exactly as recorded):

    - **CLAUDE-DEDUP** — one API response writes 1–5 assistant rows sharing a `requestId`
      + `message.id`, each with a full copy of `usage`. `parse_calls` keys on `uuid` and
      counts every one, inflating claude spend ~2–3×. Here the fold key IS the grain, so
      the duplicates collapse by construction and the row count is the request count.
    - **CLAUDE-SUBAGENT-KEY** — a subagent transcript is session-keyed by filename stem in
      `parse_calls`, landing its spend in a phantom chat. `_claude_chat_key` reads each
      record's OWN `sessionId`, so a subagent's requests join their parent chat.

    `model` comes from the record's own `message.model`, so every row carries the single
    model its cost prices against — the one thing the chat-grain row structurally cannot
    give (it holds a `model_totals` list). `request` is the fold key's `requestId` when
    the store wrote one, else the `message.id`, else the `uuid` — the same three-step
    fallback the fold itself uses, so a row can never end up with an empty grain key while
    the fold considered it distinct.

    `metric_id` folds the row's own recorded values, so a re-capture of an unchanged
    request dedupes and a corrected one appends; `ledger.claude_request_metrics` resolves
    the latest per `(session, request)`."""
    folded, _raw = _fold_claude_records(fileset, session_hint)
    rows: list[dict] = []
    for (chat_key, k1, k2), rec in folded.items():
        msg = rec.get("message") or {}
        usage = msg.get("usage") or {}
        cache_read = int(usage.get("cache_read_input_tokens", 0) or 0)
        cache_write = int(usage.get("cache_creation_input_tokens", 0) or 0)
        tin = int(usage.get("input_tokens", 0) or 0) + cache_read + cache_write
        out = int(usage.get("output_tokens", 0) or 0)
        request = k1 if k1 and k1 != "uuid" else (k2 or "")
        cc = usage.get("cache_creation") or {}
        ttl_5m = int(cc.get("ephemeral_5m_input_tokens", 0) or 0) if isinstance(cc, dict) else 0
        ttl_1h = int(cc.get("ephemeral_1h_input_tokens", 0) or 0) if isinstance(cc, dict) else 0
        otd = usage.get("output_tokens_details") or {}
        thinking = int(otd.get("thinking_tokens", 0) or 0) if isinstance(otd, dict) else 0
        stu = usage.get("server_tool_use") or {}
        web_search = int(stu.get("web_search_requests", 0) or 0) if isinstance(stu, dict) else 0
        web_fetch = int(stu.get("web_fetch_requests", 0) or 0) if isinstance(stu, dict) else 0
        model = str(msg.get("model", "") or "")
        cwd = rec.get("cwd") or ""
        payload = json.dumps({"ti": tin, "to": out, "ci": cache_read, "cw": cache_write,
                              "t5": ttl_5m, "t1": ttl_1h, "th": thinking,
                              "ws": web_search, "wf": web_fetch, "m": model},
                             sort_keys=True, default=str)
        rows.append(schema.make_claude_metric(
            source="request", session=chat_key, request=request, model=model,
            # The same provider `parse_calls` stamps on this store's call rows —
            # `policy.price_match` keys on (provider, model), so without it a
            # perfectly-counted row prices as `none`.
            provider="anthropic" if model else "",
            project=Path(cwd).name if cwd else "",
            tokens_in=tin, tokens_out=out, cached_in=cache_read,
            cache_write_in=cache_write, ttl_5m=ttl_5m, ttl_1h=ttl_1h,
            thinking=thinking, web_search=web_search, web_fetch=web_fetch,
            requests=1,
            sidechain_tokens_in=tin if rec.get("isSidechain") else 0,
            sidechain_tokens_out=out if rec.get("isSidechain") else 0,
            ts=rec.get("timestamp"),
            metric_id="clm_" + hashlib.sha1(
                f"request|{chat_key}|{request}|{payload}".encode("utf-8")).hexdigest()[:16]))
    return rows


# `workspace.yaml`'s `name:` key, anchored at column 0 so a nested `name:` under some
# future block can never be mistaken for the conversation's own. `[^\S\n]` rather than
# `\s` for the same reason: `\s` matches a newline, which would let the pattern slide
# onto the following line and lift an unrelated value.
_COPILOT_CLI_NAME = re.compile(r"^name:[^\S\n]*(.*)$", re.MULTILINE)


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


def session_name_copilot_cli(events_path: Path) -> str:
    """The session name for a Copilot **CLI** conversation — read from `workspace.yaml`,
    the sibling of the `events.jsonl` cage already parses.

    **`events.jsonl` carries no title.** Probed 2026-08-14 across 24 real session files:
    457 events, 269 distinct nested key paths, 12 event types, and every title-shaped key
    belongs to a *tool call* (`data.toolRequests[].name`, `data.toolName`,
    `data.predictedLabel`), never to the conversation. `session.start` carries the
    sessionId, version and a cwd/git context; `session.shutdown` carries token and model
    metrics. Neither has a name
    ([probe](../work/research/2026-08-14-chat-title-store-probes.md)).

    `workspace.yaml`, beside it, does: `name:` on **24 of 32** files, every present slot
    non-empty, and `user_named: false` on all 32 (the name is auto-derived from the
    opening turn, never user-set). The 8 files with no `name:` key at all are the honest-
    empty case and stay ``""``.

    **Parsed by hand, and deliberately not with a YAML subset parser.** `dependencies = []`
    is law, the stdlib ships no YAML, and every file probed is **flat** — no nesting, no
    lists, one `key: value` per line. So this reads exactly one key with a regex and
    **fails closed**: anything it does not understand yields ``""``. Writing a general
    parser to serve one string would be strictly more code and strictly more ways to be
    wrong about someone else's file.

    Note the two stores are **not in bijection** (32 `workspace.yaml` to 24
    `events.jsonl`), so neither side may be assumed present.

    Parse-only/additive and counts-never-content: only the title string is read, and it
    lands only in `imports.jsonl`, never on a call row. Fail-open ⇒ ``""``."""
    if not events_path.exists():
        return ""
    ws = events_path.parent / "workspace.yaml"
    try:
        text = ws.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    m = _COPILOT_CLI_NAME.search(text)
    if not m:
        return ""
    raw = m.group(1).strip()
    # A YAML scalar may be single- or double-quoted; strip ONE matching pair and nothing
    # else. No escape processing: a name that needs it is a name this reader does not
    # understand, and "" beats a mangled guess.
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        raw = raw[1:-1]
    return raw.strip()


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


def _proposed_lines(name: str, inp: dict) -> list[str]:
    """The exact text an edit tool-use block proposed to write, split into lines.

    One branch per tool because each carries the new text under its own key — and the
    keys are read as a **closed set**, never `for v in inp.values()`: a future tool
    input field holding a prompt or a shell command must never be swept in here as if
    it were file content.

    - ``Edit``          → ``new_string``
    - ``MultiEdit``     → every ``edits[].new_string``, in order
    - ``Write``         → ``content`` (the whole file body)
    - ``NotebookEdit``  → ``new_source`` (one cell)

    Returns [] for a malformed/absent payload — a block cage can't read proposes
    nothing, which the matcher then scores as `unknown`, never as human."""
    if name == "Edit":
        s = inp.get("new_string")
        return s.splitlines() if isinstance(s, str) else []
    if name == "MultiEdit":
        out: list[str] = []
        for e in inp.get("edits") or []:
            s = e.get("new_string") if isinstance(e, dict) else None
            if isinstance(s, str):
                out.extend(s.splitlines())
        return out
    if name == "Write":
        s = inp.get("content")
        return s.splitlines() if isinstance(s, str) else []
    if name == "NotebookEdit":
        s = inp.get("new_source")
        return s.splitlines() if isinstance(s, str) else []
    return []


def _context_lines(name: str, inp: dict) -> list[str]:
    """The lines an `Edit`/`MultiEdit` block was **replacing** (`old_string`).

    An `Edit`'s `new_string` is a replacement *block*, not a diff: it re-states enough
    surrounding lines to anchor the edit, and every one of those was already in the file.
    Counting them as proposals inflates `suggested` — and, via
    `modified = suggested - kept`, `kept_modified` too.

    This function only **transports** the raw text. It deliberately does not compare or
    normalize anything: `linematch` documents itself as the one normalizer, and matching
    a proposal against a context line is a matching operation, so the subtraction lives
    there (`linematch.subtract_context`). Normalizing on this side of that boundary is
    how the two halves would drift apart.

    `Write` and `NotebookEdit` have no `old_string` — they carry a whole file body or a
    whole cell — so their unchanged lines stay unsubtractable and their `suggested`
    stays inflated. Stated rather than papered over; there is no evidence in the
    transcript to fix it with."""
    if name == "Edit":
        s = inp.get("old_string")
        return s.splitlines() if isinstance(s, str) else []
    if name == "MultiEdit":
        out: list[str] = []
        for e in inp.get("edits") or []:
            s = e.get("old_string") if isinstance(e, dict) else None
            if isinstance(s, str):
                out.extend(s.splitlines())
        return out
    return []


def parse_edits(transcript_path: Path, session: str = "") -> list[dict]:
    """Every edit an assistant turn **proposed**, with the text it proposed and the
    turn's timestamp — the direct evidence behind agent-vs-human authorship (v2 P1).

    One record per `Edit`/`Write`/`MultiEdit`/`NotebookEdit` tool-use block::

        {"session": …, "file": <absolute path as the agent wrote it>,
         "ts": <ISO turn timestamp>, "cwd": <record cwd>, "lines": [<proposed lines>]}

    **The `lines` never leave process memory.** They exist so the matcher can compare
    them, transiently, against the added lines of a commit; only the resulting *counts*
    are ever written (`schema.PROVENANCE_COUNT_FIELDS`). No line body and no line hash
    is persisted, shipped, or logged — the plant-string test in
    `tests/test_authorship_capture.py` greps every written shard to prove it.

    `ts` is the turn's own timestamp, not an import-time clock: it is what places the
    edit inside a commit's window (`commitjoin.commit_windows`), so a transcript
    imported days later still resolves to the commit that actually contains the work.
    Paths are returned exactly as the agent wrote them (absolute); making them
    repo-relative is the caller's job, because only the caller knows the repo.

    Parse-only and fail-open, like every other reader here: a bad line is skipped, an
    unreadable transcript yields []. Order is transcript order (deterministic)."""
    if not transcript_path.exists():
        return []
    session = session or transcript_path.stem
    out: list[dict] = []
    try:
        text = transcript_path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") != "assistant":
            continue
        ts = rec.get("timestamp")
        cwd = rec.get("cwd") or ""
        for block in (rec.get("message") or {}).get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            name = block.get("name")
            if name not in _EDIT_TOOLS:
                continue
            inp = block.get("input") or {}
            if not isinstance(inp, dict):
                continue
            fp = inp.get("file_path") or inp.get("notebook_path")
            if not fp or not isinstance(fp, str):
                continue
            lines = _proposed_lines(name, inp)
            if not lines:
                continue  # nothing proposed ⇒ nothing to match (never a human residual)
            out.append({"session": session, "file": fp, "ts": ts, "cwd": cwd,
                        "lines": lines,
                        # Carried alongside, never subtracted here — see `_context_lines`.
                        "context": _context_lines(name, inp)})
    return out


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

# The **billed** credit figure, per surface (COPILOT-CREDITS, rung 1 of the copilot
# pricing ladder). Two different keys because the two stores are different products:
#   · VS Code chatSessions — `copilotCredits`, per REQUEST, fractional
#     (real store, 2026-08-02: 11/348 requests, 0.100185 … 1.382565, all copilot/auto).
#   · Copilot CLI events   — `totalPremiumRequests`, CUMULATIVE per session, fractional
#     (real samples: 0.33) — so it is delta'd exactly like the token counters.
# Both are read as floats and recorded verbatim: cage never interprets the unit, so a
# vendor-side change of what a credit means relabels, never renumbers. `sessionCopilotCredits`
# is deliberately NOT read — it is a running session total, and summing it per request
# would multi-count (it is also absent from the store version probed).
_COPILOT_CREDIT_KEYS = ("copilotCredits", "copilot_credits")
_COPILOT_CLI_CREDIT_KEYS = ("totalPremiumRequests", "total_premium_requests")

# The running whole-SESSION credits figure (COPILOT-METRICS handoff §4.4) — take
# max/last per session, **never sum**: it already covers out-of-turn work like
# compaction, so summing it across a session's own per-request rows would multi-count
# the same spend `_COPILOT_CREDIT_KEYS` already counts once per request.
_COPILOT_SESSION_CREDIT_KEYS = ("sessionCopilotCredits", "session_copilot_credits")
# The nano-AIU figure — the finer-grain twin of `_COPILOT_CLI_CREDIT_KEYS`
# (1 credit = 1e9 nano-AIU, research 2026-08-13). Recorded verbatim; the division is
# derive-time work cage never does at capture.
_COPILOT_NANO_AIU_KEYS = ("totalNanoAiu", "total_nano_aiu")


def _first_int(d: dict, keys: tuple[str, ...]) -> int:
    """First numeric value among ``keys``, as an int; 0 when absent or unusable.

    **Non-finite values are skipped, not converted.** `json.loads` accepts bare `NaN`
    / `Infinity` (they are not legal JSON, but Python's decoder allows them by
    default), and `int()` *raises* on both — `ValueError` for NaN, `OverflowError` for
    an infinity. That exception used to escape the parser and cost the whole file's
    rows, which is a far bigger loss than the one bad field."""
    import math
    for k in keys:
        v = d.get(k)
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v):
            return int(v)
    return 0


def _first_float(d: dict, keys: tuple[str, ...]) -> float | None:
    """The float twin of :func:`_first_int`, for the **credit** fields — which are
    genuinely fractional in both real stores (VS Code `copilotCredits: 0.100185`,
    CLI `totalPremiumRequests: 0.33`) and which `int()` would floor to a silent 0.

    Returns ``None`` when no key is present or the value is not a number, so the
    caller can keep *absent* distinct from a recorded ``0.0`` (`schema.make_call`'s
    `credits` sentinel). `bool` is excluded explicitly — it is an `int` subclass, and
    a `True` credit is malformed data, not the number 1.

    A non-finite value (`NaN`/`Infinity`, which `json.loads` accepts) also reads as
    **absent**: a non-finite dollar figure is worse than no figure at all, and absent
    is a fact cage already knows how to render."""
    import math
    for k in keys:
        v = d.get(k)
        if (isinstance(v, (int, float)) and not isinstance(v, bool)
                and math.isfinite(v)):
            return float(v)
    return None


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
    That counter is stamped **twice, deliberately**: as the legacy int `premium` (unchanged)
    and as the float `credits` that rung 1 of the pricing ladder actually reads — the real
    values are fractional, and int truncation had been silently discarding every one.
    Fail-open per line."""
    if not events_path.exists():
        return []
    session = session or events_path.parent.name  # session-state/<id>/events.jsonl
    sid = session.replace("-", "")
    rows: list[dict] = []
    prev: dict[str, tuple[int, int, int]] = {}  # model -> (cum_in, cum_out, cum_cached)
    prev_prem = 0
    prev_cred = 0.0   # the float track of the same counter — see the `credits` note below
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
        cum_prem = _first_int(data, _COPILOT_CLI_CREDIT_KEYS)
        prem_delta = cum_prem if cum_prem < prev_prem else cum_prem - prev_prem
        prev_prem = cum_prem
        # `credits` is the SAME counter read as a float, and it exists because `premium`
        # structurally cannot carry it: `totalPremiumRequests` is fractional in every real
        # sample (0.33), so `_first_int` floors it to 0 and `make_call`'s `if premium:`
        # drops the key — 13 copilot-CLI rows in a real ledger, not one carrying a premium.
        # `premium` is left exactly as it was (legacy int contract, its id scheme
        # untouched); the pricing ladder reads `credits` on BOTH copilot surfaces and never
        # falls back to `premium`. Absent counter ⇒ absent credits, never a fabricated 0.
        # A cumulative counter that goes DOWN means the store reset or was rewritten
        # (a resume can restart it), not that GitHub refunded you. Stored verbatim the
        # negative delta would quietly shrink every USD total that sums it. Read it as
        # a reset instead: the new cumulative value **is** the delta, because it counts
        # billing since the reset. Clamping to 0 would be the other option and is
        # worse — it silently discards real spend, which is the defect above.
        cum_cred = _first_float(data, _COPILOT_CLI_CREDIT_KEYS)
        cred_delta = None if cum_cred is None else (
            cum_cred if cum_cred < prev_cred else cum_cred - prev_cred)
        if cum_cred is not None:
            prev_cred = cum_cred
        suffix = "" if ordinal == 0 else f"s{ordinal:03d}"  # ord 0 → legacy id, byte-identical
        # Build the shutdown's rows FIRST, then place the billing delta on one of them.
        # `prev_cred` has already advanced at this point, so a delta pinned to a fixed
        # index whose model happened to idle was dropped on the floor — no row carried
        # it, the cursor had moved, nothing was logged, and billed spend was
        # undercounted permanently. Dict order decided whether that happened.
        emitted: list[tuple[int, dict]] = []
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
            emitted.append((i, schema.make_call(
                route="chat", provider=_copilot_provider(model), model=model,
                tokens_in=din, tokens_out=dout, cached_in=dcached,
                session=session, agent="copilot", ts=ts, surface="cli",
                call_id=f"c_cop{sid[:12]}{i:03d}{suffix}")))
        _place_billing_delta(emitted, prem_delta, cred_delta, session=session, ts=ts,
                             sid=sid, suffix=suffix)
        rows.extend(row for _i, row in emitted)
        ordinal += 1
    return rows


def _place_billing_delta(emitted: list[tuple[int, dict]], prem_delta: int,
                         cred_delta: float | None, *, session: str, ts,
                         sid: str, suffix: str) -> None:
    """Stamp one shutdown's session-level billing counters onto exactly ONE of its rows.

    **The carrier is the largest token mover, ties broken by model name** — a rule that
    is deterministic (a re-parse produces byte-identical rows), explicable, and
    independent of `modelMetrics`' dict order. It is *not* an attribution claim: the
    counter is computed by GitHub over the whole shutdown, so no single row truly owns
    it.

    **Which is why every OTHER row of a credit-bearing shutdown is stamped
    `billed_with = <carrier id>`** (REV-CREDITS defect 2, closed 2026-08-11 — the fork
    the docstring used to route to the compare doc, now decided there as *one basis per
    shutdown*). Without it the carrier priced by credits — GitHub's figure for the
    **whole** shutdown — while its siblings fell through to tokens×table, so a
    multi-model shutdown billed the same spend twice, once at GitHub's rate and once at
    cage's list rates. The link is a recorded structural fact about the shutdown; the
    alternative, splitting the credit pro-rata by token share, was rejected for deriving
    per-row credits from tokens, which is forbidden in both directions.

    **A shutdown with no credit delta stamps nothing** — there is no group basis to
    suppress, and its rows price by tokens exactly as before (byte-identical).

    When **every** model idled and a non-zero credit delta still arrived, a zero-token
    carrier row is appended rather than dropping it. That row is a true statement — this
    shutdown billed N credits and moved no tokens — and dropping it instead undercounts
    real billed spend forever, which is the defect this function exists to close.
    Mutates ``emitted`` in place. Never raises."""
    if emitted:
        _i, carrier = max(emitted, key=lambda p: (p[1]["tokens_in"], p[1]["model"]))
        if prem_delta:
            carrier["premium"] = prem_delta
        if cred_delta is not None:
            carrier["credits"] = cred_delta
            # One basis per shutdown: the carrier's credit figure covers every model in
            # it, so its siblings must not price a second time off the token table.
            # `is not None` (not truthiness) — a recorded 0.0 credit is still a recorded
            # billing fact for the whole shutdown, and its siblings are still covered.
            for _j, row in emitted:
                if row is not carrier:
                    row["billed_with"] = carrier["id"]
        return
    if not cred_delta and not prem_delta:
        return                      # nothing idled away — nothing to carry
    emitted.append((0, schema.make_call(
        route="chat", provider="copilot", model="copilot/unknown",
        tokens_in=0, tokens_out=0, session=session, agent="copilot", ts=ts,
        surface="cli", premium=prem_delta, credits=cred_delta,
        call_id=f"c_cop{sid[:12]}bil{suffix}")))


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


def _uri_basename(uri: str) -> str:
    """The basename of a `file://` URI (or a plain path), percent-decoded.

    Percent-decoding is not cosmetic: VS Code stores `file:///Users/x/my%20project`, and
    without it the stamped `project` is `my%20project` — which matches nothing a
    `--project` filter or a commit join would ever look for. Windows drive URIs
    (`file:///c%3A/...`) decode through the same path."""
    from urllib.parse import unquote, urlparse
    if not uri:
        return ""
    raw = uri
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.path or ""
    raw = unquote(raw).rstrip("/\\")
    if not raw:
        return ""
    return PurePosixPath(raw.replace("\\", "/")).name


def _vscode_project(chat_session_path: Path, first_cwd: str) -> str:
    """The project basename for a whole VS Code chat-session file, or ``""``.

    **The closest precedent is kiro CLI, not claude** — and getting that wrong is what
    made this look easy. Claude's `cwd` sits on the very record the call row is built
    from (`transcript.py:94`); here it does not: the per-request serialized fields carry
    no cwd at all. So this resolves **one** project per *file*, before the row loop, the
    way `parse_kiro_cli_calls` resolves a store-level cwd.

    Two carriers, both evidenced by this repo's probe of 1,132 real parts across 157
    files ([research](../work/research/2026-08-07-graphify-store-evidence.md)):

    1. ``workspaceStorage/<hash>/workspace.json`` → ``{"folder": "file:///…"}`` — ONE
       read, covers every request in the file. Preferred for exactly that reason.
    2. the first ``toolSpecificData.cwd.path`` on a `run_in_terminal` part — exact, but
       **partial** (only requests that ran a terminal command carry one).

    Three decisions, recorded here because each could reasonably have gone the other way:

    - **Multi-root workspaces fall through, they are not guessed.** VS Code stores a
      ``"workspace"`` key (a path to a `.code-workspace` file) instead of ``"folder"``,
      and that file names *several* roots. Stamping the workspace file's basename would
      put a whole chat's spend on a "project" that is not a working directory and may not
      be where the work happened. So carrier 1 declines and carrier 2 gets a chance —
      a terminal command's cwd is a real directory and is better evidence here than the
      workspace file ever was.
    - **A ``--path`` override must fail open to ``""``.** Under `--path`, the file is
      read from a relocated tree where ``parents[1]`` is no longer the
      ``workspaceStorage/<hash>`` dir, so a `workspace.json` found there could belong to
      something else entirely. The layout is therefore *checked*, not assumed: the file's
      own parent must be named ``chatSessions``. Failing to a blank project is the honest
      outcome — an empty `project` is the legacy contract and reads as *unconfirmable*,
      which is true, whereas a wrong basename silently moves another project's spend.
    - **Basename only, percent-decoded** — the same PII guard as `scope` and
      `tasks.jsonl`, never a full path.
    """
    if chat_session_path.parent.name == "chatSessions":
        ws = chat_session_path.parents[1] / "workspace.json"
        try:
            folder = json.loads(ws.read_text(encoding="utf-8")).get("folder") or ""
        except (OSError, ValueError, AttributeError):
            folder = ""
        if folder and (name := _uri_basename(folder)):
            return name
    return _uri_basename(first_cwd)


def _vscode_chat_requests(chat_session_path: Path, session: str = "") -> tuple[str, dict[str, dict]]:
    """Read a VS Code chatSessions file once: resolve the session id (a `kind:0` state
    record's `sessionId`, falling back to the caller-supplied value / the file stem) and
    merge every `kind:2, k:["requests"]` mutation **last-write-wins by `requestId`** —
    the store rewrites its requests array as the session grows, so a later line's copy
    of a request always wins. Pure extraction (COPILOT-METRICS handoff §4.4) of the read
    + merge loop `parse_copilot_vscode_calls` always performed, shared with
    `parse_copilot_vscode_metrics` so the two parsers can never disagree about which
    request state is current. Caller is responsible for the `chat_session_path.exists()`
    early-out — this assumes the file is there."""
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
    return session, reqs


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
    `modelId` is often the virtual `copilot/auto`, which no price row matches — so the
    token rung cannot price such a row, and it would cost $0 with `cage doctor` flagging
    it UNPRICED (a wrong number is worse). `copilotCredits`, recorded here verbatim as the
    `credits` field, is what retires that hole: GitHub already resolved the auto-routing
    and its own rates into that figure, so rung 1 of the ladder prices `copilot/auto`
    *exactly* without a single price-table row. Coverage is partial by the store's own
    doing (11/348 requests carried it in the real store probed 2026-08-02) — the ladder
    falls through per row, and an absent credit stays absent, never derived from tokens."""
    if not chat_session_path.exists():
        return []
    session, reqs = _vscode_chat_requests(chat_session_path, session)
    # Carrier 2 for the project (see `_vscode_project`): the first `run_in_terminal`
    # cwd in the file. Collected in the same pass — it is a *file*-level fact, not a
    # per-row one, so it is resolved once before the row loop.
    first_cwd = ""
    for req in reqs.values():
        parts = req.get("response")
        for part in parts if isinstance(parts, list) else ():
            if not isinstance(part, dict):
                continue
            cwd = ((part.get("toolSpecificData") or {}).get("cwd") or {}).get("path") or ""
            if cwd:
                first_cwd = cwd
                break
        if first_cwd:
            break
    project = _vscode_project(chat_session_path, first_cwd)
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
            project=project,
            credits=_first_float(req, _COPILOT_CREDIT_KEYS),
            call_id=f"c_cop{rid_hash}"))
    return rows


def _copilot_model_totals(req_or_metrics: dict, *, from_metrics: bool = False) -> tuple[list[dict], int]:
    """`modelTotals` (`[{model, inputTokens, cachedTokens, outputTokens}]`, whole-turn
    per-model sums including subagent calls and compaction — chatSessions) OR a CLI
    shutdown's `modelMetrics` map (`{model: {usage: {...}}}`, cumulative-verbatim),
    mapped to cage's `model_totals` shape (COPILOT-METRICS handoff §4.1/§4.4). Returns
    the mapped list plus the summed cached-token figure — the only durable, ungated
    cached-token source either store has. `[]`/`0` when the store carries none (only
    agent-host chatSessions sessions supply `modelTotals` — research 2026-08-13)."""
    out: list[dict] = []
    cached = 0
    if from_metrics:
        items = [(model, (m.get("usage") if isinstance(m.get("usage"), dict) else m))
                 for model, m in req_or_metrics.items() if isinstance(m, dict)]
    else:
        raw = req_or_metrics.get("modelTotals")
        items = [(mt.get("model") or mt.get("modelId") or "", mt)
                 for mt in raw if isinstance(mt, dict)] if isinstance(raw, list) else []
    for model, u in items:
        c = _first_int(u, _COPILOT_CACHE_KEYS)
        out.append({"model": model, "tokens_in": _first_int(u, _COPILOT_IN_KEYS),
                    "cached_in": c, "tokens_out": _first_int(u, _COPILOT_OUT_KEYS)})
        cached += c
    return out, cached


def parse_copilot_vscode_metrics(chat_session_path: Path, session: str = "") -> list[dict]:
    """Copilot-metrics rows from the VS Code chatSessions store — the `source="chat"`
    leg of COPILOT-METRICS (handoff §4.4). Reuses `_vscode_chat_requests` (the same
    read + last-write-wins merge `parse_copilot_vscode_calls` performs), so the two
    parsers can never disagree about which request state is current.

    One row per merged request carrying ANY signal — tokens, credits, or `modelTotals`
    — the same zero-signal skip `parse_copilot_vscode_calls` applies (a request with
    nothing recorded contributes no row). `cached_in` sums `modelTotals[].cachedTokens`
    — the only durable, ungated cached-token figure this store has (agent-host sessions
    only; a classic-extension session carries no `modelTotals` at all, so `cached_in`
    is honestly 0 for it, never guessed). `credits` is the per-request `copilotCredits`;
    `session_credits` is the running whole-session figure the store itself says to take
    as max/last, never summed — exactly what `ledger.copilot_metrics`'s collapse does.

    `metric_id` folds the row's own recorded values into a sha1: a grown request (more
    tokens, a later credits figure) hashes to a NEW id and appends a fresh row rather
    than silently overwriting a stale one; `ledger.copilot_metrics` resolves the latest
    per key at read time. Same foreign-chat-provider guard as `parse_copilot_vscode_calls`
    (`_copilot_chat_extension`) — other chat providers share this store and must never
    be attributed to copilot. Counts-never-content: only the whitelisted usage props are
    ever read, never a title, prompt, or response body."""
    if not chat_session_path.exists():
        return []
    session, reqs = _vscode_chat_requests(chat_session_path, session)
    project = ""
    rows: list[dict] = []
    for rid, req in reqs.items():
        if not _copilot_chat_extension(req):
            continue
        md = (req.get("result") or {}).get("metadata") or {}
        inp = _first_int(req, _COPILOT_IN_KEYS) or _first_int(md, _COPILOT_IN_KEYS)
        out = _first_int(req, _COPILOT_OUT_KEYS) or _first_int(md, _COPILOT_OUT_KEYS)
        model_totals, cached_in = _copilot_model_totals(req)
        credits = _first_float(req, _COPILOT_CREDIT_KEYS)
        session_credits = _first_float(req, _COPILOT_SESSION_CREDIT_KEYS)
        if not (inp or out or model_totals or credits is not None
                or session_credits is not None):
            continue
        if not project:  # file-level fact, resolved once (no per-row terminal-cwd scan
            project = _vscode_project(chat_session_path, "")  # here — that stays calls-only)
        model = req.get("modelId") or ""
        payload = json.dumps({"in": inp, "out": out, "cached": cached_in,
                              "mt": model_totals, "cr": credits, "scr": session_credits,
                              "el": req.get("elapsedMs"), "wt": req.get("timeSpentWaiting")},
                             sort_keys=True, default=str)
        rows.append(schema.make_copilot_metric(
            source="chat", session=session, surface="vscode", request=rid, model=model,
            # METRICS-PRIMARY P2 — the same derivation `parse_copilot_vscode_calls`
            # stamps; `policy.price_match` keys on (provider, model).
            provider=_copilot_provider(model) if model else "",
            tokens_in=inp, tokens_out=out, cached_in=cached_in, model_totals=model_totals,
            credits=credits, session_credits=session_credits,
            elapsed_ms=_first_int(req, ("elapsedMs",)),
            waiting_ms=_first_int(req, ("timeSpentWaiting",)),
            project=project, ts=_epoch_ms_iso(req.get("timestamp")),
            metric_id="cm_" + hashlib.sha1(f"chat|{session}|{rid}|{payload}"
                                           .encode("utf-8")).hexdigest()[:16]))
    return rows


def parse_copilot_cli_metrics(events_path: Path, session: str = "") -> list[dict]:
    """Copilot-metrics rows from a CLI session's `events.jsonl` — the `source="cli"`
    leg of COPILOT-METRICS (handoff §4.4). One row per `session.shutdown` that carries a
    `modelMetrics` map, recorded **cumulative-verbatim** — unlike `parse_copilot_calls`,
    never delta'd: `model_totals` is the per-model cumulative usage map exactly as the
    store wrote it (`inputTokens` already includes cache read+write — never add
    `cacheReadTokens` to it), `credits` is the cumulative `totalPremiumRequests` (float,
    verbatim — `int()` floors the real fractional values to 0), `nano_aiu` is the
    cumulative `totalNanoAiu`. The row's own top-level `tokens_in`/`tokens_out`/
    `cached_in` are the sum across `model_totals` — CLI has no other per-row token
    figure, the same reason `parse_copilot_vscode_metrics` sums `modelTotals` into its
    `cached_in`; summing a snapshot's OWN per-model breakdown into its own row total is
    not the forbidden op — summing *across* a session's rows is.

    `request`/`call` are both empty (this row describes the whole session's cumulative
    state, not one request or one model call) — so every shutdown of a session collapses
    to the SAME `ledger.copilot_metrics` key, and the reader keeping the highest-
    tokens/credits row already resolves to the latest, largest cumulative snapshot with
    no ordinal bookkeeping. This structurally dodges the v0.44 delta-loss bug (fixing it
    in `parse_copilot_calls` is a separate, out-of-scope defect) and needs no ordinal
    suffix the way that parser's id scheme does. `metric_id` folds the shutdown's own
    payload, so an unchanged re-shutdown (nothing grew) dedupes and a resumed session
    (larger cumulative) appends a fresh row.

    **Plus one `source="cli-delta"` row per shutdown** (METRICS-PRIMARY P0a) — the same
    shutdown's per-model **delta**, not its cumulative. It exists because a cumulative row
    cannot be a spend spine: `ledger.spend` partitions by each row's own `ts`, and a
    cumulative row carries its session's whole life at the latest capture, so a session
    straddling the cutover would be counted once in `calls` for its early half and again
    in full here. The arithmetic is `parse_copilot_cli_calls`'s, reused rather than
    reinvented — including its **reset rule**: a cumulative counter that goes DOWN means
    the store reset, so the new value *is* the delta (clamping to 0 would silently discard
    real spend). The verbatim `cli` row is still written and is untouched; the two describe
    the same traffic and must never be summed, which is why only `cli-delta` is in
    `ledger.SPEND_SOURCES`. A shutdown that added nothing emits no delta row at all."""
    if not events_path.exists():
        return []
    session = session or events_path.parent.name
    rows: list[dict] = []
    prev: dict[str, tuple[int, int, int]] = {}  # model -> cumulative (in, out, cached)
    prev_cred = 0.0
    prev_nano = 0.0
    ordinal = 0
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
        if not isinstance(metrics, dict):
            continue
        ts = rec.get("timestamp")
        model_totals, cached_in = _copilot_model_totals(metrics, from_metrics=True)
        tokens_in = sum(mt["tokens_in"] for mt in model_totals)
        tokens_out = sum(mt["tokens_out"] for mt in model_totals)
        credits = _first_float(data, _COPILOT_CLI_CREDIT_KEYS)
        nano_aiu = _first_float(data, _COPILOT_NANO_AIU_KEYS)
        if not (model_totals or credits is not None or nano_aiu is not None):
            continue
        payload = json.dumps({"mt": model_totals, "cr": credits, "na": nano_aiu},
                             sort_keys=True, default=str)
        rows.append(schema.make_copilot_metric(
            source="cli", session=session, surface="cli",
            tokens_in=tokens_in, tokens_out=tokens_out, cached_in=cached_in,
            model_totals=model_totals, credits=credits, nano_aiu=nano_aiu, ts=ts,
            metric_id="cm_" + hashlib.sha1(f"cli|{session}|{payload}"
                                           .encode("utf-8")).hexdigest()[:16]))
        # ── the point-in-time twin ────────────────────────────────────────────
        d_totals: list[dict] = []
        for mt in model_totals:
            model = mt["model"]
            pin, pout, pcached = prev.get(model, (0, 0, 0))
            cin, cout, ccached = mt["tokens_in"], mt["tokens_out"], mt.get("cached_in", 0)
            prev[model] = (cin, cout, ccached)
            # A DECREASE is a store reset, not a refund — the new value is the delta.
            din = cin if cin < pin else cin - pin
            dout = cout if cout < pout else cout - pout
            dcached = ccached if ccached < pcached else ccached - pcached
            if din or dout:
                d_totals.append({"model": model, "tokens_in": din, "tokens_out": dout,
                                 "cached_in": dcached})
        d_cred = None
        if credits is not None:
            d_cred = credits if credits < prev_cred else credits - prev_cred
            prev_cred = credits
        d_nano = None
        if nano_aiu is not None:
            d_nano = nano_aiu if nano_aiu < prev_nano else nano_aiu - prev_nano
            prev_nano = nano_aiu
        ordinal += 1
        if d_totals or d_cred or d_nano:
            d_payload = json.dumps({"mt": d_totals, "cr": d_cred, "na": d_nano,
                                    "o": ordinal}, sort_keys=True, default=str)
            rows.append(schema.make_copilot_metric(
                source="cli-delta", session=session, surface="cli",
                model=d_totals[0]["model"] if len(d_totals) == 1 else "",
                provider=_copilot_provider(d_totals[0]["model"]) if len(d_totals) == 1 else "",
                # The shutdown ORDINAL is the row's grain key. `ledger.copilot_metrics`
                # collapses on `(source, session, surface, request, call)`, so leaving
                # `request` empty — as the cumulative `cli` row correctly does, being one
                # snapshot per session — would collapse every delta of a session into one
                # and silently discard all but the largest. A delta is per shutdown, so it
                # says so. Mirrors `parse_copilot_cli_calls`'s `s{ordinal:03d}` id suffix.
                request=f"s{ordinal - 1:03d}",
                tokens_in=sum(mt["tokens_in"] for mt in d_totals),
                tokens_out=sum(mt["tokens_out"] for mt in d_totals),
                cached_in=sum(mt["cached_in"] for mt in d_totals),
                model_totals=d_totals, credits=d_cred, nano_aiu=d_nano, ts=ts,
                metric_id="cm_" + hashlib.sha1(f"cli-delta|{session}|{d_payload}"
                                               .encode("utf-8")).hexdigest()[:16]))
    return rows


def parse_copilot_sidecar_metrics(path: Path, session: str = "") -> list[dict]:
    """Copilot-metrics rows from the agent-host usage sidecar
    (`<vscode-user>/agentHostUsage/<sanitizedSessionId>.jsonl`) — the `source="sidecar"`
    leg of COPILOT-METRICS (handoff §4.4), gated behind
    `chat.agentHost.agentDebugLog.enabled`. One row per line (`IAgentHostUsageRecord`):
    `call=turnId`; `model` is the REAL routed model for this one call — the one thing
    neither the chatSessions store nor the CLI's cumulative totals can give (both hide
    behind the virtual `copilot/auto`). Tokens from `inputTokens`/`outputTokens`/
    `cacheReadTokens`; `nano_aiu=totalNanoAiu` recorded verbatim — **never derive
    `credits = nano_aiu / 1e9` at capture** (research 2026-08-13: 1 credit = 1e9
    nano-AIU, but that division is derive-time work, if it ever happens at all).

    `session` is the file stem — the store's own SANITIZED session id, recorded as-is
    (it may not equal the chatSessions session id for the same chat; joining the two is
    a read-surface problem, out of scope here, handoff §8). `id` folds the line's own
    payload, so a re-import of an unchanged line dedupes and any change appends fresh.
    Fail-open per line — a malformed line is skipped, not fatal to the file. Lifecycle
    hazard named in the research, not handled here: the file is deleted when the host
    reports `SessionRemoved`, ungated on the enabling setting — import promptly, the
    ledger is the durable copy."""
    if not path.exists():
        return []
    session = session or path.stem
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        turn_id = rec.get("turnId") or ""
        if not turn_id:
            continue
        inp = _first_int(rec, _COPILOT_IN_KEYS)
        out = _first_int(rec, _COPILOT_OUT_KEYS)
        cached = _first_int(rec, _COPILOT_CACHE_KEYS)
        nano_aiu = _first_float(rec, _COPILOT_NANO_AIU_KEYS)
        if not (inp or out or cached or nano_aiu is not None):
            continue
        model = rec.get("model") or ""
        payload = json.dumps({"in": inp, "out": out, "cached": cached, "na": nano_aiu,
                              "m": model}, sort_keys=True, default=str)
        rows.append(schema.make_copilot_metric(
            source="sidecar", session=session, call=turn_id, model=model,
            tokens_in=inp, tokens_out=out, cached_in=cached, nano_aiu=nano_aiu,
            ts=rec.get("ts"),
            metric_id="cm_" + hashlib.sha1(f"sidecar|{session}|{turn_id}|{payload}"
                                           .encode("utf-8")).hexdigest()[:16]))
    return rows


def parse_copilot_debuglog_metrics(path: Path) -> list[dict]:
    """Copilot-metrics rows from the copilot-chat extension's debug logs
    (`<vscode-user>/workspaceStorage/<hash>/GitHub.copilot-chat/debug-logs/<sessionId>/
    *.jsonl`) — the `source="debuglog"` leg of COPILOT-METRICS (handoff §4.4), gated
    behind `github.copilot.chat.agentDebugLog.fileLogging.enabled`.

    **Whitelist read, strictly.** The same lines carry `attrs.userRequest` and
    `attrs.inputMessages` — prompt bodies — right next to the numbers. Only
    `attrs.model` / `attrs.inputTokens` / `attrs.outputTokens` / `attrs.ttft` / `ts` /
    `spanId` are ever read into a row (ADR-0009 discipline: a transient whitelist read,
    counts only — the body fields are never touched, not even to check their presence).
    Only `type == "llm_request"` lines carry usage; every other span type is skipped.
    **No cached-token field survives into this store** (the file serializer omits it,
    even though the live Chat Debug view shows one) — least useful of the five stores
    for cage, kept for completeness.

    `session` is the containing `debug-logs/<sessionId>/` directory name — an
    extension-internal id that may not equal the chatSessions session id for the same
    chat (recorded verbatim; joining the two is a read-surface problem, out of scope
    here, handoff §8). `call=spanId`. `id` folds the line's own whitelisted values."""
    if not path.exists():
        return []
    session = path.parent.name
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if rec.get("type") != "llm_request":
            continue
        attrs = rec.get("attrs") or {}
        if not isinstance(attrs, dict):
            continue
        span_id = rec.get("spanId") or ""
        if not span_id:
            continue
        inp = _first_int(attrs, _COPILOT_IN_KEYS)
        out = _first_int(attrs, _COPILOT_OUT_KEYS)
        ttft = _first_int(attrs, ("ttft", "ttft_ms"))
        if not (inp or out or ttft):
            continue
        model = attrs.get("model") or ""
        payload = json.dumps({"in": inp, "out": out, "ttft": ttft, "m": model},
                             sort_keys=True, default=str)
        rows.append(schema.make_copilot_metric(
            source="debuglog", session=session, call=span_id, model=model,
            tokens_in=inp, tokens_out=out, ttft_ms=ttft, ts=rec.get("ts"),
            metric_id="cm_" + hashlib.sha1(f"debuglog|{session}|{span_id}|{payload}"
                                           .encode("utf-8")).hexdigest()[:16]))
    return rows


def parse_copilot_otel_metrics(db_path: Path) -> list[dict]:
    """Copilot-metrics rows from the OTel SQLite span store
    (`<vscode-user>/globalStorage/github.copilot-chat/agent-traces.db`) — the
    `source="otel"` leg of COPILOT-METRICS (handoff §4.4), gated behind
    `github.copilot.chat.otel.dbSpanExporter.enabled`. Opened `mode=ro`: cage never
    writes, never migrates. Reads ONLY the denormalized `spans` table columns named
    below — **never** `span_attributes`/`span_events` (they can carry message content
    under `otel.captureContent`; those tables are simply never queried, a stricter
    guard than `debuglog`'s field-level whitelist).

    ``SELECT span_id, COALESCE(conversation_id, chat_session_id), COALESCE
    (response_model, request_model), input_tokens, output_tokens, cached_tokens,
    ttft_ms, start_time_ms FROM spans WHERE operation_name='chat'``. `call=span_id`;
    `ts` from `start_time_ms` (epoch ms) via `_epoch_ms_iso`. This is the only
    per-model-call cached-token source for the *classic* extension surface (the
    sidecar covers only agent-host sessions).

    Any `sqlite3.Error` — a schema surprise on this pre-1.0 store, a lock, a permission
    error — returns `[]`: fail-open, never assert the schema. A WAL tail not yet
    checkpointed is acceptably missed on this pass; cage never checkpoints (that
    mutates the store)."""
    if not db_path.exists():
        return []
    uri = f"file:{db_path}?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    rows: list[dict] = []
    try:
        cur = con.execute(
            "SELECT span_id, COALESCE(conversation_id, chat_session_id), "
            "COALESCE(response_model, request_model), input_tokens, output_tokens, "
            "cached_tokens, ttft_ms, start_time_ms FROM spans WHERE operation_name='chat'")
        for span_id, session, model, inp, out, cached, ttft, start_ms in cur:
            if not span_id:
                continue
            inp = int(inp) if isinstance(inp, (int, float)) else 0
            out = int(out) if isinstance(out, (int, float)) else 0
            cached = int(cached) if isinstance(cached, (int, float)) else 0
            ttft = int(ttft) if isinstance(ttft, (int, float)) else 0
            if not (inp or out or cached):
                continue
            session = session or ""
            model = model or ""
            payload = json.dumps({"in": inp, "out": out, "cached": cached,
                                  "ttft": ttft, "m": model}, sort_keys=True)
            rows.append(schema.make_copilot_metric(
                source="otel", session=session, call=str(span_id), model=model,
                tokens_in=inp, tokens_out=out, cached_in=cached, ttft_ms=ttft,
                ts=_epoch_ms_iso(start_ms),
                metric_id="cm_" + hashlib.sha1(
                    f"otel|{session}|{span_id}|{payload}".encode("utf-8")).hexdigest()[:16]))
    except sqlite3.Error:
        return rows
    finally:
        con.close()
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


def parse_kiro_ide_metrics(db_path: Path) -> list[dict]:
    """Kiro-metrics rows from the IDE's timestamped twin of `parse_kiro_calls`'s jsonl
    — `dev_data/devdata.sqlite`, table `tokens_generated` (the `source="ide"` leg of
    KIRO-METRICS, handoff §4.4). The SAME counter as the jsonl, plus a `timestamp` and
    a cursorable `id` the jsonl never carried.

    Read-only (`mode=ro&immutable=1`); never writes, migrates, or locks the DB.
    **Explicit-column SELECT, never `SELECT *`**: `id, tokens_prompt, tokens_generated,
    timestamp` are the four columns the research probe assumed (2026-08-13 §6,
    UNVERIFIED-COLUMNS — the real schema probe is still pending); any column beyond
    those four stays unread until that probe confirms it, so an unexpected extra
    column can never leak into a row. Rows where both counts are 0 are skipped, the
    same rule `parse_kiro_calls` applies. Any `sqlite3.Error` — a missing table, a
    schema surprise, a lock — returns `[]`: fail-open, never a crash, never a guess.

    **The 2026-02-28 `tokens_prompt` semantics cutover is recorded verbatim, never
    corrected, here**: before that date the store's `tokens_prompt` was the full
    context sent per call; after, it is incremental. This parser stores the number
    exactly as the row carries it either way — branching on it is a derive-time
    concern, if it is ever needed.

    `session="kiro"` (the store has none — the same honest constant `parse_kiro_calls`
    uses) and `surface="ide"`. `row_ref=str(id)` is both provenance and the dedupe
    anchor. `ts` from `timestamp`: tried as ISO-8601 text first, then as an epoch
    ms/s number: `_epoch_ms_iso` per row (Kiro's exact text/epoch shape is another
    piece of the pending schema probe) — a row whose `timestamp` parses neither way
    still lands, just with no `ts` (the legacy unpartitioned shard, never lost)."""
    if not db_path.exists():
        return []
    uri = f"file:{db_path}?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    rows: list[dict] = []
    try:
        cur = con.execute("SELECT id, tokens_prompt, tokens_generated, timestamp "
                          "FROM tokens_generated ORDER BY id")
        for row_id, tokens_prompt, tokens_generated, timestamp in cur:
            inp = int(tokens_prompt) if isinstance(tokens_prompt, (int, float)) else 0
            out = int(tokens_generated) if isinstance(tokens_generated, (int, float)) else 0
            if not (inp or out):
                continue
            ts = _kiro_devdata_ts(timestamp)
            rows.append(schema.make_kiro_metric(
                source="ide", session="kiro", surface="ide", tokens_in=inp,
                tokens_out=out, row_ref=str(row_id), ts=ts,
                metric_id=f"km_ide{int(row_id):08d}"))
    except sqlite3.Error:
        return rows
    finally:
        con.close()
    return rows


def _kiro_devdata_ts(value) -> str | None:
    """Best-effort `ts` for a `devdata.sqlite` row: try an ISO-8601 text timestamp
    first, then an epoch ms/s number — Kiro's exact `timestamp` column shape is one of
    the pending real-store probes (research 2026-08-13 §6). Returns ``None`` (never
    raises) when neither reading is plausible, so the row still lands, just without a
    `ts` (the legacy unpartitioned shard)."""
    if isinstance(value, str) and value:
        try:
            text = value[:-1] + "+00:00" if value.endswith("Z") else value
            dt = _dt.datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=_dt.timezone.utc)
            return dt.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
                f"{dt.microsecond // 1000:03d}Z"
        except ValueError:
            pass
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        # Epoch seconds vs milliseconds: a millisecond value for "now" is ~13 digits;
        # a second value is ~10. `_epoch_ms_iso` expects ms, so a second-scale number
        # is scaled up first.
        ms = value if value > 1e12 else value * 1000
        return _epoch_ms_iso(ms)
    return None


# The Kiro CLI store is a SQLite DB, `conversations_v2(key=cwd, conversation_id,
# value TEXT, created_at, updated_at)` (an older `conversations(key, value)` table may
# also be present — enumerated by `_kiro_cli_conversations`, KIRO-METRICS handoff §4.4).
# `value` is the whole conversation JSON — token fields
# (`request_metadata.{total_tokens,uncached_input_tokens,output_tokens,…}`) are NULL
# even with an explicit model (§0 probe; the KIRO-METRICS build records them the day
# they stop being NULL — the upgrade-watch), so today's usage is credits + context% +
# per-turn metadata only. The credits parser (`_kiro_cli_credit_row`) and the metrics
# parser (`parse_kiro_cli_metrics`) share ONE whitelist of numeric/metadata fields —
# `request_metadata` / `user_turn_metadata` / `model_info` keys only. Both NEVER read
# `history[].user`, `history[].assistant`, `content`, `text`, `transcript`,
# `next_message`, `latest_summary`, or the `auth_kv` table: counts-never-content is
# hardest here because content and metadata share the row (capture-precision §3.3).
#
# ONE scoped carve-out, ratified 2026-08-07:
# [ADR 0009](work/archive/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md).
# `parse_kiro_cli_tool_runs` below reads `history[].assistant.ToolUse` and
# `history[].user.content.ToolUseResults` — tool **commands and their stdout** — so the
# graphify savings route can size a counterfactual on kiro like it does on claude. The
# boundary that makes it safe is the same one the claude transcript route lives inside:
# those bodies are **transient**. They are hashed and token-counted in memory and are
# never returned to a writer, never stamped on a row, never logged. `_kiro_cli_credit_row`
# — the *credits* parser, and everything that writes a ledger row from this store — is
# unchanged and still bound by the whitelist above.
_KIRO_CLI_TS_KEYS = ("stream_end_timestamp_ms", "request_start_timestamp_ms")

# Kiro CLI truncates a tool's stdout and appends this marker verbatim, at the very end,
# cutting mid-token. Pinned against a real `graphify query` on kiro-cli 2.16.0, 2026-08-07
# (work/research/2026-08-07-graphify-store-evidence.md). Matched **anchored at the end**,
# never as a substring: a command whose own output discusses truncation must not be
# mistaken for a truncated one (the false positive the VS Code corpus actually produced).
KIRO_CLI_TRUNCATION_MARKER = "... (truncated to ~2000 token budget)"


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


_KIRO_CLI_TABLES = ("conversations_v2", "conversations")


def _kiro_cli_conversations(db_path: Path, workspace: str = "") -> list[tuple[str, str, dict, object]]:
    """Read the Kiro CLI SQLite store once, scoped to ``workspace`` (`_under`; empty =
    unscoped, the whole machine — the caller's choice, ADR 0006 *Scope*), and yield
    ``(key, conversation_id, doc, updated_at)`` for every conversation across whichever
    of the two known tables exist. Extracted from `parse_kiro_cli_credits`
    (KIRO-METRICS handoff §4.4) so `parse_kiro_cli_metrics` shares the exact same
    read/scan/scope pass — the two parsers can never disagree about which
    conversations are in scope.

    **Enumerates BOTH tables**: `conversations_v2` (verified against a real store,
    2026-08-01: `key, conversation_id, value, created_at, updated_at`) first, then the
    older `conversations` table when present. Its column shape is not pinned (the
    community tracker's version-era boundary contradicts cage's own 2.16.0
    observation, so treat it as unverified) — read defensively: the `conversations_v2`
    shape first, falling back to a bare `(key, value)` read (`conversation_id` lifted
    from the JSON body itself, `updated_at` absent ⇒ `None`, so a row with no `ts`
    still lands — the legacy unpartitioned shard, never lost). Either table missing
    (or neither column shape matching) raises `sqlite3.OperationalError`, caught and
    skipped per table — fail-open, never fatal to the sweep.

    Read-only (`mode=ro&immutable=1`); never writes, migrates, or locks the DB. Opens
    the DB connection once regardless of how many tables it reads."""
    if not db_path.exists():
        return []
    uri = f"file:{db_path}?mode=ro&immutable=1"
    try:
        con = sqlite3.connect(uri, uri=True)
    except sqlite3.Error:
        return []
    con.row_factory = sqlite3.Row
    out: list[tuple[str, str, dict, object]] = []
    try:
        for table in _KIRO_CLI_TABLES:
            try:
                cur = con.execute(f"SELECT key, conversation_id, value, created_at, "
                                  f"updated_at FROM {table}")
                wide = True
            except sqlite3.OperationalError:
                try:
                    cur = con.execute(f"SELECT key, value FROM {table}")
                    wide = False
                except sqlite3.OperationalError:
                    continue  # neither column shape exists — this table is absent
            try:
                for r in cur:
                    key = r["key"] or ""
                    if workspace and not _under(key, workspace):
                        continue
                    try:
                        doc = json.loads(r["value"]) if r["value"] else {}
                    except (ValueError, TypeError):
                        continue
                    if not isinstance(doc, dict):
                        continue
                    if wide:
                        cid = r["conversation_id"] or ""
                        updated_at = r["updated_at"]
                    else:
                        cid = str(doc.get("conversation_id") or "")
                        updated_at = None
                    out.append((key, cid, doc, updated_at))
            except sqlite3.Error:
                continue
    finally:
        con.close()
    return out


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

    A thin wrapper over `_kiro_cli_conversations` (KIRO-METRICS handoff §4.4 refactor —
    byte-identical output to before the extraction, pinned by the existing
    `tests/test_kiro_routing.py` suite) + `_kiro_cli_credit_row`, which does the actual
    whitelisted-field extraction — never a prompt or response body. Fail-open per
    conversation.

    ``workspace`` scopes the read to one **directory tree** — that directory or anything
    beneath it (`_under`). Empty reads every conversation on the machine, which is right
    for exactly one caller: a sweep into the machine ledger. Reading unscoped from a
    *project* sweep is what double-counted kiro CLI across ledgers;
    `paths.kiro_cli_workspace` is the one place that choice is made."""
    rows: list[dict] = []
    for key, cid, doc, updated_at in _kiro_cli_conversations(db_path, workspace):
        try:
            row = _kiro_cli_credit_row(cid, doc, updated_at, key)
        except Exception:  # noqa: BLE001 — fail-open per conversation
            row = None
        if row is not None:
            rows.append(row)
    rows.sort(key=lambda x: x["id"])  # deterministic order
    return rows


def parse_kiro_cli_metrics(db_path: Path, workspace: str = "") -> list[dict]:
    """Kiro-metrics rows from the CLI SQLite store — the `source="cli-conv"`/
    `source="cli-turn"` legs of KIRO-METRICS (handoff §4.4). Reuses
    `_kiro_cli_conversations` (the same read + table-enumeration + scope
    `parse_kiro_cli_credits` performs), so the two parsers can never disagree about
    which conversations are in scope, and the same whitelist
    (`request_metadata`/`user_turn_metadata`/`model_info` keys only).

    One `source="cli-conv"` row per conversation carrying turns, a `usage_info` list,
    or a context% signal: `credits` is the `usage_info` sum **when the list is
    present, even if it sums to a real 0.0 — else `None`** (the None-sentinel law,
    generalized from `make_call.credits`; distinct from `_kiro_cli_credit_row`'s
    stricter "credits<=0 and context<=0 ⇒ no row at all" skip, which is a *credits
    row* rule this store-verbatim kind does not inherit). `context_pct` is the last
    non-null value across turns; `turns=len(history)`.

    Plus one `source="cli-turn"` row per `history[]` entry carrying a
    `request_metadata` dict: `chunks=len(time_between_chunks)` (a chunk COUNT, never
    repurposed as `tokens_out`), `prompt_bytes`/`response_bytes`/`tool_uses`/
    `context_pct` from their own populated fields, and — the **upgrade-watch** — the
    CLI's `tokens_in`/`tokens_out`/`cached_in`/`cached_out` slots
    (`uncached_input_tokens`/`output_tokens`/`cache_read_input_tokens`/
    `cache_write_input_tokens`) recorded only when the store's own field is a real
    number; all NULL today (kiro-cli 2.16.0, research 2026-08-13), so every `cli-turn`
    row omits them via the schema's own omit-at-zero idiom — the day Kiro fills them,
    capture picks them up with zero code change. `row_ref` is the turn's own
    `request_metadata.message_id` when present, else omitted (the `turn` index alone
    already keys the row uniquely).

    `metric_id` folds each row's own recorded values into a sha1: a grown conversation
    (more turns, a later credits/context figure) hashes to a NEW id for its `cli-conv`
    row and appends a fresh row rather than silently overwriting a stale one;
    `ledger.kiro_metrics` resolves the latest per key at read time."""
    rows: list[dict] = []
    for key, cid, doc, updated_at in _kiro_cli_conversations(db_path, workspace):
        history = doc.get("history")
        turns_list = history if isinstance(history, list) else []
        turns = len(turns_list)
        model = ""
        mi = doc.get("model_info")
        if isinstance(mi, dict):
            model = str(mi.get("model_id") or mi.get("model_name") or "")
        credits = None
        utm = doc.get("user_turn_metadata")
        usage = utm.get("usage_info") if isinstance(utm, dict) else None
        if isinstance(usage, list):
            total = 0.0
            for u in usage:
                if isinstance(u, dict) and str(u.get("unit", "")).startswith("credit"):
                    v = u.get("value")
                    if isinstance(v, (int, float)):
                        total += float(v)
            credits = round(total, 6)
        context_pct = 0.0
        for turn in turns_list:
            rm = turn.get("request_metadata") if isinstance(turn, dict) else None
            if isinstance(rm, dict) and isinstance(rm.get("context_usage_percentage"), (int, float)):
                context_pct = float(rm["context_usage_percentage"])
        project = Path(key).name if key else ""
        conv_ts = _epoch_ms_iso(updated_at) if updated_at is not None else None
        if turns or credits is not None or context_pct:
            conv_payload = json.dumps({"turns": turns, "credits": credits,
                                       "context": context_pct}, sort_keys=True, default=str)
            rows.append(schema.make_kiro_metric(
                source="cli-conv", session=str(cid), surface="cli", model=model,
                credits=credits, context_pct=context_pct, turns=turns, ts=conv_ts,
                project=project,
                metric_id="km_" + hashlib.sha1(f"cli-conv|{cid}|{conv_payload}"
                                               .encode("utf-8")).hexdigest()[:16]))
        for idx, turn in enumerate(turns_list):
            rm = turn.get("request_metadata") if isinstance(turn, dict) else None
            if not isinstance(rm, dict):
                continue
            row_ref = str(rm.get("message_id") or "")
            turn_ms = _first_int(rm, _KIRO_CLI_TS_KEYS)
            turn_ts = _epoch_ms_iso(turn_ms) if turn_ms else None
            chunks_field = rm.get("time_between_chunks")
            chunks = len(chunks_field) if isinstance(chunks_field, list) else 0
            tool_field = rm.get("tool_use_ids_and_names")
            tool_uses = len(tool_field) if isinstance(tool_field, list) else 0
            prompt_bytes = _first_int(rm, ("user_prompt_length",))
            response_bytes = _first_int(rm, ("response_size",))
            turn_context = _first_float(rm, ("context_usage_percentage",))
            turn_context = turn_context if turn_context is not None else 0.0
            model_id = str(rm.get("model_id") or "")
            # The upgrade-watch: NULL on every real store probed so far (2.16.0) — the
            # day Kiro fills these, capture records them with zero code change.
            tin = _first_int(rm, ("uncached_input_tokens",))
            tout = _first_int(rm, ("output_tokens",))
            cin = _first_int(rm, ("cache_read_input_tokens",))
            cout = _first_int(rm, ("cache_write_input_tokens",))
            payload = json.dumps({"chunks": chunks, "tool_uses": tool_uses,
                                  "prompt_bytes": prompt_bytes,
                                  "response_bytes": response_bytes,
                                  "context": turn_context, "tin": tin, "tout": tout,
                                  "cin": cin, "cout": cout, "model": model_id},
                                 sort_keys=True, default=str)
            rows.append(schema.make_kiro_metric(
                source="cli-turn", session=str(cid), surface="cli", turn=str(idx),
                model=model_id, tokens_in=tin, tokens_out=tout, cached_in=cin,
                cached_out=cout, context_pct=turn_context, chunks=chunks,
                prompt_bytes=prompt_bytes, response_bytes=response_bytes,
                tool_uses=tool_uses, row_ref=row_ref, ts=turn_ts, project=project,
                metric_id="km_" + hashlib.sha1(f"cli-turn|{cid}|{idx}|{payload}"
                                               .encode("utf-8")).hexdigest()[:16]))
    rows.sort(key=lambda x: x["id"])
    return rows


def _kiro_cli_tool_runs(doc: dict, key: str) -> list[dict]:
    """Every completed tool run in one kiro-CLI conversation, as
    ``{op_kind, session, cwd, command|paths, stdout, exit_status, truncated}``.

    **The ADR-0009 carve-out lives here** — this is the one function allowed to read
    `history[].assistant.ToolUse` and `history[].user.content.ToolUseResults`. Everything
    it returns is transient: the caller hashes and counts it, and nothing reaches a row.

    Store shape, verified against a live `execute_bash` run (kiro-cli 2.16.0, 2026-08-07):
    a `ToolUse` sits in one history entry and its results in the **next**, paired by
    `tool_use_id`. `execute_bash` results are `{Json: {exit_status, stdout, stderr}}`;
    `fs_read` results are `{Text: …}` and are not read at all (a report-read needs no
    result body). A turn that errored before the follow-up leaves a use with no result —
    it yields nothing rather than a half-sized saving."""
    history = doc.get("history")
    if not isinstance(history, list):
        return []
    uses: dict[str, dict] = {}
    results: dict[str, dict] = {}
    cwd_seen = ""
    for entry in history:
        if not isinstance(entry, dict):
            continue
        user = entry.get("user")
        if isinstance(user, dict):
            env = user.get("env_context")
            if isinstance(env, dict) and isinstance(env.get("env_state"), dict):
                cwd_seen = str(env["env_state"].get("current_working_directory") or "") or cwd_seen
            content = user.get("content")
            if isinstance(content, dict) and isinstance(content.get("ToolUseResults"), dict):
                for res in content["ToolUseResults"].get("tool_use_results") or []:
                    if isinstance(res, dict) and res.get("tool_use_id"):
                        results[res["tool_use_id"]] = res
        asst = entry.get("assistant")
        if isinstance(asst, dict) and isinstance(asst.get("ToolUse"), dict):
            for use in asst["ToolUse"].get("tool_uses") or []:
                if isinstance(use, dict) and use.get("id"):
                    uses[use["id"]] = use
    out: list[dict] = []
    for uid, use in uses.items():
        args = use.get("args") if isinstance(use.get("args"), dict) else {}
        name = use.get("name")
        if name == "execute_bash":
            res = results.get(uid)
            if not isinstance(res, dict):
                continue                      # the turn errored before the result landed
            stdout = exit_status = None
            for blk in res.get("content") or []:
                if isinstance(blk, dict) and isinstance(blk.get("Json"), dict):
                    j = blk["Json"]
                    if isinstance(j.get("stdout"), str):
                        stdout = j["stdout"]
                        exit_status = str(j.get("exit_status", ""))
            if stdout is None:
                continue
            out.append({"op_kind": "bash", "tool_use_id": uid,
                        "command": str(args.get("command") or ""),
                        "cwd": str(args.get("working_dir") or "") or cwd_seen or key,
                        "stdout": stdout, "exit_status": exit_status,
                        "truncated": stdout.rstrip().endswith(KIRO_CLI_TRUNCATION_MARKER)})
        elif name == "fs_read":
            paths_read = [str(op.get("path")) for op in (args.get("operations") or [])
                          if isinstance(op, dict) and op.get("path")]
            if paths_read:
                out.append({"op_kind": "read", "tool_use_id": uid, "paths": paths_read,
                            "cwd": str(args.get("working_dir") or "") or cwd_seen or key})
    out.sort(key=lambda r: r["tool_use_id"])   # deterministic order
    return out


def parse_kiro_cli_tool_runs(db_path: Path, workspace: str = "") -> list[dict]:
    """Every kiro-CLI conversation's completed tool runs, for the graphify savings route
    (GFX-COV/P2). ``[{conversation_id, key, runs: [...]}]``.

    Same read-only SQLite access, same ``workspace`` tree scoping and the same fail-open
    discipline as :func:`parse_kiro_cli_credits` — it is the *same store*, read for a
    different question. It writes nothing and returns bodies the caller must not persist;
    see :data:`KIRO_CLI_TRUNCATION_MARKER` and ADR 0009 for the boundary."""
    if not db_path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error:
        return []
    con.row_factory = sqlite3.Row
    out: list[dict] = []
    try:
        for r in con.execute("SELECT key, conversation_id, value FROM conversations_v2"):
            key = r["key"] or ""
            if workspace and not _under(key, workspace):
                continue
            try:
                doc = json.loads(r["value"]) if r["value"] else {}
                runs = _kiro_cli_tool_runs(doc, key)
            except Exception:  # noqa: BLE001 — fail-open per conversation
                continue
            if runs:
                out.append({"conversation_id": r["conversation_id"] or "", "key": key,
                            "runs": runs})
    except sqlite3.Error:
        return out
    finally:
        con.close()
    out.sort(key=lambda c: c["conversation_id"])   # deterministic order
    return out


#: The four columns `parse_kiro_ide_metrics` reads from `tokens_generated`. Named here
#: so the doctor probe below and the parser can never disagree about what "drift" means.
KIRO_IDE_COLUMNS = ("id", "tokens_prompt", "tokens_generated", "timestamp")


def probe_kiro_ide_store(db_path: Path) -> tuple[str, str]:
    """Why the kiro IDE metric source produced nothing — ``(state, detail)``.

    **Three outcomes that used to render one indistinguishable zero** (USAGE-ONLY P3).
    `parse_kiro_ide_metrics` is fail-open by design: a missing file, a missing table and
    a renamed column all return `[]`, so `cage doctor` reported "ide: none yet" for all
    three and a reader could not tell *Kiro is not installed* from *cage is reading the
    wrong schema*. Only the last is a cage defect, and it was invisible.

    States: ``"absent"`` (no db — Kiro IDE not installed, or never run) · ``"no-table"``
    (db exists, no `tokens_generated` table) · ``"drift"`` (table exists but is missing
    a column cage reads — the schema moved and capture is silently broken) · ``"ok"``
    (readable; detail carries the row count).

    Read-only and fail-open like the parser: any sqlite error is reported as its own
    detail string rather than raised."""
    if not db_path.exists():
        return "absent", f"no {db_path.name} at {db_path.parent}"
    try:
        con = sqlite3.connect(f"file:{db_path}?mode=ro&immutable=1", uri=True)
    except sqlite3.Error as exc:
        return "no-table", f"{db_path.name} unreadable: {exc}"
    try:
        cur = con.execute("SELECT name FROM sqlite_master "
                          "WHERE type='table' AND name='tokens_generated'")
        if cur.fetchone() is None:
            return "no-table", f"{db_path.name} has no `tokens_generated` table"
        have = {r[1] for r in con.execute("PRAGMA table_info(tokens_generated)")}
        missing = [c for c in KIRO_IDE_COLUMNS if c not in have]
        if missing:
            return "drift", ("`tokens_generated` is missing column(s) "
                             f"{', '.join(missing)} — cage reads "
                             f"{', '.join(KIRO_IDE_COLUMNS)}; the schema moved")
        n = con.execute("SELECT count(*) FROM tokens_generated").fetchone()[0]
        return "ok", f"{n} row(s) in `tokens_generated`"
    except sqlite3.Error as exc:
        return "drift", f"{db_path.name} probe failed: {exc}"
    finally:
        con.close()
