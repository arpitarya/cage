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

from cage import ledger, paths

_SHORTSTAT = re.compile(r"(\d+) files? changed(?:, (\d+) insertion)?(?:.*?(\d+) deletion)?")


def _git(root: Path, *args: str) -> str | None:
    """Run a read-only git command; return stripped stdout, or None on any failure."""
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def git_snapshot(root: Path) -> dict:
    """SHA / branch / diff counts / top-level dirs — fail-open, fields omitted if absent."""
    snap: dict = {}
    sha = _git(root, "rev-parse", "--short", "HEAD")
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
    return ledger.append(paths.Footprint(root).tasks, row)


def read(root: Path) -> dict[str, dict]:
    """Latest row per task id (last-write-wins) keyed by id — pure derive."""
    latest: dict[str, dict] = {}
    for r in ledger.read(paths.Footprint(root).tasks):
        if r.get("id"):
            latest[r["id"]] = {**latest.get(r["id"], {}), **r}
    return latest
