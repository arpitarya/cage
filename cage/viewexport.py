"""`--export` — write a rendered view to disk as a dated artifact (`cage query
view-export`).

Every report and insight is exportable, uniformly, through this one module. Two
destination shapes, one rule each:

| `--export`         | writes                                                        |
|--------------------|---------------------------------------------------------------|
| bare               | `<ledger>/.cage/output/<view>-<stamp>/` — every format the view has |
| a path with a known suffix | exactly that file, in exactly that format             |
| any other path     | `<path>/<view>-<stamp>/` — every format the view has           |

**A directory destination always gets a per-run subfolder.** Two runs of the same view
must never silently clobber each other — an artifact whose whole job is to be the
as-of record is worthless if the previous as-of is gone. Naming the file explicitly is
the one way to overwrite, and that is a thing the user typed.

**Every artifact carries the metadata block** (`runstamp.block`) — the generated-at is
mandatory here and has no suppression flag; see `runstamp`'s docstring for why the
determinism law survives it. **stdout is untouched**: the view still prints exactly
what it would have printed without the flag, and the write confirmation goes to
stderr, so `--export` can never corrupt a piped stream.

**Formats are what the view actually has**, never a promised set: text always, JSON
always (the same payload `--json` prints), CSV only where that view owns a
`render_csv`. Asking for a format a view cannot produce is a typed refusal naming the
gap — never an empty file, which would read as *this view has no rows*.

`--html` stays `cage insights matrix`'s own flag: it renders a standalone dashboard
page (`serve.write_html`), a different artifact with a different purpose, and folding
it in here would make one flag mean two things.

Deliberately NOT in this module: any pruning of `.cage/output/`. `cleanup.py` is a
closed allowlist and this directory is not on it, so cage will never delete an
artifact it wrote — the same standing `ledger/` has. Growth is the user's to manage
(`docs/OPEN-WORK.md` carries the open question of whether it ever earns a class).
"""
from __future__ import annotations

import sys
from pathlib import Path

from cage import runstamp
from cage.errors import CageError

# suffix → format id. `.md` and `.txt` are the same renderer: the text view is already
# plain enough to paste into a doc, and forcing a reader to remember which one cage
# blesses is friction for no gain.
SUFFIXES = {".txt": "text", ".md": "text", ".csv": "csv", ".json": "json"}

# Render order, and the order artifacts are listed in the confirmation.
ORDER = ("text", "csv", "json")

_EXT = {"text": "txt", "csv": "csv", "json": "json"}


def _fail(msg: str) -> None:
    raise CageError(msg)


def available(*, text: str | None, csv_text=None, payload=None) -> tuple[str, ...]:
    """The formats this view can actually produce, in render order."""
    have = []
    if text is not None:
        have.append("text")
    if csv_text is not None:
        have.append("csv")
    if payload is not None:
        have.append("json")
    return tuple(f for f in ORDER if f in have)


def default_dir(root: Path) -> Path:
    """The bare-`--export` destination: the **active ledger's** `.cage/output/`.

    The artifact lives beside the ledger it describes — one root, the same one every
    read on this invocation already resolved (`cliutil.captured_read_root`), so no
    second precedence ladder is introduced. A no-project user exporting the global
    ledger therefore gets `~/.cage/output/`, which is the honest home for a view of
    `~/.cage`; `--why-ledger` names the root, and `--export PATH` overrides it."""
    from cage import paths
    return paths.Footprint(root).output


def _render(fmt: str, fields: dict, *, text, csv_text, payload) -> str:
    if fmt == "text":
        return runstamp.prefix_text(text, fields)
    if fmt == "csv":
        return runstamp.prefix_csv(csv_text() if callable(csv_text) else csv_text,
                                   fields)
    import json as _json
    return _json.dumps(runstamp.wrap_json(payload, fields), ensure_ascii=False,
                       indent=2) + "\n"


def _write(path: Path, body: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # newline="" so the LF the renderers emit survives Windows untranslated — the
        # same guarantee `csvout.write` makes, applied to every format.
        with path.open("w", encoding="utf-8", newline="") as fh:
            fh.write(body)
    except OSError as e:
        _fail(f"cannot write {path}: {e}")


def export(dest: str, *, view: str, root: Path, text: str, csv_text=None,
           payload=None, args=None, stamp: str | None = None) -> list[Path]:
    """Write ``view``'s artifacts and return the paths, newest-run folder first.

    ``csv_text`` may be a callable so a view's CSV is rendered only when it is actually
    written — the same-numbers-by-construction rule still holds (it renders from the
    very structure the text view consumed), it just isn't paid for on a text-only
    export."""
    stamp = stamp or runstamp.now()
    fields = runstamp.block(view, root=root, args=args, stamp=stamp)
    formats = available(text=text, csv_text=csv_text, payload=payload)
    base = Path(dest).expanduser() if dest else default_dir(root)
    name = runstamp.view_slug(view)

    suffix = base.suffix.lower()
    if suffix:
        if suffix not in SUFFIXES:
            _fail(f"--export: unknown format '{suffix}' — cage writes "
                  f"{', '.join(sorted(SUFFIXES))} (a path with no suffix is a "
                  f"directory and gets every format)")
        fmt = SUFFIXES[suffix]
        if fmt not in formats:
            _fail(f"--export: `{view}` has no {fmt} renderer — this view exports "
                  f"{', '.join(_EXT[f] for f in formats)}. An empty file would read "
                  f"as 'no rows', so cage refuses instead")
        _write(base, _render(fmt, fields, text=text, csv_text=csv_text,
                             payload=payload))
        return [base]

    run_dir = base / f"{name}-{runstamp.slug(stamp)}"
    written = []
    for fmt in formats:
        p = run_dir / f"{name}.{_EXT[fmt]}"
        _write(p, _render(fmt, fields, text=text, csv_text=csv_text, payload=payload))
        written.append(p)
    return written


def confirm(written: list[Path], quiet: bool = False) -> None:
    """The write confirmation — **stderr**, so stdout stays exactly the stream it was
    without the flag (a `--export` alongside `--csv -` must still pipe cleanly).
    Silenced by `--quiet`/`CAGE_QUIET`, like every other cage confirmation."""
    if quiet or not written:
        return
    if len(written) == 1:
        print(f"✔ wrote {written[0]}", file=sys.stderr)
        return
    print(f"✔ wrote {len(written)} artifacts → {written[0].parent}", file=sys.stderr)
    for p in written:
        print(f"  · {p.name}", file=sys.stderr)
