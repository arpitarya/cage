"""Unified hookless metering — `cage import [--agent claude|copilot|kiro|all]`.

One umbrella over the per-agent hookless paths. Cage targets the wire protocol, so a
metered call is the same row no matter which agent emitted it; only *how we recover it
without hooks* differs by agent:

All three agents now persist a usage log to disk, so the hookless path is an on-disk
**import** for every one of them:

- **claude / copilot** — `~/.claude/projects/**/*.jsonl`,
  `~/.copilot/session-state/*/events.jsonl`.
- **kiro** — `kiro.kiroagent/dev_data/tokens_generated.jsonl` (coarse: prompt tokens are
  reliable, output tokens often 0, model frequently the generic `"agent"`). **There is no
  higher-fidelity fallback any more** — the metering proxy that was one went with the `data`
  group in v0.50 (SURFACE-CUT); a thin Kiro log is now a stated limit, not a routable one.

This is the ONLY capture path (capture is pull-based; MCP is the wired *read* surface).
It dedupes by call id (`ledger.append_new`), so a call seen by two racing imports (or an
import + capture-on-read) is counted once. Fail-open per file, idempotent on re-import,
$0/stdlib, counts-never-content.
"""
from __future__ import annotations

import contextlib
import datetime as _dt
import json
from pathlib import Path

from cage import (agents, capturelog, debuglog, ledger, lockutil, paths,
                  policy, transcript)

# Agents that persist a usage log to disk (everything else → proxy fallback).
LOG_BEARING = ("claude", "copilot", "kiro")


@contextlib.contextmanager
def _import_lock(foot: paths.Footprint, pol: dict | None = None):
    """Serialize concurrent import sweeps so two of them can't both snapshot the
    ledger's ``seen`` set *before* either appends — the window that let a single turn
    land twice under two racing sweeps (e.g. an explicit `cage import` and a
    capture-on-read firing at once). Holding an exclusive lock across the read-check-append section means the
    second sweep rebuilds ``seen`` only after the first has committed, so id-dedupe
    catches it. **Fail-open** via `lockutil.locked` (fcntl → msvcrt → unlocked): if
    the lock can't be taken, proceed — `ledger.append_new`'s id-dedupe stays the
    backstop, exactly as before this lock existed. Never raises into capture."""

    def _miss(exc):
        # Fail-open but never silent: an untakeable lock means the id-dedupe backstop
        # is carrying dedupe alone — attributable under CAGE_DEBUG=1.
        if exc is None:
            debuglog.event(foot.root, pol=pol, event="import",
                           skip="no-lock-primitive-on-platform")
        else:
            debuglog.exception(foot.root, "import.lock", exc, pol=pol)

    with lockutil.locked(foot.state / "import.lock", on_miss=_miss):
        yield


def _mtime_utc(f: Path):
    try:
        return _dt.datetime.fromtimestamp(f.stat().st_mtime, _dt.timezone.utc)
    except OSError:
        return None


# ── incremental high-water cursors (plan §3.7) ──────────────────────────────
# The ledger is 22k+ rows and the no-daemon model means manual `cage import`,
# `export`'s import-first refresh, and the `cage data watch` loop all re-run the scan
# repeatedly. Re-parsing every transcript + reloading the whole ledger per file each
# run is O(all logs × ledger). The cursor records each source file's last-seen
# (size, mtime) so an unchanged file is skipped *before* parsing; `append_new`'s
# id-dedupe stays the correctness backstop for grown/new files, never the throughput
# plan. Machine-local state, never a derived view.

def _load_cursors(foot: paths.Footprint) -> dict:
    try:
        return json.loads(foot.cursors.read_text(encoding="utf-8")) if foot.cursors.exists() else {}
    except (ValueError, OSError) as e:  # fail-open: a corrupt cursor file ⇒ full re-scan
        debuglog.exception(foot.root, "import.cursors-load", e)
        return {}


def _save_cursors(foot: paths.Footprint, cur: dict) -> None:
    try:
        foot.cursors.parent.mkdir(parents=True, exist_ok=True)
        foot.cursors.write_text(json.dumps(cur), encoding="utf-8")
    except OSError as e:  # fail-open: a cursor that can't persist just means a fuller re-scan next run
        debuglog.exception(foot.root, "import.cursors-save", e)


def _file_sig(f: Path):
    try:
        st = f.stat()
        return [st.st_size, st.st_mtime]
    except OSError:
        return None


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def last_import(root: Path) -> str | None:
    """ISO timestamp of the last `cage import` run over this ledger, or ``None`` if it has
    never run. Capture is pull-based (no daemon), so `cage doctor` and the read views surface
    this as "last import: N ago" and nudge when stale (plan §3.7)."""
    return _load_cursors(paths.Footprint(root)).get("_last_import")


# ── capture health: make silent zero-capture loud (docs/capture-health) ─────────
# When an agent is installed but its log source matched nothing, cage should say so
# instead of printing confident totals from the agents that still work. The gate
# inputs are recorded here at import (from facts `_scan` + the shared ledger read
# already compute — no new I/O on any read path) into cursors["_health"]; the report
# and doctor surfaces read them back and apply the triple gate (report.capture_warnings):
# installed (home exists) AND 0 files matched AND never contributed a row. Clause 3
# self-silences the warning after one captured row. `_health` rides in the cursor map
# beside `_last_import` (the same `_`-prefixed-metadata precedent, cleanup-safe: its
# keys are agent names, never absolute paths).

def _tilde(p) -> str:
    """``~``-relative form of a path when it's under the real home — keeps the stored
    ``_health`` (and the warning it renders) free of the username, and machine-portable
    in tests. An env-redirected home that isn't under ``~`` stays absolute."""
    s = str(p)
    home = str(Path.home())
    return "~" + s[len(home):] if s.startswith(home) else s


def _home_markers(agent: str) -> list[Path]:
    """The home marker(s) whose existence means agent is *installed* (capture-health
    gate 1). Copilot and Kiro have two homes each — gate 1 passes if **either** exists
    (a CLI-only Copilot user must not be nagged for an absent VS Code dir, §8)."""
    if agent == "claude":
        return [paths.claude_home()]
    if agent == "copilot":
        return [paths.copilot_home(), paths.vscode_user_dir()]
    if agent == "kiro":
        return [paths.kiro_home(), paths._first_existing(paths.kiro_data_candidates())]
    return []


def _record_health(root: Path, cursors: dict, health: dict, captured: set,
                   targets, pol: dict | None) -> None:
    """Merge the swept agents' capture-health gate inputs into ``cursors["_health"]``
    ({agent: {home, home_path, src, files, captured}}). Only the agents actually swept
    this run are touched (a single-agent `cage import --agent X` must not erase the
    others). Directive A (capture-precision §3.6): an agent with **no `[sources]` entry**
    is never swept, so it is dropped from health and stays silent — declaring capture is
    now the deliberate opt-in (this replaces the old `replace=true`-disabled path).
    Fail-open — health is best-effort and must never break an import (§6)."""
    try:
        configured = {s.agent for s in paths.resolve_log_sources(pol).sources}
        hb = cursors.get("_health")
        if not isinstance(hb, dict):
            hb = cursors["_health"] = {}
        for a in targets:
            if a not in agents.SURFACES:
                continue  # custom tools are not gated
            if a not in configured:
                hb.pop(a, None)  # no [sources.<agent>] ⇒ never swept ⇒ silent; drop stale
                continue
            info = health.get(a, {"files": 0, "src": "", "pattern": ""})
            markers = _home_markers(a)
            home_path = next((m for m in markers if m.exists()), markers[0] if markers else None)
            # `captured` is a lifetime set snapshotted BEFORE this run's appends, so a
            # first-ever import wouldn't be in it; OR in the rows this run just appended
            # (`imported > 0`) so a surface's very first capture reads healthy immediately
            # rather than only after the next import (the F2 first-capture false-negative).
            hb[a] = {"home": any(m.exists() for m in markers),
                     "home_path": _tilde(home_path) if home_path is not None else "",
                     "src": _tilde(info.get("src", "")),
                     # The glob(s) actually tried — so the zero-match ⚠ can name them
                     # instead of leaving "matched 0 files" unanswerable (handoff §5).
                     "pattern": info.get("pattern", ""),
                     "files": info.get("files", 0),
                     "captured": a in captured or info.get("imported", 0) > 0}
    except Exception as e:  # fail-open: health is best-effort, never aborts capture
        debuglog.exception(root, "import.health", e)


def _record_capture_log(root: Path, health: dict, all_rows: list, targets) -> None:
    """One `state/capture.log` breadcrumb line per swept agent this run — the
    always-on proof-of-capture (`cage/capturelog.py`; diagnose via `cage doctor --bundle`).
    ``rows_total`` is derived from the shared ``all_rows`` read (taken *before* this
    run's appends) plus this run's own ``imported`` delta — no second ledger read.
    Fail-open: best-effort, never aborts an import."""
    try:
        before_counts: dict[str, int] = {}
        for c in all_rows:
            a = agents.row_surface(c.get("agent"))
            before_counts[a] = before_counts.get(a, 0) + 1
        for a in targets:
            if a not in agents.SURFACES:
                continue  # custom tools ([sources.<name>]) aren't part of this breadcrumb
            info = health.get(a, {"files": 0, "src": ""})
            rows_new = info.get("imported", 0)
            capturelog.record(root, a, files_seen=info.get("files", 0),
                              rows_new=rows_new,
                              rows_total=before_counts.get(a, 0) + rows_new,
                              src=_tilde(info.get("src", "")))
    except Exception as e:  # fail-open: the breadcrumb is best-effort, never aborts capture
        debuglog.exception(root, "capture.log", e)


def capture_health(root: Path) -> dict:
    """The per-agent capture-health record from the last import (``cursors["_health"]``)
    — the gate inputs behind the report/doctor "installed but capturing nothing" warning.
    Empty when never imported. Parallels :func:`last_import`: read once at the CLI
    boundary and passed into the **pure** `render_report`; the report path never touches
    the filesystem for it."""
    h = _load_cursors(paths.Footprint(root)).get("_health")
    return h if isinstance(h, dict) else {}


def glob_source(src: Path, pattern) -> list[Path]:
    """The raw files a source's declared pattern(s) match — **before** any `--since`
    or cursor filtering. Extracted from `_scan` because the authorship pass needs the
    same file set under a *different* cursor (`authorcapture`'s docstring explains why
    the call cursor is the wrong one for it), and two globs would be two answers.

    An empty pattern sequence matches nothing, including for a file source — a
    ``--path`` with nothing declared is a loud no-op, never a directory sweep."""
    patterns = [pattern] if isinstance(pattern, str) else list(pattern)
    if not patterns:
        return []
    if src.is_dir():
        return sorted({f for p in patterns for f in src.glob(p)})
    if src.is_file():
        return [src]  # a file source (kiro's token log, an explicit --path file)
    return []  # absent location — a normal miss, recorded by the probe event


def _scan(root: Path, agent: str, src: Path, pattern, since,
          *, pol: dict | None = None, agent_cursor: dict | None = None,
          health: dict | None = None) -> list[Path]:
    """The files to ingest, honoring ``--since`` and the incremental cursor. Files whose
    (size, mtime) match the cursor are dropped — already fully ingested, nothing new to
    parse. Records observational ``skip=since-filtered`` / ``skip=cursor-unchanged`` debug
    events when files existed but were all dropped (a common "why nothing captured?" cause).
    ``agent_cursor=None`` (the standalone import-claude command) ⇒ no skip.
    Every candidate source gets a metadata-only ``probe`` event (path, exists, files
    matched) so `CAGE_DEBUG=1` answers "which locations did cage look at, and which
    missed" — the raw feed behind `cage doctor --paths`.

    ``pattern`` is one anchored glob (a ``[sources]`` entry) **or** a sequence of them
    (the root-agnostic ``path_globs`` a ``--path`` run scans with, path-globs handoff
    §5). The matched set is deduped across patterns, so two overlapping patterns can
    never hand the same file to `_ingest` twice. An **empty** sequence matches nothing,
    including for a file source — a ``--path`` with no declared patterns is a no-op the
    caller announces, never a quiet full-directory sweep."""
    raw = glob_source(src, pattern)
    patterns = [pattern] if isinstance(pattern, str) else list(pattern)
    shown = ", ".join(patterns)
    debuglog.event(root, pol=pol, event="probe", agent=agent, src=str(src),
                   pattern=shown, exists=src.exists(), files_matched=len(raw))
    if health is not None:  # capture-health gate 2: raw glob matches (pre-cursor), so a
        # steady-state agent whose files are all cursor-skipped still reads as "has data";
        # the first src per agent is kept as the representative probed path for the message.
        # The patterns ride along so the zero-match ⚠ can NAME what it looked for — a
        # "matched 0 files" that hides its glob is unanswerable (path-globs handoff §5).
        h = health.setdefault(agent, {"files": 0, "src": str(src), "pattern": shown})
        h["files"] += len(raw)
        h.setdefault("pattern", shown)
    cut = ledger.since_cutoff(since)  # reuses constants.SINCE_WINDOW_DAYS — no new literal
    if cut is None:
        files = raw
    else:
        files = [f for f in raw if _mtime_utc(f) is not None and _mtime_utc(f) >= cut]
        if raw and not files:
            debuglog.event(root, pol=pol, event="import", agent=agent, skip="since-filtered",
                           src=str(src), candidates=len(raw))
    if agent_cursor is not None and files:
        fresh = [f for f in files if _file_sig(f) != agent_cursor.get(str(f))]
        if not fresh:
            debuglog.event(root, pol=pol, event="import", agent=agent, skip="cursor-unchanged",
                           src=str(src), candidates=len(files))
        files = fresh
    return files


def _ingest(root: Path, agent: str, src: Path, files: list[Path], parse,
            *, pol: dict | None = None, seen: set | None = None,
            agent_cursor: dict | None = None, collect: list | None = None,
            import_id: str = "") -> int:
    """Parse + dedupe-append each file; returns #appended. Records a metadata-only
    import-detail event (src, #files, #parsed, #appended, #deduped) and turns the
    previously-silent per-file `except` into a recorded `debuglog.exception` — still
    fail-open (a broken transcript never aborts the scan), but the traceback survives.

    ``seen`` (the run-shared, already-known call-id set) is threaded into `append_new`
    so the 22k-row ledger is read once per run, not once per file. After a file ingests
    cleanly its (size, mtime) is written to ``agent_cursor`` so the next run skips it."""
    total = parsed = 0
    for f in files:
        try:
            rows = parse(f)
            if import_id:  # stamp the sweep's manifest FK on each row (plan §4)
                for r in rows:
                    r["import_id"] = import_id
            if not rows and f.is_file() and f.stat().st_size > 0:
                # A non-empty log parsing to 0 rows is the format-drift signature
                # (handoff §8) — recorded so "why nothing captured?" is answerable.
                debuglog.event(root, pol=pol, event="import", agent=agent,
                               skip="parsed-zero-rows", file=str(f), bytes=f.stat().st_size)
            parsed += len(rows)
            total += ledger.append_new(root, rows, seen, collect=collect)
            if agent_cursor is not None:
                sig = _file_sig(f)
                if sig is not None:
                    agent_cursor[str(f)] = sig
        except Exception as e:  # fail-open: a broken/unreadable transcript never aborts the scan
            debuglog.exception(root, "import.ingest", e, pol=pol, agent=agent, file=str(f))
            continue
    debuglog.event(root, pol=pol, event="import", agent=agent, result="ok", src=str(src),
                   files=len(files), parsed=parsed, appended=total, deduped=parsed - total)
    return total


def _lift_names(files: list[Path], names: dict | None, lift) -> None:
    """Populate the run-shared ``{session: name}`` map from the files this sweep ingests,
    keyed by the log's session id (the file stem — the same value the parser stamps as a
    row's ``session``). Parse-only and additive: the name lands only in `imports.jsonl`,
    never on a call row (plan §4). A file with no title contributes no entry — the manifest
    then falls back (claude → the cwd basename, others → honest ``""``)."""
    if names is None:
        return
    for f in files:
        nm = lift(f)
        if nm:
            names[f.stem] = nm


def _override_sources(agent: str, src: Path, pol: dict | None) -> list[tuple]:
    """THE ``--path`` / ``--project`` source list, shared by all three adapters — the one
    place a user-provided root is paired with the patterns to scan it by (path-globs
    handoff §5). No glob literal lives in an import branch any more: the patterns come
    from ``cage.toml``'s ``[sources] path_globs``, which is **root-agnostic** precisely
    because the anchored ``glob`` cannot reach a store when the root is replaced (the
    copilot ``chatSessions`` bug).

    No declared patterns ⇒ **no sources at all**, not a bare directory sweep. Directive A
    holds here too — values live in `cage.toml`, never in Python — so an unmaterialized
    project gets a loud no-op (`run` prints the fix) rather than a silent code fallback,
    which is exactly the two-places problem this key exists to close. ``surface`` is
    always ``""``: under an override the parser's own value stands, so a `chatSessions`
    file keeps its ``vscode`` stamp with nothing declared."""
    pats = paths.path_globs_for(agent, pol)
    return [(src, pats, "")] if pats else []


def missing_path_globs(args, targets, pol: dict | None) -> list[str]:
    """The loud line for a ``--path``/``--project`` run whose target agents declare no
    ``path_globs`` — the deliberate behaviour change (path-globs handoff §2). Silence
    here would look exactly like "your logs are empty", which is the failure mode this
    whole change exists to end, so the absence and its fix are named."""
    if not (getattr(args, "path", None) or getattr(args, "project", None)):
        return []
    return [f"⚠ {a}: no `path_globs` declared for {a} in cage.toml — "
            f"--path/--project scanned nothing. Run `cage setup --sync-sources` "
            f"to materialize the defaults."
            for a in targets
            if a in agents.SURFACES and not paths.path_globs_for(a, pol)]


def graphify_scan_set(args, src, pattern, files: list[Path]) -> list[Path]:
    """The files **graphify detection** walks: normally the ones this sweep ingested (so
    detection inherits the incremental cursor), but the source's **full match set** under
    `cage import --rescan-graphify`.

    Why the flag has to exist: the cursor is keyed on `(size, mtime)` and a log that has
    not changed is skipped — correct for calls, wrong for savings. A route that ships
    *after* a session was ingested can never see that session again, so every graphify run
    before the route existed is permanently invisible. That is exactly what happened to
    copilot VS Code (skipped through v0.46) and kiro (no route at all). Detection is
    idempotent by receipt id, so a rescan is safe to re-run; it re-ingests **no** call or
    credit rows, because it only ever feeds the graphify detectors."""
    if not getattr(args, "rescan_graphify", False):
        return files
    return glob_source(src, pattern)


def metrics_scan_set(args, src, pattern, files: list[Path],
                     agent_cursor: dict | None) -> tuple[list[Path], dict | None]:
    """The files the **per-agent metrics** legs parse, and the cursor they may advance:
    normally the ones this sweep ingested (inheriting the incremental cursor), but the
    source's **full match set** under `cage import --rescan-metrics`.

    Why the flag has to exist — METRICS-CURSOR-BLIND, the exact class
    `graphify_scan_set` above already documents, in a second place. The three metric
    kinds (`ledger/{claude,copilot,kiro}/`) ride the calls sweep's cursor-filtered
    `files` list, so every store file ingested **before those routes shipped**
    (2026-08-14) is skipped forever: `_scan` drops it as `cursor-unchanged` and the
    metric parsers never see it. Measured on the maintainer's machine at the
    METRICS-PRIMARY P0 gate: copilot had 102 metric rows on disk (27 CLI + 75 VS Code)
    and kiro 56, with **zero** captured — while claude captured 11 only because its
    transcripts were still being written. A backfill needs the cursor ignored exactly
    once, and ingest is idempotent by row id, so a rescan is safe to re-run.

    **Returns the cursor too, and under a rescan that cursor is `None` — this is the
    load-bearing half.** The metric ingests advance the *calls* cursor (a harmless
    no-op today, since they only ever see files the calls leg just ingested). Handed
    the full match set they would stamp it for files the calls leg has **not** ingested
    — a `--since`-filtered file most of all — marking them already-read and making
    those calls permanently invisible. A backfill of one kind must never blind another,
    so the rescan path advances nothing; row-id dedupe is the idempotency guarantee,
    not the cursor. (`graphify_scan_set` needs no such half: detection writes receipts
    and touches no cursor at all.)"""
    if not getattr(args, "rescan_metrics", False):
        return files, agent_cursor
    return glob_source(src, pattern), None


def _claude_session_filesets(files: list[Path]) -> list[list[Path]]:
    """Regroup a sweep's changed claude files into WHOLE session filesets, so a chat's
    CLAUDE-METRICS totals are never computed from a partial view (handoff §4.5, §8):

    - a subagent path (`…/<sessionId>/subagents/agent-*.jsonl`) maps to its parent main
      file `…/<sessionId>.jsonl`;
    - every OTHER file is treated as a main file directly;
    - each distinct main file expands to `[main] + sorted(<main's subagents dir>.glob(
      "agent-*.jsonl"))` — **even the unchanged members**, because the emitted row is a
      whole-chat total, not a delta;
    - a main file whose path doesn't exist (a subagent-only change, or a subagent whose
      parent transcript was never itself swept) keeps the fileset WITHOUT it — the fold
      still keys chats on each row's own `sessionId`, never on this file's presence.

    Distinct main files always land in distinct filesets — a sweep touching files from
    two different chats regroups into two filesets, never merged."""
    mains: dict[Path, None] = {}
    for f in files:
        main = (f.parent.parent.parent / (f.parent.parent.name + ".jsonl")
               if f.parent.name == "subagents" else f)
        mains.setdefault(main, None)
    filesets: list[list[Path]] = []
    for main in mains:
        sub_dir = main.parent / main.stem / "subagents"
        subs = sorted(sub_dir.glob("agent-*.jsonl")) if sub_dir.is_dir() else []
        fileset = ([main] if main.exists() else []) + subs
        if fileset:
            filesets.append(fileset)
    return filesets


def _ingest_claude_metrics(root: Path, files: list[Path], *,
                           pol: dict | None = None) -> int:
    """Regroup `files` into whole session filesets (`_claude_session_filesets`) and
    parse each into claude-metrics rows via `transcript.parse_claude_chat_metrics`,
    appending the ones not already recorded (CLAUDE-METRICS handoff §4.5). Mirrors
    `_ingest_copilot_metrics`/`_ingest_kiro_metrics`: own kind (`"claude"`), own id
    namespace (`clm_`), own seen-set rebuilt fresh from `ledger.claude_metrics_raw`
    each call — metrics rows never touch the call-id `seen` set or the call stderr
    rollup (they are not calls). Fail-open per fileset, like `_ingest`.

    **No own cursor** — this rides the calls sweep's already-cursor-filtered `files`
    list (a changed file re-triggers regrouping of its whole fileset); a second,
    independent cursor here would let a subagent-only change slip through both."""
    seen_ids = {r.get("id") for r in ledger.claude_metrics_raw(root)}
    filesets = _claude_session_filesets(files)
    total = 0
    for fileset in filesets:
        f0 = fileset[0]
        session_hint = (f0.parent.parent.name if f0.parent.name == "subagents"
                        else f0.stem)
        try:
            rows = transcript.parse_claude_chat_metrics(fileset, session_hint=session_hint)
        except Exception as e:  # fail-open: a broken/unreadable fileset never aborts the sweep
            debuglog.exception(root, "import.claude-metrics", e, pol=pol, file=str(f0))
            continue
        for r in rows:
            if r.get("id") not in seen_ids:
                if ledger.append_row(root, "claude", r):
                    seen_ids.add(r.get("id"))
                    total += 1
    debuglog.event(root, pol=pol, event="import", agent="claude", result="ok",
                   kind="claude-metrics", filesets=len(filesets), appended=total)
    return total


def import_claude(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                  agent_cursor: dict | None = None, health: dict | None = None,
                  collect: list | None = None, import_id: str = "",
                  names: dict | None = None,
                  authorship_cursor: dict | None = None) -> tuple[int, int]:
    """Meter Claude Code from the transcripts it already writes to ~/.claude/projects.

    ``authorship_cursor`` opts this sweep into the **authorship pass** (agent-vs-human
    v2 P1): the same transcripts are re-read for the text of each proposed edit, matched
    against the commits whose windows contain those edits, and one provenance row per
    (sha, agent, session) is appended. Passing ``None`` (the default, and what a
    standalone `import_claude` call does) skips it entirely — capture of *calls* is
    byte-identical either way."""
    if getattr(args, "path", None):
        sources = _override_sources("claude", Path(args.path), pol)
    elif getattr(args, "project", None):
        sources = _override_sources("claude", paths.claude_home() / "projects"
                                    / paths.claude_project_slug(Path(args.project)), pol)
    else:
        sources = [(s.path, s.glob, s.surface) for s in paths.agent_log_sources("claude", pol)]
    total_rows = total_files = 0
    # GC2 (graphify-capture): the graphify savings ids already in the ledger — the
    # deferral/idempotency backstop threaded through the whole claude sweep (built once,
    # mutated as receipts are filed). Fail-open: a read failure just means no deferral
    # this run (id-dedupe in `ledger.receipts` stays the correctness backstop).
    try:
        gfx_ids = {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}
    except Exception as e:  # noqa: BLE001 — never break capture over the savings snapshot
        debuglog.exception(root, "import.graphify-snapshot", e, pol=pol)
        gfx_ids = set()
    for src, pattern, surface in sources:
        files = _scan(root, "claude", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor, health=health)
        _lift_names(files, names, transcript.session_name_claude)
        total_rows += _ingest(root, "claude", src, files,
                              _surface_restamp(lambda f: transcript.parse_calls(
                                  f, session=f.stem, root=root, pol=pol), surface),
                              pol=pol, seen=seen, agent_cursor=agent_cursor, collect=collect, import_id=import_id)
        # CLAUDE-METRICS: the SAME `files` this sweep just scanned, into the metrics
        # kind — or the source's full match set under `--rescan-metrics`
        # (METRICS-CURSOR-BLIND; `metrics_scan_set`). Never folded into
        # `total_rows`/`total_files` below: metrics rows are not calls, and the printed
        # "imported N call(s)" summary must not count them (handoff §4.5).
        mfiles, _ = metrics_scan_set(args, src, pattern, files, agent_cursor)
        _ingest_claude_metrics(root, mfiles, pol=pol)
        _detect_graphify(root, graphify_scan_set(args, src, pattern, files),
                         gfx_ids, pol)
        # The authorship pass reads the source's FULL match set, not `files`: the call
        # cursor skips an unchanged transcript, and a session's last edits are almost
        # always committed after its transcript stops growing — so gating authorship on
        # the call cursor would mean those edits were never recorded at all
        # (`authorcapture`'s own cursor closes that). Fail-open inside `capture`.
        if authorship_cursor is not None:
            from cage import authorcapture
            authorcapture.capture(root, glob_source(src, pattern), pol=pol,
                                  cursor=authorship_cursor)
        total_files += len(files)
    return total_rows, total_files


def _detect_graphify(root: Path, files: list[Path], gfx_ids: set, pol: dict | None) -> None:
    """GC2 transcript-side graphify detection over the claude files this sweep ingested —
    files graphify savings receipts (query + report-read) for uses no shim caught. Runs
    only on claude (the GC0 verdict §3.0), over the SAME `files` `_ingest` processed, so
    it inherits the incremental cursor. Fail-open per file — a detection error never
    aborts the sweep or the import."""
    from cage import graphifytx
    for f in files:
        try:
            counts = graphifytx.detect_and_file(root, f, session=f.stem,
                                                existing_ids=gfx_ids, pol=pol)
            if counts["query"] or counts["report_read"] or counts["deferred"]:
                debuglog.event(root, pol=pol, event="graphify-tx", file=str(f),
                               **counts)
        except Exception as e:  # noqa: BLE001 — detection is best-effort, never a gate
            debuglog.exception(root, "import.graphify-tx", e, pol=pol, file=str(f))


_CHAT_SESSION_DIRS = ("chatSessions", "emptyWindowChatSessions", "transferredChatSessions")


def _is_chat_session_file(f: Path) -> bool:
    """True for a file living in any of the three chatSessions-shaped roots
    (COPILOT-METRICS handoff §4.5) — the normal per-workspace store plus the two
    globalStorage roots added alongside it (`_builtin_log_sources`'s new copilot
    tuples). Without this, a file under `emptyWindowChatSessions`/
    `transferredChatSessions` mis-dispatches to the CLI `events.jsonl` parser: neither
    sits in a directory literally named `chatSessions`, which is what `_parse_copilot_any`
    and `_copilot_name` checked before this existed. `no-workspace/chatSessions/` needs
    no entry here — its parent dir IS named `chatSessions`, already covered."""
    return f.parent.name in _CHAT_SESSION_DIRS


def _parse_copilot_any(f: Path) -> list[dict]:
    """Dispatch on the on-disk store: VS Code chat-session files (extension) parse via
    `parse_copilot_vscode_calls`; everything else is the CLI `events.jsonl` format."""
    if _is_chat_session_file(f):
        return transcript.parse_copilot_vscode_calls(f, session=f.stem)
    return transcript.parse_copilot_calls(f, session=f.parent.name)


def _parse_copilot_metrics_any(f: Path) -> list[dict]:
    """The metrics twin of `_parse_copilot_any` (COPILOT-METRICS handoff §4.5): the
    SAME dispatch, routed to the metrics parsers instead of the calls parsers."""
    if _is_chat_session_file(f):
        return transcript.parse_copilot_vscode_metrics(f, session=f.stem)
    return transcript.parse_copilot_cli_metrics(f, session=f.parent.name)


# The parser per gated-store tag (`paths.copilot_metric_sources()`'s third tuple
# element) — COPILOT-METRICS handoff §4.5. `otel` takes the whole db path, not a
# per-file match, since `_scan`'s glob for it (`"agent-traces.db"`) matches the db
# file itself.
_COPILOT_METRIC_PARSERS = {
    "sidecar": lambda f: transcript.parse_copilot_sidecar_metrics(f, session=f.stem),
    "debuglog": transcript.parse_copilot_debuglog_metrics,
    "otel": transcript.parse_copilot_otel_metrics,
}


# The parser to reuse per declared `[sources.<name>] format` (plan Phase 4). The three
# built-in import fns above inline the same callables; a custom tool routes through
# here by its declared format so no new parser is ever written for a custom source.
_PARSERS = {"claude": lambda f: transcript.parse_calls(f, session=f.stem),
            "copilot": _parse_copilot_any,
            "kiro": lambda f: transcript.parse_kiro_calls(f)}


def _surface_restamp(parse, surface: str):
    """Wrap a parser so each parsed row's ``surface`` is restamped to the source's
    declared value — the same technique as the custom-tool ``agent`` restamp below.
    Called only when a `[sources.<x>] surface = …` is set; an empty surface returns
    the parser unwrapped, so an undeclared source is byte-identical to before."""
    if not surface:
        return parse
    return lambda f, _p=parse: [{**r, "surface": surface} for r in _p(f)]


def _ingest_credits(root: Path, name: str, src: Path, files: list[Path], *,
                    pol: dict | None = None, agent_cursor: dict | None = None,
                    graphify_files: list[Path] | None = None,
                    metrics_files: list[Path] | None = None) -> int:
    """Drive the Kiro-CLI store's two legs — metrics and graphify — and advance the cursor.

    **The top-level `credits-<month>.jsonl` shard is NO LONGER WRITTEN (P2, v0.51).** It
    was a duplicate: `ledger/kiro/`'s `cli-conv` rows already carry these credits, from the
    same store, through the same shared reader (`_kiro_cli_conversations`), under the same
    whitelist. `ledger.credits` now reads `cli-conv` — re-applying the credits skip rule
    on the way — **and every existing `credits-*.jsonl` shard, forever**. Nothing on disk
    moved, nothing was rewritten, and `transcript.parse_kiro_cli_credits` is kept as the
    reference implementation of the semantics that projection preserves.

    The name and the return value are unchanged so every caller and the stderr rollup stay
    put; it now returns **0 credits appended**, always, because this leg appends no credits
    row. That is the honest count, not a placeholder.

    **Scoped by cwd** (ADR 0006 *Scope*): the store keys every conversation by the
    directory it ran in, so a sweep into a project ledger reads only that project's tree
    and stamps `project` on the row. Reading unscoped — what this did through v0.35 — is
    what pulled every conversation on the machine into every ledger. The machine ledger
    still reads all of them; `paths.kiro_cli_workspace` makes that call once."""
    workspace = paths.kiro_cli_workspace(root)
    debuglog.event(root, pol=pol, event="import", agent=name, kind="credits",
                   scoped=bool(workspace), writer="retired-p2")
    total = 0
    # The cursor advance lived inside the credits loop that is now gone. It is NOT
    # incidental: without it a store is re-read in full on every sweep. Kept here, and
    # still per-file + fail-open, so an unreadable file never advances past itself.
    for f in files:
        try:
            if agent_cursor is not None:
                sig = _file_sig(f)
                if sig is not None:
                    agent_cursor[str(f)] = sig
        except Exception as e:  # fail-open: an unreadable DB never aborts the sweep
            debuglog.exception(root, "import.credits", e, pol=pol, agent=name, file=str(f))
    # KIRO-METRICS: the SAME `files`/`workspace` this leg just resolved, into the
    # metrics kind — ADR 0006 scoping inherited rather than re-decided. Under
    # `--rescan-metrics` the caller passes the store's full match set as
    # ``metrics_files`` (METRICS-CURSOR-BLIND; the caller owns the resolution because
    # this function never sees `args`, exactly as ``graphify_files`` above). A rescan
    # set means the calls cursor is **not** advanced from here — see `metrics_scan_set`.
    # Never folded into `total` above: metrics rows are not credits (handoff §4.5).
    _ingest_kiro_metrics(root, files if metrics_files is None else metrics_files,
                        lambda f: transcript.parse_kiro_cli_metrics(f, workspace=workspace),
                        src=src, pol=pol,
                        agent_cursor=agent_cursor if metrics_files is None else None)
    _detect_graphify_kiro_cli(root, files if graphify_files is None else graphify_files,
                              workspace, pol)
    debuglog.event(root, pol=pol, event="import", agent=name, result="ok", src=str(src),
                   files=len(files), kind="credits", appended=total)
    return total


def _ingest_copilot_metrics(root: Path, files: list[Path], parse, *, src: Path,
                            pol: dict | None = None,
                            agent_cursor: dict | None = None) -> int:
    """Parse `files` into copilot-metrics rows via `parse` (dispatched per file by the
    caller — chat vs cli metrics in the always-on leg, one of the three gated-store
    parsers in the gated leg) and append the ones not already recorded
    (COPILOT-METRICS handoff §4.5). Mirrors `_ingest_credits`: own kind (`"copilot"`),
    own id namespace (`cm_`), own seen-set rebuilt fresh from `ledger.copilot_metrics_raw`
    each call — metrics rows never touch the call-id `seen` set or the call stderr
    rollup (they are not calls). Fail-open per file, like `_ingest`. Reuses the SAME
    `files` list the caller already scanned — no second scan. `agent_cursor`, when
    given, advances the same way `_ingest`'s does (cursor keys are per file path, so
    sharing one dict with the calls leg or across the three gated stores never
    collides)."""
    seen_ids = {r.get("id") for r in ledger.copilot_metrics_raw(root)}
    total = parsed = 0
    for f in files:
        try:
            rows = parse(f)
            parsed += len(rows)
            for r in rows:
                if r.get("id") not in seen_ids:
                    if ledger.append_row(root, "copilot", r):
                        seen_ids.add(r.get("id"))
                        total += 1
            if agent_cursor is not None:
                sig = _file_sig(f)
                if sig is not None:
                    agent_cursor[str(f)] = sig
        except Exception as e:  # fail-open: a broken/unreadable store never aborts the sweep
            debuglog.exception(root, "import.copilot-metrics", e, pol=pol, file=str(f))
    debuglog.event(root, pol=pol, event="import", agent="copilot", result="ok",
                   src=str(src), kind="copilot-metrics", files=len(files),
                   parsed=parsed, appended=total)
    return total


def _ingest_kiro_metrics(root: Path, files: list[Path], parse, *, src: Path,
                         pol: dict | None = None,
                         agent_cursor: dict | None = None) -> int:
    """Parse `files` into kiro-metrics rows via `parse` (the CLI conv/turn parser in the
    always-on CLI leg, the IDE devdata parser in the IDE leg) and append the ones not
    already recorded (KIRO-METRICS handoff §4.5). Mirrors `_ingest_copilot_metrics`
    exactly: own kind (`"kiro"`), own id namespace (`km_`), own seen-set rebuilt fresh
    from `ledger.kiro_metrics_raw` each call — metrics rows never touch the call-id
    `seen` set, the credits seen-set, or either rollup (they are neither calls nor
    credits). Fail-open per file, like `_ingest`/`_ingest_credits`. Reuses the SAME
    `files` list the caller already scanned — no second scan."""
    seen_ids = {r.get("id") for r in ledger.kiro_metrics_raw(root)}
    total = parsed = 0
    for f in files:
        try:
            rows = parse(f)
            parsed += len(rows)
            for r in rows:
                if r.get("id") not in seen_ids:
                    if ledger.append_row(root, "kiro", r):
                        seen_ids.add(r.get("id"))
                        total += 1
            if agent_cursor is not None:
                sig = _file_sig(f)
                if sig is not None:
                    agent_cursor[str(f)] = sig
        except Exception as e:  # fail-open: a broken/unreadable store never aborts the sweep
            debuglog.exception(root, "import.kiro-metrics", e, pol=pol, file=str(f))
    debuglog.event(root, pol=pol, event="import", agent="kiro", result="ok",
                   src=str(src), kind="kiro-metrics", files=len(files),
                   parsed=parsed, appended=total)
    return total


def _detect_graphify_kiro_cli(root: Path, files: list[Path], workspace: str,
                              pol: dict | None) -> None:
    """GFX-COV/P2: graphify detection over the kiro-CLI store this sweep just read.

    Hung off the credits leg deliberately — that leg has already resolved the one thing
    the route must not decide for itself: **which sink and which tree**. Receipts land in
    the same `root` the credit rows did, scoped by the same ``workspace``, so a project
    sweep and a machine sweep each keep their own rows (ADR 0006) with no second resolver.
    Fail-open per file; the savings-id snapshot is rebuilt here for the same reason the
    claude and copilot legs rebuild theirs."""
    from cage import graphifytx
    try:
        gfx_ids = {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}
    except Exception as e:  # noqa: BLE001 — never break capture over the savings snapshot
        debuglog.exception(root, "import.graphify-snapshot", e, pol=pol)
        gfx_ids = set()
    for f in files:
        try:
            counts = graphifytx.detect_and_file_kiro_cli(root, f, workspace=workspace,
                                                         existing_ids=gfx_ids, pol=pol)
            if counts["query"] or counts["report_read"] or counts["deferred"]:
                debuglog.event(root, pol=pol, event="graphify-tx", agent="kiro",
                               surface="cli", file=str(f), **counts)
        except Exception as e:  # noqa: BLE001 — detection is best-effort, never a gate
            debuglog.exception(root, "import.graphify-tx.kiro-cli", e, pol=pol, file=str(f))


def import_custom_tools(root: Path, args, *, pol: dict | None = None,
                        seen: set | None = None, cursors: dict | None = None,
                        collect: list | None = None, import_id: str = "") -> list[str]:
    """Meter every `[sources.<name>]` custom tool (a name that is not one of the four
    agents, plan Phase 4). Each reuses its declared-format parser and stamps
    ``agent = <name>`` on the rows, so the per-agent views split it out naturally.
    Same `_scan`/`_ingest`/cursor/dedupe/fail-open path as the built-ins; a custom
    tool gets its own cursor bucket (keyed on the resolved file path, like every
    other source). Returns one summary line per tool that imported anything."""
    by_tool: dict[str, list] = {}
    for s in paths.custom_tool_sources(pol):
        by_tool.setdefault(s.agent, []).append(s)
    out: list[str] = []
    for name in sorted(by_tool):
        n = m = 0
        agent_cursor = cursors.setdefault(name, {}) if cursors is not None else None
        credit_rows = 0
        for s in by_tool[name]:
            files = _scan(root, name, s.path, s.glob, getattr(args, "since", None),
                          pol=pol, agent_cursor=agent_cursor)
            if s.fmt == "kiro-cli":  # SQLite credits store — a distinct row kind, not calls
                mfiles, _ = metrics_scan_set(args, s.path, s.glob, files, agent_cursor)
                credit_rows += _ingest_credits(
                    root, name, s.path, files, pol=pol, agent_cursor=agent_cursor,
                    graphify_files=graphify_scan_set(args, s.path, s.glob, files),
                    metrics_files=None if mfiles is files else mfiles)
                m += len(files)
                continue
            base_parse = _PARSERS[s.fmt]
            # Reuse the declared format's parser, then restamp `agent` to the tool name
            # (the parser stamps its own format's agent, e.g. "claude-code") and, when
            # the source declares one, `surface` (same technique, `_surface_restamp`).
            parse = lambda f, _p=base_parse, _n=name, _sf=s.surface: [
                {**r, "agent": _n, **({"surface": _sf} if _sf else {})} for r in _p(f)]
            n += _ingest(root, name, s.path, files, parse,
                         pol=pol, seen=seen, agent_cursor=agent_cursor, collect=collect, import_id=import_id)
            m += len(files)
        if by_tool[name][0].fmt == "kiro-cli":
            if m:
                out.append(f"✔ {name} (kiro-cli): recorded {credit_rows} credit row(s) "
                           f"from {m} store(s) — usage is credits, not tokens (estimated).")
        elif m:
            out.append(f"✔ {name} (custom, format={by_tool[name][0].fmt}): "
                       f"imported {n} call(s) from {m} file(s).")
    return out


def _copilot_name(f: Path) -> str:
    """A copilot file's session name: the VS Code chat title for a chatSessions-shaped
    file (any of `_CHAT_SESSION_DIRS`), ``""`` for a CLI `events.jsonl` (which carries no
    title — honest empty, plan §4)."""
    if _is_chat_session_file(f):
        return transcript.session_name_copilot_vscode(f)
    return ""


def import_copilot(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                   agent_cursor: dict | None = None, health: dict | None = None,
                   collect: list | None = None, import_id: str = "",
                   names: dict | None = None) -> tuple[int, int]:
    """Meter Copilot from both stores it actually writes:

    - CLI: `~/.copilot/session-state/*/events.jsonl` (usage in `session.shutdown`;
      the session dir name is the session id);
    - VS Code extension: `<vscode-user>/workspaceStorage/*/chatSessions/*.jsonl` —
      the extension's own transcripts dir carries no usage event, so the per-request
      counts come from VS Code's chat-session store (plan §3.7; `CAGE_VSCODE_USER`
      overrides the user dir for tests)."""
    sources = (_override_sources("copilot", Path(args.path), pol)
               if getattr(args, "path", None)
               else [(s.path, s.glob, s.surface) for s in paths.agent_log_sources("copilot", pol)])
    total_rows = total_files = 0
    # F1: the graphify savings-id snapshot for the copilot sweep's cross-route deferral —
    # built once, mutated as receipts file (same pattern as the claude sweep). Fail-open;
    # id-dedupe in `ledger.receipts` stays the correctness backstop.
    try:
        gfx_ids = {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}
    except Exception as e:  # noqa: BLE001 — never break capture over the savings snapshot
        debuglog.exception(root, "import.graphify-snapshot", e, pol=pol)
        gfx_ids = set()
    for src, pattern, surface in sources:
        files = _scan(root, "copilot", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor, health=health)
        _lift_names(files, names, _copilot_name)
        total_rows += _ingest(root, "copilot", src, files,
                              _surface_restamp(_parse_copilot_any, surface),
                              pol=pol, seen=seen, agent_cursor=agent_cursor, collect=collect, import_id=import_id)
        # COPILOT-METRICS: the SAME `files` this sweep just scanned, into the metrics
        # kind — or the source's full match set under `--rescan-metrics`
        # (METRICS-CURSOR-BLIND; `metrics_scan_set`). Never folded into
        # `total_rows`/`total_files` below: metrics rows are not calls, and the printed
        # "imported N call(s)" summary must not count them (handoff §4.5).
        mfiles, mcur = metrics_scan_set(args, src, pattern, files, agent_cursor)
        _ingest_copilot_metrics(root, mfiles, _parse_copilot_metrics_any, src=src,
                                pol=pol, agent_cursor=mcur)
        _detect_graphify_copilot(root, graphify_scan_set(args, src, pattern, files),
                                 gfx_ids, pol)
        total_files += len(files)
    # The three gated-store legs (COPILOT-METRICS handoff §4.5, §4.2): opt-in,
    # per-model-call stores that feed no calls parser — metrics only, own scan, own
    # cursor bucket (cursor keys are per file path, so sharing `agent_cursor` with the
    # always-on leg above never collides).
    for gpath, gglob, tag in paths.copilot_metric_sources():
        gfiles = _scan(root, "copilot", gpath, gglob, getattr(args, "since", None),
                       pol=pol, agent_cursor=agent_cursor, health=health)
        gparse = _COPILOT_METRIC_PARSERS[tag]
        gfiles, gcur = metrics_scan_set(args, gpath, gglob, gfiles, agent_cursor)
        _ingest_copilot_metrics(root, gfiles, gparse, src=gpath, pol=pol,
                                agent_cursor=gcur)
    return total_rows, total_files


def _detect_graphify_copilot(root: Path, files: list[Path], gfx_ids: set,
                             pol: dict | None) -> None:
    """F1 + GFX-COV/P1: GC2 transcript-side graphify detection over **both** copilot
    stores, reusing the claude counterfactual/id/deferral in either case.

    Dispatch is on the on-disk store, the same split `_parse_copilot_any` makes: a
    `chatSessions/` file is the VS Code extension's patch stream, everything else is the
    CLI `events.jsonl`. The VS Code store was skipped outright through v0.46 on the F2
    assumption that it carried no tool result — **the 2026-08-07 field probe disproved
    that** (`run_in_terminal` persists the command, the cwd and the output; see
    `graphifytx.detect_and_file_copilot_vscode`), so it now files like every other route.
    Fail-open per file."""
    from cage import graphifytx
    for f in files:
        vscode = f.parent.name == "chatSessions"
        detect = (graphifytx.detect_and_file_copilot_vscode if vscode
                  else graphifytx.detect_and_file_copilot)
        try:
            counts = detect(root, f, session=f.stem if vscode else f.parent.name,
                            existing_ids=gfx_ids, pol=pol)
            if counts["query"] or counts["report_read"] or counts["deferred"]:
                debuglog.event(root, pol=pol, event="graphify-tx", agent="copilot",
                               surface="vscode" if vscode else "cli", file=str(f), **counts)
        except Exception as e:  # noqa: BLE001 — detection is best-effort, never a gate
            debuglog.exception(root, "import.graphify-tx.copilot", e, pol=pol, file=str(f))


def _log_kiro_src(root: Path, src: Path, *, pol: dict | None = None) -> None:
    """F3 visibility (work/regression/2026-07-22-capture-report.md): one debug event
    per import run recording the resolved kiro `src`'s raw state — existed?, byte
    size, rows parsed, tokens summed. Read **unconditionally**, independent of the
    incremental cursor, so "found but empty/thin" stays visible on every run even
    when the cursor would otherwise skip an unchanged file — the failure mode F3
    named ("no logging to distinguish 'empty' from 'never checked'"). Kiro's log is
    a single small file by design (coarse capture), so a second parse pass here is
    cheap; the same approach does not apply to claude/copilot's larger transcript
    sets. Counts/paths only — never token content (PII guard). Fail-open."""
    try:
        exists = src.exists()
        size = src.stat().st_size if exists else 0
        rows = transcript.parse_kiro_calls(src) if exists else []
        tin = sum(r.get("tokens_in", 0) for r in rows)
        tout = sum(r.get("tokens_out", 0) for r in rows)
        debuglog.event(root, pol=pol, event="kiro-src", src=str(src), exists=exists,
                       bytes=size, rows_parsed=len(rows), tokens_in=tin, tokens_out=tout)
    except Exception as e:  # fail-open: this visibility log must never break import
        debuglog.exception(root, "import.kiro-src", e, pol=pol)


def import_kiro(root: Path, args, *, pol: dict | None = None, seen: set | None = None,
                agent_cursor: dict | None = None, health: dict | None = None,
                collect: list | None = None, import_id: str = "",
                names: dict | None = None) -> tuple[int, int]:
    """Meter Kiro from its append-only usage log (kiro.kiroagent/dev_data/
    tokens_generated.jsonl) — a single file, not a glob. Best-effort and idempotent.

    ``names`` is accepted for a uniform adapter signature and ignored: Kiro's log carries
    no session title, so its manifest name stays ``""`` (honest empty, plan §4)."""
    sources = (_override_sources("kiro", Path(args.path), pol)
               if getattr(args, "path", None)
               else [(s.path, s.glob, s.surface) for s in paths.agent_log_sources("kiro", pol)])
    total_rows = total_files = 0
    for src, pattern, surface in sources:
        _log_kiro_src(root, src, pol=pol)
        files = _scan(root, "kiro", src, pattern, getattr(args, "since", None), pol=pol,
                      agent_cursor=agent_cursor, health=health)
        total_rows += _ingest(root, "kiro", src, files,
                              _surface_restamp(lambda f: transcript.parse_kiro_calls(f), surface),
                              pol=pol, seen=seen, agent_cursor=agent_cursor, collect=collect, import_id=import_id)
        total_files += len(files)
    # KIRO-METRICS IDE leg (handoff §4.5): a single fixed file, not a glob — resolved
    # directly rather than through `_scan`/`agent_log_sources` (`paths.kiro_devdata_db`
    # is deliberately not a registered source; see its docstring). `import_kiro` already
    # runs against the ROUTED SINK as `root` when kiro routes away (`_kiro_leg` calls
    # `run_agent(sink, "kiro", ...)`, ADR 0006), so these rows land machine-side with
    # zero new routing code — never folded into `total_rows`/`total_files` above:
    # metrics rows are not calls.
    devdata = paths.kiro_devdata_db()
    if devdata.exists():
        _ingest_kiro_metrics(root, [devdata], transcript.parse_kiro_ide_metrics,
                            src=devdata, pol=pol, agent_cursor=agent_cursor)
    return total_rows, total_files


_ADAPTERS = {"claude": import_claude, "copilot": import_copilot, "kiro": import_kiro}


def proxy_line(agent: str) -> str:
    """What cage can say about an agent that writes no usage transcript.

    It used to name a remedy — `cage data meter -- <cmd>`, the metering proxy. SURFACE-CUT
    (v0.50) deleted that command **and** `proxy.py`/`metercmd.py` with it, so the line went
    on prescribing a fix that could not be run: the F1 class in prose, printed on stdout.
    A stated absence is worth more than a false remedy, so this now says what is true."""
    return (f"· {agent}: no on-disk usage log — cage cannot capture this surface "
            "(the metering proxy that was the fallback went in v0.50)")


def run_agent(root: Path, agent: str, args, *, pol: dict | None = None,
              seen: set | None = None, agent_cursor: dict | None = None,
              health: dict | None = None, collect: list | None = None,
              import_id: str = "", names: dict | None = None,
              sink_note: str = "", authorship_cursor: dict | None = None) -> str:
    """Import one agent into ``root``. ``sink_note`` replaces the summary line's trailing
    period when the rows landed in a ledger **other** than the sweep's own (the routed
    kiro leg, ADR 0006) — the summary must never read as "into this project" for rows
    that went elsewhere. Empty (the default) keeps the line byte-identical.

    ``authorship_cursor`` reaches **claude only**, and deliberately isn't accepted-and-
    ignored by the other two the way ``names`` is: copilot and kiro persist no edit
    payload at all (`authorcapture.COVERAGE_GAPS`), so a parameter they could never act
    on would read as a capability gap rather than a structural one."""
    if agent in _ADAPTERS:
        extra = ({"authorship_cursor": authorship_cursor}
                 if agent == "claude" and authorship_cursor is not None else {})
        n, m = _ADAPTERS[agent](root, args, pol=pol, seen=seen, agent_cursor=agent_cursor,
                                health=health, collect=collect, import_id=import_id,
                                names=names, **extra)
        # Record rows appended *this run* so `_record_health` can mark an agent captured
        # on its FIRST-ever import: the run-shared `captured` set is snapshotted from the
        # ledger *before* these appends, so a brand-new surface isn't in it yet (the F2
        # first-capture false-negative). `imported > 0` closes that off-by-one.
        if health is not None:
            health.setdefault(agent, {"files": 0, "src": ""})["imported"] = n
        return f"✔ {agent}: imported {n} call(s) from {m} file(s){sink_note or '.'}"
    debuglog.event(root, pol=pol, event="import", agent=agent, result="proxy",
                   note="no on-disk usage log")
    return proxy_line(agent)


def _import_rollup(collected: list[dict], pol: dict, deduped: int) -> list[str]:
    """The loud per-agent×surface token rollup (plan §2.2), built from the rows this run
    actually appended (``collected`` — no second ledger read). Tokens only since
    USAGE-ONLY (ADR 0011): there is no price table left, so there is no priced/unpriced
    distinction to report. Returns [] when nothing was appended (an empty import stays
    quiet)."""
    if not collected:
        return []
    # bucket key: (surface-name display, surface) — e.g. ("claude", ""), ("copilot", "cli")
    buckets: dict[tuple[str, str], dict] = {}
    for r in collected:
        a = agents.row_surface(r.get("agent")) or r.get("agent") or "?"
        surf = r.get("surface", "")
        b = buckets.setdefault((a, surf), {"calls": 0, "tokens_in": 0, "cached": 0,
                                           "tokens_out": 0})
        b["calls"] += 1
        b["tokens_in"] += int(r.get("tokens_in", 0))
        b["cached"] += int(r.get("cached_in", 0))
        b["tokens_out"] += int(r.get("tokens_out", 0))

    def order(k):
        a = k[0]
        return (agents.SURFACES.index(a) if a in agents.SURFACES else len(agents.SURFACES), k[1])

    hdr = f"  {'agent':<8} {'surface':<7} {'calls':>6} {'tokens_in':>12} " \
          f"{'cached':>11} {'tokens_out':>11}"
    lines = ["", hdr]
    tot = {"calls": 0, "tokens_in": 0, "cached": 0, "tokens_out": 0}
    for k in sorted(buckets, key=order):
        b = buckets[k]
        surf = k[1] or "—"
        lines.append(f"  {k[0]:<8} {surf:<7} {b['calls']:>6} {b['tokens_in']:>12,} "
                     f"{b['cached']:>11,} {b['tokens_out']:>11,}")
        for f in ("calls", "tokens_in", "cached", "tokens_out"):
            tot[f] += b[f]
    lines.append("  " + "─" * 55)
    lines.append(f"  {'total':<8} {'':<7} {tot['calls']:>6} {tot['tokens_in']:>12,} "
                 f"{tot['cached']:>11,} {tot['tokens_out']:>11,}")
    if deduped:
        lines.append(f"  ({deduped} already-recorded call(s) deduped)")
    return lines


def _write_manifest(root: Path, import_id: str, collected: list[dict], health: dict,
                    pol: dict, ts: str, names: dict | None = None) -> None:
    """Emit one `imports.jsonl` manifest row per (agent, surface, session) this sweep
    captured rows from (plan §4), built from the run's appended rows (`collected`), the
    per-agent probed source (`health`), and the lifted `{session: name}` map (`names`).
    Each row gets a cage-minted `session_uid` and the best-available `session_name` —
    the lifted title (claude `summary` / copilot `customTitle`), else the claude cwd
    basename (`project`), else `""` (honest empty for copilot CLI / kiro). Counts only —
    the name is the sole prose, deliberate for this local audit file (plan §7) and never
    on a call row. Fail-open: a manifest error never breaks the import."""
    if not collected:
        return
    try:
        from cage import manifest
        machine_id = ""
        try:
            from cage import machine
            machine_id = machine.machine_id(root) or ""
        except Exception:  # noqa: BLE001 — machine id is additive
            machine_id = ""
        names = names or {}
        buckets: dict[tuple[str, str, str], dict] = {}
        for r in collected:
            a = agents.row_surface(r.get("agent")) or r.get("agent") or "?"
            key = (a, r.get("surface", ""), r.get("session", ""))
            b = buckets.setdefault(key, {"rows": 0, "tokens_in": 0, "tokens_out": 0,
                                         "cached": 0, "project": ""})
            b["rows"] += 1
            b["tokens_in"] += int(r.get("tokens_in", 0))
            b["tokens_out"] += int(r.get("tokens_out", 0))
            b["cached"] += int(r.get("cached_in", 0))
            if not b["project"] and r.get("project"):
                b["project"] = r.get("project")  # claude cwd basename — the name fallback
        for (a, surf, session), b in buckets.items():
            info = health.get(a, {})
            # lifted title → claude cwd basename → "" (copilot CLI / kiro carry no title).
            name = names.get(session) or b["project"]
            manifest.record_import(
                root, import_id=import_id, agent=a, surface=surf, session=session,
                session_uid=manifest.new_session_uid(),
                source_path=_tilde(info.get("src", "")),
                files_scanned=int(info.get("files", 0)),
                rows_appended=b["rows"], tokens_in=b["tokens_in"], tokens_out=b["tokens_out"],
                cached_in=b["cached"], ts=ts, session_name=name, machine=machine_id)
    except Exception as e:  # noqa: BLE001 — the manifest is an audit trail, never a gate
        debuglog.exception(root, "import.manifest", e, pol=pol)


def _kiro_leg(root: Path, sink: Path, args, pol: dict) -> list[str]:
    """The **routed kiro-IDE leg** (ADR 0006): capture kiro into ``sink`` (the machine
    ledger) while the rest of the sweep captures into ``root``.

    `run` is built on "one active sink per run — never a double-write", and this
    deliberately breaks that for one agent. It is a *contained* leg, not a rewrite: every
    per-root object `run` builds is rebuilt here against ``sink`` — its own `seen` set (or
    kiro would dedupe against the wrong ledger and re-append every run), its own cursors
    (the high-water skip must be relative to the sink), its own lock, health, capture-log
    breadcrumb, manifest and `import_id`. Nothing crosses between the legs, so the sweep's
    own counts can never include a row that landed here.

    **Locking.** The leg's lock is taken and released entirely inside this function,
    *before* `run` takes the project's — no process ever holds two import locks, so the
    hold-and-wait edge a deadlock needs never exists (two projects importing at once
    simply serialize on the machine ledger). The same-process double-lock case is excluded
    upstream: when the two ledger dirs coincide, `paths.kiro_routed` returns ``None`` and
    there is no second leg at all.

    **Which policy governs what.** Sources come from ``pol`` (the sweep's own config) —
    routing changes where rows *land*, never which file cage *reads*. The sink's own
    policy governs the sink's economics: its capture switch and its prices (the manifest's
    recorded cost). The capture switches **compose as AND** — the most restrictive wins,
    the only composition that honours both stated intents: a project that paused metering
    meant "not for this work", and a machine ledger that paused it meant "not to my
    machine ledger", and neither may be overridden by the other.

    Two things `run` does that this leg deliberately does **not**: it never writes the
    sink's ``_last_import`` (a kiro-only leg is not a full sweep — claiming one would both
    lie to `doctor` and throttle a later global capture-on-read out of sweeping claude/
    copilot), and it never runs cleanup there (the sink gets that when it is the active
    sink). Fail-open throughout, like every other capture path."""
    foot = paths.Footprint(sink)
    gpol = _load_policy(sink)
    on_here, on_sink = policy.capture_enabled(pol), policy.capture_enabled(gpol)
    # One routing event in the SWEEP's debug log (not just the sink's): the leg's own
    # `_scan`/`_ingest` traces land in `sink`, so without this a `CAGE_DEBUG=1 cage import`
    # run from a project would show kiro simply vanishing — the exact silent-routing
    # failure this design otherwise fixes.
    debuglog.event(root, pol=pol, event="import", agent="kiro", route="sink",
                   sink=str(foot.base), capture_here=on_here, capture_at_sink=on_sink)
    where = _tilde(str(foot.base))
    if not on_sink:
        debuglog.event(root, pol=pol, event="import", agent="kiro", route="sink",
                       skip="capture-disabled-at-sink", sink=str(foot.base))
        return [f"· kiro → {where}: capture is disabled at the machine ledger "
                f"([capture] enabled=false / CAGE_CAPTURE=0) — not imported"]
    with _import_lock(foot, pol):
        cursors = _load_cursors(foot)
        all_rows = ledger.calls(sink)
        seen = {c.get("id") for c in all_rows}
        captured = {agents.row_surface(c.get("agent")) for c in all_rows}
        health: dict = {}
        collected: list[dict] = []
        from cage import manifest
        # Its own import_id: each ledger's manifest must be internally consistent, and one
        # id spanning two ledgers would claim the two row sets were one.
        import_id = manifest.new_import_id()
        note = (f" → {where} (machine ledger; kiro's log carries no project "
                f"— `cage query kiro-routing`).")
        line = run_agent(sink, "kiro", args, pol=pol, seen=seen,
                         agent_cursor=cursors.setdefault("kiro", {}), health=health,
                         collect=collected, import_id=import_id, sink_note=note)
        _write_manifest(sink, import_id, collected, health, gpol, _now_iso())
        # `pol`, not `gpol`: "is kiro a configured source?" is a question about the sweep's
        # own registry — the one this leg actually read from.
        _record_health(sink, cursors, health, captured, ("kiro",), pol)
        _record_capture_log(sink, health, all_rows, ("kiro",))
        _save_cursors(foot, cursors)  # NB: `_last_import` deliberately untouched
    return [line]


def _drop_routed_kiro_state(cursors: dict) -> None:
    """Drop the sweep-root cursor/health entries kiro leaves behind once its rows route to
    the machine ledger (ADR 0006). Both would otherwise **lie**: a stale ``_health["kiro"]``
    re-fires report/doctor's "installed but capturing nothing" ⚠ forever (kiro is capturing
    fine — elsewhere), and a stale file-signature high-water mark records a skip against a
    sink that no longer receives the rows. Idempotent; the read side explains kiro's
    absence in its place (`report.kiro_routed_line`)."""
    cursors.pop("kiro", None)
    hb = cursors.get("_health")
    if isinstance(hb, dict):
        hb.pop("kiro", None)


def _load_policy(root: Path) -> dict:
    """Load policy fail-open: a malformed `policy.toml` (e.g. a duplicate `[debug]` table
    that makes `tomllib` raise) must degrade to the bundled default + a recorded debug
    event, never traceback out of the capture path (plan §3.7)."""
    try:
        return policy.load(paths.Footprint(root).policy)
    except Exception as e:  # fail-open: a broken project policy never aborts capture
        debuglog.exception(root, "import.policy", e)
        return {}


def _metrics_row_count(root: Path, pol: dict | None = None) -> dict[str, int]:
    """Row counts of the three per-agent metric kinds in **this** ledger — the before/after
    probe behind `--rescan-metrics`'s summary line. Counts only, never content; read-only.
    Fail-open per kind (a missing or truncated shard counts 0 rather than aborting the
    sweep), traced under ``CAGE_DEBUG`` like every other swallow site here."""
    readers = {"claude": ledger.claude_metrics_raw,
               "copilot": ledger.copilot_metrics_raw,
               "kiro": ledger.kiro_metrics_raw}
    out: dict[str, int] = {}
    for kind, read in readers.items():
        try:
            out[kind] = len(read(root))
        except Exception as e:  # fail-open: the summary probe never breaks capture
            debuglog.exception(root, "import.metrics-count", e, pol=pol, kind=kind)
            out[kind] = 0
    return out


def _rescan_metrics_line(before: dict[str, int], after: dict[str, int]) -> list[str]:
    """The one line a `--rescan-metrics` run prints: what the backfill actually added,
    per kind, in **this** ledger.

    Stated even when the answer is zero — the whole reason the flag exists is that a
    silently-skipped store is indistinguishable from an empty one (METRICS-CURSOR-BLIND),
    so a rescan that finds nothing must SAY it found nothing rather than look like a
    no-op that ran. It never claims a row that landed in another sink: kiro's routed IDE
    leg completes before this sweep's lock and reports itself (ADR 0006), exactly as the
    call rollup does."""
    added = {k: after.get(k, 0) - before.get(k, 0) for k in sorted(after)}
    total = sum(added.values())
    per = " · ".join(f"{k} +{n:,}" for k, n in added.items())
    tail = (f"recorded {total:,} new metric row(s) — {per}" if total
            else f"no new metric rows — every matched store was already recorded ({per})")
    return [f"✔ rescan-metrics: {tail}"]


def run(root: Path, agent: str, args) -> list[str]:
    """Dispatch to one agent or, for ``all`` (the default), every surface in order.

    Capture is global by default (plan §3.7): ``root`` is the resolved active sink
    (``--ledger``/``CAGE_BASE`` → project ``.cage/`` → global ``~/.cage``), so an import
    fired anywhere — including a user-level Copilot hook in a repo with no ``.cage/`` —
    lands in the one resolved ledger and never scatters a stray local footprint.

    **One exception, by decision:** kiro's *IDE* rows are a machine fact, not a project
    fact, so they route to the machine ledger ([ADR 0006](work/archive/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md))
    — the one place this sweep writes two ledgers. That leg is fully contained in
    `_kiro_leg` (own lock, `seen`, cursors, health, manifest), runs to completion before
    this function's own lock is taken, and its counts never enter this sweep's rollup or
    manifest: a summary line here can never claim a row that landed elsewhere. Everything
    below is otherwise per-``root`` exactly as before. Honors the
    consumer's capture switch (`[capture] enabled` / `CAGE_CAPTURE`): when off, hooks still
    fire but this no-ops, pausing metering without unwiring anything. The ledger ``seen``
    set and the per-agent cursors are built once and shared across every agent (one ledger
    read per run, unchanged files skipped). Fail-open on a malformed policy."""
    pol = _load_policy(root)
    debuglog.heartbeat(root, agent, "import", str(root), pol=pol)
    debuglog.event(root, pol=pol, event="import", agent=agent, resolved_root=str(root),
                   capture_enabled=policy.capture_enabled(pol))
    if not policy.capture_enabled(pol):
        debuglog.event(root, pol=pol, event="import", agent=agent, skip="capture-disabled",
                       resolved_root=str(root))
        return ["· capture disabled ([capture] enabled=false or CAGE_CAPTURE=0) — import skipped"]
    targets = agents.SURFACES if agent == "all" else (agent,)
    foot = paths.Footprint(root)
    # Serialize the read-check-append section: two sweeps racing here (two hooks, or a
    # hook + a manual import) must not both build `seen` before either commits, or the
    # same turn lands twice. Fail-open — an untakeable lock just falls back to the
    # id-dedupe backstop (see `_import_lock`).
    # Fail-open: a malformed `[sources]` entry is a debug-logged skip, never an error
    # (plan Phase 4). Doctor --paths / `cage query sources` surface these loudly.
    resolved = paths.resolve_log_sources(pol)
    for problem in resolved.problems:
        debuglog.event(root, pol=pol, event="import", agent=agent,
                       skip="bad-source", detail=problem)
    # Directive A (capture-precision §3.6): sources come only from `cage.toml [sources]`.
    # No `[sources]` ⇒ cage captures NOTHING — say so loudly (silence here looks exactly
    # like broken capture). Skipped for an explicit `--path`/`--project` (self-sourcing).
    nosrc: list[str] = []
    if (not resolved.sources and not getattr(args, "path", None)
            and not getattr(args, "project", None)):
        debuglog.event(root, pol=pol, event="import", agent=agent, skip="no-sources")
        nosrc = ["⚠ no [sources] in cage.toml — cage is capturing nothing. Run "
                 "`cage setup` (or `cage setup --sync-sources`) to materialize the defaults."]
    # The same law one level down: a `--path`/`--project` run draws its patterns from
    # `[sources] path_globs`, so an unmaterialized project scans nothing there too.
    nopg = missing_path_globs(args, targets, pol)
    for line in nopg:
        debuglog.event(root, pol=pol, event="import", agent=agent, skip="no-path-globs",
                       detail=line)
    # ── the routed kiro leg (ADR 0006) ───────────────────────────────────────────
    # Kiro's IDE log is one global file with no project dimension, so its rows are a
    # machine fact and land in the machine ledger. The leg runs to completion HERE —
    # its lock is released before the project's is taken, so no process ever holds two
    # (see `_kiro_leg`). Its summary line is rendered below with the other agents', but
    # its counts never enter this sweep's `collected`/rollup/manifest/health.
    kiro_sink = paths.kiro_routed(root) if "kiro" in targets else None
    routed: list[str] = []
    if kiro_sink is not None:
        routed = _kiro_leg(root, kiro_sink, args, pol)
        targets = tuple(t for t in targets if t != "kiro")
    if not targets:  # a kiro-only import that routed away — nothing left to do here
        return nosrc + nopg + routed
    with _import_lock(foot, pol):
        cursors = _load_cursors(foot)
        if kiro_sink is not None:  # kiro captures elsewhere now — its state here would lie
            _drop_routed_kiro_state(cursors)
        all_rows = ledger.calls(root)  # one ledger read shared across agents + capture health
        seen = {c.get("id") for c in all_rows}
        captured = {agents.row_surface(c.get("agent")) for c in all_rows}  # gate 3 (no 2nd read)
        health: dict = {}  # per-agent {files, src} accumulated by _scan across this sweep
        collected: list[dict] = []  # rows this run appended — feeds the §2.2 rollup, no re-read
        names: dict[str, str] = {}  # {session: lifted name}, parse-only — feeds the manifest only
        # One import_id per sweep (plan §4): stamped on every call row this sweep appends
        # (the FK back to the manifest) and shared by the per-session manifest rows.
        from cage import manifest
        import_id = manifest.new_import_id()
        # The authorship pass (agent-vs-human v2 P1) rides the same sweep and keeps its
        # own bucket in the cursor map — the `_`-prefixed-metadata precedent beside
        # `_last_import`/`_health`, and NOT the per-agent call cursor (see
        # `authorcapture`). Nothing here can move a token or cost number: it writes
        # only `provenance.jsonl`, which no money view reads.
        from cage import authorcapture
        authorship = cursors.setdefault(authorcapture.CURSOR_KEY, {})
        # METRICS-CURSOR-BLIND: a `--rescan-metrics` run reports what it backfilled.
        # Counted before/after around the whole sweep rather than accumulated through
        # the four ingest sites — the ledger is the one place all three kinds agree,
        # and a count read cannot drift from what was actually appended.
        rescan_metrics = getattr(args, "rescan_metrics", False)
        m_before = _metrics_row_count(root, pol) if rescan_metrics else {}
        lines = [run_agent(root, a, args, pol=pol, seen=seen,
                           agent_cursor=cursors.setdefault(a, {}), health=health,
                           collect=collected, import_id=import_id, names=names,
                           authorship_cursor=authorship)
                 for a in targets]
        lines += routed  # kiro's line, in SURFACES order, naming the ledger it landed in
        # Custom tools ([sources.<name>], plan Phase 4) sweep on the umbrella `all`
        # import — the global capture path that grabs the whole stack.
        if agent == "all":
            lines += import_custom_tools(root, args, pol=pol, seen=seen, cursors=cursors,
                                         collect=collected, import_id=import_id)
        if rescan_metrics:
            lines += _rescan_metrics_line(m_before, _metrics_row_count(root, pol))
        # The loud per-agent×surface token/cost rollup (plan §2.2), from this run's
        # appended rows (the per-agent `✔ …` lines above already report file counts).
        lines += _import_rollup(collected, pol, deduped=0)
        # The capture manifest (plan §4): one audit row per (agent, surface, session)
        # captured, each carrying its lifted session name (parse-only, manifest-only).
        _write_manifest(root, import_id, collected, health, pol, _now_iso(), names)
        _record_health(root, cursors, health, captured, targets, pol)
        _record_capture_log(root, health, all_rows, targets)
        cursors["_last_import"] = _now_iso()  # pull-based staleness signal for doctor/report
        _save_cursors(foot, cursors)
    # Piggybacked state maintenance (plan §3.6.4): every hook/watch/export sweep
    # converges here — the one chokepoint. Throttled + fail-open inside; cage
    # installs no scheduler, so this is the only auto path cleanup ever gets.
    from cage import cleanup
    cleanup.maybe_run(root, pol)
    return nosrc + nopg + lines


def _parse_iso(ts: str):
    try:
        return _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class _SweepArgs:
    """The minimal arg shape `run` reads for a capture-on-read sweep — deliberately a
    FRESH namespace, never the read command's own args: a read command's own `--project`
    must not have its output-filter `project` (a basename) misread by `import_claude` as
    a Claude project *slug* restriction, and its `--since` must not narrow capture. A
    capture-on-read sweep is always the full all-agent incremental scan (cursors keep a
    warm no-op cheap)."""
    agent = "all"
    path = None
    project = None
    since = None


def ensure_captured(root: Path, args=None, *, pol: dict | None = None,
                    force: bool = False) -> dict | None:
    """The **capture-on-read** primary path (capture-architecture Phase 1): lazily run
    the incremental sweep before a read returns, so any number a user sees was captured
    the instant before. Returns a counts-only summary of what became newly visible
    (``{"calls", "agents", "savings"}``) when there is something to announce, else
    ``None`` — **zero new ⇒ silent** (no nag on a warm cache). Prints nothing itself; the
    CLI read handler renders the summary line, the MCP server returns it as a structured
    field (never stray stdout).

    Suppressed — returns ``None`` — when: ``--no-import`` is set; capture is off
    (`[capture] enabled=false` / `CAGE_CAPTURE=0`); capture-on-read specifically is off
    (`[capture] on_read=false` / `CAGE_CAPTURE_ON_READ=0`, the switch the determinism
    suite pins); or the throttle window (`policy.read_throttle_secs`, keyed on the
    `_last_import` cursor — no new state file) hasn't elapsed since the last sweep.

    **Fail-open**: any capture error is traced under ``CAGE_DEBUG`` and swallowed — a
    read must always succeed even if capture can't. Reuses `run`'s `_import_lock`, so
    concurrent reads can't double-append (id-dedupe is the backstop regardless)."""
    try:
        if pol is None:
            pol = _load_policy(root)
        if getattr(args, "no_import", False):
            debuglog.event(root, pol=pol, event="capture-on-read", skip="--no-import")
            return None
        if not policy.capture_enabled(pol):
            debuglog.event(root, pol=pol, event="capture-on-read", skip="capture-disabled")
            return None
        if not policy.capture_on_read_enabled(pol):
            debuglog.event(root, pol=pol, event="capture-on-read", skip="on-read-disabled")
            return None
        prev_import = last_import(root)
        window = policy.read_throttle_secs(pol)
        if force:
            # `force` skips the THROTTLE only, and only one caller sets it:
            # `hookcmd._session_end`, which sweeps so that the session's own calls (and
            # therefore its tasks) are visible to `_open_tasks` a few lines later. Under
            # the throttle that sweep returned `None`, so any read in the preceding
            # window left the session's final tasks silently un-closable — and a session
            # end happens exactly once, with no later trigger to make up for it.
            #
            # It deliberately does NOT bypass the two gates above it: `capture.enabled`
            # is the consumer's master switch (pausing metering must actually pause it),
            # and `--no-import` is an explicit per-invocation refusal. Both are decisions
            # a user made; the throttle is only an optimisation.
            debuglog.event(root, pol=pol, event="capture-on-read", action="forced",
                           window=window)
            window = 0
        if prev_import and window > 0:
            from cage import render
            secs = render.age_seconds(prev_import)
            if secs is not None and secs < window:
                debuglog.event(root, pol=pol, event="capture-on-read", skip="throttled",
                               age_secs=secs, window=window)
                return None
        before_calls = {c.get("id") for c in ledger.calls(root)}
        debuglog.event(root, pol=pol, event="capture-on-read", action="sweep",
                       resolved_root=str(root))
        run(root, "all", args if isinstance(args, _SweepArgs) else _SweepArgs())
        after_calls = ledger.calls(root)
        new_calls = [c for c in after_calls if c.get("id") not in before_calls]
        # Savings surfaced "since last read": receipts pushed (graphify/fux) between the
        # previous sweep and now — the pull sweep never appends receipts itself, so this
        # is the push-side arrivals. First read (no prior cursor) establishes the
        # baseline and announces none (nothing is "since last read" when there was none).
        cut = _parse_iso(prev_import) if prev_import else None
        new_savings = 0
        if cut is not None:
            for r in ledger.receipts(root):
                if r.get("tool") == "human" or r.get("unit") == "minutes":
                    continue
                ts = _parse_iso(r.get("ts", ""))
                if ts is not None and ts > cut:
                    new_savings += 1
        n_calls = len(new_calls)
        if not n_calls and not new_savings:
            return None  # zero new ⇒ silent
        agent_set = sorted({agents.row_surface(c.get("agent")) for c in new_calls})
        debuglog.event(root, pol=pol, event="capture-on-read", result="captured",
                       calls=n_calls, savings=new_savings, agents=",".join(agent_set))
        return {"calls": n_calls, "agents": agent_set, "savings": new_savings}
    except Exception as e:  # fail-open: a read must succeed even if capture can't
        debuglog.exception(root, "capture-on-read", e, pol=pol)
        return None


def capture_summary_line(summary: dict | None) -> str:
    """The dim one-line capture-on-read confirmation printed *above* a read (§12.2), or
    ``""`` when there's nothing to announce (zero new ⇒ silent). Counts only, never
    content. Shared by every CLI read handler so the wording is defined once."""
    if not summary:
        return ""
    parts = []
    n = summary.get("calls", 0)
    if n:
        agents_ = summary.get("agents") or []
        who = f" ({', '.join(agents_)})" if agents_ else ""
        parts.append(f"{n} new call{'s' if n != 1 else ''}{who}")
    m = summary.get("savings", 0)
    if m:
        parts.append(f"{m} graphify saving{'s' if m != 1 else ''}")
    if not parts:
        return ""
    return f"· captured {' + '.join(parts)} since last read"
