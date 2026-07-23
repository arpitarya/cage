"""Always-on capture breadcrumb — `state/capture.log` (plan F6, docs/debugging-capture.md).

F1 (zero real savings receipts) was undiagnosable because there was no log of *why*
a receipt wasn't filed — this module is half the instrument that fixes that (the
other half is the `CAGE_DEBUG`-gated produce/skip logging at the receipt sites). This
one is deliberately **always on**, not gated by `CAGE_DEBUG`: it's the standing proof
that capture ran at all, one line per agent per real import run —
``ts · agent · files_seen · rows_new · rows_total · src``.

**Strictly observational**, same discipline as `debuglog.py`: counts-never-content
(``src`` is a tilde-relative path, never contents), never read by any derived view (a
report/attrib/matrix table is byte-identical whether this writes or not), and
fail-open — a write error is swallowed and traced under `CAGE_DEBUG` so a broken log
can never break an import. Pruned by the `capture-log` cleanup class (`cleanup.py`);
it is prunable state, not permanent record.
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from cage import debuglog, paths


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def record(root: Path, agent: str, *, files_seen: int, rows_new: int,
           rows_total: int, src: str) -> None:
    """Append one breadcrumb line for `agent`'s sweep this run. Always on — no
    `CAGE_DEBUG` gate. Fail-open: a write error never breaks the import that
    triggered it; the failure itself is traced under `CAGE_DEBUG`."""
    try:
        path = paths.Footprint(root).capture_log
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": _now(), "agent": agent, "files_seen": files_seen,
               "rows_new": rows_new, "rows_total": rows_total, "src": src}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover — observability must never break capture
        debuglog.exception(root, "capture.log", e, agent=agent)


def tail(root: Path, n: int = 20) -> list[dict]:
    """The last `n` breadcrumb rows (oldest→newest) — the raw feed behind a future
    `cage doctor` view; also what `cage doctor --bundle` ships as `state/capture.log`."""
    path = paths.Footprint(root).capture_log
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
    return rows[-n:] if n > 0 else rows
