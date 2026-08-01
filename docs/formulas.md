# FORMULAS

Every computed number in cage, in one place: the formula, where it lives in code,
its **method tag**, and the knobs that move it. Derived from the source at
v0.36 — `cage query <id>` prints the live version of most of these with your
actual policy values interpolated.

Three standing laws frame everything below:

- **`method` is sacred.** `measured` = a real invoice/run · `modeled` =
  reconstructed · `estimated` = a guess. Trust rank
  `{measured: 2, modeled: 1, estimated: 0}` (`constants.METHOD_TRUST`). A
  projection never reads as measured.
- **Derive-time only.** Money is recomputed from tokens × policy on every read;
  the ledger is never rewritten. Change a price, re-read, get new numbers.
- **Determinism.** No clocks or randomness in any formula here. Same ledger +
  same policy ⇒ same output, byte for byte.

Entry-point tracker: ALL-CAPS, no frontmatter.

---

## 1. Money

### 1.1 Per-call cost — `measured`

```
full_in = max(0, tokens_in − cached_in)
usd     = (full_in·input + cached_in·cache_read + tokens_out·output) / 1_000_000
```

- Code: [prices.call_cost_usd / call_usd_match](../cage/prices.py) · knobs:
  `prices.toml [prices]` (split out of `cage.toml`, prices-toml plan §3;
  a legacy in-`cage.toml` block still reads via the fallback) ·
  `TOKENS_PER_MILLION = 1_000_000`.
- Cached input bills at the `cache_read` rate, not `input` — this is why a
  cache-heavy ledger's headline is dominated by cache reads.
- **Match ladder** (`call_usd_match` → `exact | alias | family | self | none`):
  an exact/alias/family price row ⇒ recompute from tokens; no row but a stored
  `est_cost_usd` ⇒ `self` (a provider cage can't tokenize, self-reporting);
  neither ⇒ `none` = **UNPRICED**, surfaced loudly, never a silent `$0`.
- A normalized match renders `family`/`alias`, never `exact` (method law applied
  to pricing).

### 1.2 Input-only cost (counterfactual cells) — `modeled`

```
usd = tokens_in · input / 1_000_000
```

Code: [prices.input_cost_usd](../cage/prices.py). Used by the matrix, where only
input volume differs between cells.

### 1.3 Budget — `measured`

```
Σ call_usd(window)  vs  policy [budgets] session_usd / daily_usd
on_exceed = warn | block
```

Code: [budget.py](../cage/budget.py). The totals are measured; the ceiling is
policy, not a guess.

### 1.4 Forecast — `estimated`

```
per_day   = Σ call_usd / span_days
projected = per_day × 30
blows     = projected > (daily_usd × 30)
day_blown = ⌊(daily_usd × 30) / per_day⌋ + 1
```

Code: [forecast.project](../cage/forecast.py). Linear extrapolation of observed
spend — no seasonality, no model.

### 1.5 Cost-per-call drift (regression) — `measured` totals, `estimated` verdict

```
mean(window) = Σ call_usd(rows) / n
drift        = (recent_mean − base_mean) / base_mean
regressed    = drift > tolerance            (default tolerance 0.2)
```

Code: [regression.detect](../cage/regression.py). Split at `--since`; both sides
repriced at derive time.

### 1.6 Quality-adjusted cost — `measured`

```
per_task    = Σ call_usd / task_count
per_success = Σ call_usd / ok_count        (None when ok = 0 — never faked)
```

Code: [quality.summarize](../cage/quality.py) · outcomes in `.cage/outcomes.json`
(`ok | redo`). Cost per *successful* task is the metric that catches false
economies.

### 1.7 Kiro CLI cost — credit-derived, `estimated` (by vendor design; no token counts exist)

```
Kiro CLI usage = credits + context_usage_percentage        (never token counts)
credit row: schema.make_credit, method = "estimated", recorded not priced
```

- Code: [transcript.parse_kiro_cli_credits](../cage/transcript.py) →
  `credits-YYYY-MM.jsonl`, a **distinct row kind** (never a `tokens_in=0` call).
- **Which conversations enter the sum** (2026-08-01, [ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)
  *Scope*): the store keys each conversation by the cwd it ran in, so a sweep into a
  project ledger sums only that project's **directory tree** and stamps `project` on the
  row; a sweep into the machine ledger sums all of them. Knob:
  `paths.kiro_cli_workspace`. Reading unscoped from a project (the behaviour through
  v0.35) summed every conversation on the machine into every ledger.
  **This is the opposite of the kiro *IDE* store**, whose rows carry no cwd and are
  therefore machine-level by construction — see §1.7a.
- **Why `estimated` is final — not a temporary limit.** Kiro CLI (the Amazon Q /
  CodeWhisperer CLI) reports usage only as **credits + context %**; its store's
  token fields (`total_tokens`/`uncached_input_tokens`/`output_tokens`/
  `cache_read/write_input_tokens`) are **null on every turn**, floor and large-input
  alike. There is no token count to measure, so no `measured`/`modeled` cost is
  derivable — only a credit-derived `estimated` one, always.
- **The proxy route was tried and closed (P2, 2026-07-28 —
  [`docs/regression/2026-07-28-kiro-proxy-probe.md`](regression/2026-07-28-kiro-proxy-probe.md)).**
  `cage data meter` (the in-path proxy, [proxy.py](../cage/proxy.py)) sets only
  `ANTHROPIC_BASE_URL`/`OPENAI_BASE_URL`; kiro-cli honors **neither** — it routes to
  AWS CodeWhisperer / Amazon Q (`api.codewhisperer.service`/`api.q.service`), speaks
  a SigV4 AWS protocol `usageparse` can't read, and cage's plaintext reverse-proxy
  can't MITM its TLS. Two real probe turns under the proxy recorded **0 call rows**.
  Even a perfect intercept would parse null tokens (the same reason the store is null).
- **Method law:** a *proxy-measured* Kiro number could be `measured` — but that path
  does not exist for Kiro. The credit-derived number is `estimated`, always; the two
  are never blurred.

### 1.7a Kiro IDE cost — which *ledger* the rows are summed in

```
kiro-IDE rows → the machine ledger (~/.cage), one copy per machine
             → unless --ledger/CAGE_BASE names a sink (then: that sink)
```

- Code: [paths.kiro_ledger / kiro_routed](../cage/paths.py) · the leg is
  `importcmd._kiro_leg`. Decision:
  [ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md).
- **Not a formula change — a *domain* change.** The per-row arithmetic is untouched;
  what changed is which rows are in a project's sum at all. `tokens_generated.jsonl` is
  one global file with no project, session or per-turn `ts`, so every ledger that
  imported it summed the same turns. Now exactly one ledger holds them.
- **Knobs:** `--ledger`/`CAGE_BASE` (or `CAGE_LEDGER`) collapse the two sinks and the
  override wins; `[capture] enabled` must be on in **both** the project and the machine
  ledger for the routed leg to run.
- **Limit that survives:** a kiro-IDE row's `ts` is stamped at import, so it can be
  summed but never *windowed* — `--since` includes or excludes it by when the import
  ran ([finding](regression/2026-08-01-finding-kiro-rows-carry-no-time-session-project.md)).
  Pre-0.36 duplicated rows in a project ledger are never rewritten and still sum.

## 2. Savings

### 2.1 Saved is **GROSS** — inherits the receipt's method

```
saved = raw_alternative − actual                       ← GROSS: avoided read cost
```

- **It excludes the cost of *using* the tool** — the turn that invoked it, the
  round-trip, the context a hook injected, a re-read a thin answer provokes. So
  cage can truthfully print a large `saved` for a session that cost *more* than
  its unassisted twin ([finding](regression/2026-08-01-finding-saved-is-gross.md)).
- Every surface says `gross` for this number: `report`'s `gross`/`gross tok`
  columns, `attrib`'s `gross tok`/`gross $`, `roi`'s `gross saved`, the overview
  headline, the graphify ceiling/history band, and CSV's `gross_saved_*`. One
  phrasing, one home: `netsaved.GROSS_NOTE`.
- Code: [schema.make_savings / make_receipt](../cage/schema.py) — **derived at
  construction**, so the stored number can never be edited into disagreement.
- USD conversion dispatches on `unit` ([convert.saved_usd](../cage/convert.py)):
  `usd` passthrough · `tokens` at the model's input price · `ms` / `gco2` → `$0`
  (real, not missing). `minutes` was a unit through v0.35 (the removed human
  axis); a legacy `minutes` row is excluded from money and footnoted, never priced.

### 2.1a Net saved (cost of use) — `modeled`, its own lower confidence

```
cost of use = Σ prices.call_usd(c)  over the DISTINCT calls joined to the receipt's
              task whose ts lies within ±NET_ATTRIB_WINDOW_S (120s) of ANY of that
              tool's receipts on that task        (union per task — counted once)
net         = gross − cost of use                        (covered tasks only)
```

- Code: [netsaved.by_tool](../cage/netsaved.py) · knobs:
  `constants.NET_ATTRIB_WINDOW_S = 120`, `constants.NET_SAVED_CONFIDENCE = 0.4`.
  Live: `cage query gross-vs-net`. Rendered by `cage insights verdict <tool>`.
- **Why the window.** Shim receipts are *call-less* (a `task`, never a `call`), so
  per-query netting is impossible and is not attempted. Of the three computable
  candidates: *the whole task* charges the tool for work it merely assisted (it
  measures task size); *only turns carrying a tool-use block* is sharper but no
  ledger field marks one, so it needs a capture-time change. The ±window is the
  honest computable middle. **Symmetric** because both adjacent turns are
  cost-of-use — the turn that *invoked* the tool precedes the receipt, the turn
  that *consumed* its output follows it.
- **A lower bound.** A re-read three turns later is not counted. Net is the
  optimistic end of the range, never the pessimistic one.
- **Coverage refuses rather than approximates.** A task whose receipts join no
  in-window call is UNCOVERED — its net is *unavailable*, never rendered equal to
  gross. Since one in-window call at a priced model implies a non-zero subtrahend,
  `net == gross` cannot be produced by a failed join.
- **Method:** gross is `modeled`; the subtrahend is `measured` (recorded tokens
  repriced through the same `prices.call_usd` as `report`/`budget`); **net is
  `modeled`** at `0.4` — below gross's own confidence, because it stacks a
  time-window join on top of gross's counterfactual. Net is never `measured`.

### 2.2 Call-less token receipt pricing ladder — `modeled`

A `tokens` receipt with a task but no call (graphify/fux shims) prices via
[receiptprice.resolve](../cage/receiptprice.py):

```
1. policy [tools.<tool>] price_at          (cage prices route-tool → cage.toml)
2. dominant model of the task              (ties: tokens_in → call count → lexicographic)
   priced against prices.toml [prices]
3. UNPRICED + a runnable per-tool fix line
```

Linked receipts never enter the ladder. Rung is footnoted in text, `priced_via`
in CSV.

### 2.3 Marginal attribution — per-row method = least-trusted receipt for that tool

```
walk tools in policy order (cage.toml [tools.order])
each receipt's credit = its marginal saving given the tools upstream of it
⇒ Σ(marginals) = total saving, no double-count
```

Code: [attribution.py](../cage/attribution.py). Marginal-by-fixed-order is
deliberate: Shapley is fairer but combinatorial, and cage is `$0`
([PLAN.md](PLAN.md) §4, §10).

### 2.4 Counterfactual matrix — one `measured` cell, the rest `modeled`

```
enumerate 2ⁿ on/off tool permutations        (n ≤ MAX_MATRIX_TOOLS = 12 ⇒ 4096 rows)
cell input tokens = base + Σ(actual if tool on else raw_alternative)
cell usd          = input_cost_usd(cell tokens) at the task's model
```

Code: [matrix.py](../cage/matrix.py). Only the configuration actually run is
`measured`; every other cell is `modeled` — `estimated` if it leans on an
estimated receipt.

### 2.5 ROI — inherits each receipt's method

```
per tool:  Σ gross_saved_usd  vs  Σ meta.tool_cost_usd  and  Σ meta.added_latency_ms
net of own cost =  gross_saved_usd − cost_usd
verdict         =  enable if net > 0 else skip           (cage insights recommend)
```

Code: [roi.py](../cage/roi.py), [recommend.py](../cage/recommend.py). A
deterministic tool declares `$0` of its **own** cost — which is *not* the same as
free: the cost of *using* it is in neither column (§2.1, §2.1a). Columns are named
for exactly that: `gross saved` / `net of own cost` (CSV: `gross_saved_usd`,
`net_of_own_cost_usd`).

### 2.6 Verdict — `modeled` headline, per-line tags below

A pure composer — computes no new statistics
([verdict.py](../cage/verdict.py)):

```
net        = roi.gross − roi.own_cost [− netsaved.cost_of_use, if it covers the window]
             → sign gives SAVING / COSTING
break_even = net / receipt_count
≈$/mo      = net scaled by the receipts' own time span (≥ 7 days, no clock)
```

Plus marginal saving (attribution), **net of use** (§2.1a), drift (regression),
redo-rate (quality). A missing input ⇒ **INSUFFICIENT DATA**, never an
approximation.

**The gross qualifier (NET-2).** The cost of use is subtracted only when
`netsaved` covers **every** receipt in the window; otherwise it is not subtracted
at all. The omitted term is **≥ 0**, and the refusal rule follows from that
asymmetry rather than from taste:

| roi net | cost of use known | verdict |
|---|---|---|
| `< 0` | either | **COSTING** — omission can only worsen it, so the sign is safe |
| `≥ 0` | no / partial | **SAVING (GROSS)** / **BREAK-EVEN (GROSS)** + a ⚠ naming the exclusion and pointing at `cage insights compare` |
| any | yes, complete | **SAVING / COSTING / BREAK-EVEN** on `net of use` |

A distinct verdict rather than INSUFFICIENT DATA because gross is a genuinely
computed number — the defect was the *label*, not the arithmetic, and discarding
the figure would hide the very comparison the finding exists to make visible.

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
  Copilot **VS Code** is usage-row-only (F2: its `chatSessions` log has the command but not
  the result, so no counterfactual). **Kiro is HONEST-LIMIT** (no tool bodies in the log).

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
- **⚠️ The 0.3 is UNVALIDATED (OPEN-WORK G.1):** a placeholder, never scored against
  measured outcomes — `insights calibration` has no report-read receipts with recorded
  outcomes to score yet. The footnote says so; the figure is not tuned by intuition.
- Deduped per `(session, file, graph-mtime bucket)` — one per read, not per line.

### 2.9 graphify receipt id + cross-route dedupe — deterministic ([ADR 0005](adr/0005-graphify-receipt-ids-session-inclusive-cross-route-deferral.md))

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

[graphifymodel](../cage/graphifymodel.py), composed into `insights verdict graphify`:

```
(a) history band  = median + IQR of graphify receipts' GROSS saved tokens (refuses < MIN_ESTIMATE_N=5)
(b) repo ceiling  = Σ toks(files of the LARGEST community in graph.json)   # day-one, deterministic, BOUNDED
    typical       = median over communities' corpus tokens   ·   whole corpus = context only
```

- **Both are GROSS** (§2.1): the cost of *running* the query is not subtracted, so
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

## 3. The human axis — **removed in v0.36**

Every formula that lived here (human cost `usd = minutes / 60 × rate`, derived
attention `minutes = Σ min(gap_ms, cap)`, and time saved
`human_minutes − agent_active_minutes`) is **gone with the Tier-1 axis**, substrate
included — see [PLAN.md](PLAN.md) §4.6 and the CHANGELOG's v0.36 *Removed* section.

The one rule that outlives them, because pre-0.36 ledgers still hold the rows:

- A legacy `tool="human"` / `unit="minutes"` receipt is worth **`$0` in
  `convert.saved_usd`** and is **excluded from every money view** by
  [`report._is_legacy_human`](../cage/report.py) — there is no rate left to price it
  at. The exclusion is **counted and footnoted** on `cage report`
  (`· N legacy human-axis receipt(s) excluded …`), never applied silently.
  Explained by `cage query savings-axis`; pinned by `tests/test_legacy_ledger.py`.

## 4. Prediction & calibration

### 4.1 Estimate band — `modeled`

```
band = median + IQR of measured totals over closed tasks matching the EXACT keys
       (scope / label / agent)          — no similarity scoring, no ML
refuses below MIN_ESTIMATE_N = 5 matching tasks
```

Code: [estimate.py](../cage/estimate.py). `--record` stamps
`est_tokens`/`est_usd`/`est_n` **plus the band bounds** onto the open task row,
so calibration can later score against the band *as recorded*.

### 4.2 Calibration — `measured`

```
ratio    = actual_tokens / est_tokens          (median + IQR)
hit_rate = share of actuals inside the band recorded at estimate time
```

Code: [calibration.py](../cage/calibration.py). This observed frequency **is**
the estimator's confidence — the estimator never self-reports one. Open,
zero-actual, and band-less tasks are skipped with a visible count.

### 4.3 Group compare — `measured` groups, `estimated` delta

```
group closed tasks by stack signature (task-id join; session-window fallback)
per group: n · median · IQR of measured tokens + USD
delta = median(stack) − median(agent-only), same non-stack keys
refuses below MIN_COMPARE_N = 5
```

Code: [compare.py](../cage/compare.py), [taskgroup.py](../cage/taskgroup.py).
The delta ships with a standing observational caveat: different tasks, nothing
randomized — an observed difference, never a causal claim.

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
  counts **exactly once** — the guarantee behind `cage data migrate-savings`
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
| **Policy** | `cage.toml` (your decisions) + `prices.toml` (vendor rate card) | budgets, human rate, tool order, routing · **prices**/`[credits]` in `prices.toml` |
| **Constants** | `constants.py` (code heuristics, reviewable) | `CHARS_PER_TOKEN`, `MIN_COMPARE_N`, `IDLE_CAP_MINUTES` |

Several constants are **policy-preferred fallbacks** — the policy value wins when
present: `DEFAULT_CONFIDENCE`, `IDLE_CAP_MINUTES`, `LEDGER_WARN_BYTES`,
cleanup days, price staleness, import staleness.

## Maintaining this file

Update it in the same change as any formula, constant, or method-tag change —
it is in [DOC-REGISTRY.md](DOC-REGISTRY.md) with that trigger. Cross-check
against the live explainer registry ([explain_data.py](../cage/explain_data.py))
and `cage query --list --kind calculation`: this file and the registry must
agree, and the registry is the one that ships in the binary.
