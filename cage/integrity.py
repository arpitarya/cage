"""Tamper-evidence for the append-only files — a hash chain, checkpointed, report-only.

**The question this answers:** did anything that was already written change? Under the
append-only law a recorded row is never edited, so a changed prefix is the one signal that
means something went wrong — a bad merge, a hand-edit, a corrupted disk, a script that
"cleaned up" the ledger. Everything else that moves is growth.

## Why a chain, and why checkpointed

A full-file digest recomputed per append is O(n) per row on a hot, fail-open capture path
over a multi-MB ledger. So the digest is a **chain over appended segments** —
``current = sha256(previous ‖ appended_bytes)`` — which costs O(delta) to advance.

**And it advances at SWEEP boundaries, not per row.** `ledger.append_row` is untouched:
`checkpoint()` is called once at the end of an import — its sole caller is
`importcmd.py`; `cage doctor` reads the manifest but never checkpoints it (an earlier
draft did; see `doctorcmd.py`'s comment on why that changed). Two reasons,
both load-bearing. The hot path stays exactly as fast and exactly as fail-open as it was;
and the segment list stays short (one entry per sweep, not one per row), which matters
because **verification replays it**.

Verification is O(n) — it re-reads each file and replays the recorded segmentation. That is
the right trade and it is the one the design constraint actually asked for: *appends* must
not be O(n); a `cage doctor` run already reads the ledger. Replaying rather than comparing
a stored digest is what makes this detect a change **anywhere** in the file, not just at
the tail.

## What it reports, and what it never does

Two verdicts, deliberately never blended into one scary word:

* ``altered-history`` — the replay diverges over bytes that were already recorded. Under
  append-only this is **never legitimate**. It is the only real tamper signal.
* ``damaged`` — the file is shorter than recorded, or a segment cannot be read to its
  recorded length. A crash mid-write does this, and `ledger.read` already **tolerates a
  truncated tail** by design. Reporting it as tampering would turn a documented fail-open
  behaviour into an alarm.

Plus two non-findings that are as important as the findings:

* ``unverified`` — the lock was missed while recording, so the segment boundary may not
  reflect one atomic append. **A lock miss marks a segment, it never breaks the chain.**
  `lockutil`'s contract is that the lock closes a wasted-work window and **proceeds
  unlocked**; making it load-bearing here would quietly promote it to a correctness
  guarantee it is not built to be. A stated unknown beats a fabricated verdict.
* ``expected`` — files that are rewritten or pruned **by design**: `cursors.json` is
  rewritten wholesale every import, and the logs are size-managed by cleanup. Classifying
  those as findings would make the report cry wolf on every run, and a report its reader
  learns to ignore is worse than no report.

**Report-only, always.** The precedent is `cage authorship verify`, which is report-only
and always exits 0. This never refuses a read, never blocks a write, and never changes an
exit code — it surfaces in `cage doctor` and nowhere else.

**Never read by a derived view.** The manifest lives in `state/`, is protected by
`cleanup.NEVER`, and is **excluded from its own hashing** (a manifest cannot hash itself).
Deleting the whole thing must move zero numeric cells.

**Determinism:** the chain is a function of file bytes only. A `ts` is recorded as
metadata and never enters a hash.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cage import lockutil, paths

#: The chain's starting value. A fixed, non-empty genesis so an empty file's chain is
#: distinguishable from "never recorded" — `sha256(b"")` would collide with a plausible
#: accident.
GENESIS = "cage-integrity-v1"

#: Files that are rewritten or pruned **by design**. Matched on the manifest's relative
#: path. Their entries are still chained (so growth is still tracked) but a divergence is
#: reported as ``expected`` rather than as a finding.
#:
#: This list is the difference between a report someone reads and a report someone mutes.
BY_DESIGN = ("state/cursors.json", "state/debug.log", "state/capture.log",
             "state/hooks-seen.jsonl", "state/graphify-usage.jsonl")

#: Never chained: the manifest itself (it cannot hash itself — recording would change the
#: bytes it just hashed), and its lock.
_SELF = ("state/integrity.json", "state/integrity.lock")

_OK, _ALTERED, _DAMAGED, _UNVERIFIED, _EXPECTED = (
    "ok", "altered-history", "damaged", "unverified", "expected")


def _tracked(root: Path) -> list[Path]:
    """Every append-only file worth chaining, in a deterministic order.

    Ledger data **and** `state/` — decision 10.8. `state/` is in because the question is
    *did something change what was already written*, and a rewritten cursor file is
    exactly as interesting to a person debugging a capture gap as a rewritten shard; the
    `BY_DESIGN` list is what keeps it from being noise."""
    foot = paths.Footprint(root)
    out: list[Path] = []
    if foot.ledger.is_dir():
        out.extend(p for p in foot.ledger.rglob("*.jsonl") if p.is_file())
    if foot.state.is_dir():
        out.extend(p for p in foot.state.iterdir()
                   if p.is_file() and p.suffix in (".json", ".jsonl", ".log"))
    return sorted(set(out))


def _rel(root: Path, path: Path) -> str:
    try:
        return path.relative_to(paths.Footprint(root).base).as_posix()
    except ValueError:
        return path.as_posix()


def _chain(prev: str, blob: bytes) -> str:
    return hashlib.sha256(prev.encode("utf-8") + blob).hexdigest()


def manifest_path(root: Path) -> Path:
    return paths.Footprint(root).state / "integrity.json"


def read_manifest(root: Path) -> dict:
    """The recorded chain state; ``{}`` when absent or unreadable. Fail-open — a
    diagnostic must never be the thing that breaks."""
    try:
        return json.loads(manifest_path(root).read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return {}


def checkpoint(root: Path) -> dict:
    """Advance the chain for every tracked file; return the updated manifest.

    Called at the end of an import sweep — `importcmd.py` is its sole caller. `cage
    doctor` reads the manifest but never checkpoints it. **Fail-open throughout** —
    every failure mode leaves the previous manifest intact and returns it.

    A file that SHRANK is not chained further: its recorded state is preserved so `verify`
    can report the truncation rather than quietly adopting the shorter file as the new
    truth. That is the whole point of recording anything.
    """
    entries = read_manifest(root)
    missed = {"v": False}

    def _on_miss(_exc):
        missed["v"] = True

    try:
        with lockutil.locked(paths.Footprint(root).state / "integrity.lock", on_miss=_on_miss):
            for path in _tracked(root):
                rel = _rel(root, path)
                if rel in _SELF:
                    continue
                try:
                    size = path.stat().st_size
                except OSError:
                    continue
                e = entries.get(rel) or {"size": 0, "current": GENESIS, "segments": []}
                recorded = int(e.get("size", 0))
                if size == recorded:
                    continue
                if size < recorded:
                    # Truncated. Leave the entry alone — `verify` reports it.
                    e["shrank"] = True
                    entries[rel] = e
                    continue
                try:
                    with path.open("rb") as fh:
                        fh.seek(recorded)
                        blob = fh.read(size - recorded)
                except OSError:
                    continue
                e = {"size": recorded + len(blob),
                     "prev": e.get("current", GENESIS),
                     "current": _chain(e.get("current", GENESIS), blob),
                     "segments": list(e.get("segments", [])) + [len(blob)],
                     # A lock miss taints only the segments recorded under it. It never
                     # resets the chain — `unverified` is a stated unknown, not a break.
                     "unverified": bool(e.get("unverified")) or missed["v"]}
                entries[rel] = e
            _write(root, entries)
    except Exception:  # noqa: BLE001 — never raises into capture
        return entries
    return entries


def _write(root: Path, entries: dict) -> bool:
    try:
        p = manifest_path(root)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(entries, indent=1, sort_keys=True) + "\n",
                     encoding="utf-8")
        return True
    except OSError:
        return False


def verify(root: Path) -> list[dict]:
    """Replay every recorded chain and classify each file. **Never raises, never gates.**

    Returns one dict per tracked entry: ``{path, verdict, detail}``. An entry with no
    recorded state is skipped rather than reported — "not yet checkpointed" is not a
    finding, and reporting it would make a first run look like a disaster.
    """
    out: list[dict] = []
    entries = read_manifest(root)
    base = paths.Footprint(root).base
    for rel, e in sorted(entries.items()):
        path = base / rel
        expected = rel in BY_DESIGN
        try:
            size = path.stat().st_size
        except OSError:
            out.append({"path": rel, "verdict": _EXPECTED if expected else _DAMAGED,
                        "detail": "recorded but no longer on disk"})
            continue
        recorded = int(e.get("size", 0))
        if size < recorded or e.get("shrank"):
            out.append({"path": rel, "verdict": _EXPECTED if expected else _DAMAGED,
                        "detail": f"shorter than recorded ({size} < {recorded} bytes) — "
                                  "a crash mid-write does this, and `ledger.read` "
                                  "tolerates a truncated tail by design"})
            continue
        # Replay the recorded segmentation over the recorded prefix. Bytes appended SINCE
        # the last checkpoint are deliberately not replayed — they are growth, not history.
        chain = GENESIS
        try:
            with path.open("rb") as fh:
                for n in e.get("segments", []):
                    blob = fh.read(n)
                    if len(blob) != n:
                        raise EOFError
                    chain = _chain(chain, blob)
        except (OSError, EOFError):
            out.append({"path": rel, "verdict": _EXPECTED if expected else _DAMAGED,
                        "detail": "a recorded segment could not be read to its length"})
            continue
        if chain != e.get("current"):
            out.append({"path": rel,
                        "verdict": _EXPECTED if expected else _ALTERED,
                        "detail": ("bytes that were already recorded no longer hash the "
                                   "same — under the append-only law a written row is "
                                   "never edited") if not expected else
                                  "rewritten by design (cursor/log), not a finding"})
            continue
        if e.get("unverified"):
            out.append({"path": rel, "verdict": _UNVERIFIED,
                        "detail": "a segment was recorded without the lock — the "
                                  "boundary may not be one atomic append. The chain is "
                                  "intact; this is a stated unknown, not a mismatch"})
            continue
        out.append({"path": rel, "verdict": _OK, "detail": f"{size} bytes chained"})
    return out


def findings(root: Path) -> list[dict]:
    """Only the rows a person should act on — `altered-history` and `damaged`.

    `ok`, `expected` and `unverified` are deliberately excluded: the first is noise, the
    second is designed behaviour, and the third is an admitted gap rather than a defect."""
    return [r for r in verify(root) if r["verdict"] in (_ALTERED, _DAMAGED)]
