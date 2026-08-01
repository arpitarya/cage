"""The substrate contract — call-record and receipt row factories (plan §3.1–3.2).

Rows are plain JSON dicts (append-only, diffable, stdlib-parseable). These
factories stamp ids/timestamps and validate the closed enums so a malformed row
never reaches the log. Prompt *bodies* are never a field — counts only (plan §10).
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
# or vice versa. See docs/PLAN.md §3.5.
PROV_METHODS = ("hooked", "transcript", "heuristic")
ORIGINS = ("human", "agent", "agent-autonomous", "unknown")

CALL_FIELDS = ("id", "ts", "session", "task", "agent", "route", "provider", "model",
               "tokens_in", "tokens_out", "cached_in", "est_cost_usd",
               "latency_ms", "ok", "retries", "scope", "project",
               "surface", "cache_write_in", "premium", "import_id")
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


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_call(*, route: str, provider: str, model: str, tokens_in: int = 0,
              tokens_out: int = 0, cached_in: int = 0, est_cost_usd: float = 0.0,
              session: str = "", task: str = "", agent: str = "lib",
              latency_ms: int = 0, ok: bool = True, retries: int = 0,
              scope: str = "", project: str = "",
              surface: str = "", cache_write_in: int = 0, premium: int = 0,
              import_id: str = "", ts: str | None = None,
              call_id: str | None = None) -> dict:
    """One ground-truth call row. `cached_in` ⊆ `tokens_in` (billed at discount).

    `call_id` may be supplied for idempotent sources (a transcript turn's uuid) so
    re-parsing the same transcript never double-records the call.

    `scope` is the optional top-level changed dir of the work (plan §3.6.2) — the same
    coarse, counts-safe key `tasks.jsonl` carries (top-level dir only, never sub-paths
    or filenames). Empty string is the default and the non-monorepo case; an empty
    `scope` makes a row byte-identical to the pre-§3.6 contract.

    `project` is the optional working-dir **basename** the call ran under — a *derived
    attribution axis* (`cage report --project`, plan §3.7), deliberately separate from
    `scope` (the monorepo top-level dir). Basename only, never a full path (the same PII
    guard as `scope`/tasks). Only logs that carry the cwd can set it (Claude transcripts
    do; Copilot/Kiro leave it empty), so an empty `project` is the legacy contract.

    Four more additive-optional fields (import-ledger plan §2.1), each **omitted when
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
      (plan §4, threaded in Phase 3). Empty until a manifest is written.
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
    return row


def make_receipt(*, tool: str, raw_alternative: float, actual: float,
                 call: str = "", task: str = "", unit: str = "tokens",
                 method: str = "modeled", confidence: float = 1.0,
                 meta: dict | None = None, scope: str = "", route_key: str = "",
                 ts: str | None = None) -> dict:
    """One savings receipt. `saved` is derived so it can never disagree (plan §3.2).

    `scope` is the optional top-level changed dir (plan §3.6.2) — same counts-safe key
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
                turns: int = 0, method: str = "estimated", ts: str | None = None,
                project: str = "", credit_id: str | None = None) -> dict:
    """One **credits** usage row — a deliberately *distinct* row kind for a source that
    reports credits, not tokens (Kiro CLI's SQLite store; capture-precision §3.4).

    Why not a call row: a call with ``tokens_in=0`` is a lie that poisons every
    token-based average and cost-per-call. Credits are the only usage signal Kiro CLI's
    store carries (`total_tokens` etc. are null even with an explicit model — proven by
    the §0 probe), so they get their own shape, in their own ``credits-<month>.jsonl``
    shard, read by no call-based view. **Never `measured`** — the credit *value* is real,
    but as a stand-in for the tokens/cost cage cannot see it is a proxy, so `estimated`.
    **Recorded, not priced** by default (an unattested credit→USD rate would be a guess
    wearing a number — handoff §6). Counts/metadata only: session id, model, timestamps,
    a turn *count*, context %; never a prompt or response body.

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


def _repo_relative(path: str) -> None:
    if path.startswith("/") or path.startswith("~") or ".." in Path(path).parts:
        raise ValueError(f"provenance file path must be repo-relative: {path!r}")


def make_provenance(*, sha: str, files: list[str], agent: str = "",
                    lines_added: int = 0, lines_removed: int = 0,
                    method: str = "heuristic", origin: str = "unknown",
                    confidence: float = 0.0, session_id: str = "",
                    ts: str | None = None, schema_ver: int = 1,
                    row_id: str | None = None) -> dict:
    """One authorship-attribution row — which agent touched which files in `sha`.

    `origin="human"` is reachable only by explicit attestation (plan §3.5), which is
    always `method="heuristic"` (no automated signal fired; a person asserted it) — so
    this combination is the one case where the row's own fields enforce that rule.
    Counts-never-content: `files` are validated repo-relative, never absolute, and the
    row carries paths + line counts only — never diff bodies or commit messages.
    """
    if method not in PROV_METHODS:
        raise ValueError(f"method {method!r} not in {PROV_METHODS}")
    if origin not in ORIGINS:
        raise ValueError(f"origin {origin!r} not in {ORIGINS}")
    if origin == "human" and method != "heuristic":
        raise ValueError("origin='human' is only reachable via attestation (method='heuristic')")
    for f in files:
        _repo_relative(f)
    return {"schema_ver": schema_ver, "id": row_id or ids.new_id("p"), "ts": ts or _now(),
            "sha": sha, "agent": agent, "files": list(files),
            "lines_added": int(lines_added), "lines_removed": int(lines_removed),
            "method": method, "origin": origin, "confidence": float(confidence),
            "session_id": session_id}
