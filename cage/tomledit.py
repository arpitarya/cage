"""Comment-preserving TOML text surgery on the *project* `cage.toml` — the only
module that writes policy text.

**Formerly `pricestoml.py`.** Its price-specific setters (`set_price`, `set_credit`,
`set_alias`, `set_tool_route`, the `prices.toml` write target and the price `[meta]`
counters) went with the money subsystem (USAGE-ONLY, ADR 0011). The *generic writer*
underneath them did not: `cage policy sync` and `cage setup --python-launcher` still
need comment-preserving, atomic, locked table edits, and deleting the module wholesale
would have taken those with it. Renamed to say what it actually is.

The bundled policy is read-only at runtime — every mutation lands in the project file.

There is no comment-preserving TOML serializer in the stdlib, so cage never rewrites
the whole file. Two write modes, both text surgery on the original:

- **in-place** — the target table already exists outside the managed block: only its
  `key = value` lines are rewritten (surrounding comments survive) and the header gains
  a ``# cage:custom`` mark so a later sync knows the row is user-owned.
- **managed block** — the table doesn't exist yet: it is (re)generated inside one
  clearly marked block appended at the end of the file, deterministically (sorted
  tables, sorted keys), so two inserts in either order produce identical bytes.

TOML forbids declaring the same table twice, and a duplicate header would make the whole
project policy unparseable — capture would silently fall back to the bundled table. So
every mutation (a) refuses when a table exists both inside and outside the block, and
(b) re-parses the full candidate text *before* atomically replacing the file. These are
CLI commands, not capture paths — failures raise
:class:`~cage.errors.CageError` at the boundary, never fail-open silence.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import lockutil, paths
from cage.errors import CageError

BLOCK_START = "# --- cage:managed block — written by cage; edits inside are regenerated ---"
BLOCK_END = "# --- cage:managed end ---"
CUSTOM_MARK = "# cage:custom"

_BARE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_HEADER = re.compile(r"^\s*\[([^\[\]]*)\]\s*(#.*)?$")


def _fmt_seg(seg: str) -> str:
    """One dotted-key segment, bare when TOML allows it, quoted otherwise
    (model ids carry dots/slashes; the empty provider is ``""``)."""
    if seg and _BARE_KEY.fullmatch(seg):
        return seg
    return '"' + seg.replace("\\", "\\\\").replace('"', '\\"') + '"'


def table_header(*path: str) -> str:
    """``table_header("tools", "graphify")`` → ``[tools.graphify]``; a segment needing
    quotes gets them (``table_header("sources", "my tool")`` → ``[sources."my tool"]``)."""
    return "[" + ".".join(_fmt_seg(p) for p in path) + "]"


def _split_key_path(raw: str) -> list[str] | None:
    """Parse a header's dotted key into segments, honoring quotes; None if odd."""
    segs, buf, i, n = [], "", 0, len(raw)
    while i < n:
        ch = raw[i]
        if ch in "\"'":
            quote = ch
            i += 1
            while i < n and raw[i] != quote:
                if quote == '"' and raw[i] == "\\" and i + 1 < n:
                    esc = raw[i + 1]
                    buf += {"\\": "\\", '"': '"'}.get(esc, "\\" + esc)
                    i += 2
                    continue
                buf += raw[i]
                i += 1
            if i >= n:
                return None
            i += 1
        elif ch == ".":
            segs.append(buf.strip() if buf.strip() or not segs else buf)
            buf = ""
            i += 1
        else:
            buf += ch
            i += 1
    segs.append(buf.strip())
    return [s.strip() if not s.startswith(('"', "'")) else s for s in segs]


def _header_path(line: str) -> list[str] | None:
    m = _HEADER.match(line)
    if not m:
        return None
    return _split_key_path(m.group(1))


def find_table_span(lines: list[str], path: tuple[str, ...]) -> tuple[int, int] | None:
    """(header_idx, end_exclusive) of the table declaring exactly ``path``;
    the span runs to the next header or EOF. None when absent."""
    want = list(path)
    start = None
    for i, line in enumerate(lines):
        hp = _header_path(line)
        if hp is None:
            continue
        if start is not None:
            return (start, i)
        if hp == want:
            start = i
    if start is not None:
        return (start, len(lines))
    return None


def _fmt_value(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(float(v)) if isinstance(v, float) else str(v)
    if isinstance(v, list):
        return "[" + ", ".join(_fmt_value(x) for x in v) + "]"
    return '"' + str(v).replace("\\", "\\\\").replace('"', '\\"') + '"'


def split_block(text: str) -> tuple[str, str, str]:
    """(before, block_body, after). No block → ``(text, "", "")``."""
    lines = text.splitlines(keepends=True)
    s = e = None
    for i, line in enumerate(lines):
        if line.rstrip("\n") == BLOCK_START and s is None:
            s = i
        elif line.rstrip("\n") == BLOCK_END and s is not None:
            e = i
            break
    if s is None or e is None:
        return text, "", ""
    return "".join(lines[:s]), "".join(lines[s + 1:e]), "".join(lines[e + 1:])


def parse(path: Path) -> tuple[str, dict]:
    """(raw text, parsed dict) of the project policy; empty file when absent."""
    if not path.exists():
        return "", {}
    text = path.read_text(encoding="utf-8")
    if tomllib is None:  # pragma: no cover — Python <3.11
        raise CageError("this Python lacks tomllib — cannot edit policy.toml")
    try:
        return text, tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise CageError(f"cannot edit {path} — it does not parse as TOML ({e})") from e


def render_block(tables: dict[tuple[str, ...], dict]) -> str:
    """The managed block body — deterministic: paths sorted, keys in a fixed
    order (input/output/cache_read/to first, the rest alphabetical)."""
    order = {"input": 0, "output": 1, "cache_read": 2, "to": 0}
    out = []
    for path in sorted(tables):
        out.append(table_header(*path) + "\n")
        vals = tables[path]
        for k in sorted(vals, key=lambda k: (order.get(k, 9), k)):
            out.append(f"{k} = {_fmt_value(vals[k])}\n")
        out.append("\n")
    return "".join(out)


def _block_tables(body: str) -> dict[tuple[str, ...], dict]:
    """The managed block parsed back to {path: values} (leaf tables only)."""
    if not body.strip():
        return {}
    try:
        data = tomllib.loads(body)
    except (tomllib.TOMLDecodeError, ValueError) as e:
        raise CageError(f"the cage-managed block in policy.toml is corrupt ({e}) — "
                        f"fix or delete the block between the markers") from e
    tables: dict[tuple[str, ...], dict] = {}

    def walk(prefix: tuple[str, ...], node: dict):
        leaves = {k: v for k, v in node.items() if not isinstance(v, dict)}
        subs = {k: v for k, v in node.items() if isinstance(v, dict)}
        if leaves:
            tables[prefix] = leaves
        for k, v in subs.items():
            walk(prefix + (k,), v)

    walk((), data)
    return tables


def _atomic_write(path: Path, text: str) -> None:
    """Write-temp → re-parse → os.replace: a mutation can never leave an
    unparseable policy.toml behind (capture would silently fall back to bundled)."""
    try:
        tomllib.loads(text)
    except (tomllib.TOMLDecodeError, ValueError) as e:  # pragma: no cover — guarded upstream
        raise CageError(f"refusing to write policy.toml — result would not parse ({e})") from e
    tmp = path.with_name(path.name + ".cage-write")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _inplace_table_edit(text: str, path: tuple[str, ...], values: dict,
                        mark_custom: bool = True) -> str:
    """Rewrite ``key = value`` lines inside an existing table span; preserve
    every other line; mark the header ``# cage:custom`` (a `policy sync`
    default-update passes ``mark_custom=False`` — a synced default must not
    start reading as user-owned).

    A brand-new key (not already present) is inserted right after the table's
    **last recognized key line**, never at the span's far end — ``find_table_span``
    runs to the next header, so a table like ``[meta]`` whose only content is
    followed by a long prose block introducing the *next* section would otherwise
    land the new key deep inside that unrelated comment block (still valid TOML —
    the table stays open until the next header — but confusing to read)."""
    lines = text.splitlines(keepends=True)
    span = find_table_span(lines, path)
    assert span is not None  # caller checked
    start, end = span
    if mark_custom and CUSTOM_MARK not in lines[start]:
        lines[start] = lines[start].rstrip("\n") + f"   {CUSTOM_MARK}\n"
    pending = dict(values)
    last_key_line = start
    for i in range(start + 1, end):
        m = re.match(r"^(\s*)([A-Za-z0-9_-]+|\"[^\"]+\")\s*=", lines[i])
        if not m:
            continue
        last_key_line = i
        key = m.group(2).strip('"')
        if key in pending:
            lines[i] = f"{m.group(1)}{key} = {_fmt_value(pending.pop(key))}\n"
    if pending:
        insert = last_key_line + 1
        add = [f"{k} = {_fmt_value(v)}\n" for k, v in
               sorted(pending.items(), key=lambda kv: kv[0])]
        lines[insert:insert] = add
    return "".join(lines)


def _require_footprint(root: Path) -> paths.Footprint:
    foot = paths.Footprint(root)
    if not foot.base.exists():
        raise CageError(f"no cage footprint at {foot.base} — run `cage setup` first "
                        f"(or point --ledger/CAGE_BASE at one)")
    return foot


def _project_policy(root: Path) -> Path:
    """The project *policy* file (cage.toml/legacy policy.toml) — the write target for
    routing decisions ([tools] order, [wiring], [meta])."""
    return _require_footprint(root).policy


def _write_table(root: Path, path: tuple[str, ...], values: dict,
                 mark_custom: bool = True, *, target: Path | None = None,
                 created_head: str | None = None) -> dict:
    """Insert-or-update one leaf table in ``target`` (defaults to the project policy
    file); returns
    ``{"mode": "in-place"|"block"|"created"|"unchanged", "before": dict|None, "after": dict}``."""
    pol_path = target if target is not None else _project_policy(root)
    result = {"path": pol_path}
    with lockutil.locked(paths.Footprint(root).state / "policy.lock"):
        # parse() already refused a duplicate table declaration (TOML law) — past
        # this point the path exists outside the block, inside it, or nowhere.
        text, _ = parse(pol_path)
        before_txt, body, after_txt = split_block(text)
        outside_lines = (before_txt + after_txt).splitlines(keepends=True)
        outside = find_table_span(outside_lines, path) is not None
        block = _block_tables(body)
        if outside:
            lines = text.splitlines(keepends=True)
            span = find_table_span(lines, path)
            if span is None:  # only ever true if the header sits inside the block region
                raise CageError(f"{table_header(*path)} found outside the managed block "
                                f"but not addressable — check {pol_path}")
            current = _table_values(lines, span)
            if current == values:
                return {**result, "mode": "unchanged", "before": current, "after": values}
            new_text = _inplace_table_edit(text, path, values, mark_custom=mark_custom)
            _atomic_write(pol_path, new_text)
            return {**result, "mode": "in-place", "before": current, "after": values}
        before_vals = block.get(path)
        if before_vals == values:
            return {**result, "mode": "unchanged", "before": before_vals, "after": values}
        block[path] = dict(values)
        new_text = _assemble(before_txt, block, after_txt, created=not text,
                             created_head=created_head)
        _atomic_write(pol_path, new_text)
        return {**result, "mode": ("created" if not text else "block"),
                "before": before_vals, "after": values}


def _table_values(lines: list[str], span: tuple[int, int]) -> dict:
    """The leaf values of one table span, via tomllib on just those lines."""
    start, end = span
    header = re.sub(r"#.*$", "", lines[start]).strip()
    chunk = header + "\n" + "".join(
        line for line in lines[start + 1:end] if not _HEADER.match(line))
    try:
        data = tomllib.loads(chunk)
    except (tomllib.TOMLDecodeError, ValueError):
        return {}
    while isinstance(data, dict) and len(data) == 1 and isinstance(next(iter(data.values())), dict):
        data = next(iter(data.values()))
    return {k: v for k, v in data.items() if not isinstance(v, dict)}


def _assemble(before: str, block: dict[tuple[str, ...], dict], after: str,
              created: bool = False, created_head: str | None = None) -> str:
    head = before
    if created:
        head = created_head or ("# Cage project policy — rows here shadow the bundled "
                                "defaults (policy.load two-level merge).\n\n")
    if head and not head.endswith("\n\n"):
        head = head.rstrip("\n") + "\n\n"
    body = render_block(block).rstrip("\n")
    return f"{head}{BLOCK_START}\n{body}\n{BLOCK_END}\n{after}"


def remove_table(root: Path, path: tuple[str, ...]) -> dict:
    """Delete one leaf table from the *managed block only*; returns
    ``{"mode": "removed"|"absent", "before": dict|None}``.

    A table living outside the block is user-owned text — cage edits values
    in place on a write (`_write_table`) but never deletes a user's table:
    that raises, naming the file, so the person deletes their own lines.
    Absent everywhere ⇒ ``absent`` (idempotent re-runs are clean no-ops)."""
    pol_path = _project_policy(root)
    result = {"path": pol_path}
    with lockutil.locked(paths.Footprint(root).state / "policy.lock"):
        text, _ = parse(pol_path)
        before_txt, body, after_txt = split_block(text)
        outside_lines = (before_txt + after_txt).splitlines(keepends=True)
        if find_table_span(outside_lines, path) is not None:
            raise CageError(f"{table_header(*path)} was hand-added outside the "
                            f"cage-managed block in {pol_path} — cage never deletes "
                            f"your own text; remove those lines by hand")
        block = _block_tables(body)
        before_vals = block.pop(path, None)
        if before_vals is None:
            return {**result, "mode": "absent", "before": None}
        new_text = _assemble(before_txt, block, after_txt, created=not text)
        _atomic_write(pol_path, new_text)
        return {**result, "mode": "removed", "before": before_vals}


def update_meta(root: Path, meta: dict) -> dict:
    """Stamp ``[meta]`` in-place in the project policy file. The per-key split across a
    second prices file went with the money subsystem (USAGE-ONLY, ADR 0011); there is
    one target again."""
    return _write_table(root, ("meta",), dict(meta))


def set_wiring(root: Path, values: dict) -> dict:
    """Persist ``[wiring]`` keys (e.g. ``python_launcher = true``) in the project
    policy — same locked, atomic text surgery as the price writes."""
    return _write_table(root, ("wiring",), dict(values))


def set_table(root: Path, path: tuple[str, ...], values: dict, *,
              mark_custom: bool = True) -> dict:
    """Generic insert-or-update of one leaf table. `cage policy sync`'s update
    path passes ``mark_custom=False`` — a refreshed bundled default must stay
    sync-updatable, not start reading as user-owned."""
    return _write_table(root, tuple(path), dict(values), mark_custom=mark_custom)


def add_table(root: Path, path: tuple[str, ...], values: dict,
              comment: str | None = None) -> dict:
    """Append one leaf table as *plain text outside the managed block* (before
    the block when one exists, EOF otherwise), with an optional provenance
    comment line above the header — `cage policy sync`'s add path. Unlike the
    managed block, a table written here is not user-owned: no ``# cage:custom``
    mark, so a later bundle change to it still syncs. Idempotent."""
    pol_path = _project_policy(root)
    result = {"path": pol_path}
    with lockutil.locked(paths.Footprint(root).state / "policy.lock"):
        text, _ = parse(pol_path)
        before_txt, body, after_txt = split_block(text)
        outside_lines = (before_txt + after_txt).splitlines(keepends=True)
        span = find_table_span(outside_lines, path)
        if span is not None:  # already present — fall back to a no-mark value edit
            current = _table_values(outside_lines, span)
            if current == values:
                return {**result, "mode": "unchanged", "before": current, "after": values}
            new_text = _inplace_table_edit(text, path, values, mark_custom=False)
            _atomic_write(pol_path, new_text)
            return {**result, "mode": "in-place", "before": current, "after": values}
        if path in _block_tables(body):
            raise CageError(f"{table_header(*path)} lives in the cage-managed block of "
                            f"{pol_path} — that table is user-owned; refusing to add "
                            f"a duplicate outside it")
        chunk = ([comment.rstrip("\n") + "\n"] if comment else [])
        chunk.append(table_header(*path) + "\n")
        chunk += [f"{k} = {_fmt_value(values[k])}\n" for k in sorted(values)]
        lines = text.splitlines(keepends=True)
        idx = next((i for i, ln in enumerate(lines)
                    if ln.rstrip("\n") == BLOCK_START), len(lines))
        if idx == len(lines) and lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        pre = "" if idx == 0 or lines[idx - 1].strip() == "" else "\n"
        post = "\n" if idx < len(lines) else ""
        lines[idx:idx] = [pre + "".join(chunk) + post]
        _atomic_write(pol_path, "".join(lines))
        return {**result, "mode": "added", "before": None, "after": values}


def custom_headers(text: str) -> set[tuple[str, ...]]:
    """Table paths the user owns: marked ``# cage:custom`` or inside the managed block
    (a table cage wrote there on the user's instruction is customized by definition).

    Lived in `pricescmd` until USAGE-ONLY (ADR 0011) deleted that module; it is generic
    text surgery, not pricing, and `cage policy sync` still needs it to know which
    tables it must never clobber."""
    owned: set[tuple[str, ...]] = set()
    before, body, after = split_block(text)
    for line in (before + after).splitlines():
        if CUSTOM_MARK in line:
            hp = _header_path(line.split(CUSTOM_MARK)[0].rstrip())
            if hp:
                owned.add(tuple(hp))
    owned.update(_block_tables(body))
    return owned
