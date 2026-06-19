# Handoff — token-saving receipts for graphify & fux

**Goal.** Teach **graphify** and **fux** to file token-saving receipts into cage so
`cage attrib` / `cage matrix` / `cage roi` stop printing *"no receipts recorded yet
— teach your tools to emit them"* and start showing real with/without numbers for
points 2 & 3 of the cage spec. The engines already exist (`attribution.py`,
`matrix.py`, `roi.py`); this is purely **instrumentation** — emitting the receipts
they consume.

**Status:** spec-first. The one prompt in §7 executes the whole thing.

---

## 1. The receipt contract (don't reinvent it)

cage already exposes a fail-open emit API and a deterministic token heuristic. Use
them verbatim — matching numbers is what makes graphify and fux comparable.

```python
from cage import record_receipt   # fail-open: returns "" on failure, never raises

record_receipt(
    tool="graphify",            # or "fux" — must match policy.toml [tools].order
    unit="tokens",
    raw_alternative=raw_tok,    # the no-tool counterfactual, in tokens
    actual=actual_tok,          # what the tool actually put in context
    method="modeled",           # the alternative is reconstructed, not invoiced
    confidence=0.7,             # honest: the counterfactual is an upper bound
    call="",                    # link to a call id if known; else ""
    task=task_id,               # the task/session this saving belongs to
    meta={"op": "query"},       # small, non-PII provenance only
)
# saved = raw_alternative − actual is DERIVED by cage; never set it yourself.
```

**Token count — copy cage's heuristic exactly** (`compress._toks`), so all tools
speak the same unit, `$0`, no tokenizer dependency:

```python
def _toks(text: str) -> int:
    return max(0, round(len(text) / 4))   # ~4 chars/token, deterministic
```

## 1a. Two integration strategies — because the repos are owned differently

| Tool | Ownership | Strategy |
|------|-----------|----------|
| **fux** | yours | **In-tool shim** (§3) — fux emits its own receipts; it knows the exact injected payload + selected sources, so this is the most accurate. |
| **graphify** | **third-party — NO repo edits allowed** | **External cage-side adapter** (§4) — cage wraps the unmodified `graphify` command, parses its output, and files the receipt itself. graphify is never touched. |

This asymmetry is deliberate and matches cage's design: cage already meters tools it
doesn't own by observing them (`cage meter -- <cmd>`, `import-codex`, the transcript
parser). graphify joins that family; only fux, which you control, emits in-process.

## 2. The hard constraints

- **graphify repo is read-only.** Nothing in this handoff edits graphify. All
  graphify measurement lives in cage (or an anton-side wrapper you own).
- **cage is an *optional* dependency for fux, never a hard one.** fux is
  zero-runtime-dep; importing cage unconditionally breaks that. Use the **fail-open
  lazy shim** in §3 so fux works identically with cage absent. (Mirrors anton's
  `cage_meter` adapter and the `[cage]` optional extra.)
- **Deterministic, no model, no network** on the measuring path — both sides of the
  receipt are computed by counting characters of text the tool already has/emits.
- **`method` is sacred.** The *actual* side is real (text the tool emitted), but the
  *alternative* is a reconstructed counterfactual → tag the receipt **`modeled`**
  (never `measured`), with `confidence < 1`. Don't oversell the saving.
- **No PII / no payload bodies in `meta`.** Counts, op-name, and ids only — never
  rule text, file contents, code, or paths beyond a top-level area.

## 3. The fux shim (in fux only, ~15 lines, fail-open)

`fux/cage_receipt.py` (graphify gets **no** shim — see §4):

```python
"""Optional cage integration — emit a token-saving receipt, no-op if cage absent."""
from __future__ import annotations


def toks(text: str) -> int:
    return max(0, round(len(text) / 4))


def emit(tool: str, raw_alternative: int, actual: int, *, task: str = "",
         op: str = "", confidence: float = 0.7) -> None:
    """File a 'tokens' receipt with cage. Silent if cage isn't installed/usable."""
    if actual >= raw_alternative:          # no saving to claim — stay honest
        return
    try:
        from cage import record_receipt
        record_receipt(tool=tool, unit="tokens", raw_alternative=raw_alternative,
                       actual=actual, method="modeled", confidence=confidence,
                       task=task, meta={"op": op})
    except Exception:                       # cage missing or any error → no-op
        return
```

## 4. graphify — measured externally by a cage adapter (no repo edits)

**graphify is read-only**, so cage measures it by wrapping the unmodified command:

```
cage graphify -- graphify query "how does X relate to Y"
```

The adapter (`cage/graphifymeter.py` + a `cage graphify` subcommand) runs graphify
as a subprocess, **passes its stdout/stderr/exit-code through unchanged** (the user
sees an identical result), and on the side parses the captured answer to file one
receipt. A metering failure must never alter graphify's output or exit code
(fail-open, like `cage meter`). An alias `graphify='cage graphify -- graphify'` (or
pointing the agent's graphify tool at the wrapper) makes it transparent.

**Saving mechanism.** `graphify query|path|explain` returns a graph-traversal
answer instead of the agent grepping and reading raw source files to derive the
same thing.

**Counterfactual — `raw_alternative` binding (resolved).** graphify nodes store
`source_file` + a *single-line* `source_location` (e.g. `L42`), **not** line
ranges, and the source files may be absent when querying a prebuilt `graph.json`.
So there is no reliable per-node *region* to read. Bind to **whole touched source
files, present-only**:

- `actual` = `toks(captured_answer)` — graphify's stdout for this invocation.
- `raw_alternative` = **parse the answer for the `source_file` paths it cites,
  dedupe, read each whole file that exists on disk, sum `toks()`**. Bounded to
  *touched* files (never the repo). Deterministic, no extra dependency.
- **If no source files resolve / can't be parsed** (off-repo prebuilt graph,
  output format changed), **emit nothing** — do not fall back to graph-internal
  text (collapses to ~zero) or infer spans between nodes (fabricates ranges).
  Honest silence beats a fabricated or collapsed saving.
- `saved` = the delta. `confidence ≈ 0.6` already discounts that a grep-and-read
  agent might not read each file whole. `meta={"op": "query"}`.

> Rejected alternatives (for the record): *graph-body text only* — pointers not
> bodies, saving ≈ 0; *inferred line spans `[Lk, L(k+1)]`* — fragile, guesses
> unrecorded ranges, high complexity for little honesty gain.

**Parsing graphify's output (the adapter's one fragile point).** graphify's output
format is owned by someone else, so the parser must be tolerant and fail-open:
**prefer a structured mode** (`graphify query --json` or equivalent) for a stable
extraction of `source_file`s; fall back to a regex over the text answer; if neither
yields source paths, emit nothing. Pin the expected format in a comment and treat a
parse miss as "unmeasurable," never as zero saving. One receipt per invocation,
emitted via `cage.record_receipt(tool="graphify", unit="tokens", …,
method="modeled", confidence=0.6, meta={"op": "<query|path|explain>"})`.

## 5. fux — what it saves and where to measure it

**Saving mechanism.** `fux hook-recall` (UserPromptSubmit) injects only the rules
relevant to the prompt instead of the whole rule/memory corpus; `fux why|refs`
return a targeted entry instead of the agent reading whole docs.

**Counterfactual (honest, conservative default).**
- `actual` = `toks(injected_recall_payload)` — what fux actually injected.
- `raw_alternative` = `toks(relevant_sources_whole)` — the same knowledge as the
  raw rule/ADR/memory files fux selected, loaded *whole* (the distilled-vs-source
  saving). This is the defensible default. A broader "entire corpus" framing is
  allowed but lower confidence — note it in `meta`, don't make it the default.
- `saved` = delta. `confidence ≈ 0.7`. `meta={"op": "hook-recall"}` (or `why`/`refs`).

**Instrumentation point.** In the hook-recall assembly (`hooks` / `recall`), once
the injected payload and the set of source entries are both known, call
`cage_receipt.emit("fux", raw, actual, task=<session>, op="hook-recall")`. Likewise
in `why`/`refs` if you want those credited.

## 6. Why graphify + fux compose cleanly in the matrix

They shrink **disjoint context slices** — graphify the *code/structure* slice, fux
the *rules/decision/memory* slice. Their savings don't overlap, so their marginal
contributions are simply additive in `policy.toml [tools].order =
["graphify", "fux", …]`. No double-counting to subtract; `cage matrix <task>` will
show graphify-on/off × fux-on/off as four honest, independent cells.

## Acceptance criteria

1. **graphify is never edited** — zero diff in the graphify repo. `cage graphify --
   graphify query …` produces byte-identical stdout/stderr/exit vs bare `graphify
   query …`; a metering failure does not change graphify's result.
2. With cage absent, **fux** runs byte-identically (shim no-ops in a cage-less env —
   no error, no output change).
3. With cage present: a real `fux hook-recall` appends exactly one `tool="fux"`
   receipt (in-tool); a real `cage graphify -- graphify query …` appends exactly one
   `tool="graphify"` receipt (adapter-parsed). Both `unit="tokens"`,
   `method="modeled"`, `saved` positive and `= raw_alternative − actual`.
4. Nothing is filed when `actual >= raw_alternative`, and the graphify adapter files
   nothing when no `source_file` can be parsed/resolved (unmeasurable ≠ zero).
5. After a session, `cage attrib <task>` shows both tools as separate rows and
   `cage matrix <task>` shows the 4-cell graphify×fux grid; `cage roi` lists both.
6. Token counts use `len/4`; **no dependency added to fux** (stays zero-dep) and
   **nothing added to graphify** (untouched). The cage adapter is stdlib-only.
7. `meta` contains only `op` + counts — no rule text, code, file contents, or PII.

## 7. Doc-sync

- **cage:** `README.md` / `docs/agents.md` — document the `cage graphify` adapter
  (external metering of a third-party tool) and that fux emits in-tool; this handoff
  is the contract.
- **fux:** `docs/fux-implementation.md` — add the optional cage receipt under
  hook-recall; `README.md` if the integration is user-visible.
- **graphify:** **no edits** (third-party). If anything, note the wrapper usage in
  *anton*'s docs where graphify is invoked, not in graphify itself.

---

## 8. THE prompt — run once to execute all

The copy-paste build prompt is maintained as a separate file so it stays in sync
with this contract: **`cage/docs/tool-receipts.graphify-fux.build-prompt.md`**. It
implements the two-strategy split — fux in-tool shim (§3), graphify external cage
adapter (§4) — with staged, stop-if-red steps and the doc-sync in §7. Hand that
file to Claude Code.
