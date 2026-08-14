# ADR 0011 — Cage measures token and credit USAGE, never cost

- **Status:** Accepted (v0.51, unreleased) · supersedes the money half of [ADR 0010](0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md)
- **Date:** 2026-08-14
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

- Cage priced tokens because pricing was the point: the wedge was "prove what your
  tools save, in dollars". Every derived money view — `roi`, `budget`, `verdict`,
  `matrix`, `forecast`, `regression`, `recommend`, `prices` — existed to serve it.
- **The dollars were never measured.** They were a *reconstruction*: recorded tokens ×
  a rate card cage shipped, hand-researched at build time, that cage is forbidden to
  fetch and cannot check against any invoice. Two pricing ladders had grown to paper
  over the gaps (`creditprice` for copilot's router, `receiptprice` for call-less shim
  receipts), each with its own UNPRICED refusal.
- **The vendors moved away from tokens.** Since 2026-06-01 a Copilot credit *is*
  GitHub's own tokens×rates computation done with what cage cannot see; Kiro CLI
  records credits and **no tokens at all** (`total_tokens` NULL even with an explicit
  model). Cage's per-call price table was reconstructing a number the provider had
  already computed correctly and recorded.
- **The metric ledgers made the token side honest and exposed the contrast.**
  CLAUDE-DEDUP was measured at **2.00×** over a full matched window (43,973 `calls`
  rows vs 21,955 request rows, both spanning 2026-07-12 → 2026-08-14): the metric rows
  were right and `calls` was inflated. Once the *counts* were trustworthy, the dollars
  sitting on top of them were the only unverifiable figure left.
- [ADR 0010](0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md)'s
  `SPEND_CUTOVER` existed solely to protect six months of unrebuildable `calls` history
  behind a time boundary. That history is no longer wanted, so the boundary's only job
  was done.

## Decision

**Cage measures token and credit USAGE. It does not price, and it ships no rate card.**

- The money subsystem is **deleted**, not deprecated: fifteen modules (~2,457 lines),
  eleven CLI commands, four MCP read tools, the `--usd` view, `data/prices.toml`, and
  the `[prices]`/`[credits]`/`[billing]`/`[alias]` config sections.
- **The two units are tokens and credits, both recorded counts**, each read back
  verbatim from the store that wrote it. Nothing is converted between them, in either
  direction, ever.
- **`ledger.spend()` partitions by AGENT, not by time.** An agent with a metric ledger
  resolves from it for all of history; an agent without one resolves from `calls`.
  `SPEND_CUTOVER` is gone with nothing in its place.
- **Neither unit is universal, and each absence carries its own reason** (`units.py`):
  Claude Code records no credit unit on disk; kiro has no IDE token store on this
  install. Both render `—` with the sentence, **never a `0`**.
- **Credits are never summed or ranked across agents** (`units.summable`). A copilot
  credit is GitHub's tokens×rates figure; a kiro credit is an AWS credit. They share a
  column heading and nothing else.
- **Savings survive intact, in tokens, and stay GROSS.** `savings.GROSS_NOTE` outlived
  `netsaved.py` on purpose: netting was a dollar computation, the gross/net *distinction*
  is not. Cage reports gross and says so; it reports no net at all.
- Kiro credits are retagged **`measured`**: they were `estimated` only while standing in
  for dollars cage could not see.

## Consequences

- **`cage report`, `attrib`, `chats`, `compare`, `estimate`, `study` and the OTel export
  keep working, in tokens.** The views that answered *"is this worth the money"* are
  gone, and there is no token-denominated replacement for them — that is the point, not
  an omission to fill in later.
- **Pre-metrics `calls` history is no longer a spend source.** A claude row older than
  the metric routes resolves to nothing in every derived view. The rows are never
  deleted (append-only; `join_table` still resolves a receipt's `call` id against them),
  but they no longer produce a number. This is the decision, stated: the corrected metric
  rows are the basis, the inflated `calls` history is not.
- **Metric rows carry no `task`**, so the task-grouped views (`compare`/`estimate`/
  `calibration`) currently see zero for claude and copilot. Filed as **TASK-GRAIN-SPINE**
  in `work/OPEN-WORK.md` — a real gap, not a design choice.
- **`report --by route` collapses to `chat`** for spined agents: the metric stores carry
  no route field, and `_spend_row` defaults rather than inventing one.
- The append-only law is untouched: `est_cost_usd` remains a field on `calls` rows and a
  self-costing provider's own figure is still stored verbatim. Cage derives none and
  reads none.
- Three non-money things had to be **relocated rather than deleted**, because they lived
  inside money modules by accident: the outcome store (`quality.py` → `outcomes.py`,
  which is the write half of the only MCP mutation cage exposes), the gross caveat
  (`netsaved.py` → `savings.py`), and the comment-preserving TOML writer
  (`pricestoml.py` → `tomledit.py`, still needed by `cage policy sync` and
  `cage setup --python-launcher`).

## Alternatives rejected

- **Keep pricing behind a flag.** Rejected: an unverifiable number that renders only
  sometimes is still an unverifiable number, and the two ladders' complexity is paid in
  full whether or not the flag is set.
- **Re-denominate the deleted commands in tokens** (a token `budget`, a token `roi`).
  Rejected: `roi`/`verdict`/`recommend` are *return-on-investment* questions that need a
  common unit across tools, and tokens are not one — a `ms` receipt and a `tokens`
  receipt have no ratio. Deleted, not converted.
- **A literal pre-cutover row wipe.** Rejected on measurement: **every** copilot and kiro
  row in existence is pre-cutover, so a literal wipe zeroes both agents outright — and
  their stores persist, so re-import lands pre-cutover stamps and is excluded again,
  forever. Retiring the boundary achieves the goal and keeps the corrected history.
- **`spend()` reads metric ledgers only** (the tempting literal reading of "one basis").
  Rejected on measurement: it silently zeroes every library-, proxy- and custom-source
  row — **373 `codex` rows in one real ledger alone**, plus the AlphaForge/Anton
  integration's `agent="lib"` traffic. The `calls` fallback is scoped, not universal.
- **Pro-rata splitting of a group credit by token share.** Rejected under COPILOT-CREDITS
  and still rejected: it derives per-row credits from tokens, which this ADR forbids in
  both directions.
- **Emit an `ide` metric row from kiro's `tokens_generated.jsonl`** to give kiro a token
  spine. Rejected on the 2026-08-14 field probe: 28 rows totalling 1,576 in / **0 out**,
  model `"agent"` on every row, with a byte-identical 6-row block repeated. Not summable
  — a spine built on it would be fabricated, not measured.

## Reference

- **Field session 2026-08-14**, against real stores:
  [`work/research/2026-08-13-kiro-per-chat-usage-fetch-spec.md`](../../work/research/2026-08-13-kiro-per-chat-usage-fetch-spec.md).
- **The CLAUDE-DEDUP 2.00× measurement** and the metric-ledger correctness argument:
  [ADR 0010](0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md).
- **Why `saved` is gross** — the finding that produced `GROSS_NOTE`:
  [`work/regression/2026-08-01-finding-saved-is-gross.md`](../../work/regression/2026-08-01-finding-saved-is-gross.md).
- **The build's own spec:** `work/archive/v0.51-usage-only.{handoff,prompt}.md`.
- The precedent this follows is cage's own: the v0.36 Tier-1 human-axis amputation
  removed a whole valuation axis rather than keep a rate nobody could substantiate. This
  is the same judgement applied to the remaining one.

## Veto condition (when to revisit)

**1 · The falsifiable trigger — and it is a source, not an argument.**

Cage prices again **only when a provider exposes a per-request billed amount cage can
read from a store it already parses** — a recorded figure, in the row, like `credits` is
today. Not a rate card, not a published price page, not a user-configured rate: all
three are reconstructions, and reconstructions are what this ADR removed.

The number that reopens it: **a store carrying a per-request currency amount on ≥ 80% of
its rows**, measured on a real install and written up in `work/research/` before any code
moves. Below that threshold a currency column would be mostly `—`, which is worse than
no column.

Where it lands: a new **additive optional** field on the metric row (the `credits`
precedent, `schema.make_*`) and one rendered column. **Not** a price table, **not** a
rate config, **not** a `prices` command group — those are the parts this ADR closed, and
reopening them is a redesign, not a revisit.

**2 · Contingent vs. invariant.**

- **Contingent (auto-revisits on the evidence above):** whether cage displays a currency
  figure at all; kiro's absent token spine (`ledger.ABSENT_SPINES`) — a Kiro that ships
  `devdata.sqlite` flips it, and `cage doctor`'s three-way probe announces the flip;
  `parse_kiro_ide_metrics` is deliberately kept for that day.
- **Invariant (moves only by ratified reversal of this ADR):** cage **never computes a
  cost from a rate it cannot verify against an invoice**, and **never converts between
  units** — tokens↔credits↔currency, in any direction. These are product values, not
  volume-gated engineering calls. The cross-agent credit law is the same kind of
  statement: it is arithmetic that would invent a unit, and no measurement makes it valid.

**3 · Deliberately not taken.**

- **A user-supplied rate, applied locally and labelled `modeled`.** Considered and
  declined, not dogmatically rejected — it is honest in a way a shipped rate card is not,
  since the user is asserting their own contract. It is not taken now because it
  reintroduces the entire pricing surface (a ladder, a config section, an UNPRICED
  refusal, a per-view basis split) to serve a number only its author can check. Threshold
  to reconsider: **more than one user asks for it by name**, and it lands as a *display
  multiplier over an existing recorded count* — never as a table cage ships, and never as
  a second pricing basis a total can silently span.
- **A token-denominated `verdict`.** Left open. It needs a defensible way to compare
  savings across tools whose receipts use different units; until such a rule exists and
  is written down, no view should imply one.
