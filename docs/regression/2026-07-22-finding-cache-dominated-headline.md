# Finding — Headline token/$ is 98% cache reads (`cache-dominated-headline`)

**Severity:** MEDIUM · **Status:** ✅ RESOLVED (**v0.34.0**) · **Surface:** `report --usd` presentation

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) (98.0% cache-read share) |
| Fix shipped | **v0.34.0** — cache-efficiency footer line in `report --usd` |

## Status now

RESOLVED. Not a bug — a reporting-honesty gap: the default view didn't separate
cache-read cost from fresh cost, so "8.2 billion tokens, $7,046" read as alarming
when it's almost entirely prefix-cache re-reads billed at ~0.1×. v0.34.0 added a
footer line that splits it.

## Evidence (as observed 2026-07-22)

The run's cache split (see [lab-run-001](2026-07-22-lab-run-001.md)): **98.0%** of
`tokens_in` were cache reads, fresh input only ~162M. The `$7,046` headline was
dominated by cache-read billing, not fresh generation, and the default view didn't
say so.

## History

**2026-07-22 (observed, lab-run-001):** 98.0% cache-read share; proposed a
cache-efficiency line/column in `report --usd`. No new logging (reporting/UX
addition).

**v0.34.0 (RESOLVED):** one new footer line in `report --usd`:
`· cache: {tok%} of input tokens were cache reads, {cost%} of cost ($x of $y)`.
The cost split uses the model's **real `cache_read` price row**
(`report._cache_read_usd`, resolved via `policy.price`) — not a hardcoded 0.1× — so
it stays correct if pricing changes. No table/column/CSV structure change;
`summarize()` gains one `cache_usd` field on the existing payload. Verified: on a
1M-token / 950k-cached synthetic call the line reads exactly `95% of input tokens
were cache reads, 63% of cost` — the cost share is meaningfully smaller than the
token share, precisely the honesty signal this finding asked for.
