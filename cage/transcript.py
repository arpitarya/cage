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
    files ([research](../docs/research/2026-08-07-graphify-store-evidence.md)):

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
#
# ONE scoped carve-out, ratified 2026-08-07:
# [ADR 0009](docs/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md).
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
# (docs/research/2026-08-07-graphify-store-evidence.md). Matched **anchored at the end**,
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
