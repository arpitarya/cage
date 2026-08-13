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
- **Match ladder** (`call_usd_match` → `credits | exact | alias | family | self | none`):
  a recorded billed credit + a configured rate ⇒ `credits` (§1.1a, and it wins
  outright); else an exact/alias/family price row ⇒ recompute from tokens; no row
  but a stored `est_cost_usd` ⇒ `self` (a provider cage can't tokenize,
  self-reporting); neither ⇒ `none` = **UNPRICED**, surfaced loudly, never a
  silent `$0`.
- A normalized match renders `family`/`alias`, never `exact` (method law applied
  to pricing).
- **`call_usd_match` is the ONE pricing choke point.** Every USD consumer in cage
  (report · budget · chats · compare · verdict · roi · netsaved · study · forecast ·
  quality · freshness · doctor) reaches a dollar through it or its `call_usd`
  wrapper, so a rung added there is inherited with no per-view fork.

### 1.1a Billed-credit pricing (rung 1) — `modeled`, never `measured`

```
usd = credits · [billing.<agent>] usd_per_credit
```

Code: [creditprice.resolve](../cage/creditprice.py), reached from
`prices.call_usd_match`. Knob: `cage.toml [billing.<agent>] usd_per_credit`
(**unset by default**). Explained by `cage query copilot-credits`.

| rung | applies when | tag |
|---|---|---|
| 0 · `credits-rate`, **$0.00** | the row carries `billed_with` (its billing is on another row) **and** a rate is configured | `modeled` |
| 1 · `credits-rate` | the row carries a recorded `credits` **and** a rate is configured | `modeled` |
| 2 · `token-table` | otherwise, if the model resolves a price row (§1.1) | `measured` |
| 3 · UNPRICED | neither | none — loud, counted, two runnable fixes |

- **Rung 0 · one basis per shutdown** (REV-CREDITS defect 2, closed 2026-08-11 —
  [compare](compare/copilot-pricing-basis.compare.md)). GitHub computes
  `totalPremiumRequests` over **every** model in a `session.shutdown`, so the figure
  lands on one carrier row and every sibling carries `billed_with = <carrier id>`. Such a
  row prices at `$0.00` **on the credits basis** with the carrier's id as the matched key
  — *priced, elsewhere, by name*. Without it the carrier billed GitHub's whole-shutdown
  figure while its siblings billed their own tokens at list rates: the same spend twice.
  Splitting the credit pro-rata by token share was **rejected** — it would derive per-row
  credits from tokens, forbidden in both directions. The suppression is conditional on a
  rate existing (with none, the carrier falls to rung 2 and so must the group).
  **Forward-only:** rows written before the change are never rewritten and still split.

- **Why rung 1 outranks a perfectly good price row:** since 2026-06-01 a Copilot
  credit *is* GitHub's own tokens×rates computation, done with what cage cannot see —
  which model `copilot/auto` actually routed to, and GitHub's current rates. It
  prices that router *exactly*, with no price-table row at all.
- **The tag is `modeled` and the reason is the split of fact and interpretation:**
  the credit *count* is recorded on the row, but the *dollar* is that count times a
  rate the user configured, which cage cannot check against an invoice. Any aggregate
  containing one credits-priced row degrades to `modeled` — the weaker tag always
  wins (`creditprice.method_for`), because a mixed cell claiming `measured` would let
  a configured rate read as an invoice.
- **Rate unset is not rate zero.** Unset ⇒ rung 1 is skipped and credits render as a
  **count**, never a dollar. A rate of exactly `0.0` is a different, legitimate
  statement and does price, at `$0.0000`.
- **Absence ≠ zero, and neither is derived from tokens.** No recorded credit ⇒ fall
  through to rung 2; a recorded `0.0` ⇒ a real zero priced through rung 1 (§3.1).
- **Never blended silently:** a total spanning both bases prints the split
  (`creditprice.split_footnote`), and CSV names the winning basis per row in
  `priced_via` (`credits-rate | token-table | mixed`).
- A credits-priced row contributes **no** `cache_usd` split — its dollar never came
  from the price table, so attributing a slice of it to `cache_read` would describe a
  total that was never token-derived.

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
- **Two read surfaces, both derive-only (REPORT-CREDITS, 2026-08-13).**
  `cage insights chats` (§2.13) renders one row per conversation; `cage report`
  (`report.py`) folds credits into its own `--by agent` / default `--by route`
  table, a new `credits` column present only when this view actually joined a
  `ledger.credits` row (other dims, and a ledger with none, are byte-identical to
  before). A credits-only group's `calls`/`tok in`/`tok out` cells are `—` in text /
  **empty** in CSV — absence, never a fabricated `0` — while its `credits` cell
  carries the recorded figure. `cost` prices only through `[billing.<agent>]
  usd_per_credit` — unset ⇒ `—`, a configured `0.0` ⇒ a real `$0.0000` — the same
  ladder rung `creditprice.rate_for` already serves `chats.py`. **The one number a
  report total must never silently drop:** a group whose calls and credits rows
  share one bucket (rare — an agent whose calls and call-less credits conversations
  land in the same ledger root) sums both into that cell rather than keeping only
  the token-priced half, and `render_report` names the split
  (`· total spans two pricing bases: …`) whenever both sides are non-zero — the same
  discipline `creditprice.split_footnote` applies to the copilot per-call ladder.
  `net vs spend` subtracts the same full sum, so a rated credits dollar can never
  read as an uncounted saving. CSV `method` degrades to `modeled` whenever any group
  priced via this rung (`creditprice.method_for`, weaker tag wins) — the same rule
  as the existing per-call credits ladder, extended to cover this second population.

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
- **⚠️ The 0.3 is UNVALIDATED** (raised 2026-07-29 as OPEN-WORK §G.1, a section the
  2026-08-11 restructure removed; **this bullet is now the standing note**): a placeholder, never scored against
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

**It is `sha1(argv[1:])` — the tail, `argv[0]` excluded — on every route.** The shim
invokes the meter as `cage data graphify -- "$REAL" "$@"`, so `argv[0]` is an absolute,
machine-specific path; folding it in makes a key nothing else can reproduce. This is the
same exclusion `graphifymeter.content_signature` documents (§2.10), and the reason the
§2.12 attestation join read zero for nine days
([finding](regression/2026-08-12-l1-attest-args-hash-mismatch.md)).

### 2.12 Adoption — **no method**: counts of recorded rows, never an estimate

`cage insights adoption` ([adoption.py](../cage/adoption.py)) makes no claim that needs a
method tag. Its only two assertions are *this many rows exist* and *this many join to an
agent*. Two halves, never blended — they have different precision:

| half | source | precision | agent? |
|---|---|---|---|
| **A · invocations** | usage rows (§2.11) | exact, no join | only with an **L1 attestation** (below) — otherwise none |
| **B · per-agent** | savings rows → `calls.agent` | exact where a link resolves | only where it resolves |

- **Half A's agent split needs the opt-in L1 hooks, and says nothing without them.**
  A usage row has no `agent` field, so half A was agent-blind by construction. A hook
  runs *inside* the agent, so `cage hook tool --agent X` records an attestation
  ([attest.py](../cage/attest.py), `state/attest.jsonl`) keyed by the **same
  `args_hash`** the usage row already carries (§2.11 — the **tail**, on both sides; one
  producer disagreed until 2026-08-12 and the join could not fire at
  all) — an exact join, never proximity. With no
  attestations the block is **absent entirely**, not empty: `by_agent.present = False`
  and the renderer emits nothing, so a hookless project's output is byte-identical to
  before L1 existed. An `args_hash` **two agents attested resolves to unknown**, never a
  pick. Every attested number carries `attest.LIMIT` — hooks are CLI-only, so a VS Code
  run is a real invocation that leaves no attestation and must never read as *no agent*.
- **Attestation does NOT fix half B.** A graphify savings row's id folds in an *answer*
  hash no attestation can reconstruct, so `no-link` stays structurally true. The two
  halves are still never blended.

- **Outcomes are read, never re-derived.** The per-outcome tally reads each row's
  recorded `outcome` (`usagelog.OUTCOMES`); re-deriving "did a receipt land?" from the
  receipts would produce a second, disagreeing answer.
- **Half B's join, in order:** linked `call` id → that call's agent · else a `session`
  exactly one agent's calls carry. A session shared by two agents stays **unknown** —
  picking one would invent a fact.
- **Agent-unknown has two reasons, kept apart:** `no-link` (no call, no session) is the
  interceptor's *structural* limit — a subprocess cannot know which agent spawned it, so
  it stamps an empty session on purpose ([graphifymeter](../cage/graphifymeter.py));
  `unjoined` (a link nothing matches) is a *capture gap*. Never an "other" bucket, never
  attributed by timestamp proximity.
- **"Never invoked" has two strengths, and the weaker one is the default when anything
  is unattributed.** *No evidence of invocation* is sound only when **every** savings row
  found an agent; otherwise an unattributed row could belong to any agent, so the claim
  drops to *no savings row attributed to them*. Neither is ever stated as proof of
  non-use.
- **No currency anywhere.** Nothing here calls `convert`/`receiptprice`/`prices`; §2.11's
  diagnostic-only invariant holds unchanged, asserted from this new caller in
  `tests/test_adoption.py`.
- CSV column contract: `section` · `dimension` · `key` · `agent` · `tool` · `rows` ·
  `joined_via` · `reason` · one column per outcome. An inapplicable cell is **empty**,
  never `0`. The attested split adds `usage,agent,<name>` rows with `joined_via=attest`
  plus a `usage,agent-unattested` row carrying its reason — CSV never gates a caveat
  away. Explained by `cage query tool-adoption` and `cage query agent-layers`.

### 2.13 Chats view — no new math, one column per ledger field

`cage insights chats` ([chats.py](../cage/chats.py)) is a pure group-by over `calls`,
summed per `(agent, surface, session)` bucket — every column is a straight ledger field
or the existing `prices.call_usd_match` (§1). No formula lives here that isn't already
spec'd elsewhere.

| column | source |
|---|---|
| `chat` | `imports.jsonl` `session_name` (last-write-wins per `(agent, session)`) → the session id → `(no session)` |
| `agent` / `surface` | `calls.agent` (mapped via `agents.row_surface`) / `calls.surface` |
| `calls` | count of call rows in the bucket |
| `tokens_in` / `cached_in` / `cache_write_in` / `tokens_out` | summed straight off the matching call field |
| ~~`premium`~~ | **no column since 2026-08-11** (COPILOT-PREMIUM-DEAD). It is `floor(credits)` — the same counter as an int — so it stood beside `credits` as a lossy duplicate that printed `0` for every row cage writes (`totalPremiumRequests` is fractional; `int()` floors, `make_call` omits). Still summed into the payload, so `--json` keeps the recorded fact; the *field* is untouched |
| `credits` | summed `calls.credits`, or `—` when **no** call in the bucket recorded one (absence, not zero — §1.1a). Text renders 2dp; CSV carries the full float and leaves the cell **empty** when absent, so `—` never enters data |
| `agent%` | `agent_lines / (agent_lines + residual_lines)` over the provenance rows sharing this chat's `(agent, session)` — **read** from §2.14's recorded counts, never re-matched. Refuses (`—`, footnoted) three ways; see below |
| `agent_lines` / `residual_lines` (CSV only) | the two sums the share is built from, raw counts. **Empty — not `0` — on a refusal**, like `credits` |
| `agent_pct` (CSV only) | the same share as `0–100` with **1dp** (`csvout.cell` trims a cosmetic trailing zero); empty when refused |
| `cost` (`--usd` only) | `Σ prices.call_usd_match(pol, call)` per row (§1); UNPRICED counted, never a silent `$0` |
| `priced_via` (CSV only) | which rung paid for this bucket — `credits-rate` \| `token-table` \| `mixed` when its rows split, empty when nothing priced |

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
- **The second money-independent carve-out.** `agent%` reads `provenance.jsonl` —
  counts only, and deleting it moves **zero** pre-existing cell; only the authorship
  cells fall to `—`. Same terms as the `chat`-label carve-out, pinned by the same test
  file. **No USD, no rate, no minutes ever touches it** (the v0.36 law): `agent%` never
  combines with `cost`, and `--usd` moves no authorship cell (asserted per-formula in
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
  [ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)). Kiro-CLI used
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
[ADR 0008](adr/0008-line-match-authorship-counts-persisted-content-transient.md)).
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
[finding](regression/2026-08-02-finding-commit-window-timestamp-skew.md).

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
  ([dogfood](regression/2026-08-02-p1-authorship-dogfood.md) §4).
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

**A v2 exists, and it is a different question.** §2.14 rebuilds agent-vs-human
**per commit** — the unit v1 lacked. Nothing here came back: no rate, no USD, no
`gap_ms`, no `minutes` unit, no derived attention. What v2 adds is line-level evidence
(the agent's proposals matched against the commit's added lines) and a human that is an
explicitly-labelled *residual*, split into `human~` and `unattributed` so a generated
file is never reported as a person's work. Hours exist only as an attestation or a
guarded, `~`-marked estimate whose method is printed beside it.

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
