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

- [claude-md-sources-authority.md](claude-md-sources-authority.md) — proposed
  CLAUDE.md edits for the `[sources]` single-authority + Kiro-credits changes
  (capture-precision cycle). `status: proposed`.
- [claude-md-prices-file.md](claude-md-prices-file.md) — proposed CLAUDE.md edits
  for the model-prices split into `prices.toml` (prices-toml cycle). `status:
  proposed`.
- [larger-lab-corpus.md](larger-lab-corpus.md) — `tinyshop` (~43 KB) may understate
  graphify's value; leg D's +14% may partly measure the fixture. Trigger: NET-1.
- [policysync-synthetic-bundle.md](policysync-synthetic-bundle.md) — the sync tests
  borrow a live bundle table; own it instead. Trigger: a **third** table removal.
