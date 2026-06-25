"""Distribute local ledger fragments into `refs/notes/cage-ledger` (plan §3.6.3).

The team view reuses the **exact** §3.5 distribution model — buffer → notes,
merge-by-row-id, CI-sole-writer — applied to calls/receipts instead of provenance:

- Each machine's `.cage/ledger/` (the partitioned shards) is the local buffer. A
  single `refs/notes/cage-ledger` ref is the canonical shared record.
- Rows are unioned by globally-unique id (`mergeutil.union_by_id`, no method tie-break —
  call/receipt ids never legitimately collide, so first-by-id holds). This is a CRDT
  for append-only logs: two machines only ever add unique ids, never edit a shared line.
- **CI is the sole writer** (`sync` pushes only when `CAGE_NOTES_WRITE=1`, which CI sets
  and a dev machine normally doesn't). A dev's `cage ledger-sync` defaults to a dry-run.
- The aggregate rolls up by `scope` (§3.6.2), never per-developer identity by default —
  the shared artifact stays a cost/ROI ledger, not a monitoring dataset. (Per-person
  attribution is a deliberately-deferred opt-in; see the `# v2:` marker in `read_team`.)

Unlike provenance (one note per commit sha), ledger rows have no commit to attach to,
so all rows live in **one note on the repo's empty-tree object** — a universal, stable
anchor (same across machines, unlike HEAD). `cage report --team` / `attrib --team` read
the merged ref and fall back to the local buffer when it's empty/missing (fail-open).
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from cage import ledger, mergeutil

_REF = "refs/notes/cage-ledger"


def _git(root: Path, *args: str, input_text: str | None = None) -> str | None:
    try:
        out = subprocess.run(("git", "-C", str(root), *args), capture_output=True,
                             text=True, timeout=5, check=True, input=input_text)
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _anchor(root: Path) -> str | None:
    """The repo's empty-tree object id — a universal, deterministic note anchor (resolved
    via git so it's correct under both SHA-1 and SHA-256 repos), fail-open ⇒ None."""
    return _git(root, "hash-object", "-t", "tree", "/dev/null")


def _parse_rows(text: str | None) -> list[dict]:
    if not text:
        return []
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


def _existing_note(root: Path, anchor: str) -> list[dict]:
    return _parse_rows(_git(root, "notes", f"--ref={_REF}", "show", anchor))


def _local_rows(root: Path) -> list[dict]:
    """Every local call + receipt row (across all month shards). Order is stable
    (calls then receipts) so the merge plan is deterministic."""
    return [*ledger.calls(root), *ledger.receipts(root)]


def plan(root: Path) -> dict:
    """`{"existing", "incoming", "merged"}` — pure, read-only; never touches refs/notes.
    Union is plain first-by-id (no method tie-break — ledger ids don't collide)."""
    anchor = _anchor(root)
    existing = _existing_note(root, anchor) if anchor else []
    incoming = _local_rows(root)
    return {"anchor": anchor, "existing": existing, "incoming": incoming,
            "merged": mergeutil.union_by_id(existing, incoming)}


def sync(root: Path, *, write: bool | None = None) -> dict:
    """Compute the merge plan; push to refs/notes only if `write` (default: the
    `CAGE_NOTES_WRITE=1` env CI sets — never a dev machine implicitly). Mirrors
    `notessync.sync`."""
    do_write = write if write is not None else os.environ.get("CAGE_NOTES_WRITE") == "1"
    result = plan(root)
    n = len(result["merged"])
    if not do_write or not result["anchor"] or not result["merged"]:
        return {"wrote": False, "rows": n}
    body = "\n".join(json.dumps(r, ensure_ascii=False) for r in result["merged"])
    ok = _git(root, "notes", f"--ref={_REF}", "add", "-f", "-F", "-", result["anchor"],
              input_text=body)
    return {"wrote": ok is not None, "rows": n}


def read_team(root: Path) -> dict | None:
    """Merged team rows split into `{"calls", "receipts"}` by id prefix, or None when
    the ref is empty/missing (caller falls back to the local view). Default rollup is by
    `scope`; identity is not bucketed here — that's the CI merge's job.

    # v2: opt-in per-developer attribution would key/group on an author field here;
    # deliberately not built (plan §3.6.3 — scope-only default keeps it a cost ledger).
    """
    anchor = _anchor(root)
    if not anchor:
        return None
    rows = _existing_note(root, anchor)
    if not rows:
        return None
    calls = [r for r in rows if str(r.get("id", "")).startswith("c_")]
    receipts = [r for r in rows if str(r.get("id", "")).startswith("r_")]
    return {"calls": calls, "receipts": receipts}
