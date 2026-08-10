"""The run stamp + the export metadata block — **the one place a wall clock reaches a
derived-view surface** (`cage query view-export` explains it).

Cage's determinism law says *no clocks in derived views: same ledger + same policy ⇒
same tables*. A generated-at stamp is a clock, so it is admitted here on three
conditions that keep the law intact rather than bending it:

1. **It is never a number.** The stamp is metadata *about the run*, never an input to
   a cell, a total, a price or a method tag. Delete every stamp and no derived figure
   moves — the same standing every `state/` file has.
2. **stdout stays clock-free by default.** `cage report` prints byte-identically with
   and without `--export`; the stamp reaches stdout only when the user asks for it
   (`--stamp`). That is what keeps `tests/test_output_spec.py`'s goldens and
   `tests/test_floor.py`'s byte-identical assertions meaningful — they pin the default
   surface, and the default surface has no clock in it.
3. **It is mandatory in an artifact.** A file outlives its terminal: an exported table
   with no generated-at is a number with no as-of, which is the one thing a cost
   artifact must never be. So every artifact `viewexport` writes carries this block,
   and there is no flag to suppress it.

**One phrasing, three renderings.** The field list is built once (:func:`block`) and
rendered as `# cage: k=v` lines for text and CSV, and as a `cage` object for JSON.
Never re-word it per format — the `netsaved.GROSS_NOTE` discipline, applied to
metadata.

**`CAGE_RUN_STAMP` pins the clock** to an exact string. That exists for tests and for
anyone who needs a byte-reproducible artifact; it is read here and nowhere else, so
there is exactly one clock call to pin.

Deliberately NOT covered: `--csv` / `--json` on stdout keep their existing byte
contract (the pinned column contract in `csvout.py`, the `cage.v1` envelope in
`render.envelope`). A `--csv PATH` is a *stream redirected to a file*; `--export` is
an *artifact*. Only the artifact grows the block — a preamble silently appearing in
every `--csv` would break the column contract every BI consumer already reads.
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from pathlib import Path

# The args that shape the DATA — the row set, the window, the join. A filter belongs in
# the block because it changes what the numbers mean; a presentation switch (`--usd`,
# `--all`, `--csv`, `--json`, `--export`, `--quiet`) does not and stays out. Closed
# list, in render order, so two artifacts of the same view read the same way.
FILTER_ARGS = ("task", "sha", "call_id", "tool", "session", "by", "since", "agent",
               "scope", "project", "team")

_STAMP_ENV = "CAGE_RUN_STAMP"
_DIGITS = re.compile(r"(\d{4})-?(\d{2})-?(\d{2})[T ](\d{2}):?(\d{2}):?(\d{2})")


def now() -> str:
    """The run stamp: local-time ISO-8601 with offset, seconds precision
    (`2026-08-10T08:42:40+05:30`). Local, not UTC, because the reader of an artifact is
    the person who ran it — and the offset is carried, so it is never ambiguous.

    ``CAGE_RUN_STAMP`` overrides it verbatim (the one pin point). THE only clock call on
    any read surface; every other module asks this one."""
    pinned = os.environ.get(_STAMP_ENV)
    if pinned:
        return pinned.strip()
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def slug(stamp: str) -> str:
    """A filename-safe `YYYYMMDD-HHMMSS` from a run stamp, so artifacts sort
    chronologically in a directory listing. A stamp cage cannot parse (a hand-pinned
    ``CAGE_RUN_STAMP``) degrades to a conservative character fold rather than raising —
    a stamp is metadata, and metadata must never be able to fail a read."""
    m = _DIGITS.search(stamp or "")
    if m:
        return f"{m[1]}{m[2]}{m[3]}-{m[4]}{m[5]}{m[6]}"
    fold = re.sub(r"[^0-9A-Za-z]+", "-", stamp or "").strip("-")
    return fold or "run"


def view_slug(view: str) -> str:
    """`insights chats` → `insights-chats` — the artifact's basename. Whitespace only;
    a view name is a parser verb path, never user input, so nothing else can appear."""
    return re.sub(r"\s+", "-", (view or "view").strip()) or "view"


def filters(args) -> str:
    """The active data-shaping filters as `k=v` pairs, or `""` when a view is
    unfiltered. Booleans render as the bare flag name (`team`), because `team=true` is
    noise; a falsey value is absent, not `k=`."""
    out = []
    for name in FILTER_ARGS:
        v = getattr(args, name, None)
        if v is None or v is False or v == "":
            continue
        if v is True:
            out.append(name)
        else:
            out.append(f"{name}={v}")
    return " ".join(out)


def block(view: str, root: Path | None = None, args=None,
          stamp: str | None = None) -> dict[str, str]:
    """The metadata block, built once and rendered per format. Insertion order IS the
    render order — `view` first (what am I looking at), `generated_at` second (as of
    when), then provenance. Empty values are dropped, never rendered as `k=`."""
    from cage import __version__
    fields = {
        "view": view or "",
        "generated_at": stamp or now(),
        "cage_version": __version__,
    }
    if root is not None:
        from cage import paths
        fields["ledger"] = str(paths.Footprint(root).base)
    if args is not None and (f := filters(args)):
        fields["filters"] = f
    return {k: v for k, v in fields.items() if v}


def render_comment(fields: dict[str, str]) -> str:
    """`# cage: k=v` lines — the text and CSV rendering. `#` is a comment to every
    spreadsheet importer worth the name and to a human reading a `.txt`, and the `cage:`
    prefix means a grep for the stamp finds it in either format."""
    return "".join(f"# cage: {k}={v}\n" for k, v in fields.items())


def prefix_text(text: str, fields: dict[str, str]) -> str:
    """A rendered text view with the block above it, one blank line between."""
    return f"{render_comment(fields)}\n{text}"


def prefix_csv(csv_text: str, fields: dict[str, str]) -> str:
    """A rendered CSV with the block as a preamble. **No blank line** — a stray empty
    line inside a CSV is a row to some parsers, while a leading `#` comment run is the
    conventional, widely-skipped preamble."""
    return f"{render_comment(fields)}{csv_text}"


def wrap_json(payload, fields: dict[str, str]) -> dict:
    """The JSON artifact: the block under `cage`, the view's own payload under `data`.

    Deliberately NOT `render.envelope` — that is the pinned `cage.v1` *stdout* contract
    for `--json` and grows a `generatedAt` of its own. An artifact is a different
    surface with a different reader, and folding the two would make a change to either
    a change to both."""
    return {"cage": dict(fields), "data": payload}
