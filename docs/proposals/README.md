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

**Reviewed 2026-08-01** — every entry checked against the code; the two parked
CLAUDE.md proposals were found **still needed** (CLAUDE.md verified stale on both).

Active (awaiting Arpit's accept or a trigger):

- [claude-md-prices-file.md](claude-md-prices-file.md) — parked CLAUDE.md edits for the
  `prices.toml` split. **Still needed** (flow diagram stale). → CMD-SYNC
- [claude-md-sources-authority.md](claude-md-sources-authority.md) — parked CLAUDE.md
  edits for Directive A. **Still needed** (extend/replace language stale). → CMD-SYNC
- [agent-vs-human-v2.md](agent-vs-human-v2.md) — per-commit rebuild: tokens/commit ·
  authorship (mostly built) · suggested-vs-accepted (counts) · time (attestation only).

- [net-positive-evidence-run.md](net-positive-evidence-run.md) — NET-1 protocol:
  5 closed tasks per arm, outcomes pre-committed. Arpit's hands, no code.
- [dogfood-report.md](dogfood-report.md) — "Measured on itself" README section from the
  real ledger; refreshed per release via checklist line.
- [insights-adoption.md](insights-adoption.md) — `cage insights adoption`: per-agent
  invoked/receipted/missed/never; counts only, usage rows stay unpriced.
- [structural-debt.md](structural-debt.md) — two rules: `paths.py` splits on contact
  (named seams, re-exports); a bare-`cage` landing screen. Low.
- [cage-skills.md](cage-skills.md) — six skills over existing surfaces; start with
  cage-analyst + cage-task-closer (feeds the starved closed-task pipeline).
- [otel-genai-export.md](otel-genai-export.md) — `cage data export --otel`, one-way
  like CSV; feeds Langfuse/Helicone rather than competing. **Not scheduled.** (Was
  `market-plays.md`; its two other plays were declined and removed 2026-08-01.)
- [tool-integration-contract.md](tool-integration-contract.md) — the paved road:
  interceptor template · `cage data meter <tool>` · per-tool detection registry.
  **fux is the second tool**; ships only when two tools use it.
- [larger-lab-corpus.md](larger-lab-corpus.md) — tinyshop (~43 KB) may understate
  graphify; trigger: NET-1 still net-negative at n=5.
- [policysync-synthetic-bundle.md](policysync-synthetic-bundle.md) — sync tests own a
  fake bundle; trigger: a **third** table removal (guard shipped 2026-08-01).

## Graduated (implemented → archived)

A proposal that gets built is **archived, not left in this directory** — the folder must
read as *ideas not yet built*. See the lifecycle rule in [`../../CLAUDE.md`](../../CLAUDE.md).

- **windows-graphify-interceptor** → built as v0.38's `graphify.cmd` twin.
  [archived proposal](../archive/v0.38-windows-graphify-interceptor.proposal.md) ·
  living spec: [shim-contract.md](../shim-contract.md)
