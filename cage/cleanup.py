"""State-dir maintenance — a CLOSED allowlist over `.cage/state/` (plan §3.6.4).

`.cage/state/` accumulates files nothing prunes: `debug.log` and
`hooks-seen.jsonl` grow unbounded, per-session provenance buffers go stale when a
session never commits (their transcript fallback already ran at SessionEnd),
cursors outlive deleted source logs, tmp files linger. This module ages them out.

What may be cleaned is closed **by construction** — `scan` only ever looks at:

- ``debug-log``      — `debug.log` rows older than the window (current rows kept);
- ``capture-log``    — `capture.log` rows older than the window (current rows kept);
- ``hooks-seen``     — `hooks-seen.jsonl` rows older than the window;
- ``pending-buffer`` — `pending-*.jsonl` session buffers untouched for the window;
- ``cursor-orphan``  — `cursors.json` entries whose source log no longer exists
  (safe by design: the next import re-reads the whole log, id-dedupe absorbs it);
- ``tmp``            — `state/*.tmp` older than the window.

Never cleanable — enforced by the allowlist, not convention: anything in
``ledger/``, ``policy.toml``, ``outcomes``, the machine id (fleet pairing breaks
without it), ``study.jsonl``, ``limits.json``. State files are never read by
derived views, so cleanup cannot change a single reported number.

Two paths: **auto** (`maybe_run`, piggybacked on `cage import` — cage installs no
scheduler — throttled to one real check per `CLEANUP_THROTTLE_HOURS`, entirely
fail-open: an error is debug-logged under ``cleanup.prune`` and never blocks
capture) and **manual** (`cage data cleanup`, dry-run print by default, ``--apply`` to
execute). Retention: policy ``[cleanup] days`` (`constants.CLEANUP_DEFAULT_DAYS`
fallback); the whole feature gates on `policy.cleanup_enabled` (env
``CAGE_CLEANUP`` beats policy).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path

from cage import debuglog, lockutil, paths, policy
from cage.constants import CLEANUP_THROTTLE_HOURS

CLASSES = ("debug-log", "capture-log", "hooks-seen", "pending-buffer", "cursor-orphan", "tmp")

# Temp suffix for the atomic line-file rewrites below — deliberately NOT `.tmp`,
# so a crash mid-rewrite can never leave a file the next run classifies as
# cleanable tmp and deletes while it is being written.
_REWRITE_SUFFIX = ".cleanup-new"
_STAMP = "cleanup.stamp"


def _now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _cutoff_iso(days: int) -> str:
    """ISO cutoff; write-path only (a clock never feeds a derived view)."""
    return (_now() - _dt.timedelta(days=days)).isoformat()


def _age_days(path: Path) -> float:
    return max(0.0, (_now().timestamp() - path.stat().st_mtime) / 86400.0)


def _aged_rows(path: Path, cutoff: str) -> tuple[int, int]:
    """(stale, total) JSON rows by their own ``ts`` field; unparseable rows and
    rows with no ts are kept (never delete what can't be dated)."""
    stale = total = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            ts = str(json.loads(line).get("ts", ""))
        except ValueError:
            continue
        if ts and ts < cutoff:
            stale += 1
    return stale, total


def scan(root: Path, pol: dict, days: int | None = None) -> list[dict]:
    """What cleanup would touch: ``[{path, cls, age_days, action, detail}]``,
    sorted ``(cls, path)`` — deterministic given the same file state. Read-only."""
    foot = paths.Footprint(root)
    if not foot.state.exists():
        return []
    window = days if days is not None else policy.cleanup_days(pol)
    cutoff = _cutoff_iso(window)
    found: list[dict] = []

    for cls, path in (("debug-log", foot.debug_log), ("capture-log", foot.capture_log),
                      ("hooks-seen", foot.hooks_seen)):
        try:
            if path.exists() and path.is_file():
                stale, total = _aged_rows(path, cutoff)
                if stale:
                    found.append({"path": str(path), "cls": cls,
                                  "age_days": round(_age_days(path), 1),
                                  "action": "rewrite",
                                  "detail": f"drop {stale} of {total} rows > {window}d"})
        except OSError:
            continue

    for buf in sorted(foot.state.glob("pending-*.jsonl")):
        try:
            age = _age_days(buf)
            if age > window:
                found.append({"path": str(buf), "cls": "pending-buffer",
                              "age_days": round(age, 1), "action": "delete",
                              "detail": "stale session buffer (transcript fallback "
                                        "already ran at SessionEnd)"})
        except OSError:
            continue

    try:
        if foot.cursors.exists():
            cursors = json.loads(foot.cursors.read_text(encoding="utf-8"))
            orphans = [f"{agent}: {src}"
                       for agent, table in cursors.items()
                       if isinstance(table, dict)
                       for src in table
                       if os.path.isabs(src) and not Path(src).exists()]
            if orphans:
                found.append({"path": str(foot.cursors), "cls": "cursor-orphan",
                              "age_days": round(_age_days(foot.cursors), 1),
                              "action": "rewrite",
                              "detail": f"drop {len(orphans)} cursor(s) whose source "
                                        f"log is gone (next import re-reads; id-dedupe "
                                        f"absorbs it)"})
    except (OSError, ValueError):
        pass

    for tmp in sorted(foot.state.glob("*.tmp")):
        try:
            age = _age_days(tmp)
            if age > window:
                found.append({"path": str(tmp), "cls": "tmp",
                              "age_days": round(age, 1), "action": "delete",
                              "detail": "leftover temp file"})
        except OSError:
            continue

    return sorted(found, key=lambda i: (i["cls"], i["path"]))


def _rewrite_lines(path: Path, keep) -> None:
    """Atomic line-filter rewrite: temp file (non-`.tmp` suffix) then os.replace."""
    kept = [line for line in path.read_text(encoding="utf-8").splitlines()
            if keep(line)]
    tmp = path.with_name(path.name + _REWRITE_SUFFIX)
    tmp.write_text("".join(k + "\n" for k in kept), encoding="utf-8")
    os.replace(tmp, path)


def _apply_item(foot: paths.Footprint, item: dict, cutoff: str) -> None:
    path = Path(item["path"])
    if item["action"] == "delete":
        path.unlink(missing_ok=True)
        return
    if item["cls"] in ("debug-log", "capture-log", "hooks-seen"):
        def keep(line: str) -> bool:
            line = line.strip()
            if not line:
                return False
            try:
                ts = str(json.loads(line).get("ts", ""))
            except ValueError:
                return True  # never delete what can't be dated
            return not ts or ts >= cutoff
        _rewrite_lines(path, keep)
        return
    if item["cls"] == "cursor-orphan":
        cursors = json.loads(path.read_text(encoding="utf-8"))
        for agent, table in list(cursors.items()):
            if not isinstance(table, dict):
                continue
            cursors[agent] = {src: sig for src, sig in table.items()
                              if not (os.path.isabs(src) and not Path(src).exists())}
        tmp = path.with_name(path.name + _REWRITE_SUFFIX)
        tmp.write_text(json.dumps(cursors, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path)


def prune(root: Path, pol: dict, days: int | None = None,
          items: list[dict] | None = None) -> dict:
    """Apply `scan` under the cleanup lock; per-item fail-open (an error is
    debug-logged under ``cleanup.prune``, the rest still prune). Returns counts
    per class."""
    foot = paths.Footprint(root)
    window = days if days is not None else policy.cleanup_days(pol)
    cutoff = _cutoff_iso(window)
    counts: dict[str, int] = {}
    with lockutil.locked(foot.state / "cleanup.lock"):
        for item in (items if items is not None else scan(root, pol, days)):
            try:
                _apply_item(foot, item, cutoff)
                counts[item["cls"]] = counts.get(item["cls"], 0) + 1
            except Exception as e:  # noqa: BLE001 — fail-open, but never silent
                debuglog.exception(root, "cleanup.prune", e, pol=pol,
                                   path=item.get("path", ""))
    return counts


def maybe_run(root: Path, pol: dict) -> None:
    """The auto path, piggybacked on `cage import`/hook sweeps (cage installs no
    scheduler): a cheap staleness check (one stat on the throttle stamp), then a
    fail-open prune. Never raises — capture must survive a broken cleanup."""
    try:
        if not policy.cleanup_enabled(pol):
            return
        foot = paths.Footprint(root)
        if not foot.state.exists():
            return
        stamp = foot.state / _STAMP
        if stamp.exists():
            fresh = (_now().timestamp() - stamp.stat().st_mtime) < CLEANUP_THROTTLE_HOURS * 3600
            if fresh:
                return
        prune(root, pol)
        stamp.write_text(_now().isoformat(), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 — fail-open, but never silent
        debuglog.exception(root, "cleanup.prune", e, pol=pol)


def run_cli(root: Path, pol: dict, apply: bool = False,
            days: int | None = None) -> tuple[dict, str]:
    """`cage data cleanup` — dry-run table by default (house pattern), ``--apply``
    executes. ``(payload, text)`` for the emit helper."""
    enabled = policy.cleanup_enabled(pol)
    window = days if days is not None else policy.cleanup_days(pol)
    items = scan(root, pol, days)
    payload = {"enabled": enabled, "days": window, "items": items,
               "applied": None}
    if not items:
        return payload, (f"✔ nothing stale in state/ (window: {window}d) — the "
                         "ledger, policy, machine id, study markers and limits are "
                         "never cleanup's to touch.")
    lines = [f"cleanup — {len(items)} candidate(s), window {window}d "
             f"({'enabled' if enabled else 'DISABLED by policy/env'}):", ""]
    lines += [f"  {i['cls']:<15} {i['action']:<8} age {i['age_days']:>6.1f}d  "
              f"{Path(i['path']).name}  — {i['detail']}" for i in items]
    if not apply:
        lines += ["", "dry-run (house pattern) — `cage data cleanup --apply` to execute."]
        return payload, "\n".join(lines)
    if not enabled:
        lines += ["", "· cleanup is disabled ([cleanup] enabled=false or CAGE_CLEANUP=0) "
                      "— nothing applied."]
        return payload, "\n".join(lines)
    counts = prune(root, pol, days, items=items)
    payload["applied"] = counts
    done = " · ".join(f"{n} {c}" for c, n in sorted(counts.items())) or "nothing"
    lines += ["", f"✔ applied: {done}"]
    return payload, "\n".join(lines)


# The never-list, adjacent to the allowlist it guards. Documentation + tests
# assert it; `scan` enforces it by construction (it never looks at these).
NEVER = ("ledger/", "policy.toml", "machine.json", "study.jsonl", "limits.json",
         "outcomes")
