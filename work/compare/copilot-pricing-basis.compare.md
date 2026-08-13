---
doc: compare — pricing basis for Copilot usage
status: DECIDED — verdict C accepted by Arpit 2026-08-02, IMPLEMENTED v0.44; **reopened and re-decided 2026-08-11 for the multi-model shutdown (REV-CREDITS defect 2), IMPLEMENTED same day** — living spec: ../FORMULAS.md §1.1a · ../PLAN.md §3.1 · `cage query copilot-credits`; the proposal it graduated through is archived at ../archive/v0.44-copilot-credits.proposal.md
raised: 2026-08-02 (fork surfaced by COPILOT-CREDITS — the store persists the billed credits cage drops)
evidence: ../research/copilot-vscode-token-sources.md
---

# Compare — Copilot cost: credits vs tokens vs both

**Proposed verdict up front: C — both, each axis with exactly ONE job, joined by a
ladder, never blended in a cell.** Credits answer *"what was I billed?"* (recorded
fact); tokens answer *"what would this cost at list rates?"* (the uniform
counterfactual and the savings denominator). §Verdict has the precise rule.

## The fork

Cage prices copilot rows by `tokens × price-table` (family-matched to provider rows).
The [research doc](../research/copilot-vscode-token-sources.md) found the chatSessions
store persists **`copilotCredits`/`sessionCopilotCredits` per request** — the billed
figure GitHub itself computed — and cage drops it. So: keep tokens, switch to credits,
or carry both?

**The grounding fact that reshapes the debate** (already cited in
`data/prices.toml`, retrieved 2026-07-11): since **2026-06-01 Copilot bills
usage-based AI Credits "calculated based on token consumption, including input,
output, and cached tokens, using the listed API rates for each model"**
([github.blog](https://github.blog/news-insights/company-news/github-copilot-is-moving-to-usage-based-billing/)).
Credits are no longer a flat per-request quota — they are GitHub's *own*
tokens-×-rates computation, done with information cage can't see (the model `auto`
actually routed to, GitHub's current rates).

## The debate — the real case for each

### A — credits as the basis

- **The recorded credit is the closest thing to an invoice cage will ever get from
  Copilot.** GitHub already resolved auto-routing, cache discounts, and current rates
  into it. It prices `copilot/auto` **exactly** — the 24/60-calls/975k-tokens-at-$0
  finding ([regression 2026-07-22](../regression/), [research §4.1](../research/copilot-vscode-token-sources.md))
  dies without a single price-table row.
- No rate-drift risk: when GitHub changes rates, the recorded credit is already right;
  cage's price table is always chasing.
- *The honest weakness:* a credit **count** is recorded fact, but credit→**USD** needs
  the user's plan rate (included allowance ⇒ marginal $0; overage rate per plan) — a
  policy input, so the dollar figure is still `modeled`. Coverage is partial: legacy
  ledger rows carry no credits, CLI rows only per-shutdown `premium` deltas, the
  sidecar (`totalNanoAiu`) is debug-gated. And credits are copilot-only — attribution,
  budget, and the whole savings axis are token-denominated across three agents;
  credits can't feed any of it.

### B — tokens as the basis (status quo)

- **Uniform across claude · copilot · kiro** — one denominator for report totals,
  budget, attrib, roi, and the gross-savings axis (`saved` is tokens → USD via model
  price, FORMULAS §2.x). A copilot-only special case fragments every consumer.
- Deterministic from ledger + policy alone; zero coverage gap for concrete model ids
  (`copilot/claude-*` family-prices at the anthropic rows — `data/prices.toml`'s
  stated design).
- Since 2026-06 the billing IS tokens×rates, so B *approximates the invoice* well —
  for rows with a real model id.
- *The honest weakness:* `copilot/auto` stays loudly UNPRICED by design ("a router
  priced silently is a wrong number"), and that is now the **majority** of real
  vscode traffic. B also silently diverges whenever cage's table lags GitHub's rates.

### C — both, one job each

- Cage's numbers discipline already IS this shape: three layers never mixed
  (contract/policy/constants), the receiptprice **ladder** (best signal first, loudly
  UNPRICED last), kiro-CLI rows already recorded as **credits, not tokens** with a
  separate `[credits]` axis, and `premium` already stamped on copilot-CLI rows.
  `prices.toml`'s own rule — "never blur a credit multiplier into a per-token price"
  — is a *both-axes* rule, not a pick-one rule.
- Method law fits perfectly: credit count = recorded fact on the row; credit-USD =
  `modeled` (count × configured plan rate); token-USD = `modeled`/`estimated`
  counterfactual. Tag every cell, never average the axes.
- *The honest weakness (tenth-man on "both is a cop-out"):* two numbers per row can
  read as indecision, and something must still drive budget/verdict/report totals —
  "both" only survives if that choice is a **rule**, not a per-view mood. The rule is
  in the verdict.

## Matrix

| criterion (what actually matters) | A credits | B tokens | C both |
|---|---|---|---|
| matches the real bill (incl. `copilot/auto`) | ✅ exact count | ❌ auto UNPRICED | ✅ via ladder |
| uniform denominator across 3 agents (attrib/savings/budget) | ❌ copilot-only | ✅ | ✅ tokens keep that job |
| method-honest without new fiction | ⚠️ credit-USD still modeled | ⚠️ estimates read as costs | ✅ every cell tagged |
| covers legacy rows / partial capture | ❌ | ✅ | ✅ falls through ladder |
| rate-drift immunity | ✅ | ❌ | ✅ where credits exist |
| implementation cost | medium (capture + rate config) | zero | medium (same as A + one ladder rung) |
| consistency with existing design (kiro credits · `premium` · receiptprice ladder · `[credits]` axis) | partial | partial | ✅ it *is* the existing shape |

## Proposed verdict — C, with the rule that makes "both" a decision

1. **Capture credits** as additive optional fields on copilot rows (COPILOT-CREDITS):
   vscode per-request `copilotCredits`; CLI keeps the `premium` shutdown delta;
   sidecar `totalNanoAiu` when present. Recorded count, never derived from tokens
   (the `prices.toml` rule holds in both directions).
2. **Tokens keep their jobs unchanged:** the cross-agent denominator for report
   volume, attribution, budget, and the entire savings axis. No consumer re-plumbed.
3. **The copilot USD cell resolves by ladder**, footnoted like `priced_via`:
   recorded credits × configured plan rate (`[credits.copilot]`-style policy key,
   off by default — no rate ⇒ this rung is skipped, credits still *displayed* as a
   count) → token × price-table (family match) → loudly UNPRICED. One rung wins per
   row; the winning rung is named in text and CSV.
4. **Never blended:** no cell ever sums a credit-priced and token-priced figure
   without the mixed-basis count footnoted (same discipline as the UNPRICED ⚠).

## Reopen triggers (numbered, falsifiable)

- **R1:** GitHub changes the billing model again (a new github.blog/docs source
  contradicting the 2026-06-01 basis) → re-run this compare with the new facts.
- **R2:** credit coverage on real ledgers reaches ≥95% of copilot rows for 2
  consecutive regression reports → revisit whether the token rung still earns its
  place *for copilot USD* (tokens keep the denominator job regardless).
- **R3:** the recorded credit fields prove unstable across two VS Code releases
  (field renamed/regressed, tracked in a dated research doc) → demote rung 1 to
  debug-gated and re-verdict.

**Deliberately not taken:** deriving credits from tokens when unrecorded (forbidden
by the standing `prices.toml` rule — absence stays absence); nano-AIU→USD conversion
without a published rate card (would be invented precision).

---

## Reopened 2026-08-11 — the multi-model shutdown (REV-CREDITS defect 2) · **DECIDED**

**Verdict: one basis per shutdown, carried by a recorded link.** Implemented same day.

**The fork.** GitHub computes `totalPremiumRequests` over **every** model in a
`session.shutdown`. Cage stamps that delta on one carrier row (largest token mover), so a
multi-model shutdown priced the carrier by credits — GitHub's figure for the *whole*
shutdown — while its siblings fell through to tokens×table. Rule 4 above says a cell
never blends the axes; this blended them **inside one shutdown**, and it double-billed:
the same spend counted once at GitHub's rate and again at cage's list rates.

| # | option | verdict |
|---|---|---|
| **1** | split the credit **pro-rata by token share** across the shutdown's rows | ❌ **rejected** — it derives per-row credits *from tokens*, which the standing `prices.toml` rule forbids in **both** directions. It would also invent a per-model precision GitHub never published |
| **2** | **one basis per shutdown** — the group prices once, on the carrier | ✅ **taken** |
| **3** | leave it; footnote the double count | ❌ a footnote does not stop a wrong total being summed |

**How 2 is made real without a derived number.** Every non-carrier row of a
credit-bearing shutdown is stamped `billed_with = <carrier id>` — an additive-optional
call field that is a **recorded structural fact** (these rows came out of one shutdown,
whose billing the provider computed jointly), not a computation. `prices.call_usd_match`
reads it as **rung 0**: the row prices at `$0.00` on the *credits* basis, with the
carrier's id as the matched key — *priced, elsewhere, by name*, which is neither a
fabricated `$0` nor UNPRICED.

Three properties that made it the cheap option:

- It reports the **same `credits` match kind** as rung 1, so every consumer already
  excluding a credits-priced row from token-derived reasoning (report's `cache_usd`
  split, the mixed-basis footnote, `method_for`) inherits it with **no per-view fork**.
- The suppression is **conditional on a rate existing**. With none, the carrier itself
  drops to rung 2, so its siblings must too — otherwise the shutdown would price at one
  model's tokens instead of all of them.
- A recorded `0.0` credit still covers the group (`is not None`, never truthiness): the
  shutdown *was* billed as a group, and it billed zero.

**The limit, stated not hidden — this fix is FORWARD-ONLY.** The ledger is append-only
and rows are never rewritten, so multi-model shutdown rows captured before this change
carry no link and still price on two bases. A re-import cannot heal them: `append_new`
dedupes on the deterministic id. Carried in OPEN-WORK as **CREDITS-LEGACY-SPLIT**.

### Reopen triggers for this half

- **R4:** a provider other than copilot starts reporting a group-level billed figure →
  `billed_with` is already agent-neutral, but re-check that "the carrier is the largest
  token mover" is still the right pick for that store's shape.
- **R5:** GitHub begins publishing `totalPremiumRequests` **per model** → rung 0 is no
  longer needed for that store; each row carries its own credit and prices on rung 1.
  Reopen with a store probe, not an argument.

Graduates to: the COPILOT-CREDITS plan entry (capture) + a pricing-ladder line in
FORMULAS on ship; ADR if the ladder rule proves load-bearing.
