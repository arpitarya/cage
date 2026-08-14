"""Shared CLI helpers (≤50 lines)."""
from __future__ import annotations

import json as _json
from pathlib import Path

from cage import paths


def root() -> Path:
    """The **project** root (nearest `.cage/`) or the cwd — for scaffold/wiring/git
    commands (`init`, `setup`, `doctor`, `origin`, `notes-sync`, `verify`)
    that act on *this directory's* project, never the global ledger."""
    return paths.find_project_root() or Path.cwd()


def ledger_root() -> Path:
    """The root whose `.cage/` is the **active ledger**, per the capture precedence
    (`--ledger`/`CAGE_BASE` → nearest project `.cage/` → global `~/.cage`, ADR-LAWS Law 2) —
    for every read/emit/capture command (`report`, `import`, `export`, `watch`, …). Capture
    is global by default: a no-project user reads/writes the global ledger rather than
    scattering a footprint into the cwd."""
    return paths.resolve_root()


def quiet(args) -> bool:
    """Whether capture confirmations are suppressed — the per-invocation ``--quiet``
    flag or ``CAGE_QUIET`` env (1/true/yes/on). Visibility, never a gate: pricing/reads
    are untouched, only the ``· captured …`` / ``✔ cage: … captured`` lines are silenced."""
    import os
    if getattr(args, "quiet", False):
        return True
    return (os.environ.get("CAGE_QUIET") or "").strip().lower() in ("1", "true", "yes", "on")


def captured_read_root(args) -> Path:
    """The active-ledger root for a **read**, after running capture-on-read (the lazy
    pre-read sweep) and surfacing its one-line confirmation (capture-architecture Phase 1).
    Every read handler uses this in place of `ledger_root()`.

    The confirmation goes to **stderr** — never stdout — so it can never corrupt a
    ``--json``/``--csv`` stream or a piped table (CSV never gates), while still landing in
    the terminal (and the agent's tool result) as visible proof capture ran. Suppressed by
    ``--quiet``/``CAGE_QUIET``. `ensure_captured` is throttled, gated, and fail-open, and
    ``--why-ledger`` (when set) prints the ledger-resolution decision on demand."""
    import sys

    from cage import importcmd, paths
    r = ledger_root()
    if getattr(args, "why_ledger", False) and not quiet(args):
        print(f"· ledger: {paths.active_ledger_source()} → "
              f"{paths.Footprint(r).base} (route-key {paths.routing_key(r)})",
              file=sys.stderr)
    summary = importcmd.ensure_captured(r, args)
    line = importcmd.capture_summary_line(summary)
    if line and not quiet(args):
        print(line, file=sys.stderr)
    return r


def _resolve(v):
    """A renderer passed as a string, or as a zero-arg callable so an expensive render
    is only paid for when it is actually emitted (a view's footer can do I/O)."""
    return v() if callable(v) else v


def emit(args, payload: dict, text, *, csv=None, root=None) -> int:
    """The ONE emit chokepoint for a read view: export artifacts if asked, then print
    exactly one stream — CSV, JSON, or text.

    ``--export`` is **additive and never touches stdout**: the view prints byte-for-byte
    what it would have printed without the flag, and the write confirmation goes to
    stderr (`viewexport.confirm`). That is what lets the golden and floor suites keep
    asserting a byte-identical default surface while every view is exportable.

    ``--stamp`` is the opposite direction — the *opt-in* half of the same block: it puts
    the run stamp onto stdout, in whichever format is being emitted. Mandatory in an
    artifact, optional on a terminal (`runstamp`'s docstring says why).

    ``csv`` is the view's CSV renderer (string or callable) or ``None`` for a view that
    has none; ``root`` is the already-resolved active-ledger root, so no second
    resolution ladder appears here."""
    from cage import runstamp
    dest = csv_dest(args)            # validates output-format exclusivity first
    stamped = getattr(args, "stamp", False)
    view = getattr(args, "view", "") or ""
    fields = (runstamp.block(view, root=root, args=args)
              if (stamped or getattr(args, "export", None) is not None) else {})

    if (export := getattr(args, "export", None)) is not None:
        from cage import viewexport
        written = viewexport.export(
            export, view=view, root=root if root is not None else ledger_root(),
            text=_resolve(text), csv_text=csv, payload=payload, args=args,
            stamp=fields.get("generated_at"))
        viewexport.confirm(written, quiet=quiet(args))

    if dest is not None:
        from cage import csvout
        body = _resolve(csv)
        return csvout.write(runstamp.prefix_csv(body, fields) if stamped else body, dest)
    if getattr(args, "json", False):
        out = runstamp.wrap_json(payload, fields) if stamped else payload
        print(_json.dumps(out, ensure_ascii=False, indent=2))
    else:
        body = _resolve(text)
        print(runstamp.prefix_text(body, fields) if stamped else body)
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
