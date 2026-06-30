"""The single typed error cage raises for an expected, user-facing failure.

cage's write paths are constitutionally **fail-open** — they never raise into a
request/hook path (see `hooks.py`, `metering.py`, `ledger.append`). This module is
the *read / CLI boundary* counterpart: an expected failure the user can act on (a
malformed `policy.toml`, …) raises `CageError`, so `cli.main` renders a clean
`error: <message>` line and exits 1 instead of dumping a raw traceback.

There is exactly **one** error type — no hierarchy, no logging framework, no
retries (stdlib-only, `dependencies = []`). It is for surfacing, never for control
flow on a fail-open path.
"""
from __future__ import annotations

import os


class CageError(Exception):
    """An expected, user-facing failure.

    Raised at read/CLI boundaries; rendered as ``error: <msg>`` + exit 1 by
    `cli.main`. Never raised on a fail-open write path.
    """


def debug_enabled() -> bool:
    """Whether ``CAGE_DEBUG`` requests verbose CLI output (a full traceback at the
    boundary for an *unexpected* exception).

    Env-only by design: the boundary handler in `cli.main` may fire before/without a
    resolved ledger, so it does no policy/root I/O. The truthiness set matches
    `policy._flag` / `debuglog` so the one switch behaves identically everywhere.
    """
    return os.environ.get("CAGE_DEBUG", "").strip().lower() in ("1", "true", "yes", "on")
