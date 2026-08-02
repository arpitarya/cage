"""Commit windows — placing a timestamped thing on the commit that contains it
(agent-vs-human v2, P1 windows · P2 the call join).

**The design decision this module exists to make.** A transcript is imported minutes
or days after the work, and the only thing an edit carries is its own turn timestamp.
Resolving it against `HEAD` at import time would attribute every late-imported edit to
whatever happened to be checked out when `cage import` ran — which is how a capture
path quietly becomes a random-number generator. So instead each commit owns the
half-open window ending at its own commit timestamp::

    commit_i owns (ts_{i-1}, ts_i]        the first commit owns (-inf, ts_0]

and a thing belongs to the commit whose window contains its timestamp. The upper bound
is **inclusive**: an edit made at the same second as the commit is part of it.

Work after the newest commit falls in **no** window and is deliberately left
unrecorded this sweep. That is not a loss — provenance writes are idempotent on
(sha, agent, session, method) and the ids are deterministic, so the next import after
the commit exists picks it up exactly once. Guessing a commit that does not exist yet
is the one option that would be wrong forever.

Git access is the `tasks._git` idiom throughout: shell out, read-only, 5s timeout,
**fail-open** — no repo / no git / a detached or empty HEAD yields an empty window
list and the caller records nothing, never an exception into the capture path.
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import NamedTuple


class Window(NamedTuple):
    """One commit's ownership window, ``(lo, hi]``. ``lo`` is ``""`` for the oldest
    commit — the empty string sorts below every ISO timestamp, so the open lower bound
    needs no special case at the comparison site."""
    sha: str
    lo: str
    hi: str


def _git(root: Path, *args: str) -> str | None:
    """Read-only git; stripped stdout, or None on any failure (the `tasks._git` idiom
    — same 5s timeout, same fail-open contract, deliberately not imported so a change
    to one module's git policy can never silently re-govern the other)."""
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout
    except (OSError, subprocess.SubprocessError):
        return None


def toplevel(start: Path) -> Path | None:
    """The git work-tree root containing ``start``, or None when there isn't one.

    The anchor for the whole authorship pass: provenance describes ONE repository, so
    the pass resolves the repo once and ignores every edit outside it rather than
    writing rows whose short shas would be ambiguous across repos."""
    out = _git(start, "rev-parse", "--show-toplevel")
    if not out or not out.strip():
        return None
    try:
        return Path(out.strip()).resolve()
    except OSError:  # pragma: no cover — a path git printed but the OS can't resolve
        return None


def head(root: Path) -> str:
    """The short sha of ``HEAD``, or "" — used only as a *cursor* input (has the repo
    moved since we last looked?), never to attribute an edit. See the module docstring."""
    out = _git(root, "rev-parse", "--short", "HEAD")
    return out.strip() if out else ""


def commit_windows(root: Path) -> list[Window]:
    """Every commit reachable from HEAD as an ordered list of ownership windows,
    **oldest first**.

    Read from ``git log --format=%h|%cI`` — the *committer* date, not the author date:
    a rebase or a cherry-pick rewrites when a commit joined this history, and the
    window is about when the work landed here, not when it was first typed. Commits
    are re-sorted by timestamp rather than trusted in log order, so a repo carrying an
    out-of-order committer date (an amended or grafted commit) still yields
    non-overlapping windows instead of a silently negative one.

    Fail-open ⇒ ``[]`` (no repo, no git, no commits): the caller then records nothing,
    which is the honest answer when there is no history to attribute against."""
    out = _git(root, "log", "--format=%h|%cI")
    if not out:
        return []
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        sha, sep, ts = line.strip().partition("|")
        if sep and sha and ts:
            pairs.append((sha, ts))
    if not pairs:
        return []
    pairs.sort(key=lambda p: (p[1], p[0]))  # oldest first; sha breaks a same-second tie
    windows: list[Window] = []
    prev = ""
    for sha, ts in pairs:
        windows.append(Window(sha, prev, ts))
        prev = ts
    return windows


def window_for(windows: list[Window], ts: str) -> Window | None:
    """The window containing ``ts`` (``lo < ts <= hi``), or None when ``ts`` is after
    the newest commit — the deliberately-unrecorded case (module docstring).

    Linear rather than bisecting on purpose: the caller resolves a handful of distinct
    timestamps per sweep against a few hundred windows, and a plain scan has no
    boundary-condition surface to get wrong."""
    if not ts:
        return None
    for w in windows:
        if w.lo < ts <= w.hi:
            return w
    return None


def newest_ts(windows: list[Window]) -> str:
    """The newest commit timestamp, or "" — the ceiling below which an edit is
    *coverable*. The authorship cursor uses it to decide whether a transcript still
    has work waiting for a commit that has not been made yet."""
    return windows[-1].hi if windows else ""
