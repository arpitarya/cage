"""Always-on graphify usage breadcrumb — `state/graphify-usage.jsonl` (graphify-capture
plan GC1).

The 0-real-receipts mystery (F1) had no way to tell *"graphify ran 47×, 3 receipts,
44 unmeasurable"* from *"graphify never ran"* — a parse-miss files no receipt (right
for savings, never fabricate), so real usage went invisible. This module fixes the
observability half: **one row per graphify run** on every route (PATH/native shim,
`cage interceptor graphify`, transcript-detected at import), recording
``ts · op · args_hash · exit · ms · outcome`` — never the query text.

Discipline mirrors `capturelog.py` exactly:

- **counts-never-content** — ``args_hash`` is a sha1 of the argv, never the argv;
- **never read by any derived view** — it lives in `state/`, which no report/attrib/
  roi/matrix table ever reads, so a usage row cannot change a reported number (the
  cleanup allowlist already guarantees this for `state/`, and GC1 tests it anyway);
- **always on** — not gated by `CAGE_DEBUG`; it's the standing proof-of-usage;
- **fail-open** — a write error is swallowed and traced under `CAGE_DEBUG`, never
  raised into graphify's own result or an import.

Pruned by the `usage-log` cleanup class (`cleanup.py`) — prunable state, not record.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
from pathlib import Path

from cage import debuglog, paths

# The closed set of outcomes a graphify run can have — a usage row's only verdict.
OUTCOMES = ("receipt", "unmeasurable", "empty", "non-measured", "error")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def args_hash(argv) -> str:
    """A sha1 of the graphify argv — counts-never-content: the row records *that* a
    query ran and a stable key for it, never the query text. Deterministic and short;
    the same argv always hashes the same, so a re-run is recognizable without the words."""
    joined = "\x00".join(str(a) for a in (argv or []))
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:16]


def record(root: Path, *, op: str, args_hash: str, exit: int, ms: int,
           outcome: str, route: str = "") -> None:
    """Append one graphify usage row. Always on (no `CAGE_DEBUG` gate). Fail-open: a
    write error never breaks graphify or the import that triggered it; the failure is
    traced under `CAGE_DEBUG`. ``outcome`` is one of :data:`OUTCOMES`; ``route`` names
    which capture path saw the run (``shim``/``native``/``transcript``) for diagnosis."""
    try:
        path = paths.Footprint(root).usage_log
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": _now(), "op": op, "args_hash": args_hash, "exit": int(exit),
               "ms": int(ms), "outcome": outcome}
        if route:
            row["route"] = route
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception as e:  # pragma: no cover — observability must never break capture
        debuglog.exception(root, "usage.log", e)


def read(root: Path) -> list[dict]:
    """Every usage row, oldest→newest. Tolerates a truncated tail (a crash mid-write)."""
    path = paths.Footprint(root).usage_log
    if not path.exists():
        return []
    rows = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        return rows
    return rows


def summary(root: Path) -> dict:
    """The counts `cage doctor` renders: total runs and a per-outcome tally — the one
    sentence F1 lacked (*"graphify ran N×, R receipts, U unmeasurable"*). Derived from
    the breadcrumb only; never touches a money view."""
    rows = read(root)
    tally = {o: 0 for o in OUTCOMES}
    for r in rows:
        o = r.get("outcome", "")
        if o in tally:
            tally[o] += 1
    return {"runs": len(rows), "outcomes": tally}
