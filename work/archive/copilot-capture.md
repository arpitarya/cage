---
doc: how Copilot numbers are captured — the standing reference
status: current as of 2026-08-13 · shipped calls capture + shipped COPILOT-METRICS
update-rule: ANY change to copilot capture (parser · source · schema field · pricing rung) updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# Copilot capture — how the numbers are made

**Design of record: [ADR-COPILOT](adr/0002_copilot.md).** This doc is the *field* reference —
what is captured today. The ADR is the *why*, and wins where the two disagree.

One page: what cage records for Copilot, from where, and what it means.
Deep detail lives in the linked research/spec docs — not here.

## Captured today (shipped)

**`calls` rows — priced, the money surface.**

| number | store → prop | lands as |
|---|---|---|
| tokens in/out (VS Code chat) | `workspaceStorage/*/chatSessions/*.jsonl` → per-request `promptTokens`/`completionTokens` | `calls` row (`c_cop<hash>`, surface `vscode`) |
| credits per request (VS Code) | same row → `copilotCredits` (float, verbatim) | `calls.credits` — prices `copilot/auto` exactly (pricing rung 1) |
| tokens + cached (CLI) | `~/.copilot/session-state/*/events.jsonl` → `session.shutdown` per-model cumulative, delta'd | `calls` rows incl. `cached_in` (surface `cli`) |
| credits (CLI) | `session.shutdown` → `totalPremiumRequests` (float, cumulative, delta'd) | `calls.credits` (+ legacy int `premium`, unused by pricing) |
| group billing | `billed_with` — one carrier row per multi-model shutdown | siblings price $0 on the credits basis, by name |

Chats land from **four** chatSessions roots now (COPILOT-METRICS): the per-workspace
store, `no-workspace/`, plus `emptyWindowChatSessions/` and `transferredChatSessions/` —
previously only the first two were swept.

- Capture is pull-based (`cage import` / capture-on-read) — no hooks, no network, $0.
- Dollars from credits = recorded count × your `[billing.copilot] usd_per_credit` —
  always **modeled**, never `measured`; rate unset ⇒ credits render as a count.
- Absence ≠ zero: a request with no recorded credit stays absent, never derived
  from tokens (either direction).

**`.cage/ledger/copilot/` rows — capture-only, COPILOT-METRICS (shipped 2026-08-13).**
A second, deliberately separate row kind (`schema.make_copilot_metric`) — never a
widened `calls` row, never priced, **not yet read by any derived view**. Verbatim
per-chat facts from all five on-disk stores:

| source | store | what lands |
|---|---|---|
| `chat` | VS Code chatSessions (same 4 roots as above) | per-request `model_totals` (per-model cached tokens), `session_credits` (max/last, never summed), `elapsed_ms`/`waiting_ms` |
| `cli` | `session-state/*/events.jsonl` | per-shutdown **cumulative-verbatim** `model_totals`, `credits`, `nano_aiu` — no delta math |
| `sidecar` | `agentHostUsage/*.jsonl` (gated: `chat.agentHost.agentDebugLog.enabled`) | per-model-call tokens + cached + `nano_aiu`, the REAL routed model |
| `debuglog` | `.../debug-logs/<sessionId>/*.jsonl` (gated: `github.copilot.chat.agentDebugLog.fileLogging.enabled`) | per-request tokens + ttft (whitelist read — the same lines carry prompt bodies) |
| `otel` | `agent-traces.db`, SQLite read-only (gated: `github.copilot.chat.otel.dbSpanExporter.enabled`) | per-model-call tokens + cached (the only per-call cached-token source for classic-extension chats) |

`ledger.copilot_metrics()` collapses last-write-wins per `(source, session, surface,
request, call)`; `cage doctor`'s `copilot-metrics` check names per-source coverage and
the enabling setting for each gated store. `cage query copilot-metrics` explains it.

## Known gaps (open)

- **CLI credit-delta loss** (v0.44 review item 2) — credit delta dropped when the
  first-listed model has no token delta. Open defect in the *calls* CLI parser only —
  the metrics CLI parser records cumulative verbatim and structurally dodges it.
- **Cache-write tokens** — persisted by no Copilot store. Permanently honest-empty;
  not a cage gap.
- **No read surface yet for `.cage/ledger/copilot/`** — a `cage insights copilot` view
  or new chats-view columns are parked in `work/OPEN-WORK.md`, not built.

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
- **A second, richer ledger now exists alongside the priced one**: per-chat cached
  tokens, authoritative session credits, and — where three optional VS Code settings
  are on — per-model-call detail from three more stores. Recorded, not yet surfaced:
  no report reads it yet, so today it is evidence banked for the next read-surface
  build, not a number anyone sees.

## Maintenance

Standing rule (frontmatter `update-rule`): a change to any copilot parser, source
path, schema field, or pricing rung updates this doc **in the same change** — stale
here = a missing changelog entry. Tracked in [DOC-REGISTRY.md](../work/DOC-REGISTRY.md).
