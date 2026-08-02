---
doc: compare — pricing basis for Copilot usage
status: DECIDED — verdict C accepted by Arpit 2026-08-02; spec: ../proposals/copilot-credits.proposal.md
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

Graduates to: the COPILOT-CREDITS plan entry (capture) + a pricing-ladder line in
FORMULAS on ship; ADR if the ladder rule proves load-bearing.
