# Copilot in VS Code: where per-chat token in/out/cached actually lives — and what cage should take from it

*Research note, 2026-08-02 (Cowork). Sources: VS Code `main` (sparse-cloned 2026-08-02:
`src/vs/workbench/contrib/chat/…`), `microsoft/vscode-copilot-chat` `main`, cage's own
real-store samples (`samples/agent-artifacts/copilot/real-vscode/`), and the public docs
cited at the bottom. Trigger: "can we look up tokens by chat title, since id-based isn't
great?" — answered in §3.*

---

## 1. What VS Code shows, per chat

Four distinct surfaces, in decreasing durability:

**a) The context-usage ring** — bottom-left of the chat input, per session. Shows
`used / context-window tokens, %`. Click/hover opens **Session Info**
(`chatContextUsageWidget.ts` / `chatContextUsageDetails.ts`): **Session Cost** (Copilot
credits — premium requests), a **Context Window** bar (used tokens, completion tokens,
output-buffer reserve), and a **prompt-composition breakdown** (`promptTokenDetails`:
category / label / `percentageOfPrompt` — instructions, tools, history, …). The data
object is `IChatContextUsageData {usedTokens, completionTokens, totalContextWindow,
percentage, outputBufferPercentage, promptTokenDetails, sessionCost}`.

**b) The Chat Debug view** (`⋯ → Show Chat Debug View`) — per **model call**: model,
`inputTokens`, `outputTokens`, **`cachedTokens`**, `totalTokens`, time-to-first-token,
duration, status (proposed API `chatDebug`, `ChatDebugModelTurnEvent`). **This is the
only per-call surface that shows cached tokens.** The **Cache Explorer** view adds cache
hit rates and tokens reused.

**c) The status-bar Copilot dashboard** — monthly premium-request quota %. Not per-chat.

**d)** Third-party `LanguageModelChatProvider` models currently display **0 tokens**
(vscode#309207) — the display is fed by the provider's usage report, not by VS Code
counting.

## 2. Where it persists on disk (the part cage can eat)

### 2a. The chatSessions store — what cage already reads, now with two unread columns

`<vscode-user>/workspaceStorage/<hash>/chatSessions/<sessionId>.jsonl`. Per request, VS
Code persists (`ISerializableChatRequestData`/`ISerializableChatResponseData`,
`chatModel.ts` ~1785–1833, write site ~1693–1702):

```
requestId, timestamp, modelId,
promptTokens, completionTokens, outputBuffer,
promptTokenDetails[{category,label,percentageOfPrompt}],
copilotCredits, sessionCopilotCredits,
elapsedMs, timeSpentWaiting
```

- **`promptTokens`/`completionTokens`** — cage's `parse_copilot_vscode_calls` already
  captures these, keyed by `requestId` hash. ✅
- **`copilotCredits` / `sessionCopilotCredits`** — **NOT captured.** This is the actual
  billing unit (premium requests), persisted per request. It prices `copilot/auto`
  **exactly**, no model table needed.
- **`elapsedMs` / `timeSpentWaiting`** — NOT captured; direct feed for the near-empty
  `gap_ms` human-attention axis.
- **No cached-token field is persisted here.** `promptTokenDetails` is percentages of
  prompt composition, not cache figures. An honest-empty `cached` column for the vscode
  surface is *correct* against this store.
- The `kind:0` record's `inputState.selectedModel.metadata` carries **`family` and
  `version`** — the concrete model behind `copilot/auto` (cage's own samples show
  `claude-haiku-4.5`, `mai-code-1-flash`, `mai-code-1-flash-tertiary`). Session-level,
  so approximate when auto re-routes mid-session — a label, not a billing basis.

### 2b. NEW: the agent-host usage sidecar — per-call cached tokens + real model + cost

`<vscode-user>/agentHostUsage/<sessionId>.jsonl` (`agentHostUsageSidecar.ts`;
`buildAgentHostUsageUri(environmentService.userRoamingDataHome, rawSessionId)`).
One line per **model call**:

```
{turnId, model, inputTokens, outputTokens, cacheReadTokens, totalNanoAiu, ts}
```

Everything the chatSessions store lacks: **`cacheReadTokens`**, the **real routed
model** per call, and **`totalNanoAiu`** (Copilot AIU billing, nano units). Two hard
caveats, stated in the source itself:

- **Debug-gated**: written only while `chat.agentHost.agentDebugLog.enabled` (agent-host
  sessions) / `github.copilot.chat.agentDebugLog.fileLogging.enabled` is on —
  "per model call, debug-gated, best-effort diagnostics".
- **Deleted with the session**: a `SessionRemoved` notification deletes the sidecar. So
  import promptly; the cage ledger is the durable copy.

The host-side store (Copilot CLI session DB, `turns.usage` — always-on, all providers,
incl. `copilotUsage.totalNanoAiu` and `autoModeResolved.chosenModel`, i.e. **what auto
actually picked, with reasoning bucket**) would be even better, but VS Code's own
renderer can't read it — "the session data directory's path is never published to
clients". Not a cage target until its location/format is published; `events.jsonl`
still only carries usage at `session.shutdown` (cage's cumulative-delta parser stands).

## 3. The title question: label yes, key no

The idea on the table: *"based on chat title we can look for token in/token out,
because based on id it isn't very great."*

The title is the wrong **key** and cage is already using it as the right **label**:

- A chat's title is `customTitle` (user-set, renameable at any time) or the first
  request's `generatedTitle` (auto). It is **mutable** (a rename would orphan
  previously-keyed rows and double-count on re-import), **non-unique** (same title
  across chats/workspaces collides), and **late** (empty until the first response).
  Cage's idempotency contract — deterministic id, `append_new` dedup, re-import adds
  zero rows — only survives on immutable keys: `sessionId` (the store filename) and
  `requestId` (already sha1-hashed into `c_cop<hash>`).
- Cage already lifts the title for humans: `session_name_copilot_vscode` resolves
  `customTitle` → `generatedTitle` → `""` and `_lift_names` stores it against the
  session, so per-chat reporting groups by id and *displays* the title. If chats show
  as bare UUIDs anywhere in `cage report`, that's a display bug to fix in report
  output, not a reason to re-key capture.

So: **keep id-keyed capture, spend the effort on the two columns the store already
persists but cage drops** (§2a) — that's where "id isn't very great" actually bites,
because the id that hurts is `modelId: copilot/auto`, not the session key.

## 4. What cage should do (ranked, evidence-backed)

1. **Capture `copilotCredits`/`sessionCopilotCredits` from chatSessions** and treat
   credits as the pricing basis for the vscode surface (premium requests × plan rate),
   with token-pricing as the estimate fallback. Directly retires the
   **copilot/auto UNPRICED** finding (24/60 real calls, 975k tokens at $0) with the
   *actual* billing signal instead of a price-table alias. Schema note: cage already
   stamps `premium` on CLI rows (`totalPremiumRequests` delta) — this is the same
   semantic, per-request instead of per-shutdown.
2. **Resolve `copilot/auto` to a concrete label** from `kind:0`
   `selectedModel.metadata.family`/`version` when `modelId == copilot/auto` — stamp as
   model (or a `model_hint` field) so family pricing can match. Approximate
   (session-level); #1 stays authoritative for cost.
3. **Add the `agentHostUsage/` sidecar as a third copilot source** (behind the existing
   two): per-call `cacheReadTokens` (fills the vscode `cached` column), real per-call
   model, `totalNanoAiu`. Doctor should say when the debug setting is off ("sidecar
   absent — enable `chat.agentHost.agentDebugLog.enabled` for cached-token capture")
   rather than reading absence as breakage — same discipline as the capture-health fix.
   Import-promptly caveat documented (files die with their sessions).
4. **Lift `elapsedMs`/`timeSpentWaiting` into `gap_ms`** for vscode rows — the
   human-attention axis is populated on 371/36,451 rows today; this is a free feed.
5. **Leave `cached` honest-empty for chatSessions-only capture** — the store genuinely
   doesn't persist it; fabricating from `promptTokenDetails` percentages would violate
   counts-never-content and honesty-first.

## Sources

- [Ken Muse — Decoding Copilot Token Costs Using VS Code](https://www.kenmuse.com/blog/decoding-copilot-token-costs-using-vs-code/) (Chat Debug view: `usage` with `prompt_tokens`, `completion_tokens`, `cached_tokens`, `cache_creation_input_tokens`; `copilot_usage.token_details` nano-AIU costs)
- [VS Code docs — Optimize AI credit usage](https://code.visualstudio.com/docs/agents/guides/optimize-usage) (Agent Debug Logs summary, Cache Explorer, status-bar dashboard)
- [VS Code blog — Improving token efficiency](https://code.visualstudio.com/blogs/2026/06/17/improving-token-efficiency-in-github-copilot) (cache-state transparency is roadmap)
- [vscode#309207 — third-party providers show 0 tokens](https://github.com/microsoft/vscode/issues/309207) (context-usage ring mechanics, `setUsage` path)
- [vscode#251807](https://github.com/microsoft/vscode/issues/251807) / [vscode-copilot-release#7823](https://github.com/microsoft/vscode-copilot-release/issues/7823) (real-time display feature requests — still open)
- VS Code source (`main`, 2026-08-02): [`chatModel.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/chat/common/model/chatModel.ts) (serialized usage fields), [`chatService.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/chat/common/chatService/chatService.ts) (`IChatUsage`), [`agentHostUsageSidecar.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/chat/browser/chatDebug/agentHostUsageSidecar.ts) (sidecar format + gating), [`chatContextUsageWidget.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/workbench/contrib/chat/browser/widgetHosts/viewPane/chatContextUsageWidget.ts) (the ring), [`sessionState.ts`](https://github.com/microsoft/vscode/blob/main/src/vs/platform/agentHost/common/state/sessionState.ts) (`autoModeResolved.chosenModel`, `totalNanoAiu`)
- [vscode-copilot-chat `vscode.proposed.chatDebug.d.ts`](https://github.com/microsoft/vscode-copilot-chat/blob/main/src/extension/vscode.proposed.chatDebug.d.ts) (`cachedTokens` per model turn)
