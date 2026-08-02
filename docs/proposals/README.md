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

Naming: `<topic>.proposal.md`. Written in short points, not walls of prose.

## Parked

**Reviewed 2026-08-01** — every entry checked against the code.

Active (awaiting Arpit's accept or a trigger):

- [net-positive-evidence-run.md](net-positive-evidence-run.md) — NET-1 protocol:
  5 closed tasks per arm, outcomes pre-committed. Arpit's hands, no code.
- [tool-integration-contract.md](tool-integration-contract.md) — the paved road:
  interceptor template · `cage data meter <tool>` · per-tool detection registry.
  **fux is the second tool**; ships only when two tools use it.
- [larger-lab-corpus.md](larger-lab-corpus.md) — tinyshop (~43 KB) may understate
  graphify; trigger: NET-1 still net-negative at n=5.
- [policysync-synthetic-bundle.md](policysync-synthetic-bundle.md) — sync tests own a
  fake bundle; trigger: a **third** table removal (guard shipped 2026-08-01).

## Graduated (implemented → archived)

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
