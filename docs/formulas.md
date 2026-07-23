# Cage formulas — every computed number, in one place

Every `modeled` or `estimated` figure cage prints comes from a formula a human
can check by hand — no regression, no ML, no weights. This file is the
catalogue. **Live values:** each entry names its `cage query` id — the on-box
answer interpolates *your* policy/constants at render time (this file shows
the shape; `cage query` shows your numbers).

> **Maintenance rule (now mechanical):** the formula blocks below are
> **generated** from the calculation entries in `cage/explain_data.py` —
> `python -m tools.docgen --target formulas` rewrites them, and CI's
> `python -m tools.docgen --check` fails on drift (plan Phase 5.6). A new
> calculation entry without an anchored block here fails the same check.
> The prose between blocks is hand-written and survives regeneration.

## Spend

**Call cost** — `query: cost` · measured · `cage/prices.py`

<!-- formula: cost -->
```
usd = (input·in_price + cached·cache_read + output·out_price) / 1,000,000
  recompute from tokens × policy when the model is priced; else fall back to
  the stored est_cost_usd (a provider cage can't tokenize). Derive-time only —
  the ledger is never rewritten.
```

Recomputed from tokens × the policy price table at read time, every time —
the ledger stores counts, never conclusions. Unpriced model ⇒ the stored
`est_cost_usd` if the provider self-reported, else UNPRICED (never $0-as-if-free).
Knobs: `[prices.*]` rows.

**Token heuristic** — `query: token-heuristic` · deterministic approximation · `cage/constants.py`

<!-- formula: token-heuristic -->
```
tokens ≈ round(len(text) / 4)   (deterministic, no tokenizer)
```

No tokenizer, on purpose. Anything built on it can be `modeled`/`estimated`,
never `measured`.

## Pricing

**Price-row matching** — `query: pricing-match` · exact `measured`; family/alias footnoted · `cage/policy.py`

<!-- formula: pricing-match -->
```
resolution order over this policy's 51 price rows:
  exact — the raw (provider, model) key has its own row: an invoice.
  alias — an explicit [alias] route (router pseudo-models like copilot/auto);
    explicit routing beats every heuristic, and a dangling alias is none,
    never a fallback guess.
  family — the same-provider row sharing the most leading segments after
    normalization (route prefixes copilot/ strip · '.' folds to '-' ·
    effort tiers high · low · max · medium drop); needs ≥ 2 shared
    segments, so opus never borrows a sonnet price. Renders with a footnote —
    a normalized match is never allowed to read as exact (method law).
  self — no row, but the provider self-reported est_cost_usd at record time.
  none — UNPRICED: a genuine $0 that must surface, never hide in a total.
```

**Derive-time repricing** — `query: repricing` · measured · `cage/prices.py`

<!-- formula: repricing -->
```
pricing is derive-time: report/budget/compare/study recompute every call
  as tokens × the *current* policy row on each run — the ledger stores
  counts, not conclusions, and is never rewritten. So an analyst fixing
  policy.toml re-prices every imported bundle row retroactively: same
  ledger + same policy ⇒ same tables; new policy ⇒ honestly new tables.
  Exceptions that do NOT re-derive: self-costed calls (their stored
  est_cost_usd was the provider's own figure) and receipts' recorded values.
```

**UNPRICED** — `query: unpriced` · a refusal, never a number · `cage/prices.py`

<!-- formula: unpriced -->
```
a call whose model matched none bills $0 — the totals are understated and
  every read surface says so out loud rather than hiding it (a wrong number
  is worse than none). In text tables the cell renders `—` (the ONLY
  meaning of the dash: couldn't price; `$0.0000` is always a real zero),
  the TOTAL carries `(+ unpriced)`, and the full ⚠ block renders in the
  `--usd` view (the token default carries one muted pointer). CSV keeps an
  explicit empty + priced_via=none — the glyph never enters data.
  Fix workflow: `cage prices unpriced` lists each
  offending (provider, model) with call count, token volume, and a
  ready-to-run fix line; find the real rate on the vendor's pricing page
  (cage never fetches — no network on any cage code path), then
  `cage prices set <provider> <model> --input … --output …` or, for a
  router pseudo-model, `cage prices alias`. Caveat: self-costed rows
  (stored est_cost_usd) and receipts keep their recorded values.
  Tool receipts refuse the same way: a call-less token receipt no ladder
  rung prices prints its own ⚠ line with a runnable fix —
  run: cage prices route-tool <tool> --to <provider>/<model>  (or run in a metered session)
  (see `receipt-pricing` for the ladder).
```

In text views an unpriced cell renders `—` (never `$0.0000`); the ⚠ block
carries the counts and one runnable fix per model. CSV keeps an explicit
empty + `priced_via=none` — the glyph never enters data.

## Savings & attribution

**Receipt saving** — `query: saved` · inherits the receipt's method · `cage/schema.py`

<!-- formula: saved -->
```
saved = raw_alternative − actual   (USD via the call's model price)
```

`raw_alternative` is what would have been sent without the tool — a
reconstruction, so tool receipts are `modeled` unless the tool measured both
sides.

**Call-less receipt pricing (the ladder)** — `query: receipt-pricing` · modeled · `cage/receiptprice.py`

<!-- formula: receipt-pricing -->
```
a token receipt with no resolvable call (graphify/fux shims — the saved
  tokens belong to future calls the shim can't know) prices by a
  deterministic ladder, resolved at derive time (never written back):
  1. price_at — explicit routing: [tools.<tool>] price_at = "provider/model",
     written by `cage prices route-tool <tool> --to <provider>/<model>`
     (this policy: none configured). A dangling route is UNPRICED, never a
     fall-through — the dangling-alias rule.
  2. task-model — the dominant model of the calls joined to the receipt's
     task (task-id calls + session-window adoptions): max Σ tokens_in,
     ties → call count → lexicographic provider/model (a total order).
  3. refusal — UNPRICED, loudly: run: cage prices route-tool <tool> --to <provider>/<model>  (or run in a metered session).
  The USD keeps the receipt's own method; the rung is footnoted in
  roi/attrib text and a `priced_via` CSV column. Receipts with a
  resolvable call never enter the ladder (their path is unchanged).
```

**Marginal attribution** — `query: marginal-attribution` · per-row worst-case method · `cage/attribution.py`

<!-- formula: marginal-attribution -->
```
walk tools in policy order (graphify → fux → router → compressor → cache → response-cache); each receipt is its marginal saving
  given the tools upstream of it, so Σ(marginals) = total, no overlap.
```

**Counterfactual matrix** — `query: matrix` · only the run stack is measured · `cage/matrix.py`

<!-- formula: matrix -->
```
enumerate 2^n on/off tool permutations (n ≤ 12); input tokens =
  base + Σ(actual if on else raw_alternative), costed at the task's model.
```

**ROI** — `query: roi` · inherits receipt methods · `cage/roi.py`

<!-- formula: roi -->
```
per tool: Σ saved_usd  vs  Σ meta.tool_cost_usd  and  Σ meta.added_latency_ms
  (a deterministic tool saves at $0 of its own cost).
```

## Cost impact

**Estimate band** — `query: estimate-band` · modeled · `cage/estimate.py`

<!-- formula: estimate-band -->
```
band = median + IQR of measured totals over closed tasks matching the exact
  keys (scope / label / agent) — no similarity scoring, no ML. Below
  n = 5 matching tasks the command refuses. --record stamps
  est_tokens/est_usd/est_n + the token band bounds onto the open task row.
```

**Calibration hit-rate** — `query: calibration-hit-rate` · measured · `cage/calibration.py`

<!-- formula: calibration-hit-rate -->
```
over closed tasks with recorded estimates: ratio = actual_tokens / est_tokens
  (median + IQR), and hit-rate = share of actuals inside the est band recorded
  at estimate time. Open / zero-actual / band-less tasks are skipped with a
  visible count.
```

This measured frequency *is* the estimator's confidence — it never
self-reports one.

**Compare delta** — `query: compare-delta` · groups measured, delta estimated · `cage/compare.py`

<!-- formula: compare-delta -->
```
group closed tasks by stack signature (joined receipt tools; task-id join,
  session-window fallback); per group report n · median · IQR of measured
  tokens + USD; delta = median(stack) − median(agent-only), same non-stack
  keys. Groups below n = 5 render a refusal, never a number.
```

**Trend buckets** — `query: trend` · per-bucket receipt methods · `cage/trend.py`

<!-- formula: trend -->
```
group receipts/calls by week or month; show saved $ and saved hours per bucket.
```

Saved $ and saved hours per ISO week or month; the derived-attention series
renders as its own section, never blended.

**Budget check** — `query: budget` · measured · `cage/budget.py`

<!-- formula: budget -->
```
Σ call_usd over the window vs [budgets] session_usd / daily_usd; on_exceed = warn|block.
```

Money-native: budget always shows dollars regardless of `[display] usd`.

**Verdict** — `query: verdict-composition` · pure composer · `cage/verdict.py`

<!-- formula: verdict-composition -->
```
a pure composer — no new statistics: net = roi.saved − roi.own_cost over the
  window (verdict = its sign); marginal saving from attribution's latest task;
  direction from trend; drift from regression; redo-rate from quality;
  break-even = net / receipts. ≈$/mo scales net by the receipts' own time-span
  (≥7 days, no clock). Missing input ⇒ INSUFFICIENT DATA, never an approximation.
```

Computes no new statistics — composes attribution, roi, trend, regression,
quality.

## Human axis

**Human cost** — `query: human-cost` · estimated · `cage/human.py`

<!-- formula: human-cost -->
```
usd = minutes / 60 × rate     (rate = $80/hr, source: policy)
  chain: explicit usd > per-receipt minutes > task-type table > global default
  confidence: measured 0.9 · estimated 0.7 · type-table 0.5 · default 0.3
```

Never `measured` without a real timesheet/quote.

**Attention minutes (passive)** — `query: attention-minutes` · estimated, "derived (turn-gaps, capped)" · `cage/attention.py`

<!-- formula: attention-minutes -->
```
minutes = Σ min(gap_ms, idle cap) / 60000    (cap = 10 min; policy
  [human] idle_cap_minutes wins, constants.IDLE_CAP_MINUTES is the fallback)
  gap_ms = wall-clock between the previous assistant turn's end and the human
  turn that led to the call — stamped at import only where the log carries
  per-turn timestamps (claude today; copilot/kiro lack the signal ⇒ no
  field, never fabricated). Read-time derive: changing the cap re-prices the
  backlog, the ledger is never rewritten. Attested minutes (`human-record`,
  `cage human outcome --minutes`) beat derived for a task — never summed;
  `cage insights calibration --human` measures the heuristic's derived/attested ratio.
```

Stamped at import only where logs carry per-turn timestamps; attested minutes
beat derived per task — never summed.

**Time saved** — `query: time-saved` · estimated · `cage/trend.py`

<!-- formula: time-saved -->
```
saved_minutes = human_minutes − agent_active_minutes
  (negative when the agent took longer than a person would have — honest).
```

## Fleet

**Study pairing** — `query: study-pairing` · delta estimated · `cage/study.py`

<!-- formula: study-pairing -->
```
phases are recorded markers (`cage study start/stop`), resolved per machine
  against that machine's own clock; the sample unit is the machine-day.
  paired delta = median over machines of (phase-B median daily − phase-A
  median daily), controlling between-machine variance; below
  5 machines with both phases the delta refuses. Coverage
  (days + gaps) always prints first. Machine ids are opaque random tokens —
  never a hostname.
```

## Meta

**Confidence ladder** — `query: confidence` · `cage/constants.py`, `[human.confidence]` wins

<!-- formula: confidence -->
```
measured 0.9 · estimated 0.7 · type-table 0.5 · default 0.3
  policy [human.confidence] wins; constants.DEFAULT_CONFIDENCE is the fallback.
```

Orthogonal to method: low confidence flags a round guess, not a wrong tag.

**Method ranking** — `query: method-tags`

<!-- formula: method-tags -->
```
trust rank: measured 2 · modeled 1 · estimated 0
  measured = an actual invoice/run · modeled = reconstructed · estimated = a guess.
```

A projection never renders as `measured` — the one law every formula above
obeys.

---

*Gates (`MIN_COMPARE_N`, `MIN_ESTIMATE_N`, `CHARS_PER_TOKEN`) are constants,
not policy — a threshold you could lower is a refusal you could silence.
Economics (rates, prices, caps, confidence) are policy — see
[pricing.md](pricing.md) and your `policy.toml`.*
