# Handoff: COPILOT-CREDITS — capture billed credits, price copilot by ladder

**One-liner:** capture the `copilotCredits` Copilot persists per request as an
additive call field, and resolve every copilot USD cell by ladder — credits ×
configured rate → token × price-table → loudly UNPRICED.
**Owner / executor:** Claude Code.
**Status:** Ready to build.
**Stress-tested (2026-08-02):** the fork was debated to a decision in
[compare/copilot-pricing-basis.compare.md](compare/copilot-pricing-basis.compare.md)
(verdict C ACCEPTED — both axes, one job each, never blended; reopen triggers R1–R3).
Packaging surfaced two NEW items: (a) this touches the **substrate contract**
(`CALL_FIELDS` + a pricing-method discipline) → **Opus tier**, plan §3 amended in the
same change; (b) `[credits.copilot] usd_per_credit` is a scalar under a table whose
existing shape is per-provider/per-model `per_mtok` multiplier rows — collision risk
named in §10 with a decided fallback, not left to improvisation. Residual risk:
`copilotCredits`' unit may shift between VS Code releases — recorded verbatim, so a
shift changes labels, never invents numbers.

## 1. Context & background

Design of record: [proposals/copilot-credits.proposal.md](proposals/copilot-credits.proposal.md)
(the §4 example outputs are the rendering contract-by-example; goldens pin the real
bytes). Evidence: [research/copilot-vscode-token-sources.md](research/copilot-vscode-token-sources.md).
Retires the copilot/auto $0 hole (24/60 real calls, 975k tokens —
regression 2026-07-22) with the billing signal GitHub itself computed.
`cage insights chats` shipped v0.42 — this work **extends** it with the credits column.

## 2. Definition of done

- [ ] `schema.make_call` accepts additive optional `credits: float = 0.0`, appended to
      `CALL_FIELDS`; old ledgers parse and re-render byte-identically; plan §3 updated.
- [ ] `transcript.parse_copilot_vscode_calls` records per-request `copilotCredits`
      verbatim (absent ⇒ 0/absent, never derived); CLI path unchanged (`premium`
      already captured; the read side treats it as that row's credits).
- [ ] ONE pricing choke point implements the ladder for copilot rows (rung order:
      credits×rate → token×table → UNPRICED); every consumer
      (report/budget/chats/compare/verdict) inherits it — no per-view forks.
- [ ] Policy key `[credits.copilot] usd_per_credit` (cage.toml side — routing/plan
      economics, NOT prices.toml): unset ⇒ rung 1 skipped, credits render as a count
      only (never a dollar). See §10 for the shape-collision fallback.
- [ ] Rendering matches the proposal §4 shapes: mixed-basis footnote with the split ·
      the ⚠ UNPRICED block gains the second runnable fix line when credit-less rows
      remain · rate-unset advisory line · chats credits column (`—` in text, absent
      in CSV) · CSV `priced_via` column (`credits-rate` | `token-table`).
- [ ] `cage doctor` credits coverage line (advisory `ok`/info — never a failure).
- [ ] `cage query copilot-credits` concept entry (code_refs + plan_ref); FORMULAS
      gains the rung table; method tag: rung-1 cells are `modeled`, never `measured`.
- [ ] Legacy/no-credit ledgers: all existing goldens byte-identical except where the
      new advisory lines are specced; full suite green (1148 baseline + new).
- [ ] Documentation per §9.5.

## 3. Scope

**In:** schema field · vscode transcript capture · the ladder at the pricing choke
point · policy key + `policy.load` merge · report/chats/CSV/doctor/explain/FORMULAS
surfaces · tests/goldens.
**Out (explicit):** monthly included-allowance modeling · nano-AIU→USD conversion ·
agentHostUsage sidecar capture (all three parked WITH triggers in the proposal §6) ·
`elapsedMs`→gap_ms (separate OPEN-WORK item) · any receipt/savings change
(`receiptprice` ladder untouched) · deriving credits from tokens or back-filling ·
kiro/claude pricing (unchanged everywhere).

## 4. Current state

- Baseline: v0.42 in tree, suite 1148/0. Read first: `cage/schema.py`
  (`CALL_FIELDS`/`make_call` — `premium`/`cache_write_in` are the additive-field
  precedents), `cage/transcript.py` (`parse_copilot_vscode_calls` ~L347;
  `_COPILOT_*_KEYS`), `cage/prices.py` (`call_usd`/`call_usd_match` — the likely
  choke point), `cage/policy.py` (`_TWO_LEVEL`/`_PRICE_SECTIONS` — how `[credits]`
  merges), `cage/report.py` (footnote/⚠ machinery), `cage/chats.py` (shipped view to
  extend), `cage/csvout.py`, `cage/receiptprice.py` (the ladder PATTERN to copy —
  rung footnote + `priced_via` — not the code to touch), `data/prices.toml` copilot
  comment block (the standing never-blur rule), `docs/proposals/copilot-credits.proposal.md`.
- Precedent for "recorded count, policy rate, modeled tag": kiro-CLI credit rows.

## 5. Technical approach (decided — do not re-litigate)

- Verdict C (compare doc): credits = what was billed; tokens keep every existing job
  (savings axis, attrib, budget denominators). Axes never blended in a cell.
- Field name `credits`, float, recorded verbatim — unit-agnostic by design.
- Ladder lives ONCE, at the same layer `call_usd` serves today; rung named per row
  (text footnote + CSV `priced_via`), mixed totals footnoted with the split.
- CLI rows: `premium` (per-shutdown delta, stamped on the shutdown's first model
  row) reads as that row's credits — totals correct; per-model attribution of a
  multi-model shutdown is knowingly coarse (footnote-grade, not a blocker).

## 6. Non-negotiables / constraints

- **$0 / stdlib only · fail-open write path · derive-time only** (ledger never
  rewritten; no backfill).
- **Method law:** rung-1 is `modeled` — a `measured` anywhere here is a spec
  violation. **Never derive credits from tokens, in either direction** (the
  standing `prices.toml` rule).
- **Determinism:** same ledger + policy ⇒ same bytes; no clocks, no quota state.
- **Honesty:** UNPRICED stays loud; `—` never enters CSV; absence stays absence.
- **Do not touch:** `receiptprice.py` rungs · savings/receipt pricing · `netsaved` ·
  kiro/claude parsers · the CLI copilot parser's cumulative-delta id scheme.

## 7. Dependencies & prerequisites

None external. No new config required to ship (rate unset = count-only display).

## 8. Edge cases & risks

- Credits present, rate unset → count shown, advisory line, row prices by rung 2/3.
- Credits absent, model priced → rung 2 exactly as today (byte-identical goal).
- `copilotCredits: 0` recorded (included/0x model) → a REAL zero: rung 1 prices it
  $0.0000 with rung named — distinct from absent. · Fractional credits → float,
  rendered 2dp. · Malformed field → skip, absent semantics (fail-open). · A row
  with credits AND an unpriced model → rung 1 wins, ⚠ shrinks accordingly.
- Old cage reading a new ledger: unknown key tolerated by readers (verify — if any
  strict reader exists, that's a finding to fix, not to work around).

## 9. Testing & validation

`tests/test_copilot_credits.py`: capture verbatim/absent/zero/malformed · ladder
selection per row incl. rung-1-wins-over-unpriced · rate-unset count-only · mixed
split footnote · both-fixes ⚠ block · CSV `priced_via` · chats credits column ·
legacy ledger byte-identity · determinism. Re-bless only the goldens the spec
changes (`CAGE_BLESS_GOLDENS=1`), diff-review each. Run: `just test` → 0 fail.

## 9.5 Documentation impact

- [ ] **PLAN.md §3** — the additive `credits` field (substrate contract change).
- [ ] **CLAUDE.md** — Unit→USD / per-call-cost bullets gain the copilot ladder
      sentence; ⚠️ propose, surface for Arpit's review — never silently rewrite.
- [ ] **FORMULAS.md** — the rung table + method tags. **README** — a "What's new"
      line. **CHANGELOG** — entry under next version.
- [ ] **explain_data.py** — `copilot-credits` entry. **GLOSSARY** — *credit (copilot)*.
- [ ] **data/cage.toml** — commented `[credits.copilot]` example block (inert).
- [ ] **compare doc** — no change (already DECIDED); **proposal** — archive per the
      lifecycle on green (`docs/archive/vX.Y-copilot-credits.proposal.md`, header
      naming the living spec), proposals/README → Graduated, OPEN-WORK row deleted
      after IMPLEMENTATION.md records it; this handoff/prompt pair archived too.
- [ ] **DOC-REGISTRY** — bump every touched row. **WORKLOG/IMPLEMENTATION** — entries.
- N/A: ADR — promote the ladder to an ADR only if it becomes load-bearing beyond
  copilot (the compare doc's graduation note).

## 10. Open questions

- OPEN QUESTION (decided fallback, verify then choose): `[credits]` currently holds
  per-provider/per-model `per_mtok` multiplier rows; `[credits.copilot]
  usd_per_credit` puts a scalar at the model level of that shape. **Verify
  `policy.load`'s two-level merge tolerates it; if it collides, use `[billing.copilot]
  usd_per_credit` instead and amend the proposal §2 in the same change** — either
  spelling is acceptable; a silent half-merge is not.
- OPEN QUESTION (display only): credits column format `6.50` vs `6.5 cr` in chats —
  executor picks per column-width, golden pins.
