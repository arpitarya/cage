# docs/compare — decision records for forks

**Standing rule.** Whenever a decision has multiple viable options, write a
*compare doc* here **first** — before committing to a plan. A compare doc carries:

- the **debate** — the real case for each option, not a strawman;
- a **matrix** — the options scored against what actually matters;
- **grounded references** — a plan section, a measurement, a paper, or a worked
  example per claim (an assertion without a reference is incomplete);
- a **proposed verdict** — which Arpit accepts or overrides;
- a **reopen-trigger** — what evidence would revisit the call (the same discipline
  as an ADR's veto condition).

A settled fork graduates to a plan entry and, when it ships, an
[ADR](../adr/TEMPLATE.md). The compare doc stays as the evidence behind it.

Distinct from [proposals/](../proposals/): a compare doc resolves a **fork** (two+
live options now); a proposal parks an **idea** (worth keeping, not being built).

Naming: `<topic>.compare.md`. Written in short points, not walls of prose.

## Decided / awaiting verdict

- [gf-launcher-metering.compare.md](gf-launcher-metering.compare.md) — **GF-LAUNCHER**:
  how the graphify interceptor reaches cage when `--python-launcher` leaves no `cage` on
  PATH. Three options (setup-time twin variants · a runtime interpreter arm · accept the
  gap); **proposed verdict B**, awaiting Arpit's accept or override.
- [copilot-pricing-basis.compare.md](copilot-pricing-basis.compare.md) — Copilot
  cost: credits vs tokens vs both. **Proposed verdict C — both, one job each**
  (credits = what was billed; tokens = the cross-agent denominator), joined by a
  ladder, never blended. **DECIDED — C accepted 2026-08-02 · IMPLEMENTED v0.44**
  (unreleased). Living spec: [FORMULAS.md §1.1a](../FORMULAS.md) ·
  [PLAN.md §3.1](../PLAN.md) · `cage query copilot-credits`; the proposal it graduated
  through is [archived](../archive/v0.44-copilot-credits.proposal.md).
- [view-export-and-run-stamp.compare.md](view-export-and-run-stamp.compare.md) — the
  artifact surface: where a generated-at stamp may live, whether a read command writes a
  file, and what bare `--export` produces. **DECIDED 2026-08-10 · IMPLEMENTED v0.48**
  (unreleased): an artifact-only metadata block, `--export` as a capability not a side
  effect, all available formats per run. Living spec: [CLI.md](../CLI.md) §Export flags ·
  `cage query view-export`.
