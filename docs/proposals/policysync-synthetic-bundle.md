---
doc: proposal — a synthetic bundle fixture for the sync tests
status: proposed
raised: 2026-08-01
trigger: a THIRD table removal reddens the sync tests
---

# Proposal — `test_policysync` should own its bundle

**The coupling:** five tests exercise **generic sync mechanics** (keep-customized,
update-stale-default, confirm-bucket, orphan-warning) but borrow whatever live bundle
table happens to be scalar-keyed as their worked example. Remove that table and five
tests unrelated to it go red.

**Happened twice in one cycle** — `[human]` (axis removal) and `[budgets]` (opt-in), both
v0.36.

## Why it is NOT being built now (2026-08-01)

- The suite is **956 / 0**. A half-day test refactor takes real regression risk on a
  green suite immediately before a release that is already built.
- **The pain was diagnosis, not repair.** Re-pointing took minutes; understanding why
  five budget-unrelated tests failed took far longer. A [guard test](../archive/v0.36-sync-guard.prompt.md)
  captures that value for ~an hour — **built 2026-08-01**, see
  [IMPLEMENTATION.md](../IMPLEMENTATION.md#2026-08-01--sync-guard-name-the-sync-tests-borrowed-table-guard-its-removal).
- Two removals in one cycle is **not the steady state**. This cycle deleted an entire
  axis *and* made budgets opt-in; a normal release removes no tables at all. Until it
  recurs outside an unusually destructive cycle, the fixture is speculative.

## The design, if the trigger fires

`policy.bundled_raw()` is the **single** point `policysync` reads the bundle from, and it
is uncached — so a fixture can monkeypatch it and hand back a synthetic dict.

**The fixture must own both sides.** `v016` currently calls `initcmd.run()`, which
scaffolds the project file *from the real bundle*; with a fake bundle the two stop
corresponding. So it must also write a synthetic project `cage.toml` — valid enough for
`pricestoml`'s text surgery (which reads the *project* file's text, never the bundle's).

Also synthetic: the `OLD_DEFAULTS` / `REMOVED_KEYS` entries the tests already monkeypatch,
keyed to the fake table.

## The cost, stated plainly

A fully synthetic bundle **stops testing that sync works on the actually-shipped
bundle.** `test_already_in_sync_message_on_current_file` covers that today and must
survive any refactor — otherwise this trade is a downgrade wearing the clothes of an
upgrade.

## Trigger

**A third table removal reddening these tests.** At that point "unusual cycle" is no
longer the explanation and the fixture has earned its cost.

Cheaper partial already in place: the borrowed table/key lives in **one named constant**,
so a re-point is a one-line edit rather than a five-test rewrite.
