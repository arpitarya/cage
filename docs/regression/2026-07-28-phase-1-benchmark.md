# Phase 1 BENCHMARK — what cage captures, and how correct it is

> **⚠ SUPERSEDED (2026-07-30) by
> [2026-07-29-phase-benchmark.md](2026-07-29-phase-benchmark.md).** Phase I's
> benchmark replaces this one as the current statement of what cage captures. This
> file is retained **unedited below the marker** as the published Phase-1 record —
> cite it as history, never as current coverage.
>
> _Banner only: it sits **above** the `HASH-COVERS-BELOW` marker, so the body and the
> published hash below are byte-identical to what was originally published._

**Benchmark sha256 (body below the marker):** `58948469192cae0620e08fa4a46538a818142be13c08b932b6f073238aa0cf4a`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
**Artifact type:** phase benchmark — the third kind after *run report* (one run)
and *finding doc* (one defect). It answers **"what does cage capture, and how
correct is it?"** across **all of Phase 1**. Spec: `cage/docs/phase1-closeout.plan.md`
§P5.

**Derived, never observed.** Every cell below cites a run report or finding doc.
This document introduces **no new number** — if a figure isn't already in a run
report or finding, its cell is UNPROVEN by definition.

**Sources** (read; nothing re-run): [run-002](runs/run-002/REPORT.md) ·
[run-003](runs/run-003/REPORT.md) · [HISTORY](HISTORY.md) · the five finding docs
+ the Kiro proxy probe + the capture-precision fixes in
`cage/docs/regression/2026-07-28-*` · `cage/docs/FORMULAS.md` §1.7.

---

## 1. Headline verdict (three lines)

- **claude — CLI: EXACT.** Every token field reconciles three ways
  (log recount = cage ledger = hand count) to the token. **VS Code: UNPROVEN** (P3).
- **copilot — CLI: EXACT** (post-fix). All captured fields reconcile to the token;
  two fields (`cache_write_in`, `gap_ms`) are honestly absent from the store, not
  wrong. **VS Code: UNPROVEN** (P3).
- **kiro — CLI: HONEST-LIMIT.** Credits captured (`estimated`); token counts are
  **null in the store and unrecoverable by vendor design — FINAL**, not a pending
  gap. **VS Code / IDE: UNPROVEN** (P3).

## 2. Coverage — stated up front

Phase 1 ran **6 of 12 cells: scripted CLI only.** The six CLI cells
(V1–V5b, ±graphify per agent) are proven; the six VS Code / IDE cells (V6–V11)
**did not run** — extensions can't be driven headlessly. Anything about a VS Code
surface below is **UNPROVEN**, not assumed-good.

| ran (6) | did NOT run (6) |
|---|---|
| claude CLI ±graphify (V1/V2) | claude VS Code ±graphify (V6/V7) |
| copilot CLI ±graphify (V3/V4) | copilot VS Code ±graphify (V8/V9) |
| kiro CLI ±graphify (V5/V5b) | kiro IDE ±graphify (V10/V11) |

**The three questions P3 (Arpit's manual sweep) still owes:**

1. Does the graphify PATH interceptor fire under the VS Code extensions at all?
   (The scripted CLI A/B already showed agents don't invoke graphify unprompted,
   so the honest expected answer may be "no" — [finding](../../cage/docs/regression/2026-07-28-finding-graphify-ab-no-fire.md).)
2. Are the claude CLI and VS Code stores distinguishable? — V1-vs-V6 on identical
   questions, the cleanest test the `surface=""` blank has ever had.
3. Does a VS Code / IDE surface carry any field the CLI store doesn't (or lose one
   it has)?

## 3. The accuracy summary — Arpit's actual question

```
agent    surface   verdict          proof
claude   CLI       EXACT            381,813 / 565,637 · 3-way · run-003
copilot  CLI       EXACT            227,298 / 233,675 · 3-way · run-003
kiro     CLI       HONEST-LIMIT     credits only; tokens null (FINAL)
*        VS Code   UNPROVEN         P3 pending
```

## 4. FINAL vs PENDING — the distinction this document must not blur

A limit is one of two kinds, and they are **not the same class of statement**:

- **FINAL** — the source carries no such number, closed by evidence. Reopening
  needs a vendor change, not a test.
- **PENDING** — merely untested in Phase 1. A test settles it.

| limit | kind | why |
|---|---|---|
| kiro CLI token counts (all four fields) null | **FINAL** | store fields null on every turn (floor + large); proxy route closed four independent ways ([P2 probe](../../cage/docs/regression/2026-07-28-kiro-proxy-probe.md); [FORMULAS §1.7](../../cage/docs/FORMULAS.md)) |
| copilot CLI `cache_write_in` absent | **FINAL** | field not present in the copilot store (run-002 §4) |
| copilot CLI `gap_ms` absent | **FINAL** | copilot log carries no per-turn timestamps (run-002 §4) |
| copilot / kiro / claude session name (CLI) | **FINAL** | store carries none / `latest_summary` null (run-002 §4) |
| **every VS Code / IDE cell** | **PENDING** | did not run in Phase 1 — P3 |
| claude CLI-vs-VS-Code distinguishability | **PENDING** | V6 not run — P3 |

"Kiro has no tokens" and "we haven't tested VS Code" are different statements.
This table keeps them apart.

## 5. The matrix — agent × surface × field

Legend — **method** = `measured` / `estimated` / absent · **verdict** = EXACT
(3-way reconciled) / HONEST-LIMIT (source has no number; recorded + tagged) /
UNPROVEN (untested) / WRONG (open defect).

### 5.1 claude / CLI — all token fields EXACT

| field | captured (method) | verdict | perm. | evidence |
|---|---|---|---|---|
| tokens_in | ✅ measured | EXACT | — | 381,813 (V1) / 565,637 (V2), log=cage=hand · run-002 §2, run-003 §1 |
| tokens_out | ✅ measured | EXACT | — | 3,395 / 5,292 · run-002 §2 |
| cached_in | ✅ measured | EXACT | — | 290,384 / 465,631 (Q3 read) · run-002 §2/§4 |
| cache_write_in | ✅ measured | EXACT | — | 91,193 / 99,968 (Q2 create) · run-002 §2/§4 |
| model | ✅ measured | EXACT | — | `claude-opus-4-8` · run-002 §4 |
| gap_ms | ✅ measured | EXACT | — | 4,416 ms turn gap present · run-002 §4 |
| session id | ✅ measured | EXACT | — | uuid per turn · run-002 §4 |
| session name | ⚠ measured (summary record) | HONEST-LIMIT | FINAL | `summary` record only, not a per-turn name · run-002 §4 |
| surface | `""` (honest blank) | HONEST-LIMIT | **PENDING** | CLI store carries no surface marker; blank is honest. Distinguishability from VS Code is the P3 test · run-002 §4/§5 |
| premium | absent | HONEST-LIMIT | FINAL | no premium-request concept for claude |
| credits | absent | HONEST-LIMIT | FINAL | no credits concept for claude |

### 5.2 copilot / CLI — EXACT after the delta-id fix

| field | captured (method) | verdict | perm. | evidence |
|---|---|---|---|---|
| tokens_in | ✅ measured | EXACT | — | 227,298 (V3) / 233,675 (V4), 3-way · run-003 §1. Pre-fix WRONG (189,788 / 191,414, −16.5% / −18.1%) → RESOLVED · [finding](../../cage/docs/regression/2026-07-28-finding-copilot-resumed-undercount.md) |
| tokens_out | ✅ measured | EXACT | — | 1,995 / 2,337 (truth), reconciled post-fix · run-002 §2, run-003 §1 |
| cached_in | ✅ measured | EXACT | — | 186,864 / 210,513 (`cacheReadTokens`) · run-002 §2/§4 |
| cache_write_in | absent | HONEST-LIMIT | **FINAL** | not present in the copilot store · run-002 §4 |
| model | ✅ measured | EXACT | — | mixed `claude-haiku-4.5` + `gpt-5-mini` · run-002 §4 |
| gap_ms | absent | HONEST-LIMIT | **FINAL** | copilot log has no per-turn timestamps; absence explicit, never faked · run-002 §4 |
| session id | ✅ measured | EXACT | — | uuid per session · run-002 §4 |
| session name | absent | HONEST-LIMIT | FINAL | none in the CLI store · run-002 §4 |
| surface | ✅ `"cli"` measured (store-derived) | EXACT | — | store-derived `cli` · run-002 §4 |
| premium | ✅ measured | EXACT | — | `totalPremiumRequests` cumulative → delta-fixed, 0.33→0.66 on real `8073abba` · [finding](../../cage/docs/regression/2026-07-28-finding-copilot-resumed-undercount.md), capture-precision §HIGH |
| credits | absent | HONEST-LIMIT | FINAL | no credits concept for copilot |

### 5.3 kiro / CLI (SQLite store) — credits captured; tokens FINAL-null

| field | captured (method) | verdict | perm. | evidence |
|---|---|---|---|---|
| tokens_in | null | HONEST-LIMIT | **FINAL** | store field null every turn; route closed 4 ways · [kiro finding](../../cage/docs/regression/2026-07-28-finding-kiro-cli-sqlite-credits.md), [P2 probe](../../cage/docs/regression/2026-07-28-kiro-proxy-probe.md) |
| tokens_out | null | HONEST-LIMIT | **FINAL** | `output_tokens` null · kiro finding |
| cached_in | null | HONEST-LIMIT | **FINAL** | `cache_read_input_tokens` null · kiro finding |
| cache_write_in | null | HONEST-LIMIT | **FINAL** | `cache_write_input_tokens` null · kiro finding |
| model | ⚠ measured `"auto"` | HONEST-LIMIT | FINAL (default) | `model_id="auto"` server-routed; an explicit `--model` surfaces a real name but `auto` is not persisted · kiro finding, capture-precision STEP 0 |
| gap_ms | derivable, not stamped | UNPROVEN | source: FINAL upside | store has ms `created_at`/`updated_at` (a real upside); cage emits credit rows, not gap-stamped call rows · run-002 §4 |
| session id | ✅ measured | EXACT | — | `conversation_id` uuid, per-directory · run-002 §4, kiro finding |
| session name | null | HONEST-LIMIT | **FINAL** | `latest_summary` null · run-002 §4 |
| surface | ✅ `"cli"` (declared-wins) | EXACT | — | `[sources.kiro] surface="cli"` now upgrades the built-in (collision fix) · [finding](../../cage/docs/regression/2026-07-28-finding-surface-restamp-collision.md) |
| premium | absent | HONEST-LIMIT | FINAL | no premium-request concept for kiro |
| credits | ✅ **estimated** | HONEST-LIMIT (the honest substitute) | FINAL | 12 (V5) / 15 (V5b) credit rows; `schema.make_credit`, recorded not priced; V5 0.197 credits / 5 turns, V5b 0.2368 / 7 · run-002 §2, run-003 §1, kiro finding |

**Why kiro is HONEST-LIMIT, not WRONG:** cage records exactly what the store
holds (credits + context %), tags it `estimated`, and states the token gap in
words. The proxy probe proves no `measured` path exists — so the estimated credit
row is the honest ceiling, not a defect.

### 5.4 all VS Code / IDE cells — UNPROVEN (P3)

Six cells (claude/copilot VS Code, kiro IDE, ±graphify) did **not run**. Per the
citation rule, every field in every one of these cells is **UNPROVEN**,
permanence **PENDING** — settled only by P3.

| field (all agents, VS Code/IDE) | verdict | perm. | evidence |
|---|---|---|---|
| tokens_in · tokens_out · cached_in · cache_write_in · model · gap_ms · session id · session name · surface · premium · credits | **UNPROVEN** | **PENDING** | not captured in Phase 1 — extensions can't be driven headlessly; P3 manual sweep · run-002 §5, run-003 §4 |

No VS Code cell is upgraded for tidiness. UNPROVEN staying UNPROVEN is what makes
the EXACT cells above worth believing.

## 6. Open defects

Two genuinely open; three closed and cited so the matrix cells above can lean on
them.

| finding | sev | status | note |
|---|---|---|---|
| [graphify shim recursion](../../cage/docs/regression/2026-07-28-finding-graphify-shim-recursion.md) | MED | **OPEN** | cage shim hardened (skips every interceptor, exit 127, re-entry guard); a **stale foreign dead-verb shim left on a real machine's PATH remains a hazard** the fix mitigates but cannot erase — reopens if a stacked-interceptor hang recurs in the wild |
| [graphify A/B didn't fire](../../cage/docs/regression/2026-07-28-finding-graphify-ab-no-fire.md) | — | **OPEN** (product-level) | savings path validated directly (11,810 raw → 118 actual → **11,692 saved**, modeled); but agents don't shell out to graphify unprompted, so A−B = 0 through no cage fault — Phase 2 driver change |
| [copilot resumed undercount](../../cage/docs/regression/2026-07-28-finding-copilot-resumed-undercount.md) | HIGH | ✅ RESOLVED | delta-id fix; self-heal 70,071 → 107,581 (+37,510 exact) → +0; verified run-003 8/8 |
| [kiro CLI SQLite / credits](../../cage/docs/regression/2026-07-28-finding-kiro-cli-sqlite-credits.md) | HIGH | ✅ CLOSED | credits parser shipped; exact-token route closed by [P2 probe](../../cage/docs/regression/2026-07-28-kiro-proxy-probe.md) |
| [surface-restamp collision](../../cage/docs/regression/2026-07-28-finding-surface-restamp-collision.md) | LOW | ✅ RESOLVED | declared `surface` now wins on built-in collision |

## 7. What this benchmark closes

- Phase 1's question — *what is captured, how correct is it* — is **answered for
  the 6 scripted CLI cells** and **explicitly deferred for the 6 VS Code cells**.
- The golden captures (`golden/captures/**`) are wired as the lab's **primary
  inputs** (`inputs.toml`); `samples/**` stays secondary/legacy.
- P4's Phase-2 sweep enriches this benchmark later (graphify A/B measured, the
  full 18-question set) — it does **not** gate this close.
