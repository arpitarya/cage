# Finding — kiro rows double-count **across** ledgers (a global log meeting per-workspace ledgers)

**Severity:** medium (any cross-ledger kiro total is inflated) ·
**Status:** ◻ **OPEN — document or warn** · **Surface:** kiro import into more than one
ledger root · **From:** [2026-08-01 leg D run report](2026-08-01-leg-d-run-report.md),
cell D6.

## What happens

Kiro writes **one global log**
(`~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/tokens_generated.jsonl`).
Every ledger that imports kiro re-reads that whole log, so the same turns land in every
ledger.

Measured in leg D:

| ledger | kiro rows |
|---|---|
| `workspace-off/.cage` | 22 |
| `workspace-on/.cage` | 28 |

**22 of the 28 rows in `workspace-on` are the same turns already in `workspace-off`.**

## What is *not* broken

- **Within** a ledger, dedupe is correct: a second import yields **0 new rows** (D5).
  Kiro row ids are content-derived and stable even though the `ts` is stamped at import
  time.
- Nothing is corrupted, and no single ledger over-counts.

## The consequence

**The two lab ledgers must never be summed for kiro.** For claude and copilot the
per-workspace stores keep the arms genuinely separate; for kiro they do not, because the
source is global.

This generalises beyond the lab: any user with more than one project ledger who imports
kiro into each will find the *same* kiro turns in all of them. Summing across roots — a
team roll-up, a manual `cat`, a per-project comparison — inflates kiro.

## Why it is structural, not a slip

A global per-machine log meeting per-workspace ledgers has no ledger-local way to know
another ledger already claimed a row. Cage's dedupe is per-ledger by design (append-only,
id-scoped). The candidate responses are therefore about **honesty**, not about a dedupe
fix:

- **document** it wherever kiro totals appear (the minimum), and/or
- **warn** — e.g. a doctor/report note when a kiro source is shared across ledger roots.

Neither is built. This finding records the defect; it does not pick the fix.

## Status history

- **2026-08-01** — filed OPEN from leg D cell D6, measured on two real lab ledgers.
