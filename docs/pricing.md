# Pricing — how a call prices, and why $0 is never silent

Design of record for cage's pricing surface (plan §3.3; shipped v0.19). The rule
underneath everything: **the ledger stores counts, never conclusions** — every
dollar figure is recomputed at derive time from `tokens × policy`, so fixing the
price table re-prices all history retroactively without rewriting a row.

## How a call prices

`report`/`budget` (and every cost view) recompute each call via `prices.call_usd`:
tokens × the `[prices.<provider>."<model>"]` row in policy, falling back to the
stored `est_cost_usd` only when the model is unpriced (so a self-costing provider
cage can't tokenize keeps its own figure). A call prices only if `(provider,
model)` resolves in the table; `policy.price_match` resolves **exact → alias →
family** over *normalized* ids, and the match kind is part of the method law:

- **exact** — the id is a table row, verbatim.
- **alias** — an explicit `[alias]` route (see the router workflow below); renders
  as an `≈ priced by alias` footnote, never `exact`.
- **family** — normalized-id match: known router prefixes strip (`copilot/` — a
  closed list; an unknown router stays UNPRICED), `.` folds to `-`
  (`claude-sonnet-4.6` matches the `claude-sonnet-4-6` row), and trailing effort
  tiers (`low|medium|high|max`) drop — both vendors bill every tier at the same
  per-token rate (verified 2026-07-11), so tiers price at the base row with a
  family footnote, never `exact`.
- **none** — UNPRICED. A dangling alias is `none` too: a router is never silently
  defaulted, because a wrong number is worse than none.

## The unpriced workflow

A call whose model has no row bills **$0 and says so**: `report`, the bare-`cage`
overview, `compare`, and `study report` print
`⚠ N calls (X tokens) UNPRICED — totals understated; run 'cage prices unpriced'`
whenever `none`-match calls exist, so an analyst can't publish an understated
total without seeing the gap. The fix is a paste, not a hunt (real field example —
the VS Code Copilot extension stamps dotted, route-prefixed model ids and an
empty-provider router):

```
$ cage prices unpriced
  —/copilot/auto   38 calls   412,000 tokens
    fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly
$ cage prices alias - copilot/auto --to anthropic/claude-sonnet-4-6
  ✔ —/copilot/auto → anthropic/claude-sonnet-4-6 — .cage/policy.toml
    renders as an alias footnote (approximate routing), never exact.
    derived views re-price immediately — the ledger is never rewritten.
$ cage prices set anthropic claude-sonnet-5 --input 2 --output 10 --cache-read 0.20
  ✔ [prices.anthropic."claude-sonnet-5"] updated — derived views re-price immediately
```

`cage prices list` shows every visible row with bundled-vs-project origin and
which wins. All writes are text surgery on the project `policy.toml` (in-place
value edits marked `# cage:custom`, or a deterministic cage-managed block — never
a whole-file rewrite; every mutation re-parses before an atomic replace). The
bundled `data/policy.toml` is read-only at runtime. `policy.load` merges
`prices`/`credits`/`alias` two levels deep (per provider *and* per model), so a
partial project table never wipes bundled siblings.

## Policy versioning and `cage prices sync`

The bundled table carries `[meta] prices_version` / `prices_date` /
`cage_version`, with source URLs cited row by row. `cage init` copies (and a
first `prices set` stamps) it into the project policy. When a newer cage ships
newer rates, `cage doctor` and `cage prices list` print one recommendation line —
`bundled prices are newer — run 'cage prices sync'` — and **never auto-apply**.
`sync` diffs project vs bundle (dry-run; `--update --yes <prov>/<model>` applies
per confirmed row), preserves customized rows by construction, and requires
per-row confirmation for unmarked drift (cage can't reconstruct which old bundle
a row came from — honest over clever). cage itself never fetches a price: no
network on any cage code path; the research step is build-time/user work.

## Pricing freshness — the per-commit note (v0.24)

cage never fetches a rate, so "are my prices current?" is answered from **local
evidence only** — three signals, one implementation
([cage/freshness.py](../cage/freshness.py)), three surfaces:

1. **sync drift** — the project `[meta]` is older than the installed bundle's →
   the `cage prices sync` recommendation above, verbatim.
2. **bundle age** — the bundle's own `[meta] prices_date` is more than
   `stale_days` old → `bundled prices are N days old — check for a newer cage
   release`. A project faithfully synced to a six-month-old bundle is
   confidently stale; this signal catches that. Threshold: policy `[prices]
   stale_days` (the `constants.PRICES_STALE_DAYS` fallback, 45); **`stale_days
   = 0` disables the age signal** — the documented opt-out.
3. **UNPRICED presence** — calls or call-less token receipts billing $0 → the
   existing runnable fix hints, byte-for-byte.

Surfaces: the **git post-commit hook** prints the actionable lines
(`cage:`-prefixed, print-only, fail-open, exit 0, silent when clean — never
gates a commit); **`cage doctor`** always shows the age check (`prices-age`,
beside `prices-meta` and `pricing`); the **`cage report` footer** appends
actionable lines only (UNPRICED already renders natively there; never in
`--csv`). Clock law: the report footer is a derived view, so its age math
anchors on the **newest ledger `ts`** (data-relative — same ledger + policy ⇒
byte-identical output; an empty ledger has no anchor, so the report stays
silent and doctor carries the age); the hook and doctor are clock-allowed
events and use today. `cage query prices-freshness` explains with live values.

Maintainer side: a weekly scheduled workflow
(`.github/workflows/prices-freshness-nag.yml`) reads the bundled `prices_date`
and, past `stale_days`, upserts one pinned issue asking a human to re-verify
the cited sources — it never fetches or parses a vendor page, and the publish
workflow is untouched.

## Fleet repricing

Because pricing is derive-time, imported fleet bundles (`cage export --study` →
`cage import bundle*.zip`) reprice under the *analyst's* policy: fix the table
once on the analysis machine and every historical row — including rows captured
on machines that never had the fix — costs out correctly. Self-costed rows and
receipts keep their stored figures (they are invoices, not reconstructions).

## The Copilot approximation

Copilot-served Claude ids (`copilot/claude-opus-4.6`) need no fix at all: family
matching normalizes the route prefix, `.`↔`-` punctuation, and effort-tier
suffixes, so they price at the Anthropic rows with a footnote — which is also
GitHub's own AI-Credits metering basis since June 2026. Only the bare router
`copilot/auto` stays loudly unpriced until *you* route it with an explicit alias:
a router priced silently is a wrong number. (The bundle ships a commented-out
alias example, never an active one.)

## Tool receipts — the pricing ladder (v0.23)

A savings receipt in `unit="tokens"` normally prices at its **linked call's**
model. But a shim that saves tokens for *future* calls — graphify's interceptor,
fux — files a receipt with a `task` and **no call id**: there is no model on the
row, so pre-0.23 it rendered $0 silently. Call-less token receipts now resolve
a pricing model at derive time via a deterministic ladder (`receiptprice.py`,
one implementation for roi / attrib / verdict / report):

1. **`price_at`** — explicit routing, written by the managed verb:

   ```
   $ cage prices route-tool graphify --to anthropic/claude-sonnet-4-6
     ✔ [tools.graphify] written to the cage-managed block — .cage/policy.toml
   $ cage prices route-tool graphify --remove     # idempotent delete
   ```

   (`[tools.graphify] price_at = "anthropic/claude-sonnet-4-6"` in the project
   policy — a hand-added table outside the managed block is honored and, on the
   next `route-tool`, edited in place with a `# cage:custom` mark, exactly like
   `prices set`.) Validated against `policy.price_match` at use time. A dangling
   route (no price row resolves) prices **nothing** and never falls through to
   rung 2 — the same rule as a dangling alias — and is flagged in `cage prices
   list` and `cage doctor`; unlike `alias`, `route-tool` *writes* a dangling
   target with a warning, so set-route-then-add-price works.
2. **task model** — the dominant model of the calls joined to the receipt's
   task (task-id calls plus session-window adoptions, the `taskgroup` join):
   max summed `tokens_in`; ties break by call count, then lexicographic
   `provider/model` — a total order, so the winner never depends on row order.
3. **refusal** — UNPRICED, loudly: roi and report print the ⚠ headline plus a
   **runnable** fix per affected tool —
   `run: cage prices route-tool <tool> --to <provider>/<model>  (or run in a
   metered session)` — with the real tool name substituted. A wrong number is
   worse than none.

The resolved USD keeps the receipt's own `method` (`modeled` stays `modeled`,
never `measured`); the rung is footnoted in text views (`≈ graphify priced at
task model (anthropic/…)`) and is a `priced_via` column in `roi`/`attrib`
CSV. Receipts **with** a resolvable call id never enter the ladder — their
path is byte-identical to before. Derive-time only, like every cage price:
`route-tool` today re-prices history without touching a ledger row. Routes are
user intent — the bundled policy ships none, and `prices sync` never touches
them.

## Credits vs prices — two layers, never mixed

`[prices]` is dollars per token — the ledger's economics. `[credits.<provider>."<model>"]
per_mtok` is a *separate* multiplier for provider AI-credit accounting
(`cage limits`), token-based providers only, **exact model-id match** (no family
fallback — a borrowed estimate is a different wrong number), **off by default**
(no active rows ship). An unknown multiplier ⇒ no number; Kiro/Copilot credits
are never derived from tokens (units-of-work ≠ token multiples). Every credit
figure is `estimated`, names its source, and ends with a "reconcile against your
provider dashboard" note.

---

Ask the tool itself: `cage query prices-cli` · `cage query unpriced` ·
`cage query pricing-match` · `cage query repricing` · `cage query receipt-pricing` ·
`cage query effort-tiers` · `cage query policy-versioning` ·
`cage query prices-freshness` · `cage query copilot-pricing` — all answered
deterministically with live values.
