---
doc: how Copilot numbers are captured — the standing reference
status: current as of 2026-08-13 · shipped capture + the filed COPILOT-METRICS build
update-rule: ANY change to copilot capture (parser · source · schema field · pricing rung) updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# Copilot capture — how the numbers are made

One page: what cage records for Copilot, from where, and what it means.
Deep detail lives in the linked research/spec docs — not here.

## Captured today (shipped)

| number | store → prop | lands as |
|---|---|---|
| tokens in/out (VS Code chat) | `workspaceStorage/*/chatSessions/*.jsonl` → per-request `promptTokens`/`completionTokens` | `calls` row (`c_cop<hash>`, surface `vscode`) |
| credits per request (VS Code) | same row → `copilotCredits` (float, verbatim) | `calls.credits` — prices `copilot/auto` exactly (pricing rung 1) |
| tokens + cached (CLI) | `~/.copilot/session-state/*/events.jsonl` → `session.shutdown` per-model cumulative, delta'd | `calls` rows incl. `cached_in` (surface `cli`) |
| credits (CLI) | `session.shutdown` → `totalPremiumRequests` (float, cumulative, delta'd) | `calls.credits` (+ legacy int `premium`, unused by pricing) |
| group billing | `billed_with` — one carrier row per multi-model shutdown | siblings price $0 on the credits basis, by name |

- Capture is pull-based (`cage import` / capture-on-read) — no hooks, no network, $0.
- Dollars from credits = recorded count × your `[billing.copilot] usd_per_credit` —
  always **modeled**, never `measured`; rate unset ⇒ credits render as a count.
- Absence ≠ zero: a request with no recorded credit stays absent, never derived
  from tokens (either direction).

## Known gaps (open)

- **VS Code cached tokens** — the store now persists `modelTotals` per request
  (cached incl.); cage drops it. → COPILOT-METRICS.
- **`sessionCopilotCredits`** (authoritative session total) — not captured. → same.
- **Two chat roots missed** (`emptyWindowChatSessions/`, `transferredChatSessions/`)
  — those chats are invisible today. → same.
- **CLI credit-delta loss** (v0.44 review item 2) — credit delta dropped when the
  first-listed model has no token delta. Open defect, separate fix.
- **Cache-write tokens** — persisted by no Copilot store. Permanently honest-empty;
  not a cage gap.

## Next build (filed 2026-08-13 — COPILOT-METRICS)

`.cage/ledger/copilot/chats-YYYY-MM.jsonl`: per-chat metrics verbatim from **all
five** stores (chatSessions · CLI · agentHostUsage sidecar · extension debug-logs ·
OTel `agent-traces.db`) — closes the first three gaps above and adds per-model-call
cached tokens + nano-AIU. Capture-only; no reported number moves.
Spec: [copilot-metrics-ledger.handoff.md](copilot-metrics-ledger.handoff.md) ·
evidence: [research/2026-08-13-copilot-per-chat-usage-fetch-spec.md](research/2026-08-13-copilot-per-chat-usage-fetch-spec.md).

## Executive summary (for the meeting)

- We meter Copilot from its **own on-disk records** — no vendor API, no network,
  zero infra cost. Numbers are the vendor's, recorded verbatim.
- Per chat we can state: **tokens in/out**, and — where GitHub recorded it — the
  **actual billed credits** (premium requests). Credits are the billing truth;
  token-based dollars are estimates beside it.
- **Dollar figures are modeled, not invoiced**: recorded credits × our plan rate.
  Cage labels every such figure `modeled` and never lets it read as an invoice.
- **Coverage is partial by the vendor's doing**: only some requests carry a credit
  (~3% observed on real data — all on the auto-router, exactly where nothing else
  could price). Cage reports what exists; it never fills gaps with guesses.
- **Cache detail**: cache-read tokens land fully with the next build (already
  specced); cache-write is not recorded by Microsoft anywhere — nobody can
  report it, including us.
- **Trajectory**: the filed build adds a dedicated per-chat Copilot ledger from all
  five of Microsoft's stores — per-chat cached tokens and authoritative session
  credits, with zero settings required for the core numbers.

## Maintenance

Standing rule (frontmatter `update-rule`): a change to any copilot parser, source
path, schema field, or pricing rung updates this doc **in the same change** — stale
here = a missing changelog entry. Tracked in [DOC-REGISTRY.md](DOC-REGISTRY.md).
