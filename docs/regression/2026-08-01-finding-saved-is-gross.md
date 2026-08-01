# Finding — `saved` is GROSS: it excludes the cost of using the tool

**Severity:** **HIGH** — correctness of the *label* on cage's primary number, not a
capture gap · **Status:** ◻ **OPEN** · **Confidence in the supporting delta:**
**UNPROVEN — signal, not measurement (n = 1)** · **Surface:** `saved` on every savings
receipt, and the derived views that sum it (`report` · `insights attrib` · `roi` ·
`repoceiling`) · **From:** leg D's own paired data
([run report](2026-08-01-leg-d-run-report.md), cells D1 + D2), filed by the operator
during the run.

## The metric problem (this part does not depend on n)

```
saved = raw_alternative − actual
```

is a **per-query counterfactual**: *the files this answer cites would have cost 10,784
tokens; the answer cost 1,556.* It does **not** subtract the cost of **using** the tool —
the query turn itself, the tool round-trip, the hook's injected context, or any re-read
that a truncated answer provokes.

So cage can truthfully print **"27,658 tokens saved"** for a session that **cost more than
its unassisted twin**. Nothing is miscomputed. **The label is narrower than it reads**, and
a reader will take it as *"this got cheaper"*.

> This is the same class of quiet wrongness cage exists to catch in other tools — pointed
> at cage's own headline.

**The ceiling inherits it.** `repoceiling` reports "≈10,784 tokens per architecture
question avoided" with no netting of the query cost, so the day-one bound is gross too.

## The supporting observation — leg D's paired arms

Same agent (claude), same surface (VS Code), same workspace fixture, same six questions,
same model (`claude-haiku-4-5-20251001`). **The only variable was graphify.**

| | D1 OFF | D2 ON | delta |
|---|---|---|---|
| calls | 30 | 41 | **+11 (+37%)** |
| tokens in | 1,288,664 | 1,667,521 | **+378,857 (+29%)** |
| — cached read | 1,206,526 | 1,577,032 | +370,506 |
| — cache write | 81,872 | 90,119 | +8,247 |
| — fresh input | 266 | 370 | +104 |
| tokens out | 8,000 | 14,204 | **+6,204 (+78%)** |
| est. cost (per-session import row) | **$0.242783** | **$0.319212** | **+$0.076429 (+31%)** |

**Cage recorded 18,456 tokens SAVED for D2** (2 receipts × 9,228). **Both are true.** They
measure different things, and the gap between them is this finding.

### Correction to the cell record's cost row — stated, not silently applied

The cell record (`cage-lab/reports/cells/FINDING-gross-vs-net-savings.md`) estimated D1's
cost at **≈$0.28 by apportioning** the $0.35 that `workspace-off` reported across two
sessions, and derived **≈+14%**. **No apportionment is necessary:** `imports.jsonl`
carries a **per-session** row for D1 — `session 49e6b647…`, `rows_appended 30`,
`est_cost_usd 0.242783` — measured on exactly the 30 D1 rows, by the same code path that
produced D2's `0.319212`.

Using the measured per-session figures the delta is **+$0.076429 = +31%**, not +14%. The
correction makes the finding **stronger**, not weaker; the cell record is otherwise exact
(every token split above reconciles to the ledger row-for-row).

### Why the ON arm plausibly cost more

1. **A `graphify query` is itself an agent turn** — tool call → result → the model
   re-reads the conversation. At this context size every extra turn drags a large cached
   prefix. Two queries, eleven extra calls.
2. **The hook taxes every matching tool call.** graphify 0.9.30's PreToolUse fires on
   `Bash|Grep` and `Read|Glob` and injects context — paid whether or not graphify is
   ultimately used.
3. **The graph answer was truncated** ("~2,000-token budget"), so the agent may have read
   files *in addition to* querying — paying both costs.

These are **mechanisms consistent with the delta**, not measured contributions. None is
individually quantified here.

## Confidence — deliberately limited

- **n = 1.** The repeats = 3 rule exists for exactly this comparison; the manual cells ran
  once each. **This is a signal, not a measurement — UNPROVEN, not FAIL.**
- **~95% of input is cache reads**, ~10× cheaper than fresh input, so the raw token delta
  overstates the harm. **Dollars are the right lens**; there the gap is +31%.
- Agent non-determinism is unbounded across two separate sessions: some of +11 calls may
  be run-to-run variance rather than graphify.
- Three of the six questions are near-deterministic with near-zero output, so the delta
  concentrates in the graphify-sensitive ones — where it should be, and also where
  variance is largest.

**What would settle it:** the ON/OFF pair at **repeats = 3** on the graphify-sensitive
questions, reporting the delta as a **range**. That is the run this finding should
trigger.

## Proposal — cage can measure the cost side

The graphify query turn is in the transcript cage **already parses**, so netting is
computable, not hand-wavy.

| option | what it does | cost |
|---|---|---|
| **A — report both** *(recommended next)* | `gross saved` (today's number, unchanged) **and** `net saved` = gross − the token cost of the turns that produced the query. Keeps the existing figure stable and auditable; `method` stays `modeled`, but net is *more* modeled than gross and needs its **own** confidence | real work |
| **B — relabel only** *(minimum, do now)* | Footnote/rename to *"avoided read cost (**gross**) — excludes the cost of using the tool."* Stops the misreading even if netting is never built | cheap |
| **C — session-level A/B in `insights verdict`** | Report the measured ON/OFF delta where both arms exist, alongside the counterfactual | strongest; needs paired data most users won't have |

**Recommendation: B now, A next, C only if paired data becomes routine.**

## Why this is filed at HIGH with an UNPROVEN delta

The two halves have different strengths, and collapsing them would be dishonest in either
direction:

- **The label problem is structural and does not need n > 1.** `saved` excludes the tool's
  own cost by construction — that is readable in the formula, not inferred from the data.
- **The "graphify made this session more expensive" claim is n = 1** and stays UNPROVEN
  until the repeats = 3 run.

## Status history

- **2026-08-01** — filed OPEN from leg D's paired arms, by the operator, during the run.
  Published with the cost row corrected to the measured per-session figures (+31%, not
  +14%) and the correction stated explicitly.
