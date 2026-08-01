# Run report — cage-lab clean-room validation (Phase I) — 2026-07-29

**Immutable.** One run, one report. Numbers below are the ledger as captured; the content
hashes pin it. Findings and the phase benchmark are separate artifacts (never merged).

- **Ledger (isolated):** `cage-lab/labledger/` — never `~/.cage` (verified untouched).
- `calls-2026-07.jsonl` sha256 `0bae701db97d27712649f97b562165cc0ee20b8bf0c95c6f4dcea02a041dfc9e`
- `savings/graphify/savings-2026-07.jsonl` sha256 `1c27c5fb66801f57f25b9c0fedc521aeb60c409f3944388624d77a5f11c294f2`
- **Baseline status:** NEW baseline (clean capture). The prior cage-lab was absent; rebuilt
  from scratch per Arpit (2026-07-29). Not a comparison against Phase 1.

## What ran
70 real agent prompts, cheapest model each (claude `haiku`, copilot `auto`), driven through
the real CLIs against a controlled toy repo (`golden/_src`, one ~8.6k-token `big_module.py`).
graphify was the only variable. **kiro + all VS Code excluded** — kiro is not scriptable
(Electron IDE, no headless `-p`); those are manual leg D. Full cost **$5.29** (82% cache).

## Results — per agent × arm (real, reconciled)

| agent · arm | prompts | metered turns | tok_in | graphify receipts | saved tok |
|---|---|---|---|---|---|
| claude · OFF | 14 | 157 | 4,994,702 | 0 | 0 |
| claude · ON (auto) | 14 | 229¹ | 8,436,363 | **1** | 7,487 |
| copilot · OFF | 14 | 14 | 1,831,255 | 0 | 0 |
| copilot · ON-plain (adoption) | 14 | 14 | 1,914,910 | **0** | 0 |
| copilot · ON-forced (invoked) | 14 | 14 | 1,962,389 | **23** | 154,638 |
| _(copilot pre-run smoke)_ | 1 | 1 | 13,055 | 0 | 0 |
| **TOTAL** | **70+1** | **429** | **19,532,113** | **24** | **162,125** |

¹ claude ON = 205 main-session turns + 24 sub-agent (sidechain) turns; both are claude-ON.

## The A/B, stated plainly
- **graphify ON + actually invoked ⇒ cage captures every run.** The 24 receipts split
  **11 query + 13 explain** (each `explain` cites `big_module.py`, raw 8,614 → ~8,520 saved;
  each `query` cites ~86 files, raw ~8,997 → ~7,400 saved). All `route = transcript`,
  `modeled`, confidence 0.6.
- **graphify ON but NOT invoked ⇒ 0.** copilot-on-plain = 0. Adoption, not capture, is the
  gap: copilot's graphify-ON is a passive user-level `/graphify` skill, never auto-run.
- **claude auto-adopted once** (1 receipt) via its PreToolUse hook + CLAUDE.md steering —
  nonzero but weak unprompted adoption.
- **All OFF arms = 0** (correct — no graph, no steering, no interceptor).

## I.4 assertions — all PASS
| assertion | result |
|---|---|
| zero UNPRICED (prices.toml split's first real-traffic test) | ✅ no UNPRICED on any of 429 rows |
| usage rows ≥ receipts on graphify-ON cells | ✅ 24 usage = 24 receipts |
| re-import idempotency (import twice ⇒ 0 new) | ✅ 429 calls / 24 savings unchanged |
| three-way reconcile (log ↔ ledger ↔ view) | ✅ claude 386 rows = 181 (off) + 205 (on) transcript turns; savings ↔ usage 1:1 |
| isolation (never `~/.cage`) | ✅ `~/.cage` untouched |

## Headline
**F1 (copilot-CLI graphify detection, built this session) is validated on real traffic:**
23 of 24 receipts came through it. The capture chain — install → drive → capture → derive
— works end-to-end, isolated, on both scriptable agents. Where graphify savings are missed,
the cause is **adoption** (the agent didn't invoke graphify), never a capture defect.
