---
doc: research — the definitive fetch spec for Claude Code per-chat tokens in/out, cached in/out, and credits
date: 2026-08-13
verified-against: live Claude Code 2.1.229 transcript store (this Cowork session's own `~/.claude/projects/`, probed 2026-08-13 — assistant-row duplication, subagent layout, and every usage prop measured on real rows) · code.claude.com docs (cost-tracking · statusline · monitoring-usage) · ccusage issues #4/#888 · cage HEAD (`transcript.py`, `paths.py`)
relates: 2026-08-13-copilot-per-chat-usage-fetch-spec.md (the Copilot twin, same question) · copilot-vscode-token-sources.md
---

# Claude Code per-chat usage: where every number lives, exactly

Question answered: **for every chat, how do we fetch token in, token out, cached
in, cached out, and credits — which directory, which file, which row, which
property.**

Four sources exist. One is on-disk and durable (the transcript store — the only
one cage can read); one is a live per-session tap (statusline JSON); two are
stream/export-only and never touch disk (SDK result messages, OTel). Unlike
Copilot, **cache-write IS persisted** (`cache_creation_input_tokens`). Unlike
Copilot, **no credit unit exists anywhere** — the vendor writes no billed figure
to disk at all (the old `costUSD` row field died in v1.0.9, June 2025).

Two defects in cage's current parser fall out of the live probe — see
*What cage should fix* at the end.

---

## The answer in one table

| value | on-disk source (durable) | live/stream source |
|---|---|---|
| token in (uncached, per request) | transcript row → `message.usage.input_tokens` | statusline → `context_window.current_usage.input_tokens` |
| token out (per request) | transcript row → `message.usage.output_tokens` (**last** row per request — see the dedup law) | SDK result → `usage.output_tokens` (per-step is a placeholder) |
| cached in (read) | transcript row → `message.usage.cache_read_input_tokens` | statusline `current_usage`; OTel `type="cacheRead"` |
| cached out (write) | transcript row → `message.usage.cache_creation_input_tokens` (+ TTL split in `cache_creation.{ephemeral_5m,1h}_input_tokens`) | OTel `type="cacheCreation"` |
| credits | **nowhere — no credit unit exists** | nearest analogs: statusline `cost.total_cost_usd` (client-side USD estimate) + `rate_limits.{five_hour,seven_day}.used_percentage` (subscription quota); SDK result `total_cost_usd`/`modelUsage[].costUSD`; OTel `cost_usd` |

Per-chat totals = fold source 1 by `sessionId`, **after** deduplicating by
`(requestId, message.id)`.

---

## Source 1 — the transcript store (always-on, durable; cage reads this today)

**Directory**: `~/.claude/projects/<slug>/` (`CLAUDE_CONFIG_DIR` overrides the
`~/.claude` root — cage's `paths.claude_home()` honors it). `<slug>` is the
absolute working-dir path with non-alphanumerics folded to `-`
(`paths.claude_project_slug`). CLI and the VS Code extension **share this one
store** — there is no second Claude store to sweep.

**File**: `<sessionId>.jsonl` — one file **is** one chat; the filename stem is
the session UUID. Append-only, one JSON object per line. Record `type`s observed
live on 2.1.229: `user` · `assistant` · `attachment` · `queue-operation` ·
`last-prompt` (+ `summary` — the chat title cage already reads — and `system`
compaction/meta rows in longer sessions).

**Row**: usage lives ONLY on `type: "assistant"` records, envelope:

```json
{"type":"assistant", "uuid":"…", "parentUuid":"…", "requestId":"req_011C…",
 "sessionId":"…", "timestamp":"ISO-8601Z", "cwd":"/abs/path", "gitBranch":"…",
 "version":"2.1.229", "isSidechain":false, "effort":"high",
 "entrypoint":"cli|sdk-py|remote_cowork|…",
 "message":{"id":"msg_011C…", "model":"claude-…", "usage":{…}}}
```

**Props on `message.usage`** (all measured live):

| prop | meaning | caveat |
|---|---|---|
| `input_tokens` | **uncached** input only | tiny by design (often 1–3) — the bulk of input is in the two cache fields; total input = sum of all three. Community "input undercounted 100×" posts misread this |
| `output_tokens` | output incl. thinking | historically a `message_start` placeholder; duplicates can disagree and **latest == final** (ccusage #888: 550/551). Live 2.1.229 rows carried final values on every duplicate |
| `cache_read_input_tokens` | cached in (read) | reliable |
| `cache_creation_input_tokens` | cached out (write) | reliable; **exists — the value Copilot persists nowhere** |
| `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` | cache-write TTL split | prices differ (5m = 1.25×, 1h = 2× base input) — the split, not the total, is what costs out exactly |
| `output_tokens_details.thinking_tokens` | thinking share of output | new; display/analysis only, already inside `output_tokens` |
| `server_tool_use.web_search_requests` / `web_fetch_requests` | billable server-tool call counts | API-billing line items ($/1k requests), not tokens |
| `service_tier` / `speed` / `inference_geo` | serving metadata | `speed` pairs with the OTel `speed` attr |
| `iterations[]` | per-iteration copy of the same counts | new on 2.1.x; the top-level fields already sum it |

**THE DEDUP LAW (the headline finding).** One API response = **N assistant rows**
(one per content block: text · thinking · each tool_use), every one carrying a
**distinct `uuid`** but the **same `requestId` + `message.id` and a full copy of
`usage`**. Measured live: 27 usage-bearing rows for 11 requests (1–5 rows each);
naive per-row summation inflates output tokens **3.17×** in this session's file.
Every serious reader (ccusage, ccost) folds by `(message.id, requestId)`;
per ccusage #888 keep the **last** row (earlier ones can be intermediate
snapshots; latest == max in 550/551 observed cases). **Cage does not do this**:
`transcript._usage_to_row` keys `call_id` on the row `uuid`, so every duplicate
becomes its own ledger call — Claude spend in every cage view is inflated
roughly 2–3×.

**Subagents (Task tool)**: current builds write them to a **session
subdirectory** — `<slug>/<sessionId>/subagents/agent-<agentId>.jsonl`, rows
`isSidechain: true`, sibling `agent-<agentId>.meta.json`
(`{agentType, description, toolUseId, spawnDepth, model}`). Their usage is real
spend (measured live: a one-word haiku probe wrote 51,975 cache-creation
tokens). Two facts matter: (a) cage's `**/*.jsonl` glob already sweeps them in;
(b) **every subagent row's own `sessionId` field is the PARENT session id** —
but cage sets `session = filename stem` (`agent-<id>`), so subagent spend lands
in a phantom chat instead of the chat that spawned it. Older builds wrote
sidechain rows inline in the parent file (`isSidechain: true`, same
`sessionId`) — folding by the row's `sessionId` handles both layouts with one
rule. The `<sessionId>/tool-results/` sibling dir holds oversized tool outputs —
**content, never read** (counts-never-content).

**Retention hazard**: transcripts are **auto-deleted after 30 days** by default
(`cleanupPeriodDays` in `settings.json`; note `0` disables persistence
entirely, not cleanup — issue #23710). Capture cadence must beat 30 days;
cage's capture-on-read already does unless a machine sits idle a month.

**What is NOT in the store**: no cost, no USD, no credits, no rate-limit state.
`costUSD` (and `durationMs`) existed per-row through Claude Code 1.0.8 and was
removed in 1.0.9 (ccusage #4) — legacy files may still carry it; nothing
current writes it.

## Source 2 — statusline JSON (live per-session tap; CLI-only, not persisted)

A configured statusline command (`settings.json → statusLine`) receives JSON on
stdin at every refresh — the only place Claude Code hands over its own computed
session cost **and subscription quota**:

| prop | meaning |
|---|---|
| `cost.total_cost_usd` | session-cumulative USD, **client-side estimate** (docs' own warning: never billing truth; resets on `/clear`) |
| `cost.total_duration_ms` / `total_api_duration_ms` / `total_lines_added` / `total_lines_removed` | wall/API time, LoC delta |
| `context_window.total_input_tokens` | context now = `input + cache_creation + cache_read` of the last response |
| `context_window.current_usage.{input_tokens, output_tokens, cache_read_input_tokens, cache_creation_input_tokens}` | last API call, per component |
| `rate_limits.five_hour.used_percentage` / `.resets_at` · `rate_limits.seven_day.*` | **the subscription "credits" analog** — % of the 5-hour / 7-day window consumed, epoch reset |
| `session_id` / `transcript_path` / `model.id` / `effort.level` / `exceeds_200k_tokens` / `version` | joins straight back to source 1 |

Nothing persists it — a statusline script that tees the JSON is the only way to
record rate-limit history. (For cage that would be a new consent surface, L1
territory; noted, not proposed.)

## Source 3 — SDK result messages (stream-only; never written to the transcript)

Agent SDK / headless (`claude -p --output-format json`) emits a terminal
`result` message per `query()` call: `total_cost_usd` (cumulative estimate,
subagents INCLUDED), `usage` (main loop only — undercounts once subagents run),
and `modelUsage` / `model_usage`: per-model
`{inputTokens, outputTokens, cacheReadInputTokens, cacheCreationInputTokens,
costUSD}`. Official caveats: per-step `output_tokens` on assistant messages is
a `message_start` placeholder — read output from the result; parallel tool
calls share one `message.id` — count once; crash results may be zeroed. This is
where `costUSD` went after v1.0.9: computed client-side from a bundled price
table, explicitly "not authoritative billing data".

## Source 4 — OTel telemetry (opt-in export; no local file, unlike Copilot)

`CLAUDE_CODE_ENABLE_TELEMETRY=1` + OTLP exporter env. Metrics:
`claude_code.token.usage` (attrs `type ∈ {input, output, cacheRead,
cacheCreation}`, `model`, `speed`, `effort`, agent/skill/MCP attribution) and
`claude_code.cost.usage` (USD). Per-request event `claude_code.api_request`:
`input_tokens · output_tokens · cache_read_tokens · cache_creation_tokens ·
cost_usd · cost_usd_micros · duration_ms · model · request_id` (joins to
source 1's `requestId`). Export-only — there is **no local SQLite twin** of
Copilot's `agent-traces.db`; without a collector, nothing lands anywhere.

## Credits: a firm no, and what stands in for them

Checked everywhere: **no credit unit exists for Claude Code, on disk or off.**
The store persists tokens only; `schema.make_call`'s `credits=None` sentinel is
exactly right for every claude row (absence, not zero). The three stand-ins,
none per-chat-persisted: (a) **client-computed USD** — cage's own
`tokens × prices.toml` recompute is the same computation the statusline/SDK
estimate does, and equally non-authoritative; (b) **subscription quota** — the
5-hour/7-day `rate_limits` percentages (statusline / `/usage`), a windowed
throttle, not a spend meter; (c) **extra usage** — Anthropic's overage for
subscription plans, billed in USD server-side, surfaced nowhere locally
(`.claude.json` carries only eligibility caches, e.g.
`cachedExtraUsageDisabledReason`). Copilot's `copilotCredits` has **no Claude
equivalent**, and inventing one from tokens would violate the
never-derive-credits-from-tokens rule in both directions.

---

## What cage reads today (transcript.py) — and what to fix, ranked

Today: `~/.claude/projects/**/*.jsonl` (via `agent_log_sources`), assistant rows
→ `_usage_to_row`: `tokens_in = input + cache_read + cache_creation`,
`cached_in = cache_read`, `cache_write_in = cache_creation`,
`call_id = c_ + uuid[:15]`, `session = filename stem`, `project = basename(cwd)`.

1. **CLAUDE-DEDUP (defect, inflation ~2–3×)** — fold assistant rows by
   `(requestId, message.id)` last-write-wins *before* emitting a call row; derive
   the call id from `requestId` (stable across re-imports; keeps
   `ledger.append_new` dedup exact). Existing ledgers hold the inflated rows —
   remediation (derive-time collapse by a recorded group key vs. one-time
   rescan) needs its own decision; the `billed_with` precedent says record
   structure, never rewrite.
2. **CLAUDE-SUBAGENT-KEY (defect, mis-keyed chats)** — set `session` from the
   row's own `sessionId` field, falling back to the filename stem only when
   absent. Fixes both the `subagents/agent-*.jsonl` layout and legacy inline
   sidechains with one rule; `cage insights chats` then bills subagent spend to
   the chat that spawned it.
3. **Cache-TTL split (additive)** — record `ephemeral_5m/1h` if cage ever prices
   cache writes distinctly; today's single `cache_write_in` loses a real 1.6×
   price spread between the two TTLs.
4. **Additive niceties** — `thinking_tokens`, `server_tool_use` counts,
   `effort`/`speed`: analysis columns, zero pricing impact. Optional.
5. **Retention note for doctor** — a claude source whose newest transcript is
   >25 days old is about to lose history to the 30-day sweep; a doctor advisory
   is cheap.

## Verification commands (run on the Mac, read-only)

```bash
# 1. THE DEDUP MEASUREMENT — rows vs requests vs naive/dedup output sums
python3 - <<'EOF'
import json, glob, os, collections
root=os.path.expanduser("~/.claude/projects")
rows=reqs=naive=0; dedup={}
for f in glob.glob(root+"/**/*.jsonl", recursive=True):
    for line in open(f, encoding="utf-8", errors="replace"):
        try: r=json.loads(line)
        except ValueError: continue
        if r.get("type")!="assistant": continue
        m=r.get("message") or {}; u=m.get("usage") or {}
        if not u: continue
        rows+=1; k=(r.get("requestId"), m.get("id"))
        naive+=u.get("output_tokens",0); dedup[k]=u.get("output_tokens",0)
print("usage rows:",rows," unique requests:",len(dedup),
      " naive out:",naive," dedup out:",sum(dedup.values()),
      " inflation:",round(naive/max(1,sum(dedup.values())),2),"x")
EOF

# 2. subagent layout + parent-session linkage
ls ~/.claude/projects/*/*/subagents/ 2>/dev/null | head
head -1 ~/.claude/projects/*/*/subagents/agent-*.jsonl 2>/dev/null | \
  python3 -c "import json,sys;[print(json.loads(l).get('sessionId'),'sidechain:',json.loads(l).get('isSidechain')) for l in sys.stdin if l.strip().startswith('{')]" 2>/dev/null | head -3

# 3. which usage props your local version writes
grep -h '"usage"' ~/.claude/projects/*/*.jsonl 2>/dev/null | tail -1 | \
  python3 -c "import json,sys; r=json.loads(sys.stdin.read()); print(sorted((r['message']['usage']).keys()))"

# 4. retention setting + legacy costUSD presence
grep -o '"cleanupPeriodDays"[^,}]*' ~/.claude/settings.json 2>/dev/null || echo "cleanupPeriodDays unset → 30-day default"
grep -l '"costUSD"' ~/.claude/projects/*/*.jsonl 2>/dev/null | head -3
```

## Sources

- **Live probe (primary)**: this Cowork session's own store, Claude Code runtime
  2.1.229 — `~/.claude/projects/-home-claude/<session>.jsonl` (27 usage rows /
  11 requests, 3.17× naive inflation; full usage prop set incl. `cache_creation`
  TTL split, `iterations[]`, `thinking_tokens`) and a spawned haiku subagent
  (`<session>/subagents/agent-*.{jsonl,meta.json}`, parent `sessionId` on rows).
- code.claude.com docs: [cost-tracking](https://code.claude.com/docs/en/agent-sdk/cost-tracking)
  (placeholder `output_tokens`, dedupe-by-`message.id`, `total_cost_usd`/
  `modelUsage` semantics, estimate-not-billing warning),
  [statusline](https://code.claude.com/docs/en/statusline) (`cost.*`,
  `context_window.*`, `rate_limits.*` field tables),
  [monitoring-usage](https://code.claude.com/docs/en/monitoring-usage)
  (`claude_code.token.usage` type attrs, `claude_code.api_request` event).
- ccusage [#4](https://github.com/ryoppippi/ccusage/issues/4) (`costUSD` removed
  in 1.0.9), [#888](https://github.com/ryoppippi/ccusage/issues/888)
  (duplicate `(message.id, requestId)` entries, latest==final in 550/551);
  claude-code issues [#62476](https://github.com/anthropics/claude-code/issues/62476)
  (30-day default cleanup), [#23710](https://github.com/anthropics/claude-code/issues/23710)
  (`cleanupPeriodDays: 0` kills persistence),
  [#22686](https://github.com/anthropics/claude-code/issues/22686) /
  [#27361](https://github.com/anthropics/claude-code/issues/27361) (streaming
  output-count reliability history).
- cage HEAD: `transcript.py` (`_usage_to_row`, uuid-keyed call ids, no
  requestId read), `paths.py` (`claude_home`, `claude_project_slug`,
  `**/*.jsonl` source glob).
- Treated skeptically, not relied on: gille.ai "100× undercount" post — its
  input-token claim misreads cache accounting (uncached input genuinely is ~1–3
  tokens under caching); its output concern is the real, separately-sourced
  placeholder issue above.
