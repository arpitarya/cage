# FORMULAS

Every computed number in cage, in one place: the formula, where it lives in code,
its **method tag**, and the knobs that move it. Derived from the source at
v0.36 — `cage query <id>` prints the live version of most of these with your
actual config values interpolated.

Three standing laws frame everything below:

- **`method` is sacred.** `measured` = a recorded fact, read back verbatim · `modeled` =
  reconstructed · `estimated` = a guess. Trust rank
  `{measured: 2, modeled: 1, estimated: 0}` (`constants.METHOD_TRUST`). A
  projection never reads as measured.
- **Derive-time only.** Every view is recomputed from the log on each read; the ledger
  is never rewritten. Change the config, re-read, get new tables.
- **Counts, never conversions.** Cage records tokens and credits and reports them in
  those units. It ships no rate card, computes no currency, and converts between no two
  units in either direction ([ADR-LAWS](adr/0001_laws.md) Law 5).
- **Determinism.** No clocks or randomness in any formula here. Same ledger +
  same policy ⇒ same output, byte for byte.

Entry-point tracker: ALL-CAPS, no frontmatter.

---

## 1. Usage — the two recorded units

**Cage computes no money.** The whole of what was §1 (per-call cost, the credit
pricing ladder, input-only counterfactual cost, budget, forecast, cost drift,
quality-adjusted cost, the two kiro cost sections) was deleted with the money
subsystem — USAGE-ONLY, [ADR-LAWS](adr/0001_laws.md) Law 5. There is
no rate card, no price table and no dollar on any surface.

What replaces it is not a formula. It is a **read**:

### 1.1 Tokens — `measured`

    tokens_in / tokens_out / cached_in / cache_write_in, summed over the rows
    `ledger.spend()` returns.

- **Code:** `cage/ledger.py` (`spend`, `SPEND_SOURCES`) · `cage/report.py`.
- **Basis, and it is per PRODUCER, not per instant:** a producer with its own ledger
  resolves from it for all of history; one without (the retired `codex`, custom
  `[sources.*]` tools, and any pre-v0.51 `lib`/proxy row) resolves from `calls`. There is
  no time cutover — `SPEND_CUTOVER` was retired with the money subsystem.
- **The library consumer joined the first group in v0.51** (`ledger/consumer/`, P1 —
  ADR-CONSUMERS' partial reversal). It is the one producer whose `calls` twin is
  suppressed by an **exact id match** rather than by its agent name
  (`ledger.consumer_twin_calls`): an agent-name test would also suppress every
  *pre-v0.51* `lib` row, which has no twin to replace it. Both halves are counted once,
  and nothing untwinned is ever dropped.
- **`measured`** throughout: every figure is a recorded count read back verbatim.

### 1.2 Credits — `measured`

    credits, summed per agent — NEVER across agents.

- **Code:** `cage/units.py` (`summable`, `cross_agent_note`) · `cage/ledger.py`
  (`credits`, `_credit_from_cli_conv`) · `cage/chats.py`. *(`cage/report.py` went with
  SURFACE-CUT.)*
- **Two homes, one shape (P2, v0.51):** kiro credits are read from `ledger/kiro/`'s
  `cli-conv` rows — the live home — **and** from every legacy `credits-<month>.jsonl`
  shard, forever. The top-level shard is no longer written; nothing was migrated. The
  projection re-applies the credits **skip rule** (credits ≤ 0 **and** context ≤ 0 ⇒ no
  row), which `cli-conv` deliberately does not have, and treats a `None` credit as *no
  signal* rather than a recorded `0.0`. Collapse is unchanged: last-write-wins per
  session, highest turn count, and a session present in both homes yields **one** row.
- **The cross-agent law:** a copilot credit is GitHub's own tokens×rates computation
  over a request; a kiro credit is an AWS credit. They share a column heading and
  nothing else, so a total spanning both is refused (`total.credits = None`) and the
  view says why. Enforced in code, not by convention.
- **Absence ≠ zero, twice over.** A recorded `0.0` is a real billing fact; an absent
  value is written as no key at all (`schema.make_call`'s None sentinel — the one
  additive field that breaks the omit-at-zero idiom). And an agent that records no
  credits *at all* renders `—` with its own sentence (`units.ABSENT`), never a `0`.

### 1.3 The two absences — `units.ABSENT`

Neither unit is universal, and the two gaps are different kinds of fact, so they never
render alike:

| agent | tokens | credits |
|---|---|---|
| claude | value | `—` *"Claude Code records no credit unit on disk"* — a vendor law |
| copilot | value | value |
| kiro | `—` *"no IDE token store on this install"* — a missing file a future Kiro can ship | value |

`cage doctor`'s kiro-IDE check distinguishes **db absent / table missing / column
drift**, so the fixable case announces itself rather than reading as permanent.

---

## 2. Savings

### 2.1 Saved is **GROSS** — inherits the receipt's method

```
saved = raw_alternative − actual                       ← GROSS: avoided read cost
```

- **It excludes the cost of *using* the tool** — the turn that invoked it, the
  round-trip, the context a hook injected, a re-read a thin answer provokes. So
  cage can truthfully print a large `saved` for a session that cost *more* than
  its unassisted twin ([finding](../work/regression/2026-08-01-finding-saved-is-gross.md)).
- Every surface says `gross` for this number: `report`'s `gross tok` column,
  `attrib`'s `gross tok`, the overview headline, the graphify ceiling/history band,
  and CSV's `gross_saved_tokens`. One phrasing, one home: `savings.GROSS_NOTE`
  (relocated from the deleted `netsaved.py` — the netting was money, the *caveat* is
  not).
- Code: [schema.make_savings / make_receipt](../cage/schema.py) — **derived at
  construction**, so the stored number can never be edited into disagreement.
- **A receipt is denominated in its own `unit` and cage converts nothing.** A
  `tokens` receipt contributes tokens; `ms`/`gco2` receipts are recorded, readable
  per-task, and contribute to no token total. The `convert.saved_usd` dispatch that
  used to turn all of them into dollars is gone (ADR 0011). `minutes` was a unit
  through v0.35 (the removed human axis); a legacy `minutes` row is excluded and
  footnoted, never silently dropped.

### 2.1a Net saved — **removed, and not replaced**

Cage reported a task-level net (`gross − the attributable cost of use`) through v0.50.
It is gone with the money subsystem: netting required pricing every in-window call to a
common unit, and **per-query netting was never computable at all** — a shim receipt
carries a `task` but no `call`, and inventing that link is forbidden.

So cage reports **gross only, and says so on every view that prints the number**
(`savings.GROSS_NOTE`, one phrasing, one owner). A large `saved` and a session that
consumed more tokens overall remain simultaneously true; the caveat is what makes that
readable rather than misleading.

The §2.2 call-less receipt **pricing ladder** (`price_at` → dominant task model →
UNPRICED) went with it — there is nothing left to price into.

### 2.3 Marginal attribution — **removed in v0.50 (SURFACE-CUT)**

`cage insights attrib` and `attribution.py` are deleted, so cage computes no marginal
per-tool split. Receipts are still recorded with their own `saved` and `method`; what is
gone is the walk that made Σ(marginals) = total under a fixed pipeline order.
`[tools] order` is still parsed and now has **no consumer at all**
(`work/OPEN-WORK.md`, UNREAD-FACTS). The GROSS rule in §2.1 is unchanged and still
governs every saving cage prints.

### 2.7 graphify transcript receipt — `modeled` (graphify-capture GC2)

At `cage import`, a `graphify query|explain` run detected in a **claude** transcript
(Bash `tool_use` + its `tool_result` text) **or a copilot CLI `events.jsonl`** (F1:
`tool.execution_start` bash `command` + `tool.execution_complete` `result.content`, paired
by `toolCallId`) reuses the ONE counterfactual formula the shim uses
([graphifymeter](../cage/graphifymeter.py)):

```
raw_alternative = Σ toks(cited source files, whole, on disk)   # _cited_files → _raw_alternative
actual          = toks(answer text)                             # the tool_result
saved           = raw_alternative − actual        (filed only when > 0; else no receipt)
```

- `method = "modeled"`, `confidence = GRAPHIFY_RECEIPT_CONFIDENCE (0.6)`.
- Files resolve against the transcript's **own recorded `cwd`**, at import time — they
  may have **drifted** since the query ran (deleted/edited). Unresolved files are
  skipped; a total parse-miss files **no receipt** (never fabricate). This drift is
  acceptable within `modeled`.
- **claude + copilot CLI** (F1, 2026-07-29): both carry command + result, and both route
  through the same `_file_query` (shared counterfactual/id/deferral, ADR 0005 — dedupe and
  the two acceptance tests hold for copilot too, `cage/graphifytx.py:detect_and_file_copilot`).
- **FOUR of five store surfaces file receipts, and the fifth says why not.** The single
  source of truth is `graphifytx.GRAPHIFY_COVERAGE`, and
  `tests/test_formulas_coverage.py` re-derives this list from it — the two-strikes gate for
  a drift review caught twice (this paragraph called copilot-VS-Code *usage-row-only* and
  kiro *HONEST-LIMIT* for three releases after both routes shipped in **v0.47.0**):

  | agent / surface | files receipts? | why |
  |---|---|---|
  | claude cli+vscode | ✅ | transcript Bash `tool_use` paired with its `tool_result` (one store, both surfaces) |
  | copilot cli | ✅ | `events.jsonl` `tool.execution_start`/`complete`, paired by `toolCallId` |
  | copilot vscode | ✅ | `chatSessions` `run_in_terminal` — `commandLine.original` + `cwd.path` + output |
  | kiro cli | ✅ | `conversations_v2` `execute_bash` — but a >~2000-token answer is truncated and correctly files **nothing** |
  | kiro ide | N/A | the store persists no assistant output at all (26/26 empty completions, probed 2026-08-07). The PATH interceptor is the only route here |

  The mark is **N/A**, not ❌, and the two are not interchangeable: per
  [ADR-COVERAGE](adr/0008_coverage.md)'s legend a ❌ means *the signal is in a store cage already
  reads and no code reads it yet* — cage's own backlog. Nothing here is buildable; the store has
  no output to detect. `graphifytx.GRAPHIFY_COVERAGE` records this as `False` either way, which is
  why the gate below asserts the verdict and not the mark's spelling.

### 2.8 graphify report-read receipt — `modeled`, weaker (graphify-capture GC2)

A **Read** of `graphify-out/GRAPH_REPORT.md` / `wiki/**` (reading the map instead of
scanning the files it maps). Counterfactual = the graph's **whole** source-file corpus
([`repoceiling.corpus_tokens`](../cage/repoceiling.py)) — reading the *full* report
genuinely stands in for the whole graph, so unlike the day-one *ceiling* (§2.10, now
community-**bounded**) the report-read legitimately uses the whole corpus:

```
raw_alternative = Σ toks(graph.json source_files, resolved on disk)   # whole corpus
actual          = toks(GRAPH_REPORT.md read)
```

- `op = "report-read"`, `confidence = GRAPHIFY_REPORT_READ_CONFIDENCE (0.3)` — a weaker
  inference than a query citing exact files, so **lower confidence, still `modeled`, and
  footnoted apart** (`graphifytx.report_read_footnote`), never conflated with a query.
- **⚠️ The 0.3 is UNVALIDATED** (raised 2026-07-29 as OPEN-WORK §G.1, a section the
  2026-08-11 restructure removed; **this bullet is now the standing note**): a placeholder, never scored against
  measured outcomes — calibration was deleted in v0.50 and never scored these receipts with recorded
  outcomes to score yet. The footnote says so; the figure is not tuned by intuition.
- Deduped per `(session, file, graph-mtime bucket)` — one per read, not per line.

### 2.9 graphify receipt id + cross-route dedupe — deterministic ([ADR-GRAPHIFY](adr/0007_graphify.md))

```
id = "s_" + sha1(session | op | args_hash | answer_hash)          # graphifymeter.receipt_id
args_hash/answer_hash are route-independent (binary spelling dropped, answer stripped)
```

- Session-inclusive ⇒ per-session attribution (same query, two sessions = two receipts).
- Cross-route convergence (shim + transcript, one run) is a **content-key deferral**, not
  id-collision: the transcript recomputes the shim's session-empty id and defers if
  present. The shim stamps `session=""` (honest — it cannot know the session). Re-import
  is idempotent (`union_by_id`). Residual: a truncated tool result can miss the deferral
  and double-count — the ADR's veto metric.

### 2.10 graphify forward model — `modeled` band/ceiling, never a measured total (GC5)

[graphifymodel](../cage/graphifymodel.py). ⚠️ **Nothing reads it.** Both consumers —
`insights verdict graphify` and `cage report`'s ceiling footer — were deleted in v0.50
(SURFACE-CUT); the module is reachable only from `tests/` and the explain registry. It is
an UNREAD-FACTS item (GFX-MODEL-ORPHAN), kept because it is the only surface that ever
answered *"what would graphify save me here"* with **no receipts on hand** — the day-one
question, currently unanswerable by any command. The formula below is recorded, not live:

```
(a) history band  = median + IQR of graphify receipts' GROSS saved tokens (refuses < MIN_ESTIMATE_N=5)
(b) repo ceiling  = Σ toks(files of the LARGEST community in graph.json)   # day-one, deterministic, BOUNDED
    typical       = median over communities' corpus tokens   ·   whole corpus = context only
```

- **Both are GROSS** (§2.1): the tokens spent *running* the query are not subtracted, so
  the ceiling is a bound on avoided reading, never on net spend. Both renderers say
  so on their own line.

- **Bounded by community structure (Phase A, 2026-07-29).** The whole-corpus sum
  (`repoceiling.corpus_tokens`) over-claims on a real repo — on cage's own graph it is
  552,159 tokens across 249 files, and "one architecture question would read every file"
  is not credible. A graph answer stands in for **one community**, so the ceiling is the
  **largest** community's corpus (`repoceiling.community_corpus` → 89,853 tokens / 22
  files on cage), typical ≈ the **median** community (≈3,007), the whole corpus kept only
  as context. A pre-community graph (no `community` field) falls back to the whole corpus,
  labelled `bounded=False` / `UNBOUNDED` — loud, never silent decoration.
- Both `modeled`; the ceiling is deterministic (same graph + files ⇒ same band) and shown
  even with zero history (the "worth installing here" number). A projection is a band,
  labelled, refusable — never summed into a measured total. (The whole-corpus sum is still
  the counterfactual for a *report-read* receipt, §2.9 — reading the full GRAPH_REPORT.md
  genuinely stands in for the whole graph; that route is separate and confidence-gated.)

### 2.11 graphify usage row — no method (diagnostic only, GC1)

One `state/graphify-usage.jsonl` row per graphify run (`{op, args_hash, exit, ms,
outcome}`, [usagelog](../cage/usagelog.py)). **Never priced, never read by a money view**
— it lives in `state/`, so it can't move a reported number (tested byte-identical).
`args_hash` is a hash, never the query text (counts-never-content).

**It is `sha1(argv[1:])` — the tail, `argv[0]` excluded — on every route.** The shim
invokes the meter as `cage interceptor graphify -- "$REAL" "$@"` (the verb was `cage data
graphify` until v0.50 deleted it and v0.51 restored the door under the new spelling), so
`argv[0]` is an absolute,
machine-specific path; folding it in makes a key nothing else can reproduce. This is the
same exclusion `graphifymeter.content_signature` documents (§2.10), and the reason the
§2.12 attestation join read zero for nine days
([finding](../work/regression/2026-08-12-l1-attest-args-hash-mismatch.md)).

### 2.12 Adoption — **removed in v0.50 (SURFACE-CUT)**

`cage insights adoption` and `adoption.py` are deleted. The usage breadcrumb it read
(`state/`, `usagelog.py`) is still written and still diagnostic-only, and the L1
attestation store (`state/attest.jsonl`) is still written by every wired hook — both now
have no reader (`work/OPEN-WORK.md`, UNREAD-FACTS). The invariant they existed to prove
is unchanged and still tested: a `state/` row can never move a derived number.

### 2.13 Chats view — no new math, one column per ledger field

`cage insights chats` ([chats.py](../cage/chats.py)) is a pure group-by over `calls`,
summed per `(agent, surface, session)` bucket — every column is a straight ledger field
or the existing token sums (§1). No formula lives here that isn't already
spec'd elsewhere.

| column | source |
|---|---|
| `chat` | `imports.jsonl` `session_name` (last-write-wins per `(agent, session)`) → the session id → `(no session)` |
| `agent` / `surface` | `calls.agent` (mapped via `agents.row_surface`) / `calls.surface` |
| `calls` | count of call rows in the bucket |
| `tokens_in` / `cached_in` / `cache_write_in` / `tokens_out` | summed straight off the matching call field |
| ~~`premium`~~ | **no column since 2026-08-11** (COPILOT-PREMIUM-DEAD). It is `floor(credits)` — the same counter as an int — so it stood beside `credits` as a lossy duplicate that printed `0` for every row cage writes (`totalPremiumRequests` is fractional; `int()` floors, `make_call` omits). Still summed into the payload, so `--json` keeps the recorded fact; the *field* is untouched |
| `credits` | summed `calls.credits`, or `—` when **no** call in the bucket recorded one (absence, not zero — §1.2). Text renders 2dp; CSV carries the full float and leaves the cell **empty** when absent, so `—` never enters data. Never summed across agents (§1.2) |
| `agent%` | `agent_lines / (agent_lines + residual_lines)` over the provenance rows sharing this chat's `(agent, session)` — **read** from §2.14's recorded counts, never re-matched. Refuses (`—`, footnoted) three ways; see below |
| `agent_lines` / `residual_lines` (CSV only) | the two sums the share is built from, raw counts. **Empty — not `0` — on a refusal**, like `credits` |
| `agent_pct` (CSV only) | the same share as `0–100` with **1dp** (`csvout.cell` trims a cosmetic trailing zero); empty when refused |

- **The one carve-out:** `chat` is the only column that reads `imports.jsonl` — a
  **label**, not a number. Every other column derives from `calls` + policy alone, and
  deleting `imports.jsonl` moves zero numeric cell (`manifest.py`'s docstring; pinned by
  `tests/test_chats.py`'s money-independence test).
  Kiro-IDE stamps a constant session id, so its rows already collapse into one bucket by
  construction — `chat` renders the honest `kiro (no session identity)`, never a
  fabricated per-run label.
- **Kiro-CLI conversations render too (CHATS-CREDITS, 2026-08-13)** — they are
  `ledger.credits` rows (no `tokens_in`/`tokens_out`, no call at all), read alongside
  `calls` and bucketed the same way, one row per `(agent, surface, session)`, kept
  structurally apart from any call bucket by a trailing discriminator in the bucket key
  so the two shapes can never blend. A credits-only chat renders `calls` and all four
  token cells `—` in text / **empty** in CSV (absence, not a fabricated `0`); `credits`
  is filled from the row exactly as any other chat's `credits` column. `cost` prices
  only through the existing `[billing.<agent>] usd_per_credit` rung (`creditprice.
  rate_for`) — unset ⇒ `—` (a count with nowhere to convert, not a `$0.0000`), `0.0` ⇒
  a real `$0.0000`. CSV `method` is the row's own recorded method (`estimated`,
  `schema.make_credit`'s default) when unrated, `modeled` when rate-priced — the
  generic `creditprice.method_for` alone would read an all-empty `basis` as `measured`,
  which overclaims a bucket that was never token-priced at all. Rank gains a second key:
  `(-tokens_in, -(credits or 0.0), session)` — a credits-only chat (`tokens_in=0`)
  always sorts below any token-bearing chat, and among its own kind, higher credits
  first; this is ordering, never arithmetic, so it does not blend the two axes. No
  manifest row exists for a kiro-CLI conversation today, so its title always falls back
  to the session id (a future store-side title is a follow-up, not this change).
- **No method tag on the grouping itself** — the same reasoning as §2.12: a sum and a
  sort are not a claim about how a number was priced. `cost` inherits `call_usd_match`'s
  tag exactly like `report` (§1), which means a bucket with any credits-priced row
  carries `modeled` in the CSV `method` column, not `measured` (§1.1a).
- **`agent%` scope, and the sentence the footnote must carry:** it is the share of
  *evidenced lines in files this chat touched* — **never** a share of the chat's work.
  Lines in files no session proposed are §2.14's `unattributed`: commit-scoped, so
  structurally outside this denominator. That is scope, not redistribution.
- **Three refusal shapes, each `—` and each footnoted — `—` is never 0%.**
  **coverage** (copilot/kiro, `authorcapture.coverage_note()` verbatim — their stores
  hold no edit text) · **no landed evidence** (no row joined, or rows carrying no
  matchable line: not committed yet, or committed in another repo/ledger root —
  "nothing landed" ≠ "the agent wrote nothing") · **pre-upgrade** (rows predating
  `residual_lines`; excluded from **both** sums and counted in one footnote). A
  *measured* `0%` renders `0%`, which is why the dash can never be spent on absence.
- **The second money-independent carve-out.** `agent%` reads `ledger/provenance/` (monthly since v0.51; the legacy `provenance.jsonl` is read forever) —
  counts only, and deleting it moves **zero** pre-existing cell; only the authorship
  cells fall to `—`. Same terms as the `chat`-label carve-out, pinned by the same test
  file. **No USD, no rate, no minutes ever touches it** (the v0.36 law): `agent%` never
  combines with a spend figure, and no presentation switch moves an authorship cell (asserted per-formula in
  `tests/test_chats.py`, since this module legitimately imports `prices` for `cost`).
- **Two stated limits.** A provenance row carries no `surface`, so a session split
  across surfaces attaches its counts to **every** such bucket — footnoted, because
  those rows are not independent evidence. And per chat there is no diff to clamp
  against (§2.14 clamps per commit), so two chats that proposed the same landed file
  each count its lines: **the commit view stays the arbiter for any single sha**.
- **The third money-independent carve-out, restated for the new shape.** `ledger.
  credits` no longer feeds only a refusal — it feeds real rows — but the guarantee is
  the same as the manifest-title and provenance-count carve-outs: a credits row can
  never perturb a **call** chat's cells, only add a row of its own. Deleting the
  credits shard removes the credits-only rows and changes zero numeric cell on any
  call-based chat (`tests/test_chats.py::
  test_reading_credits_adds_a_row_and_moves_no_call_chat_cell`).
- **The filter is blamed only when the filter is the reason.** `No chats match agent
  'kiro' — the filter is empty, not the ledger` is true about the filter and misleading
  about kiro-IDE, whose absence is structural (IDE rows routed to the machine ledger,
  [ADR-KIRO](adr/0005_kiro.md)). Kiro-CLI used
  to carry a second structural reason (credits rows produced no chat at all); CHATS-
  CREDITS removed it by giving those rows a real chat row, so the only structural
  reason left is the IDE-routing one. The empty view names the reasons it can evidence,
  and only for the agent asked about; an absence with no structural cause keeps the
  filter message unchanged.
- Ranking (`tokens_in` desc, then session id) and the top-20 cut (`--all` lifts it) are
  render-time only — `chats.summarize()` returns every row un-truncated, so `--all` can
  never move a number, only how many rows are shown. CSV is never truncated. Explained
  by `cage query chats-view`.

### 2.14 Per-commit authorship — the four buckets, and **no money at all**

`cage insights commits` / `commit <sha>` / `cage authorship summary`
([commitview.py](../cage/commitview.py), [linematch.py](../cage/linematch.py),
[ADR-AUTHORSHIP](adr/0009_authorship.md)).
**No USD, no rate, no valuation appears on any of these surfaces** — the standing guard
from the v0.36 removal, and it is structural: `commitview.py` imports no pricing module
(asserted in `tests/test_commitview.py`).

**Commit windows, and the one UTC normal form** ([commitjoin.py](../cage/commitjoin.py)).
Commit `i` owns `(ts_{i-1}, ts_i]` — upper bound **inclusive**, oldest commit open below.

```
norm_ts(ts)   = parse (naive ⇒ assume UTC) → astimezone(UTC) → "%Y-%m-%dT%H:%M:%SZ"
                sub-seconds TRUNCATED, never rounded; unparseable/empty ⇒ ""
Window(lo,hi) = bounds normalized AT CONSTRUCTION — a raw-bound window cannot be built
window_for    = normalize the probe, then  lo < probe <= hi        (a STRING compare)
```

Three shapes reach that one `<`: git's `%cI` renders each commit in its **committer's own
offset** (`…+05:30`; `…Z` only when that offset is zero), a call stamps `…SSZ`, a
transcript turn stamps `…SS.mmmZ`. Ordering strings across offset representations is
meaningless, so normalization happens **at the boundary** — bounds on construction, probes
on entry — and the comparison itself stays a string compare (determinism law: no datetime
objects in stored rows).

**Seconds, not milliseconds, is load-bearing.** `%cI` carries no sub-second, so a commit
stamped `10:00:00` happened somewhere in `[10:00:00, 10:00:01)`. Finer precision would push
an edit at `10:00:00.500` — plausibly *before* the commit — into the next window, breaking
the inclusive bound. Evidence and the two claims this corrected:
[finding](../work/regression/2026-08-02-finding-commit-window-timestamp-skew.md).

**Line matching (capture, P1).** For each edit an agent proposed, in the commit whose
window contains that edit's own turn timestamp:

```
normalize(line)  = collapse internal whitespace runs, strip ends   (ONE function, BOTH sides)
matchable(line)  = len(normalize(line)) >= MIN_MATCH_CHARS          (= 4)
proposed         = new_string lines − old_string lines              (MULTISET, 2026-08-11)
kept             = |proposed ∩ added|   as MULTISETS — a proposed line is spent once
suggested        = kept + kept_modified + dropped                   (exactly; asserted)
```

**`proposed` subtracts re-stated context (2026-08-11).** An `Edit`'s `new_string` is a
replacement *block*, not a diff — it repeats surrounding lines to anchor the edit, and
those were already in the file. They were entering `suggested`, and `kept_modified` with
them via `modified = suggested − kept`. `old_string` was read nowhere in the package
before this. The subtraction is `linematch.subtract_context`, and it lives **in
`linematch`** because deciding "is this proposed line the same as that context line" is
matching, and rule 1 says only `linematch` may normalize for matching; `transcript`
carries the raw text and compares nothing.

- Consumes 1:1 and never touches a sub-gate line — removing one would move lines out of
  `unknown`, which is never redistributed.
- **The opposite error is real and deliberate:** an agent that legitimately *re-adds* a
  line from `old_string` is now under-credited. That is the direction to err in — this
  surface observes the agent precisely and lets the human be the residual, so an unearned
  proposal is worse than a missed one.
- `Write` / `NotebookEdit` carry a whole body or cell and have **no** `old_string`, so
  their unchanged lines stay unsubtractable. Stated, not papered over.
- Rows written before 2026-08-11 keep the inflated counts — provenance is frozen by its
  idempotency key and is never backfilled.

| persisted count | definition |
|---|---|
| `suggested` | proposed lines clearing the gate |
| `kept` | of those, landed **verbatim** in the commit's added lines |
| `kept_modified` | proposed lines whose **file** landed but whose line did not match |
| `dropped` | proposed lines whose file is absent from the commit |
| `agent_lines` | the added-line side of the same match (= `kept`; separate name, §3.5) |
| `residual_lines` | matchable added lines in **this row's own landed files**, minus `agent_lines`, floored at 0 — the not-the-agent side of its own scope, and the denominator half of §2.13's `agent%`. Scoped to the row's landed files on purpose: `unattributed` is a commit fact, and folding it in would let every session on a commit claim the same lines |

**Commit shas are stored FULL and displayed SHORT (2026-08-11).** `commitjoin.head`,
`commit_windows` (`%H`), `tasks.git_snapshot` and `originrecord.current_sha` all record
the full 40 characters; every table abbreviates to `constants.SHORT_SHA_DISPLAY` (7).
`--json`/`--csv` carry the full sha — an abbreviated *key* is what this change exists to
stop storing.

- **Why, given both sides were `--short` and therefore agreed:** they agreed by
  coincidence of the moment. Git's auto-abbreviation length grows with a repo's object
  count, so rows written at 7 characters sit beside rows written at 8 and an
  exact-equality join between them fails **silently** — a task's calls stop landing on
  their commit, and an attestation stops beating the `~` estimate.
- **Every read joins through `commitjoin.prefix_match`, which is prefix-SYMMETRIC** — a
  stored short sha is a prefix of a full probe and vice versa — so rows written before
  the change keep joining. They are append-only and can never be rewritten.
- **A probe matching two commits is refused** (`AMBIGUOUS`), distinct from `no-match`:
  *cannot tell which* and *do not have it* are different answers. This was the real
  defect in the area — prefix matching already existed here, but `render_commit` takes
  `rows[0]` over an **oldest-first** sort, so an ambiguous prefix rendered the *oldest*
  match confidently.
- Method tags are untouched: a window join stays `modeled`, an attestation stays
  `attested`.

**A rename's numstat name is not a path (2026-08-11).** `git show --numstat` renders a
rename as `old.py => new.py` or `d/{a => b}/f.py`, neither of which can key-match a
`+++ b/<path>` line. `linematch.numstat_path` resolves both to the **destination**, and
is shared by `commit_diff` and `originrecord.commit_numstat` so the two duplicate
`_NUMSTAT` patterns cannot disagree. Before it, a renamed file's counts went to a
phantom key and the file itself scored `DROPPED`.

Line **bodies** and line **hashes** are never persisted — a hash is a membership oracle
over the source. Only these six integers, and only counts.

**Five are omitted at 0; `residual_lines` is written at 0** — the one deliberate
deviation (`schema.PROVENANCE_ZERO_BEARING_COUNTS`). **Presence of the key is the
version gate**: absent means *this row predates the count* (renders `—` forever — rows
are frozen by `originrecord`'s idempotency key and are never backfilled), while a
recorded `0` is the real finding *everything matchable matched the agent*. Omitting it
would make the most flattering true result indistinguishable from no data. Same
absent-vs-recorded-zero law as `credits`' `None` sentinel (§1.1a). A caller that does
not line-match supplies nothing and writes the pre-v2 row byte-for-byte.

**The four buckets (derive, P3).** Over one commit's added lines:

```
unknown       = lines failing matchable()                    (+ binary files, counted as FILES)
agent         = Σ agent_lines from that commit's provenance rows, clamped to
                (matchable − unattributed)                    ← READ, never re-matched
unattributed  = matchable lines in files NO session proposed
human~        = matchable − unattributed − agent
```

- **Nothing is redistributed.** `unknown` is shown, never folded into agent or human to
  make a split reach 100.
- **`unattributed` is not `human`.** A file nobody proposed may be human-written,
  vendored, or generated — cage has no evidence which. Measured: a single `human`
  bucket printed **76.6%** on cage's own repo, 89% of it one commit of generated JSON
  ([dogfood](../work/regression/2026-08-02-p1-authorship-dogfood.md) §4).
- **`agent` is read from the row, never re-derived.** Re-matching at render time would
  be a second matcher, free to disagree with the one that wrote the row.
- The split renders as a share of *classified* added lines, so the four sum to 100%.

**Call → commit join (P2, `modeled`).** Task-id first (`taskgroup.join_rows`, reused —
never a second join), then the commit window. A task closed on a **dirty tree** is not
trusted: its snapshot sha is the *prior* commit, so it falls back to the window. A call
must be confirmable as this project — a **different** `project` stamp is excluded, and
an **empty** one is excluded as *unconfirmable* (adopting it would pull other repos'
spend onto these commits). Exclusions are counted by reason, never merged.

**Hours — three visibly distinct tiers, and it refuses four ways.**

```
*  attested  = human_minutes / 60          (cage task time)  — ALWAYS wins
~  estimated = max(0, wall − agent_span) / 3600
—  refused   when: estimate_hours = false · no previous commit (no wall)
                 · NO agent span joined (the value would be the raw commit gap)
                 · wall > [authorship] max_est_gap (default 4h)
wall       = commit_ts − previous commit_ts                      measured
agent_span = Σ latency_ms where > 0                              measured (lib-metered only)
             else last_turn_ts − first_turn_ts, rendered `~`     modeled (includes think-time)
```

| number | method |
|---|---|
| tokens per commit | **measured** counts, **modeled** join |
| `agent` lines | **transcript** (the provenance row's own method), direct evidence |
| `human~` lines | **estimated** — "not the agent" is the observation, so the label says so |
| `unattributed` / `unknown` | not an estimate at all: counted refusals |
| attested hours | the user's assertion — never inferred, never outranked |
| estimated hours | **estimated**, method named in the view's own footnote |

Knobs: `MIN_MATCH_CHARS` (constants — **not** policy: it changes what the buckets
*mean*) · `[authorship] capture` / `estimate_hours` / `max_est_gap` (+ `CAGE_AUTHORSHIP`,
`CAGE_AUTHORSHIP_ESTIMATE`). Explained by `cage query agent-authorship`.

### 2.15 Graphify per-chat view — `modeled`, GROSS throughout

`cage insights graphify` ([graphifychat.py](../cage/graphifychat.py)) reuses
`chats.summarize` verbatim for the chat universe (title, agent, surface, session,
token sums) and joins `ledger.savings` rows (`tool="graphify"`) onto it by `session`
alone — a savings row carries no agent field at all.

```
tokens   = tokens_in + tokens_out             (the chat's recorded, WITH-graphify world;
                                                None when the chat is from_credits — a
                                                kiro-CLI conversation has no token counts)
Σsaved   = Σ saved over this session's graphify savings rows      (0 when receipts = 0)
without  = tokens + Σsaved                    (the MODELED without-graphify counterfactual;
                                                None when tokens is None; never clamped —
                                                a negative `saved` can push it below tokens)
saved%   = 100 × Σsaved / without              (None when tokens is None or without <= 0)
```

- **`tokens` is real regardless of graphify usage** — it is the chat's own recorded
  fact, independent of whether any graphify receipt joined. Only the graphify-derived
  cells (`gfx uses` / `without gfx` / `saved` / `saved%`) dash for a chat with zero
  receipts, and only in `--all-chats` (the default view excludes them entirely) — a
  receipt-less chat's "no usage" must never render as "measured zero saving", the same
  absence-vs-recorded-zero law every other view in this file follows.
- **A real zero renders `0%`.** A chat WITH receipts whose `raw_alternative == actual`
  (`saved = 0`) is a *measured* zero and renders `0%`, never a dash — distinct from the
  "no receipts at all" refusal above.
- **A kiro-CLI credit chat** (`from_credits`) carries `saved` (a real receipt still
  joined by session) but `tokens`/`without`/`saved%` dash — it has no token counts to
  build a counterfactual from, footnoted.
- **Never clamped.** `saved` can be negative (the answer cost more than the read it
  avoided) and `without` can then fall below `tokens`; both render honestly.
- **GROSS throughout** (`savings.GROSS_NOTE`, §2.1) — per-chat NET is not computable:
  the attributable-cost rule needed a call-level tool-use mark this ledger
  doesn't carry, so this view is explicitly GROSS and says so on every render.
- **`method`/`confidence`** per chat are the worst-case across its joined receipts
  (least-trusted method wins, confidence is the min) — the exact
  `attribution.receipts_by_tool` aggregation, inlined. Always `modeled` in practice
  (every graphify receipt is `modeled` or `estimated`, never `measured`).
- **Two tallies never redistribute into a chat row**, footnoted apart: `unassignable`
  (the native shim's honest-empty `session=""`, GC3) and `unmatched` (a savings session
  joining no chat bucket — a different ledger root, a deleted call). Neither is folded
  into any row's numbers.
- **A session split across surfaces** (rare — savings rows carry no surface) attaches
  its receipts to every chat bucket sharing that session, footnoted (`gfx_split`), the
  `auth_split` precedent (§2.13).
- Tokens-only, like every view since ADR 0011 (and the v0.36 no-blend law before it). Ranking
  `(-saved, session)`, top-20 (`GRAPHIFY_CHATS_DEFAULT_ROWS`), `--all` lifts the cut
  (footnoted, never silent); CSV is always untruncated and never filters by receipts.
  Explained by `cage query graphify-chats`.

## 3. The human axis — **removed in v0.36**

Every formula that lived here (human cost `usd = minutes / 60 × rate`, derived
attention `minutes = Σ min(gap_ms, cap)`, and time saved
`human_minutes − agent_active_minutes`) is **gone with the Tier-1 axis**, substrate
included — see the CHANGELOG's v0.36 *Removed* section.

The one rule that outlives them, because pre-0.36 ledgers still hold the rows:

- A legacy `tool="human"` / `unit="minutes"` receipt is worth **`$0` in
  any unit conversion** and is **excluded from every derived total** by
  [`report._is_legacy_human`](../cage/report.py) — there is no rate left to price it
  at. The exclusion is **counted and footnoted** on `cage insights chats`
  (`· N legacy human-axis receipt(s) excluded …`), never applied silently.
  Explained by `cage query savings-axis`; pinned by `tests/test_legacy_ledger.py`.

**A v2 exists, and it is a different question.** §2.14 rebuilds agent-vs-human
**per commit** — the unit v1 lacked. Nothing here came back: no rate, no USD, no
`gap_ms`, no `minutes` unit, no derived attention. What v2 adds is line-level evidence
(the agent's proposals matched against the commit's added lines) and a human that is an
explicitly-labelled *residual*, split into `human~` and `unattributed` so a generated
file is never reported as a person's work. Hours exist only as an attestation or a
guarded, `~`-marked estimate whose method is printed beside it.

## 4. Prediction & calibration

### 4.1–4.3 Estimate, calibration, group compare — **removed in v0.50 (SURFACE-CUT)**

`cage insights estimate` / `calibration` / `compare` and their three modules are deleted,
so cage predicts nothing and scores nothing. `tasks.jsonl` still records outcomes, labels
and any previously-stamped `est_*` fields — a closed task is still a closed task, and
`MIN_COMPARE_N` / `MIN_ESTIMATE_N` remain in `constants.py` unread. **§4.4 below is
unaffected**: the fleet study has its own pairing math in `study.py` and survives whole.

### 4.4 Fleet study pairing — `measured` per machine-day, `estimated` delta

```
sample unit = the machine-day
paired delta = median over machines of (phase-B median daily − phase-A median daily)
refuses below MIN_COMPARE_N machines having both phases
```

Code: [study.py](../cage/study.py). Phases are recorded markers resolved against
each machine's own clock; machine ids are opaque random tokens, never hostnames.
Coverage (days + gaps) always prints first.

### 4.5 Task correlation — `estimated` at confidence 0.5, **disabled by default**

```
adopt import-sourced (empty-task) calls into CLOSED tasks by the taskgroup
session-window join (session match → task call-span window → overlaps: smallest task id)
gates: policy [capture] task_correlation (default false) AND MIN_TASK_CORRELATION_N = 5
```

Code: [taskcorr.py](../cage/taskcorr.py). **Derive-time only — never mutates a
call row's `task`** (a heuristic written in-row would read as ground truth).
Activation requires validation against real correlated data.

## 5. Heuristics & counts

### 5.1 Token heuristic — makes anything built on it `modeled`/`estimated`

```
tokens ≈ round(len(text) / CHARS_PER_TOKEN)        (CHARS_PER_TOKEN = 4)
```

Code: [constants.py](../cage/constants.py), used by
[compress.py](../cage/compress.py), [graphifymeter.py](../cage/graphifymeter.py).
Deterministic, no tokenizer, no network. The zero-dep third-party shims
(`fux/cage_receipt.py`, graphify) keep a local `len/4` copy — an intentional
duplicate.

### 5.2 Window parsing

```
24h / 7d / 2w → days via SINCE_WINDOW_DAYS = {h: 1/24, d: 1, w: 7}
```

A malformed `--since` raises at the CLI boundary rather than silently rendering
an unfiltered table (a table claiming a window it didn't apply is a wrong
number).

### 5.3 Ledger size warning

```
LEDGER_WARN_BYTES = LEDGER_WARN_MONTHS(24) × 30 × LEDGER_HEAVY_ROWS_PER_DAY(2000)
                    × LEDGER_ROW_BYTES(290)
```

Policy `[ledger] warn_mb` wins over the constant.

## 6. Reader semantics that change totals

Not formulas, but they decide which rows the formulas see:

- **`ledger.receipts()` is an id-deduped union** of `receipts.jsonl` with the
  `savings/<tool>/` tree ([mergeutil.union_by_id](../cage/mergeutil.py), tree
  wins on a duplicate id; id-less rows preserved). A row present in both stores
  counts **exactly once** — the guarantee behind the deleted `migrate-savings` verb
  being idempotent and half-migration-safe.
- **Month partitioning:** writers append to the shard chosen from the row's own
  `ts`; readers glob + concatenate; `--since` skips whole below-cutoff months.
- **Derive-time repricing** applies in report · budget · quality · regression ·
  forecast — every surface that sums money.

## 7. Where the numbers live (the three layers)

Never mixed, by design ([CLAUDE.md](../CLAUDE.md) *Constants*):

| Layer | Home | Example |
|---|---|---|
| **Contract** | `schema.py` closed enums | `METHODS`, `UNITS` |
| **Policy** | `cage.toml` (your decisions) | tool order, capture switches, cleanup, authorship. **No `prices.toml`** — the rate card went with ADR 0011 |
| **Constants** | `constants.py` (code heuristics, reviewable) | `CHARS_PER_TOKEN`, `MIN_COMPARE_N`, `IDLE_CAP_MINUTES` |

Several constants are **policy-preferred fallbacks** — the policy value wins when
present: `DEFAULT_CONFIDENCE`, `IDLE_CAP_MINUTES`, `LEDGER_WARN_BYTES`,
cleanup days, price staleness, import staleness.

## Maintaining this file

Update it in the same change as any formula, constant, or method-tag change —
it is in [DOC-REGISTRY.md](../work/DOC-REGISTRY.md) with that trigger. Cross-check
against the live explainer registry ([explain_data.py](../cage/explain_data.py))
and `cage query --list --kind calculation`: this file and the registry must
agree, and the registry is the one that ships in the binary.
