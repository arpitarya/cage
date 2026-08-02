"""State-dir maintenance — a CLOSED allowlist over `.cage/state/` (plan §3.6.4).

`.cage/state/` accumulates files nothing prunes: `debug.log` and
`hooks-seen.jsonl` grow unbounded, per-session provenance buffers go stale when a
session never commits (their transcript fallback already ran at SessionEnd),
cursors outlive deleted source logs, tmp files linger. This module ages them out.

What may be cleaned is closed **by construction** — `scan` only ever looks at:

- ``debug-log``      — `debug.log` rows older than the window (current rows kept);
- ``capture-log``    — `capture.log` rows older than the window (current rows kept);
- ``usage-log``      — `graphify-usage.jsonl` rows older than the window (GC1 breadcrumb);
- ``attest-log``     — `attest.jsonl` rows older than the window (the L1 hook breadcrumb);
- ``hooks-seen``     — `hooks-seen.jsonl` rows older than the window;
- ``pending-buffer`` — `pending-*.jsonl` session buffers untouched for the window;
- ``cursor-orphan``  — `cursors.json` entries whose source log no longer exists
  (safe by design: the next import re-reads the whole log, id-dedupe absorbs it);
- ``tmp``            — `state/*.tmp` older than the window.

Never cleanable — enforced by the allowlist, not convention: anything in
``ledger/``, ``cage.toml`` (and ``prices.toml`` + the legacy ``policy.toml``),
``outcomes``, the machine id (fleet pairing breaks without it), ``study.jsonl``,
``limits.json``.
State files are never read by
derived views, so cleanup cannot change a single reported number.

Two paths, and since v0.37 they are no longer symmetric:

- **auto** (`maybe_run`, piggybacked on `cage import` — cage installs no scheduler —
  throttled to one real check per `CLEANUP_THROTTLE_HOURS`) **only ever warns**. It
  computes what would go and prints one stderr reminder (silent when nothing is
  eligible); it never deletes. Gated by `policy.cleanup_enabled` (env `CAGE_CLEANUP`
  beats policy) — `enabled=false` silences the reminder entirely — and, when
  enabled, further by `policy.cleanup_warn` (env `CAGE_CLEANUP_WARN`). Entirely
  fail-open: an error is debug-logged under ``cleanup.prune`` and never blocks
  capture.
- **manual** (`cage data cleanup`, dry-run print by default, ``--apply`` to execute)
  is the only path that ever deletes, and runs regardless of `cleanup_enabled` —
  an explicitly-typed command is always honored, never silently ignored because a
  switch happens to be off.

Retention: policy ``[cleanup] days`` (`constants.CLEANUP_DEFAULT_DAYS` fallback,
90 days). Deletion is unrecoverable, so this module never automates it — the
accepted trade-off is that `state/` grows unbounded for anyone who ignores the
reminder; the reminder keeps firing (every throttle interval, while items remain)
rather than warning once and going quiet.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys
from pathlib import Path

from cage import debuglog, lockutil, paths, policy
from cage.constants import CLEANUP_THROTTLE_HOURS

CLASSES = ("debug-log", "capture-log", "usage-log", "attest-log", "hooks-seen",
           "pending-buffer", "cursor-orphan", "tmp")

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


def _aged_rows(path: Path, cutoff: str) -> tuple[int, int, int]:
    """(stale, total, stale_bytes) JSON rows by their own ``ts`` field; unparseable
    rows and rows with no ts are kept (never delete what can't be dated).
    ``stale_bytes`` feeds the reclaimable-size estimate shown in the reminder/dry-run
    — it is the line bytes, not a claim about post-rewrite file size."""
    stale = total = stale_bytes = 0
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
            stale_bytes += len(line.encode("utf-8")) + 1
    return stale, total, stale_bytes


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
                      ("usage-log", foot.usage_log), ("attest-log", foot.attest_log),
                      ("hooks-seen", foot.hooks_seen)):
        try:
            if path.exists() and path.is_file():
                stale, total, stale_bytes = _aged_rows(path, cutoff)
                if stale:
                    found.append({"path": str(path), "cls": cls,
                                  "age_days": round(_age_days(path), 1),
                                  "action": "rewrite", "bytes": stale_bytes,
                                  "detail": f"drop {stale} of {total} rows > {window}d"})
        except OSError:
            continue

    for buf in sorted(foot.state.glob("pending-*.jsonl")):
        try:
            age = _age_days(buf)
            if age > window:
                found.append({"path": str(buf), "cls": "pending-buffer",
                              "age_days": round(age, 1), "action": "delete",
                              "bytes": buf.stat().st_size,
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
                              "action": "rewrite", "bytes": 0,  # a few bytes; not worth counting
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
                              "bytes": tmp.stat().st_size,
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
    if item["cls"] in ("debug-log", "capture-log", "usage-log", "attest-log",
                       "hooks-seen"):
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


def _reminder_line(items: list[dict], window: int) -> str:
    """The auto path's one stderr line: count, window, reclaimable size, and the
    exact runnable fix — never printed when `items` is empty (the caller's job)."""
    total_bytes = sum(i.get("bytes", 0) for i in items)
    return (f"cage: {len(items)} state/ item(s) older than {window}d "
            f"(~{total_bytes / 1024:.0f} KB reclaimable) — "
            f"`cage data cleanup` to review, `--apply` to prune.")


def maybe_run(root: Path, pol: dict) -> None:
    """The auto path, piggybacked on `cage import`/read sweeps (cage installs no
    scheduler): a cheap staleness check (one stat on the throttle stamp), then —
    since v0.37 — a **warning, never a deletion**. Deletion is unrecoverable; only
    an explicit `cage data cleanup --apply` performs it. Silent when nothing is
    eligible; keeps reminding every throttle interval while something is. Gated by
    `policy.cleanup_enabled` (auto path off entirely) and, when enabled, by
    `policy.cleanup_warn` (the reminder specifically). Never raises — capture must
    survive a broken cleanup."""
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
        if policy.cleanup_warn(pol):
            items = scan(root, pol)
            if items:
                print(_reminder_line(items, policy.cleanup_days(pol)), file=sys.stderr)
        stamp.write_text(_now().isoformat(), encoding="utf-8")
    except Exception as e:  # noqa: BLE001 — fail-open, but never silent
        debuglog.exception(root, "cleanup.prune", e, pol=pol)


def run_cli(root: Path, pol: dict, apply: bool = False,
            days: int | None = None) -> tuple[dict, str]:
    """`cage data cleanup` — dry-run table by default (house pattern), ``--apply``
    executes. ``(payload, text)`` for the emit helper. Runs regardless of
    `policy.cleanup_enabled` — that switch gates only the *automatic* reminder
    (`maybe_run`); a command the user typed is always honored, never silently
    ignored because a policy switch happens to be off."""
    auto_reminder = policy.cleanup_enabled(pol)
    window = days if days is not None else policy.cleanup_days(pol)
    items = scan(root, pol, days)
    payload = {"auto_reminder": auto_reminder, "days": window, "items": items,
               "applied": None}
    if not items:
        return payload, (f"✔ nothing stale in state/ (window: {window}d) — the "
                         "ledger, policy, machine id, study markers and limits are "
                         "never cleanup's to touch.")
    lines = [f"cleanup — {len(items)} candidate(s), window {window}d "
             f"(auto-reminder {'on' if auto_reminder else 'off'}):", ""]
    lines += [f"  {i['cls']:<15} {i['action']:<8} age {i['age_days']:>6.1f}d  "
              f"{Path(i['path']).name}  — {i['detail']}" for i in items]
    if not apply:
        lines += ["", "dry-run (house pattern) — `cage data cleanup --apply` to execute."]
        return payload, "\n".join(lines)
    counts = prune(root, pol, days, items=items)
    payload["applied"] = counts
    done = " · ".join(f"{n} {c}" for c, n in sorted(counts.items())) or "nothing"
    lines += ["", f"✔ applied: {done}"]
    return payload, "\n".join(lines)


# The never-list, adjacent to the allowlist it guards. Documentation + tests
# assert it; `scan` enforces it by construction (it never looks at these).
#
# Tool savings (`ledger/savings/<tool>/savings-*.jsonl`) are covered here ONLY because
# they sit under `ledger/` — there is no dedicated savings entry. That is deliberate:
# a per-tool cleanup class must NEVER be added. Savings rows are unrecoverable and
# nothing else reconstructs them (unlike a cursor or a debug-log row); moving the
# savings tree out from under `ledger/` without adding it back here would silently
# make it cleanable, with no test failing until `test_cleanup.py`'s
# `ledger/savings/<tool>/` survival case is the one that catches it.
NEVER = ("ledger/", "cage.toml", "prices.toml", "policy.toml", "machine.json",
         "study.jsonl", "limits.json", "outcomes")  # both config names — the legacy
                                     # `policy.toml` survives on machines that never
                                     # re-ran setup; `prices.toml` is the split-out
                                     # vendor rate card, protected alongside cage.toml
