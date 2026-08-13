# work/compare — decision records for forks

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
[ADR](../../docs/adr/TEMPLATE.md). The compare doc stays as the evidence behind it.

There is no longer a `docs/proposals/` directory — every parked idea was closed unbuilt
2026-08-12 (see [OPEN-WORK.md](../../work/OPEN-WORK.md)). A compare doc resolves a **fork** (two+
live options now); if a parked-idea home is ever re-established, the format contract to
copy is in [archive/v0.49-proposals-readme.md](../archive/v0.49-proposals-readme.md).

Naming: `<topic>.compare.md`. Written in short points, not walls of prose.

## Decided / awaiting verdict

- [commits-view-cost-bound.compare.md](commits-view-cost-bound.compare.md) —
  **COMMITS-WINDOW**: `cage insights commits` costs one `git show` per commit in the
  whole history to print 20 rows (measured 6.4s / 123 commits). Three options (a default
  relative `--since` · cap the READ by the row cap · leave it). **DECIDED — B accepted 2026-08-11, built** (`commitview.summarize(limit=…)`, text path
  only; dropped commits footnoted as *not read*);
  A was rejected on the determinism law — a relative default puts a wall clock in the
  default path — and on the measurement, since 90d cut zero commits here.
- [gf-launcher-metering.compare.md](gf-launcher-metering.compare.md) — **GF-LAUNCHER**:
  how the graphify interceptor reaches cage when `--python-launcher` leaves no `cage` on
  PATH. Three options (setup-time twin variants · a runtime interpreter arm · accept the
  gap); **proposed verdict B**, awaiting Arpit's accept or override.
- [copilot-pricing-basis.compare.md](copilot-pricing-basis.compare.md) — Copilot
  cost: credits vs tokens vs both. **Proposed verdict C — both, one job each**
  (credits = what was billed; tokens = the cross-agent denominator), joined by a
  ladder, never blended. **DECIDED — C accepted 2026-08-02 · IMPLEMENTED v0.44 · RELEASED**
  (v0.44.0; corrected 2026-08-11 — this line said "unreleased" for nine days). Living spec: [FORMULAS.md §1.1a](../../docs/FORMULAS.md) ·
  [PLAN.md §3.1](../../docs/PLAN.md) · `cage query copilot-credits`; the proposal it graduated
  through is [archived](../archive/v0.44-copilot-credits.proposal.md).
- [view-export-and-run-stamp.compare.md](view-export-and-run-stamp.compare.md) — the
  artifact surface: where a generated-at stamp may live, whether a read command writes a
  file, and what bare `--export` produces. **DECIDED 2026-08-10 · IMPLEMENTED v0.48 · RELEASED** (v0.48.0, PyPI
  2026-08-10; corrected 2026-08-11 — this line said "unreleased" the day after it shipped): an artifact-only metadata block, `--export` as a capability not a side
  effect, all available formats per run. Living spec: [CLI.md](../../docs/CLI.md) §Export flags ·
  `cage query view-export`.
