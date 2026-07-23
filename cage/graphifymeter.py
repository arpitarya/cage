"""`cage data graphify -- graphify <args>` — meter a third-party tool without touching it.

graphify is read-only, so cage measures it the way it meters any tool it doesn't own
(`cage data meter`, `import-codex`): run it as a subprocess, pass stdout/stderr/exit
through **unchanged**, and on the side parse the captured answer to file one
token-saving receipt. A metering error never alters graphify's result (fail-open).

Counterfactual (handoff §4): `actual = toks(answer)`; `raw_alternative` = the whole
*touched* source files the answer cites (`src=`/`Source:` paths), deduped, present on
disk only — never the repo. If no path parses/resolves, emit **nothing** (a parse
miss is "unmeasurable," not zero saving). `method="modeled"`, confidence from
`constants.GRAPHIFY_RECEIPT_CONFIDENCE`.

**Native-shim dedupe (v0.22.1 finding #35):** graphify ≥ 0.5.0 carries its own cage
receipt shim, so a wrapped run would file the same saving twice (once natively, once
here) — savings must never inflate. The wrapper snapshots the ledger's graphify
receipt ids before the child runs and, if the child filed one itself, defers to it
and emits nothing. The child also runs with ``CAGE_GRAPHIFY_METERED=1`` in its
environment — a forward handshake: a graphify version that respects it skips its
native receipt, the detection then sees no new row, and the wrapper's task-bound
receipt wins. Either side deduping is enough; both together converge on one receipt.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from cage import debuglog, ledger
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


def _meter(root: Path, answer: str, argv: list[str], task: str) -> int:
    """File one graphify receipt from the captured answer. Fully fail-open. Returns the
    saved token count when a receipt was filed (for the confirmation line), else 0."""
    try:
        op = _op_of(argv)
        if not op:
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="non-measured-op")
            return 0
        files = _cited_files(answer, op)
        raw = _raw_alternative(files)
        if raw <= 0:                      # nothing parsed/resolved → unmeasurable
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="no-source-file-parsed", op=op)
            return 0
        actual = toks(answer)
        if actual >= raw:                 # no saving to claim — stay honest
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="no-saving-to-claim", op=op)
            return 0
        from cage import record_receipt
        rid = record_receipt(tool="graphify", unit="tokens", raw_alternative=raw,
                             actual=actual, method="modeled",
                             confidence=GRAPHIFY_RECEIPT_CONFIDENCE,
                             task=task, root=root, meta={"op": op})
        debuglog.event(root, event="receipt", tool="graphify", produced=bool(rid),
                       skip_reason="" if rid else "ledger-write-failed", op=op)
        return int(raw - actual) if rid else 0
    except Exception as e:                # any metering error → graphify result intact
        debuglog.exception(root, "graphify.meter", e)
        return 0


def _quiet() -> bool:
    import os
    return (os.environ.get("CAGE_QUIET") or "").strip().lower() in ("1", "true", "yes", "on")


def _confirm(root: Path, saved_tokens: int) -> None:
    """One **stderr** line proving cage captured the graphify saving (§12.2) — counts
    only, never content. stderr, never stdout: graphify's stdout is parseable output a
    caller may pipe, and this line must never corrupt it. Suppressed by ``CAGE_QUIET``.
    Because graphify runs as a command in the agent's turn, the line lands in the tool
    result the human/agent sees — "graphify saving captured," exactly the ask. Fail-open
    (a confirmation must never break the passthrough)."""
    try:
        if _quiet() or saved_tokens <= 0:
            return
        from cage import paths
        where = paths.Footprint(root).base
        print(f"✔ cage: graphify saving captured — ~{saved_tokens:,} tokens "
              f"(→ {where})", file=sys.stderr)
    except Exception:  # noqa: BLE001 — the confirmation must never break graphify
        pass


def _graphify_receipt_ids(root: Path) -> set[str] | None:
    """Ids of the graphify receipts in the ledger, or ``None`` when the read fails.
    None (not an empty set) keeps the dedupe symmetric: a failed *before* snapshot
    must not make every pre-existing receipt look new post-run — the caller only
    trusts the diff when both reads succeeded, else it meters as pre-dedupe cage did."""
    try:
        return {r.get("id", "") for r in ledger.receipts(root) if r.get("tool") == "graphify"}
    except Exception:
        return None


def run(root: Path, argv: list[str], task: str = "") -> int:
    """Run `graphify <argv>` transparently; meter on the side. Returns its exit code."""
    cmd = list(argv)
    if cmd and cmd[0] == "--":            # tolerate `cage data graphify -- graphify …`
        cmd = cmd[1:]
    if not cmd:
        print("usage: cage data graphify -- graphify <query|path|explain> …", file=sys.stderr)
        return 2
    # Only a measured read verb can ever file a receipt — skip both snapshot reads
    # (each a full receipts-shard scan) for install/--help/unknown-verb runs.
    op = _op_of(cmd)
    before = _graphify_receipt_ids(root) if op else None
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              env={**os.environ, "CAGE_GRAPHIFY_METERED": "1"})
    except (OSError, ValueError) as exc:
        print(f"cage data graphify: could not run {cmd[0]!r}: {exc}", file=sys.stderr)
        return 127
    sys.stdout.write(proc.stdout)         # passthrough — byte-identical to bare graphify
    sys.stderr.write(proc.stderr)
    if proc.returncode == 0 and op:
        after = _graphify_receipt_ids(root) if before is not None else None
        if after is not None and (new_ids := after - before):
            # The child self-metered — surface the same confirmation off its own receipt
            # (counts only) so a natively-shimmed graphify is just as visible.
            saved = 0
            for r in ledger.receipts(root):
                if r.get("id") in new_ids:
                    saved += int(round(r.get("saved", 0.0)))
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="linked-receipt-skipped", op=op)
            _confirm(root, saved)
            return proc.returncode        # the child self-metered — one saving, one receipt
        _confirm(root, _meter(root, proc.stdout, cmd, task or Path.cwd().name))
    return proc.returncode
