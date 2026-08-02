---
doc: proposal — COPILOT-CREDITS: capture billed credits, price copilot by ladder
status: proposed (design spec — verdict C ACCEPTED 2026-08-02) — PICKED UP: ../copilot-credits.handoff.md + ../copilot-credits.prompt.md (Opus)
raised: 2026-08-02
verdict-from: ../compare/copilot-pricing-basis.compare.md
evidence: ../research/copilot-vscode-token-sources.md
---

# Proposal — COPILOT-CREDITS: both axes, one job each, a ladder decides the cell

**What ships:** cage captures the billed credits Copilot already persists per request,
keeps tokens as the cross-agent denominator, and resolves each copilot USD cell by
ladder — **credits × configured rate → token × price-table → loudly UNPRICED** — with
the winning rung named. Retires the copilot/auto $0 hole (24/60 real calls, 975k
tokens) with the recorded billing signal.

## 1 · Capture (additive, substrate-minimal)

| source | field captured | lands as |
|---|---|---|
| VS Code chatSessions, per request | `copilotCredits` | new **additive optional** call field `credits` (recorded verbatim, float; absent ⇒ legacy contract) |
| Copilot CLI `session.shutdown` | `totalPremiumRequests` delta | already captured as `premium` — read side treats it as that row's credits (no rewrite) |
| agentHostUsage sidecar (`totalNanoAiu`) | — | **deferred** — debug-gated + session-lifetime files ([research](../research/copilot-vscode-token-sources.md) §2b); revisit trigger R3 of the compare |

- Credits are **never derived from tokens** and never back-filled — absence stays
  absence (the standing `prices.toml` rule, both directions).
- `schema.make_call` gains `credits: float = 0.0` at the end of `CALL_FIELDS`
  (additive; old ledgers parse unchanged, byte-identical re-render).

## 2 · Policy — the rate is yours, off by default

```toml
# .cage/cage.toml — routing/decisions file (not prices.toml: the rate is YOUR
# plan economics, not a vendor rate card row)
[credits.copilot]
usd_per_credit = 0.04    # your overage rate; unset ⇒ rung 1 skipped, credits still shown
```

No rate ⇒ credits render as a **count**, never a dollar. The monthly included
allowance is deliberately NOT modeled (see §6).

## 3 · The ladder (per copilot row, derive-time)

1. `credits × usd_per_credit` — row carries recorded credits AND the rate is set.
   Tag: `credits` (recorded count × policy rate — `modeled`, never `measured`).
2. `tokens × price-table` — existing family/alias/exact matching, unchanged.
3. **UNPRICED** — loud, counted, runnable fix line, as today.

One rung wins per row; mixed-basis totals are footnoted with the split (same
discipline as the UNPRICED ⚠). Non-copilot rows: nothing changes anywhere.

## 4 · Example CLI outputs (the contract-by-example; goldens will pin the real ones)

### `cage report --by agent --usd` — before

```
agent    calls     tok in  tok out                   cost
-------  -----  ---------  -------  ---------------------
copilot     60  1,968,011   96,212   $3.5900 (+ unpriced)
⚠ 24 calls (975,210 tokens) UNPRICED — totals understated
  fix: cage prices alias - 'copilot/auto' --to <provider>/<model>
```

### after (rate configured)

```
$ cage report --by agent --usd
Ledger by agent · usd

agent    calls     tok in  tok out      cost    gross  net vs spend
-------  -----  ---------  -------  --------  -------  ------------
copilot     60  1,968,011   96,212   $4.1852  $0.3000       -$3.8852
claude       2    912,400   61,200   $3.6552  $0.4800       -$3.1752
TOTAL       62  2,880,411  157,412   $7.8404  $0.7800       -$7.0604

· copilot priced on two bases: 31 calls by credits×rate (14.87 cr → $0.5948),
  29 calls by token×table ($3.5904) — `cage query copilot-credits`
≈ priced by family (approximate — no exact price row):
  copilot/claude-sonnet-4.6 → claude-sonnet-4-6
```

The ⚠ block disappears only because every former-UNPRICED row carried credits — a
credit-less `copilot/auto` row STILL prints the ⚠ with both fixes:

```
⚠ 3 calls (81,004 tokens) UNPRICED — totals understated
  fix: cage prices alias - 'copilot/auto' --to <provider>/<model>
  or:  set [credits.copilot] usd_per_credit — 3 of these rows carry recorded credits
```

### after (rate NOT configured — credits shown, never priced)

```
· copilot: 31 calls carry recorded credits (14.87 cr) — not priced;
  set [credits.copilot] usd_per_credit to use them (`cage query copilot-credits`)
⚠ 24 calls (975,210 tokens) UNPRICED — totals understated
```

### `cage insights chats` (SHIPPED v0.42 — this work adds the credits column)

```
chat                              agent    surface  calls    tok in   cached  tok out  credits      cost
--------------------------------  -------  -------  -----  --------  -------  -------  -------  --------
fix wiring liveness detector      copilot  vscode      14   412,331        —   18,240     6.50   $0.2600
cage report cache split           claude   cli          9   902,114  801,332   41,008        —   $1.2087
9f42c1d3 (untitled)               copilot  cli          7   221,458   64,110    9,332     2.00   $0.0800

· cost basis per row: credits×rate where recorded, else token×table (`—` = not recorded)
```

### CSV (`--csv`) — the rung survives as a column, `—` never enters data

```csv
agent,surface,session,calls,tokens_in,cached_in,tokens_out,credits,cost_usd,priced_via
copilot,vscode,549dd02f,14,412331,,18240,6.50,0.2600,credits-rate
copilot,cli,9f42c1d3,7,221458,64110,9332,2.00,0.0800,credits-rate
claude,cli,54b2ee8d,9,902114,801332,41008,,1.2087,token-table
```

### `cage doctor` — coverage line (advisory, never a failure)

```
credits   ok — copilot credits on 31/60 rows (vscode store); rate set ($0.04/cr)
```

## 5 · Method & law compliance

- Determinism: same ledger + same policy ⇒ same table (credits are ledger fields;
  the rate is policy). No clocks, no quota state.
- Method law: rung-1 cells are `modeled` (recorded count × configured rate) — the
  count is fact, the dollar is policy; never rendered `measured`.
- Honesty: rung named per row (text footnote + `priced_via` CSV column — the exact
  `receiptprice` pattern); mixed-basis totals footnoted; `—` never enters CSV.
- `cage query copilot-credits` explains the ladder; FORMULAS gains the rung table.

## 6 · Deliberately not taken (with triggers)

- **Monthly included-allowance modeling** (marginal-$0 inside quota): needs
  wall-clock month state and per-plan quota facts — breaks "derive from ledger +
  policy alone". Trigger: only if a recorded per-row "included vs overage" flag ever
  appears in the stores.
- **nano-AIU → USD conversion**: no published rate card; invented precision.
  Trigger: GitHub publishes one (cite it in prices.toml like every price row).
- **Sidecar capture**: debug-gated, dies with the session — parked until R3 evidence.

## 7 · Tests & graduation

Tests: capture (vscode credits parsed, verbatim, absent-stays-absent) · ladder
selection per row · rate-unset ⇒ count-only rendering · mixed-basis footnote ·
UNPRICED both-fixes block · CSV `priced_via` · legacy ledger byte-identical without
credits · determinism. Graduates to a plan entry + FORMULAS section on pickup;
handoff/prompt pair when scheduled. CHATS-VIEW shipped v0.42 mid-session — this
work extends the built view with the credits column (+ its golden re-bless).
