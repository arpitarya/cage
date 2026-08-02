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

- [copilot-credits.proposal.md](copilot-credits.proposal.md) — **COPILOT-CREDITS**
  design spec (compare verdict C accepted 2026-08-02): capture recorded credits,
  copilot USD by ladder (credits×rate → token×table → UNPRICED), worked CLI outputs
  inside. **Picked up 2026-08-02** — [handoff](../copilot-credits.handoff.md) +
  [prompt](../copilot-credits.prompt.md) (Opus).
- [agent-vs-human-v2.md](agent-vs-human-v2.md) — per-commit rebuild: tokens/commit ·
  authorship (mostly built) · suggested-vs-accepted (counts) · time (attestation only).

- [net-positive-evidence-run.md](net-positive-evidence-run.md) — NET-1 protocol:
  5 closed tasks per arm, outcomes pre-committed. Arpit's hands, no code.
- [dogfood-report.md](dogfood-report.md) — "Measured on itself" README section from the
  real ledger; refreshed per release via checklist line.
- [tool-integration-contract.md](tool-integration-contract.md) — the paved road:
  interceptor template · `cage data meter <tool>` · per-tool detection registry.
  **fux is the second tool**; ships only when two tools use it.
- [larger-lab-corpus.md](larger-lab-corpus.md) — tinyshop (~43 KB) may understate
  graphify; trigger: NET-1 still net-negative at n=5.
- [policysync-synthetic-bundle.md](policysync-synthetic-bundle.md) — sync tests own a
  fake bundle; trigger: a **third** table removal (guard shipped 2026-08-01).

## Graduated (implemented → archived)

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
