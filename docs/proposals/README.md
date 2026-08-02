# docs/proposals — parked ideas

An idea worth keeping but **not being built now** gets a *proposal doc* here — same
rigor as a compare doc (context, sketch, grounded references), with `status:
proposed` in its frontmatter.

Proposals are **parked, not lost**. When one is picked up it graduates into a
[compare doc](../compare/) (if it's a fork) or a plan entry (if the path is clear),
and from there to an [ADR](../adr/TEMPLATE.md) when it ships.

This is the home for the `# v2:` idea that would otherwise rot as a half-built
comment in the code — write the proposal, keep the code clean.

Distinct from [compare/](../compare/): a proposal is an idea with no live
competitor yet; a compare doc weighs two+ options that are both on the table now.

## The format (audited 2026-08-03 — all 11 conform)

Every file in this directory must satisfy all four. They are checkable, so check them
rather than eyeballing:

| rule | what it means |
|---|---|
| **Name** | `<topic>.proposal.md` — never a bare `<topic>.md`, and the topic is **the idea, not the file it patches or the release that raised it**. `claude-md-hr1` and `v044-review-hardening` were both wrong this way (fixed 2026-08-03); version prefixes belong to `archive/` alone |
| **Frontmatter** | `doc:` (one line, takeaway first) · `status: proposed` · `raised:` · `owner:` or `trigger:` |
| **`status:`** | the literal word `proposed` — not "held for review", not "AWAITING REVIEW". A held steering edit says so in a `held:` key, so the status vocabulary stays sortable |
| **Paragraphs** | ≤4 lines (CLAUDE.md *Documentation style*). Short points, one idea each, takeaway first; tables for comparisons |

Two more that bite in practice:

- **Evidence must be reachable.** Link `docs/regression/` or `docs/research/`, never a
  gitignored scratch path — a proof a teammate cannot open is not a proof.
- **Implemented phases are REMOVED, not struck through.** Same law as OPEN-WORK: this
  folder must read as *ideas not yet built*. The record goes to `IMPLEMENTATION.md`,
  and any divergence the build chose is stated there — the code wins over the proposal.



## Parked

**Reviewed 2026-08-01** — every entry checked against the code.

Active (awaiting Arpit's accept or a trigger):

- [steering-edits-pending.proposal.md](steering-edits-pending.proposal.md) — **the
  four CLAUDE.md edits, in one sitting.** Raised by four programs, merged 2026-08-03
  because they patch one file and need one decision. Head table carries a verdict box
  per edit; an applied section is deleted from the file, and the file goes when the
  table empties. Re-verified at HEAD: none applied.

  Its item **E** is the lesson worth keeping — both source proposals hardcoded a
  `just test` target (1354, 1391) and both fell *below* the file they patch (1401,
  suite 1423), so applying either would have regressed it. **A held patch decays against
  its target**; E is now a rule, not a number.

- [net-positive-evidence-run.proposal.md](net-positive-evidence-run.proposal.md) — NET-1 protocol:
  5 closed tasks per arm, outcomes pre-committed. Arpit's hands, no code.
- [tool-integration-contract.proposal.md](tool-integration-contract.proposal.md) — the paved road:
  interceptor template · `cage data meter <tool>` · per-tool detection registry.
  **fux is the second tool**; ships only when two tools use it.
- [larger-lab-corpus.proposal.md](larger-lab-corpus.proposal.md) — tinyshop (~43 KB) may understate
  graphify; trigger: NET-1 still net-negative at n=5.
- [policysync-synthetic-bundle.proposal.md](policysync-synthetic-bundle.proposal.md) — sync tests own a
  fake bundle; trigger: a **third** table removal (guard shipped 2026-08-01).
- [copilot-credits-integrity.proposal.md](copilot-credits-integrity.proposal.md) — **defect, not
  parked**: credit delta lost when the first-listed model idles; multi-model
  shutdowns double-count (credits + tokens); negative-delta clamp; compare's
  `measured` label. Same review.
- [review-hardening.proposal.md](review-hardening.proposal.md) — the rest of the review's
  confirmed findings, phased: dogfood **date bomb (~2026-10-02)** · `cage hook`
  exit-2 = BLOCK collision · honest-refusal fixes · wiring hygiene · durable joins.
- [chats-agent-authorship-column.proposal.md](chats-agent-authorship-column.proposal.md) — `agent%`
  per chat on `cage insights chats`: the v2 authorship counts joined by
  `(agent, session)` — pure ledger join, one new always-written `residual_lines`
  count, three standing guards answered. **Sequenced after
  timestamp-utc-normal-form**, which **landed 2026-08-02**, so it is unblocked.
  **Picked up 2026-08-02** — live pair
  [chats-author.handoff.md](../chats-author.handoff.md) ·
  [chats-author.prompt.md](../chats-author.prompt.md); entry stays put, per the
  lifecycle rule.

## Graduated (implemented → archived)

- **timestamp-utc-normal-form (REV-TS)** → **IMPLEMENTED** for v0.45.0 (unreleased)
  2026-08-02 (1401/0 ⇒ 1413/0). One UTC normal form (`YYYY-MM-DDTHH:MM:SSZ`,
  sub-seconds truncated) for every timestamp the authorship join compares; bounds
  normalize at `Window` construction, so a raw-bound window cannot be built.
  **The build falsified one of the proposal's three failure shapes** — git renders
  `%cI` as `…Z` at zero offset, never `+00:00`, so pure-UTC repos were correct all
  along, and that is exactly why the normal form is **seconds** rather than the
  milliseconds the sketch implied (milliseconds would have broken the working case).
  Frozen provenance rows are not repaired and the `_authorship` cursor is deliberately
  not invalidated. Living spec: [FORMULAS §2.14](../FORMULAS.md) ·
  [GLOSSARY](../GLOSSARY.md) *UTC normal form* · `cage query agent-authorship`.
  Evidence: [finding](../regression/2026-08-02-finding-commit-window-timestamp-skew.md).
  [archived proposal](../archive/v0.45-rev-ts.proposal.md) ·
  [handoff](../archive/v0.45-rev-ts.handoff.md) ·
  [prompt](../archive/v0.45-rev-ts.prompt.md).

- **dogfood-report** → **IMPLEMENTED** for v0.44 (unreleased) 2026-08-02 (1391/0 ⇒
  1401/0). `docs/dogfood/` home (dated snapshots + `latest.md` + append-only
  `README.md`, mirroring `regression/`), the version/date-free README pointer, and the
  60-day freshness guard (`tests/test_dogfood_freshness.py`, frontmatter only, no
  ledger). **One deviation from the proposal's own Steps §1:** `cage insights attrib`
  is not published — every task-tagged row in the real global ledger turned out to be
  the `cage demo` seed itself, so it was omitted with a note rather than shown as real
  data (surfaced mid-session, decided by Arpit). Living spec:
  `docs/dogfood/README.md` · `tests/test_dogfood_freshness.py`.
  [archived proposal](../archive/v0.44-dogfood-report.proposal.md) ·
  [handoff](../archive/v0.44-dogfood-report.handoff.md) ·
  [prompt](../archive/v0.44-dogfood-report.prompt.md).

- **copilot-credits** → **IMPLEMENTED** for v0.44 (unreleased) 2026-08-02 (1354/0 ⇒
  1391/0). Billed `credits` captured verbatim on both copilot surfaces; every copilot
  dollar resolves by ladder at the one pricing choke point, so `copilot/auto` prices
  exactly with no price-table row. **Three corrections the build made:** the policy key
  is `[billing.copilot]`, not `[credits.copilot]` (the latter is a *price* section, read
  from `prices.toml` alone — a rate filed there would have merged as absent); `credits`
  defaults to a `None` sentinel, not `0.0`, or a recorded zero would collapse into
  absence; and copilot-CLI stamps `credits` directly rather than the read side reusing
  `premium`, which is an int that floored every real fractional value to zero. Living
  spec: [FORMULAS.md §1.1a](../FORMULAS.md) · [PLAN.md §3.1](../PLAN.md) ·
  `cage query copilot-credits`. Evidence:
  [real-store probe](../research/2026-08-02-copilot-credit-fields-real-stores.md).
  [archived proposal](../archive/v0.44-copilot-credits.proposal.md) ·
  [handoff](../archive/v0.44-copilot-credits.handoff.md) ·
  [prompt](../archive/v0.44-copilot-credits.prompt.md).

- **agent-vs-human-v2** → **IMPLEMENTED** 2026-08-02, all four phases (1148/0 ⇒
  1354/0). `cage insights commits` / `commit <sha>` / `authorship summary` /
  `cage task time`. **One design correction the build made:** the proposal's three-way
  `agent / human / unknown` split became **four** — `unattributed` had to be separated
  from `human~`, because a single human bucket printed 76.6% on cage's own repo, 89% of
  it one commit of generated JSON. Living spec:
  [ADR 0008](../adr/0008-line-match-authorship-counts-persisted-content-transient.md) ·
  [FORMULAS.md §2.14](../FORMULAS.md) · [PLAN.md §3.5](../PLAN.md) ·
  `cage query agent-authorship`. Evidence:
  [dogfood](../regression/2026-08-02-p1-authorship-dogfood.md).
  [archived proposal](../archive/v0.43-agent-vs-human-v2.proposal.md) ·
  [handoff](../archive/v0.43-agent-vs-human-v2.handoff.md) ·
  [prompt](../archive/v0.43-agent-vs-human-v2.prompt.md).
- **chats-view** → **IMPLEMENTED** 2026-08-02, `cage insights chats` (1125/0 ⇒
  1148/0). One naming detail corrected: the assumed `manifest.read_imports` helper
  never existed — shipped as `manifest.read()` filtered to `kind=="import"`, same
  rows. Living spec: [cage/chats.py](../../cage/chats.py) + [FORMULAS.md
  §2.13](../FORMULAS.md) + `cage query chats-view`.
  [archived proposal](../archive/v0.42-chats-view.proposal.md) ·
  [handoff](../archive/v0.42-chats-view.handoff.md) ·
  [prompt](../archive/v0.42-chats-view.prompt.md).
- **agent-surface-layers** → **IMPLEMENTED** 2026-08-02, all four phases (1024/0 ⇒
  1125/0). L0 floor proof · L2 MCP · L1 hooks+steering · L3 skills, each opt-in and
  proven to move no number. Living spec: `CLAUDE.md`'s agent-surface bullets ·
  `cage query agent-layers` · [FORMULAS.md §2.12](../FORMULAS.md).
  [archived proposal](../archive/v0.41-agent-surface-layers.proposal.md) ·
  [handoff](../archive/v0.41-agent-surface.handoff.md) ·
  [prompt](../archive/v0.41-agent-surface.prompt.md).
  Carried forward: **[L1-FIELD]**, **[KIRO-MCP-FIELD]** in
  [OPEN-WORK](../OPEN-WORK.md).
- **cage-skills** → **superseded** 2026-08-02 by `agent-surface-layers` (its premise,
  "cage already ships a skill", was pre-hookless and false).
  [archived](../archive/v0.40-cage-skills.proposal.md)

A proposal that gets built is **archived, not left in this directory** — the folder must
read as *ideas not yet built*. See the lifecycle rule in [`../../CLAUDE.md`](../../CLAUDE.md).

- **insights-adoption** → built as v0.40's `cage insights adoption` (unreleased).
  [archived proposal](../archive/v0.40-insights-adoption.proposal.md) · living spec:
  [cage/adoption.py](../../cage/adoption.py) + [FORMULAS.md §2.12](../FORMULAS.md) +
  `cage query tool-adoption`. The proposal's "per agent × tool" headline was **half-
  derivable** and its "never invoked" claim needed **two strengths** — both corrections
  are recorded in the archive header.
- **windows-graphify-interceptor** → built as v0.38's `graphify.cmd` twin.
  [archived proposal](../archive/v0.38-windows-graphify-interceptor.proposal.md) ·
  living spec: [shim-contract.md](../shim-contract.md)
- **structural-debt** → mixed outcome, both parts resolved 2026-08-01: Part 1
  (`paths.py` splits on contact) **implemented** as a CLAUDE.md rule; Part 2 (a bare-`cage`
  state line) **declined** — bare `cage` already shows ledger state via `cmd_overview`,
  the premise behind Part 2 was false on every draft.
  [archived proposal](../archive/v0.39-structural-debt.proposal.md) ·
  living spec: `CLAUDE.md`'s `paths.py splits on contact` rule
- **claude-md-prices-file** → CLAUDE.md's flow diagram + Must-Know bullets now name
  `prices.toml` as the vendor rate card home. **Implemented** verbatim (CMD-SYNC).
  [archived proposal](../archive/v0.39-claude-md-prices-file.proposal.md) ·
  living spec: `CLAUDE.md` itself
- **claude-md-sources-authority** → **declined** (CMD-SYNC) — contradicted by
  `paths.resolve_log_sources`'s own docstring (an empty/absent `[sources]` is fully
  additive, byte-identical to the built-in registry); the proposal described a
  Directive A end-state that never shipped.
  [archived proposal](../archive/v0.39-claude-md-sources-authority.proposal.md) ·
  living spec: `cage/paths.py` `resolve_log_sources`
- **otel-genai-export** → built as `cage data export --otel` (OTEL). The pre-stable
  finding survived into the build: semconv version pinned + stamped, receipts/savings
  cage-namespaced, never an invented `gen_ai.*` name.
  [archived proposal](../archive/v0.39-otel-genai-export.proposal.md) ·
  living spec: `cage/otelout.py` · `cage query otel-export`
