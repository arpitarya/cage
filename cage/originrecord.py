"""The provenance write side — authorship-attribution rows (plan §3.5).

Mirrors `tasks.py`'s git idiom exactly: shell out, read-only, 5s timeout,
fail-open (`(OSError, subprocess.SubprocessError)` → None, never raise). A
provenance row only ever exists if *some* signal fired (a live `PostToolUse`
hook, a parsed transcript, or an explicit human attestation in `origin.py`) —
there is no "unknown" row; absence of a row *is* unknown (read-time default,
plan §3.5). `method` is sacred here too: never let a recorded row claim a
stronger method than the signal that actually produced it.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from cage import ledger, paths, schema
from cage.constants import PROVENANCE_CORROBORATION_BONUS, PROVENANCE_METHOD_TRUST

_NUMSTAT = re.compile(r"^(\d+|-)\t(\d+|-)\t(.+)$")


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command; return stripped stdout, or None on any failure."""
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def current_sha(root: Path) -> str | None:
    return _git(root, "rev-parse", "--short", "HEAD")


def working_tree_numstat(root: Path, path: str | None = None) -> list[tuple[str, int, int]]:
    """`(file, added, removed)` for the uncommitted working tree (fail-open ⇒ [])."""
    args = ["diff", "--numstat"]
    if path:
        args += ["--", path]
    out = _git(root, *args)
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        m = _NUMSTAT.match(line)
        if not m:
            continue
        added, removed, f = m.groups()
        if added == "-" or removed == "-":  # binary file — numstat reports "-"
            continue
        rows.append((f, int(added), int(removed)))
    return rows


def commit_numstat(root: Path, sha: str) -> list[tuple[str, int, int]]:
    """`(file, added, removed)` for an already-committed `sha` (fail-open ⇒ []).

    v2: hunk-range fingerprints (line ranges, not just per-file counts) would
    sharpen attribution when a file has multiple authors in one commit.
    """
    out = _git(root, "show", "--numstat", "--format=", sha)
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        m = _NUMSTAT.match(line)
        if not m:
            continue
        added, removed, f = m.groups()
        if added == "-" or removed == "-":
            continue
        rows.append((f, int(added), int(removed)))
    return rows


def read_all(root: Path) -> list[dict]:
    return ledger.provenance(root)


def for_sha(root: Path, sha: str) -> list[dict]:
    return ledger.provenance_for_sha(root, sha)


def confidence_for(method: str, *, corroborated: bool = False) -> float:
    """Rank-derived confidence (0–1): `PROVENANCE_METHOD_TRUST` rank /2, +bonus if a
    second independent path corroborates the same (sha, files)."""
    base = (PROVENANCE_METHOD_TRUST.get(method, 0) + 1) / (len(PROVENANCE_METHOD_TRUST))
    bonus = PROVENANCE_CORROBORATION_BONUS if corroborated else 0.0
    return round(min(1.0, base + bonus), 4)


def _already_recorded(root: Path, *, sha: str, agent: str, session_id: str, method: str) -> bool:
    return any(r.get("sha") == sha and r.get("agent") == agent
              and r.get("session_id") == session_id and r.get("method") == method
              for r in read_all(root))


def _corroborated_by_other_method(root: Path, *, sha: str, files: list[str],
                                   session_id: str, method: str) -> bool:
    """A second, independent capture path already has a row for an overlapping file
    set on this (sha, session) — the 2-path corroboration the handoff calls for."""
    fset = set(files)
    return any(r.get("sha") == sha and r.get("session_id") == session_id
              and r.get("method") != method and fset & set(r.get("files") or [])
              for r in read_all(root))


def record(root: Path, *, sha: str, files: list[str], agent: str = "",
          lines_added: int = 0, lines_removed: int = 0, method: str = "heuristic",
          origin: str = "agent", session_id: str = "", confidence: float | None = None) -> bool:
    """Append one provenance row. Fail-open; idempotent on (sha, agent, session_id, method).
    Confidence is bumped when a *different* method already recorded an overlapping
    file for the same (sha, session) — independent-path corroboration, plan §3.5."""
    try:
        if not sha or not files:
            return False
        if _already_recorded(root, sha=sha, agent=agent, session_id=session_id, method=method):
            return False
        corroborated = _corroborated_by_other_method(root, sha=sha, files=files,
                                                      session_id=session_id, method=method)
        conf = confidence_for(method, corroborated=corroborated) if confidence is None else confidence
        row = schema.make_provenance(sha=sha, files=files, agent=agent,
                                     lines_added=lines_added, lines_removed=lines_removed,
                                     method=method, origin=origin, confidence=conf,
                                     session_id=session_id)
        return ledger.append(paths.Footprint(root).provenance, row)
    except Exception:  # noqa: BLE001 — write-path discipline: never raise
        return False


def record_hooked(root: Path, *, sha: str, files: list[str], agent: str,
                  lines_added: int = 0, lines_removed: int = 0,
                  session_id: str = "", origin: str = "agent") -> bool:
    """Live `PostToolUse` capture — the highest-trust method (sees `tool_input` as
    the agent acts, plan §3.5)."""
    return record(root, sha=sha, files=files, agent=agent, lines_added=lines_added,
                 lines_removed=lines_removed, method="hooked", origin=origin,
                 session_id=session_id)


def record_transcript(root: Path, *, sha: str, files: list[str], agent: str,
                      lines_added: int = 0, lines_removed: int = 0,
                      session_id: str = "", origin: str = "agent") -> bool:
    """Parsed after the fact from a session transcript — lower trust than a live hook."""
    return record(root, sha=sha, files=files, agent=agent, lines_added=lines_added,
                 lines_removed=lines_removed, method="transcript", origin=origin,
                 session_id=session_id)
