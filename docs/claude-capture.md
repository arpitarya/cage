---
doc: how Claude numbers are captured — the standing reference
status: current as of 2026-08-14 · shipped calls capture + shipped CLAUDE-METRICS (correct per-chat ledger) + two open calls-path defects
update-rule: ANY change to claude capture (parser · source · schema field · pricing) updates this doc in the same change, and bumps its DOC-REGISTRY row
---

# Claude capture — how the numbers are made

One page: what cage records for Claude Code, from where, and what it means.
Deep detail lives in the linked research/spec docs — not here.

## Captured today (shipped)

| number | store → prop | lands as |
|---|---|---|
| tokens in (total) | `~/.claude/projects/<slug>/**/*.jsonl` → assistant rows' `message.usage`: `input_tokens` + `cache_read_input_tokens` + `cache_creation_input_tokens` | `calls.tokens_in` (`c_`+uuid, agent `claude-code`) |
| tokens out | same row → `output_tokens` | `calls.tokens_out` |
| cached in (read) | same row → `cache_read_input_tokens` | `calls.cached_in` |
| cached out (write) | same row → `cache_creation_input_tokens` | `calls.cache_write_in` — Claude persists this; Copilot doesn't |
| project | row envelope `cwd` (basename only) | `calls.project` |
| chat title | `summary` record | `imports.jsonl` name only — never a call row |

- One transcript file = one chat; CLI and the VS Code extension share the store.
- Pull-based (`cage import` / capture-on-read) — no hooks, no network, $0.
- Dollars = tokens × your policy price table — **modeled**, never invoiced
  (Claude Code stopped writing `costUSD` in v1.0.9; nothing billed is on disk).
- Counts-never-content: usage numbers + ids only; never prompts, responses,
  or `tool-results/`.

### Captured today — the CORRECT per-chat ledger (CLAUDE-METRICS, shipped)

`.cage/ledger/claude/chats-YYYY-MM.jsonl` — one row per chat, folded correctly at
capture, deliberately kept OUT of `calls` so it can't inherit that path's defects:

| number | store → prop | lands as |
|---|---|---|
| tokens in/out (deduped) | THE DEDUP LAW folds every duplicate assistant row per `(requestId, message.id)`, last occurrence wins | `claude/*.tokens_in` / `tokens_out` — NOT inflated |
| cache-write TTL split | `cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` (1.25× / 2× base price) | `ttl_5m` / `ttl_1h` |
| thinking tokens | `output_tokens_details.thinking_tokens` | `thinking` |
| server-tool calls | `server_tool_use.web_search_requests` / `web_fetch_requests` | `web_search` / `web_fetch` |
| sidechain (subagent) split | `isSidechain` rows, joined to the PARENT chat via the row's own `sessionId` | `sidechain_tokens_in` / `sidechain_tokens_out` |
| inflation evidence | usage-bearing rows seen vs. distinct folded requests | `raw_rows` / `requests` |

Capture-only — no `report`/`insights chats` cell reads this kind yet (a read surface
is parked, `work/OPEN-WORK.md`). No credits field: none exists for Claude Code.
Spec: [claude-metrics-ledger.handoff.md](archive/v0.49-claude-metrics-ledger.handoff.md) ·
evidence: [research/2026-08-13-claude-per-chat-usage-fetch-spec.md](research/2026-08-13-claude-per-chat-usage-fetch-spec.md).

## Known gaps & defects (open)

- **CLAUDE-DEDUP (defect, calls path only)** — `calls`/`cage report` still key by
  row `uuid` and count every duplicate assistant row; Claude spend on THAT surface
  stays **inflated ~2–3×** (3.17× measured live). CLAUDE-METRICS dodges this by
  construction in its own ledger but does not fix `parse_calls` — still open.
- **CLAUDE-SUBAGENT-KEY (defect, calls path only)** — `calls` still keys a subagent
  transcript's rows by filename, landing their spend in a phantom chat. Also dodged,
  not fixed, by CLAUDE-METRICS — still open.
- **Credits: none exist** — no credit unit for Claude Code anywhere on disk;
  subscription quota is a rate-limit window, not a per-chat spend meter.
  Permanently honest-absent; not a cage gap.
- **30-day retention** — Claude Code auto-deletes transcripts
  (`cleanupPeriodDays`, default 30); import cadence must beat it. `cage doctor`'s
  `claude-metrics` check nudges when the newest transcript is >25 days old.

## Executive summary (for the meeting)

- We meter Claude from **Claude Code's own transcript records** — on-disk, no
  vendor API, no network, zero infra cost. Tokens are the vendor's numbers,
  recorded verbatim.
- Per chat we can state tokens in/out **and both cache directions**, plus the
  cache-write TTL split, thinking share, server-tool counts, and subagent
  attribution — in the dedicated `claude/` ledger, correctly folded.
- **Honesty flag, scoped**: the ORIGINAL `calls` surface (`cage report` and
  everything built on it) still carries a known double-count defect that inflates
  Claude token figures ~2–3× — that fix is a separate, still-open item. The NEW
  per-chat ledger is immune to it by construction, but nothing reads it yet.
- **No billed unit exists for Claude**: subscriptions meter by 5-hour/7-day
  rate-limit windows, not per-chat credits, and nothing billed reaches disk.
  Every Claude dollar figure is **modeled** (tokens × our price table) and is
  labeled so — never an invoice.
- **The vendor deletes its own records after ~30 days** — cage's capture is the
  durable history; regular import is the whole defense; doctor now nudges before
  the 30-day window closes.
- **Trajectory**: a read surface for the new per-chat ledger (and fixing the two
  `calls`-path defects) are the next steps, both parked in `work/OPEN-WORK.md`.

## Maintenance

Standing rule (frontmatter `update-rule`): a change to any claude parser, source
path, schema field, or pricing updates this doc **in the same change** — stale
here = a missing changelog entry. Tracked in [DOC-REGISTRY.md](DOC-REGISTRY.md).
