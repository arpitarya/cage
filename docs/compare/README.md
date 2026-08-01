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

_(No compare docs yet — the first real fork lands the first one.)_
