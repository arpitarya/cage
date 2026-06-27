"""`cage export` — refresh (import) then emit the ledger in a portable format (§3.7).

The pull-based companion to `cage import`: it imports first (so the export is fresh,
unless ``--no-import``), then serializes the active ledger as one of three formats:

- **jsonl** — the raw call rows, lossless and re-ingestable (the default).
- **csv**  — a flat row-per-call table for spreadsheets/BI (stdlib `csv`).
- **json** — a structured summary (totals by agent/model/project) whose totals match
  `cage report`.

Counts-never-content: only the call rows (token *counts*) are emitted, never prompt
bodies. Deterministic: rows are emitted in ledger order, so the same `--since` window
yields byte-identical output. The "↻ imported N new call(s)" notice goes to **stderr**,
so a piped jsonl/csv stdout stream stays pure data.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path

from cage import importcmd, ledger, prices
from cage.schema import CALL_FIELDS


class _ImportArgs:
    """The minimal arg shape `importcmd.run` reads (a refresh sweeps full transcripts;
    `--project` is an export *output* filter, never an import scope)."""
    path = None
    project = None

    def __init__(self, agent: str, since: str | None):
        self.agent = agent
        self.since = since


def _filtered(root: Path, since: str | None, project: str | None, agent: str | None) -> list[dict]:
    rows = ledger.since(ledger.calls(root, since=since), since)
    rows = ledger.by_project(rows, project)
    if agent:
        rows = [r for r in rows if r.get("agent") == agent]
    return rows


def _jsonl(rows: list[dict]) -> str:
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows)


def _csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(CALL_FIELDS), extrasaction="ignore")
    w.writeheader()  # an empty ledger still emits a valid header-only artifact
    for r in rows:
        w.writerow(r)
    return buf.getvalue()


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


def render(rows: list[dict], fmt: str, pol: dict) -> str:
    if fmt == "jsonl":
        return _jsonl(rows)
    if fmt == "csv":
        return _csv(rows)
    return json.dumps(_summary(rows, pol), ensure_ascii=False, indent=2) + "\n"


def run(root: Path, args, *, pol: dict) -> int:
    """Import-first (unless ``--no-import``), then emit. Fail-open: a failed refresh warns
    and still exports whatever is already in the ledger."""
    agent = getattr(args, "agent", None)
    since = getattr(args, "since", None)
    if getattr(args, "do_import", True):
        imported = 0
        try:
            before = len(ledger.calls(root))
            importcmd.run(root, agent or "all", _ImportArgs(agent or "all", since))
            imported = len(ledger.calls(root)) - before
        except Exception:  # fail-open: still export what the ledger already holds
            print("cage export: import refresh failed — emitting the ledger as-is.", file=sys.stderr)
        print(f"↻ imported {imported} new call(s)", file=sys.stderr)
    rows = _filtered(root, since, getattr(args, "project", None), agent)
    out = render(rows, args.format, pol)
    if getattr(args, "output", None):
        Path(args.output).write_text(out, encoding="utf-8")
        print(f"✔ wrote {len(rows)} call(s) → {args.output} ({args.format})", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0
