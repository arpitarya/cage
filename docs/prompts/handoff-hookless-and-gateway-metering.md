# Handoff + Prompt: finish hookless metering (all agents) → org gateway

Self-contained handoff for Claude Code (no chat history needed). **Part of this was
already implemented — section 2 records what's DONE so you don't redo it.** The
remaining work is: finish four-agent coverage for the per-dev hookless path
(Phase 1), then build the org-wide zero-setup gateway (Phase 2). They're one
continuum — the gateway is the multi-tenant evolution of the per-dev proxy — so do
Phase 1 first and reuse it.

---

## 1. Context / handoff

**What cage is.** A *flux*: a $0, stdlib-only, deterministic append-only ledger for
LLM token traffic + tool savings. One ledger, many agent surfaces. Read
`docs/cage-plan.md` (§5 metering, §9.5, §3 contract, §10 privacy) and `CLAUDE.md`
before changing the metering or substrate contract.

**Hard project invariant — non-negotiable.** Every cage feature must support all four
agents: **Claude Code, Codex, Copilot, Kiro.** A feature that meters only one or two
is incomplete. Anything that can't reach an agent must say so explicitly and print
that agent's supported fallback — never silently skip it.

**Additive, never a replacement.** Hooks + MCP remain the default, preferred path
(real-time capture, the `SessionStart` budget banner). Everything here runs
*alongside* hooks. Do NOT remove, deprecate, or alter the hook entrypoints. A call
metered by both a hook and an import/gateway must dedupe by id — no double-count.

**The honest mechanism split (design around it, don't fight it).** Two hookless
mechanisms; neither alone covers four agents:
1. *Log/transcript import* — only works where the agent persists token usage to disk:
   Claude Code (`~/.claude/projects/**/*.jsonl`) and Codex
   (`~/.codex/**/rollout-*.jsonl`). Per `cage/pointers.py`, **Copilot and Kiro do not
   expose a usage transcript** — verify empirically; if confirmed, there is nothing to
   import for them.
2. *Proxy / gateway* — wire-level, needs no hooks, no MCP, no on-disk log. The
   **universal** path that covers all four and the only hookless option for an agent
   that doesn't log usage.

**Reusable machinery:** `transcript.parse_calls`, `transcript.parse_codex_calls`,
`paths.claude_home()/codex_home()/kiro_home()`, `paths.claude_project_slug()`,
`hooks.append_new()` (idempotent by call id), `ledger.since_cutoff()`,
`schema.make_call`, `policy.price_match()`, `proxy.py` + `usageparse.py`.

---

## 2. Already implemented — DO NOT redo (verify, then build on)

- **Pricing family-fallback — DONE.** `policy.price_match(pol, provider, model)`
  returns `(row, match, key)` with `match ∈ {exact, family, none}`; exact wins, else
  longest shared hyphen-segment prefix on the same provider (≥
  `constants.MODEL_FAMILY_MIN_SEGMENTS = 2`, so brand+tier must agree; deterministic
  tie-break). `report` already surfaces UNPRICED models and "≈ priced by family
  (approximate)". Tests: `tests/test_pricing.py`, `tests/test_report_savings.py`.
  *Use price_match in any new test so a $0 never masks a broken import.*
- **`cage import-claude` — DONE.** Per-dev Claude Code hookless import from
  `~/.claude/projects`, with `--path`, `--project` (uses
  `paths.claude_project_slug`), `--since` (uses `ledger.since_cutoff` →
  `constants.SINCE_WINDOW_DAYS`); fail-open per file, idempotent via `append_new`.
  Tests: `tests/test_import_claude.py`.
- **`cage import-codex` — EXISTS** (separate command) — the Codex on-disk path.
- **`cage doctor` — PARTIAL.** Prints a single Claude-only hint ("Hooks blocked by
  your org? Meter Claude Code with `cage import-claude`"). Not yet a four-agent matrix.

---

## 3. Phase 1 — finish four-agent coverage for the hookless path

The two import commands cover only Claude + Codex. Close the invariant gap; keep
existing commands working (don't break `import-claude`/`import-codex`).

1. **Umbrella `cage import [--agent claude|codex|copilot|kiro|all]`** (default
   `all`), wired in `cli.py` → `clicmds.py`. It dispatches to the existing per-agent
   importers (treat `import-claude`/`import-codex` as the Claude/Codex adapters; keep
   them as working aliases). Pass through `--path`/`--project`/`--since` where they
   apply. Print one line per agent, e.g.
   `✔ claude: imported N call(s) from M transcript(s).`
2. **Copilot & Kiro: explicit fallback, never a silent skip.** If (verify first) they
   have no on-disk usage log, `cage import --agent copilot` (and `kiro`, and the
   `--all` summary) must print the exact supported path, e.g.
   `· copilot: no on-disk usage log — meter via the proxy: cage meter -- <cmd>`.
   If you discover either *does* persist usage, add a real adapter instead.
3. **`cage doctor`: replace the Claude-only hint with a four-row metering matrix** —
   for each agent: hook / proxy / import status, and if none, the exact command to
   enable hookless capture. Reuse `agents.SURFACES` so the list stays canonical.

**Phase 1 acceptance.** `tests/` cover, **for each of the four agents**: reachable via
`cage import --agent <x>`; log-bearing agents (claude, codex) import fixture rows with
correct token counts and are idempotent on re-import (incl. a no-op when a hook
already recorded the same turns); no-log agents emit the asserted proxy-instruction
line and exit 0; `--all` runs every adapter; existing `import-claude`/`import-codex`
still pass. `cage doctor` renders the four-agent matrix. `just test` stays green
(currently 112+ passing); no existing plan-number assertion changes.

---

## 4. Phase 2 — `cage gateway`: org-deployed, zero per-dev setup

Goal: meter all four agents org-wide with **no per-developer action** — the org
deploys one thing (config pushed by MDM / a shared gateway), every dev's traffic is
metered into a central ledger. Start with `docs/org-gateway.design.md`; too large to
land undocumented. Additive — a shop using per-dev hooks/import must be able to ignore
the gateway entirely.

**Resolve the $0/stdlib tension with two tiers (keep the core stdlib):**
- **Tier A — managed explicit proxy (default, stdlib, $0).** Generalize `cage proxy`
  into a multi-upstream, multi-tenant `cage gateway`. Devs reach it because MDM /
  managed config pushes base-URL + proxy env (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`,
  `HTTPS_PROXY`, …) and the gateway TLS cert machine-wide — zero *manual* setup.
  Covers every client honoring base-URL/proxy env (Claude Code, Codex).
- **Tier B — transparent interception (opt-in extra `[gateway-mitm]`, NOT default).**
  For endpoint-pinned agents that ignore base-URL/proxy env (verify — likely Copilot
  and Kiro), the only capture is transparent egress interception with an org-deployed
  trusted root CA. Fence behind an optional extra with its own cert-toolchain
  dependency (like `[embeddings]`/`[ml]`); never imported on the $0 default path.
  Document trust/security implications loudly.

**Build:** multi-upstream routing by Host/SNI to the correct real API
(Anthropic/OpenAI/Copilot/Kiro), parse `usage` per provider via `usageparse.py`
(extend as needed), forward bytes verbatim; **fail-open & safety-critical** — a
degraded gateway falls back to direct egress with a metric, never blocks/alters a
request. Per-dev/team attribution as a first-class optional (closed) field via
`schema.make_call`, storing a **hashed** identity (token fingerprint or MDM-injected
`X-Cage-Dev` header), never the raw token (update contract + plan §3).
Concurrency-safe central ledger (advisory lock or per-writer shards merged at read);
preserve append-only + deterministic derived views. Per-agent reachability matrix in
the design doc backed by observed client behavior. `cage doctor --gateway` reports
reachability; `docs/org-gateway.deploy.md` gives the MDM payload (Tier A) + root-CA
route (Tier B) with a security checklist.

**Phase 2 acceptance.** Design doc with the observed Tier A/B matrix. Tier A gateway
in stdlib: routes ≥2 upstreams, parses usage, tags hashed per-dev identity, central
concurrency-safe ledger. `tests/`: multi-upstream routing; usage parsed per provider;
identity hashed (assert raw token absent); concurrent appends don't corrupt or
double-count; gateway-error path passes traffic through unmetered (fail-open). Tier B
scaffolded behind the opt-in extra with the security writeup (impl may be phased; the
seam must exist; core must not import it). `just test` green.

---

## 5. Cage law (both phases)

- **All four agents first-class** — adapters, routing tables, and tests enumerate
  Claude Code, Codex, Copilot, Kiro.
- **Additive** — hooks/MCP/per-dev proxy/import keep working unchanged; never
  deprecated.
- **$0 / stdlib only** on the default path; cert/MITM toolchain only in an opt-in
  extra.
- **Counts-never-content** — tee `usage` only; never persist prompt/response bodies,
  secret headers, or raw tokens. Strictest where the gateway sees raw traffic.
- **Fail-open + idempotent** — malformed input skipped, never raises; re-run/double-
  capture deduped by id; degraded gateway passes traffic through.
- **Determinism** — same inputs + same policy ⇒ byte-identical derived tables, even
  with sharded concurrent writers. Clocks may filter (`--since`), never enter a stored
  row.

## 6. Out of scope

No inspection/storage of prompt-response content ever; no silent request blocking; no
daemon/live-tail in Phase 1; no fabricating a usage signal an agent doesn't emit. If
an agent genuinely can't be captured without endpoint changes you don't control, say
so in the matrix rather than claiming coverage. Tier B is never the default.

## 7. Suggested order

1. Phase 1: umbrella `cage import` + Copilot/Kiro proxy guidance + four-agent doctor
   matrix (small, finishes the invariant on work already started).
2. Phase 2 design doc + reachability matrix.
3. Tier A gateway. 4. Tier B scaffold behind the extra.
