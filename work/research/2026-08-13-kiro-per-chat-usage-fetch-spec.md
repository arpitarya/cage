---
doc: research — the definitive fetch spec for Kiro per-chat tokens in/out, cached in/out, and credits
date: 2026-08-13
verified-against: aws/amazon-q-developer-cli `main` (clone 2026-08-13, kiro-cli's upstream) · d-kuro/kirocc `main` + ZyphrZero/kiro.rs `main` (clones 2026-08-13, both carry real captured payloads) · kiro-usage 0.1.3 (PyPI wheel, community tracker) · cage HEAD (`transcript.py`, `paths.py`; real-store probes of 2026-08-01 / 2026-08-07, kiro-cli 2.16.0)
relates: 2026-08-13-copilot-per-chat-usage-fetch-spec.md (the copilot analog) · 2026-08-07-graphify-store-evidence.md (kiro-cli store shape, truncation marker) · ADR 0006 (kiro rows are machine facts) · ADR 0009 (tool-run bodies transient)
unverified: ONE probe remains — whether IDE session JSONs embed per-message usage. The `devdata.sqlite` probe was CLOSED on 2026-08-14 with a negative result: **the file does not exist on a real Kiro install** (`dev_data/` holds only `tokens_generated.jsonl` — 28 rows, 1,576 in / 0 out, model `"agent"` throughout, one byte-identical 6-row block repeated, i.e. not summable). Consequence: kiro has **no token spine** in cage — `SPEND_SOURCES["kiro"]` is empty and `ledger.ABSENT_SPINES` states the reason (USAGE-ONLY, ADR 0011). §6 lists the command that closes the remaining one
---

# Kiro per-chat usage: where every number lives, exactly

Question answered: **for every chat, how do we fetch token in, token out, cached
in, cached out, and credits — which directory, which file, which row, which
property.**

The blunt headline first: **Kiro receives all five values per request on the
wire, and persists almost none of them.** The backend streams an exact token
breakdown (`metadataEvent.tokenUsage`, all four token counts) and an exact
per-request credit charge (`meteringEvent.usage`) with every response — both the
IDE and the CLI parse these events — but on disk the IDE keeps only a coarse
prompt/output pair and the CLI keeps only credits. Cache read/write per chat is
persisted **nowhere** by either surface today. That makes the proxy (which sees
the event stream) the only complete capture path, and everything on disk a
partial fallback.

All macOS paths; Linux swaps `~/Library/Application Support/` for `~/.config/`
(IDE) and `~/.local/share/` (CLI); Windows `%APPDATA%` (both UNVERIFIED-LAYOUT,
same status as in `paths.py`).

---

## The answer in one table

| value | wire (proxy sees it) | IDE on disk | CLI on disk |
|---|---|---|---|
| token in (uncached, per call) | `metadataEvent.tokenUsage.uncachedInputTokens` | `dev_data/tokens_generated.jsonl` → `promptTokens` (≈input, semantics shifted ~2026-02-28; no cache split) · same row in `devdata.sqlite` → `tokens_prompt` | `conversations_v2.value` → `history[].request_metadata` token fields **exist but are NULL** (2.16.0 probe) |
| token out (per call) | `metadataEvent.tokenUsage.outputTokens` | `generatedTokens` / `tokens_generated` — **often 0** in real data (16-call probe: 0 out total) | NULL (same fields) |
| cached in (read, per call) | `metadataEvent.tokenUsage.cacheReadInputTokens` | **nowhere** | **nowhere** |
| cached out (write, per call) | `metadataEvent.tokenUsage.cacheWriteInputTokens` | **nowhere** | **nowhere** |
| credits (per request) | `meteringEvent.usage` (float, `unit:"credit"`) | **nowhere** (UI's "Est. Credits Used" is render-only — kirodotdev/Kiro #8524) | conversation-level only: `value.user_turn_metadata.usage_info[]` where `unit` startswith `credit` → sum `value` (cage captures this today) |
| context % (bonus) | `contextUsageEvent.contextUsagePercentage` | nowhere known | `history[].request_metadata.context_usage_percentage` (populated; cage captures last non-null) |
| join key | `messageMetadataEvent.conversationId` / `.utteranceId` | none in jsonl (line order only) | `conversations_v2.conversation_id` |

---

## Source 0 — the wire protocol (the truth source; what the proxy must capture)

Kiro's backend is the CodeWhisperer/Q streaming service —
`POST https://q.{us-east-1|eu-central-1}.amazonaws.com/` with
`x-amz-target: AmazonCodeWhispererStreamingService.GenerateAssistantResponse` —
returning an **AWS event stream**. Per response stream, the usage-bearing
events (names from the frame header `:event-type`):

- **`metadataEvent`** → payload `{"tokenUsage": {"uncachedInputTokens": N,
  "outputTokens": N, "totalTokens": N, "cacheReadInputTokens": N,
  "cacheWriteInputTokens": N}, "stopReason": "..."}`. The four token counts are
  the **final snapshot for that model call, not increments** — keep the last
  one per stream. `tokenUsage` is optional (some metadataEvents carry only
  `stopReason`). Type source: the smithy-generated `TokenUsage` struct in
  Kiro/Q's own client (`amzn-qdeveloper-streaming-client/src/types/_token_usage.rs`);
  field spellings confirmed by two independent reverse-engineered clients that
  parse real traffic (kirocc `eventstream.go`, kiro.rs `events/metadata.rs`).
- **`meteringEvent`** → payload `{"unit": "credit", "unitPlural": "credits",
  "usage": 0.0169543708291874}` — **the per-request credit charge, a float**.
  kiro.rs pins this shape against a real capture and states the metering event
  carries **no token fields** (kirocc models optional `inputTokens`/`outputTokens`
  on it; treat them as absent).
- **`contextUsageEvent`** → `{"contextUsagePercentage": f}`.
- **`messageMetadataEvent`** → `{"conversationId": "...", "utteranceId": "..."}`
  — the join key to stamp captured usage onto a chat.

So a proxy sitting on this stream gets, per model call: exact uncached-in,
cache-read, cache-write, out, total, credits, context %, and the conversation
id. **This is the only place all five requested values coexist.** It matches
cage's existing stance ("proxy is the higher-fidelity fallback") — the research
upgrades that to: for cache and IDE credits, the proxy is the *only* path.

Account-level (not per chat, but the same auth): `GET
https://q.{region}.amazonaws.com/getUsageLimits?origin=AI_EDITOR&resourceType=AGENTIC_REQUEST&isEmailRequired=true`
(bearer token; the token kiro-cli itself stores in `data.sqlite3`'s auth
tables) → `usageBreakdownList[].{currentUsage, currentUsageWithPrecision,
usageLimit, nextDateReset, bonuses[], freeTrialInfo}`,
`subscriptionInfo.{subscriptionTitle, overageCapability}`,
`overageConfiguration.{overageEnabled, overageStatus}`. This is what the CLI's
`/usage` card renders; there is no public per-chat endpoint (kirodotdev/Kiro
#7752 asks for exactly that, unanswered).

## Source 1 — Kiro IDE `dev_data` (always-on; cage reads the jsonl today)

**Directory**: `~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/`

Two sibling stores of the same counter:

1. **`tokens_generated.jsonl`** — one JSON object per LLM call:
   `{model, provider, promptTokens, generatedTokens}`. What cage's
   `parse_kiro_calls` reads. Real-ledger facts (36,451-call probe, 2026-07-22):
   16 kiro calls, 198 tokens in, **0 out**; `model` frequently the generic
   `"agent"`. No timestamp, no session id, no cache, no credits.
2. **`devdata.sqlite`** — table **`tokens_generated`** with at least
   `(id, tokens_prompt, tokens_generated, timestamp)` (the kiro-usage tracker
   SELECTs exactly these). **Timestamped and ordered by `id`** — strictly more
   usable than the jsonl for `ts` and incremental cursors. Full column list
   needs the real-file probe (§6): the jsonl carries `model`/`provider`, so the
   table likely does too.

**Semantics hazard (community-established, kiro-usage `_IDE_CUTOVER`)**: before
~**2026-02-28**, `tokens_prompt` = the **full context** sent per call (so
summing it double-counts massively); after, it is **incremental** (new tokens
only). Any importer that prices or sums IDE prompt tokens must branch on the
row's date. Cage's current parser ignores this — with 198 total tokens it is
moot today, but it stops being moot the moment Arpit uses Kiro IDE in anger.

**Also under `kiro.kiroagent/`**: hash-named per-session directories holding
conversation JSONs (~2–3 MB each; the 30 GB-growth complaints in kirodotdev/Kiro
#5727/#6780/#5469 are these) plus a LanceDB vector index. **Whether those
session JSONs embed per-message `tokenUsage`/credits is the one live unknown**
(§6 probe 3). The signal pointing to "no": #8524 (2026-06) asks for exactly
that persistence and was closed duplicate — "Est. Credits Used" exists only in
the UI, with monthly dashboard totals (5-min refresh) and enterprise per-user
daily reports as the only aggregates.

## Source 2 — Kiro CLI SQLite store (always-on; cage reads credits today)

**File**: `~/Library/Application Support/kiro-cli/data.sqlite3` (probe order in
`paths.kiro_cli_db_candidates`; distinct from the IDE globalStorage).

**Table**: **`conversations_v2`**`(key TEXT /* the launch cwd, absolute +
symlink-resolved */, conversation_id, value TEXT /* whole-conversation JSON */,
created_at, updated_at)` — verified against the real store 2026-08-01
(kiro-cli 2.16.0). The community tracker also archives a sibling table
**`conversations`**`(key, value)` whose `value` carries
`{conversation_id, history[], latest_summary, ...}` inline — present in some
CLI versions (kiro-usage labels the eras "< 2.0.1" / "2.0.1+", which
contradicts our 2.16.0 = conversations_v2 observation, so treat the version
boundary as unpinned and **enumerate both tables**; §6 probe 4 settles which
exist here).

**Inside `value` (the whitelisted fields; capture-precision §3.3):**

| prop | contains | status on real store (2.16.0) |
|---|---|---|
| `history[].request_metadata.{total_tokens, uncached_input_tokens, output_tokens, cache_…}` | the per-turn token slots — the fork's schema clearly plumbed `TokenUsage` in | **NULL even with an explicit model** (cage §0 probe). The upstream Q repo's `RequestMetadata` has no token fields at all — the kiro fork added them but doesn't fill them. **Watch trigger: the day these go non-NULL, per-turn CLI tokens become exactly fetchable** — re-probe on every kiro-cli upgrade |
| `history[].request_metadata.{model_id, request_start_timestamp_ms, stream_end_timestamp_ms, time_between_chunks[], tool_use_ids_and_names[], user_prompt_length, response_size, context_usage_percentage}` | per-turn metadata that IS populated | used by cage for ts (`_KIRO_CLI_TS_KEYS`) and context % |
| `user_turn_metadata.usage_info[]` → `{unit, value}` where `unit` startswith `"credit"` | **the credits** — conversation-level list, NOT 1:1 with history turns | populated; cage sums it (`_kiro_cli_credit_row`), collapses last-per-session in `ledger.credits` — per-turn credit attribution would be a guess, correctly refused |
| `model_info.{model_id, model_name}` | the selected model | populated |

**Token counts on the CLI surface**: not persisted. The kiro-usage tracker
fills the gap by **estimating** — chars÷4 over `history[].user`/`.assistant`
bodies for cache-write, a running cumulative for cache-read, and
`len(request_metadata.time_between_chunks)` as the output-token count (one
chunk ≈ one token; it calls only this one "accurate"). Recorded here as what
the community does — every one of those is a guess wearing a number, and two
of the three require reading message bodies, so **none of it is importable
into cage rows** (capture-precision; the ADR 0009 boundary stays tool-runs-only).
The chunk-count trick is the least dishonest of the three if ever needed for a
*labeled estimate*, never a `tokens_out` fact.

Auth aside (read nothing, know it exists): the same `data.sqlite3` holds the
bearer token + `api.codewhisperer.profile` ARN that third-party tools use to
call `getUsageLimits`. Cage's whitelist correctly never touches these tables;
any future `cage` account-level credits probe should also *not* — shipping a
tool that lifts Kiro's auth token is a different product.

## Source 3 — what does NOT exist (so nobody re-searches it)

- **No per-chat credits file in the IDE** (#8524) and **no machine-readable
  usage command/endpoint** (#7752) — both open feature requests as of
  2026-08-13.
- **No cache-token persistence anywhere** on either surface — the only cache
  numbers Kiro ever emits are in the wire `metadataEvent.tokenUsage`.
- **The IDE token log carries no credits, ts, or session id**, and its `model`
  is usually `"agent"` — the real routed Claude model id is not surfaced there
  (pricing by model id will keep hitting the `$0`/UNPRICED path — see
  [[cage-pricing-zero-bug]]).
- **`/usage` in the CLI is TUI-only** — rendered from `getUsageLimits`, not
  from any local store you can re-read.

## 4 — What cage should implement (ranked)

1. **Proxy capture of `metadataEvent` + `meteringEvent`** keyed by
   `messageMetadataEvent.utteranceId`/`conversationId` — the ONLY path to all
   five values per chat, for both surfaces. This upgrades "proxy is the
   higher-fidelity fallback" (module docstring of `kirowire.py`) to "proxy is
   the only complete path", which is worth stating in doctor/report copy.
2. **IDE importer: read `devdata.sqlite` instead of (or beside) the jsonl** —
   same counter, plus `timestamp` and a stable `id` cursor; branch
   `tokens_prompt` semantics on the 2026-02-28 cutover date rather than
   summing blind. (Verify columns first — §6 probe 2.)
3. **CLI: keep the credits capture as-is** (it is the right shape), and add a
   cheap **upgrade probe** to the import path or doctor: if any
   `history[].request_metadata.uncached_input_tokens` is non-NULL, surface
   "kiro-cli now persists per-turn tokens — importer upgrade available".
   Also enumerate the `conversations` table when present, not just
   `conversations_v2`.
4. **Never import the community estimation trio** (chars÷4 / cumulative /
   chunk-count) as token facts; honest-empty stays correct, same verdict as
   copilot cache-write.

## 5 — Deltas vs what cage's docs say today

1. `kirowire.py`/`importcmd.py` call the IDE log "coarse: prompt tokens are
   reliable" — **stale nuance**: post-2026-02-28 `tokens_prompt` is
   *incremental*, so it is no longer "the prompt" in the old sense, and
   pre/post rows are not summable with each other.
2. `paths.kiro_token_log()` points at the jsonl only — `devdata.sqlite` sits
   in the same directory with the same data plus timestamps and was not in any
   cage doc until now.
3. The `conversations` (non-v2) table was unknown to cage; enumeration should
   cover it.
4. The wire-event names and shapes (`metadataEvent.tokenUsage`,
   `meteringEvent.usage`, `messageMetadataEvent` join key) are now pinned with
   sources — the proxy leg, when built, has its exact parse targets.

## 6 — Verification commands (run on the Mac, read-only; close the `unverified` header)

```bash
# 1. what actually lives under dev_data/
ls -la ~/Library/Application\ Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/

# 2. devdata.sqlite: real schema + sample (settles the column list)
DB=~/Library/Application\ Support/Kiro/User/globalStorage/kiro.kiroagent/dev_data/devdata.sqlite
sqlite3 "file:$DB?mode=ro&immutable=1" ".schema" \
  "SELECT * FROM tokens_generated ORDER BY id DESC LIMIT 5"

# 3. do IDE session JSONs persist tokenUsage/credits? (the one live unknown)
grep -rl --include=*.json -m1 -E '"tokenUsage"|"cacheRead|creditsUsed|"metering' \
  ~/Library/Application\ Support/Kiro/User/globalStorage/kiro.kiroagent/ | head

# 4. CLI store: which conversation tables exist; are token slots still NULL?
CDB=~/Library/Application\ Support/kiro-cli/data.sqlite3
sqlite3 "file:$CDB?mode=ro&immutable=1" ".tables"
sqlite3 "file:$CDB?mode=ro&immutable=1" \
  "SELECT json_extract(value,'$.history[0].request_metadata.uncached_input_tokens'),
          json_extract(value,'$.history[0].request_metadata.total_tokens'),
          json_extract(value,'$.user_turn_metadata.usage_info')
   FROM conversations_v2 ORDER BY updated_at DESC LIMIT 3"
```

## Sources

- aws/amazon-q-developer-cli `main` (2026-08-13): `crates/amzn-qdeveloper-streaming-client/src/types/_token_usage.rs` (TokenUsage: uncached/output/cacheRead/cacheWrite), `_metadata_event.rs` (metadataEvent.tokenUsage), `crates/chat-cli/src/cli/chat/parser.rs` 688 (`RequestMetadata` — NO token fields upstream), `crates/agent/src/agent/agent_loop/{protocol.rs,types.rs}` (UserTurnMetadata, agent-crate MetadataUsage), `crates/chat-cli/src/database/mod.rs` (upstream `conversations` table).
- d-kuro/kirocc `main` (2026-08-13): `internal/kiroproto/eventstream.go` (event names + payload structs, `InputTokens = uncached + cacheRead`), `internal/kiroclient/client.go` (endpoint + `x-amz-target`), `internal/auth/db.go` (where the CLI keeps auth — not for cage).
- ZyphrZero/kiro.rs `main` (2026-08-13): `src/kiro/model/events/metering.rs` (**real captured payload** `{"unit":"credit","unitPlural":"credits","usage":0.0169…}`; "upstream sends no token fields on metering" pinned), `events/metadata.rs` (tokenUsage = final snapshot per call, optional), `src/kiro/token_manager.rs` (getUsageLimits URL + us-east-1/eu-central-1), `src/kiro/model/usage_limits.rs` (response schema).
- kiro-usage 0.1.3 (PyPI wheel, unpacked 2026-08-13): `__init__.py` (CLI_DB + **IDE_DB=devdata.sqlite** paths), `viewer.py` (`SELECT tokens_prompt, tokens_generated, timestamp FROM tokens_generated`; `_IDE_CUTOVER = 2026-02-28`; the chars÷4 / cumulative / `len(time_between_chunks)` estimation trio), `archiver.py` (**both** `conversations_v2` and `conversations` tables archived).
- kirodotdev/Kiro issues (read 2026-08-13): [#8524](https://github.com/kirodotdev/Kiro/issues/8524) (Est. Credits Used not persisted; dashboard 5-min monthly + enterprise daily are the only aggregates), [#7752](https://github.com/kirodotdev/Kiro/issues/7752) (`/usage` card fields; no machine-readable access), [#9486](https://github.com/kirodotdev/Kiro/issues/9486) (token display request), [#6780](https://github.com/kirodotdev/Kiro/issues/6780)/[#5727](https://github.com/kirodotdev/Kiro/issues/5727)/[#5469](https://github.com/kirodotdev/Kiro/issues/5469) (globalStorage session-JSON growth; layout fragments).
- cage HEAD: `transcript.py` (`parse_kiro_calls`, `_kiro_cli_credit_row`, `parse_kiro_cli_credits`), `paths.py` (`kiro_data_candidates`, `kiro_cli_db_candidates`, `kiro_token_log`), real-store probes 2026-08-01 (cwd-key normalization, request_metadata NULLs) and 2026-08-07 (truncation marker, kiro-cli 2.16.0), real-ledger analysis 2026-07-22 (16 calls / 198 in / 0 out).
