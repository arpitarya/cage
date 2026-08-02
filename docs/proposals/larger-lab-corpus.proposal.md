---
doc: proposal — a larger lab corpus
status: proposed
raised: 2026-08-01
owner: Arpit
---

# Proposal — a second, larger lab corpus

**The claim:** `tinyshop` (~43 KB, 6 modules) may systematically **understate** graphify's
value, because with six small files *reading them all is cheap* — which is precisely the
cost a graph exists to avoid. If so, leg D's "graphify ON cost ~14% more" partly measures
the fixture rather than the tool.

**Status: hypothesis, not a finding.** n = 1, and no larger corpus has been run.
Nothing published should be revised on the strength of it.

## Why it matters now

[K+NET](../regression/2026-08-01-finding-saved-is-gross.md) established that `saved` is
gross and that a graphify session can cost more than it saves. Two very different
readings of that result:

| reading | implication |
|---|---|
| graphify's overhead exceeds its benefit **generally** | the tool's value proposition is in question |
| graphify's overhead exceeds its benefit **on a 43 KB corpus** | the fixture is the wrong size to show the effect |

**Only a larger corpus separates them.** Until one is run, the two are not
distinguishable, and the honest position is that leg D bounds nothing about real repos.

## Why the effect should scale with corpus size

- graphify's saving is modelled as *avoided read cost* — files an answer would otherwise
  have required. That grows with repo size; the cost of *using* graphify (the invoking
  turn, the injected context) is roughly constant per query.
- So the gross/net gap should narrow, and eventually invert, as the corpus grows. A
  break-even corpus size is the interesting number, and it is measurable.

## Shape, if picked up

- A **new named corpus alongside** `tinyshop` — never a mutation of it
  (decision 2026-08-01: the corpus is frozen; new questions get new corpora).
- Large enough that reading the relevant files is genuinely expensive: order 100×
  tinyshop, real call-graph depth, not generated filler.
- Same protocol otherwise — both arms, byte-pinned, `.fixture-sha256`, ZERO dummy data.
- Report **per corpus**, never pooled. Two corpora are two experiments.

## Cost

A full A-arm and B-arm on a new corpus. Scripted legs are cheap (leg I: $5.29 / 70
prompts); the manual cells are Arpit's time, which is the real constraint.

## Trigger to pick this up

When **NET-1** runs (5 paired closed tasks for `cage insights compare`). If those clear
the `MIN_COMPARE_N` gate on tinyshop and graphify still reads net-negative, this proposal
becomes the next question rather than a parked idea — because at that point "the fixture
is too small" is the leading remaining explanation.

## Deliberately not proposed

**Replacing tinyshop.** Its bytes are the control for every published result to date.
Mutating it would invalidate the leg D run report and both phase benchmarks for no gain —
a second corpus costs the same runs and keeps the first experiment intact.
