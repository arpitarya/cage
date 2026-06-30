# Cage meter — what to modify or build (code-grounded plan)

**Date:** 2026-06-30 · **Basis:** read of `schema.py`, `transcript.py`, `importcmd.py`, `hooks.py`, `convert.py`, `prices.py`, `policy.toml`, `cli.py`, `paths.py`. Maps the competitive-lessons items onto concrete cage changes, filtered through cage's constitution ($0, stdlib-only, deterministic, counts-never-content, four-agents-always, separate audit layers).

---

## Two findings that shape everything

**1. The call schema is a closed contract.** `schema.make_call` returns a fixed dict and `CALL_FIELDS` is a closed tuple (`id, ts, session, task, agent, route, provider, model, tokens_in, tokens_out, cached_in, est_cost_usd, latency_ms, ok, retries, scope, project`). There is **no field for quota / rate-limit / credits**, and adding one would change the contract (plan §3) and every downstream consumer. → **Quota/limits must be a NEW record type** (a 5th append-only file, mirroring `provenance.jsonl`), not a field on calls. This also keeps "a call row is an invoice" clean — a rate-limit snapshot is not a call.

**2. There is a real dedup bug, not just a sub-agent risk.** `hooks.append_new` dedupes purely on `row["id"]`. The Claude parser sets `call_id = "c_"+uuid[:15] if uuid else None` — and when `uuid` is absent, `make_call` mints a **random** id (`ids.new_id("c")`). A turn with no uuid therefore gets a **new random id on every parse → re-imported as a duplicate every run** (the cursor only skips *unchanged* files; a growing transcript re-parses fully). Codex/Copilot use deterministic index-based ids so they're safe, but the Claude path can silently over-count. → The composite-key dedup (lesson D) is a **correctness fix**, prioritized accordingly.

---

## Work items (each: what · files · schema/contract · risk · effort)

### 1. Codex `rate_limits` extraction → first quota signal  **[$0]**
- **What:** `_codex_usage` already reads `payload.info`; the Codex `token_count` event also carries a `rate_limits` block (5-hour + weekly windows with used/remaining % and reset). Extract it and emit a **limit snapshot** record (not a call).
- **Files:** `transcript.py` (add `_codex_rate_limits(rec)` + emit snapshots from `parse_codex_calls`, or a sibling `parse_codex_limits`); `schema.py` (new `make_limit_snapshot`); `ledger.py` (allow a new `"limits"` kind in `append_row`/`read_kind` — already keyed by kind per the month-partition design); `importcmd.py` (`import_codex` also ingests limit snapshots).
- **Contract:** new record type `limits.jsonl`, own closed enums: `window ∈ {session, 5h, weekly, monthly}`, `source = "codex-rollout"`, fields = `{id, ts, agent, provider, window, used_pct, remaining_pct, resets_at, source}`. Counts-safe (percentages + reset ts only, no content). Document in plan §3 as a parallel substrate (like provenance).
- **Risk:** Codex log shape drift — read defensively, fail-open per line (existing pattern). Idempotent id from `(session, window, resets_at)`.
- **Effort:** S. Highest value:cost — data is in a file cage already parses.

### 2. Composite-key dedup → correctness  **[$0]**
- **What:** stop relying on a possibly-random `call_id`. Give every parsed call a deterministic **`dedupe_key`** = stable hash of `(agent, session, turn-index-or-uuid, model, tokens_in, tokens_out, cached_in, ts)`; dedupe on `id` **or** `dedupe_key`.
- **Files:** `schema.py` (compute a deterministic id when no stable source id is supplied — replace the `ids.new_id` fallback in the transcript path with a content-derived hash); `transcript.py` (Claude `_usage_to_row`: derive id from the composite when `uuid` is empty, instead of passing `None`); `hooks.append_new` (dedupe set keyed by the composite where present); tests in `tests/` for the Claude-no-uuid and sub-agent cases.
- **Contract:** no new field needed if the deterministic id is folded into `call_id` derivation (preferred — keeps CALL_FIELDS unchanged). The id stays opaque; only its *derivation* becomes deterministic.
- **Risk:** changing id derivation must not retro-duplicate existing rows — gate the new derivation to the no-stable-id path only; existing uuid-based ids are unchanged. Add a migration note (old random-id dups already in a ledger won't auto-heal; document `cage` can't rewrite the ledger — a one-time `--dedupe` compaction could be a follow-on).
- **Effort:** S–M. Determinism tests are the bulk.

### 3. `cage limits` view + derived credits  **[$0]**
- **What:** a read view that shows (a) local quota snapshots (from item 1) and (b) **estimated credits consumed** = tokens × per-model multiplier. Mirror caut's field shape: `primary/secondary` windows with `remaining_pct` + `resets_at`, plus `credits.estimated`.
- **Files:** new `limits.py` (sibling of `budget.py`/`report.py`, the derive logic); `clicmds.py` (`cmd_limits`); `cli.py` (`sub.add_parser("limits", …)` + `_json_flag` + `.set_defaults(fn=clicmds.cmd_limits)`); `policy.toml` (new `[credits.<provider>."<model>"] per_mtok = N` multipliers); `convert.py` or a small `credits.py` (tokens→credits, one place, mirroring `convert.saved_usd`).
- **Contract:** credits is a **derived estimate**, tagged `estimated` (never `measured`). Keep it out of the call/receipt contract; compute at derive time from calls + policy, exactly like `prices.call_usd` recomputes USD.
- **Risk:** multiplier accuracy — publish them as illustrative blended defaults (like the existing `[prices]`/`[human]` comments), overridable per project. Unpriced model ⇒ tracked by tokens, 0 credits shown (mirror the UNPRICED rule).
- **Effort:** M.

### 4. Versioned robot JSON (`cage.v1`)  **[$0]**
- **What:** every read view (`report/budget/attrib/roi/human/forecast/regression/limits`) emits a stable `{"schemaVersion":"cage.v1", ...}` envelope under `--json`. Aligns with the existing `--json` enhancement backlog.
- **Files:** `render.py` (one shared envelope helper); `clicmds.py` (route each view's `--json` through it). `_json_flag` already exists on the parsers.
- **Contract:** additive output format; no ledger change. Version it so agents parse stably.
- **Risk:** low. Keep human output byte-identical when `--json` absent.
- **Effort:** S–M (touches several views, but mechanical).

### 5. Fetch-plan refactor (ordered sources per agent)  **[$0 core]**
- **What:** generalize `importcmd._ADAPTERS` (one fn per agent) into an **ordered source list** per agent so higher-fidelity sources are tried first with graceful fallback — the precondition for items 6 & 7.
- **Files:** `importcmd.py` (`_ADAPTERS` → `_SOURCES = {"copilot": [otel, events], "kiro": [sqlite, jsonl], "codex": [rollout], "claude": [transcript]}`; `run_agent` iterates the chain, first non-empty wins or merges, all fail-open).
- **Contract:** no schema change; `seen`/cursor dedup already makes multi-source safe (item 2 hardens it).
- **Risk:** double-counting across two sources for the same agent → relies on item 2's dedup; sequence item 2 before 6/7.
- **Effort:** M.

### 6. Copilot OTEL exporter as primary source  **[$0]**
- **What:** read Copilot's OpenTelemetry file export (`COPILOT_OTEL_FILE_EXPORTER_PATH`) for **per-turn** capture instead of shutdown-only `events.jsonl` (which forces the one-session backfill lag).
- **Files:** `transcript.py` (`parse_copilot_otel` — stdlib JSON over the OTLP-json file); `paths.py` (`copilot_otel_path()`); `copilotwire.py` (set the env var when wiring so the exporter is actually on); `importcmd.py` (register as the first Copilot source, `events.jsonl` fallback).
- **Contract:** same `make_call` rows; richer timing. No new contract.
- **Risk:** ⚠️ **needs a verification probe** of the current Copilot OTLP-json shape before committing (versions vary). Keep `events.jsonl` as the guaranteed fallback. Mark as OPEN until probed.
- **Effort:** M (parser + probe).

### 7. Kiro SQLite as primary source  **[$0]**
- **What:** read Kiro's richer SQLite DB (`~/.kiro/...`) via stdlib `sqlite3` instead of (only) the coarse `tokens_generated.jsonl` cage's own docs flag as low-fidelity. Kiro's spec-vs-vibe **credit** data lives here too.
- **Files:** `transcript.py` (`parse_kiro_sqlite` — read-only `sqlite3` connect, defensive queries); `paths.py` (`kiro_sqlite_db()`); `importcmd.py` (register as first Kiro source, jsonl fallback).
- **Contract:** same call rows; optionally feed a Kiro credit snapshot into the `limits` record (item 3).
- **Risk:** ⚠️ Kiro DB schema churn — open read-only, wrap every query fail-open, fall back to jsonl on any error. Needs a probe of the current schema. Mark OPEN until probed.
- **Effort:** M.

### 8. Authoritative Copilot AI-credits (GitHub billing API)  **[opt-in net]**
- **What:** the only path to *remaining* GitHub AI-credit balance — stdlib `urllib` to `/users|orgs/{...}/settings/billing/ai_credit/usage`, fine-grained PAT via env.
- **Files:** new `ghbilling.py` (stdlib urllib, fail-open, never imported on the capture hot path); a `cage import-credits` opt-in command in `cli.py`; feeds the `limits` record tagged `source="github-api"`, `method`-equivalent `estimated`/external.
- **Contract:** off by default; a stored PAT is a secret (fintech flag) → reference by env only, never persisted by cage.
- **Risk:** breaks cage's "never talks to GitHub / reads-only-disk" property → strictly opt-in, documented divergence, off the hot path.
- **Effort:** M. **Do last, only if remaining-balance is actually needed.**

---

## Schema / substrate summary

| Change | Where | Kind |
|---|---|---|
| New `limits.jsonl` record + `make_limit_snapshot` + closed `window` enum | `schema.py`, `ledger.py` | new substrate (parallel to provenance) |
| Deterministic id derivation for stable-id-less calls | `schema.py`, `transcript.py` | **no** CALL_FIELDS change |
| `[credits.<provider>."<model>"]` multipliers | `policy.toml` | policy layer (not contract, not constants) |
| `cage.v1` JSON envelope | `render.py` | output format only |
| Fetch-plan ordered sources | `importcmd.py` | internal, no contract |

The three-audit-layers rule holds: enums/record shapes → `schema.py` (contract); credit multipliers → `policy.toml` (economics); any heuristic constants (e.g. default multiplier fallback) → `constants.py`.

---

## Recommended sequence

1. **Item 2 (composite dedup)** — correctness first; also the precondition for multi-source (5/6/7). Ship with tests.
2. **Item 1 (Codex rate_limits)** + the new `limits.jsonl` substrate — first real quota signal, $0, from data already parsed.
3. **Item 3 (`cage limits` view + derived credits)** — turns 1 + token data into a coherent surface.
4. **Item 4 (`cage.v1` JSON)** — fold into the `--json` enhancement packet.
5. **Item 5 (fetch-plan refactor)** — unblocks 6/7.
6. **Items 6 + 7 (Copilot OTEL, Kiro SQLite)** — gated on verification probes of current log/DB shapes.
7. **Item 8 (GitHub billing API)** — last, opt-in only.

Items 1–7 are all **$0 / stdlib / deterministic** — no constitutional waiver. Item 8 adds opt-in, dependency-free network and must stay off the capture hot path and be tagged non-`measured`.

---

## Constitutional / done checklist (every item)
- **$0 / stdlib only** — no new runtime dep (sqlite3, urllib, json are stdlib); ML extras untouched.
- **Determinism** — ids and derived views reproducible; `just demo` §4.4 numbers unchanged; tests assert exact figures.
- **Counts-never-content** — `limits.jsonl` carries percentages + reset timestamps only; no prompts, no balances tied to identity beyond what's needed.
- **Four agents always** — no change drops claude/codex/copilot/kiro; new sources are additive per agent.
- **Fail-open capture** — every new parser/source wraps per-line/per-file and fail-opens (existing `_ingest` pattern).
- **Method honesty** — credits are `estimated`, GitHub-API figures external/`estimated`, never `measured`.
- **Docs in same change** — `docs/cage-plan.md` (§3 new substrate; §6/§8 the limits view), `CHANGELOG.md` (newest first), `README` ("What's new" + test count), `CLAUDE.md` rule for the new `limits` substrate **proposed for review**.
- **Tests** — dedup (Claude no-uuid, sub-agent), Codex rate_limits parse, limits view, credits derive, JSON envelope, fetch-plan fallback; update the "N passing" count.

---

## Open questions (probe before building the gated items)
- OPEN: exact current shape of the Codex `token_count.rate_limits` block (field names, window labels) — confirm against a live rollout before finalizing the `make_limit_snapshot` enum.
- OPEN: Copilot OTLP-json export schema under the current CLI, and whether `COPILOT_OTEL_FILE_EXPORTER_PATH` is honored when set by `copilotwire.py` (item 6).
- OPEN: Kiro SQLite table/column names under the current build (item 7).
- OPEN: credit multipliers — source the per-model AI-credit rates (GitHub published rates for Copilot; Kiro spec/vibe units) for `policy.toml` defaults; ship illustrative blended values until confirmed, like the existing price/human defaults.
