# work/compare — decision records for forks

**Standing rule.** Whenever a decision has multiple viable options, write a
*compare doc* here **first** — before committing to a plan. A compare doc carries:

- the **debate** — the real case for each option, not a strawman;
- a **matrix** — the options scored against what actually matters;
- **grounded references** — a plan section, a measurement, a paper, or a worked
  example per claim (an assertion without a reference is incomplete). **Never an
  archived document**: under *Archived documents are named, never cited*
  ([CLAUDE.md](../../CLAUDE.md)) a file under `work/archive/` may be named but backs
  nothing, because it could have been rewritten since. An archive link in a matrix cell
  is an ungrounded claim wearing a citation;
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
- [graphify-interceptor-verb.compare.md](graphify-interceptor-verb.compare.md) —
  **SHIM-DEAD-VERB**: SURFACE-CUT deleted `cage data graphify`, the verb both interceptor
  twins probe, so the interceptor route captures nothing on every OS and `cage setup` still
  installs the dead twin. Four options (retire the interceptor · restore the verb hidden ·
  keep it dead but honest · park); **proposed verdict B — restore at the identical spelling
  as a hidden verb (`mcp`/`demo`/`debug` precedent), 8 lines**, because B3's marker set is
  already burned into every installed shim, so only B heals machines in the field.
  Awaiting Arpit's accept or override.
- [gf-launcher-metering.compare.md](gf-launcher-metering.compare.md) — **GF-LAUNCHER**:
  how the graphify interceptor reaches cage when `--python-launcher` leaves no `cage` on
  PATH. Three options (setup-time twin variants · a runtime interpreter arm · accept the
  gap); **proposed verdict B**, awaiting Arpit's accept or override.
- [copilot-pricing-basis.compare.md](copilot-pricing-basis.compare.md) — Copilot
  cost: credits vs tokens vs both. **Proposed verdict C — both, one job each**
  (credits = what was billed; tokens = the cross-agent denominator), joined by a
  ladder, never blended. **DECIDED — C accepted 2026-08-02 · IMPLEMENTED v0.44 · RELEASED**
  (v0.44.0; corrected 2026-08-11 — this line said "unreleased" for nine days). Living spec: [FORMULAS.md §1.1a](../../docs/FORMULAS.md) ·
  [ADR-LAWS](../../docs/adr/0001_laws.md) · `cage query copilot-credits`; the proposal it graduated
  through is [archived](../archive/v0.44-copilot-credits.proposal.md).
- [view-export-and-run-stamp.compare.md](view-export-and-run-stamp.compare.md) — the
  artifact surface: where a generated-at stamp may live, whether a read command writes a
  file, and what bare `--export` produces. **DECIDED 2026-08-10 · IMPLEMENTED v0.48 · RELEASED** (v0.48.0, PyPI
  2026-08-10; corrected 2026-08-11 — this line said "unreleased" the day after it shipped): an artifact-only metadata block, `--export` as a capability not a side
  effect, all available formats per run. Living spec: [CLI.md](../../docs/adr/0003_cli.md) §Export flags ·
  `cage query view-export`.
- [agent-share-historical-backfill.compare.md](agent-share-historical-backfill.compare.md) —
  **AGENT-SHARE-BACKFILL**: line-match reaches 66 of this repo's 166 commits and stops at
  2026-07-16, the vendor's ~30-day transcript wall; the other 100 can never be matched by
  any future code. Five options (leave `unknown` · a read-time `declared` column from the
  commit trailer · bulk human attestation · infer from the diff · archive raw transcripts);
  **proposed verdict B for presence + A for the percentage** — the share stays `unknown`,
  a `declared` column carries the trailer's model string and is never stored, so no
  arithmetic can turn a declaration into a share. D rejected on measured evidence
  (34 F1 vs a 45.7 random baseline out-of-domain; 39 F1 on hybrid human-edited AI code),
  E rejected on counts-never-content. **Amended 2026-08-14 with the breadth arm** —
  agent x surface: `COVERAGE_GAPS` calls copilot/kiro structural exclusions and the stores
  contradict it (copilot CLI `events.jsonl` and VS Code `chatSessions`, both already swept,
  carry edit text; kiro IDE logs carry before *and* after). Retention inverts the ranking —
  kiro IDE keeps everything, claude is capped at ~30 days — and kiro writes no trailer at all,
  so content matching is its only possible route. **DECIDED — B+A accepted by Arpit 2026-08-14,
  ratified as [ADR-AUTHORSHIP](../../docs/adr/0009_authorship.md)** (a ninth record, carved out of
  ADR-CLAUDE; ADR-COVERAGE's authorship veto is recorded as FIRED — its trigger was satisfiable
  on the day it was written). The three code changes are **not built** — OPEN-WORK
  AUTHORSHIP-CODE-CATCHUP.
- [coverage-strike-gate.compare.md](coverage-strike-gate.compare.md) —
  **COVERAGE-STRIKE-2**: ADR-COVERAGE's two-strikes trigger (parked full generator) fired
  on STRIKE 1+2, but STRIKE 3 showed the named remedy would not have caught it. Four
  options (build the full generator · extend the existing narrow generator to the two
  ✅/N-A tables using only registries that exist today · build the missing surface-grained
  registries first · close the two-strikes counter). **Proposed verdict D — close the
  counter** (STRIKE 1 was table-shaped and cheaply closeable; STRIKE 2 and STRIKE 3 were
  prose/missing-registry drift no table-diff generator reaches), **with B shippable
  separately on its own merits** since it is cheap and would have caught STRIKE 1 outright.
  Awaiting Arpit's accept or override.
