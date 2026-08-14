# ADR NNNN — <decision, as a present-tense verdict>

- **Status:** Accepted (vX.Y.Z, plan §N) · <or Proposed / Superseded by ADR MMMM>
- **Date:** YYYY-MM-DD
- **Deciders:** Arpit (ratifier), <executor>

> Copy this file to `NNNN-<kebab-slug>.md`, keep every section, delete these
> quote-blocks. The two shipped records — [0001](0001-ledger-team-aggregation-notes-not-external-sink.md)
> and [0002](0002-universal-capture-global-ledger-explicit-import-export.md) — are
> the worked examples. An ADR-worthy decision is one where a wrong call is expensive
> to reverse and the reasoning isn't obvious from the code (the substrate contract,
> the determinism/method law, the `$0`/no-infra wedge, a capture-architecture
> choice). A one-line dated call goes in the plan's decisions log instead.
>
> Write it in **short points**, not a wall of prose — one idea per point, roomy,
> lead with the takeaway.

## Context

> The forces that made a decision necessary. What broke, what's in tension, what a
> future agent needs to know to see why the obvious option isn't the chosen one.
> Field-proven facts beat speculation — cite them.

## Decision

> The verdict, stated once and in bold, then the specifics as points. Present tense
> ("Capture is pull-based and global"), not "we decided to".

## Consequences

> What this commits the codebase to, and what it now rules out. Include the ones
> that cut against the decision, not just the wins.

## Alternatives rejected

> The real options considered, one point each, with **why each lost**. This is the
> section that stops a future agent re-proposing a dead idea. "Deliberately not
> taken" (below) is different — that's an option left genuinely open.

## Reference

> **Required — an ADR that only asserts is incomplete** (fux's rule). A plan
> section, a paper, a blog post, or a concrete worked example that grounds *why*.
> Ground the claim; don't assert it.

## Veto condition (when to revisit)

> **Required — cage's own anti-rot device.** Three parts, each load-bearing; keep
> the ones that apply, and say so when one doesn't.
>
> 1. **A falsifiable trigger — numbered where the decision is volume- or
>    measurement-gated.** State the number that reopens this ("single-digit GB/yr is
>    fine; 100s of GB is not… **only then, and only with a named volume number**").
>    A veto reopenable only by a *measurement*, never an *argument*, pre-empts a
>    future agent re-litigating from first principles. Name **where** the change
>    lands, so revisiting can't quietly become a redesign.
>
> 2. **Contingent vs. invariant — labelled.** Split the parts that auto-revisit on
>    evidence from the parts that are product values and move only by ratified
>    reversal of this ADR. Pretending every decision is revisitable-on-evidence lies
>    about the ones that are values (0002: `project` capture is contingent on a
>    client exposing cwd; "no OS scheduler" is an invariant).
>
> 3. **A "deliberately not taken" record** — where there's meaningful negative
>    space, an option considered and declined but *not* dogmatically rejected, with
>    its own future threshold (0001's write-path size block). Records the omission as
>    a choice, so the next agent doesn't mistake it for an oversight and ship it as a
>    `# v2:` half-build. Omit this part only when there's no such open option.
