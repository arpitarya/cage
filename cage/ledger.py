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


def append_row(root: Path, kind, row: dict) -> bool:
    """Append a ``calls``/``receipts``/``tasks`` row to its month shard (plan §3.6.1).

    ``kind`` is normally a string; a ``("savings", tool)`` tuple routes the row into the
    per-source savings tree (`savings/<tool>/savings-<month>.jsonl`, plan §3).

    The shard is chosen from the row's own ``ts`` (`paths.Footprint.shard`), so writes
    are deterministic and the append-only past is never rewritten — new writes simply
    target dated files. Fail-open like `append` — but never *silent*: a failed append
    (the unwritable-ledger case, the one capture failure that loses a row) leaves an
    attributable line in the debug log under ``CAGE_DEBUG=1``. Local import + row
    metadata only (kind, shard path, row id) — the trace is itself fail-open.

    Fleet studies (plan §4.9): when this ledger is *enrolled* (an opaque machine id
    exists in state), the row gains an additive ``machine`` field here — the one write
    chokepoint every calls/receipts/tasks writer already goes through. Unenrolled
    ledgers stamp nothing: byte-identical to the legacy contract."""
    try:
        from cage import machine  # local: keeps the hot path import-light, no cycle
        machine.stamp(root, row)
    except Exception:  # noqa: BLE001 — stamping is additive, never blocks a write
        pass
    shard = paths.Footprint(root).shard(kind, row.get("ts", ""))
    ok = append(shard, row)
    if not ok:
        try:
            from cage import debuglog  # local import keeps the write hot path light
            kind_str = "/".join(kind) if isinstance(kind, tuple) else kind
            debuglog.event(root, event="ledger.append", result="write-failed",
                           kind=kind_str, shard=str(shard), row_id=row.get("id", ""))
        except Exception:  # noqa: BLE001 — tracing must never break the write path
            pass
    return ok


def append_new(root: Path, rows: list[dict], seen: set | None = None,
               collect: list | None = None) -> int:
    """Append only call rows whose id isn't already in the ledger. Returns #added.

    The **correctness backstop** for capture: every capture path (the pull import
    sweep, capture-on-read, a real-time hook) funnels through here, so a call seen by
    two paths is appended once — id-dedupe makes the paths idempotent and safe to run
    together (plan capture-architecture §2). Lives in ``ledger.py`` (not an agent's
    module) precisely because the universal import path must not depend on one agent's
    Claude-specific code — the sole home now that the hook capture path is gone.

    ``seen`` is an optional caller-owned set of already-known call ids: pass it to skip
    the per-call ledger reload and amortize the dedupe across a multi-file run (the
    ledger is 22k+ rows — re-reading it per file/call is the import hot path, plan
    §3.7). It is mutated in place with each appended id so later batches see them.
    Omit it and the legacy self-contained behavior holds (reload once here).

    ``collect`` is an optional caller-owned list: each row actually appended is pushed
    onto it, so a caller can roll up the run's real delta (per-agent×surface tokens/
    cost, import-ledger plan §2.2) without a second ledger read."""
    if seen is None:
        seen = {c.get("id") for c in calls(root)}
    added = 0
    for row in rows:
        if row.get("id") not in seen:
            if append_row(root, "calls", row):
                seen.add(row.get("id"))
                added += 1
                if collect is not None:
                    collect.append(row)
    return added


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


def _shard_bytes(shards: list[Path]) -> int:
    """Total size of the globbed shards; a per-shard `stat` failure is skipped, not
    raised (the byte-sum is best-effort — it feeds only the warning, never the read)."""
    total = 0
    for sh in shards:
        try:
            total += sh.stat().st_size
        except OSError:
            continue
    return total


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
        total = _shard_bytes(shards)
        if total > _warn_threshold(foot):
            _warned_dirs.add(key)
            print(f"cage: ledger is {total / 1_000_000:.0f} MB across {len(shards)} "
                  f"shard(s) — derives stay fast but history is unbounded; archive old "
                  f"*-YYYY-MM.jsonl shards or run `cage authorship ledger-sync` then prune.",
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


def credits(root: Path, since: str | None = None) -> list[dict]:
    """Kiro-CLI **credits** usage rows (capture-precision §3.4), collapsed
    **last-write-wins per session**. A resumed conversation appends a fresh row whose id
    folds in a higher turn count (`schema.make_credit`), so the shard is append-only and
    a re-import adds zero rows — but a grown conversation's credits must never be *summed*
    with its earlier partial row. This reader keeps only the highest-turn row per
    `session` (ties broken by id), the append-only analogue of `_latest_task`. Read by no
    call-based view, so it can never perturb a token/cost number (determinism preserved);
    an empty ledger with no credits shard returns []."""
    rows = read_kind(root, "credits", since=since)
    latest: dict[str, dict] = {}
    for r in rows:
        sess = r.get("session", "")
        cur = latest.get(sess)
        if cur is None or (r.get("turns", 0), r.get("id", "")) >= (cur.get("turns", 0), cur.get("id", "")):
            latest[sess] = r
    return sorted(latest.values(), key=lambda x: x.get("id", ""))


def savings(root: Path, since: str | None = None) -> list[dict]:
    """The dedicated per-source savings tree (`savings/*/savings-*.jsonl`, plan §3).
    Globbed + concatenated across every tool sub-dir, deterministic order. ``since``
    drops dated shards whose whole month predates the cutoff (same partition win as
    `read_kind`). Empty when no tool has ever recorded a saving."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in foot.savings_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    return rows


def receipts(root: Path, since: str | None = None) -> list[dict]:
    """Every savings receipt: an **id-deduped union** of the legacy `receipts.jsonl`
    shards with the dedicated `savings/<tool>/` tree (plan §3), the tree winning on a
    duplicate id. Savings rows are receipt-compatible, so every attribution/roi/report
    surface reads them unchanged.

    Why a union, not a concatenation: `cage data migrate-savings` **copies** historical
    graphify rows (keeping their original id) from `receipts.jsonl` into the tree, so the
    same id can legitimately sit in both stores. Deduping by id — ids carry the only
    entropy, so identity dedupe is exact — makes the number precise regardless: an
    idempotent re-run, a half-completed migration, or a crash mid-copy all still read each
    row exactly once. Row order is stable and deterministic (legacy order, then any
    tree-only rows), so derived views are byte-identical before/after a migration. An
    empty tree (no migration, no native shim) makes this byte-identical to the legacy
    concatenation.

    A row without an `id` can't be merged by identity, so — unlike `union_by_id`, which
    drops it — it is **preserved** here (concatenation kept it; dropping it would silently
    change a money total). It can never collide, so appending it is safe."""
    from cage.mergeutil import union_by_id
    legacy = read_kind(root, "receipts", since=since)
    tree = savings(root, since=since)
    idless = [r for r in legacy if not r.get("id")] + [r for r in tree if not r.get("id")]
    merged = union_by_id(legacy, tree, on_collision=lambda _prior, row: row)  # tree wins
    return merged + idless


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


def by_project(rows: list[dict], project: str | None) -> list[dict]:
    """Filter to one `project` (working-dir basename, plan §3.7) — a *derived*
    attribution axis distinct from `scope`. `None`/"" ⇒ unfiltered. Only logs that carry
    the cwd stamp it (Claude today; Copilot/Kiro leave it empty), so a project view
    is exact for Claude and silently drops the projectless rows of the other agents."""
    return [r for r in rows if r.get("project") == project] if project else rows


_SINCE = re.compile(r"^(\d+)([dhw])$")
_UNIT = SINCE_WINDOW_DAYS


def valid_since(spec: str | None) -> bool:
    """Whether a ``--since`` spec parses (``7d`` / ``24h`` / ``2w`` forms). ``None``/""
    (flag absent) is valid. The CLI boundary rejects an invalid spec with a typed
    error; `since_cutoff` itself stays lenient (fail-open capture callers pass
    through it and must never raise)."""
    return not spec or _SINCE.match(spec.strip()) is not None


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


def newest_ts(rows: list[dict]) -> _dt.datetime | None:
    """The newest parseable row ``ts`` — the data-relative "now" derived views use
    instead of the wall clock (freshness age math, plan §3.3). ``None`` when no row
    carries a timestamp (empty ledger ⇒ the age signal has no anchor)."""
    return max((t for r in rows if (t := _ts(r)) is not None), default=None)


def since(rows: list[dict], spec: str | None) -> list[dict]:
    cut = since_cutoff(spec)
    if cut is None:
        return rows
    return [r for r in rows if (t := _ts(r)) and t >= cut]
