"""The authorship capture pass — re-wiring provenance into the import sweep
(agent-vs-human v2, P1).

Until v2 this was **dead code**: `transcript.parse_provenance` and
`originrecord.record_transcript` had zero callers, the hookless rebuild having removed
the SessionEnd trigger that used to fire them. The read surface (`cage authorship
origin`, notes-sync, verify) was live the whole time and answering `unknown` for every
sha, because nothing wrote an automated row. This module is what writes them.

**The shape of one pass** (`capture`), for one repository and one sweep:

1. Resolve the repo — ONE repo per sweep, from the caller's cwd. Provenance rows carry
   a short sha and repo-relative paths but no repo identity, so recording two repos'
   commits into one ledger would make those shas ambiguous. Edits outside the repo are
   ignored, not guessed at.
2. Read the commit windows once (`commitjoin.commit_windows`) — never HEAD-at-import.
3. Parse each candidate transcript for proposed edits (`transcript.parse_edits`) and
   bucket them by `(commit, session)` using each edit's **own turn timestamp**.
4. Per commit: read the added lines transiently, match, and append one provenance row
   per `(sha, agent, session)` with `method="transcript"`, `origin="agent"` and the
   five additive-optional counts. `originrecord.record` already dedupes on
   `(sha, agent, session_id, method)`, so re-importing writes zero rows.

**Fail-open, absolutely.** This runs inside the capture path: every failure — no git,
no repo, an unreadable transcript, a malformed edit block — is swallowed and traced
under ``CAGE_DEBUG``, never raised into an import. A pass that cannot run records
nothing, which reads as `unknown` (absence), which is the correct answer.

**Counts-never-content.** Proposed line bodies exist only inside step 4 and are never
written, hashed, or logged. See `linematch.py` and the plant-string test.

**The cursor is not the call cursor.** `importcmd`'s per-agent cursor skips a
transcript whose bytes have not changed — correct for calls, and *wrong* here: a
session's last edits are typically committed after the transcript stops growing, so
skipping unchanged files would mean those edits were never recorded at all. This pass
keeps its own cursor (``cursors["_authorship"]``, the ``_``-prefixed-metadata
precedent beside ``_last_import``/``_health``) storing ``[size, mtime, covered]``,
where ``covered`` means every edit in the file already fell inside some commit's
window. A transcript is re-read when it changes **or** while it is still uncovered —
so each one is processed at most once more after its work lands in a commit, and the
steady state is a no-op.
"""
from __future__ import annotations

import os
from pathlib import Path

from cage import commitjoin, debuglog, linematch, originrecord, transcript

CURSOR_KEY = "_authorship"
AGENT = "claude-code"  # the only edit-parseable transcript today (see `coverage_note`)

# Which agents can be line-matched at all, and why not — stated in the views rather
# than rendered as a zero. Copilot/Kiro persist usage but not the text of an edit, so
# their rows read `—` with the reason named (proposal: "coverage is per-agent and
# stated"). A new parser moves an agent from this map into the pass; nothing else.
COVERAGE_GAPS = {
    "copilot": "its stores record usage and prompts, not the text of an edit",
    "kiro": "its usage log records token counts only, with no tool-input payload",
}


def coverage_note() -> str:
    """One line naming every agent this pass structurally cannot cover — never a
    silent omission, and never a 0% that would read as "wrote nothing"."""
    return " · ".join(f"{a}: {why}" for a, why in sorted(COVERAGE_GAPS.items()))


def _repo_relative(path: str, repo: Path) -> str | None:
    """``path`` as a repo-relative POSIX path, or None when it is outside the repo.

    Symlinks are resolved on both sides before comparing: a macOS agent working under
    ``/tmp/x`` writes ``file_path`` as ``/tmp/x/a.py`` while git's toplevel resolves to
    ``/private/tmp/x`` — the same near-miss `transcript._norm_cwd_key` exists for, and
    it would silently return "no edits in this repo", which is indistinguishable from
    "the agent wrote nothing"."""
    try:
        p = Path(os.path.realpath(path))
        rel = p.relative_to(repo)
    except (ValueError, OSError):
        return None
    s = rel.as_posix()
    return s if s and not s.startswith("..") else None


def _bucket_edits(edits, windows, repo: Path) -> dict:
    """``{(sha, session): {repo-relative path: [proposed lines]}}``.

    An edit whose timestamp is after the newest commit belongs to no window and is
    dropped **for this sweep only** — the cursor keeps the transcript uncovered so the
    next import, after the commit exists, records it exactly once."""
    out: dict = {}
    for e in edits:
        w = commitjoin.window_for(windows, e.get("ts") or "")
        if w is None:
            continue
        rel = _repo_relative(e.get("file") or "", repo)
        if rel is None:
            continue  # another repo, or outside the work tree — never guessed at
        out.setdefault((w.sha, e.get("session") or ""), {}).setdefault(rel, []).extend(
            e.get("lines") or [])
    return out


def _uncovered(edits, newest: str) -> bool:
    """Whether any edit is still waiting for a commit that has not been made yet.

    ``newest`` is already in the one normal form (it is a `Window` bound), so the edit
    side is normalized to match — this compare decides whether a transcript is re-read
    next sweep, and on a non-UTC repo the raw form gets it wrong by the offset. An edit
    whose timestamp will not parse normalizes to ``""`` and counts as covered: it can
    never be placed in a window either, so calling it uncovered would re-read the file
    forever waiting for a commit that could not help it."""
    if not newest:
        return bool(edits)
    return any(commitjoin.norm_ts(e.get("ts") or "") > newest for e in edits)


def _sig(f: Path):
    try:
        st = f.stat()
        return [st.st_size, st.st_mtime]
    except OSError:
        return None


def capture(root: Path, files, *, repo: Path | None = None, pol: dict | None = None,
            cursor: dict | None = None) -> dict:
    """Run one authorship pass over ``files`` (claude transcripts) and append the
    provenance rows it can evidence. Returns a counts-only summary::

        {"repo": str, "rows": int, "commits": int, "sessions": int,
         "files_read": int, "suggested": int, "kept": int, "uncovered": int,
         "skipped": str}

    ``root`` is the sweep's ledger root (where rows land, beside every other captured
    row); ``repo`` is the git work tree being described, resolved from the cwd when not
    given. ``cursor`` is ``cursors["_authorship"]`` — omit it and every file is read.

    Never raises."""
    summary = {"repo": "", "rows": 0, "commits": 0, "sessions": 0, "files_read": 0,
               "suggested": 0, "kept": 0, "uncovered": 0, "skipped": ""}
    try:
        from cage import policy
        if not policy.authorship_capture(pol or {}):
            summary["skipped"] = "disabled"
            debuglog.event(root, pol=pol, event="authorship", skip="capture-disabled")
            return summary
        repo = repo or commitjoin.toplevel(Path.cwd())
        if repo is None:
            summary["skipped"] = "no-git-repo"
            debuglog.event(root, pol=pol, event="authorship", skip="no-git-repo")
            return summary
        summary["repo"] = str(repo)
        windows = commitjoin.commit_windows(repo)
        if not windows:
            summary["skipped"] = "no-commits"
            debuglog.event(root, pol=pol, event="authorship", skip="no-commits",
                           repo=str(repo))
            return summary
        newest = commitjoin.newest_ts(windows)
        repo_key = str(repo)
        table = (cursor.setdefault(repo_key, {}) if cursor is not None else None)

        buckets: dict = {}
        pending: list[tuple[str, list]] = []  # (path, cursor value) written on success
        for f in files:
            sig = _sig(f)
            prior = table.get(str(f)) if table is not None else None
            # Re-read when the bytes changed OR the file still has uncovered edits.
            if (prior is not None and sig is not None
                    and list(prior[:2]) == sig and prior[2:] == [True]):
                continue
            edits = transcript.parse_edits(f, session=f.stem)
            summary["files_read"] += 1
            covered = not _uncovered(edits, newest)
            if not covered:
                summary["uncovered"] += 1
            if sig is not None:
                pending.append((str(f), [sig[0], sig[1], covered]))
            for key, by_file in _bucket_edits(edits, windows, repo).items():
                dest = buckets.setdefault(key, {})
                for path, lines in by_file.items():
                    dest.setdefault(path, []).extend(lines)

        by_sha: dict = {}
        for (sha, session) in buckets:
            by_sha.setdefault(sha, []).append(session)
        summary["commits"] = len(by_sha)
        summary["sessions"] = len({s for _sha, s in buckets})

        for sha in sorted(by_sha):
            diff = linematch.commit_diff(repo, sha)   # ONE git call per commit
            added, binary, numstat = diff["added"], diff["binary"], diff["numstat"]
            for session in sorted(by_sha[sha]):
                proposed = buckets[(sha, session)]
                matches, totals = linematch.match_commit(proposed, added, binary)
                landed = sorted(m.path for m in matches
                                if m.verdict in (linematch.KEPT,
                                                 linematch.LANDED_MODIFIED,
                                                 linematch.UNREADABLE))
                if not landed:
                    continue  # proposed nothing that survived: no row, i.e. unknown
                add = sum(numstat.get(p, (0, 0))[0] for p in landed)
                rem = sum(numstat.get(p, (0, 0))[1] for p in landed)
                ok = originrecord.record_transcript(
                    root, sha=sha, files=landed, agent=AGENT, lines_added=add,
                    lines_removed=rem, session_id=session,
                    suggested=totals["suggested"], kept=totals["kept"],
                    kept_modified=totals["kept_modified"], dropped=totals["dropped"],
                    agent_lines=totals["agent_lines"])
                if ok:
                    summary["rows"] += 1
                    summary["suggested"] += totals["suggested"]
                    summary["kept"] += totals["kept"]

        if table is not None:
            table.update(dict(pending))
        debuglog.event(root, pol=pol, event="authorship", result="ok", repo=str(repo),
                       files_read=summary["files_read"], commits=summary["commits"],
                       rows=summary["rows"], suggested=summary["suggested"],
                       kept=summary["kept"], uncovered=summary["uncovered"])
        return summary
    except Exception as e:  # noqa: BLE001 — capture-path discipline: never raise
        debuglog.exception(root, "authorship.capture", e, pol=pol)
        summary["skipped"] = summary["skipped"] or "error"
        return summary
