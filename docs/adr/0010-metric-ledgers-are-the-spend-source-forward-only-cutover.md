# ADR 0010 — The per-agent metric ledgers become the spend source, at a forward-only pinned cutover

- **Status:** Accepted (v0.49.1 unreleased, plan §3.14)
- **Date:** 2026-08-14
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

- Three capture-only metric ledgers shipped 2026-08-14 — `ledger/{claude,copilot,kiro}/`
  (PLAN §3.11–3.13). Nothing read them.
- They exist because `calls` structurally cannot hold vendor-native facts at three grains.
  Measured on this repo: `calls` and the claude metric ledger **disagree by 2.01×** on
  identical sessions — 43,885 assistant transcript rows folding to 21,875 actual API
  responses (CLAUDE-DEDUP). **The metric ledger is the correct one.**
- Arpit's directive, 2026-08-14: *"flip it — the future is going to be ledger/claude,
  ledger/copilot, ledger/kiro."*
- The literal "rewire everything" was stress-tested and did not survive intact: 6 months
  and 52,296 `calls` rows cannot be rebuilt into metric rows (the vendor fields were never
  captured then, and fabricating them violates counts-never-content), and Claude Code's
  own ~30-day transcript sweep makes backfill impossible past that cliff.

## Decision

- **A single pinned constant** — `constants.SPEND_CUTOVER = "2026-08-14T00:00:00Z"`. A
  **literal, never `now()`**: a computed cutover would make yesterday's report
  irreproducible tomorrow, and the determinism law rests on it.
- **One resolver, `ledger.spend(root, since)`** — rows with `ts <` the cutover from
  `calls`, rows at or after it from the metric kinds. Every derive site reads it; no site
  reads `calls` for spend.
- **Resolution is by each row's OWN `ts`**, never by its session's start, so a chat
  straddling the instant contributes to both sides — once each, never twice.
- **Capture stays dual-write.** `parse_calls` and the metric parsers both keep running, so
  the flip is a one-constant rollback rather than a data-loss event.
- **The cutover is SCOPED to the three agents that have a metric ledger.** `cage.meter`'s
  library rows (`agent="lib"`), proxy rows, and `[sources.<name>]` custom tools have no
  metric ledger and never will under this design; they resolve from `calls` forever.
- **A spend spine must be point-in-time, never cumulative** (`ledger.SPEND_SOURCES`), and
  each metric kind contributes exactly one source per surface — never a sum, because each
  kind deliberately holds several overlapping views of the same traffic.
- **`ledger.join_table` resolves a receipt's `call` id** — `spend()` plus the `calls` rows
  it superseded. A lookup table, never a sum source.

## Consequences

- Claude spend post-cutover drops ~2× as CLAUDE-DEDUP's overcount disappears.
  **CLAUDE-DEDUP and CLAUDE-SUBAGENT-KEY are closed by this build**, in the new ledger;
  `parse_calls` is untouched so recorded history stays as recorded.
- **Kiro reads zero post-cutover** (Arpit's explicit choice over a per-agent refusal): its
  metric route reads `devdata.sqlite`, its calls route reads `tokens_generated.jsonl`, and
  only the latter exists on the maintainer's machine.
- **No boundary footnote** (Arpit: *"there hasn't been a major release yet so flip"*) — no
  users are on the old basis, so there is nothing to explain away.
- `cage demo` now seeds a fixed pre-cutover instant. It stamped `now()` and printed empty
  §4.4 tables the moment the clock passed the cutover — a worked example is recorded
  history and should never have depended on a wall clock.
- Team aggregation (`ledgersync`) carries the three metric kinds, or `--team` would show
  every teammate's spend stopping dead at the cutover with no error.
- **One golden moved** (`R6`), agent label only, every number identical.

## Alternatives rejected

- **Migrate history into the metric ledgers.** Impossible without fabricating vendor
  fields, and the source transcripts are already gone past ~30 days.
- **Stop writing `calls`.** Removes the rollback path for no gain while the new spine is
  one day old.
- **Stamp `est_cost_usd` at capture** (the handoff's own §5.4). That field is only a
  last-resort fallback in `prices.call_usd_match`, and the transcript meter deliberately
  never sets it — dead weight, and freezing a price contradicts cage's derive-time law.
  The real blocker was `provider`, which `policy.price_match` keys on.
- **Delta the cumulative sources pro-rata / clamp a negative delta to 0.** Clamping
  silently discards real spend; the reset rule (a decrease means the counter reset, so the
  new value *is* the delta) is reused from `parse_copilot_cli_calls`.
- **An unscoped cutover.** Zeroes every library- and proxy-metered call the instant the
  clock passes. Caught only because the machine clock crossed the instant mid-build and
  47 tests went red at once.

## Reference

- Directive and the three answered questions: `work/WORKLOG.md`, 2026-08-14.
- Measured evidence: `work/IMPLEMENTATION.md`, 2026-08-14 (2.01× dedup on 43,885 real
  rows; the R6 receipt-orphaning measurement, 80,000 → 0).
- The grain problem this ADR's `SPEND_SOURCES` rule exists to prevent is the same class as
  [ADR 0004](0004-append-only-delta-rows-and-separate-by-schema.md)'s append-only delta
  rows — a cumulative row and a point-in-time row cannot be summed together.
- Spec: `work/archive/v0.50-metrics-primary.handoff.md` (archived; where it disagrees with
  the plan, the plan wins — §5.4 was corrected during the build).

## Veto condition (when to revisit)

**Contingent — auto-revisits on evidence:**

- **The cutover instant itself.** If a capture gap is found that leaves a hole *after*
  `SPEND_CUTOVER` for an agent that has a spine, moving the constant forward is the
  correction — but only with **the named row count of the hole**, measured from
  `cage doctor`'s per-source lines, never from an argument that "it feels wrong".
- **Kiro's zero.** Reopens the moment a kiro `ide` metric row can be parsed from
  `tokens_generated.jsonl` (the file the calls route already reads). That is a contained
  parser change; the zero is a capture gap, not a decision about kiro.
- **Dual-write's end.** Revisit only after **one full retention window (~30 days)** of
  clean metric capture with no gap — i.e. not before 2026-09-13, and then only with the
  gap count at zero.
- **`SPEND_SOURCES` membership.** A store added to a metric kind does NOT join the spine.
  It joins only if it is point-in-time AND covers a surface no existing spine covers.

**Invariant — product values, moved only by reversing this ADR:**

- **The cutover is a literal.** No computed, relative, or policy-configurable cutover,
  ever. It would put a wall clock in the derive path and end the determinism law.
- **Resolution is by the row's own `ts`.** Never by session start, and never by a
  session-level exclusion rule.
- **No row is counted twice.** The boundary is a partition, and `join_table` is a lookup
  table precisely so the union can never become a sum.
- **The scope stays the three agents with a metric ledger.** Library and proxy rows are
  not second-class; they are outside this decision entirely.

**Deliberately not taken:**

- **Writing receipts against metric-row ids.** Considered and declined *for now*: every
  receipt cage's own shims file is call-less by construction (graphify/fux carry a `task`
  and no `call`), so the linkage only matters for `cage.meter` callers passing `call=`,
  and `join_table` resolves those exactly. **Threshold to revisit:** a measured count of
  post-cutover receipts carrying a `call` id that `join_table` fails to resolve. It was
  **0 of 9** when this ADR was written. Do not ship the id change speculatively — it is a
  capture-path change in service of a problem that does not yet exist.
