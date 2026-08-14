---
doc: the superseded numeric ADRs 0001–0011 — HISTORY, never current spec
status: frozen 2026-08-14 · superseded by the four per-agent ADRs in docs/adr/
---

# Archived ADRs — history, not spec

**Never cite anything in this directory as current spec.** These eleven records were the
ADR set until 2026-08-14, when the standing set became **four per-agent records**
([docs/adr/](../../../docs/adr/README.md)). Each is preserved **verbatim** — only relative
link paths were adjusted for the move, never a claim, a number, or a verdict.

They stay readable because the *reasoning* is still load-bearing: a per-agent ADR states
where a decision landed; these state why it beat the alternatives. When the two disagree
about what cage does **today**, the per-agent ADR wins.

## Where each one went

| archived record | folded into | what carried forward |
|---|---|---|
| [0001](0001-ledger-team-aggregation-notes-not-external-sink.md) — team ledger via `refs/notes` | *(no live home)* | **Retired by SURFACE-CUT** — `ledgersync.py` and `--team` are deleted; `notes-sync` survives for provenance only |
| [0002](0002-universal-capture-global-ledger-explicit-import-export.md) — universal capture, global ledger | all four (shared law) | One-sink resolution · `project` is a derived view · no OS scheduler |
| [0003](0003-hookless-capture-pull-only-mcp-only-wiring.md) — hookless, pull-only | all four (shared law) | `cage import` + capture-on-read; MCP is the only wired surface |
| [0004](0004-append-only-delta-rows-and-separate-by-schema.md) — delta rows, separate by schema | [ADR-COPILOT](../../../docs/adr/0003_copilot.md) · [ADR-KIRO](../../../docs/adr/0004_kiro.md) | Cumulative → append-only deltas · a different *shape* of number gets its own row kind |
| [0005](0005-graphify-receipt-ids-session-inclusive-cross-route-deferral.md) — receipt ids, cross-route deferral | [ADR-GRAPHIFY](../../../docs/adr/0005_graphify.md) | Session-inclusive id · deferral not id-collision · shim stamps `session=""` |
| [0006](0006-kiro-rows-are-machine-facts-not-project-facts.md) — kiro IDE rows are machine facts | [ADR-KIRO](../../../docs/adr/0004_kiro.md) | The two-store split and the routing law, inherited never re-decided |
| [0007](0007-graphify-twin-pair-hand-paired-not-templated.md) — hand-paired twin pair | [ADR-GRAPHIFY](../../../docs/adr/0005_graphify.md) | Both twins on every OS · hand-paired · contract in `docs/` |
| [0008](0008-line-match-authorship-counts-persisted-content-transient.md) — line-match authorship | [ADR-CLAUDE](../../../docs/adr/0002_claude.md) | Counts persisted, content transient · `human~` is a residual · windows never `HEAD` |
| [0009](0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md) — kiro tool-run bodies transient | [ADR-KIRO](../../../docs/adr/0004_kiro.md) · [ADR-GRAPHIFY](../../../docs/adr/0005_graphify.md) | The one named carve-out · truncation files nothing · store stays read-only |
| [0010](0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md) — metric ledgers are the spend source | all four | `SPEND_SOURCES` · point-in-time-never-cumulative |
| [0011](0011-cage-measures-usage-not-cost.md) — usage, never cost | all four (shared law) | Two units, both recorded counts · no rate card · no conversion, ever |

## What here is genuinely dead

Two records describe machinery that **no longer exists**. They are kept because the
reasoning was ratified and the reversal should be visible — not because the behaviour is
current:

- **0001's `refs/notes/cage-ledger` team aggregation.** `ledgersync.py` and the ledger
  note are deleted (SURFACE-CUT, 2026-08-14). The union-by-id law it established survives
  in `mergeutil.union_by_id`, which `notes-sync` still uses for provenance.
- **0010's `SPEND_CUTOVER`.** Retired by 0011 — `ledger.spend()` partitions by **agent**,
  not by time. The constant is gone with nothing in its place. 0010's other rules
  (`SPEND_SOURCES` membership, point-in-time-never-cumulative) are still binding.

[TEMPLATE.md](TEMPLATE.md) is the **old** single-audience ADR template, kept for reading
the eleven. New records use [docs/adr/TEMPLATE.md](../../../docs/adr/TEMPLATE.md).
