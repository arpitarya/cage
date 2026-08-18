"""The substrate contract — call-record and receipt row factories (ADR-LAWS).

Rows are plain JSON dicts (append-only, diffable, stdlib-parseable). These
factories stamp ids/timestamps and validate the closed enums so a malformed row
never reaches the log. Prompt *bodies* are never a field — counts only (ADR-LAWS Law 4).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ids

UNITS = ("tokens", "usd", "ms", "gco2")
METHODS = ("measured", "modeled", "estimated")

# Provenance (authorship attribution) is a separate record type with its own closed
# enums — `measured/modeled/estimated` answers "how do we know a saving"; this answers
# "how do we know who wrote it". Keeping the two method vocabularies distinct (rather
# than overloading METHODS) means a provenance row can never misread as a cost claim
# or vice versa. See ADR-AUTHORSHIP.
PROV_METHODS = ("hooked", "transcript", "heuristic")
ORIGINS = ("human", "agent", "agent-autonomous", "unknown")

CALL_FIELDS = ("id", "ts", "session", "task", "agent", "route", "provider", "model",
               "tokens_in", "tokens_out", "cached_in", "est_cost_usd",
               "latency_ms", "ok", "retries", "scope", "project",
               "surface", "cache_write_in", "premium", "import_id", "credits",
               "billed_with")
RECEIPT_FIELDS = ("id", "ts", "call", "task", "tool", "unit", "raw_alternative",
                  "actual", "saved", "method", "confidence", "meta", "scope")
SAVINGS_FIELDS = ("id", "ts", "import_id", "tool", "op", "session", "task", "unit",
                  "raw_alternative", "actual", "saved", "method", "confidence",
                  "source_files", "route_key")

# A savings-tool directory name must be a closed, path-safe token — never a path — so it
# is safe as `savings/<tool>/…` (same PII discipline as `scope`/`label`).
import re as _re  # noqa: E402
_SAFE_TOOL = _re.compile(r"^[a-z0-9][a-z0-9_-]*$")
PROVENANCE_FIELDS = ("schema_ver", "id", "ts", "sha", "agent", "files",
                     "lines_added", "lines_removed", "method", "origin",
                     "confidence", "session_id")

# The line-match counts (agent-vs-human v2, P1) — additive and OPTIONAL: each is
# omitted when zero, so a row from any pre-v2 capture path stays byte-identical to
# `PROVENANCE_FIELDS` and `schema_ver` stays 1 (additive, not a new contract). They
# are the ONLY thing the matcher persists: the proposed line bodies it compares
# exist in process memory for the length of one import and are never written, never
# hashed, and never shipped (counts-never-content, ADR-LAWS Law 4).
#
# `residual_lines` is the ONE deliberate exception to omitted-at-zero: it is written
# whenever the caller supplies it, **including 0**, because presence of the key is the
# version gate for the per-chat `agent%` column (`chats.py`). See `make_provenance`.
PROVENANCE_COUNT_FIELDS = ("suggested", "kept", "kept_modified", "dropped",
                           "agent_lines", "residual_lines")

# Counts written whenever supplied, even at 0 — absence means *this row predates the
# count*, which is a different fact from *this row recorded zero*. Everything else in
# `PROVENANCE_COUNT_FIELDS` is omitted at 0.
PROVENANCE_ZERO_BEARING_COUNTS = ("residual_lines",)


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_call(*, route: str, provider: str, model: str, tokens_in: int = 0,
              tokens_out: int = 0, cached_in: int = 0, est_cost_usd: float = 0.0,
              session: str = "", task: str = "", agent: str = "lib",
              latency_ms: int = 0, ok: bool = True, retries: int = 0,
              scope: str = "", project: str = "",
              surface: str = "", cache_write_in: int = 0, premium: int = 0,
              import_id: str = "", credits: float | None = None,
              billed_with: str = "",
              ts: str | None = None, call_id: str | None = None) -> dict:
    """One ground-truth call row. `cached_in` ⊆ `tokens_in` (billed at discount).

    `call_id` may be supplied for idempotent sources (a transcript turn's uuid) so
    re-parsing the same transcript never double-records the call.

    `scope` is the optional top-level changed dir of the work (ADR-LAWS) — the same
    coarse, counts-safe key `tasks.jsonl` carries (top-level dir only, never sub-paths
    or filenames). Empty string is the default and the non-monorepo case; an empty
    `scope` makes a row byte-identical to the pre-§3.6 contract.

    `project` is the optional working-dir **basename** the call ran under — a *derived
    attribution axis* (ADR-LAWS Law 2 — its `--project` rollup view was deleted in
    SURFACE-CUT; the field is still stamped, and no view reads it), deliberately separate from
    `scope` (the monorepo top-level dir). Basename only, never a full path (the same PII
    guard as `scope`/tasks). Only logs that carry the cwd can set it, so an empty
    `project` is the legacy contract. Three routes stamp it: Claude transcripts (a `cwd`
    on the record itself), Kiro CLI (a store-level cwd), and — since 2026-08-11 — Copilot
    **VS Code**, resolved once per chat-session file from `workspaceStorage/<hash>/
    workspace.json` with the first `run_in_terminal` cwd as fallback
    (`transcript._vscode_project`). Copilot **CLI** and Kiro **IDE** still leave it empty:
    neither store carries a cwd at all. *(This docstring previously said "Copilot/Kiro
    leave it empty" flatly — false for two of those four routes.)*

    Five more additive-optional fields (import-ledger plan §2.1), each **omitted when
    at its default** so an unstamped row stays byte-identical to the legacy contract,
    and **never part of any id**:

    - `surface` — `cli` | `vscode` | `ide` | `""`. Which client wrote the log.
      Derivable for copilot (CLI vs VS Code store) and kiro (`ide`); `""` for claude
      (its CLI and extension share one store — honest, not a TODO).
    - `cache_write_in` — Claude's `cache_creation_input_tokens`, split out of
      `tokens_in` (whose semantics are unchanged) so cache-write cost is exact.
    - `premium` — copilot CLI `totalPremiumRequests`, the one billing-relevant signal
      copilot exposes that was previously dropped.
    - `import_id` — a foreign key to the capture-manifest row that produced this row
      (ADR-CONSUMERS, threaded in Phase 3). Empty until a manifest is written.
    - `credits` — the **billed** AI-credit figure the provider itself computed for this
      request (COPILOT-CREDITS, ADR-COPILOT). Copilot persists it per request in VS Code's
      chatSessions store (`copilotCredits`) and per shutdown in the CLI's
      `totalPremiumRequests`; since 2026-06-01 it *is* GitHub's own tokens×rates
      computation, done with information cage cannot see (what `copilot/auto` actually
      routed to, GitHub's current rates). It is rung 1 of the copilot pricing ladder
      (`cage/creditprice.py`) — recorded count × the configured `[billing.<agent>]
      usd_per_credit`, always `modeled`, never `measured`.

      **`None` and `0.0` are different facts, and the sentinel default exists to keep
      them apart.** `None` (the default) means *not recorded* — the key is omitted and
      the row is byte-identical to the pre-COPILOT-CREDITS contract. `0.0` means the
      store recorded a real zero (an included or 0x-rate model), which rung 1 prices at
      $0.0000 with the rung named. This is the one additive field that does NOT use the
      `if value:` omit-at-default idiom (`surface`/`premium`/`cache_write_in` do): that
      idiom would collapse a recorded zero into absence, and **credits are never derived
      from tokens in either direction, so absence must stay absence**. Float, verbatim —
      the unit is deliberately not interpreted, so a vendor-side unit shift changes
      labels, never invents numbers. Never part of any id.
    - `billed_with` — the id of the row that carries **this row's billing**, when the
      provider computed ONE billed figure over a GROUP of calls (REV-CREDITS defect 2,
      closed 2026-08-11; verdict *one basis per shutdown* in
      `work/compare/copilot-pricing-basis.compare.md`). A copilot-CLI `session.shutdown`
      reports `totalPremiumRequests` over **every** model in that shutdown, so stamping
      the delta on one row while its siblings fell through to tokens×table priced the
      same spend twice — once billed, once at list rates.

      It is a **recorded structural fact** (these rows came out of one shutdown, whose
      billing the provider computed jointly), never a derived number. That distinction is
      the whole reason the other option — splitting the credit pro-rata across the rows
      by token share — was **rejected**: it would derive per-row credits from tokens,
      which the standing `prices.toml` rule forbids in both directions.

      Empty for every row that bills for itself, so an unstamped row is byte-identical to
      the legacy contract. Never part of any id. `prices.call_usd_match` reads it as a
      rung-0 suppression: a stamped row prices at **$0.00 on the credits basis**, with the
      carrier's id as the matched key — *priced, elsewhere, by name*, which is neither a
      fabricated zero nor UNPRICED.
    """
    row = {"id": call_id or ids.new_id("c"), "ts": ts or _now(), "session": session, "task": task,
           "agent": agent, "route": route, "provider": provider, "model": model,
           "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
           "cached_in": int(cached_in), "est_cost_usd": round(float(est_cost_usd), 6),
           "latency_ms": int(latency_ms), "ok": bool(ok), "retries": int(retries),
           "scope": str(scope), "project": str(project)}
    if surface:
        row["surface"] = str(surface)
    if cache_write_in:
        row["cache_write_in"] = int(cache_write_in)
    if premium:
        row["premium"] = int(premium)
    if import_id:
        row["import_id"] = str(import_id)
    if credits is not None:   # `is not None`, never truthiness — 0.0 is a recorded zero
        row["credits"] = float(credits)
    if billed_with:
        row["billed_with"] = str(billed_with)
    return row


def make_receipt(*, tool: str, raw_alternative: float, actual: float,
                 call: str = "", task: str = "", unit: str = "tokens",
                 method: str = "modeled", confidence: float = 1.0,
                 meta: dict | None = None, scope: str = "", route_key: str = "",
                 ts: str | None = None) -> dict:
    """One savings receipt. `saved` is derived so it can never disagree (ADR-LAWS).

    `scope` is the optional top-level changed dir (ADR-LAWS) — same counts-safe key
    as `make_call`; empty by default (non-monorepo), so an unset `scope` is the legacy
    contract.

    `route_key` is the optional non-PII project routing key (`paths.routing_key`, a hash
    of the resolved ledger-root path — never a path, never a basename) stamped on a
    **pushed** receipt (graphify/fux/proxy) so a read can reclaim a stray saving by
    *exact* key (capture-architecture §9.6). Additive and included **only when set** —
    like `surface` on a call, an absent `route_key` is byte-identical to the legacy
    contract, and it is deliberately kept out of the CSV column contract (`RECEIPT_FIELDS`)
    so the reporting CSV is unchanged. Never part of any id.
    """
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} not in {UNITS}")
    if method not in METHODS:
        raise ValueError(f"method {method!r} not in {METHODS}")
    row = {"id": ids.new_id("r"), "ts": ts or _now(), "call": call, "task": task,
           "tool": tool, "unit": unit, "raw_alternative": float(raw_alternative),
           "actual": float(actual), "saved": float(raw_alternative) - float(actual),
           "method": method, "confidence": float(confidence), "meta": meta or {},
           "scope": str(scope)}
    if route_key:
        row["route_key"] = str(route_key)
    return row


def make_savings(*, tool: str, raw_alternative: float, actual: float, op: str = "",
                 session: str = "", task: str = "", unit: str = "tokens",
                 method: str = "modeled", confidence: float = 1.0,
                 source_files: int = 0, import_id: str = "", route_key: str = "",
                 ts: str | None = None, savings_id: str | None = None) -> dict:
    """One dedicated tool-savings row for the ``savings/<tool>/savings-<month>.jsonl``
    tree (import-ledger plan §3). Parallel to `make_receipt` but tuned for tool savings:
    `op` (the tool operation), `source_files` (a **count**, never the paths — PII guard),
    and an `import_id` FK. `saved` is derived (`raw_alternative − actual`) so it can never
    be edited into disagreement. The row is deliberately receipt-compatible (tool/unit/
    raw_alternative/actual/saved/method/confidence/task) so the existing attribution/roi
    surfaces read it unchanged through `ledger.receipts`'s union.

    `tool` is validated as a closed, path-safe token because it names a directory —
    never a path (same discipline as `scope`/`label`). `import_id`/`route_key` are
    additive-optional (omitted when empty), like `route_key` on a receipt.

    `savings_id` may be supplied for deterministic sources (the graphify shim and the
    GC2 transcript route both derive it from the run's content, `graphifymeter.receipt_id`)
    so re-imports dedupe and cross-route duplicates collapse in `ledger.receipts`'
    `union_by_id` — the exact `call_id`/`credit_id`/`row_id` precedent (graphify-capture
    plan GC3, ADR 0005). ``None`` falls back to a fresh random `s_` id, byte-identical to
    before."""
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} not in {UNITS}")
    if method not in METHODS:
        raise ValueError(f"method {method!r} not in {METHODS}")
    if not _SAFE_TOOL.match(tool or ""):
        raise ValueError(f"savings tool {tool!r} must be a path-safe token [a-z0-9_-]")
    row = {"id": savings_id or ids.new_id("s"), "ts": ts or _now(), "tool": str(tool), "op": str(op),
           "session": str(session), "task": str(task), "unit": unit,
           "raw_alternative": float(raw_alternative), "actual": float(actual),
           "saved": float(raw_alternative) - float(actual), "method": method,
           "confidence": float(confidence), "source_files": int(source_files)}
    if import_id:
        row["import_id"] = str(import_id)
    if route_key:
        row["route_key"] = str(route_key)
    return row


def make_credit(*, session: str, credits: float, agent: str = "kiro",
                model: str = "", surface: str = "", context_pct: float = 0.0,
                turns: int = 0, method: str = "measured", ts: str | None = None,
                project: str = "", credit_id: str | None = None) -> dict:
    """One **credits** usage row — a deliberately *distinct* row kind for a source that
    reports credits, not tokens (Kiro CLI's SQLite store; capture-precision §3.4).

    Why not a call row: a call with ``tokens_in=0`` is a lie that poisons every
    token-based average and cost-per-call. Credits are the only usage signal Kiro CLI's
    store carries (`total_tokens` etc. are null even with an explicit model — proven by
    the §0 probe), so they get their own shape, in their own ``credits-<month>.jsonl``
    shard, read by no call-based view.

    **`measured`, retagged from `estimated` in USAGE-ONLY (P3, ADR 0011).** The old tag
    was right for the question then being asked and is wrong for the one asked now. A
    credit was being used as a *stand-in for the dollars cage could not see* — a proxy,
    hence `estimated`. Cage no longer reports dollars, so the credit is no longer
    standing in for anything: it is AWS's own recorded charge for the conversation, read
    back verbatim, which is exactly what `measured` means everywhere else in cage.
    Grading it down now would be the mirror of the error the method law exists to
    prevent — understating provenance is still misstating it.

    **Never priced**, and there is nothing left to price it with. Counts/metadata only:
    session id, model, timestamps, a turn *count*, context %; never a prompt or response
    body.

    `credit_id` is supplied by the parser as a deterministic id that folds in the turn
    count, so a *resumed* conversation (more credits) appends a fresh row while an
    unchanged one dedupes — and `ledger.credits` collapses last-write-wins per session,
    so a grown conversation's credits are never double-summed (the append-only analogue
    of Copilot's delta rows, §3.1).

    `project` is the optional working-dir **basename** the conversation ran under — the
    same additive-optional axis (and the same PII guard: basename only, never a path) that
    `make_call` carries. Kiro's *CLI* store keys every conversation by its cwd, so unlike
    the IDE store it can honestly fill this in (ADR 0006 *Scope*); omitted when empty, so
    an unstamped row stays byte-identical to the pre-0.36 contract."""
    if method not in METHODS:
        raise ValueError(f"method {method!r} not in {METHODS}")
    row = {"id": credit_id or ids.new_id("k"), "ts": ts or _now(),
           "session": str(session), "agent": str(agent), "model": str(model),
           "unit": "credits", "credits": float(credits), "turns": int(turns),
           "context_pct": round(float(context_pct), 4), "method": method}
    if surface:
        row["surface"] = str(surface)
    if project:
        row["project"] = str(project)
    return row


CREDIT_FIELDS = ("id", "ts", "session", "agent", "model", "unit", "credits",
                 "turns", "context_pct", "method", "surface", "project")


# ── consumer metrics (P1, v0.51) ────────────────────────────────────────────────────
#
# One grain and one source, deliberately. A consumer meters at the provider boundary and
# hands cage one response at a time, so `call` is the only grain that exists here; the
# enum is closed and single-valued so a future second grain is a decision rather than a
# string.
CONSUMER_METRIC_SOURCES = ("call",)

CONSUMER_METRIC_FIELDS = ("id", "ts", "agent", "source", "call", "route", "provider",
                          "model", "session", "task", "project", "scope",
                          "tokens_in", "tokens_out", "cached_in", "cache_write_in",
                          "latency_ms", "ok", "retries", "import_id")


def make_consumer_metric(*, route: str, provider: str = "", model: str = "",
                         call: str = "", agent: str = "lib", session: str = "",
                         task: str = "", project: str = "", scope: str = "",
                         source: str = "call",
                         tokens_in: int = 0, tokens_out: int = 0, cached_in: int = 0,
                         cache_write_in: int = 0, latency_ms: int = 0, ok: bool = True,
                         retries: int = 0, import_id: str = "",
                         ts: str | None = None, metric_id: str | None = None) -> dict:
    """One **consumer metrics** row — a library/proxy call, in the same per-producer
    directory shape every other producer now owns (`ledger/consumer/`).

    **This kind is an honest near-duplicate of `calls`, and that was the objection.**
    [ADR-CONSUMERS](../docs/adr/0007_consumer.md) rejected giving consumers a metric
    ledger precisely because *"a metric kind exists to hold vendor-native facts a caller
    could not supply. For a library caller there is no vendor store — the kind would be a
    rename of `calls` with a longer path."* That reasoning is still correct **about the
    facts**, and this kind does not pretend otherwise: it carries no field a call row
    could not. The reversal is about **shape**, not richness — with consumers homed here,
    every producer owns one directory under `ledger/` and `calls` can stop being written
    by anything current, which is what P5 needs. The reversal is recorded in that record,
    not smuggled past it.

    **`call` is the load-bearing field.** It is the id of the `calls` row written in the
    same `record_call` (the dual-write), and it is what lets `ledger.spend()` suppress
    **exactly the twinned rows by id** instead of by agent name. That distinction is the
    whole safety argument: an agent-name test would suppress every *historical* `lib` row
    too — rows written before this kind existed, with no twin to replace them — which is
    the silent-zeroing failure ADR-CONSUMERS measured at 373 codex rows. An id match
    cannot do that. A consumer row written without a `call` suppresses nothing.

    **Counts are omit-at-zero** (the house idiom). **There is no currency field and no
    `est_cost_usd`** — cage measures usage, never cost (ADR 0011). The `calls` twin keeps
    its own legacy `est_cost_usd` untouched under the append-only law; a *new* schema does
    not get one. **No `credits` field either**, and unlike `make_call` that is not a
    sentinel decision: a credit is a vendor's own billing computation and there is no
    vendor here, so there is nothing an absent-vs-zero distinction could ever mean.

    **No `machine` field either, since v0.51.** It existed only so the fleet study could
    partition rows by an opaque per-machine id; the study was removed whole (STUDY-CUT)
    and the field went with it. Rows written before that keep theirs and still read —
    append-only, so the recorded past is never rewritten.

    `metric_id` may be supplied for an idempotent caller; ``None`` mints a fresh `csm_`
    id. Unlike the three agent kinds there is no growth-fold: a consumer row is a
    point-in-time fact about one response and is never re-captured, so there is no later
    version of it to win a last-write-wins collapse."""
    if source not in CONSUMER_METRIC_SOURCES:
        raise ValueError(
            f"consumer-metric source {source!r} not in {CONSUMER_METRIC_SOURCES}")
    row = {"id": metric_id or ids.new_id("csm"), "ts": ts or _now(),
           "agent": str(agent or "lib"), "source": source, "route": str(route)}
    if call:
        row["call"] = str(call)
    if provider:
        row["provider"] = str(provider)
    if model:
        row["model"] = str(model)
    if session:
        row["session"] = str(session)
    if task:
        row["task"] = str(task)
    if project:
        row["project"] = str(project)
    if scope:
        row["scope"] = str(scope)
    if tokens_in:
        row["tokens_in"] = int(tokens_in)
    if tokens_out:
        row["tokens_out"] = int(tokens_out)
    if cached_in:
        row["cached_in"] = int(cached_in)
    if cache_write_in:
        row["cache_write_in"] = int(cache_write_in)
    if latency_ms:
        row["latency_ms"] = int(latency_ms)
    # `ok` is written whenever FALSE — the omit-at-zero idiom inverted, because the
    # default is True. A failed call is the interesting one and must never be omitted
    # into looking like a success.
    if not ok:
        row["ok"] = False
    if retries:
        row["retries"] = int(retries)
    if import_id:
        row["import_id"] = str(import_id)
    return row


# Claude's two grains. `transcript` is the per-chat whole-life total CLAUDE-METRICS
# shipped; `request` is the per-API-response row METRICS-PRIMARY P1 adds, one per folded
# `(requestId, message.id)` — the SAME fold, emitted at the grain the money path needs.
# A closed enum, like `COPILOT_METRIC_SOURCES`. The two describe the same traffic at
# different grains and must NEVER be summed: only `request` is in `ledger.SPEND_SOURCES`,
# and `ledger.claude_metrics`/`claude_request_metrics` are separate readers for that
# reason.
CLAUDE_METRIC_SOURCES = ("transcript", "request")


def make_claude_metric(*, session: str, project: str = "", surface: str = "",
                       source: str = "transcript", request: str = "", model: str = "",
                       provider: str = "",
                       model_totals: list[dict] | None = None,
                       tokens_in: int = 0, tokens_out: int = 0, cached_in: int = 0,
                       cache_write_in: int = 0, ttl_5m: int = 0, ttl_1h: int = 0,
                       thinking: int = 0, web_search: int = 0, web_fetch: int = 0,
                       requests: int = 0, raw_rows: int = 0,
                       sidechain_tokens_in: int = 0, sidechain_tokens_out: int = 0,
                       ts: str | None = None, metric_id: str | None = None) -> dict:
    """One **Claude metrics** row — a store-verbatim, correctly-folded per-chat usage
    fact from the transcript store, kept deliberately separate from `make_call`
    (CLAUDE-METRICS handoff §1). The `calls` schema (§3.1) doesn't hold the cache-TTL
    split, thinking share, server-tool counts, or a sidechain split, and widening it
    again would blur what a call row means; this kind exists so it never has to — the
    `make_copilot_metric`/`make_kiro_metric` precedent, generalized to Claude's one
    store. `agent` is always `"claude-code"`, `source` is always `"transcript"` (one
    store; the constant keeps cross-kind symmetry with copilot's source enum).

    Token semantics **match `make_call`**: `tokens_in` = uncached + cache-read +
    cache-write; `cached_in` = read; `cache_write_in` = write. `ttl_5m + ttl_1h` should
    equal `cache_write_in` when the store carries the TTL split (older rows may not —
    then the two are simply omitted, never backfilled from the total).

    **Counts are omit-at-zero** (the house idiom) — every numeric field here, unlike
    `make_call.credits`/`make_copilot_metric.credits`: **no credits field exists at
    all**, because no credit unit exists for Claude Code anywhere on disk (the research
    doc's firm no) — there is nothing a sentinel could ever distinguish.

    `raw_rows` = usage-bearing assistant rows seen before THE DEDUP LAW folds them;
    `requests` = distinct folded `(requestId, message.id)` keys. The pair together IS
    the inflation evidence the calls-path defect (CLAUDE-DEDUP) produces today —
    `raw_rows / requests` on this row is the same ratio, captured correctly here.

    `model_totals`: list of `{model, tokens_in, tokens_out, cached_in, cache_write_in}`,
    keys whitelisted per entry — an unexpected key on the parser's accumulator can
    never ride along into the ledger. Omitted entirely when empty.

    `metric_id` is always supplied by the parser as a deterministic id that folds in
    the row's own recorded values (the `make_credit`/`make_copilot_metric` turns-fold
    idea, generalized) — so a grown chat (more tokens since the last capture) appends
    a FRESH row rather than silently overwriting a stale one, and `ledger.claude_metrics`
    resolves the latest per session at read time. ``None`` falls back to a fresh
    random `clm_` id."""
    if source not in CLAUDE_METRIC_SOURCES:
        raise ValueError(f"claude-metric source {source!r} not in {CLAUDE_METRIC_SOURCES}")
    row = {"id": metric_id or ids.new_id("clm"), "ts": ts or _now(),
           "agent": "claude-code", "source": source, "session": str(session)}
    if request:
        row["request"] = str(request)
    if model:
        row["model"] = str(model)
    # `provider` exists for exactly one reason (METRICS-PRIMARY P2): `policy.price_match`
    # keys on `(provider, model)`, so a row without it prices as `none` no matter how good
    # its token counts are. It is NOT a new fact — it is the same derivation
    # `transcript.parse_calls` already stamps on every call row from this store
    # (`provider="anthropic"`), moved to the grain the money path now reads. Absent on the
    # chat grain, which never prices as one call.
    if provider:
        row["provider"] = str(provider)
    if surface:
        row["surface"] = str(surface)
    if tokens_in:
        row["tokens_in"] = int(tokens_in)
    if tokens_out:
        row["tokens_out"] = int(tokens_out)
    if cached_in:
        row["cached_in"] = int(cached_in)
    if cache_write_in:
        row["cache_write_in"] = int(cache_write_in)
    if ttl_5m:
        row["ttl_5m"] = int(ttl_5m)
    if ttl_1h:
        row["ttl_1h"] = int(ttl_1h)
    if thinking:
        row["thinking"] = int(thinking)
    if web_search:
        row["web_search"] = int(web_search)
    if web_fetch:
        row["web_fetch"] = int(web_fetch)
    if requests:
        row["requests"] = int(requests)
    if raw_rows:
        row["raw_rows"] = int(raw_rows)
    if sidechain_tokens_in:
        row["sidechain_tokens_in"] = int(sidechain_tokens_in)
    if sidechain_tokens_out:
        row["sidechain_tokens_out"] = int(sidechain_tokens_out)
    if model_totals:
        row["model_totals"] = [
            {"model": str(mt.get("model", "") or ""),
             "tokens_in": int(mt.get("tokens_in", 0) or 0),
             "tokens_out": int(mt.get("tokens_out", 0) or 0),
             "cached_in": int(mt.get("cached_in", 0) or 0),
             "cache_write_in": int(mt.get("cache_write_in", 0) or 0)}
            for mt in model_totals]
    if project:
        row["project"] = str(project)
    return row


CLAUDE_METRIC_FIELDS = ("id", "ts", "agent", "source", "session", "surface",
                        "request", "model", "provider",
                        "tokens_in", "tokens_out", "cached_in", "cache_write_in",
                        "ttl_5m", "ttl_1h", "thinking", "web_search", "web_fetch",
                        "requests", "raw_rows", "sidechain_tokens_in",
                        "sidechain_tokens_out", "model_totals", "project")


# The five on-disk Copilot stores that carry per-chat usage numbers cage's `calls`
# schema doesn't (COPILOT-METRICS, docs/copilot-metrics-ledger.handoff.md §4.1):
# `chat` (VS Code chatSessions, per-request) · `cli` (Copilot CLI session-state,
# per-session-cumulative) · `sidecar`/`debuglog`/`otel` (three opt-in, per-model-call
# stores). A closed enum, like `UNITS`/`METHODS` — `make_copilot_metric` validates it.
# `cli-delta` is the ONE derived source in this otherwise store-verbatim kind, and the
# exception is deliberate + named (METRICS-PRIMARY P0a). The CLI store writes only
# CUMULATIVE per-shutdown totals; a cumulative row cannot be a spend spine, because the
# cutover partitions the time axis by each row's own `ts` and a cumulative row carries
# its session's whole life at the latest capture — a session straddling the cutover would
# be billed twice. So `cli` stays exactly as the store wrote it (verbatim, the kind's
# reason to exist) and `cli-delta` is emitted ALONGSIDE it, carrying the per-shutdown
# delta, using the same arithmetic and the same reset rule `parse_copilot_cli_calls`
# already applies for the `calls` kind. Both are written; only `cli-delta` is in
# `ledger.SPEND_SOURCES`. Never sum the two.
COPILOT_METRIC_SOURCES = ("chat", "cli", "cli-delta", "sidecar", "debuglog", "otel")


def make_copilot_metric(*, source: str, session: str, surface: str = "",
                        request: str = "", call: str = "", model: str = "",
                        provider: str = "",
                        tokens_in: int = 0, tokens_out: int = 0, cached_in: int = 0,
                        model_totals: list[dict] | None = None,
                        credits: float | None = None,
                        session_credits: float | None = None,
                        nano_aiu: float | None = None,
                        elapsed_ms: int = 0, waiting_ms: int = 0, ttft_ms: int = 0,
                        ts: str | None = None, project: str = "",
                        metric_id: str | None = None) -> dict:
    """One **Copilot metrics** row — a vendor-recorded usage fact from one of the five
    on-disk stores, kept deliberately separate from `make_call` (COPILOT-METRICS handoff
    §1). Widening the closed call schema again for facts at three different grains
    (per-request / per-session-cumulative / per-model-call) would blur what a `calls` row
    means; this kind exists so it never has to.

    `agent` is always `"copilot"`; `source` is validated against
    `COPILOT_METRIC_SOURCES` — every other field describes WHICH request/session/call
    the row is about and WHAT the store recorded for it, verbatim, no derivation.

    **Counts are omit-at-zero** (`tokens_in`/`tokens_out`/`cached_in`/`elapsed_ms`/
    `waiting_ms`/`ttft_ms`) — the house idiom, same as `make_call`.

    **`credits` / `session_credits` / `nano_aiu` are None-sentinel, never omit-at-zero**
    — the same law `make_call.credits` already breaks the pattern for, and for the same
    reason: a store that recorded a real `0.0` and a store that recorded nothing are
    different facts, and absence must never collapse into a fabricated zero. Never
    derived from one another or from tokens at capture — that division is derive-time
    work, if it ever happens at all.

    `model_totals` — the chatSessions store's new per-request, per-model usage list
    (`[{model, inputTokens, cachedTokens, outputTokens}]`) — is read through a strict
    whitelist: only the four named keys survive per entry, renamed to `model`/
    `tokens_in`/`cached_in`/`tokens_out`, so an unexpected key on the store's dict can
    never ride along into the ledger. Omitted entirely when empty.

    `metric_id` is always supplied by a parser as a deterministic id that folds in the
    row's own values (the `make_credit`/`make_savings` turns-fold idea, generalized) —
    so a grown chatSessions request or a resumed CLI session appends a FRESH row rather
    than silently losing the update, and `ledger.copilot_metrics` collapses to the
    latest per key at read time. ``None`` falls back to a fresh random `cm_` id."""
    if source not in COPILOT_METRIC_SOURCES:
        raise ValueError(f"copilot-metric source {source!r} not in {COPILOT_METRIC_SOURCES}")
    row = {"id": metric_id or ids.new_id("cm"), "ts": ts or _now(),
           "agent": "copilot", "source": source, "session": str(session)}
    if surface:
        row["surface"] = str(surface)
    if request:
        row["request"] = str(request)
    if call:
        row["call"] = str(call)
    if model:
        row["model"] = str(model)
    # METRICS-PRIMARY P2 — `policy.price_match` keys on (provider, model), so a spine row
    # without it prices as `none`. The same `_copilot_provider(model)` derivation
    # `parse_copilot_*_calls` already stamps, at the grain the money path reads.
    if provider:
        row["provider"] = str(provider)
    if tokens_in:
        row["tokens_in"] = int(tokens_in)
    if tokens_out:
        row["tokens_out"] = int(tokens_out)
    if cached_in:
        row["cached_in"] = int(cached_in)
    if model_totals:
        row["model_totals"] = [
            {"model": str(mt.get("model", "") or ""),
             "tokens_in": int(mt.get("tokens_in", 0) or 0),
             "cached_in": int(mt.get("cached_in", 0) or 0),
             "tokens_out": int(mt.get("tokens_out", 0) or 0)}
            for mt in model_totals]
    if credits is not None:
        row["credits"] = float(credits)
    if session_credits is not None:
        row["session_credits"] = float(session_credits)
    if nano_aiu is not None:
        row["nano_aiu"] = float(nano_aiu)
    if elapsed_ms:
        row["elapsed_ms"] = int(elapsed_ms)
    if waiting_ms:
        row["waiting_ms"] = int(waiting_ms)
    if ttft_ms:
        row["ttft_ms"] = int(ttft_ms)
    if project:
        row["project"] = str(project)
    return row


# The three grains a Kiro store actually persists usage at (KIRO-METRICS,
# docs/kiro-metrics-ledger.handoff.md §4.1) — Kiro's own on-disk stores, not the wire
# protocol (which carries more but is proxy-only, out of scope here): `ide-log` (the
# IDE's append-only `tokens_generated.jsonl`, per LLM call) · `cli-conv` (CLI SQLite
# store, per conversation, cumulative-verbatim) · `cli-turn` (same store, per history
# turn — the populated `request_metadata` fields, plus token slots that are NULL today
# but schema-present). A closed enum, like `COPILOT_METRIC_SOURCES` — `make_kiro_metric`
# validates it.
#
# A fourth source, `ide`, lived here through 2026-08-15 for `devdata.sqlite` — a SQLite
# twin of the SAME counter `ide-log` reads, timestamped and with a cursorable `id` the
# jsonl lacks. It was never observed on any install cage has probed; its dead reader
# was removed (DEVDATA-CUT, docs/adr/0006_kiro.md) rather than kept armed for a store
# that may never ship — see that record's Veto condition for what would bring it back.
KIRO_METRIC_SOURCES = ("ide-log", "cli-conv", "cli-turn")


def make_kiro_metric(*, source: str, session: str = "", surface: str = "",
                     turn: str = "", model: str = "", provider: str = "",
                     tokens_in: int = 0, tokens_out: int = 0, cached_in: int = 0,
                     cached_out: int = 0, credits: float | None = None,
                     context_pct: float = 0.0, turns: int = 0, chunks: int = 0,
                     prompt_bytes: int = 0, response_bytes: int = 0,
                     tool_uses: int = 0, row_ref: str = "", ts: str | None = None,
                     project: str = "", metric_id: str | None = None) -> dict:
    """One **Kiro metrics** row — a store-verbatim usage fact from one of Kiro's two
    on-disk stores, kept deliberately separate from `make_call`/`make_credit`
    (KIRO-METRICS handoff §1). Widening either of those again for facts at three
    different grains (per-IDE-call / per-CLI-conversation / per-CLI-turn) would blur
    what those rows mean; this kind exists so it never has to — the `make_copilot_metric`
    precedent, generalized to Kiro's stores.

    `agent` is always `"kiro"`; `source` is validated against `KIRO_METRIC_SOURCES` —
    every other field describes WHICH call/conversation/turn the row is about and WHAT
    the store recorded for it, verbatim, no derivation.

    **Counts are omit-at-zero** (`tokens_in`/`tokens_out`/`cached_in`/`cached_out`/
    `turns`/`chunks`/`prompt_bytes`/`response_bytes`/`tool_uses`) — the house idiom.

    **`credits` is None-sentinel, never omit-at-zero** — the same law `make_call.credits`
    and `make_copilot_metric.credits` already break the pattern for: a store that
    recorded a real `0.0` and a store that recorded nothing are different facts.

    **Never estimated.** The community chars÷4 / cumulative-context / chunk-count trio
    is explicitly BANNED as a source for `tokens_in`/`tokens_out`/`cached_in`/
    `cached_out` — `chunks` is recorded as a chunk *count* (from
    `len(request_metadata.time_between_chunks)`), never repurposed as a token figure.
    `cached_in`/`cached_out`/the CLI `tokens_*` slots are filled ONLY when the store's
    own `request_metadata` field is non-NULL — today that means every `cli-turn` row
    omits them (the upgrade-watch: the day Kiro starts filling those fields, capture
    picks them up with zero code change).

    `row_ref` is the store's own row key (`ide-log`'s line index, or the CLI turn's
    `request_metadata.message_id`) — provenance, and the dedupe anchor.

    `metric_id` is always supplied by a parser as a deterministic id that folds in the
    row's own values (the `make_credit`/`make_copilot_metric` turns-fold idea) — so a
    grown CLI conversation appends a FRESH row rather than silently losing the update,
    and `ledger.kiro_metrics` collapses to the latest per key at read time. ``None``
    falls back to a fresh random `km_` id."""
    if source not in KIRO_METRIC_SOURCES:
        raise ValueError(f"kiro-metric source {source!r} not in {KIRO_METRIC_SOURCES}")
    row = {"id": metric_id or ids.new_id("km"), "ts": ts or _now(),
           "agent": "kiro", "source": source}
    if session:
        row["session"] = str(session)
    if surface:
        row["surface"] = str(surface)
    if turn:
        row["turn"] = str(turn)
    if model:
        row["model"] = str(model)
    if provider:
        row["provider"] = str(provider)
    if tokens_in:
        row["tokens_in"] = int(tokens_in)
    if tokens_out:
        row["tokens_out"] = int(tokens_out)
    if cached_in:
        row["cached_in"] = int(cached_in)
    if cached_out:
        row["cached_out"] = int(cached_out)
    if credits is not None:
        row["credits"] = float(credits)
    if context_pct:
        row["context_pct"] = round(float(context_pct), 4)
    if turns:
        row["turns"] = int(turns)
    if chunks:
        row["chunks"] = int(chunks)
    if prompt_bytes:
        row["prompt_bytes"] = int(prompt_bytes)
    if response_bytes:
        row["response_bytes"] = int(response_bytes)
    if tool_uses:
        row["tool_uses"] = int(tool_uses)
    if row_ref:
        row["row_ref"] = str(row_ref)
    if project:
        row["project"] = str(project)
    return row


KIRO_METRIC_FIELDS = ("id", "ts", "agent", "source", "session", "surface", "turn",
                      "model", "provider", "tokens_in", "tokens_out", "cached_in",
                      "cached_out", "credits", "context_pct", "turns", "chunks",
                      "prompt_bytes", "response_bytes", "tool_uses", "row_ref",
                      "project")


def _repo_relative(path: str) -> None:
    if path.startswith("/") or path.startswith("~") or ".." in Path(path).parts:
        raise ValueError(f"provenance file path must be repo-relative: {path!r}")


def make_provenance(*, sha: str, files: list[str], agent: str = "",
                    lines_added: int = 0, lines_removed: int = 0,
                    method: str = "heuristic", origin: str = "unknown",
                    confidence: float = 0.0, session_id: str = "",
                    ts: str | None = None, schema_ver: int = 1,
                    row_id: str | None = None, suggested: int = 0, kept: int = 0,
                    kept_modified: int = 0, dropped: int = 0,
                    agent_lines: int = 0, residual_lines: int | None = None) -> dict:
    """One authorship-attribution row — which agent touched which files in `sha`.

    `origin="human"` is reachable only by explicit attestation (ADR-AUTHORSHIP), which is
    always `method="heuristic"` (no automated signal fired; a person asserted it) — so
    this combination is the one case where the row's own fields enforce that rule.
    Counts-never-content: `files` are validated repo-relative, never absolute, and the
    row carries paths + line counts only — never diff bodies or commit messages.

    The line-match counts (`PROVENANCE_COUNT_FIELDS`, agent-vs-human v2 P1) are
    **additive-optional** — each is omitted at 0, so a row from any other capture path
    is byte-identical to the pre-v2 contract and `schema_ver` stays 1. They partition
    what the agent PROPOSED in this session against what the commit actually contains:

    - `suggested` — proposed lines that cleared the min-content gate (matchable).
    - `kept` — of those, the ones that landed **verbatim** in the commit's added lines.
    - `kept_modified` — proposed lines whose FILE landed but whose line did not match.
    - `dropped` — proposed lines whose file is absent from the commit entirely.
      (`suggested == kept + kept_modified + dropped`, by construction.)
    - `agent_lines` — the added-line side of the same match: commit lines attributed
      to this agent. Equal to `kept` today because matching consumes 1:1, and kept as
      its own name because it answers the other question ("how much of this commit is
      the agent's", not "how much of the agent's suggestion survived") — the two
      diverge the moment matching stops being one-to-one.

    **`residual_lines` is the one count written at 0** (`PROVENANCE_ZERO_BEARING_COUNTS`),
    and the deviation is deliberate. It is the *other* side of `agent_lines` inside this
    row's own landed files — matchable added lines there, minus `agent_lines`, floored at
    0 (computed in `authorcapture.capture`) — and the per-chat `agent%` column reads the
    two together. Omitting it at 0 would make *everything matchable matched the agent*
    (a real, and the most flattering, finding) indistinguishable from *this row predates
    the count*, whose honest render is `—`. So **presence of the key is the version
    gate**: `None` (the default) omits it and keeps every legacy and non-matching caller
    byte-identical; any supplied value, `0` included, is written. Same absent-vs-recorded-
    zero law as `credits`' `None` sentinel on `make_call`. Rows are frozen by
    `originrecord`'s idempotency key, so pre-upgrade rows can never be backfilled — they
    must stay distinguishable forever, not be guessed at.

    Deliberately **not** persisted: `unknown` (sub-gate and binary-file lines) and
    `not-proposed` (files in the commit nobody proposed). Both are properties of the
    COMMIT, not of any one (agent, session) row, and both re-derive exactly from git
    at read time — which the commit views must touch anyway. Persisting a commit-level
    fact once per session row would let two rows disagree about one commit.
    """
    if method not in PROV_METHODS:
        raise ValueError(f"method {method!r} not in {PROV_METHODS}")
    if origin not in ORIGINS:
        raise ValueError(f"origin {origin!r} not in {ORIGINS}")
    if origin == "human" and method != "heuristic":
        raise ValueError("origin='human' is only reachable via attestation (method='heuristic')")
    for f in files:
        _repo_relative(f)
    row = {"schema_ver": schema_ver, "id": row_id or ids.new_id("p"), "ts": ts or _now(),
           "sha": sha, "agent": agent, "files": list(files),
           "lines_added": int(lines_added), "lines_removed": int(lines_removed),
           "method": method, "origin": origin, "confidence": float(confidence),
           "session_id": session_id}
    for name, value in (("suggested", suggested), ("kept", kept),
                        ("kept_modified", kept_modified), ("dropped", dropped),
                        ("agent_lines", agent_lines)):
        if value:
            row[name] = int(value)
    # The zero-bearing count: supplied ⇒ written (0 included), None ⇒ absent.
    if residual_lines is not None:
        row["residual_lines"] = int(residual_lines)
    return row
