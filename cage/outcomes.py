"""The task outcome store — `.cage/outcomes.json`, task → ``ok`` | ``redo``.

**Why this module exists as its own file.** The store used to live in `quality.py`
alongside the cost-per-successful-task view (`cage task quality`). That view was money and
died with the rest of the money subsystem (USAGE-ONLY, ADR 0011); the *store* is not
money and had to survive it, because it is the write half of the one mutation cage
exposes anywhere:

- `cage task outcome` — the task-close verb the whole cost-impact surface
  (`compare`/`estimate`/`calibration`) depends on for its closed-task join.
- `cage_task_outcome` — the **only** write tool on the MCP surface
  (`mcpserver.WRITE_TOOLS`), which reaches it through `clicmds.close_task`, the single
  task-close path the CLI verb also uses.

Both go through `record_outcome` below. Deleting `quality.py` without relocating it
would have removed the task-close verb and the entire MCP write surface as collateral of
a pricing deletion.

**This is a different axis from `tasks.jsonl`'s `outcome` field, and they must not be
conflated** (CLAUDE.md, L1 hooks): a session-end hook writes `outcome="auto"` there —
closed for the join, deliberately invisible here — because a session that merely *ended*
is not a task that *succeeded*. Only an explicit `cage task outcome` reaches this store.
"""
from __future__ import annotations

import json
from pathlib import Path

from cage import paths


def _file(root: Path) -> Path:
    return paths.Footprint(root).base / "outcomes.json"


def load(root: Path) -> dict:
    """Task → ``"ok"`` | ``"redo"``. A missing or corrupt store reads empty, never
    raises — the outcome signal is best-effort and must not break a task close."""
    f = _file(root)
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def record_outcome(root: Path, task: str, ok: bool) -> None:
    data = load(root)
    data[task] = "ok" if ok else "redo"
    f = _file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
