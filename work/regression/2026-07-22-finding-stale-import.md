# Finding — Import is stale (`stale-import`)

**Severity:** LOW · **Status:** ◻ OPEN — user-action item (cage installs no
scheduler by design) · **Surface:** pull-based capture freshness

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) |

## Status now

OPEN, and by design a user-action item, not a cage defect: cage installs no OS
scheduler ([ADR 0002](../../docs/adr/0002-universal-capture-global-ledger-explicit-import-export.md)),
so keeping the ledger fresh is the user's own cron/`schtasks` line or a foreground
`cage data watch`.

## Evidence (as observed 2026-07-22)

`_last_import = 2026-07-19` (the report showed "last import 3d ago"). Capture is
pull-based; with nothing scheduled, the ledger drifts behind reality — and (at the
time) every agent flipped to `captured:false` between runs (that flag behavior was
itself corrected — see [health-contradiction](2026-07-22-finding-health-contradiction.md)).

## Action

A user cron line calling `cage import` (cage installs no scheduler by design), or
`cage data watch` in the foreground.

## History

**2026-07-22 (observed, lab-run-001):** `_last_import = 2026-07-19`, 3 days stale.
Remains a user-action item as of this record.
