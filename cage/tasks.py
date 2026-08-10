"""`tasks.jsonl` — one append-only row per task (design §5b.2, decision E).

A task is a first-class entity calls/receipts reference by id but nothing described.
Read = last-write-wins by `id` at derive time (append, never mutate). The git
snapshot is shelled out, never imported, and **fail-open**: no repo / no git /
detached HEAD omits those fields and never raises (write-path discipline).
PII guard (§5b.5): SHA + numeric diff counts + top-level dirs only — never the
commit message, author identity, or file contents.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from cage import ledger

_SHORTSTAT = re.compile(r"(\d+) files? changed(?:, (\d+) insertion)?(?:.*?(\d+) deletion)?")


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command; return stripped stdout, or None on any failure.

    **`core.quotePath=false` is not optional here.** With git's default, any path
    containing a non-ASCII byte is emitted C-quoted — `"caf\\303\\251.py"` rather than
    `café.py` — so every downstream path parse silently misses. It is passed as `-c`
    *before* the subcommand, which is the only position git accepts, and set here rather
    than at each call site so a new git read cannot forget it."""
    try:
        out = subprocess.run(("git", "-C", str(root), "-c", "core.quotePath=false",
                              *args), capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def git_snapshot(root: Path) -> dict:
    """SHA / branch / diff counts / top-level dirs — fail-open, fields omitted if absent."""
    snap: dict = {}
    # FULL sha: an abbreviation's length grows with the repo, so a short `commit`
    # written today stops comparing equal to one written later. Readers join through
    # `commitjoin.prefix_match`, which keeps already-written short rows working.
    sha = _git(root, "rev-parse", "HEAD")
    if sha:
        snap["commit"] = sha
    branch = _git(root, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":  # detached HEAD ⇒ omit, don't store the literal
        snap["branch"] = branch
    stat = _git(root, "diff", "--shortstat")
    if stat and (m := _SHORTSTAT.search(stat)):
        snap["files_changed"] = int(m.group(1))
        snap["insertions"] = int(m.group(2) or 0)
        snap["deletions"] = int(m.group(3) or 0)
    names = _git(root, "diff", "--name-only")
    if names:
        dirs = sorted({n.split("/", 1)[0] for n in names.splitlines() if n})
        if dirs:
            snap["dirs"] = dirs  # top-level only (decision F) — never full paths
    return snap


def scope_for(root: Path) -> str:
    """The single top-level changed dir of the working tree, for `scope` (plan §3.6.2).

    Reuses `git_snapshot`'s `dirs` (the same top-level-dirs-only PII guard, decision F)
    — no new git code path. A monorepo commit touching exactly one component resolves to
    that component; a multi-dir or empty diff (or non-repo) resolves to `""` (unknown),
    fail-open. Deterministic: derived from git, never a clock."""
    dirs = git_snapshot(root).get("dirs") or []
    return dirs[0] if len(dirs) == 1 else ""


def record(root: Path, task: str, *, type: str = "", outcome: str = "",
           agents: list[str] | None = None, ts: str | None = None,
           snapshot: bool = True, **extra) -> bool:
    """Append one task row (git snapshot folded in unless disabled). Fail-open."""
    from cage import schema
    row = {"id": task, "ts": ts or schema._now()}
    if type:
        row["type"] = type
    if outcome:
        row["outcome"] = outcome
    if agents:
        row["agents"] = sorted(set(agents))
    row.update({k: v for k, v in extra.items() if v not in (None, "", [])})
    if snapshot:
        row.update(git_snapshot(root))
    return ledger.append_row(root, "tasks", row)


_DURATION = re.compile(r"^(?:(\d+)\s*h)?\s*(?:(\d+)\s*m(?:in)?)?$", re.IGNORECASE)


def parse_duration(spec: str) -> int:
    """A human duration → **whole minutes**. Raises ``ValueError`` on anything else.

    Accepts ``45m`` · ``90`` (bare digits are minutes) · ``2h`` · ``1h30m`` ·
    ``1h 30min``. Deliberately narrow, and deliberately **strict rather than
    fail-open**: this is the one number on the authorship surfaces a human asserts
    outright, so a typo must be rejected at the CLI boundary rather than silently
    become a different figure. `0` is rejected too — "I spent no time on this" is not
    an attestation, it is the absence of one, and absence is already how cage says
    unknown.

    Days are not a unit here. A commit-scale attestation measured in days is a
    different claim (and would sail past `max_est_gap` on the estimator side); if that
    turns out to be a real workflow it earns its own decision, not a silent `d`."""
    s = (spec or "").strip()
    if s.isdigit():
        mins = int(s)
    else:
        m = _DURATION.match(s)
        if not m or not (m.group(1) or m.group(2)):
            raise ValueError(f"cannot read {spec!r} as a duration — use 45m, 2h, "
                             f"1h30m, or a bare number of minutes")
        mins = int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    if mins <= 0:
        raise ValueError("a duration must be greater than zero — an attestation of "
                         "no time is the absence of one, which cage already reads "
                         "as unknown")
    return mins


def read(root: Path) -> dict[str, dict]:
    """Latest row per task id (last-write-wins) keyed by id — pure derive."""
    latest: dict[str, dict] = {}
    for r in ledger.read_kind(root, "tasks"):
        if r.get("id"):
            latest[r["id"]] = {**latest.get(r["id"], {}), **r}
    return latest
