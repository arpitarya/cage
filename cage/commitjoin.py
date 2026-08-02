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

**Timestamps have ONE normal form here, and it is the module's whole safety story**
(REV-TS). Three shapes arrive at the same ``<``: git's ``%cI`` carries the
*committer-local* offset (``…+05:30``, and ``…Z`` only when that offset is zero), a
call stamps ``…SSZ``, and a transcript turn stamps ``…SS.mmmZ``. Ordering strings
across different offset representations is meaningless, so every bound and every
probe is passed through `norm_ts` before it is ever compared — bounds at
construction (`Window` normalizes, so a non-normalized window cannot be built), and
probes on entry to `window_for`. The comparison itself stays a **string** compare:
the determinism law keeps datetime objects out of stored rows.
"""
from __future__ import annotations

import collections
import datetime as _dt
import subprocess
from pathlib import Path

_UTC = _dt.timezone.utc

# The one normal form. Seconds, not milliseconds, and deliberately so: `%cI` has no
# sub-second component, so a commit stamped `10:00:00` happened *somewhere* in
# [10:00:00, 10:00:01). Millisecond precision would push an edit at `10:00:00.500` —
# plausibly before the commit — into the next window on precision cage does not have,
# and would break the inclusive upper bound documented above in the one case
# (a pure-UTC repo) that already gets it right.
_NORM = "%Y-%m-%dT%H:%M:%SZ"


def as_utc(ts: str) -> _dt.datetime | None:
    """``ts`` as a UTC-**aware** datetime, or None when it cannot be parsed.

    The ONE timestamp parse for the authorship surfaces — `commitview._iso` is this
    function, not a second copy. A naive input is *assumed* UTC rather than left
    naive: returning naive is how a comparison against an aware cutoff raises
    `TypeError` at some caller that has no idea it is holding two kinds of datetime.
    """
    try:
        d = _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None
    return (d if d.tzinfo is not None else d.replace(tzinfo=_UTC)).astimezone(_UTC)


def norm_ts(ts: str) -> str:
    """``ts`` in the one normal form (``YYYY-MM-DDTHH:MM:SSZ``), or ``""``.

    Sub-seconds are **truncated, never rounded** — rounding is non-monotone at a
    boundary and could carry an edit across the very window it belongs in. Empty and
    unparseable both yield ``""``, which every comparison site already reads as
    *no usable timestamp* (`window_for` returns None for it, and it sorts below every
    real timestamp, which is what keeps the oldest window open below)."""
    d = as_utc(ts)
    return d.strftime(_NORM) if d is not None else ""


_WindowFields = collections.namedtuple("Window", "sha lo hi")


class Window(_WindowFields):
    """One commit's ownership window, ``(lo, hi]``. ``lo`` is ``""`` for the oldest
    commit — the empty string sorts below every ISO timestamp, so the open lower bound
    needs no special case at the comparison site.

    **The bounds normalize at construction**, which is why no comparison site converts
    one: a `Window` holding a raw ``%cI`` string cannot be built, in this module or in
    a test. That is deliberately structural rather than a convention — the skew this
    fixes was invisible for exactly as long as it depended on every caller remembering.
    (`_make`/`_replace` bypass `__new__`, as they do for every namedtuple; nothing here
    uses them. It is a `collections.namedtuple` subclass and not a `typing.NamedTuple`
    because the latter forbids overriding `__new__`.)"""
    __slots__ = ()

    def __new__(cls, sha: str, lo: str, hi: str):
        return super().__new__(cls, sha, norm_ts(lo), norm_ts(hi))


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

    **The sort happens on normalized timestamps**, which is the whole point: ``%cI``
    renders each commit in its own committer's offset, so a history mixing local
    commits with ``+00:00`` merges from CI or the GitHub web UI sorts *backwards* on
    the raw strings and builds windows whose bounds run the wrong way.

    Fail-open ⇒ ``[]`` (no repo, no git, no commits): the caller then records nothing,
    which is the honest answer when there is no history to attribute against. A commit
    whose ``%cI`` will not parse is dropped from the list, matching the malformed-line
    filter beside it — a bound cage cannot place in time is worse than one less window.
    """
    out = _git(root, "log", "--format=%h|%cI")
    if not out:
        return []
    pairs: list[tuple[str, str]] = []
    for line in out.splitlines():
        sha, sep, ts = line.strip().partition("|")
        if sep and sha and (norm := norm_ts(ts)):
            pairs.append((sha, norm))
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

    The probe is normalized on entry (the bounds already are, by construction), so
    ``lo < probe <= hi`` compares one shape against itself. An unparseable or empty
    ``ts`` yields None: a thing cage cannot place in time is never placed at all.

    Linear rather than bisecting on purpose: the caller resolves a handful of distinct
    timestamps per sweep against a few hundred windows, and a plain scan has no
    boundary-condition surface to get wrong."""
    probe = norm_ts(ts)
    if not probe:
        return None
    for w in windows:
        if w.lo < probe <= w.hi:
            return w
    return None


def newest_ts(windows: list[Window]) -> str:
    """The newest commit timestamp, or "" — the ceiling below which an edit is
    *coverable*. The authorship cursor uses it to decide whether a transcript still
    has work waiting for a commit that has not been made yet."""
    return windows[-1].hi if windows else ""


# ── P2: joining CALLS to commits ──────────────────────────────────────────────
#
# Two joins, tried in order and **named on every row** so neither is passed off as
# the other — the same discipline `adoption.py` applies to its two attribution paths.

VIA_TASK = "task"      # the call belongs to a closed task whose snapshot names a commit
VIA_WINDOW = "window"  # the call's own timestamp falls inside the commit's window

# Why a call could not be window-joined. Each is a *different fact* with a different
# fix, so they are counted separately and never merged into one "other" bucket.
NO_TS_FIDELITY = "no-ts-fidelity"    # the source's timestamps cannot place a call in time
OTHER_PROJECT = "other-project"      # stamped with a different project — definitely not ours
NO_PROJECT = "no-project"            # unstamped: cage cannot confirm it belongs to this repo
AFTER_HEAD = "after-head"            # newer than the newest commit — work not yet committed
DANGLING_TASK = "dangling-task"      # the task's snapshot sha is not in this history

# **Per-agent joinability is a stated table, not an assumption.** A window join is only
# as good as the timestamp it reads, and the four capture routes carry four different
# grades of timestamp. Naming them here (rather than discovering it as a wrong number)
# is the whole point: a source whose rows all share one timestamp would dump an entire
# session's tokens onto whichever commit that instant happened to fall in.
#
# Keyed `(agent, surface)`; a `None` surface matches any. Anything NOT in this table is
# excluded and counted with the reason named — cage never assumes a new source's
# timestamps are per-call.
_TS_FIDELITY = {
    ("claude", None): "per-turn timestamp, recorded by the agent",
    ("copilot", "vscode"): "per-request timestamp from the chat store",
    ("lib", None): "recorded in-process at the call",
}
_TS_GAPS = {
    ("copilot", "cli"): "one shutdown timestamp per session — every call in a session "
                        "shares it, so a window join would dump the whole session on "
                        "one commit",
    ("kiro", None): "its rows carry the IMPORT time, not the call time — the log has "
                    "no per-call timestamp to place",
}


def ts_fidelity(agent: str, surface: str) -> tuple[bool, str]:
    """``(window-joinable?, the reason either way)`` for one call's source."""
    for key in ((agent, surface), (agent, None)):
        if key in _TS_GAPS:
            return False, _TS_GAPS[key]
        if key in _TS_FIDELITY:
            return True, _TS_FIDELITY[key]
    return False, (f"{agent or 'unknown'}: cage has not verified that this source's "
                   f"timestamps are per-call, so it is not placed on a commit")


def joinability_note() -> str:
    """Every source cage declines to window-join, with its reason — rendered as a
    footnote so an exclusion is never a silently missing row."""
    return " · ".join(f"{a}{'/' + s if s else ''}: {why}"
                      for (a, s), why in sorted(_TS_GAPS.items(),
                                                key=lambda kv: (kv[0][0], kv[0][1] or "")))


def _task_commits(tasks: dict) -> tuple[dict, int]:
    """``({task id: sha}, dirty_count)`` for closed tasks whose snapshot names a commit
    cage is willing to trust.

    **A task closed on a dirty tree is not trusted.** `tasks.git_snapshot` records HEAD
    *plus* `git diff --shortstat` of the working tree, so a non-zero `files_changed`
    means the work had not been committed when the task closed — its `commit` is the
    *prior* commit, and attributing the task's calls to it would put the spend on the
    wrong sha. Those tasks fall through to the window join, which reads the call's own
    timestamp and gets it right."""
    out, dirty = {}, 0
    for tid, row in tasks.items():
        if not row.get("outcome") or not row.get("commit"):
            continue
        if int(row.get("files_changed", 0) or 0):
            dirty += 1
            continue
        out[tid] = row["commit"]
    return out, dirty


def join_calls(calls: list[dict], windows: list[Window], tasks: dict | None = None,
               *, project: str = "", receipts: list[dict] | None = None) -> dict:
    """Place each call on the commit it belongs to. Pure derive — no clock, no I/O.

    **Task-id join first**, because a task id is an *asserted* link and a window is an
    inferred one. The task join is `taskgroup.join_rows` — the documented precedence
    (task-id, then session-window), reused rather than re-implemented, so the two
    surfaces can never drift apart.

    **Window join as the fallback**, gated twice: the source's timestamps must be
    per-call (`ts_fidelity`) and the call must be confirmable as *this* project.

    ``project`` is the repo's basename. Three outcomes, deliberately not two:
    a matching stamp joins; a **different** stamp is excluded as another project's
    work; an **empty** stamp is excluded as *unconfirmable* — a distinct fact with a
    distinct fix, and never quietly adopted. Adopting unstamped rows is exactly how a
    global ledger (the default sink) would pull every other repo's spend onto these
    commits. Two repos sharing a basename are indistinguishable here; that is a stated
    caveat, not something this join pretends to solve.

    Returns::

        {"by_sha": {sha: {"calls": [...], "via": {"task": n, "window": n}}},
         "attributed": n, "excluded": [{"reason", "calls", "tokens"}],
         "unattributed": [sha, …], "dirty_tasks": n, "joined": n}

    ``unattributed`` lists commits with **no** joinable call. They are excluded from
    every total and **counted** — never rendered as a zero, which would claim the
    commit cost nothing.

    There is deliberately no "before history" exclusion: the oldest commit's window is
    open below, so a call predating the first commit lands **on** it. That is right, not
    a fallback — the work that produced a repo's first commit necessarily precedes it."""
    from cage import agents as _agents
    from cage import taskgroup

    by_sha: dict[str, dict] = {}
    excluded: dict[str, dict] = {}
    shas = {w.sha for w in windows}

    def _place(sha: str, call: dict, via: str) -> None:
        g = by_sha.setdefault(sha, {"calls": [], "via": {VIA_TASK: 0, VIA_WINDOW: 0}})
        g["calls"].append(call)
        g["via"][via] += 1

    def _drop(reason: str, call: dict) -> None:
        e = excluded.setdefault(reason, {"reason": reason, "calls": 0, "tokens": 0})
        e["calls"] += 1
        e["tokens"] += int(call.get("tokens_in", 0)) + int(call.get("tokens_out", 0))

    task_sha, dirty = _task_commits(tasks or {})
    # Which task each call belongs to, via the ONE documented join.
    call_task: dict[str, str] = {}
    for tid, grp in taskgroup.join_rows(calls, receipts or []).items():
        for c in grp["calls"]:
            if c.get("id"):
                call_task[c["id"]] = tid

    lo = windows[0].lo if windows else ""
    hi = newest_ts(windows)
    for c in calls:
        tid = call_task.get(c.get("id", ""))
        if tid in task_sha:
            sha = task_sha[tid]
            if sha in shas:
                _place(sha, c, VIA_TASK)
                continue
            _drop(DANGLING_TASK, c)   # squashed/rebased/other-branch — never chased
            continue
        agent = _agents.row_surface(c.get("agent")) or c.get("agent") or ""
        ok, _why = ts_fidelity(agent, c.get("surface", ""))
        if not ok:
            _drop(NO_TS_FIDELITY, c)
            continue
        stamped = c.get("project", "")
        if not stamped:
            _drop(NO_PROJECT, c)
            continue
        if project and stamped != project:
            _drop(OTHER_PROJECT, c)
            continue
        ts = c.get("ts", "")
        w = window_for(windows, ts)
        if w is None:
            _drop(AFTER_HEAD, c)   # the only way out: newer than every window
            continue
        _place(w.sha, c, VIA_WINDOW)

    joined = sum(len(g["calls"]) for g in by_sha.values())
    return {"by_sha": by_sha,
            "joined": joined,
            "attributed": len(by_sha),
            "excluded": sorted(excluded.values(), key=lambda e: (-e["calls"], e["reason"])),
            "unattributed": [w.sha for w in windows if w.sha not in by_sha],
            "dirty_tasks": dirty}


# Why an exclusion happened, in one line each — rendered as footnotes, never dropped.
EXCLUSION_TEXT = {
    NO_TS_FIDELITY: "their source has no per-call timestamp to place on a commit",
    OTHER_PROJECT: "they are stamped with a different project",
    NO_PROJECT: "they carry no project stamp, so cage cannot confirm they are this "
                "repo's work (adopting them would pull other repos' spend onto these "
                "commits)",
    AFTER_HEAD: "they are newer than the newest commit — not committed yet",
    DANGLING_TASK: "their task's recorded commit is not in this history "
                   "(squashed, rebased or another branch) — never chased",
}
