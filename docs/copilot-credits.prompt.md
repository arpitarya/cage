# Claude Code prompt: COPILOT-CREDITS — billed credits + the copilot pricing ladder

**Model:** Opus — this change touches the substrate contract (`CALL_FIELDS` gains an
additive field, plan §3 amended) and adds a pricing rung with its own method-tag
discipline; the rubric routes any substrate/method change to Opus even when additive
and specced.

You are implementing COPILOT-CREDITS: capture the billed `copilotCredits` Copilot
persists per request, and resolve copilot USD by ladder — credits × configured rate →
token × price-table → loudly UNPRICED. The full spec is
[docs/copilot-credits.handoff.md](copilot-credits.handoff.md); design of record is
[docs/proposals/copilot-credits.proposal.md](proposals/copilot-credits.proposal.md)
(its §4 example outputs are the rendering contract-by-example); the decision behind
it is [docs/compare/copilot-pricing-basis.compare.md](compare/copilot-pricing-basis.compare.md)
(verdict C — do not re-litigate). Read all three first; Definition of Done and
Non-negotiables are binding.

## Context to load first

- `CLAUDE.md` (laws: substrate contract, determinism, method, honesty, two error
  regimes, $0/stdlib).
- `cage/schema.py` (`CALL_FIELDS`, `make_call` — `premium`/`cache_write_in` are the
  additive precedents) · `cage/transcript.py` `parse_copilot_vscode_calls` ·
  `cage/prices.py` (`call_usd`/`call_usd_match`) · `cage/policy.py` (`_TWO_LEVEL`,
  `_PRICE_SECTIONS`) · `cage/report.py` (⚠/footnote machinery) · `cage/chats.py`
  (shipped v0.42 — extend, don't rebuild) · `cage/csvout.py` ·
  `cage/receiptprice.py` (the ladder PATTERN — rung footnote + `priced_via`; do NOT
  modify it) · `data/prices.toml` copilot comment block · `data/cage.toml`.

## Task

Per the handoff: (1) additive `credits` field on call rows + plan §3; (2) vscode
capture verbatim (absent stays absent; zero is a real zero); (3) the ladder at ONE
pricing choke point so report/budget/chats/compare/verdict all inherit it; (4)
`[credits.copilot] usd_per_credit` policy key — **resolve the handoff §10 shape
question first** (verify `policy.load` merge; fall back to `[billing.copilot]` and
amend the proposal in the same change if it collides); (5) rendering per proposal §4:
mixed-basis split footnote, second runnable fix line in the ⚠ block, rate-unset
advisory, chats credits column, CSV `priced_via`, doctor coverage line; (6)
explain entry + FORMULAS + docs.

## Required workflow

1. **Explore** the named files; confirm the real choke point (`call_usd` vs its
   callers) and the `[credits]` merge behavior before deciding the key's home.
2. **Plan** — files to change, the choke-point choice, the §10 resolution, the
   golden set you expect to re-bless; pause for confirmation.
3. **Implement incrementally** — schema+capture → ladder → surfaces → tests green at
   each step.
4. **Update docs to match** (handoff §9.5): PLAN §3, FORMULAS, README, CHANGELOG,
   explain_data, GLOSSARY, commented `[credits.copilot]` block in `data/cage.toml`,
   DOC-REGISTRY bumps, WORKLOG + IMPLEMENTATION entries. **CLAUDE.md: propose the
   edit and flag for Arpit's review — never silently rewrite.** On green: archive
   the proposal AND this handoff/prompt pair per the lifecycle (headers naming the
   living spec), proposals/README → Graduated, OPEN-WORK row deleted.
5. **Verify**: `just test` — 0 fail; re-blessed goldens diff-reviewed one by one
   (only spec-changed lines may move); legacy no-credit ledger renders
   byte-identical except specced advisory lines.

## Constraints (hard)

- stdlib only · derive-time only · ledger never rewritten · no backfill.
- **Never derive credits from tokens, either direction.** Absence stays absence;
  recorded zero is a real zero.
- Rung-1 cells are `modeled` — a `measured` tag here is a spec violation.
- ONE ladder implementation — a second copy in any view is a spec violation.
- Do not modify: `receiptprice.py` · savings/receipt pricing · `netsaved.py` ·
  kiro/claude parsers · the CLI copilot cumulative-delta id scheme.
- `—` never enters CSV; UNPRICED never silently $0; no new deps, no new required
  config (rate unset must ship clean).

## Acceptance criteria (self-check before finishing)

- [ ] Every Definition-of-Done box in the handoff checks true.
- [ ] §10 shape question resolved explicitly (key home named in the plan step);
      proposal amended if the fallback was taken.
- [ ] Ladder inherited by every USD consumer with zero per-view forks.
- [ ] Suite 0 fail; goldens re-blessed only where specced; legacy byte-identity test
      green; determinism test green.
- [ ] Docs per §9.5 incl. archives + Graduated index + OPEN-WORK deletion;
      CLAUDE.md edit proposed, not applied.

## Tests

`tests/test_copilot_credits.py`: capture (verbatim/absent/zero/malformed) · rung
selection incl. rung-1-beats-UNPRICED · rate-unset count-only · mixed-basis footnote
split · both-fixes ⚠ block · chats credits column (`—` text / absent CSV) · CSV
`priced_via` · legacy ledger byte-identity · determinism. `just test`.

## Guardrails

- Ask before: touching anything on the do-not-modify list, changing `CALL_FIELDS`
  order (append only), or re-blessing a golden whose diff you can't trace to a
  specced line.
- If the choke point turns out NOT to be one place (callers price independently),
  STOP and report — unifying that is its own decision, not a silent refactor.
- If `copilotCredits` in the real store turns out to be a different unit/shape than
  the research doc describes, STOP, record the finding in a dated research doc, and
  ask.
