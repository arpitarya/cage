"""The append-only event log — read/write `calls.jsonl` + `receipts.jsonl` (plan §3).

The only mutation is append; everything else derives. Writes are best-effort
(metering must never break the request path); reads tolerate a half-written tail.
"""
from __future__ import annotations

import datetime as _dt
import json
import re
from pathlib import Path

from cage import paths
from cage.constants import SINCE_WINDOW_DAYS


def append(path: Path, row: dict) -> bool:
    """Append one JSON row. Returns False on failure rather than raising."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except OSError:
        return False


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


def calls(root: Path) -> list[dict]:
    return read(paths.Footprint(root).calls)


def receipts(root: Path) -> list[dict]:
    return read(paths.Footprint(root).receipts)


def receipts_for(root: Path, call_id: str) -> list[dict]:
    return [r for r in receipts(root) if r.get("call") == call_id]


def provenance(root: Path) -> list[dict]:
    return read(paths.Footprint(root).provenance)


def provenance_for_sha(root: Path, sha: str) -> list[dict]:
    return [r for r in provenance(root) if r.get("sha") == sha]


def by_task(rows: list[dict], task: str | None) -> list[dict]:
    return [r for r in rows if r.get("task") == task] if task else rows


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
