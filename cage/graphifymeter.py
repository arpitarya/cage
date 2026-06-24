"""`cage graphify -- graphify <args>` — meter a third-party tool without touching it.

graphify is read-only, so cage measures it the way it meters any tool it doesn't own
(`cage meter`, `import-codex`): run it as a subprocess, pass stdout/stderr/exit
through **unchanged**, and on the side parse the captured answer to file one
token-saving receipt. A metering error never alters graphify's result (fail-open).

Counterfactual (handoff §4): `actual = toks(answer)`; `raw_alternative` = the whole
*touched* source files the answer cites (`src=`/`Source:` paths), deduped, present on
disk only — never the repo. If no path parses/resolves, emit **nothing** (a parse
miss is "unmeasurable," not zero saving). `method="modeled"`, confidence from
`constants.GRAPHIFY_RECEIPT_CONFIDENCE`.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from cage.constants import CHARS_PER_TOKEN, GRAPHIFY_RECEIPT_CONFIDENCE

# Expected graphify output formats (owned by graphify; pinned here so a format
# drift fails closed → "unmeasurable" → no receipt, never a fabricated saving):
#   query  : NODE <label> [src=<source_file> loc=<Lnn> community=<n>]
#   explain:   Source:    <source_file> L<nn>
#   path   : <label> --rel--> <label>          (cites no files → no receipt)
_SRC_QUERY = re.compile(r"\[src=(.*?) loc=")
_SRC_EXPLAIN = re.compile(r"^\s*Source:\s+(.+?)\s+L\d+\s*$", re.MULTILINE)


def toks(text: str) -> int:
    return max(0, round(len(text) / CHARS_PER_TOKEN))


def _op_of(argv: list[str]) -> str:
    """The graphify subcommand → receipt op; '' if it isn't a measured read verb."""
    for a in argv:
        if a in ("query", "path", "explain"):
            return a
    return ""


def _cited_files(answer: str, op: str) -> list[str]:
    if op == "explain":
        paths = _SRC_EXPLAIN.findall(answer)
    else:  # query (path cites none, so its findall is simply empty)
        paths = _SRC_QUERY.findall(answer)
    return [p.strip() for p in paths if p.strip()]


def _raw_alternative(files: list[str]) -> int:
    """Sum toks() over the deduped, whole, present-on-disk cited files (CWD- or
    project-relative). Files that don't resolve are skipped — bounded to touched."""
    seen: set[str] = set()
    total = 0
    roots = (Path.cwd(), Path.cwd() / "graphify-out" / "..")  # repo root fallbacks
    for f in files:
        if f in seen:
            continue
        seen.add(f)
        for cand in (Path(f), *(r / f for r in roots)):
            try:
                if cand.is_file():
                    total += toks(cand.read_text(encoding="utf-8", errors="ignore"))
                    break
            except OSError:
                continue
    return total


def _meter(root: Path, answer: str, argv: list[str], task: str) -> None:
    """File one graphify receipt from the captured answer. Fully fail-open."""
    try:
        op = _op_of(argv)
        if not op:
            return
        files = _cited_files(answer, op)
        raw = _raw_alternative(files)
        if raw <= 0:                      # nothing parsed/resolved → unmeasurable
            return
        actual = toks(answer)
        if actual >= raw:                 # no saving to claim — stay honest
            return
        from cage import record_receipt
        record_receipt(tool="graphify", unit="tokens", raw_alternative=raw,
                       actual=actual, method="modeled",
                       confidence=GRAPHIFY_RECEIPT_CONFIDENCE,
                       task=task, root=root, meta={"op": op})
    except Exception:                     # any metering error → graphify result intact
        return


def run(root: Path, argv: list[str], task: str = "") -> int:
    """Run `graphify <argv>` transparently; meter on the side. Returns its exit code."""
    cmd = list(argv)
    if cmd and cmd[0] == "--":            # tolerate `cage graphify -- graphify …`
        cmd = cmd[1:]
    if not cmd:
        print("usage: cage graphify -- graphify <query|path|explain> …", file=sys.stderr)
        return 2
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True)
    except (OSError, ValueError) as exc:
        print(f"cage graphify: could not run {cmd[0]!r}: {exc}", file=sys.stderr)
        return 127
    sys.stdout.write(proc.stdout)         # passthrough — byte-identical to bare graphify
    sys.stderr.write(proc.stderr)
    if proc.returncode == 0:
        _meter(root, proc.stdout, cmd, task or Path.cwd().name)
    return proc.returncode
