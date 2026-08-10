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

- [agent-lane-sweep.handoff.md](agent-lane-sweep.handoff.md) +
  [agent-lane-sweep.prompt.md](agent-lane-sweep.prompt.md) — **the agent-lane sweep**:
  every buildable item left in [OPEN-WORK.md](OPEN-WORK.md), in seven independently-landable
  phases (release v0.48.0 · CIGF-HERMETIC · REV-HARDEN P3 · REV-HARDEN P4 ×2 ·
  HR-COPILOT-JOIN · EXPORT-SCOPE). All twelve REV-HARDEN items were **re-verified against
  the code 2026-08-10** — none already fixed, and the sources are wrong about their own
  premises in eight places, corrected inline. Model: **Opus**. Progress: **29%** — P0 was
  **already released** when the pair was picked up (STOP gate moot), P1 CIGF-HERMETIC
  landed 2026-08-11 with the real CI leg green **7/7 on a developer machine**.

- [steering-edits-pending.proposal.md](proposals/steering-edits-pending.proposal.md) —
  **STEERING-EDITS**: the four held CLAUDE.md edits (authorship bullet · copilot credit
  ladder · `FORMULAS.md` entry point · dogfood section), merged into one file 2026-08-03
  and re-verified at HEAD — **none applied**. One read, four verdicts; an applied section
  is deleted from the file.

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

- **[CLI.md](CLI.md) — every `cage` command in one place.** The 5 daily verbs, the 7
  groups, the 4 hidden plumbing commands and every flag, plus the removed-verb
  migration table and the surface's known gaps. **Test-gated**: `tests/test_cli_reference.py`
  checks it bidirectionally against `cli.build_parser()`, so a rename that misses this
  file turns the suite red rather than leaving a dead verb in prose.
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
- [dogfood/](dogfood/README.md) — cage's own ledger, published as dated snapshots
  (append-only, mirrors [regression/](regression/README.md)); linked from the README,
  version-free. Freshness guarded by `tests/test_dogfood_freshness.py` (60-day gate).

## Standing records

- [adr/](adr/) — architecture decision records (the durable *why*; each ends with a
  veto condition). Author new ones from [adr/TEMPLATE.md](adr/TEMPLATE.md).
- [compare/](compare/) — decision records for forks (debate + matrix + verdict +
  reopen-trigger); [proposals/](proposals/) — parked ideas (`status: proposed`).
- [regression/](regression/) — dated cage-lab capture/regression reports (data, not
  spec).
- [archive/README.md](archive/README.md) — every shipped handoff/prompt/build-prompt
  and superseded draft. History, not spec.
