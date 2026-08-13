# Phase benchmark (2026-07-29) — SUPERSEDED

> **⚠ SUPERSEDED (2026-08-01) by
> [2026-08-01-phase-benchmark.md](2026-08-01-phase-benchmark.md).** Leg D (the manual
> VS Code / IDE cells) has since run, so this benchmark's four ⬜ UNPROVEN cells are no
> longer the current coverage statement. Retained **unedited below the marker** as the
> published record of what was true before leg D — cite it as history, never as current
> coverage.
>
> _Banner only: it sits **above** the `HASH-COVERS-BELOW` marker, so the body below is
> byte-identical to what was originally published, and the published sha256 is unchanged._

**Benchmark sha256 (body below the marker = the whole file as originally published):**
`555073bf63e25985cb36912853c8dd650877236a52599750f45ff537b1efe7f4`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
# Phase benchmark — cage capture, per agent × surface × graphify-state (2026-07-29)

Derived from the 2026-07-29 run report (no new numbers). **Supersedes**
`2026-07-28-phase-1-benchmark.md`. States, per cell, what was verified and how.

## Legend
✅ verified (real traffic, this run) · ⚠️ limited (stated) · ⬜ UNPROVEN (manual leg D) ·
n/a not applicable.

| agent · surface | token capture | graphify-OFF | graphify-ON capture | how verified |
|---|---|---|---|---|
| **claude · CLI** | ✅ exact (386 rows = 181+205 turns) | ✅ 0 receipts | ✅ 1 receipt (auto-adopt) | 3-way reconcile, isolated ledger |
| **copilot · CLI** | ✅ exact (idempotent, zero UNPRICED) | ✅ 0 receipts | ✅ **23 receipts via F1** (when invoked); 0 when not (adoption) | 3-way reconcile; F1 on real traffic |
| **kiro · CLI** | ⬜ **NOT AVAILABLE** — kiro has no headless `-p` (Electron IDE); credit-derived `estimated` capture is FINAL by design | — | — | premise-checked; manual only |
| **claude · VS Code** | ⬜ UNPROVEN (leg D) | — | ⚠️ shim CONTINGENT (Phase B) | manual, Arpit — pending |
| **copilot · VS Code** | ⬜ UNPROVEN (leg D) | — | ⚠️ usage-row only, **no receipt** (Phase F2: command but no result) | manual, Arpit — pending |
| **kiro · VS Code** | ⬜ UNPROVEN (leg D) | — | ⚠️ HONEST-LIMIT (no tool bodies) | manual, Arpit — pending |

## What this phase proves (that Phase 1 did not)
- The **whole chain end-to-end on a lab nobody had touched**: rebuild → install → drive →
  capture → derive → verify, graphify the single toggled variable, on **both** scriptable CLIs.
- **F1 (copilot-CLI graphify detection) works on real traffic** — 23 real receipts.
- The I.4 bar met per agent: **zero UNPRICED**, usage ≥ receipts, re-import idempotent,
  three-way reconciliation exact.

## Coverage, honestly (not completeness)
- **Verified: 2 of 6** agent×surface cells (claude-CLI, copilot-CLI) — the scriptable ones.
- **UNPROVEN: 4 of 6** — every VS Code cell + kiro. These are **leg D (manual, Arpit's
  hands)**, gated on Phase B's shim contingency; kiro-CLI is NOT AVAILABLE (no headless mode).
- This is a good report: it states what ran and what didn't, and never fabricates the gap.

## Cost
$5.29 for 70 prompts / 429 metered turns (cheapest models, 82% cache). New baseline for
future comparison (`golden/_src` hash-stable via `rebuild.sh`).
