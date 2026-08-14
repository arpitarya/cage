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
    `session` (ties broken by id), the append-only analogue of `_latest_task`. **Read by
    `cage insights chats`** (CHATS-CREDITS) as its own row shape — a credits row gets its
    own bucket there and never enters a token/cost aggregate, so reading it can never
    perturb a *call*-derived number (determinism preserved on that axis); an empty ledger
    with no credits shard returns []."""
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
# The choices, and why each is the one that can carry money:
#   claude   `request`   the P1 request-grain row — one per folded (requestId,
#                        message.id). The chat-grain row is a whole-life total for the
#                        SAME traffic, so including it would double every chat.
#   copilot  `chat`      VS Code, per request, durable and ungated (surface=vscode).
#                        `sidecar`/`debuglog`/`otel` are finer views of that SAME traffic
#                        and are opt-in, so a machine that enables one would silently
#                        double its own spend.
#            `cli-delta` Copilot CLI, per shutdown — the DELTA twin, not the cumulative
#                        `cli` row beside it (see below).
#   kiro     `ide`       per LLM call (surface=ide).
#
# **THE SECOND RULE, found while building P0 and not anticipated by the handoff: a spine
# source must be POINT-IN-TIME, never CUMULATIVE.** A cutover partitions the time axis by
# each row's own `ts`. A cumulative row carries its session's ENTIRE life in one row
# stamped at the latest capture, so post-cutover it would land wholly on the metrics side
# while that same session's earlier traffic is still counted on the `calls` side — a
# straddling session billed twice, invisibly, because both figures are individually
# correct. Caught by a straddling fixture, not by reading.
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
    "kiro": ("ide",),
}

#: Cumulative sources deliberately excluded from `SPEND_SOURCES`, each with the reason —
#: named rather than silently dropped, so a reader can tell "excluded by design" from
#: "nobody thought about it". Neither leaves a hole: copilot CLI is covered by its
#: `cli-delta` twin, kiro CLI by the separate credits mechanism.
CUMULATIVE_SOURCES: dict[str, tuple[str, str]] = {
    "copilot": ("cli", "superseded by the cli-delta twin"),
    "kiro": ("cli-conv", "kiro-CLI spend is credits-only (ledger.credits), never in calls"),
}


def _spend_row(row: dict) -> dict:
    """One metric row, normalized to the call-row shape every derive site already reads.

    Additive only — a field the metric kind does not carry is simply absent, exactly as
    it would be on a legacy call row, and is NEVER synthesized. `basis` is the one field
    that is not on a call row: it names which ledger the figure came from, so a view can
    state a split instead of blending two bases silently (the `creditprice` precedent)."""
    out = {k: row[k] for k in ("id", "ts", "agent", "model", "provider", "session",
                               "task", "surface", "project", "scope", "tokens_in",
                               "tokens_out", "cached_in", "cache_write_in",
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

    Rows with `ts < constants.SPEND_CUTOVER` resolve from the `calls` ledger; rows at or
    after it resolve from the three per-agent metric ledgers, normalized by `_spend_row`
    to the shape `calls` already had. **No row is counted twice**, because the boundary
    is a partition of the time axis and every row lands on exactly one side of it by its
    OWN `ts` — never by its session's start, so a chat that began before the cutover and
    grew after it contributes its early rows to one side and its later rows to the other.

    Why forward-only rather than a migration: six months of recorded `calls` history
    cannot be rebuilt into metric rows (the vendor fields were never captured then, and
    fabricating them would violate counts-never-content), and all 43 golden fixtures are
    pre-cutover — so a golden that moves is a bug in THIS function, never a re-bless.

    Capture stays dual-write on both sides of the boundary, so the flip is a one-constant
    rollback rather than a data-loss event.

    **A row with no `ts` resolves to the `calls` side**, the conservative default: it is
    how every pre-cutover row that predates timestamping already behaves, and the metric
    kinds have carried a `ts` from their first row, so the case cannot arise there."""
    from cage import agents
    cut = constants.SPEND_CUTOVER
    rows = []
    for r in calls(root, since):
        # **The cutover is SCOPED to the three agents that have a metric ledger.** A
        # post-cutover `calls` row is superseded only when its own agent has a spine to be
        # superseded BY. Everything else — `cage.meter`'s library rows (`agent="lib"`, the
        # AlphaForge/Anton integration), proxy-metered rows, and every `[sources.<name>]`
        # custom tool — has no metric ledger and never will under this design, so the
        # cutover simply does not apply to it and it keeps resolving from `calls` forever.
        #
        # Without this scope the flip silently zeroes every library- and proxy-metered
        # call the moment the clock passes the instant. Found the hard way: the suite went
        # red across 47 tests when the machine clock crossed `SPEND_CUTOVER` mid-build.
        # This is NOT the per-agent `calls` fallback rejected earlier for kiro — kiro HAS a
        # spine (`ide`) and correctly reads zero when its store is absent, exactly as
        # decided. This is about sources that were never in the flip's scope at all.
        if (r.get("ts") or "") >= cut and agents.row_surface(r.get("agent")) in SPEND_SOURCES:
            continue
        r["basis"] = "calls"
        rows.append(r)
    # `claude_metrics` collapses last-write-wins per SESSION — the right reader for a
    # chat-grain whole-life total and the wrong one here, because it would keep one row
    # per chat and discard every other request in it. Request-grain rows are point-in-time
    # facts, so they collapse on their own identity instead (`claude_request_metrics`).
    readers = ((claude_request_metrics, "claude"), (copilot_metrics, "copilot"),
               (kiro_metrics, "kiro"))
    for read_rows, agent in readers:
        allowed = SPEND_SOURCES[agent]
        for r in read_rows(root, since):
            if (r.get("ts") or "") >= cut and r.get("source", "") in allowed:
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
