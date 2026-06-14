"""Claude Code hook entrypoints (plan §5, §9.5) — wired by `cage hooks install`.

- SessionEnd  → parse the session transcript, append any not-yet-recorded turns
  (idempotent on the turn uuid). Off the request path: never blocks a call.
- SessionStart → print a one-line spend/budget banner; Claude Code injects hook
  stdout into context, the same way the fux INDEX is surfaced.

Every entrypoint is fail-open and exits 0 — a hook must never break the session.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import budget, ledger, paths, policy, transcript


def _stdin_json() -> dict:
    try:
        return json.loads(sys.stdin.read() or "{}")
    except (ValueError, OSError):
        return {}


def _root(payload: dict) -> Path:
    cwd = payload.get("cwd")
    start = Path(cwd) if cwd else Path.cwd()
    return paths.find_project_root(start) or start


def append_new(root: Path, rows: list[dict]) -> int:
    """Append only call rows whose id isn't already in the ledger. Returns #added."""
    seen = {c.get("id") for c in ledger.calls(root)}
    added = 0
    for row in rows:
        if row.get("id") not in seen:
            if ledger.append(paths.Footprint(root).calls, row):
                added += 1
    return added


def session_end() -> int:
    payload = _stdin_json()
    tp = payload.get("transcript_path")
    if tp:
        try:
            root = _root(payload)
            rows = transcript.parse_calls(Path(tp), session=payload.get("session_id", ""))
            append_new(root, rows)
        except Exception:  # pragma: no cover — best-effort
            pass
    return 0


def session_start() -> int:
    try:
        root = _root(_stdin_json())
        pol = policy.load(paths.Footprint(root).policy)
        v = budget.check(root, pol)
        day = v["scopes"]["day"]
        if day["used"]:
            cap = f" / ${day['cap']:.2f} cap" if day["cap"] else ""
            flag = "  ⚠ over budget" if day["over"] else ""
            print(f"Cage: ${day['used']:.4f} spent today{cap}{flag}. `cage report` for detail.")
    except Exception:  # pragma: no cover — best-effort
        pass
    return 0
