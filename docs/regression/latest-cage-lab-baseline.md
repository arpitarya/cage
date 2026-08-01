# 2026-07-25 — cage-lab correctness baseline

Black-box matrix against the shipped wheel (cage 0.36.0). **16/16 scenarios pass.** Every asserted number reconciles to a hand-authored `reference/` file three independent ways (lab recount · cage report/CSV/rollup cross-check · lab-priced USD), reads run twice byte-identical.

## Matrix

| scenario | verdict | proves |
|----------|---------|--------|
| M1 | ✓ pass | claude solo (shared store, honest surface="") |
| M2 | ✓ pass | copilot solo (cli+vscode split, premium, customTitle ladder) |
| M3 | ✓ pass | kiro solo (surface=ide, volatile ts, priced via kiro proxy) |
| M4a | ✓ pass | claude CLI alone — still surface="" (honest, WHY in eyeball) |
| M4b | ✓ pass | copilot CLI alone — surface=cli, premium present |
| M4c | ✓ pass | kiro has NO CLI surface — assert the honest gap, fabricate nothing |
| M5a | ✓ pass | claude VS Code alone — the one honest blank surface |
| M5b | ✓ pass | copilot VS Code alone — surface=vscode, customTitle ladder, UNPRICED |
| M5c | ✓ pass | kiro IDE — kiro's only surface |
| M6 | ✓ pass | kiro+copilot combined — one sweep, manifest per (agent,surface,session) |
| G1 | ✓ pass | graphify solo — one saving, no calls |
| G2 | ✓ pass | graphify + claude — saving coexists with calls |
| G3 | ✓ pass | graphify + copilot — UNPRICED calls don't poison savings |
| G4 | ✓ pass | graphify + kiro — saving on the thinnest log |
| G5 | ✓ pass | graphify+kiro+copilot — native-shim dedupe ⇒ EXACTLY ONE saving |
| MIG | ✓ pass | savings migration precision — NOT WRONG, NOT DUPLICATED |

## Findings

- **[spec-correction] kiro-priced-not-unpriced** (not a cage bug) — cage-lab-plan.md M3/M5b call kiro 'agent' UNPRICED; the shipped bundle PRICES it via [prices.kiro.agent] (sonnet 3/15/0.3). cage is correct; the spec line is stale. Lab references corrected to $0.0201 for the kiro fixture.

## Real-ledger L-labs (read-only)

```
L-labs (READ-ONLY on ~/.cage)
  ------------------------------------------------------------
  L1 spend per agent × surface: 39020 calls across 4 (agent,surface) cells
     claude-code    —       calls=38571  tok_in=8,949,197,929
     codex          —       calls=373    tok_in=18,425,552
     copilot        —       calls=60     tok_in=2,164,279
     kiro           —       calls=16     tok_in=198
  L2 savings reality: 0 savings receipt(s) in the tree/legacy
  L4 UNPRICED population (UPPER BOUND — lab exact-match only, not cage's family/alias/normalized matching): 6 (provider,model) pair(s): ∅/copilot/auto, anthropic/claude-haiku-4-5-20251001, anthropic/claude-haiku-4.5, anthropic/copilot/claude-haiku-4.5, anthropic/copilot/claude-opus-4.6, anthropic/copilot/claude-sonnet-4.6
  L5 manifest coverage: 0% of call-sessions have a manifest row (0 manifest sessions)

  (read-only: no import, no write, no mutation performed)
```

_PII-safe: counts never content, tilde paths, no usernames._
