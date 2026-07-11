"""Shared CSV renderer for the read views — one table shape, two renderers.

CSV is a **reporting** format: flat, one-way, for spreadsheets/BI. It is never an
import source, and it is deliberately distinct from the fleet bundle
(`cage export --study`, jsonl — lossless, merge-by-id, re-importable). Every view
that grows `--csv` passes the *same* data structure its text renderer consumes, so
the two outputs cannot disagree — no view computes twice (the same-numbers-by-
construction rule).

Laws this module pins:

- **stdlib `csv`, $0** — RFC-4180 quoting comes from the module, never hand-rolled.
- **Determinism** — LF line endings regardless of OS (`lineterminator="\\n"` here;
  file writes pass `newline=""` so the platform layer can't re-translate), one
  canonical number rendering (no locale, no float noise), fixed column order per
  view (documented in docs/csv-output.md).
- **`method` is sacred** — method/match tags are columns, never dropped; a
  spreadsheet must be able to tell `measured` from `estimated`.
"""
from __future__ import annotations

import csv
import io
import json
import sys
from pathlib import Path


def cell(v) -> str:
    """One canonical, deterministic cell rendering.

    bool → true/false (spreadsheet-friendly, checked before int — bool is an int
    subclass) · float → trimmed 6-decimal fixed point (no exponent, no repr noise)
    · list/tuple → ";"-joined (never a comma — the delimiter stays unambiguous)
    · dict → compact sorted JSON (RFC-4180 quoting handles its commas) · None → "".
    """
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return f"{v:.6f}".rstrip("0").rstrip(".") or "0"
    if isinstance(v, (list, tuple)):
        return ";".join(cell(x) for x in v)
    if isinstance(v, dict):
        return json.dumps(v, sort_keys=True, ensure_ascii=False,
                          separators=(",", ":"))
    return str(v)


def table(headers: list[str], rows: list[list]) -> str:
    """Header + rows as one CSV string (LF-terminated lines, RFC-4180 quoting).
    An empty view still emits a valid header-only artifact."""
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(headers)
    for r in rows:
        w.writerow([cell(v) for v in r])
    return buf.getvalue()


def dict_rows(fieldnames: tuple[str, ...], rows: list[dict]) -> str:
    """Raw ledger rows flattened against a fixed field list (the export path).
    Unknown extra keys are ignored — the column contract stays closed and
    deterministic; absent keys render empty."""
    return table(list(fieldnames), [[r.get(f) for f in fieldnames] for r in rows])


def write(text: str, dest: str) -> int:
    """Emit a rendered CSV: ``"-"`` → stdout (pipe-friendly, no trailing chatter);
    a path → the file, ``newline=""`` so the LF lines survive Windows untranslated.
    The confirmation goes to **stderr** — stdout stays pure data. Unwritable target
    is a user-facing failure (`CageError` at the CLI boundary)."""
    if dest == "-":
        sys.stdout.write(text)
        return 0
    from cage.errors import CageError
    p = Path(dest)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8", newline="") as fh:
            fh.write(text)
    except OSError as e:
        raise CageError(f"cannot write CSV to {dest}: {e}") from e
    print(f"✔ wrote {dest} (csv)", file=sys.stderr)
    return 0
