# Cage docs — start here

**2026-07-25: doc sweep.** Cage is being rebuilt hookless (pull-only capture, MCP
read surface). Most operational/subsystem docs were removed with the hook machinery
and rendered assets — they described the pre-removal world and will be rebuilt on
the new base. What remains here is **current spec**; everything in
[`archive/`](../work/archive/README.md) is **history** and must never be cited as current
spec.

## Current spec

- [PLAN.md](PLAN.md) — the design of record: substrate contract, attribution
  engine, every plan-§ referenced from code and CLAUDE.md.
- **[OPEN-WORK.md](../work/OPEN-WORK.md) — the ONE plan of pending work, and ONLY that.**
  It lives in root `work/`, not `docs/` (moved 2026-08-12). It is an **index**: one
  line per item, one screen, nothing else. **The queue is empty** — Arpit closed
  every item and every parked proposal unbuilt, and the file states only that;
  the closure history lives in [archive/](archive/) and [IMPLEMENTATION.md](../work/IMPLEMENTATION.md),
  not here. A completed item is **removed, never left ticked** — legal only once its outcome is
  in [IMPLEMENTATION.md](../work/IMPLEMENTATION.md) and any evidence is published to
  [regression/](regression/), with residual limits carried forward as their own
  items. So its length is a truthful measure of what is left. **Test-gated**:
  `tests/test_queue_honesty.py` fails the suite when the header's *checkable* claims
  (version · tag · clean-and-pushed) contradict git — and stays silent when it makes
  no claim, because a gate that reddens on every in-flight change teaches you to
  ignore it.
- **`open/` is gone** (2026-08-12). It held one file per open item from 2026-08-11;
  when the queue was closed wholesale every item moved to
  [archive/](archive/) as `v0.49-*.item.md`. An item is now **one line in the index**,
  with detail inline or in a handoff/prompt pair in `../work/` root. The standing
  constraints that lived beside it did **not** lapse —
  [archive/v0.49-open-queue-constraints.md](../work/archive/v0.49-open-queue-constraints.md)
  names which are enforced mechanically and which are now prose-only, including the
  **ZERO dummy data** law.

## Active work

Created when an [OPEN-WORK.md](../work/OPEN-WORK.md) item is picked up; archived on
implement. COPILOT-METRICS, KIRO-METRICS, and CLAUDE-METRICS — the three per-chat
metrics-ledger builds, one per agent — were all built and green on 2026-08-14 and
archived: [copilot](../work/archive/v0.49-copilot-metrics-ledger.handoff.md) ·
[kiro](../work/archive/v0.49-kiro-metrics-ledger.handoff.md) ·
[claude](../work/archive/v0.49-claude-metrics-ledger.handoff.md).

**METRICS-PRIMARY** — the flip that made those three ledgers the SOURCE of derived
spend from a pinned cutover — was built and green on 2026-08-14 and archived:
[handoff](../work/archive/v0.50-metrics-primary.handoff.md) ·
[prompt](../work/archive/v0.50-metrics-primary.prompt.md). Its design of record is
[ADR 0010](../work/archive/adr/0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md).

**USAGE-ONLY** — the deletion of the money subsystem, and the largest removal in the
project's history — was built and green on 2026-08-14 and archived:
[handoff](../work/archive/v0.50-usage-only.handoff.md) ·
[prompt](../work/archive/v0.50-usage-only.prompt.md). Its design of record is
[ADR 0011](../work/archive/adr/0011-cage-measures-usage-not-cost.md), which also **supersedes the money
half of ADR 0010**: the spend cutover is retired and `ledger.spend()` partitions by
agent rather than by time.

**SURFACE-CUT is BUILT (2026-08-14)** — [handoff](../work/archive/v0.50-surface-cut.handoff.md) ·
[prompt](../work/archive/v0.50-surface-cut.prompt.md), archived on implement; rationale and
the six recorded-but-unread facts it leaves behind are in
[surface-cut.decision.md](../work/surface-cut.decision.md). It deleted `cage report`, all
of `cage data`, `insights attrib|adoption|compare|estimate|calibration` and
`authorship ledger-sync`, and cut MCP from 6 tools to 2. **Capture is unchanged** — every
row those views read is still recorded. One phase was deliberately not executed: the
graphify shim still probes a deleted verb (SHIM-DEAD-VERB, 15 red tests, Arpit's call).

**One thing each of the three left open is not a pair and does not live here:** a
`CLAUDE.md` diff (ledger diagram line + a substrate bullet) is **proposed, awaiting
Arpit** for each — steering files are never silently rewritten, so the diffs sit in
those sessions' responses and in [WORKLOG.md](../work/WORKLOG.md), not as docs in
this tree.

## The lab manual

- **[cage-lab/](../work/cage-lab/README.md) — how to build `../cage-lab` from scratch.** The
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
[DOC-REGISTRY.md](../work/DOC-REGISTRY.md). **Four of these live in root `work/`, not
`docs/`** (moved 2026-08-12) — `WORKLOG.md`, `INTERVIEW.md`, `IMPLEMENTATION.md`,
and `OPEN-WORK.md` above; `MACHINE.md` moved with them. Each bullet below links
to its real location.

- **[CLI.md](adr/0002_cli.md) — every `cage` command in one place.** The 5 daily verbs, the 7
  groups, the 4 hidden plumbing commands and every flag, plus the removed-verb
  migration table and the surface's known gaps. **Test-gated**: `tests/test_cli_reference.py`
  checks it bidirectionally against `cli.build_parser()`, so a rename that misses this
  file turns the suite red rather than leaving a dead verb in prose.
- **`doc-size-discipline.md` and `restricted-environments.md` moved to `work/`**
  (2026-08-14). Both are working docs rather than design/reference: one is a
  time-boxed process trial, the other an operations guide. They keep their owner
  triggers and their DOC-REGISTRY rows —
  [doc-size-discipline](../work/doc-size-discipline.md) ·
  [restricted-environments](../work/restricted-environments.md).
- [GLOSSARY.md](GLOSSARY.md) — every recurring term, defined once against the code.
- **`claude-capture.md` · `copilot-capture.md` · `kiro-capture.md` · `shim-contract.md`
  are GONE (2026-08-14).** Each was absorbed **whole** into its ADR — the store→property
  tables and known gaps into §2, the executive summary into §1, and the entire
  interceptor behaviour contract (B1–B8, B8a, D1–D8, the anti-recursion proof) into
  ADR-GRAPHIFY §2. One document per agent now carries both *what is captured* and *why*,
  so a capture change and its rationale can no longer drift apart. The same
  update-in-the-same-change rule applies, now to the ADR:
  [ADR-CLAUDE](adr/0003_claude.md) · [ADR-COPILOT](adr/0004_copilot.md) ·
  [ADR-KIRO](adr/0005_kiro.md) · [ADR-GRAPHIFY](adr/0007_graphify.md).
- [FORMULAS.md](FORMULAS.md) — every computed number: formula · code home ·
  method tag · the knobs that move it.
- [WORKLOG.md](../work/WORKLOG.md) — the running per-session handoff (append every
  exchange, Claude Code and Cowork/chat alike).
- [INTERVIEW.md](../work/INTERVIEW.md) — the **exit interview**: notes from the outgoing
  maintainer-model to every future one. Read it after CLAUDE.md.
- [DOC-REGISTRY.md](../work/DOC-REGISTRY.md) — the doc freshness tracker (triggers +
  last-verified).
- [architecture-flow.mermaid](architecture-flow.mermaid) — the one-way data flow as
  a diagram (also linked from the README).
- [example/](example/) — copy-from contracts: cli · debug · setup · toml-config.
- [IMPLEMENTATION.md](../work/IMPLEMENTATION.md) — the build log.
- [dogfood/](../work/dogfood/README.md) — cage's own ledger, published as dated snapshots
  (append-only, mirrors [regression/](../work/regression/README.md)); linked from the README,
  version-free. Freshness guarded by `tests/test_dogfood_freshness.py` (60-day gate).

## Standing records

- **[adr/](adr/README.md) — the durable *why*: [ADR-LAWS](adr/0001_laws.md) plus one
  record per metered thing** (restructured 2026-08-14): [ADR-CLAUDE](adr/0003_claude.md) ·
  [ADR-COPILOT](adr/0004_copilot.md) · [ADR-KIRO](adr/0005_kiro.md) ·
  [ADR-GRAPHIFY](adr/0007_graphify.md). Each has **§1 for humans** (one screen, Mermaid +
  ASCII diagrams) and **§2 for agents** (the binding detail, ending in a veto condition).
  The five laws that bind them all — pull-only · one sink · append-only ·
  counts-never-content · usage-never-cost — live in [ADR-LAWS](adr/0001_laws.md), each
  with its ratification and veto, and are restated in no other record. Author from [adr/TEMPLATE.md](adr/TEMPLATE.md).
  **Cite by name — `ADR-KIRO`, never "ADR 0003"**: the numeric names belong to the
  eleven superseded records, now history in
  [work/archive/adr/](../work/archive/adr/README.md) and never current spec.
- [compare/](compare/) — decision records for forks (debate + matrix + verdict +
  reopen-trigger). `proposals/` is gone (2026-08-12): all five parked ideas were closed
  unbuilt and are [archive/](archive/)`v0.49-*.proposal.md`; the format contract to copy
  if it is re-established is
  [archive/v0.49-proposals-readme.md](../work/archive/v0.49-proposals-readme.md).
- [regression/](regression/) — dated cage-lab capture/regression reports (data, not
  spec).
- [archive/README.md](../work/archive/README.md) — every shipped handoff/prompt/build-prompt
  and superseded draft. History, not spec.
