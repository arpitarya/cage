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

from cage import constants, paths
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
    dir per process. The remedy it points at — archiving old shards —
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
                  f"*-YYYY-MM.jsonl shards.",
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


def _credit_from_cli_conv(row: dict) -> dict | None:
    """Project one `ledger/kiro/` `cli-conv` metric row into the **credits row shape**,
    or ``None`` when the credits skip rule says there is nothing honest to record.

    P2 (v0.51) re-homed kiro's credits: `credits-<month>.jsonl` is no longer written, and
    `cli-conv` — which reads the same store, through the same shared reader, under the
    same whitelist — became their home. The top-level shard was a duplicate of it.

    **The credits SEMANTICS are preserved here rather than inherited**, because the two
    row kinds differ in exactly two ways and both differences matter:

    1. **The skip rule.** `_kiro_cli_credit_row` drops a conversation when credits ≤ 0
       **and** context ≤ 0 — no usage signal, nothing to say. `cli-conv` is deliberately
       laxer: it emits whenever the store carried a `usage_info` list at all, *including
       one summing to a real 0.0*, because a store-verbatim kind records what the store
       said. `cli-conv` is therefore a **superset**, and the credits rule is re-applied on
       this projection so a credits reader sees exactly what it always saw.
       **Measured 2026-08-14: the delta is 0** across all 20 conversations on a real store
       (all 20 carry `usage_info`; all 20 have credits > 0 or context > 0) — see the
       [cross-check](../work/regression/2026-08-14-calls-vs-metric-crosscheck.md). n = 20,
       one machine: that bounds the claim and is *not* a reason to drop the rule, which
       still guards a case this store happens not to contain.
    2. **`credits` may be `None`** on a `cli-conv` row (the None-sentinel: no `usage_info`
       at all, distinct from a recorded 0.0). A credits row has no such sentinel, so
       `None` is treated as no-signal for the skip test and never rendered as a 0.

    `method="measured"` and `unit="credits"` come from `make_credit`'s own contract — an
    AWS credit read back verbatim. The projected row keeps the **source row's id**, so a
    number can be traced to the shard it came from.

    A projection, never a write: nothing is appended anywhere by this function."""
    credits_val = row.get("credits")
    if isinstance(credits_val, bool) or not isinstance(credits_val, (int, float)):
        credits_val = None
    context = row.get("context_pct", 0.0) or 0.0
    if (credits_val or 0) <= 0 and context <= 0:
        return None                      # the credits skip rule, re-applied verbatim
    return {"id": row.get("id", ""), "ts": row.get("ts", ""),
            "session": row.get("session", ""), "agent": row.get("agent", "kiro"),
            "model": row.get("model", ""), "unit": "credits",
            "credits": float(credits_val or 0.0), "turns": row.get("turns", 0),
            "context_pct": context, "method": "measured",
            "surface": row.get("surface", ""), "project": row.get("project", "")}


def _credit_score(row: dict, live: bool) -> tuple:
    """Collapse score for `credits()`: highest turn count wins, then the **live writer**,
    then id (append order).

    The middle term is P2's addition and it is deliberate rather than incidental. Before
    P2 the score was `(turns, id)`, and on a tie between a legacy `k_cred…` row and a
    projected `km_…` one the winner would have been decided by where `_` and `m` sit in
    ASCII — a real outcome resting on an accident. Preferring the source that is still
    being written states the intent instead. With legacy rows alone the term is constant,
    so the ordering is byte-identical to the pre-P2 collapse."""
    return (row.get("turns", 0), 1 if live else 0, row.get("id", ""))


def credits(root: Path, since: str | None = None) -> list[dict]:
    """Kiro-CLI **credits** usage rows (capture-precision §3.4), collapsed
    **last-write-wins per session** across BOTH homes.

    **Two sources, one shape, forever** (P2, v0.51):

    - `ledger/kiro/` `cli-conv` rows — the live home, projected through
      `_credit_from_cli_conv`, which re-applies the credits skip rule.
    - `credits-<month>.jsonl` — **no longer written, read forever.** Every real install
      has rows here (17 in the maintainer's own ledger, `method="estimated"` from before
      the USAGE-ONLY retag). They are never migrated, rewritten or deleted; append-only
      means the old shard is history that still counts.

    A resumed conversation appends a fresh row whose id folds in a higher turn count, so
    both shards are append-only and a re-import adds zero rows — but a grown
    conversation's credits must never be *summed* with its earlier partial row. This
    reader keeps only the highest-turn row per `session`, which is also what makes the two
    sources safe to union: a session captured under both homes collapses to one row rather
    than double-counting, because they describe the same conversation.

    **Read by `cage insights chats`** (CHATS-CREDITS) as its own row shape — a credits row
    gets its own bucket there and never enters a token aggregate, so reading it can never
    perturb a *call*-derived number (determinism preserved on that axis); an empty ledger
    with neither home returns []."""
    scored: dict[str, tuple[tuple, dict]] = {}
    for r in read_kind(root, "credits", since=since):
        key, s = r.get("session", ""), _credit_score(r, live=False)
        if key not in scored or s >= scored[key][0]:
            scored[key] = (s, r)
    for m in kiro_metrics(root, since=since):
        if m.get("source") != "cli-conv":
            continue
        r = _credit_from_cli_conv(m)
        if r is None:
            continue
        key, s = r.get("session", ""), _credit_score(r, live=True)
        if key not in scored or s >= scored[key][0]:
            scored[key] = (s, r)
    return sorted((v[1] for v in scored.values()), key=lambda x: x.get("id", ""))


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


def captured_surfaces(root: Path) -> set[str]:
    """Every agent surface this ledger holds ANY recorded usage for — the capture-health
    "has this agent ever captured?" gate (gate 3), and doctor's timeline basis.

    **It reads the metric ledgers ∪ `calls`, and that union is the whole point.** Before P5
    it was a set comprehension over `ledger.calls` alone. P5 retired the three agents'
    transcript→`calls` writer, so on a perfectly healthy install that set is now EMPTY for
    all three — and every surface built on it would report *never captured*: a silent false
    negative, the F1 class this repo has already paid for twice.

    `calls` stays in the union because it is not empty and never will be: retired-agent
    rows (codex) and pre-P5 history live there, and an agent that captured for six months
    and then stopped should still read as *has captured*.

    Fail-open per source — a broken metric shard must not make an agent look uncaptured,
    which is the same false negative one layer down."""
    from cage import agents
    return {s for r in usage_rows(root) if (s := agents.row_surface(r.get("agent")))}


def usage_rows(root: Path) -> list[dict]:
    """Every recorded usage row this ledger holds, across every producer — **the
    DIAGNOSTIC union, and deliberately not a sum source.**

    `spend()` is the single resolver for *what was used*: one basis per producer, each row
    exactly once, safe to add up. This is the other question — *what did cage capture at
    all* — and it must see rows `spend()` correctly excludes:

    * **kiro has no token spine** (`ABSENT_SPINES`), so it never appears in `spend()`. A
      capture diagnostic that could not see kiro would report the one agent whose capture
      is most fragile as absent.
    * cumulative sources (`CUMULATIVE_SOURCES`), and claude's `transcript` grain, are
      excluded from spend precisely because they would double-count — which is harmless
      for "did anything arrive?" and fatal for a total.

    **So this OVERLAPS by construction and must never be summed.** Every caller uses it
    for presence, counts-per-agent, and freshness only. Fail-open per reader — one broken
    shard must not make an agent look uncaptured, which is the same false negative one
    layer down."""
    out: list[dict] = []
    for reader in (calls, claude_metrics_raw, copilot_metrics_raw, kiro_metrics_raw,
                   consumer_metrics_raw):
        try:
            out.extend(reader(root))
        except Exception:  # noqa: BLE001 — a diagnostic never breaks on one bad shard
            continue
    return out


def consumer_metrics_raw(root: Path) -> list[dict]:
    """Every consumer-metrics row, unfiltered (`consumer/calls-*.jsonl`) — mirrors
    `copilot_metrics_raw()`. Feeds any seen-set that must see every id ever written
    regardless of a reporting window."""
    foot = paths.Footprint(root)
    rows: list[dict] = []
    for sh in foot.consumer_shards():
        rows.extend(read(sh))
    return rows


def consumer_metrics(root: Path, since: str | None = None) -> list[dict]:
    """Consumer-metrics rows (P1, v0.51), in append order.

    **No last-write-wins collapse, deliberately.** The three agent kinds collapse because
    a chat GROWS and is re-captured, so a later row supersedes an earlier one. A consumer
    row is a point-in-time fact about one provider response, written once at the moment it
    happened by a caller that will never re-capture it — there is no later version to win.
    Adding a collapse here would be machinery guarding an event that cannot occur, and the
    obvious key to collapse on (`session`) would silently keep one call per session.

    Dedupe is by id, exactly as everywhere else: ids carry the only entropy, and
    `mergeutil.union_by_id` handles a re-imported bundle without help from this reader.

    ``since`` drops dated shards whose whole month predates the cutoff (same partition win
    as `read_kind`). An empty ledger with no `consumer/` tree returns []."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in foot.consumer_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    return rows


def consumer_twin_calls(root: Path, since: str | None = None) -> set[str]:
    """The set of `calls`-row ids that a consumer-metric row claims as its twin.

    This is `spend()`'s **exact** suppression key, and the reason P1 could reverse
    ADR-CONSUMERS without losing a row. The alternative — testing a `calls` row's agent
    name against `SPEND_SOURCES` the way the three agents are tested — would suppress
    every *historical* `lib`/proxy row too: rows written before this kind existed, whose
    twin does not and cannot exist, silently zeroed. That is the exact failure that
    record measured at 373 codex rows, pointed at a different population.

    An id match cannot make that mistake. A consumer row with no `call` (a caller that
    minted one directly, or a dual-write whose `calls` half failed) contributes nothing
    here, so its `calls` twin — if any — keeps resolving. Fail-open in the direction of
    keeping data."""
    return {c for r in consumer_metrics(root, since) if (c := r.get("call", ""))}


def copilot_metrics_raw(root: Path) -> list[dict]:
    """Every copilot-metrics row, unfiltered (`copilot/chats-*.jsonl`, mirrors
    `savings()` minus the ``since`` filter) — feeds the import sweep's seen-set, which
    must see every id ever written regardless of any reporting window."""
    foot = paths.Footprint(root)
    rows: list[dict] = []
    for sh in foot.copilot_shards():
        rows.extend(read(sh))
    return rows


def _copilot_metric_key(row: dict) -> tuple:
    return (row.get("source", ""), row.get("session", ""), row.get("surface", ""),
            row.get("request", ""), row.get("call", ""))


def _copilot_metric_score(row: dict) -> tuple:
    return (row.get("tokens_in", 0) + row.get("tokens_out", 0),
            row.get("credits") if row.get("credits") is not None else -1,
            row.get("id", ""))


def copilot_metrics(root: Path, since: str | None = None) -> list[dict]:
    """Copilot-metrics rows (COPILOT-METRICS handoff §4.3), collapsed **last-write-wins
    per `(source, session, surface, request, call)`** — the `credits()` collapse,
    generalized to a wider key. Call-grain keys (the sidecar/debuglog/otel `call` field)
    are unique per row, so the collapse is a no-op for them; it bites only on a grown
    chatSessions request or a resumed CLI session, whose parser-minted `id` folds in the
    row's new values and appends a fresh row under the same key.

    Winner = max by `(tokens_in + tokens_out, credits or -1, id)` — the row carrying the
    most usage wins; ties break on credits, then on id (append order). **Never sum**
    `session_credits` or a CLI row's cumulative `model_totals` across a session's rows —
    each row already IS the cumulative total as of its own capture, so summing would
    double- or triple-count. ``since`` drops dated shards whose whole month predates the
    cutoff (same partition win as `read_kind`). Capture-only: no derived view reads this
    kind yet — an empty ledger with no `copilot/` tree returns []."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in foot.copilot_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = _copilot_metric_key(r)
        cur = latest.get(key)
        if cur is None or _copilot_metric_score(r) >= _copilot_metric_score(cur):
            latest[key] = r
    return sorted(latest.values(), key=lambda x: x.get("id", ""))


def kiro_metrics_raw(root: Path) -> list[dict]:
    """Every kiro-metrics row, unfiltered (`kiro/chats-*.jsonl`, mirrors
    `copilot_metrics_raw()` minus the ``since`` filter) — feeds the import sweep's
    seen-set, which must see every id ever written regardless of any reporting window."""
    foot = paths.Footprint(root)
    rows: list[dict] = []
    for sh in foot.kiro_metric_shards():
        rows.extend(read(sh))
    return rows


def _kiro_metric_key(row: dict) -> tuple:
    return (row.get("source", ""), row.get("session", ""), row.get("turn", ""),
            row.get("row_ref", ""))


def _kiro_metric_score(row: dict) -> tuple:
    return (row.get("turns", 0), row.get("tokens_in", 0) + row.get("tokens_out", 0),
            row.get("id", ""))


def kiro_metrics(root: Path, since: str | None = None) -> list[dict]:
    """Kiro-metrics rows (KIRO-METRICS handoff §4.3), collapsed **last-write-wins per
    `(source, session, turn, row_ref)`** — the `copilot_metrics()` collapse, generalized
    to Kiro's grain keys. IDE call-grain keys (`row_ref` = the store's own `id`) are
    unique per row, so the collapse is a no-op for them; it bites only on a grown CLI
    conversation, whose parser-minted `id` folds in the row's new values and appends a
    fresh row under the same key.

    Winner = max by `(turns, tokens_in + tokens_out, id)` — the row reflecting the most
    conversation growth wins; ties break on token volume, then on id (append order).
    **Never sum** a conversation's own growth rows across its history — each `cli-conv`/
    `cli-turn` row already IS the state as of its own capture, so summing would
    double- or triple-count (the same law `copilot_metrics` states for `session_credits`).
    ``since`` drops dated shards whose whole month predates the cutoff (same partition
    win as `read_kind`). Capture-only: no derived view reads this kind yet — an empty
    ledger with no `kiro/` tree returns []."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in foot.kiro_metric_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    latest: dict[tuple, dict] = {}
    for r in rows:
        key = _kiro_metric_key(r)
        cur = latest.get(key)
        if cur is None or _kiro_metric_score(r) >= _kiro_metric_score(cur):
            latest[key] = r
    return sorted(latest.values(), key=lambda x: x.get("id", ""))


def claude_metrics_raw(root: Path) -> list[dict]:
    """Every claude-metrics row, unfiltered (`claude/chats-*.jsonl`, mirrors
    `copilot_metrics_raw()`/`kiro_metrics_raw()` minus the ``since`` filter) — feeds the
    import sweep's seen-set, which must see every id ever written regardless of any
    reporting window."""
    foot = paths.Footprint(root)
    rows: list[dict] = []
    for sh in foot.claude_shards():
        rows.extend(read(sh))
    return rows


def _claude_metric_score(row: dict) -> tuple:
    return (row.get("requests", 0), row.get("tokens_in", 0) + row.get("tokens_out", 0),
            row.get("id", ""))


def claude_metrics(root: Path, since: str | None = None) -> list[dict]:
    """Claude-metrics rows (CLAUDE-METRICS handoff §4.3), collapsed **last-write-wins
    per `session`** — the `credits()` collapse, `turns` generalized to `requests`. A
    chat that grew since its last capture appends a fresh row whose parser-minted id
    folds in the new values (`schema.make_claude_metric`), so the shard is append-only
    and a re-import adds zero rows — but a grown chat's totals must never be *summed*
    with an earlier partial capture of the same chat, because each row already IS the
    chat's whole-life total as of its own capture.

    Winner = max by `(requests, tokens_in + tokens_out, id)` — the row reflecting the
    most conversation growth wins; ties break on token volume, then on id (append
    order). A chat spanning multiple months has rows in different shards; the collapse
    resolves across all of them (the latest row lives in the newest month, so a
    ``since`` window that skips an early shard still returns it). ``since`` drops dated
    shards whose whole month predates the cutoff (same partition win as `read_kind`).
    Capture-only: no derived view reads this kind yet — an empty ledger with no
    `claude/` tree returns []."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in foot.claude_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    latest: dict[str, dict] = {}
    for r in rows:
        # CHAT GRAIN ONLY. Since METRICS-PRIMARY P1 this kind holds two grains, and this
        # collapse is per SESSION — handed a request-grain row it would keep ONE request
        # per chat and silently discard every other, while also mixing two different
        # meanings of "row". `claude_request_metrics` is the reader for that grain.
        if r.get("source") != "transcript":
            continue
        sess = r.get("session", "")
        cur = latest.get(sess)
        if cur is None or _claude_metric_score(r) >= _claude_metric_score(cur):
            latest[sess] = r
    return sorted(latest.values(), key=lambda x: x.get("id", ""))


def claude_request_metrics(root: Path, since: str | None = None) -> list[dict]:
    """Claude **request-grain** metric rows (source ``request``, METRICS-PRIMARY P1),
    collapsed last-write-wins per ``(session, request)``.

    Deliberately a second reader beside `claude_metrics`, not a parameter on it: the two
    answer different questions and collapse on different keys. `claude_metrics` keeps one
    whole-life total per chat — correct for a per-chat view, and catastrophic here, since
    it would discard every request in a chat but one. A request row is a point-in-time
    fact, so its own identity is the collapse key and a re-capture of the same request
    simply wins over its earlier copy.

    Winner = max by ``(tokens_in + tokens_out, id)``: the fullest capture of that request
    wins, ties break on append order. Empty until P1 emits the grain."""
    foot = paths.Footprint(root)
    cut = since_cutoff(since)
    latest: dict[tuple, dict] = {}
    for sh in foot.claude_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        for r in read(sh):
            if r.get("source") != "request":
                continue
            key = (r.get("session", ""), r.get("request", ""))
            cur = latest.get(key)
            score = (r.get("tokens_in", 0) + r.get("tokens_out", 0), r.get("id", ""))
            if cur is None or score >= (cur.get("tokens_in", 0) + cur.get("tokens_out", 0),
                                        cur.get("id", "")):
                latest[key] = r
    return sorted(latest.values(), key=lambda x: x.get("id", ""))


# ── METRICS-PRIMARY: the one spend resolver (ADR 0010, PLAN §3.14) ──────────────
#
# Which metric `source` is the SPEND SPINE for each agent. This table is the answer to
# the one question the metric ledgers pose that `calls` never did: **each kind holds
# several overlapping views of the same traffic, on purpose.** Copilot's five stores all
# describe the same requests at three different grains; kiro's `cli-conv` and `cli-turn`
# are the same conversation counted two ways. Summing a kind is therefore WRONG — it
# double- or triple-counts — so spend picks exactly one source per (agent, surface) and
# never adds a second.
#
# The choices, and why each is the one that can carry usage:
#   claude   `request`   the P1 request-grain row — one per folded (requestId,
#                        message.id). The chat-grain row is a whole-life total for the
#                        SAME traffic, so including it would double every chat.
#   copilot  `chat`      VS Code, per request, durable and ungated (surface=vscode).
#                        `sidecar`/`debuglog`/`otel` are finer views of that SAME traffic
#                        and are opt-in, so a machine that enables one would silently
#                        double its own spend.
#            `cli-delta` Copilot CLI, per shutdown — the DELTA twin, not the cumulative
#                        `cli` row beside it (see below).
#   kiro     —           no spine. See `ABSENT_SPINES`.
#
# **THE SECOND RULE: a spine source must be POINT-IN-TIME, never CUMULATIVE.** A
# cumulative row carries its session's ENTIRE life in one row stamped at the latest
# capture, so it would land in the same total as the point-in-time rows describing that
# session's individual turns — a straddling session counted twice, invisibly, because
# both figures are individually correct. Caught by a straddling fixture, not by reading.
# (The rule was found under the retired spend cutover, where the double-count crossed a
# time boundary; retiring the boundary did not retire the rule — the overlap is between
# two views of the same traffic, which is a property of the stores, not of the clock.)
#
# Copilot's `cli` store is the only place this bites, and it is fixed at capture:
# `transcript.parse_copilot_cli_metrics` now emits a `cli-delta` row beside every
# cumulative `cli` row, reusing `parse_copilot_cli_calls`'s delta arithmetic and its reset
# rule. Verbatim capture is preserved (`cli` is untouched — it is why the kind exists);
# only the derived twin is a spine. **Never sum the two.**
#
# Kiro's `cli-conv` is cumulative too and is likewise NOT a spine — but that is not a gap
# and must not be read as one: kiro-CLI spend never lived in `calls` at all. It is
# credits-only (`schema.make_credit` → `ledger.credits`), folded by `report.summarize` as
# its own group (REPORT-CREDITS, CLAUDE.md), a mechanism this cutover does not touch and
# does not need to. Excluding it loses nothing.
#
# Adding a store to a kind does NOT add it here. That is the point: capture stays wide,
# spend stays single-basis and point-in-time.
SPEND_SOURCES: dict[str, tuple[str, ...]] = {
    "claude": ("request",),
    "copilot": ("chat", "cli-delta"),
    "kiro": (),
    # P1 (v0.51). **Read here, but NOT used as the suppression test** — the three above
    # are keyed by `agents.row_surface(row["agent"])`, and a consumer row's agent is
    # whatever its caller stamped (`lib` by default, but a proxy or a named application
    # too). Suppression of the `calls` twin is by **id** (`consumer_twin_calls`), which
    # is what keeps a pre-P1 `lib` row resolving. See `spend()`.
    "consumer": ("call",),
}

#: Agents with **no token spine at all**, each with the reason — stated here rather than
#: left as a pointer at a store that does not exist, so a reader can tell "this agent has
#: no token store" from "the source name is a typo".
#:
#: Kiro's entry was `("ide",)` through v0.50, naming `devdata.sqlite` — a file that is
#: **not present on a real Kiro install**. Its *calls* route reads a different file
#: (`tokens_generated.jsonl`) for the same facts, so the pointer read as a live source
#: while resolving zero rows forever (KIRO-IDE-METRIC-ROW). Emitting an `ide` metric row
#: from `tokens_generated.jsonl` instead was rejected on the 2026-08-14 field probe: that
#: file carries 28 rows totalling 1,576 in / **0 out**, model `"agent"` on every row, and
#: a byte-identical 6-row block repeated — it is not summable, so a spine built on it
#: would be a fabricated number, not a measured one. Kiro renders `—` with this reason;
#: it is never a zero. `transcript.parse_kiro_ide_metrics` is deliberately KEPT so a
#: future Kiro that ships the store flips this back — `cage doctor` announces the flip.
ABSENT_SPINES: dict[str, str] = {
    "kiro": "no IDE token store on this install",
}

#: Cumulative sources deliberately excluded from `SPEND_SOURCES`, each with the reason —
#: named rather than silently dropped, so a reader can tell "excluded by design" from
#: "nobody thought about it". Neither leaves a hole: copilot CLI is covered by its
#: `cli-delta` twin, kiro CLI by the separate credits mechanism.
CUMULATIVE_SOURCES: dict[str, tuple[str, str]] = {
    "copilot": ("cli", "superseded by the cli-delta twin"),
    # Reworded in P2 (v0.51). It used to read "credits-only (ledger.credits), never in
    # calls", which pointed at a shard that is no longer written. `cli-conv` IS the
    # credits home now — `ledger.credits` projects it — and it stays out of the token
    # spine for the unchanged reason (10.3): `_spend_row` normalizes every spine row to
    # the call-row TOKEN shape, so a cli-conv row in `spend()` would carry credits with
    # zero tokens, which is the exact lie `make_credit` exists to prevent.
    "kiro": ("cli-conv", "kiro-CLI usage is credits, read by ledger.credits — never tokens"),
}


def _spend_row(row: dict) -> dict:
    """One metric row, normalized to the call-row shape every derive site already reads.

    Additive only — a field the metric kind does not carry is simply absent, exactly as
    it would be on a legacy call row, and is NEVER synthesized. `basis` is the one field
    that is not on a call row: it names which ledger the figure came from, so a view can
    state a split instead of blending two bases silently (the `creditprice` precedent)."""
    # `machine` is in this list because the fleet study partitions by it
    # (`study.summarize`): omitted, every metric-sourced row lands "unphased" and a
    # machine's whole plugin phase reads as zero days. Found by a golden, not by
    # reading — the same class of miss as `route` needing a default below.
    out = {k: row[k] for k in ("id", "ts", "agent", "model", "provider", "session",
                               "task", "surface", "project", "scope", "machine",
                               "tokens_in", "tokens_out", "cached_in", "cache_write_in",
                               "est_cost_usd", "credits", "billed_with", "latency_ms",
                               "import_id", "route")
           if k in row}
    out.setdefault("route", "chat")
    out.setdefault("ok", True)
    out["basis"] = "metrics"
    return out


def spend(root: Path, since: str | None = None) -> list[dict]:
    """**The single derive resolver** (METRICS-PRIMARY): every view that asks "what was
    spent" reads this, never `calls()` directly.

    **The basis is per-AGENT, and there is no time boundary.** An agent that has a metric
    ledger resolves from it, always, for all of history; an agent that has none resolves
    from `calls`, always. A row therefore lands on exactly one side by *whose* it is, and
    **no row is counted twice**.

    This replaced a time-partitioned cutover (`SPEND_CUTOVER`, v0.50, retired with the
    money subsystem). The cutover existed to protect six months of recorded `calls`
    history that could not be rebuilt into metric rows; that history is no longer wanted,
    and retiring the boundary is what makes the corrected pre-cutover metric rows —
    ~21,900 claude request rows back to Jul 12, and every copilot and kiro row in
    existence — readable again. It also removes the last thing a reader had to footnote.

    **The `calls` fallback is scoped, not universal, and dropping it would lose data.**
    `cage.meter`'s library rows (`agent="lib"`, the AlphaForge/Anton integration),
    proxy-metered rows, the retired `codex` agent still sitting in real ledgers, and every
    `[sources.<name>]` custom tool have no metric ledger and never will under this design.
    They are not superseded by anything, so they keep resolving from `calls` forever.
    Deleting this loop entirely — the tempting reading of "one basis" — silently zeroes
    all of them; measured at 373 codex rows in one real ledger alone."""
    from cage import agents
    rows = []
    # P1: the ids of `calls` rows that a consumer-metric row already carries. Computed
    # ONCE, outside the loop — it is a full read of the consumer shards.
    twins = consumer_twin_calls(root, since)
    for r in calls(root, since):
        # Superseded only when this row's own agent HAS a spine to be superseded by.
        # `SPEND_SOURCES` is the membership test, never `agents.SURFACES`: kiro is in the
        # table with an empty tuple (`ABSENT_SPINES`), so its `calls` rows are suppressed
        # here and it renders `—` with a stated reason rather than falling back to a
        # second basis. Falling back would resurrect exactly the blend this design exists
        # to remove.
        if agents.row_surface(r.get("agent")) in SPEND_SOURCES:
            continue
        # …and, since P1, superseded when THIS EXACT ROW has a consumer twin. Note what
        # this test is not: it is not `row_surface(agent) == "consumer"`. A consumer's
        # agent name is caller-supplied, and an agent-name test would suppress every
        # pre-P1 `lib`/proxy row — rows whose twin does not exist and never will — which
        # zeroes them silently. The id match suppresses exactly the rows that were
        # dual-written and nothing else.
        if r.get("id") in twins:
            continue
        r["basis"] = "calls"
        rows.append(r)
    # `claude_metrics` collapses last-write-wins per SESSION — the right reader for a
    # chat-grain whole-life total and the wrong one here, because it would keep one row
    # per chat and discard every other request in it. Request-grain rows are point-in-time
    # facts, so they collapse on their own identity instead (`claude_request_metrics`).
    readers = ((claude_request_metrics, "claude"), (copilot_metrics, "copilot"),
               (kiro_metrics, "kiro"), (consumer_metrics, "consumer"))
    for read_rows, agent in readers:
        allowed = SPEND_SOURCES[agent]
        if not allowed:
            continue  # ABSENT_SPINES — no token store; never a fabricated zero row
        for r in read_rows(root, since):
            if r.get("source", "") in allowed:
                rows.append(_spend_row(r))
    return rows


def join_table(root: Path, since: str | None = None) -> list[dict]:
    """The row set a **receipt's `call` id** is looked up in — `spend()` plus any `calls`
    row whose id it superseded (METRICS-PRIMARY P4).

    A receipt is written with `call=<the calls-row id it was filed against>`. Post-cutover
    the spend row for that same traffic is a *metric* row with a `clm_`/`cm_` id, so a
    lookup in `spend()` alone would **orphan every linked receipt** — its saving would
    silently leave its agent and fall into the unattributed bucket. Measured on the R6
    golden: a claude row's `gross tok` fell 80,000 → 0 while the TOTAL kept 80,000.

    This is a **lookup table, never a sum source** — the distinction is what makes the
    union safe. `_nonhuman_savings`/`attribution` use it only to answer "which agent and
    model does this receipt belong to"; spend itself is summed from `spend()`, which
    contains each row exactly once. Adding the superseded rows back here therefore cannot
    double-count a token, and the resolution stays **exact** (an id match), never a
    timestamp-proximity guess.

    Today this is mostly latent: every receipt cage's own shims file is call-LESS by
    construction (graphify/fux carry a `task` and no `call`, and price through the
    `receiptprice` ladder). It matters for `cage.meter` callers that pass `call=`."""
    rows = spend(root, since)
    seen = {r.get("id") for r in rows}
    for c in calls(root, since):
        if c.get("id") not in seen:
            c.setdefault("basis", "calls")
            rows.append(c)
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


def provenance(root: Path, since: str | None = None) -> list[dict]:
    """Every authorship row, across **both homes** — `ledger/provenance/provenance-*.jsonl`
    (P3c, v0.51) and the legacy unpartitioned `ledger/provenance.jsonl`, oldest first.

    The legacy file is read forever and never rewritten: frozen rows are never backfilled,
    and `residual_lines`' absent-vs-recorded-`0` distinction — the version gate for the
    per-chat `agent%` column — depends on that. Order is deterministic (legacy, then dated
    shards ascending) and a truncated tail in any shard is tolerated.

    ``since`` drops dated shards whose whole month predates the cutoff — the bounded
    re-scan that partitioning bought. **The legacy file is never skipped by it**: it has no
    month in its name, so `_month_entirely_below` returns False, which is the safe
    direction (read too much, never too little)."""
    cut = since_cutoff(since)
    rows: list[dict] = []
    for sh in paths.Footprint(root).provenance_shards():
        if cut is not None and _month_entirely_below(sh.name, cut):
            continue
        rows.extend(read(sh))
    return rows


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
