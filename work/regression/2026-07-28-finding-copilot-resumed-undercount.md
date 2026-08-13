# Finding — Copilot resumed sessions are undercounted

**Severity:** HIGH · **Status:** ✅ RESOLVED (fixed 2026-07-28) · **Surface:** copilot CLI

| field | value |
|---|---|
| Observed in | [run-002](2026-07-28-validation-run-002.md) (pre-fix — V3/V4 check 5 red) |
| Verified fixed in | [run-003](2026-07-28-validation-run-003.md) (V3/V4 8/8, self-heal proven) |
| Fix shipped | [capture-precision-fixes §HIGH](2026-07-28-capture-precision-fixes.md) · [ADR 0004](../../docs/adr/0004-append-only-delta-rows-and-separate-by-schema.md) |

## Status history

- **OPEN** (observed run-002): cage recorded 189,788 tokens_in for a copilot
  session that consumed 227,298 — a 37,510-token (16.5%) undercount; V4 the same
  at 191,414 vs 233,675 (42,261, 18.1%).
- **RESOLVED** (fixed 2026-07-28, re-verified run-003): fixed cage re-imports the
  same baseline logs to **exactly** 227,298 (V3) / 233,675 (V4), 8/8.

## Mechanism (the *why*, retained)

- `copilot -p --continue` appends a **second** `session.shutdown` whose
  `modelMetrics` are **cumulative** — they already include the earlier turn.
  Verified in session `8073abba`: shutdown-1 `inputTokens=70,071`, shutdown-2
  `inputTokens=107,581`.
- Pre-fix `parse_copilot_calls` derived the call id from the session id
  (idempotent so re-imports don't double-count). Inside one grown file the 2nd
  (higher, cumulative) shutdown was **deduped as a duplicate id and dropped** —
  Q3's entire marginal cost lost.
- **Blast radius:** any Copilot session that shuts down more than once —
  `--continue` scripting *and* a VS Code chat spanning app restarts/reloads. 16–18%
  here; unbounded in principle (longer resumed sessions lose more).

## The fix

- `transcript.parse_copilot_calls` now emits per-shutdown **delta** rows; the id
  carries the shutdown ordinal (**ord 0 byte-identical** to the legacy id, so
  history self-heals). `totalPremiumRequests` (also cumulative) gets the same
  delta treatment. Append-only; no row mutated.
- **Self-heal proof (real session `8073abba`):** legacy row 70,071 → re-import
  fixed parser → **107,581 exact** (+37,510, the exact undercount) → third import
  **+0**. No double count.
- Independent-recount note: `drive.py`'s `recount_copilot` was itself wrong at
  first (summed all shutdowns / read the pre-`data` shape) — both were driver bugs,
  fixed, re-verified. This is why reconciliation is *three*-way: a two-way check
  would have shared the recounter's failure mode.
