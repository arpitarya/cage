---
doc: research — the definitive fetch spec for Copilot per-chat tokens in/out, cached, and credits
date: 2026-08-13
verified-against: microsoft/vscode `main` (sparse clone 2026-08-13) · microsoft/vscode-copilot-chat `main` (clone 2026-08-13) · cage HEAD (`transcript.py`, real-store probes of 2026-08-02)
relates: copilot-vscode-token-sources.md (2026-08-02 desk study) · 2026-08-02-copilot-credit-fields-real-stores.md (real-store probe)
---

# Copilot per-chat usage: where every number lives, exactly

Question answered: **for every chat, how do we fetch token in, token out, cached
tokens, and credits — which directory, which file, which row, which property.**

Five distinct on-disk sources exist. Two are always-on and durable; three are
opt-in (debug/telemetry settings). One value — **cache-write tokens — is persisted
nowhere** and cannot be fetched from any store today.

All macOS paths below; `<User>` = `~/Library/Application Support/Code/User`
(`Code - Insiders` for Insiders). On Linux `~/.config/Code/User`, on Windows
`%APPDATA%\Code\User`.

---

## The answer in one table

| value | best always-on source | best per-model-call source (opt-in) |
|---|---|---|
| token in (per request) | chatSessions row → `promptTokens` | sidecar row → `inputTokens`; OTel db → `spans.input_tokens` |
| token out (per request) | chatSessions row → `completionTokens` | sidecar row → `outputTokens`; OTel db → `spans.output_tokens` |
| cached in (read) | chatSessions row → `modelTotals[].cachedTokens` **(agent-host sessions only — NEW)**; CLI shutdown → `cacheReadTokens` delta | sidecar row → `cacheReadTokens`; OTel db → `spans.cached_tokens` |
| cached out (write) | **nowhere** | **nowhere** |
| credits (per request) | chatSessions row → `copilotCredits` (float) | sidecar row → `totalNanoAiu / 1e9` |
| credits (per session, authoritative) | chatSessions row → `sessionCopilotCredits` (max, not sum); CLI shutdown → `totalPremiumRequests` delta (float!) | — |

---

## Source 1 — VS Code chatSessions store (always-on, durable; cage reads this today)

**Directories** (all four must be swept; cage currently reads only the first):

```
<User>/workspaceStorage/<workspace-hash>/chatSessions/     ← normal workspace chats
<User>/globalStorage/emptyWindowChatSessions/              ← chats in windows with no folder open
<User>/workspaceStorage/no-workspace/chatSessions/         ← older empty-window variant
<User>/globalStorage/transferredChatSessions/              ← sessions moved between windows
```

(`chatSessionStore.ts` lines 71–79: `workspaceStorageHome/<id>/chatSessions`,
`globalStorageHome/emptyWindowChatSessions`, `no-workspace/chatSessions`,
`transferredChatSessions`.)

**File**: `<sessionId>.jsonl` — an operation log (default; `chat.useLogSessionStorage`
!== false) — or legacy flat `<sessionId>.json`. The jsonl is append-mostly: initial
`kind:0` state records plus mutation records; a request's fields can be updated by
later lines, so **last-write-wins per `requestId`** when folding.

**Row**: each serialized request (`ISerializableChatRequestData`, which extends
`ISerializableChatResponseData` — `chatModel.ts` ~1826–1843, written by `toJSON()`
~1712–1738). Key by `requestId`. Usage props per request:

| prop | meaning | caveat |
|---|---|---|
| `promptTokens` | input tokens | describes the turn's **most recent model call**, not the whole turn |
| `completionTokens` | output tokens | running per-turn count (summed across the turn's calls) |
| `modelTotals` | **NEW** — `[{model, inputTokens, cachedTokens, outputTokens}]` | whole-turn per-model sums **including subagent calls and compaction**; supplied only by agent-host sessions today (`IChatUsageModelTotal`, `chatService.ts` 169–192). **This is the only durable, ungated cached-token figure.** |
| `copilotCredits` | float credits billed for this turn | container-scoped: summing across requests is only a **lower bound** on the session (source comment, `chatService.ts` 181–187) |
| `sessionCopilotCredits` | running whole-session credits as reported by the backend | authoritative; covers out-of-turn work (compaction). Take **max/last per session, never sum**. Was absent in the VS Code 1.126 probe — present in current builds. |
| `outputBuffer`, `promptTokenDetails` | context-ring internals | `promptTokenDetails` is `{category,label,percentageOfPrompt}` — percentages, NOT cache figures |
| `elapsedMs`, `timeSpentWaiting` | wall time / time blocked on user confirmation | direct feed for `gap_ms` |
| `modelId` | selected model id | often the virtual `copilot/auto` |

**Where credits come from** (agent-host path, `stateToProgressAdapter.ts`
`usageInfoToChatUsage`): `copilotCredits = copilotUsage.totalNanoAiu / 1e9`,
`sessionCopilotCredits = copilotUsage.sessionTotalNanoAiu / 1e9`. So **1 credit
(premium request) = 1e9 nano-AIU** — the two units are the same scale, which
retires the "no nano-AIU rate card" blocker for *relative* accounting (USD still
needs the plan's per-credit rate).

**Resolving `copilot/auto`**: session-level, the `kind:0` record's
`inputState.selectedModel.metadata.family` / `.version`. Per-call, only the
sidecar (source 3) or the CLI state's `autoModeResolved.chosenModel` carry the
real routed model.

## Source 2 — Copilot CLI session state (always-on; cage reads this today)

**Directory**: `$COPILOT_HOME` if set, else `~/.copilot` → `session-state/<sessionId>/`
(`copilotHome.ts`, `copilotAgentSession.ts` line 353). VS Code **agent-host chat
sessions are Copilot CLI sessions** — they write here too; `vscode.metadata.json`
inside the session dir marks the VS Code-hosted ones (`copilotAgent.ts` 2585).

**File**: `events.jsonl`. Usage exists **only on the `session.shutdown` event**
(verified CLI 1.0.65; `buildSessionEvents.ts` writes no per-turn usage), and it is
**cumulative across the whole session** — a resumed session writes a second
shutdown with larger numbers. Fetch = delta against the previous shutdown
(cage's parser already does this).

**Props on `session.shutdown`** (per model, plus session-level):

| prop | meaning | caveat |
|---|---|---|
| per-model `inputTokens` | cumulative input | **already includes cache read + write** — do not add cache to it |
| per-model `outputTokens` | cumulative output | |
| per-model `cacheReadTokens` | cumulative cache read | the CLI surface's cached-in figure |
| `totalPremiumRequests` | cumulative credits | **float** (real value 0.33) — `int()` floors it to 0; this exact bug shipped and was fixed by the `credits` float field |
| `totalNanoAiu` | cumulative nano-AIU | ÷ 1e9 = credits; same counter, finer grain |

Known open defect (v0.44 review, item 2): in `transcript.py` copilot-CLI loop,
`if not (din or dout): continue` runs after `prev_cred` advances but before the
credit delta is stamped → the credit delta is lost when the first-listed model
has no token delta. The fetch spec above is what the code *should* implement.

## Source 3 — agent-host usage sidecar (per-model-call; debug-gated)

**Directory + file**: `<User>/agentHostUsage/<sanitizedSessionId>.jsonl`
(`buildAgentHostUsageUri(userRoamingDataHome, sessionId)` — `agentHostUsageSidecar.ts` 52).

**Row** (one per model call, `IAgentHostUsageRecord`):

```json
{"turnId": "...", "model": "...", "inputTokens": N, "outputTokens": N,
 "cacheReadTokens": N, "totalNanoAiu": N, "ts": "ISO"}
```

All fields except `turnId`/`ts` optional. Per-call credits = `totalNanoAiu / 1e9`.
`model` is the **real routed model** per call (resolves `copilot/auto` exactly).

**Gate**: `chat.agentHost.agentDebugLog.enabled` (agent-host sessions; wired in
`agentHostChatDebugProvider.ts` 130). **Lifecycle hazard**: the file is deleted
when the host reports `SessionRemoved`, and deletion is *deliberately not gated*
on the setting — import promptly; the ledger is the durable copy. A sibling
`agentHostCustomizations/<sessionId>.json` records loaded skills/hooks/MCP.

## Source 4 — copilot-chat extension debug logs (per-request; debug-gated)

**Directory + file**:
`<User>/workspaceStorage/<hash>/GitHub.copilot-chat/debug-logs/<sessionId>/main.jsonl`
(child/subagent sessions: `<label>-<childSessionId>.jsonl` in the parent's dir).

**Gate**: `github.copilot.chat.agentDebugLog.fileLogging.enabled` — the canonical
toggle (`agentDebugLog.enabled` is deprecated; VS Code's own code comments say
"only fileLogging.enabled is authoritative"). Retention caps: 50 session logs,
100 MB/session.

**Row**: span entries; the model-call ones are `type: "llm_request"` with
`attrs: {model, inputTokens, outputTokens, ttft, ...}`. **No cached-token field
survives into this file** (the in-memory Chat Debug view shows `cachedTokens`,
but the file serializer — `chatDebugFileLoggerService.ts` ~917 — writes only
input/output). Least useful of the five for cage; listed for completeness.

## Source 5 — OTel SQLite span store (per-model-call, SQL-queryable; opt-in) — NEW FIND

**Path**: `<User>/globalStorage/github.copilot-chat/agent-traces.db`
(`services.ts` ~270: `globalStorageUri + 'agent-traces.db'`).

**Gate**: `github.copilot.chat.otel.dbSpanExporter.enabled` (default false;
enabling it implies the OTel pipeline on, no endpoint needed — "db-only mode").

**Rows**: table `spans`; model calls are `operation_name = 'chat'`. Denormalized
columns (from OTel gen_ai attributes):

```
request_model, response_model, conversation_id, chat_session_id, turn_index,
input_tokens, output_tokens, cached_tokens, reasoning_tokens, ttft_ms,
start_time_ms, end_time_ms
```

`cached_tokens` ← `gen_ai.usage.cache_read.input_tokens` ← the CAPI response's
`usage.prompt_tokens_details.cached_tokens` (`chatMLFetcher.ts` 386). A built-in
`sessions` VIEW aggregates per session (`total_input_tokens`,
`total_output_tokens`, `total_cached_tokens`, `llm_calls`, `tool_calls`).
Overflow attrs land in `span_attributes (span_id, key, value)`.

This is the **only per-model-call cached-token source for the classic extension
surface** (the sidecar covers only agent-host sessions), and it's SQL, WAL-mode,
read-only-safe — the same discipline cage already uses for Kiro's SQLite store.

## Cache write ("cached out"): a firm no

Checked everywhere: the attribute constant
`gen_ai.usage.cache_creation.input_tokens` exists in `genAiAttributes.ts` but
**no producer sets it**; `APIUsage` (`openai.ts`) models only
`prompt_tokens_details.cached_tokens` (read); the sidecar record has only
`cacheReadTokens`; chatSessions has no cache field outside `modelTotals[].cachedTokens`
(read); model metadata's `cacheWriteCost` is a *price* (credits per 1M tokens),
not a count. **Honest-empty is correct for cache-write on every Copilot surface.**
(Anthropic-style `cache_creation_input_tokens` appears only in the transient
Chat Debug request inspector, never on disk.)

---

## Deltas since the 2026-08-02 research (what changed)

1. **`modelTotals` is new and durable**: chatSessions now persists per-request,
   per-model `{inputTokens, cachedTokens, outputTokens}` for agent-host sessions.
   The old conclusion "no cached-token field in chatSessions, sidecar is the only
   source" is **stale** — the sidecar is now the *per-call* refinement, not the
   only path. Cage's vscode parser should read it.
2. **`sessionCopilotCredits` exists now** (absent in the 1.126 probe) and is
   documented in-source as authoritative (max/last per session, never summed).
   Cage's "deliberately not captured" stance should soften to
   *captured-as-session-collapse*, same shape as Kiro credits.
3. **credits ≡ nano-AIU / 1e9** — confirmed in `stateToProgressAdapter.ts`. The
   CLI's `totalNanoAiu` can therefore price sessions at finer grain than
   `totalPremiumRequests`, in the same unit.
4. **The OTel SQLite store is new** (source 5) — first SQL-queryable per-call
   store on the extension path, with cached tokens.
5. **Extra chatSessions roots** (emptyWindow / no-workspace / transferred) —
   chats there are invisible to a `workspaceStorage/*/chatSessions` glob.
6. The CLI session-state path is now openly constructed in VS Code source
   (`~/.copilot/session-state/<id>/`) — the "path never published" note is stale
   for the events store (the *turn-level* host DB remains unpublished).

## What cage should implement (ranked)

1. **Read `modelTotals` in `parse_copilot_vscode_calls`** → fills `cached_in` for
   agent-host chatSessions rows, durable and ungated. Prefer its per-model sums
   over `promptTokens`/`completionTokens` when present (they are whole-turn,
   include subagents).
2. **Capture `sessionCopilotCredits`** as a last-per-session collapse (Kiro-credits
   shape); keep per-request `copilotCredits` as the row-level fact.
3. **Sweep the three extra chatSessions roots.**
4. **Sidecar import** (already planned as COPILOT-CREDITS rung 3): per-call
   cached + real routed model + `totalNanoAiu/1e9`; doctor advisory when the
   setting is off; import promptly (deleted with session).
5. **Fix the CLI credit-delta loss** (v0.44 review item 2) — the continue-before-
   stamp ordering bug.
6. **Optional fourth source**: `agent-traces.db` behind
   `otel.dbSpanExporter.enabled` — per-call cached tokens for classic extension
   chats; read-only SQLite, same pattern as Kiro.
7. **Keep cache-write honest-empty** everywhere; document why in doctor output.

## Verification commands (run on the Mac, read-only)

```bash
# 1. chatSessions: which requests carry which usage props
for f in ~/Library/Application\ Support/Code/User/workspaceStorage/*/chatSessions/*.jsonl; do
  python3 -c "
import json,sys
props=set()
for line in open(sys.argv[1],encoding='utf-8'):
    try: o=json.loads(line)
    except: continue
    s=json.dumps(o)
    for k in ('promptTokens','completionTokens','copilotCredits','sessionCopilotCredits','modelTotals','cachedTokens'):
        if f'\"{k}\"' in s: props.add(k)
print(sys.argv[1].split('/')[-1], sorted(props))" "$f"
done | grep -v "\[\]"

# 2. empty-window + transferred roots
ls ~/Library/Application\ Support/Code/User/globalStorage/emptyWindowChatSessions/ 2>/dev/null
ls ~/Library/Application\ Support/Code/User/globalStorage/transferredChatSessions/ 2>/dev/null

# 3. sidecar (only exists if chat.agentHost.agentDebugLog.enabled was on)
ls ~/Library/Application\ Support/Code/User/agentHostUsage/ 2>/dev/null && \
  head -3 ~/Library/Application\ Support/Code/User/agentHostUsage/*.jsonl

# 4. CLI store
ls ~/.copilot/session-state/ | head
grep -h '"session.shutdown"' ~/.copilot/session-state/*/events.jsonl | head -2

# 5. OTel db (only if github.copilot.chat.otel.dbSpanExporter.enabled)
DB=~/Library/Application\ Support/Code/User/globalStorage/github.copilot-chat/agent-traces.db
[ -f "$DB" ] && sqlite3 "file:$DB?mode=ro" \
  "SELECT response_model,input_tokens,output_tokens,cached_tokens FROM spans WHERE operation_name='chat' LIMIT 5"
```

## Sources

- VS Code `main` (2026-08-13): `chatModel.ts` (toJSON ~1712–1738, `ISerializableChatResponseData` ~1826–1843), `chatService.ts` (`IChatUsage`, `IChatUsageModelTotal` 157–199), `chatSessionStore.ts` (storage roots 71–79, `.jsonl`/`.json` 738–740), `agentHostUsageSidecar.ts` (path 52, record 37–49, ungated delete ~185), `agentHostChatDebugProvider.ts` (gating 130–137), `stateToProgressAdapter.ts` (`usageInfoToChatUsage`, nanoAiu/1e9), `sessionState.ts` (`ITurnTokenTotal` 194–199, `copilotUsage` meta 116–126, `autoModeResolved` 201+), `copilotAgentSession.ts` (session-state dir 130/353, turn totals 4417–4434), `copilotAgent.ts` (events.jsonl 2552, vscode.metadata.json 2585), `copilotHome.ts` (`COPILOT_HOME` env), `promptTypes.ts` (setting ids), `chatServiceImpl.ts` (fileLogging authoritative ~1432).
- vscode-copilot-chat `main` (2026-08-13): `chatDebugFileLoggerService.ts` (debug-logs layout 209–272, llm_request serialization ~880–945), `openai.ts` (`APIUsage` 27–67), `genAiAttributes.ts` (cache attrs 65–66), `otelSqliteStore.ts` (schema, denormalized attrs 28–45, sessions view), `services.ts` (agent-traces.db path ~270, dbSpanExporter gating), `chatMLFetcher.ts` (cached_tokens producer 386), `configurationService.ts` (fileLogging canonical 691–697, otel settings 700+).
- cage: `transcript.py` HEAD (current capture behavior), `work/research/copilot-vscode-token-sources.md` + `2026-08-02-copilot-credit-fields-real-stores.md` (real-store probes: `copilotCredits` float 11/348 requests all `copilot/auto`; `totalPremiumRequests: 0.33` float).
