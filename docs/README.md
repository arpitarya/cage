# Cage docs — start here

**2026-07-25: doc sweep.** Cage is being rebuilt hookless (pull-only capture, MCP
read surface). Most operational/subsystem docs were removed with the hook machinery
and rendered assets — they described the pre-removal world and will be rebuilt on
the new base. What remains here is **current spec**; everything in
[`archive/`](archive/README.md) is **history** and must never be cited as current
spec.

## Current spec

- [PLAN.md](PLAN.md) — the design of record: substrate contract, attribution
  engine, every plan-§ referenced from code and CLAUDE.md.
- **[OPEN-WORK.md](OPEN-WORK.md) — the ONE plan of pending work, and ONLY that.**
  A completed item is **removed, never left ticked** — legal only once its outcome is
  in [IMPLEMENTATION.md](IMPLEMENTATION.md) and any evidence is published to
  [regression/](regression/), with residual limits carried forward as their own
  items. So its length is a truthful measure of what is left. It also carries the
  durable rules promoted out of the archived cycle plans, including the **ZERO dummy
  data** law.

## Active work

**None.** `docs/` root carries no handoff/prompt pairs — a pair is created only when an
item in [OPEN-WORK.md](OPEN-WORK.md) is picked up, and archived the moment its work is
built and green. Everything from the v0.36 cycle is in
[archive/](archive/README.md).

What remains is not agent work: **NET-1** (a lab session, Arpit's hands), **HR1** (a
proposal doc before any rebuild), and **H**, the release — blocked on the standing
no-commit directive.

## The lab manual

- **[cage-lab/](cage-lab/README.md) — how to build `../cage-lab` from scratch.** The
  lab is a **disposable** sibling repo; this directory is what recreates it, versioned
  in cage alongside the tool it tests. Setup (`.venv` + explicit PATH · the two
  workspaces · tool-owned installers) · run protocol (manifest-before-first-call ·
  repeats where they buy something) · verification (per-agent bars · the three-way
  reconciliation · four verdicts) · publishing (three artifact types, never merged) ·
  the manual VS Code/IDE cells. **The lab is scaffolding; the evidence in
  [regression/](regression/) is permanent.**

## Living process docs (always current)

The maintained doc set, governed by the *Documentation discipline* section of
[`../CLAUDE.md`](../CLAUDE.md). Freshness is tracked in
[DOC-REGISTRY.md](DOC-REGISTRY.md).

- [doc-size-discipline.md](doc-size-discipline.md) — ⏳ **TRIAL to 2026-09-01**: the
  four doc-size rules (lead with the answer · one audience · evidence elsewhere ·
  hard budget), the fix procedure, and the retain/remove criteria.
- [GLOSSARY.md](GLOSSARY.md) — every recurring term, defined once against the code.
- [FORMULAS.md](FORMULAS.md) — every computed number: formula · code home ·
  method tag · the knobs that move it.
- [WORKLOG.md](WORKLOG.md) — the running per-session handoff (append every
  exchange, Claude Code and Cowork/chat alike).
- [INTERVIEW.md](INTERVIEW.md) — the **exit interview**: notes from the outgoing
  maintainer-model to every future one. Read it after CLAUDE.md.
- [DOC-REGISTRY.md](DOC-REGISTRY.md) — the doc freshness tracker (triggers +
  last-verified).
- [architecture-flow.mermaid](architecture-flow.mermaid) — the one-way data flow as
  a diagram (also linked from the README).
- [example/](example/) — copy-from contracts: cli · debug · setup · toml-config.
- [IMPLEMENTATION.md](IMPLEMENTATION.md) — the build log.

## Standing records

- [adr/](adr/) — architecture decision records (the durable *why*; each ends with a
  veto condition). Author new ones from [adr/TEMPLATE.md](adr/TEMPLATE.md).
- [compare/](compare/) — decision records for forks (debate + matrix + verdict +
  reopen-trigger); [proposals/](proposals/) — parked ideas (`status: proposed`).
- [regression/](regression/) — dated cage-lab capture/regression reports (data, not
  spec).
- [archive/README.md](archive/README.md) — every shipped handoff/prompt/build-prompt
  and superseded draft. History, not spec.
