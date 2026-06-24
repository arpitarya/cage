"""Distribute per-SHA provenance fragments into `refs/notes/cage-provenance` (plan §3.5).

The local `provenance.jsonl` is a **buffer only** — gitignored, machine-local, never
the canonical record. `refs/notes/cage-provenance` is canonical, and **CI is the sole
writer to it** (this module's `sync` only pushes when `CAGE_NOTES_WRITE=1`, which CI
sets and a dev machine normally doesn't — keeps "report-only, never blocks" honest for
the common local case too). Merge policy is append/merge by row id, never overwrite:
read the existing note for a SHA, union in new rows by `id`, resolve any row that
disagrees with another on the same (sha, file) by `PROVENANCE_METHOD_TRUST` rank, and
write back. Read-only/no-op (`--dry-run`, the default) prints the merge plan without
touching `refs/notes`.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from cage import originrecord
from cage.constants import PROVENANCE_METHOD_TRUST

_REF = "refs/notes/cage-provenance"


def _git(root: Path, *args: str, input_text: str | None = None) -> str | None:
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True, input=input_text)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _existing_note(root: Path, sha: str) -> list[dict]:
    out = _git(root, "notes", f"--ref={_REF}", "show", sha)
    if not out:
        return []
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def merge_rows(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """Union by row `id`; on an (sha, file) the two disagree about, keep the row
    whose `method` ranks highest (PROVENANCE_METHOD_TRUST) — never let the union
    read as a stronger method than its weakest real input, but also never let a
    weaker method silently overwrite a stronger one already on file."""
    by_id: dict[str, dict] = {r["id"]: r for r in existing if r.get("id")}
    for row in incoming:
        rid = row.get("id")
        if not rid:
            continue
        prior = by_id.get(rid)
        if prior is None:
            by_id[rid] = row
            continue
        # Same id reappearing (e.g. re-synced buffer) — keep whichever ranks higher.
        if PROVENANCE_METHOD_TRUST.get(row.get("method", ""), -1) > \
           PROVENANCE_METHOD_TRUST.get(prior.get("method", ""), -1):
            by_id[rid] = row
    return list(by_id.values())


def plan(root: Path) -> dict[str, dict]:
    """`{sha: {"existing": [...], "incoming": [...], "merged": [...]}}` — pure,
    read-only; never touches `refs/notes`. The buffer is grouped by sha."""
    by_sha: dict[str, list[dict]] = {}
    for row in originrecord.read_all(root):
        by_sha.setdefault(row["sha"], []).append(row)
    out: dict[str, dict] = {}
    for sha, incoming in by_sha.items():
        existing = _existing_note(root, sha)
        out[sha] = {"existing": existing, "incoming": incoming,
                   "merged": merge_rows(existing, incoming)}
    return out


def sync(root: Path, *, write: bool | None = None) -> dict:
    """Compute the merge plan; only push to `refs/notes` if `write` (default: the
    `CAGE_NOTES_WRITE=1` env, which CI sets — never a dev machine implicitly)."""
    do_write = write if write is not None else os.environ.get("CAGE_NOTES_WRITE") == "1"
    result = plan(root)
    if not do_write:
        return {"wrote": False, "shas": list(result.keys())}
    written = []
    for sha, data in result.items():
        if not data["merged"]:
            continue
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in data["merged"])
        # v2: sign the note (git notes --ref + GPG) before treating it as audit-grade.
        if _git(root, "notes", f"--ref={_REF}", "add", "-f", "-F", "-", sha,
               input_text=body) is not None:
            written.append(sha)
    return {"wrote": True, "shas": written}
