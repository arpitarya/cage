"""Observability for the capture path — $0/stdlib, off by default (plan §5, §9.5).

The capture path is fail-open everywhere: every hook entrypoint and every import
swallows exceptions, and the skip-reason strings `importcmd.run` returns are dropped
when a hook (whose stdout goes nowhere) calls it. So when capture silently does
nothing — a hook never fired, the `.cage` cwd guard skipped it, a parser raised — there
is no way to tell which. This module makes that path *observable* without changing it:

- **Strictly observational.** A logging error is swallowed (`_safe`); debugging never
  alters the ledger, never blocks a hook. Same ledger + same policy ⇒ byte-identical
  derived tables with debug on or off — `debug.log`/`hooks-seen.jsonl` are local state,
  never read by any derived view, so the clock used here doesn't touch determinism.
- **Counts-never-content.** Callers log metadata only (agent, event, cwd, resolved
  root, guard outcomes, file paths/counts, rows parsed/appended/deduped, skip reason,
  exception type+traceback). Never prompt/response bodies, never token text. The
  `transcript_path` is recorded as a presence bool, never its contents.
- **Off by default.** Env ``CAGE_DEBUG`` overrides ``policy.toml [debug] enabled``
  (default off). When off nothing is written and there is no overhead beyond a cheap
  env/flag check — no file is ever created.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import traceback as _tb
from pathlib import Path

from cage import paths, policy


def enabled(root: Path, pol: dict | None = None) -> bool:
    """Whether capture-debug logging runs. Env ``CAGE_DEBUG`` (0/1) overrides
    ``policy.toml [debug] enabled`` (default off). The env check is cheap and does no
    I/O; policy is consulted only when the env var is unset — and a caller that already
    holds ``pol`` (importcmd, session_start) passes it so no extra load happens."""
    try:
        if pol is None:
            env = os.environ.get("CAGE_DEBUG")
            if env is None:
                pol = policy.load(paths.Footprint(root).policy)
        return policy.debug_enabled(pol or {})
    except Exception:  # never let the gate raise into a hook
        return False


def _log_path(root: Path) -> Path:
    return paths.Footprint(root).debug_log


def _explicit_log() -> bool:
    """True when ``CAGE_DEBUG_LOG`` points the log at a fixed location — the supported
    way to observe a hook firing in a dir that has no ``.cage/``."""
    return bool(os.environ.get("CAGE_DEBUG_LOG"))


def _explicit_base() -> bool:
    """True when ``CAGE_BASE`` (what ``--ledger`` sets) names the active ledger root.
    ``paths.Footprint`` re-bases the whole footprint — ledger, state, debug log — onto
    that path, so the log lands *inside the sink the user named*, never beside a cwd."""
    return bool(os.environ.get("CAGE_BASE"))


def _may_write_under_cage(root: Path) -> bool:
    """Never *create* a `.cage/` just to log: writing the default `.cage/state/...` path
    in a non-cage dir would scatter a footprint that `find_project_root` then treats as a
    project. Default path writes only if `.cage/` already exists; an explicit
    ``--ledger``/``CAGE_BASE`` override or ``CAGE_DEBUG_LOG`` opts out of the guard.

    The override case is not a convenience: under ``CAGE_BASE`` (a scratch ledger — how a
    capture diagnosis reproduces without touching the real one) ``resolve_root`` returns
    the *cwd* while the footprint re-bases onto the override, so the old ``root/.cage``
    test inspected a directory unrelated to the active sink and silently suppressed every
    event — the F6 receipt produce/skip trace included. That cost the F1 diagnosis its
    instrument (`docs/regression/2026-07-24-f1-root-cause.md`). A bare cwd with neither
    ``.cage/`` nor an override is still refused, so debug never scatters."""
    return _explicit_log() or _explicit_base() or (root / ".cage").is_dir()


def _append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def event(root: Path, *, pol: dict | None = None, **fields) -> None:
    """Append one structured JSON line to the debug log (no-op when debug is off).
    Self-fail-open: a logging error is swallowed so capture survives a broken logger."""
    try:
        if not enabled(root, pol) or not _may_write_under_cage(root):
            return
        _append(_log_path(root), {"ts": _now(), **fields})
    except Exception:  # pragma: no cover — observability must never break capture
        pass


def exception(root: Path, context: str, exc: BaseException, *,
              pol: dict | None = None, **fields) -> None:
    """Record an exception that the fail-open path would otherwise have swallowed —
    its type + traceback, never any payload body."""
    try:
        event(root, pol=pol, event="exception", context=context,
              error=type(exc).__name__,
              traceback="".join(_tb.format_exception(type(exc), exc, exc.__traceback__)),
              **fields)
    except Exception:  # pragma: no cover
        pass


def heartbeat(root: Path, agent: str, event_name: str, cwd: str, *,
              pol: dict | None = None) -> None:
    """Stamp a per-(agent,event) last-seen record so "did this agent's hook ever fire?"
    is answerable without manual marker files. Append-only; readers take last-write-wins
    by ``(agent, event)``. Gated by the same switch — off ⇒ no file written."""
    try:
        # The heartbeat path is always `.cage/state/hooks-seen.jsonl` (no env override), so
        # restrict it to real cage projects — never scatter a footprint to record a firing.
        if not enabled(root, pol) or not (root / ".cage").is_dir():
            return
        _append(paths.Footprint(root).hooks_seen,
                {"agent": agent, "event": event_name, "ts": _now(), "cwd": cwd})
    except Exception:  # pragma: no cover
        pass


def _read(path: Path) -> list[dict]:
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


def last_seen(root: Path) -> dict[tuple[str, str], dict]:
    """Latest heartbeat per ``(agent, event)`` — last-write-wins over the append log."""
    out: dict[tuple[str, str], dict] = {}
    for r in _read(paths.Footprint(root).hooks_seen):
        out[(r.get("agent", ""), r.get("event", ""))] = r
    return out


def tail(root: Path, n: int = 20) -> list[dict]:
    """The last ``n`` debug events (oldest→newest), for ``cage debug``."""
    rows = _read(_log_path(root))
    return rows[-n:] if n > 0 else rows
