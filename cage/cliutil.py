"""Shared CLI helpers (≤50 lines)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from cage import paths


def root() -> Path:
    """The **project** root (nearest `.cage/`) or the cwd — for scaffold/wiring/git
    commands (`init`, `setup`, `doctor`, `origin`, `notes-sync`, `verify`, `ledger-sync`)
    that act on *this directory's* project, never the global ledger."""
    return paths.find_project_root() or Path.cwd()


def ledger_root() -> Path:
    """The root whose `.cage/` is the **active ledger**, per the capture precedence
    (`--ledger`/`CAGE_BASE` → nearest project `.cage/` → global `~/.cage`, plan §3.7) —
    for every read/emit/capture command (`report`, `import`, `export`, `watch`, …). Capture
    is global by default: a no-project user reads/writes the global ledger rather than
    scattering a footprint into the cwd."""
    return paths.resolve_root()


def emit(args, payload: dict, text: str) -> int:
    """Print machine-readable JSON when ``--json`` is set, else the human text."""
    if getattr(args, "json", False):
        print(_json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(text)
    return 0


def csv_dest(args) -> str | None:
    """The ``--csv`` destination (``"-"`` = stdout), or ``None`` when the flag is
    absent. One output format per invocation: combining ``--csv`` with ``--json``
    or ``--html`` is a typed error at the CLI boundary — two formats on one stdout
    would be neither."""
    dest = getattr(args, "csv", None)
    if dest is None:
        return None
    from cage.errors import CageError
    if getattr(args, "json", False):
        raise CageError("--csv and --json are mutually exclusive — pick one output format")
    if getattr(args, "html", None):
        raise CageError("--csv and --html are mutually exclusive — pick one output format")
    return dest
