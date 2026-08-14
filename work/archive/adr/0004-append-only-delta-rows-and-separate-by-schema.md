# ADR 0004 — Reconcile a cumulative source with append-only delta rows; separate row kinds by schema, not by source

- **Status:** Accepted (v0.37, unreleased; capture-precision §3.1, §3.4)
- **Date:** 2026-07-28
- **Deciders:** Arpit (ratifier), Claude Code (executor)

## Context

- Golden-set Phase 1 found two capture defects with the same root shape: a source
  reports usage in a form cage's row model didn't fit.
- **Copilot** writes a *cumulative* `session.shutdown` per shutdown. A resumed session
  (`--continue`, or a VS Code chat spanning restarts) appends a second shutdown whose
  `modelMetrics` already include the first. Cage keyed the call id on session+model
  index only, so the second (higher) shutdown collided with the first and was
  dedup-dropped — a **16–18% undercount**, unbounded in principle. Verified on real
  session `8073abba`: shutdown-1 `inputTokens=70,071`, shutdown-2 `107,581`.
- **Kiro CLI** reports **credits + context %**, never token counts — the token fields in
  its SQLite store are null even with an explicit non-`auto` model (proven by the §0
  probe). A call row with `tokens_in=0` would be a lie that poisons every token average
  and cost-per-call.
- The report's suggested Copilot fix — "on re-seeing a session id, *update* the row to
  the last cumulative" — mutates a ledger row. That breaks four standing guarantees at
  once (append-only, determinism, crash-safety, concurrent-import safety) and is *less*
  precise (it collapses the per-turn breakdown into one moving number).

## Decision

**A cumulative source is reconciled with append-only *delta* rows, and a source whose
usage has a different shape gets its own row *kind* — decided on schema, never by
identity of the source.**

- **Copilot (delta rows).** Each `session.shutdown` yields a row carrying the
  per-shutdown **delta** (`cumulative_n − cumulative_{n-1}` per model). The id encodes
  the shutdown **ordinal**; **ordinal 0 is byte-identical to the pre-fix id** (no
  suffix), and delta-from-nothing equals the raw first value. So a *legacy* ledger
  self-heals on re-import: ord 0 dedupes against the row already there, only ord≥1 delta
  rows append, and the rows *sum* to the true cumulative. `totalPremiumRequests` is
  cumulative too and gets the same delta treatment. No row is ever mutated.
- **Kiro credits (a distinct kind).** Credits are recorded as their own row kind
  (`credits-<month>.jsonl`, `schema.make_credit`, `unit="credits"`) with their own id
  namespace, read by **no** call-based view — so they can never perturb a token or cost
  number. Tagged `method="estimated"` (a proxy, never `measured`) and **recorded, not
  priced** by default (an unattested credit→USD rate is a guess wearing a number).
- **The dividing line is schema.** Copilot's usage *is* tokens → it stays a call row (as
  deltas). Kiro's usage is *not* tokens → a new kind. We do **not** fork storage per
  agent; we fork it per *shape of the number*.

## Consequences

- History self-heals rather than double-counting: the one property that makes shipping
  the fix safe against ledgers already in the field.
- Append-only / determinism / idempotency / method-law all hold unchanged — the fix is
  designed *around* them, not against them.
- A grown cumulative source now costs one extra row per shutdown (Copilot) or per
  resumed conversation (Kiro credits, collapsed last-write-wins-per-session by
  `ledger.credits`). Rows are cheap; precision is not.
- Credit rows exist in the ledger but have no report surface yet (recorded, not priced) —
  a deliberate parked edge, not a `# v2:` half-build.

## Alternatives rejected

- **Mutate the row to the latest cumulative** (the report's suggestion) — breaks
  append-only, determinism, crash-safety, concurrent-import safety; and is *less* precise
  (loses the per-turn breakdown). Rejected outright.
- **A fresh id for every shutdown** (drop ord-0 identity) — a legacy ledger would then
  add ord 0 twice (70,071 double-counted). The byte-identity of ord 0 is exactly what
  makes self-heal work.
- **A Kiro `tokens_in=0` call row** — poisons every average and cost-per-call; the lie is
  worse than the gap. Rejected.
- **Separate ledgers per agent** — separation by *source* is arbitrary; the real axis is
  schema. Copilot doesn't warrant its own store; Kiro credits do — because the *number*
  is a different shape, not because it's a different tool.

## Reference

- Worked example, real data: Copilot session `8073abba` — delta rows sum to 107,581
  (`70,071 + 37,510`), recovering the exact V3 undercount (37,510) and reaching the
  hand-counted truth 227,298. Self-heal proof executed end-to-end (legacy row → re-import
  → exact total → third import adds 0). capture-precision plan §3.1, §3.4;
  `cage-lab/golden/findings/VALIDATION-REPORT.md`.

## Veto condition (when to revisit)

1. **Falsifiable trigger (measurement-gated).** Revisit the delta-row design only if a
   **measured** case appears where per-shutdown deltas cannot reconstruct the true
   cumulative — e.g. a source that *rewrites* an earlier shutdown's figure downward
   (a non-monotonic cumulative), so `cumulative_n − cumulative_{n-1}` goes negative and a
   delta row can't represent it. **Name the session and the two figures** when reopening;
   an argument that it "might" happen is not enough. The change would land in
   `transcript.parse_copilot_calls` (clamp/negative handling), not a storage redesign.
2. **Contingent vs. invariant.** *Contingent:* which sources are cumulative (Copilot
   today; another client could join) — auto-revisit on evidence. *Invariant (product
   value, moves only by reversing this ADR):* **no ledger row is ever mutated**, and a
   credit-derived or reconstructed number is **never `measured`**. These do not bend to
   volume or convenience.
3. **Deliberately not taken.** Pricing Kiro credits into USD is left open, not rejected:
   record credits now, and add a credit→USD conversion **only** when a real credit rate
   is attested (the same evidence bar as a human timesheet). Until then a credit row
   carries no cost — recorded, honest, unpriced.
