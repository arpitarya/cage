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

from cage import budget, ledger, originrecord, paths, policy, tasks, transcript

_EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}


def _stdin_json() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def _root(payload: dict) -> Path:
    cwd = payload.get("cwd")
    start = Path(cwd) if cwd else Path.cwd()
    return paths.find_project_root(start) or start


def append_new(root: Path, rows: list[dict]) -> int:
    """Append only call rows whose id isn't already in the ledger. Returns #added."""
    seen = {c.get("id") for c in ledger.calls(root)}
    added = 0
    for row in rows:
        if row.get("id") not in seen:
            if ledger.append_row(root, "calls", row):
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
    try:
        _capture_calls(_stdin_json())
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0


def session_end() -> int:
    payload = _stdin_json()
    tp = payload.get("transcript_path")
    if tp:
        try:
            _capture_calls(payload)
            _record_transcript_provenance(_root(payload), Path(tp),
                                          payload.get("session_id", ""))
        except Exception:  # pragma: no cover — best-effort
            pass
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
    try:
        tool_name = payload.get("tool_name", "")
        files = _edit_paths(tool_name, payload.get("tool_input") or {})
        if not files:
            return 0
        root = _root(payload)
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
            ledger.append(buf, {"file": f, "added": added, "removed": removed,
                                "agent": "claude-code"})
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0


def post_commit() -> int:
    """Git `post-commit` hook — resolve this session's pending-edit buffer to the
    just-made commit's sha, write the hooked provenance row, clear the buffer."""
    try:
        root = paths.find_project_root() or Path.cwd()
        sha = originrecord.current_sha(root)
        if not sha:
            return 0
        state_dir = paths.Footprint(root).state
        if not state_dir.is_dir():
            return 0
        for buf in state_dir.glob("pending-*.jsonl"):
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
            buf.unlink(missing_ok=True)
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0


def prepare_commit_msg(msg_path: str) -> int:
    """Git `prepare-commit-msg` hook — append `Co-authored-by` / `Change-Origin` /
    `Agent-Session` trailers from this session's pending-edit buffers. Ergonomics
    only: a record-keeping convenience, never the provenance ledger's source of
    truth (that's `post_commit`). Bypassable via `git commit --no-verify`."""
    try:
        root = paths.find_project_root() or Path.cwd()
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
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0


def session_start() -> int:
    try:
        root = _root(_stdin_json())
        pol = policy.load(paths.Footprint(root).policy)
        v = budget.check(root, pol)
        day = v["scopes"]["day"]
        if day["used"]:
            cap = f" / ${day['cap']:.2f} cap" if day["cap"] else ""
            flag = "  ⚠ over budget" if day["over"] else ""
            print(f"Cage: ${day['used']:.4f} spent today{cap}{flag}. `cage report` for detail.")
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0
