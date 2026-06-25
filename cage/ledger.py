"""The append-only event log — read/write `calls.jsonl` + `receipts.jsonl` (plan §3).

The only mutation is append; everything else derives. Writes are best-effort
(metering must never break the request path); reads tolerate a half-written tail.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import sys
from pathlib import Path

from cage import paths
from cage.constants import LEDGER_WARN_BYTES, SINCE_WINDOW_DAYS

_warned_dirs: set[str] = set()  # ledger-size warning fires at most once per dir per process


def append(path: Path, row: dict) -> bool:
    """Append one JSON row. Returns False on failure rather than raising."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


def append_row(root: Path, kind: str, row: dict) -> bool:
    """Append a ``calls``/``receipts``/``tasks`` row to its month shard (plan §3.6.1).

    The shard is chosen from the row's own ``ts`` (`paths.Footprint.shard`), so writes
    are deterministic and the append-only past is never rewritten — new writes simply
    target dated files. Fail-open like `append`."""
    return append(paths.Footprint(root).shard(kind, row.get("ts", "")), row)


def read(path: Path) -> list[dict]:
    """All rows; a truncated final line (crash mid-append) is silently dropped."""
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    return rows


_SHARD_MONTH = re.compile(r"-(\d{4})-(\d{2})\.jsonl$")


def _month_entirely_below(name: str, cutoff: _dt.datetime) -> bool:
    """True if every instant of a dated shard's month is strictly before ``cutoff`` —
    i.e. a ``--since`` query can skip the whole file without dropping an in-window row.
    A legacy unpartitioned name (no month) returns False ⇒ never skipped."""
    m = _SHARD_MONTH.search(name)
    if not m:
        return False
    y, mo = int(m.group(1)), int(m.group(2))
    nxt = _dt.datetime(y + (mo == 12), (mo % 12) + 1, 1, tzinfo=_dt.timezone.utc)
    return nxt <= cutoff


def _warn_threshold(foot) -> int:
    """Bytes above which the ledger-size warning fires: policy ``[ledger] warn_mb``
    (MB) wins, else the derived ``LEDGER_WARN_BYTES`` fallback. Lazy policy import keeps
    the read path import-light and dodges a module cycle; any failure ⇒ the constant."""
    try:
        from cage import policy
        warn_mb = (policy.load(foot.policy).get("ledger") or {}).get("warn_mb")
        if warn_mb is not None:
            return int(float(warn_mb) * 1_000_000)
    except Exception:  # noqa: BLE001 — warn-only, never let threshold resolution raise
        pass
    return LEDGER_WARN_BYTES


def _warn_if_large(foot, shards: list[Path]) -> None:
    """One stderr line when the globbed shard bytes cross the threshold (plan §3.6.4 (d)).

    Warn-only and fail-open: never touches stdout (the deterministic table surface),
    never blocks or raises, swallows a `stat` error, and fires at most once per ledger
    dir per process. The remedy it points at — archive old shards / `ledger-sync` —
    acts on total size, matching the metric. A `block` mode is deliberately absent: a
    derive never refuses (flux invariant); see the ADR for the write-path discussion."""
    try:
        key = str(foot.ledger)
        if key in _warned_dirs:
            return
        total = 0
        for sh in shards:
            try:
                total += sh.stat().st_size
            except OSError:
                continue
        if total > _warn_threshold(foot):
            _warned_dirs.add(key)
            print(f"cage: ledger is {total / 1_000_000:.0f} MB across {len(shards)} "
                  f"shard(s) — derives stay fast but history is unbounded; archive old "
                  f"*-YYYY-MM.jsonl shards or run `cage ledger-sync` then prune.",
                  file=sys.stderr)
    except Exception:  # noqa: BLE001 — the warning must never perturb a read
        return


def read_kind(root: Path, kind: str, *, since: str | None = None) -> list[dict]:
    """Glob + concatenate every shard for ``kind`` (legacy file + dated months, plan
    §3.6.1). With ``since`` set, dated shards whose whole month predates the cutoff are
    skipped *before* loading — the point of the partition (bounded re-scan), not just a
    row filter. Per-shard truncated-tail tolerance holds (each `read` drops a partial
    final line). The in-memory row stream is identical to a single concatenated log."""
    foot = paths.Footprint(root)
    shards = foot.shards(kind)
    _warn_if_large(foot, shards)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in shards:
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    return rows


def calls(root: Path, since: str | None = None) -> list[dict]:
    return read_kind(root, "calls", since=since)


def receipts(root: Path, since: str | None = None) -> list[dict]:
    return read_kind(root, "receipts", since=since)


def receipts_for(root: Path, call_id: str) -> list[dict]:
    return [r for r in receipts(root) if r.get("call") == call_id]


def provenance(root: Path) -> list[dict]:
    return read(paths.Footprint(root).provenance)


def provenance_for_sha(root: Path, sha: str) -> list[dict]:
    return [r for r in provenance(root) if r.get("sha") == sha]


def by_task(rows: list[dict], task: str | None) -> list[dict]:
    return [r for r in rows if r.get("task") == task] if task else rows


def by_scope(rows: list[dict], scope: str | None) -> list[dict]:
    """Filter to one `scope` (top-level dir, plan §3.6.2). `None`/"" ⇒ unfiltered, so a
    missing `--scope` flag yields the exact pre-§3.6 row set (no-flag byte-identity)."""
    return [r for r in rows if r.get("scope") == scope] if scope else rows


_SINCE = re.compile(r"^(\d+)([dhw])$")
_UNIT = SINCE_WINDOW_DAYS


def since_cutoff(spec: str | None) -> _dt.datetime | None:
    """Parse a ``7d`` / ``24h`` / ``2w`` window into an aware UTC cutoff."""
    if not spec:
        return None
    m = _SINCE.match(spec.strip())
    if not m:
        return None
    days = int(m.group(1)) * _UNIT[m.group(2)]
    return _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)


def _ts(row: dict) -> _dt.datetime | None:
    try:
        return _dt.datetime.fromisoformat(row["ts"].replace("Z", "+00:00"))
    except (KeyError, ValueError, AttributeError):
        return None


def since(rows: list[dict], spec: str | None) -> list[dict]:
    cut = since_cutoff(spec)
    if cut is None:
        return rows
    return [r for r in rows if (t := _ts(r)) and t >= cut]
