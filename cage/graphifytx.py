"""Transcript-side graphify detection — the invocation-less saving cage was missing
(graphify-capture plan GC2, claude only per the GC0 verdict §3.0).

Every existing capture route (PATH shim, native shim, hook) is invocation-gated, so
they miss the two ways graphify actually saves without a metered process:

1. a `graphify query|path|explain` run the agent issued **through Bash** (an absolute
   path / venv entry-point / a surface where the PATH shim never fired) — the command
   AND its result text are both in the claude transcript, so `graphifymeter`'s
   counterfactual (the ONE implementation of the formula) reruns on that result text;
2. a **Read of `graphify-out/GRAPH_REPORT.md` / `wiki/**`** *instead of* scanning the
   source files the graph maps — the report-read saving. Its counterfactual is the
   graph's own source-file corpus (`repoceiling`, shared with the GC5b ceiling), which
   is a weaker inference than a query citing exact files, so it is **lower confidence,
   still `modeled`, and footnoted apart** (`op="report-read"`) — never conflated.

Pull-based, at `cage import` (ADR 0002 — never a watcher). Deterministic ids
(`graphifymeter.receipt_id`) + the cross-route content-key **deferral** (GC3, ADR 0005)
mean a query captured by shim AND transcript files exactly one receipt. Fail-open: a
parse/detection error files nothing and never breaks the import. Counts-never-content:
`args_hash`/`answer_hash` are hashes, never the query or its result.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
from pathlib import Path

from cage import debuglog, savings, usagelog
from cage.constants import (GRAPHIFY_RECEIPT_CONFIDENCE,
                            GRAPHIFY_REPORT_READ_CONFIDENCE)
from cage.graphifymeter import (_cited_files, _op_of, _raw_alternative, content_signature,
                                receipt_id, toks)

# Shell operators that separate commands — a graphify invocation is anchored to the
# start of its own segment, so `grep graphify` (command word `grep`) never matches.
_SEG_SPLIT = re.compile(r"\|\||&&|;|\||&|\n")
_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_REPORT_FILE = "graphify-out/graph_report.md"   # matched case-insensitively, path-suffix
_WIKI_MARKER = "graphify-out/wiki/"


def graphify_ops(command: str) -> list[tuple[str, list[str]]]:
    """Every real `graphify query|path|explain` invocation in a shell command, as
    ``(op, argv)`` with ``argv`` including the binary. Anchored on **command position**:
    the first non-assignment word of each `|`/`&&`/`;`-separated segment must itself be
    `graphify` — so `grep graphify foo`, `echo graphify`, `cat x | grep graphify` all
    yield nothing (the false-positive case GC2 tests explicitly)."""
    out: list[tuple[str, list[str]]] = []
    for seg in _SEG_SPLIT.split(command or ""):
        seg = seg.strip()
        if not seg:
            continue
        try:
            words = shlex.split(seg)
        except ValueError:
            continue
        i = 0
        while i < len(words) and _ASSIGN.match(words[i]):  # skip leading VAR=val
            i += 1
        if i >= len(words):
            continue
        if Path(words[i]).name != "graphify":   # command word must BE graphify
            continue
        rest = words[i + 1:]
        op = _op_of(rest)
        if op in ("query", "path", "explain"):
            out.append((op, words[i:]))
    return out


def _result_text(content) -> str:
    """The text of a `tool_result` block — content is a bare string or a list of
    `{type:text,text:…}` / `{content:…}` blocks. Read for its token count only."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            if isinstance(b, dict):
                if isinstance(b.get("text"), str):
                    parts.append(b["text"])
                elif isinstance(b.get("content"), str):
                    parts.append(b["content"])
        return "\n".join(parts)
    return ""


def _is_report_path(fp: str) -> bool:
    low = (fp or "").replace("\\", "/").lower()
    return low.endswith(_REPORT_FILE) or _WIKI_MARKER in low


def _load_records(transcript_path: Path):
    """Yield parsed JSON records from a transcript, tolerant of bad lines. A cheap
    substring pre-check keeps the common (no-graphify) transcript from being walked."""
    try:
        text = transcript_path.read_text(encoding="utf-8")
    except OSError:
        return
    if "graphify" not in text:   # early-exit: nothing to detect
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def _roots_for(cwd: str) -> list[Path]:
    """Resolve cited files / the graph against the transcript's own recorded ``cwd``
    (the repo the query ran in) — NOT wherever `cage import` fired."""
    if not cwd:
        return [Path.cwd()]
    base = Path(cwd)
    return [base, base / "graphify-out" / ".."]


def _report_read_signature(fp: str, graph_json: Path) -> tuple[str, str]:
    """``(args_hash, answer_hash)`` for a report read — per (file, mtime-bucket), so a
    re-read of the same report at the same graph revision dedupes to one receipt, not one
    per line (plan §4). Uses the graph's mtime bucket as the revision key."""
    args_hash = hashlib.sha1(fp.replace("\\", "/").lower().encode("utf-8")).hexdigest()[:16]
    try:
        bucket = str(int(graph_json.stat().st_mtime))
    except OSError:
        bucket = ""
    answer_hash = hashlib.sha1(bucket.encode("utf-8")).hexdigest()[:16]
    return args_hash, answer_hash


def detect_and_file(root: Path, transcript_path: Path, session: str, *,
                    existing_ids: set, pol=None) -> dict:
    """Detect graphify use in one claude transcript and file `modeled` savings receipts
    (query + report-read). ``existing_ids`` is the run-shared snapshot of graphify savings
    ids — the deferral/idempotency backstop, mutated as receipts are filed so intra-run
    duplicates also collapse. Returns counts ``{query, report_read, deferred, skipped}``.
    Fully fail-open — any error is traced and swallowed, never raised into the import."""
    counts = {"query": 0, "report_read": 0, "deferred": 0, "skipped": 0}
    try:
        tool_uses: dict[str, dict] = {}
        results: dict[str, str] = {}
        report_reads: list[tuple[str, str]] = []  # (file_path, cwd)
        for rec in _load_records(transcript_path):
            rtype = rec.get("type")
            cwd = rec.get("cwd") or ""
            if rtype == "assistant":
                for b in (rec.get("message") or {}).get("content") or []:
                    if not isinstance(b, dict) or b.get("type") != "tool_use":
                        continue
                    tid = b.get("id")
                    if tid:
                        tool_uses[tid] = {"name": b.get("name"), "input": b.get("input") or {},
                                          "cwd": cwd}
                    inp = b.get("input") or {}
                    if b.get("name") == "Read" and _is_report_path(str(inp.get("file_path") or "")):
                        report_reads.append((str(inp.get("file_path")), cwd))
            elif rtype == "user":
                for b in (rec.get("message") or {}).get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tid = b.get("tool_use_id")
                        if tid:
                            results[tid] = _result_text(b.get("content"))
        # (1) Bash graphify query|path|explain invocations
        for tid, tu in tool_uses.items():
            if tu.get("name") != "Bash":
                continue
            command = str((tu.get("input") or {}).get("command") or "")
            for op, argv in graphify_ops(command):
                answer = results.get(tid, "")
                _file_query(root, session, op, argv, answer, tu.get("cwd", ""),
                            existing_ids, counts, pol)
        # (2) Reads of the report / wiki — the invocation-less saving
        for fp, cwd in report_reads:
            _file_report_read(root, session, fp, cwd, existing_ids, counts, pol)
    except Exception as e:  # fail-open: detection must never break the import
        debuglog.exception(root, "graphify.tx", e, pol=pol)
    return counts


def _load_events(events_path: Path):
    """Yield parsed events from a copilot **CLI** `events.jsonl`, tolerant of bad lines,
    with the same cheap `graphify`-substring early-exit as `_load_records`."""
    try:
        text = events_path.read_text(encoding="utf-8")
    except OSError:
        return
    if "graphify" not in text:   # early-exit: nothing to detect
        return
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def detect_and_file_copilot(root: Path, events_path: Path, session: str, *,
                            existing_ids: set, pol=None) -> dict:
    """GC2/F1: detect graphify use in one **copilot CLI** `events.jsonl` and file the same
    `modeled` receipts as the claude route — reusing the SAME counterfactual, deterministic
    id and cross-route deferral (ADR 0005) via `_file_query`/`_file_report_read`, never a
    forked formula.

    The copilot CLI log pairs `tool.execution_start` (``data.toolName=="bash"``,
    ``data.arguments.command``) with `tool.execution_complete` (``data.result.content``)
    by ``data.toolCallId``; cwd comes from `session.start`'s ``data.context.cwd``. Because
    `content_signature` drops ``argv[0]`` and strips the answer, a query run via copilot
    signs identically to the same query via the shim or a claude transcript — so the
    deferral collapses cross-route duplicates and the two ADR-0005 acceptance tests hold
    for copilot too. Fail-open; returns the claude-shaped counts.

    Scope: the **query** route (the one the F1 evidence — command + result content —
    supports). Report-reads via copilot's `view` are handled symmetrically when the viewed
    path is the graph report/wiki (the `actual` comes from the file on disk, not the log).
    The copilot **VS Code** store is deliberately NOT handled here: its `chatSessions`
    log carries the command but no tool result (F2), so it can size no counterfactual —
    a usage row without a receipt, filed elsewhere, never a fabricated saving."""
    counts = {"query": 0, "report_read": 0, "deferred": 0, "skipped": 0}
    try:
        cwd = ""
        commands: list[tuple[str, str]] = []   # (toolCallId, command)
        report_views: list[str] = []           # viewed file paths (report/wiki only)
        results: dict[str, str] = {}
        for e in _load_events(events_path):
            if not isinstance(e, dict):
                continue
            etype = e.get("type")
            data = e.get("data") or {}
            if not isinstance(data, dict):
                continue
            if etype == "session.start":
                c = (data.get("context") or {}).get("cwd") if isinstance(data.get("context"), dict) else ""
                if c:
                    cwd = str(c)
            elif etype == "tool.execution_start":
                args = data.get("arguments") or {}
                tcid = data.get("toolCallId")
                if not (isinstance(args, dict) and tcid):
                    continue
                if data.get("toolName") == "bash":
                    commands.append((tcid, str(args.get("command") or "")))
                elif data.get("toolName") in ("view", "read"):
                    fp = str(args.get("path") or args.get("file_path") or "")
                    if _is_report_path(fp):
                        report_views.append(fp)
            elif etype == "tool.execution_complete":
                tcid = data.get("toolCallId")
                res = data.get("result")
                if tcid and isinstance(res, dict):
                    results[tcid] = _result_text(res.get("content"))
        for tcid, command in commands:
            answer = results.get(tcid, "")
            for op, argv in graphify_ops(command):
                _file_query(root, session, op, argv, answer, cwd, existing_ids, counts, pol)
        for fp in report_views:
            _file_report_read(root, session, fp, cwd, existing_ids, counts, pol)
    except Exception as e:  # fail-open: detection must never break the import
        debuglog.exception(root, "graphify.tx.copilot", e, pol=pol)
    return counts


def _file_query(root, session, op, argv, answer, cwd, existing_ids, counts, pol):
    op_s, ah, anh = content_signature(argv, answer)
    op_s = op_s or op
    own_id = receipt_id(session, op_s, ah, anh)
    shim_id = receipt_id("", op_s, ah, anh)      # the shim's honest-empty-session id
    if own_id in existing_ids:
        counts["skipped"] += 1                    # already imported — idempotent
        return
    if shim_id in existing_ids:
        counts["deferred"] += 1                   # shim already captured it (GC3 deferral)
        debuglog.event(root, pol=pol, event="receipt", tool="graphify", produced=False,
                       skip_reason="transcript-deferred-to-shim", op=op_s)
        return
    files = _cited_files(answer, op_s)
    raw = _raw_alternative(files, roots=_roots_for(cwd))
    actual = toks(answer)
    outcome = "unmeasurable"
    if raw > 0 and actual < raw:
        rid = savings.record(root, tool="graphify", unit="tokens", raw_alternative=raw,
                             actual=actual, method="modeled",
                             confidence=GRAPHIFY_RECEIPT_CONFIDENCE, op=op_s,
                             session=session, source_files=len(files), savings_id=own_id)
        if rid:
            existing_ids.add(own_id)
            counts["query"] += 1
            outcome = "receipt"
            debuglog.event(root, pol=pol, event="receipt", tool="graphify", produced=True,
                           op=op_s, route="transcript")
    # GC1: a transcript-detected run is a run — breadcrumb it (only on a filed receipt, so
    # the ledger id's idempotency carries the usage row too; the shim covers the rest).
    if outcome == "receipt":
        usagelog.record(root, op=op_s, args_hash=ah, exit=0, ms=0, outcome=outcome,
                        route="transcript")


def _file_report_read(root, session, fp, cwd, existing_ids, counts, pol):
    roots = _roots_for(cwd)
    graph_json = next((r / "graphify-out" / "graph.json" for r in roots
                       if (r / "graphify-out" / "graph.json").is_file()), None)
    if graph_json is None:
        counts["skipped"] += 1
        return
    ah, anh = _report_read_signature(fp, graph_json)
    own_id = receipt_id(session, "report-read", ah, anh)
    if own_id in existing_ids:
        counts["skipped"] += 1
        return
    from cage import repoceiling
    n_files, raw = repoceiling.corpus_tokens(graph_json, roots)
    # the report the agent actually read, as the `actual` (drift: read at import time)
    report_path = next((r / fp for r in roots if (r / fp).is_file()), Path(fp))
    try:
        actual = toks(report_path.read_text(encoding="utf-8", errors="ignore")) if report_path.is_file() else 0
    except OSError:
        actual = 0
    if raw <= 0 or actual <= 0 or actual >= raw:
        counts["skipped"] += 1
        return
    rid = savings.record(root, tool="graphify", unit="tokens", raw_alternative=raw,
                         actual=actual, method="modeled",
                         confidence=GRAPHIFY_REPORT_READ_CONFIDENCE, op="report-read",
                         session=session, source_files=n_files, savings_id=own_id)
    if rid:
        existing_ids.add(own_id)
        counts["report_read"] += 1
        debuglog.event(root, pol=pol, event="receipt", tool="graphify", produced=True,
                       op="report-read", route="transcript")


def report_read_footnote(receipts: list[dict]) -> str:
    """The one shared footnote every rendered view prints when graphify's savings include
    report-read receipts — so a weaker `report-read` inference is never silently blended
    with `graphify query` receipts (handoff §2, decision 2). ``""`` when none present."""
    rr = [r for r in receipts if r.get("tool") == "graphify" and r.get("op") == "report-read"]
    if not rr:
        return ""
    n = len(rr)
    return (f"† {n} graphify saving(s) are report-reads (read GRAPH_REPORT.md/wiki instead "
            f"of scanning source) — a weaker, lower-confidence counterfactual than a query "
            f"citing exact files; still modeled, counted apart. Its confidence (0.3) is "
            f"UNVALIDATED — a placeholder not yet scored by `insights calibration`.")
