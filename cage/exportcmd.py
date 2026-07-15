"""`cage data export` — refresh (import) then emit the ledger in a portable format (§3.7).

The pull-based companion to `cage import`: it imports first (so the export is fresh,
unless ``--no-import``), then serializes the active ledger as one of three formats:

- **jsonl** — the raw call rows, lossless and re-ingestable (the default).
- **csv**  — flat raw rows for spreadsheets/BI (stdlib `csv` via `csvout`):
  ``--csv calls|receipts|tasks`` picks the row kind (``--format csv`` is the
  legacy spelling of ``--csv calls``). **Two export kinds, never blurred**: the
  fleet bundle (``--study``) stays jsonl — lossless, merge-by-id, re-importable —
  while CSV is a one-way REPORTING format and never an import source.
- **json** — a structured summary (totals by agent/model/project) whose totals match
  `cage report`.

Counts-never-content: only ledger rows (token *counts*, ids) are emitted, never
prompt bodies — the CSV carries the exact same PII surface as the ledger itself.
Deterministic: rows are emitted in ledger order with LF line endings pinned, so the
same `--since` window yields byte-identical output on any OS. The "↻ imported N new
call(s)" notice goes to **stderr**, so a piped jsonl/csv stdout stream stays pure data.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from cage import csvout, importcmd, ledger, prices
from cage.errors import CageError
from cage.schema import CALL_FIELDS, RECEIPT_FIELDS

# Closed, deterministic CSV column contracts per row kind (docs/csv-output.md).
# calls/receipts extend the schema tuples with the additive fleet `machine` stamp;
# tasks.jsonl has no closed schema tuple, so the export pins one here: identity +
# outcome + label + the recorded-estimate fields (plan §3.4) + the PII-guarded git
# snapshot (counts + top-level dirs only). Unknown extras are ignored — the column
# order never depends on ledger content.
RAW_CSV_FIELDS = {
    "calls": (*CALL_FIELDS, "machine"),
    "receipts": (*RECEIPT_FIELDS, "machine"),
    "tasks": ("id", "ts", "type", "outcome", "label", "agents",
              "est_tokens", "est_usd", "est_n", "est_tokens_q1", "est_tokens_q3",
              "commit", "branch", "files_changed", "insertions", "deletions",
              "dirs", "machine"),
}


class _ImportArgs:
    """The minimal arg shape `importcmd.run` reads (a refresh sweeps full transcripts;
    `--project` is an export *output* filter, never an import scope)."""
    path = None
    project = None

    def __init__(self, agent: str, since: str | None):
        self.agent = agent
        self.since = since


def sweep(root: Path, since: str | None) -> tuple[bool, int]:
    """The all-agent import refresh export runs before emitting/bundling, so a
    capture-only machine (hooks don't fire under a VS Code extension) still ships a
    complete artifact. Always ``"all"`` — an ``--agent`` filter narrows the *output*,
    never the capture. Fail-open: ``(ran, new_calls)``; a failed sweep is warned to
    stderr and export proceeds with the pre-sweep ledger — a broken parser must
    never block a fleet participant from sending their bundle. (`importcmd.run`
    itself honors the capture switch: `CAGE_CAPTURE=0` / `[capture] enabled=false`
    ⇒ the sweep is a no-op.)"""
    try:
        before = len(ledger.calls(root))
        importcmd.run(root, "all", _ImportArgs("all", since))
        added = len(ledger.calls(root)) - before
        print(f"↻ imported {added} new call(s)", file=sys.stderr)
        return True, added
    except Exception:  # fail-open: still export what the ledger already holds
        print("cage data export: import refresh failed — emitting the ledger as-is.",
              file=sys.stderr)
        return False, 0


def _filtered(root: Path, since: str | None, project: str | None, agent: str | None) -> list[dict]:
    rows = ledger.since(ledger.calls(root, since=since), since)
    rows = ledger.by_project(rows, project)
    if agent:
        rows = [r for r in rows if r.get("agent") == agent]
    return rows


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _csv(rows: list[dict], kind: str = "calls") -> str:
    # An empty ledger still emits a valid header-only artifact. LF pinned +
    # canonical cells via csvout (bool → true/false, lists ";"-joined, dicts as
    # sorted JSON) — deterministic across OSes.
    return csvout.dict_rows(RAW_CSV_FIELDS[kind], rows)


def _bucket() -> dict:
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "usd": 0.0}


def _summary(rows: list[dict], pol: dict) -> dict:
    """Totals + breakdowns by agent/model/project. ``usd`` is recomputed per call via the
    same `prices.call_usd` `cage report` uses, so the summary totals match `cage report`."""
    total = _bucket()
    by_agent: dict[str, dict] = {}
    by_model: dict[str, dict] = {}
    by_project: dict[str, dict] = {}
    for c in rows:
        usd = prices.call_usd(pol, c)
        ti, to = c.get("tokens_in", 0), c.get("tokens_out", 0)
        for table, key in ((by_agent, c.get("agent") or "—"),
                           (by_model, c.get("model") or "—"),
                           (by_project, c.get("project") or "—")):
            g = table.setdefault(key, _bucket())
            g["calls"] += 1
            g["tokens_in"] += ti
            g["tokens_out"] += to
            g["usd"] += usd
        total["calls"] += 1
        total["tokens_in"] += ti
        total["tokens_out"] += to
        total["usd"] += usd
    return {"total": total, "by_agent": by_agent, "by_model": by_model, "by_project": by_project}


def render(rows: list[dict], fmt: str, pol: dict, refresh: dict | None = None) -> str:
    if fmt == "jsonl":
        return _jsonl(rows)
    if fmt == "csv":
        return _csv(rows)
    summary = _summary(rows, pol)
    if refresh is not None:
        summary = {"refresh": refresh, **summary}
    return json.dumps(summary, ensure_ascii=False, indent=2) + "\n"


def _raw_rows(root: Path, kind: str, since: str | None) -> list[dict]:
    """Window-filtered raw rows of one kind for the ``--csv`` reporting export —
    rows exactly as the ledger stores them (tasks stay raw append-only updates,
    not the last-write-wins merge: this is the ledger's own PII surface, flat)."""
    return ledger.since(ledger.read_kind(root, kind, since=since), since)


def run(root: Path, args, *, pol: dict) -> int:
    """Import-first (all agents; `--no-import` flag > `[capture] import_before_export`
    policy), then emit. Fail-open: a failed refresh warns and still exports whatever
    is already in the ledger. Bad flag combinations are typed errors (`CageError`)."""
    from cage import policy as _policy
    agent = getattr(args, "agent", None)
    since = getattr(args, "since", None)
    project = getattr(args, "project", None)
    kind = getattr(args, "csv_kind", None)
    fmt = getattr(args, "format", None)
    if kind and fmt:
        raise CageError("--csv and --format are mutually exclusive — --csv calls "
                        "already is the flat call-row CSV")
    if kind and kind != "calls" and (agent or project):
        raise CageError(f"--agent/--project filter call rows only, not {kind} — "
                        "drop the filter or export --csv calls")
    refresh = {"ran": False, "new_calls": 0}
    if getattr(args, "do_import", True) and _policy.import_before_export(pol):
        ran, added = sweep(root, since)
        refresh = {"ran": ran, "new_calls": added}
    fmt = fmt or ("csv" if kind else "jsonl")
    if kind and kind != "calls":
        rows = _raw_rows(root, kind, since)
        out = _csv(rows, kind)
    else:
        rows = _filtered(root, since, project, agent)
        out = render(rows, fmt, pol, refresh=refresh if fmt == "json" else None)
    unit = kind or "call"
    if getattr(args, "output", None):
        try:
            # newline="" pins the LF the renderers emit — no CRLF translation on
            # Windows, so the same window is byte-identical on any OS.
            Path(args.output).write_text(out, encoding="utf-8", newline="")
        except OSError as e:
            raise CageError(f"cannot write export to {args.output}: {e}") from e
        print(f"✔ wrote {len(rows)} {unit.rstrip('s')}(s) → {args.output} ({fmt})",
              file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0
