# Token/credit trackers for Copilot · Claude · Kiro · Codex — landscape + lessons for the cage meter

**Date:** 2026-06-30 · **Purpose:** survey real OSS trackers across cage's four agents, then extract what concretely improves cage's meter — filtered through cage's constitution ($0, stdlib-only, deterministic, PII-safe counts-never-content, four-agents-always).

---

## Part 1 — The landscape (repos worth learning from)

### Multi-agent (closest peers to cage)

| Repo | Lang | Agents covered | Capture method | Tokens | Credits/quota | Mine it for |
|---|---|---|---|---|---|---|
| **mm7894215/TokenTracker** | Node | 22 incl. **all 4** (Claude, Codex, Kiro, Copilot) | hooks + **passive readers** (SQLite/JSONL/OTEL) | ✅ | ✅ rate-limit windows for 7 providers | Per-agent parse methods; **Copilot OTEL exporter**; **Kiro SQLite**; composite-key dedup; 30-min UTC buckets |
| **Dicklesworthstone/coding_agent_usage_tracker (caut)** | Rust | Codex, Claude, Copilot, Kiro, +12 | **multi-source fetch plan** CLI→Web→OAuth→API→Local | ✅ (local JSONL) | ✅ session/weekly/credits remaining | **Fetch-strategy fallback chain**; versioned robot JSON (`caut.v1`); credits schema; exit-code taxonomy |
| **junhoyeo/tokscale** | TS | Claude, Codex, Pi, Gemini, Amp, Droid… | passive log readers | ✅ | partial | Breadth of session-log formats; leaderboard model |
| **steipete/CodexBar** | Swift | Codex, Claude, Copilot, +13 (macOS) | CLI RPC + cookies + OAuth | ✅ | ✅ remaining usage | The original caut ports; menu-bar UX; "no login" usage reads |
| **openusage.sh / OpenUsage** | — | 34 tools | spend/quota/rate-limit/burn-rate | ✅ | ✅ | Burn-rate + quota dashboard concepts; headless reporting |
| **handlecusion/tokcat**, **AgentLimits** | Swift/TS | Claude, Codex, Cursor, Copilot | passive + menu bar | ✅ | ✅ remaining | "always-visible remaining" widget framing |

### Claude-focused

| Repo | Lang | Method | Mine it for |
|---|---|---|---|
| **ryoppippi/ccusage** | TS | reads `~/.claude/projects/**/*.jsonl` | The de-facto JSONL parse contract; daily/session/model rollups; **also supports Codex** (ccusage.com/guide/codex) |
| **badlogic/cccost** | TS | instruments Claude Code | Actual-cost (not estimated) instrumentation |
| **Maciek-roboblog/Claude-Code-Usage-Monitor** | Py | real-time monitor + predictions | Burn-rate prediction, reset-window warnings |
| **aarora79/claude-code-usage-analyzer** | Py | ccusage + LiteLLM pricing | Pricing-data join pattern |

### Codex-focused

| Repo | Lang | Method | Mine it for |
|---|---|---|---|
| **douglasmonsky/codex-usage-tracker** | — | reads rollout JSONL → SQLite | **`token_count.rate_limits` → 5h/weekly remaining %** (credits-ish, already in local logs!) |
| **CasperKristiansson/codex-usage-tracker** | — | ingests `rollout-*.jsonl` → SQLite | `TokenCount` event extraction; SQLite reporting model |
| **PixelPaw-Labs/codex-trace** | — | `~/.codex/sessions` JSONL viewer | Live-tail; tool-call/token inspection |
| **majiayu000/ccstats** | — | Claude + Codex logs | Fast CLI analytics shape |

### Kiro-focused

| Repo | Lang | Method | Mine it for |
|---|---|---|---|
| **weswes0/kiro-usage-tracker** | — | parses Kiro local SQLite + JSONL | Kiro's spec-vs-vibe **credit** model; SQLite schema |
| **kiro-usage (PyPI)** | Py | stores Kiro tokens as JSON/JSONL | Python parse reference |
| **kirodotdev/Kiro#1407** | issue | — | Confirms Kiro exposes "% credits used + token cost per request" demand (the credit unit) |

### GitHub Copilot-focused (credits live server-side — see prior research)

| Repo | Method | Mine it for |
|---|---|---|
| **github-copilot-resources/copilot-metrics-viewer** | Copilot Metrics API + `ai_credits_used` | Org/user AI-credits field shape |
| **microsoft/copilot-metrics-dashboard** | Metrics + User Mgmt API | Org data model |
| **thomast1906/github-copilot-usage-metrics-viewer** | premium-request usage | Per-user premium-request flow |

---

## Part 2 — What this teaches us about fixing the cage meter

Ranked by value × constitution-fit. Each is tagged **[$0]** (no network/dep) or **[opt-in net]**.

### A. Extract Codex `token_count.rate_limits` — credits/quota for free **[$0] — do first**
cage already reads Codex `rollout-*.jsonl` (`transcript.parse_codex_calls`). Those logs **already contain** `token_count.rate_limits` with **5-hour and weekly remaining %** (proven by douglasmonsky/codex-usage-tracker). cage just isn't extracting it. This is the single highest-value, lowest-cost fix: a real quota/credits signal for Codex, deterministic, no network, no dependency — from a file cage already parses. Surface it in a new `cage limits` view.

### B. Copilot OpenTelemetry file exporter — real-time, not shutdown-lagged **[$0]**
cage's Copilot path reads `session-state/<id>/events.jsonl`, which only finalizes usage at `session.shutdown` (so cage backfills on the *next* session — laggy by design). TokenTracker instead uses Copilot's **OTEL file exporter** (`COPILOT_OTEL_FILE_EXPORTER_PATH`), which emits per-turn telemetry to a file cage could parse with stdlib JSON. Add it as a **higher-fidelity primary** with `events.jsonl` as the fallback. Eliminates the one-session lag. (Verify the OTLP-json shape against current Copilot CLI before committing.)

### C. Kiro SQLite over `tokens_generated.jsonl` — finer data, still stdlib **[$0]**
cage's own CLAUDE.md admits Kiro's `tokens_generated.jsonl` is *coarse*. TokenTracker and weswes0/kiro-usage-tracker read Kiro's **SQLite DB** (`~/.kiro/...`, polled). Python's `sqlite3` is **stdlib** — no dependency. cage can read the richer SQLite as primary, keep the jsonl as fallback (Kiro's spec-vs-vibe **credit** model lives there too). Guard against schema churn (read defensively, fail-open).

### D. Composite-key dedup — accuracy fix for Claude sub-agents **[$0] — correctness**
TokenTracker's headline accuracy claim: reqId/uuid-based dedup **over-counts by 1.6–3.7×** for providers/flows that omit a stable request id — explicitly including **Claude sub-agents**. cage dedups by a `call_id` derived from session/turn uuid, so it's exposed to the same over/under-count when Claude spawns sub-agents. Move to a **composite dedup key** (session + turn + model + token-shape) so `cage report` matches the provider's own billing. This is a determinism-preserving correctness fix, and cage's tests already assert exact numbers — add sub-agent cases.

### E. Multi-source fetch plan with fallback — architecture **[$0 core]**
caut's core design: each provider has a **fetch-strategy chain** (CLI → Web → OAuth → API → Local) tried in priority order, failing gracefully to partial results. cage has `_ADAPTERS` (one method per agent) + proxy fallback, but not a unified per-agent **plan with ordered fallback**. Generalize `_ADAPTERS` into a fetch-plan so each agent declares ordered sources — Copilot: `OTEL → events.jsonl`; Kiro: `SQLite → jsonl`; Codex: `rollout-jsonl (+rate_limits) → proxy`. Keeps fail-open; makes B/C drop-in.

### F. Credits as a first-class two-tier concept — mirror the field model **[$0] + [opt-in net]**
Both peers cleanly separate **tokens** (local, real-time) from **credits/quota** (remaining %, reset windows). cage should add a `credits`/`limits` axis with two tiers:
- **[$0] Derived credits** = tokens × per-model multiplier in `policy.toml` (fits `convert.py`/`prices.py`; the recommendation from the prior research note). Deterministic estimate of consumption.
- **[$0] Local quota signals** where they exist (Codex `rate_limits` from A; Kiro credits from C).
- **[opt-in net] Authoritative** Copilot AI-credits via the GitHub billing API using **stdlib `urllib`** (no `gh`, no dep), strictly opt-in, off the hot path, tagged `estimated`/external.
Adopt caut's response shape: `usage.{primary,secondary,tertiary}` (session/weekly/tier) with `usedPercent/remainingPercent/windowMinutes/resetsAt` + `credits.remaining`.

### G. Versioned robot JSON for every read command **[$0]**
caut ships a stable `schemaVersion: "caut.v1"` for agent consumption; TokenTracker has `status --json`. This is exactly the `--json` enhancement already in the cage backlog — formalize it as a **versioned `cage.v1`** envelope so agents (the agent-as-user) parse cage output stably. Dual human/robot output, one shared formatter.

### H. Pricing-snapshot discipline — validation of what cage already does **[$0]**
TokenTracker prices 2,200+ models via LiteLLM's `model_prices` JSON with a **24h disk cache + bundled offline snapshot**, and tracks unpriced models by tokens at **$0 cost** until a rate exists. cage already prices from `policy.toml` and shows $0 for unpriced models — same invariant, confirmed correct. Optional improvement: a bundled offline snapshot + an **opt-in** refresh helper (never on the derive path). Do **not** take a LiteLLM runtime dependency.

### I. doctor / status / exit-code taxonomy — reinforces the error-handling packet **[$0]**
All three top peers ship `doctor` + structured `status` + clear exit codes. caut's taxonomy (`0` ok · `1` general · `2` binary-not-found · `3` parse/config · `4` timeout) is a clean reference for cage's documented exit-code contract (the error-handling handoff). cage already has `cage doctor`/`cage debug` — align the codes + add `status --json`.

### J. Privacy invariant — peer-validated **[$0]**
TokenTracker and caut both store **only token counts + timestamps, never prompts/responses/content**. This is cage's existing PII-safe-by-construction law. The landscape confirms it's the right and expected invariant — keep it as the hard line, and it's a genuine differentiator vs. anything that reads transcripts.

---

## Part 3 — Recommended sequence (all constitution-safe)

1. **A** (Codex `rate_limits`) + **D** (composite dedup) — both $0, both fixes to code cage already runs; A adds a real credits signal, D fixes accuracy. Smallest, highest value.
2. **F-tier-1** (derived credits in `policy.toml` + a `cage limits` view with the caut field shape) — turns A + token data into a coherent credits surface.
3. **G** (versioned `cage.v1` JSON) + **I** (exit codes/`status --json`) — fold into the existing `--json` / error-handling packets.
4. **E** (fetch-plan refactor) — unblocks B/C as ordered fallbacks.
5. **B** (Copilot OTEL) + **C** (Kiro SQLite) — higher-fidelity capture, gated on E + a shape-verification probe.
6. **F-authoritative** (opt-in GitHub billing via stdlib urllib) — last, only if remaining-balance is actually needed; never on the hot path.
7. **H** snapshot polish — optional.

Items A, B, C, D, E, G, I, J are **all $0/stdlib/deterministic** — they fit cage's constitution with no waiver. Only F-authoritative adds (opt-in, dependency-free) network, and it must stay off the capture hot path and be tagged non-`measured`.

---

## Sources
- TokenTracker — https://github.com/mm7894215/TokenTracker
- caut (coding_agent_usage_tracker) — https://github.com/Dicklesworthstone/coding_agent_usage_tracker
- ccusage — https://github.com/ryoppippi/ccusage · Codex guide: https://ccusage.com/guide/codex/
- douglasmonsky/codex-usage-tracker — https://github.com/douglasmonsky/codex-usage-tracker
- CasperKristiansson/codex-usage-tracker — https://github.com/CasperKristiansson/codex-usage-tracker
- PixelPaw-Labs/codex-trace — https://github.com/PixelPaw-Labs/codex-trace
- tokscale — https://github.com/junhoyeo/tokscale
- CodexBar — https://github.com/steipete/codexbar · tokcat — https://github.com/handlecusion/tokcat
- weswes0/kiro-usage-tracker — https://github.com/weswes0/kiro-usage-tracker · kiro-usage (PyPI) — https://pypi.org/project/kiro-usage/
- Kiro #1407 (credits/token cost request) — https://github.com/kirodotdev/Kiro/issues/1407
- copilot-metrics-viewer — https://github.com/github-copilot-resources/copilot-metrics-viewer · microsoft/copilot-metrics-dashboard — https://github.com/microsoft/copilot-metrics-dashboard · thomast1906/github-copilot-usage-metrics-viewer — https://github.com/thomast1906/github-copilot-usage-metrics-viewer
- OpenUsage — https://openusage.sh/
