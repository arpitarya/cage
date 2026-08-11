---
item: POLICYSYNC-FIXTURE
lane: parked · gated on a third occurrence
status: guard shipped 2026-08-01; fixture speculative until the trigger fires
---

# POLICYSYNC-FIXTURE — the sync tests should own their bundle

Five tests exercise **generic sync mechanics** but borrow whatever live bundle table
happens to be scalar-keyed as their worked example. Remove that table and five unrelated
tests go red. Happened twice in one cycle (`[human]`, `[budgets]`, both v0.36).

Full design, cost and the cheaper partial already in place:
[proposal](../proposals/policysync-synthetic-bundle.proposal.md).

## Trigger

**A third table removal reddening these tests.** Two removals in one unusually destructive
cycle is not the steady state; a normal release removes no tables at all.

## The cost, stated so it is not forgotten

A fully synthetic bundle **stops testing that sync works on the actually-shipped bundle**.
`test_already_in_sync_message_on_current_file` covers that today and must survive any
refactor — otherwise the trade is a downgrade wearing the clothes of an upgrade.

The cheaper partial: the borrowed table/key lives in **one named constant**, so a re-point
is a one-line edit rather than a five-test rewrite. The
[guard test](../archive/v0.36-sync-guard.prompt.md) shipped 2026-08-01.
