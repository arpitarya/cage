"""The substrate contract — call-record and receipt row factories (plan §3.1–3.2).

Rows are plain JSON dicts (append-only, diffable, stdlib-parseable). These
factories stamp ids/timestamps and validate the closed enums so a malformed row
never reaches the log. Prompt *bodies* are never a field — counts only (plan §10).
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from cage import ids

UNITS = ("tokens", "usd", "ms", "gco2", "minutes")
METHODS = ("measured", "modeled", "estimated")

# Provenance (authorship attribution) is a separate record type with its own closed
# enums — `measured/modeled/estimated` answers "how do we know a saving"; this answers
# "how do we know who wrote it". Keeping the two method vocabularies distinct (rather
# than overloading METHODS) means a provenance row can never misread as a cost claim
# or vice versa. See docs/cage-plan.md §3.5.
PROV_METHODS = ("hooked", "transcript", "heuristic")
ORIGINS = ("human", "agent", "agent-autonomous", "unknown")

CALL_FIELDS = ("id", "ts", "session", "task", "agent", "route", "provider", "model",
               "tokens_in", "tokens_out", "cached_in", "est_cost_usd",
               "latency_ms", "ok", "retries", "scope", "project", "gap_ms")
RECEIPT_FIELDS = ("id", "ts", "call", "task", "tool", "unit", "raw_alternative",
                  "actual", "saved", "method", "confidence", "meta", "scope")
PROVENANCE_FIELDS = ("schema_ver", "id", "ts", "sha", "agent", "files",
                     "lines_added", "lines_removed", "method", "origin",
                     "confidence", "session_id")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def make_call(*, route: str, provider: str, model: str, tokens_in: int = 0,
              tokens_out: int = 0, cached_in: int = 0, est_cost_usd: float = 0.0,
              session: str = "", task: str = "", agent: str = "lib",
              latency_ms: int = 0, ok: bool = True, retries: int = 0,
              scope: str = "", project: str = "", gap_ms: int | None = None,
              ts: str | None = None, call_id: str | None = None) -> dict:
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
    do; Copilot/Kiro/Codex leave it empty), so an empty `project` is the legacy contract.

    `gap_ms` is the optional wall-clock gap (milliseconds) between the end of the
    previous assistant turn and the human user turn that led to this call — the raw
    signal behind the derived human-attention axis (plan §4.10). Timestamps/counts
    only. Stamped solely where a transcript carries real per-turn timestamps (Claude
    today); `None` omits the field entirely, so an unstamped row is byte-identical
    to the legacy contract. Never part of any id derivation.
    """
    row = {"id": call_id or ids.new_id("c"), "ts": ts or _now(), "session": session, "task": task,
           "agent": agent, "route": route, "provider": provider, "model": model,
           "tokens_in": int(tokens_in), "tokens_out": int(tokens_out),
           "cached_in": int(cached_in), "est_cost_usd": round(float(est_cost_usd), 6),
           "latency_ms": int(latency_ms), "ok": bool(ok), "retries": int(retries),
           "scope": str(scope), "project": str(project)}
    if gap_ms is not None:
        row["gap_ms"] = int(gap_ms)
    return row


def make_receipt(*, tool: str, raw_alternative: float, actual: float,
                 call: str = "", task: str = "", unit: str = "tokens",
                 method: str = "modeled", confidence: float = 1.0,
                 meta: dict | None = None, scope: str = "", ts: str | None = None) -> dict:
    """One savings receipt. `saved` is derived so it can never disagree (plan §3.2).

    `scope` is the optional top-level changed dir (plan §3.6.2) — same counts-safe key
    as `make_call`; empty by default (non-monorepo), so an unset `scope` is the legacy
    contract.
    """
    if unit not in UNITS:
        raise ValueError(f"unit {unit!r} not in {UNITS}")
    if method not in METHODS:
        raise ValueError(f"method {method!r} not in {METHODS}")
    return {"id": ids.new_id("r"), "ts": ts or _now(), "call": call, "task": task,
            "tool": tool, "unit": unit, "raw_alternative": float(raw_alternative),
            "actual": float(actual), "saved": float(raw_alternative) - float(actual),
            "method": method, "confidence": float(confidence), "meta": meta or {},
            "scope": str(scope)}


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
