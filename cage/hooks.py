"""Claude Code hook entrypoints (plan §5, §9.5, §3.5) — wired by `cage hooks install`.

- Stop        → fires when Claude finishes each turn; parse the transcript and
  append the just-completed turn (idempotent on the turn uuid). This is the
  **real-time** capture path — spend lands as soon as a turn ends, with no wait
  for SessionEnd or the next session's SessionStart-backfill.
- SessionEnd  → parse the session transcript, append any not-yet-recorded turns
  (idempotent on the turn uuid). Off the request path: never blocks a call.
- SessionStart → print a one-line spend/budget banner; Claude Code injects hook
  stdout into context, the same way the fux INDEX is surfaced.
- PostToolUse → buffer the file(s) an Edit/Write/MultiEdit touched, keyed by
  session, into `.cage/state/pending-<session>.jsonl` (plan §3.5). The edit is
  still uncommitted at this point, so no provenance row is written yet — a
  `post-commit` git hook resolves the buffer to a real sha (see `post_commit`).

Every entrypoint is fail-open and exits 0 — a hook must never break the session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import budget, debuglog, ledger, originrecord, paths, policy, tasks, transcript

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}

_AGENT = "claude"  # hooks.py is Claude Code's real-time hook surface


def _pol(root: Path) -> dict:
    """Load policy once per hook firing so the debug gate (`debuglog.enabled`) and every
    log call share it — when debug is off this is the path's only added cost (one tiny
    toml read), and no debug file is written."""
    return policy.load(paths.Footprint(root).policy)


def _trace_entry(root: Path, event: str, payload: dict, *, pol: dict | None = None,
                 **fields) -> None:
    """Log a hook firing (entry + heartbeat) for the capture-debug trail. No-op unless
    debug is enabled; metadata only — `transcript_path` is recorded as a presence bool,
    never its contents (counts-never-content)."""
    cwd = payload.get("cwd") or str(Path.cwd())
    debuglog.heartbeat(root, _AGENT, event, cwd, pol=pol)
    debuglog.event(root, pol=pol, agent=_AGENT, event=event, cwd=cwd, resolved_root=str(root),
                   cage_present=(root / ".cage").is_dir(),
                   transcript_path_present=bool(payload.get("transcript_path")),
                   **fields)


def _stdin_json() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def _root(payload: dict) -> Path:
    cwd = payload.get("cwd")
    start = Path(cwd) if cwd else Path.cwd()
    # Full §3.7 precedence, not `find_project_root or start`: a hook firing in a
    # no-project dir must land in the global ~/.cage — the old cwd fallback grew a
    # stray .cage/ footprint in whatever dir the session ran from and split the
    # ledger (2026-07 manual validation, resolver-precedence check).
    return paths.resolve_root(start)


def append_new(root: Path, rows: list[dict], seen: set | None = None) -> int:
    """Append only call rows whose id isn't already in the ledger. Returns #added.

    ``seen`` is an optional caller-owned set of already-known call ids: pass it to skip
    the per-call ledger reload and amortize the dedupe across a multi-file run (the
    ledger is 22k+ rows — re-reading it per file/call is the import hot path, plan
    §3.7). It is mutated in place with each appended id so later batches see them.
    Omit it and the legacy self-contained behavior holds (reload once here)."""
    if seen is None:
        seen = {c.get("id") for c in ledger.calls(root)}
    added = 0
    for row in rows:
        if row.get("id") not in seen:
            if ledger.append_row(root, "calls", row):
                seen.add(row.get("id"))
                added += 1
    return added


def _capture_calls(payload: dict) -> int:
    """Token capture from the live transcript — shared by Stop and SessionEnd.
    Idempotent on the turn uuid (`append_new`), so firing on every Stop never
    double-records and stacks safely with the SessionStart-backfill."""
    tp = payload.get("transcript_path")
    if not tp:
        return 0
    root = _root(payload)
    rows = transcript.parse_calls(Path(tp), session=payload.get("session_id", ""))
    added = append_new(root, rows)
    _snapshot_tasks(root, rows)
    return added


def stop() -> int:
    """Stop hook — fires when Claude finishes a turn. Records *that turn's* tokens in
    near-real-time (no wait for SessionEnd or the next SessionStart-backfill). Claude
    only — each agent captures its own data via its own hooks; cage never sweeps another
    agent's logs from this hook. Provenance stays a PostToolUse+post-commit concern;
    Stop is token capture only. Fail-open, exits 0."""
    payload = _stdin_json()
    root = _root(payload)
    pol = _pol(root)
    _trace_entry(root, "stop", payload, pol=pol)
    try:
        added = _capture_calls(payload)
        debuglog.event(root, pol=pol, agent=_AGENT, event="stop", result="ok", appended=added)
    except Exception as e:  # fail-open: a capture error never breaks the turn
        debuglog.exception(root, "hook.stop", e, pol=pol)
    return 0


def session_end() -> int:
    payload = _stdin_json()
    root = _root(payload)
    pol = _pol(root)
    tp = payload.get("transcript_path")
    _trace_entry(root, "session_end", payload, pol=pol)
    if tp:
        try:
            added = _capture_calls(payload)
            _record_transcript_provenance(root, Path(tp), payload.get("session_id", ""))
            debuglog.event(root, pol=pol, agent=_AGENT, event="session_end", result="ok",
                           appended=added)
        except Exception as e:  # fail-open
            debuglog.exception(root, "hook.session_end", e, pol=pol)
    # Claude's real-time hooks bypass `importcmd.run`, so session close is this
    # surface's cleanup chokepoint (throttled + fail-open inside — plan §3.6.4).
    from cage import cleanup
    cleanup.maybe_run(root, pol)
    return 0


def _record_transcript_provenance(root: Path, transcript_path: Path, session_id: str) -> None:
    """Fallback authorship capture: a sibling signal to the live PostToolUse hook,
    resolved against the current HEAD sha (the transcript itself can't say which
    commit an edit landed in — plan §3.5)."""
    edits = transcript.parse_provenance(transcript_path, session=session_id)
    if not edits:
        return
    sha = originrecord.current_sha(root)
    if not sha:
        return
    files = [e["file"] for e in edits]
    rel: list[str] = []
    for f in files:
        try:
            rel.append(str(Path(f).resolve().relative_to(root)))
        except ValueError:
            continue
    if rel:
        originrecord.record_transcript(root, sha=sha, files=rel, agent="claude-code",
                                       session_id=session_id)


def _snapshot_tasks(root: Path, rows: list[dict]) -> None:
    """Record a git-aware task row for each task this session touched (fail-open)."""
    seen: set[str] = set()
    for row in rows:
        t = row.get("task")
        if t and t not in seen:
            seen.add(t)
            tasks.record(root, t, agents=[row.get("agent", "")] if row.get("agent") else None)


def _edit_paths(tool_name: str, tool_input: dict) -> list[str]:
    """File path(s) an Edit/Write/MultiEdit/NotebookEdit call touched."""
    if tool_name not in _EDIT_TOOLS:
        return []
    fp = tool_input.get("file_path") or tool_input.get("notebook_path")
    return [fp] if fp else []


def post_tool_use() -> int:
    payload = _stdin_json()
    root = _root(payload)
    pol = _pol(root)
    try:
        tool_name = payload.get("tool_name", "")
        files = _edit_paths(tool_name, payload.get("tool_input") or {})
        _trace_entry(root, "post_tool_use", payload, pol=pol, tool_name=tool_name,
                     files_buffered=len(files))
        if not files:
            return 0
        session_id = payload.get("session_id", "")
        buf = paths.Footprint(root).pending_edits(session_id)
        rel = []
        for f in files:
            try:
                rel.append(str(Path(f).resolve().relative_to(root)))
            except ValueError:
                continue  # outside the project root — never buffer an absolute foreign path
        for f in rel:
            added, removed = 0, 0
            for fname, a, r in originrecord.working_tree_numstat(root, f):
                if fname == f:
                    added, removed = a, r
                    break
            if not ledger.append(buf, {"file": f, "added": added, "removed": removed,
                                       "agent": "claude-code"}):
                debuglog.event(root, pol=pol, agent=_AGENT, event="post_tool_use",
                               skip="buffer-write-failed", file=f)
    except Exception as e:  # fail-open
        debuglog.exception(root, "hook.post_tool_use", e, pol=pol)
    return 0


def post_commit() -> int:
    """Git `post-commit` hook — resolve this session's pending-edit buffer to the
    just-made commit's sha, write the hooked provenance row, clear the buffer."""
    root = paths.resolve_root()  # same tier as _root(): no-cage repo ⇒ global, no stray footprint
    pol = _pol(root)
    debuglog.heartbeat(root, "git", "post_commit", str(Path.cwd()), pol=pol)
    try:
        sha = originrecord.current_sha(root)
        if not sha:
            debuglog.event(root, pol=pol, agent="git", event="post_commit", skip="no sha (not a repo / no HEAD)")
            return 0
        state_dir = paths.Footprint(root).state
        if not state_dir.is_dir():
            debuglog.event(root, pol=pol, agent="git", event="post_commit", skip="no .cage/state dir")
            return 0
        buffers, rows_written = 0, 0
        for buf in state_dir.glob("pending-*.jsonl"):
            buffers += 1
            rows = ledger.read(buf)
            if not rows:
                buf.unlink(missing_ok=True)
                continue
            files = sorted({r["file"] for r in rows if r.get("file")})
            added = sum(r.get("added", 0) for r in rows)
            removed = sum(r.get("removed", 0) for r in rows)
            agent = rows[0].get("agent", "") if rows else ""
            session_id = buf.stem.removeprefix("pending-")
            if files:
                originrecord.record_hooked(root, sha=sha, files=files, agent=agent,
                                           lines_added=added, lines_removed=removed,
                                           session_id=session_id)
                rows_written += 1
            buf.unlink(missing_ok=True)
        debuglog.event(root, pol=pol, agent="git", event="post_commit", result="ok",
                       sha_present=True, buffers=buffers, rows_written=rows_written)
    except Exception as e:  # fail-open
        debuglog.exception(root, "hook.post_commit", e, pol=pol)
    return 0


def prepare_commit_msg(msg_path: str) -> int:
    """Git `prepare-commit-msg` hook — append `Co-authored-by` / `Change-Origin` /
    `Agent-Session` trailers from this session's pending-edit buffers. Ergonomics
    only: a record-keeping convenience, never the provenance ledger's source of
    truth (that's `post_commit`). Bypassable via `git commit --no-verify`."""
    root = paths.resolve_root()  # same tier as _root() / post_commit()
    try:
        state_dir = paths.Footprint(root).state
        if not state_dir.is_dir():
            return 0
        trailers: list[str] = []
        for buf in sorted(state_dir.glob("pending-*.jsonl")):
            rows = ledger.read(buf)
            if not rows:
                continue
            agent = rows[0].get("agent", "") if rows else ""
            session_id = buf.stem.removeprefix("pending-")
            if agent:
                trailers.append(f"Co-authored-by: {agent} <noreply@cage.local>")
                trailers.append(f"Change-Origin: agent")
                trailers.append(f"Agent-Session: {session_id}")
        if not trailers:
            return 0
        path = Path(msg_path)
        text = path.read_text(encoding="utf-8")
        if "Agent-Session:" in text:  # already stamped (e.g. a retried hook) — no dup
            return 0
        path.write_text(text.rstrip("\n") + "\n\n" + "\n".join(trailers) + "\n", encoding="utf-8")
    except Exception as e:  # best-effort — but never silent (traceable under CAGE_DEBUG)
        debuglog.exception(root, "hook.prepare_commit_msg", e)
    return 0


def session_start() -> int:
    payload = _stdin_json()
    root = _root(payload)
    pol = policy.load(paths.Footprint(root).policy)
    _trace_entry(root, "session_start", payload, pol=pol)
    try:
        v = budget.check(root, pol)
        day = v["scopes"]["day"]
        shown = bool(day["used"])
        if shown:
            cap = f" / ${day['cap']:.2f} cap" if day["cap"] else ""
            flag = "  ⚠ over budget" if day["over"] else ""
            print(f"Cage: ${day['used']:.4f} spent today{cap}{flag}. `cage report` for detail.")
        debuglog.event(root, pol=pol, agent=_AGENT, event="session_start", result="ok",
                       banner_shown=shown)
    except Exception as e:  # fail-open
        debuglog.exception(root, "hook.session_start", e, pol=pol)
    return 0
