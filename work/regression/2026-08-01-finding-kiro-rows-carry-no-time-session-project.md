# Finding — kiro rows carry no time, no session and no project (the A/B is not reconstructible)

**Severity:** — (a limit of kiro's log, not a cage defect) ·
**Status:** ⬛ **HONEST-LIMIT — FINAL** unless kiro changes what it logs ·
**Surface:** kiro capture (IDE and CLI) ·
**From:** [2026-08-01 leg D run report](2026-08-01-leg-d-run-report.md), cells D5 + D6.

## What the rows actually carry

Measured over the 22 kiro rows in `workspace-off` (D5):

| field | value | consequence |
|---|---|---|
| `ts` | **identical on all rows** (`2026-08-01T05:56:04Z`) — stamped at *import* time | no ordering, no windowing, no per-cell separation |
| `session` | `"kiro"` — a synthetic constant | no session attribution |
| `project` | absent | no workspace attribution |
| `model` | `"agent"` — synthetic | no model attribution |
| `tokens_out` | 0 | input-only log |

## The limit is bigger than "estimated tokens"

The plan recorded kiro's limit as *credit-derived `estimated` input, `tokens_out = 0`* —
true, but incomplete. **The operative limit is that kiro rows carry no time, no session
and no project**, which removes them from every per-cell, per-arm and per-question
analysis cage performs.

**Therefore: the kiro A/B cannot be reconstructed from the ledger.** Not "hard to
separate" — D5 and D6 rows are **literally indistinguishable**. The only reason we know
~6 rows belong to D6 is the count difference between two imports taken five minutes
apart: an **operator observation, not a ledger fact**.

> **No kiro ON/OFF token delta may ever be reported.** Reporting one would be a
> fabrication.

## What is *not* claimed

The rows' rising token progression (13 → 182) is **consistent with** one accumulating
conversation. That is an inference from the numbers — the log does not state it, and this
finding does not assert it.

## What still passes, and matters

- **Re-import is idempotent: 0 calls, 0 files.** Despite the read-time `ts`, kiro row ids
  are content-derived and stable — the volatile timestamp does **not** duplicate rows.
- `surface = ide` is correct.
- Pricing is honest: `unpriced_rows = 0`, totals rounding to **$0.00** at display
  precision. Cage does not invent a cost it cannot know.

## Why FINAL, not OPEN

Cage can never be more precise than its source. Kiro's `tokens_generated.jsonl` does not
record a per-turn timestamp, a session id, or a workspace, so no cage change can recover
them. The earlier attempt at a higher-fidelity route is already closed negative
([2026-07-28 kiro proxy probe](2026-07-28-kiro-proxy-probe.md)).

**Reopen only if kiro changes what it logs** — a per-turn `ts`, a real session id, or a
workspace field appearing in the source would make this contingent again, and only then.

## Related

- [kiro rows double-count across ledgers](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md)
  — the other half of "one global log, many ledgers".
- [2026-07-22 finding — kiro empty](2026-07-22-finding-kiro-empty.md) ·
  [2026-07-28 kiro-cli sqlite credits](2026-07-28-finding-kiro-cli-sqlite-credits.md).

## Status history

- **2026-08-01** — filed HONEST-LIMIT (FINAL) from leg D cells D5/D6. Extends the
  previously documented "credit-derived `estimated` / `tokens_out = 0`" limit to the
  time/session/project axis, which is what actually blocks the A/B.
