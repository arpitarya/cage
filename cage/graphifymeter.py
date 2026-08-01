"""`cage data graphify -- graphify <args>` — meter a third-party tool without touching it.

graphify is read-only, so cage measures it the way it meters any tool it doesn't own
(`cage data meter`, `cage import`): run it as a subprocess, pass stdout/stderr/exit
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

import hashlib
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


# ── deterministic receipt ids + cross-route dedupe (graphify-capture plan GC3, ADR 0005)
# The id folds in `session` so the SAME query in two sessions is two receipts (per-session
# attribution is a requirement, not a nicety). Cross-route convergence (shim + transcript
# capturing one run) is NOT solved by id-collision — it can't be, the shim honestly can't
# know the session — but by the content-key **deferral** that already dedupes the native
# shim: the transcript route computes the shim's session-empty id and defers if it's
# already filed. Ordering makes the deferral unidirectional and sufficient: the shim runs
# synchronously at query time, `cage import` always strictly later, so the shim always
# files first and the transcript always defers to it.


def content_signature(argv: list[str], answer: str) -> tuple[str, str, str]:
    """Route-independent ``(op, args_hash, answer_hash)`` for one graphify run. The
    binary spelling (``argv[0]``) is dropped, so `graphify query X`,
    `/venv/bin/graphify query X`, and `bin/graphify query X` all sign identically — the
    shim and the transcript-parsed command reach the same signature. ``answer_hash`` is
    over the stripped answer text (counts-never-content: a hash, never the words). A
    transcript that truncates a very long tool result would sign differently → the
    deferral can miss and double-count; that residual is the ADR 0005 veto metric."""
    tail = [str(a) for a in (argv[1:] if argv else [])]
    op = _op_of(tail)
    args_hash = hashlib.sha1("\x00".join(tail).encode("utf-8")).hexdigest()[:16]
    answer_hash = hashlib.sha1((answer or "").strip().encode("utf-8")).hexdigest()[:16]
    return op, args_hash, answer_hash


def receipt_id(session: str, op: str, args_hash: str, answer_hash: str) -> str:
    """The deterministic savings-row id: ``s_`` + sha1 of
    ``session | op | args_hash | answer_hash`` (plan §4 / GC3). Session-inclusive for
    per-session attribution; re-import of the same transcript reproduces it exactly, so
    `ledger.receipts`' `union_by_id` collapses re-imports with no growth in derived rows."""
    key = f"{session}|{op}|{args_hash}|{answer_hash}"
    return "s_" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:15]


def _cited_files(answer: str, op: str) -> list[str]:
    if op == "explain":
        paths = _SRC_EXPLAIN.findall(answer)
    else:  # query (path cites none, so its findall is simply empty)
        paths = _SRC_QUERY.findall(answer)
    return [p.strip() for p in paths if p.strip()]


def _raw_alternative(files: list[str], roots=None) -> int:
    """Sum toks() over the deduped, whole, present-on-disk cited files (resolved against
    ``roots``). Files that don't resolve are skipped — bounded to touched.

    ``roots`` defaults to CWD (the shim runs in the repo). The GC2 transcript route
    passes the transcript's own recorded ``cwd`` instead, so cited files resolve against
    the repo the query actually ran in, not wherever `cage import` happened to fire."""
    seen: set[str] = set()
    total = 0
    if roots is None:
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


def _meter(root: Path, answer: str, argv: list[str], task: str) -> tuple[int, str]:
    """File one graphify receipt from the captured answer. Fully fail-open. Returns
    ``(saved_tokens, outcome)`` — ``saved_tokens`` is the saving when a receipt was filed
    (for the confirmation line), else 0; ``outcome`` is the GC1 usage verdict
    (:data:`usagelog.OUTCOMES`) so `run` can breadcrumb every route with one honest word."""
    try:
        op = _op_of(argv)
        if not op:
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="non-measured-op")
            return 0, "non-measured"
        if not (answer or "").strip():    # empty result — nothing ran to save (handoff §8)
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="empty-answer", op=op)
            return 0, "empty"
        files = _cited_files(answer, op)
        raw = _raw_alternative(files)
        if raw <= 0:                      # nothing parsed/resolved → unmeasurable
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="no-source-file-parsed", op=op)
            return 0, "unmeasurable"
        actual = toks(answer)
        if actual >= raw:                 # no saving to claim — stay honest
            debuglog.event(root, event="receipt", tool="graphify", produced=False,
                           skip_reason="no-saving-to-claim", op=op)
            return 0, "unmeasurable"
        # Route into the dedicated per-source savings tree (`savings/graphify/`,
        # plan §3), not the shared receipts.jsonl. `source_files` is a COUNT only
        # (never the cited paths — PII guard). It stays receipt-compatible, so
        # attribution/roi/report read it through `ledger.receipts`'s union unchanged.
        from cage import manifest, savings
        gid = manifest.new_graphify_id()   # FK linking the savings row ↔ its manifest row
        # Deterministic id with an HONEST-EMPTY session (GC3 root-cause fix): the shim
        # genuinely cannot know the agent's session id, so it stamps "" rather than a cwd
        # basename masquerading as one. That empty-session id is exactly what the
        # transcript route recomputes to defer to this receipt (ADR 0005).
        op_s, ah, anh = content_signature(argv, answer)
        sid = receipt_id("", op_s or op, ah, anh)
        rid = savings.record(root, tool="graphify", unit="tokens", raw_alternative=raw,
                             actual=actual, method="modeled",
                             confidence=GRAPHIFY_RECEIPT_CONFIDENCE,
                             task=task, op=op, source_files=len(files), import_id=gid,
                             savings_id=sid)
        debuglog.event(root, event="receipt", tool="graphify", produced=bool(rid),
                       skip_reason="" if rid else "ledger-write-failed", op=op)
        if rid:  # capture-manifest row for this graphify run (plan §4), fail-open
            import datetime as _dt
            now = _dt.datetime.now(_dt.timezone.utc).isoformat()
            manifest.record_graphify(root, import_id=gid, op=op, session=task,
                                     source_path=Path.cwd().name,  # basename only (PII guard)
                                     saving_id=rid, saved=int(raw - actual),
                                     source_files=len(files), ts=now,
                                     session_name=task)  # graphify's name = the task (plan §4)
        return (int(raw - actual), "receipt") if rid else (0, "unmeasurable")
    except Exception as e:                # any metering error → graphify result intact
        debuglog.exception(root, "graphify.meter", e)
        return 0, "error"


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


_NATIVE_EXE_SUFFIXES = (".exe", ".bat", ".cmd", ".com")
_PY_INTERPRETER = re.compile(r"python3?(\.\d+)?$")


def _resolve_argv(cmd: list[str]) -> list[str]:
    """On Windows, ``CreateProcess`` never honors a ``#!`` shebang — that's a POSIX
    kernel behavior, not a shell one — so a script with no native-executable extension
    (``.exe``/``.bat``/``.cmd``/``.com``) fails with WinError 193 even though it runs
    fine everywhere else (a real graphify npm install ships a ``.cmd`` and is
    unaffected). Peek the shebang and prepend its interpreter so it still runs; a
    ``python``/``python3`` shebang resolves to *this* interpreter (``sys.executable``)
    rather than trusting a same-named binary on PATH. Anything else (native
    executables, POSIX) is returned unchanged."""
    if os.name != "nt" or not cmd:
        return cmd
    exe = Path(cmd[0])
    if exe.suffix.lower() in _NATIVE_EXE_SUFFIXES or not exe.is_file():
        return cmd
    try:
        with exe.open("r", encoding="utf-8", errors="ignore") as fh:
            first = fh.readline()
    except OSError:
        return cmd
    if not first.startswith("#!"):
        return cmd
    interpreter = first[2:].strip().split()
    if interpreter and Path(interpreter[0]).name == "env" and len(interpreter) > 1:
        interpreter = interpreter[1:]          # `#!/usr/bin/env X` → X (env itself isn't one)
    if not interpreter:
        return cmd
    if _PY_INTERPRETER.match(Path(interpreter[0]).name):
        interpreter = [sys.executable]
    return interpreter + cmd


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
    import time
    from cage import usagelog
    ah = usagelog.args_hash(cmd)
    t0 = time.monotonic()
    try:
        proc = subprocess.run(_resolve_argv(cmd), capture_output=True, text=True,
                              env={**os.environ, "CAGE_GRAPHIFY_METERED": "1"})
    except (OSError, ValueError) as exc:
        print(f"cage data graphify: could not run {cmd[0]!r}: {exc}", file=sys.stderr)
        usagelog.record(root, op=op, args_hash=ah, exit=127,
                        ms=int((time.monotonic() - t0) * 1000), outcome="error",
                        route="shim")
        return 127
    ms = int((time.monotonic() - t0) * 1000)
    sys.stdout.write(proc.stdout)         # passthrough — byte-identical to bare graphify
    sys.stderr.write(proc.stderr)
    outcome, route = "non-measured", "shim"
    if proc.returncode != 0:
        outcome = "error"
    elif op:
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
            outcome, route = "receipt", "native"
        else:
            saved, outcome = _meter(root, proc.stdout, cmd, task or Path.cwd().name)
            _confirm(root, saved)
    # GC1: one usage row per graphify run, every route — proves usage even on a parse
    # miss (the F1 blind spot). Counts-never-content; never read by a money view.
    usagelog.record(root, op=op, args_hash=ah, exit=proc.returncode, ms=ms,
                    outcome=outcome, route=route)
    return proc.returncode
