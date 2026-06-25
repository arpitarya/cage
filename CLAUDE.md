# CLAUDE.md — Context for Claude Code

**Cage** — a *flux*: a deterministic attribution ledger for LLM token traffic and
tool savings. Third in the family after **graphify** (code→graph) and **fux**
(decisions→rules). `$0`, stdlib-only, deterministic, independent of any AI tool.

Design of record: [docs/cage-plan.md](docs/cage-plan.md). Read it before changing
the substrate contract or the attribution engine.

## Architecture (the one-way data flow)

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks,provenance}.jsonl  (append-only)
        (meter, plan §5)                      │
                                              ▼  derive ($0, no model)
  policy.toml (prices/order/budgets/human) → report · attrib · matrix · budget
                                             · roi · human · trend · why · origin

provenance.jsonl is a local buffer only — canonical storage is
refs/notes/cage-provenance, written by CI alone (plan §3.5).
```

- **Substrate** ([schema.py](cage/schema.py)) — `make_call` / `make_receipt` stamp
  ids + validate the closed enums. Rows are plain JSON. Prompt bodies are never a
  field (counts only). Change here = change the contract; update the plan §3.
- **Constants** ([constants.py](cage/constants.py)) — the *third audit layer*. Cage
  keeps its numbers in three places, never mixed: **contract** = the enums in
  `schema.py`; **policy** = user-economics in `policy.toml`; **constants** = code
  heuristics not meant as config but that must be reviewable (`CHARS_PER_TOKEN`,
  `TOKENS_PER_MILLION`, `MAX_MATRIX_TOOLS`, `METHOD_TRUST`, `DEFAULT_CONFIDENCE`,
  `GRAPHIFY_RECEIPT_CONFIDENCE`, `SINCE_WINDOW_DAYS`). `compress`/`prices`/`matrix`/
  `attribution`/`human`/`ledger`/`graphifymeter` import from here. `DEFAULT_CONFIDENCE`
  is a *fallback* — `human.py` still prefers policy `[human.confidence]`. The
  third-party shims (`fux/cage_receipt.py`, graphify) keep a local `len/4` copy
  because they're zero-dep; it's an intentional duplicate of `CHARS_PER_TOKEN`.
- **Explain** ([explain.py](cage/explain.py) engine,
  [explain_data.py](cage/explain_data.py) registry) — `cage query` answers both
  "how is X calculated" (`kind="calculation"`, the original 12 — formulas
  interpolate **live** values from policy + constants; set `CAGE_HUMAN_RATE` ⇒ the
  printed rate changes, never a hard-coded literal) and "how does cage work"
  (`kind="concept"` — `overview`/`data-flow`/`metering`/`attribution`/
  `matrix-concept`/`method-law`/`receipts`/`human-axis`/`determinism`/
  `pii-safety`/`numbers-layers`; structural facts interpolate live too — ledger
  paths from `paths.Footprint`, pipeline order from `policy.tool_order(pol)`,
  agent surfaces from `agents.SURFACES`, subcommand count from the CLI parser —
  and every concept entry carries a `code_refs` + `plan_ref` anchor). Matching is
  stdlib token-overlap across both kinds; **no LLM, no network** (cage law). No
  match ⇒ suggest closest ids, never guess. `--list --kind concept|calculation`
  filters; `cage --help` groups subcommands and points at `cage query`.
- **Ledger** ([ledger.py](cage/ledger.py)) — the only mutation is append; reads
  tolerate a truncated tail. Everything else derives.
- **Meter** ([metering.py](cage/metering.py)) — the library adapter. **Fail-open**:
  a metering error must never propagate into a request path. The public name is
  `cage.meter` (a context manager); the *module* is `cage.metering` — keep them
  distinct or the package attribute shadows the submodule.
- **Attribution** ([attribution.py](cage/attribution.py), [matrix.py](cage/matrix.py))
  — the differentiator (plan §4). Marginal-by-fixed-order; a reconstructed
  counterfactual cell is `modeled`/`estimated`, never `measured` (only the recorded
  run is an invoice). `cage demo` must keep reproducing the plan's §4.4 tables.
- **Unit→USD** ([convert.py](cage/convert.py)) — the single dispatch for a receipt's
  `saved` in dollars: `usd` passthrough · `tokens` at model price · `minutes` at the
  human rate · `ms`/`gco2` → `$0`. `roi`/`attribution` route through it (one place
  unit semantics live).
- **Per-call cost** ([prices.py](cage/prices.py) `call_usd`) — `report`/`budget`
  **recompute** each call from `tokens × policy` at derive time, falling back to the
  stored `est_cost_usd` only when the model is unpriced. A token-only meter (the
  transcript meter never sets `est_cost_usd`) thus still costs out, and a
  self-costing provider Cage can't tokenize keeps its figure. Derive-time only — the
  ledger is never rewritten. A call prices only if `(provider, model)` is in the
  table; the transcript meter stamps `provider="anthropic"`, so that key must carry
  the Claude rows (the bundled `data/policy.toml` does; a project policy must too).
- **Tier-1 human axis** ([human.py](cage/human.py), [humanview.py](cage/humanview.py),
  [trend.py](cage/trend.py)) — *agent vs human* (design doc `docs/human-baseline.design.md`).
  A human receipt is just `tool="human"`; `human.py` resolves minutes/type/usd → USD
  by a fixed precedence + confidence ladder. **Human cost is `estimated` by default**
  (never `measured` unless a real timesheet/quote, never `modeled`). Rates live in
  `[human]` in `policy.toml`; `CAGE_HUMAN_RATE` overrides at derive time and its
  provenance prints in the `cage human` header. `matrix --human` adds the anchor row
  behind the flag (no flag ⇒ byte-identical). `cage human`/`cage trend` show **saved
  $ and saved hrs** (time can go negative — the metric can embarrass the agent).
- **Task record** ([tasks.py](cage/tasks.py)) — `tasks.jsonl`, one row per task
  (last-write-wins by `id`), git-snapshotted at task close (SessionEnd / `cage
  outcome`). **Shelled out to git, never imported; fail-open** (non-repo/detached ⇒
  omit fields). PII guard: SHA + diff *counts* + top-level dirs only — never the
  commit message, author identity, or file paths.
- **Provenance (authorship attribution)** ([schema.py](cage/schema.py) `make_provenance`,
  [originrecord.py](cage/originrecord.py) write side, [origin.py](cage/origin.py) read
  surface, [notessync.py](cage/notessync.py) distribution, [verifycmd.py](cage/verifycmd.py))
  — *who wrote which files in which commit* (plan §3.5), a fourth append-only file
  (`provenance.jsonl`) answering a different question than calls/receipts/tasks. Its
  own closed enums, deliberately separate from `METHODS`/`UNITS`: `method ∈
  {hooked, transcript, heuristic}` (ranked by `constants.PROVENANCE_METHOD_TRUST`,
  a parallel ladder to `METHOD_TRUST`) and `origin ∈ {human, agent,
  agent-autonomous, unknown}`. **`unknown` is a read-time default, never a written
  row** — a sha with no signal has no row at all; `origin.explain` derives unknown
  from absence. `origin="human"` is reachable only via explicit attestation
  (`cage origin <sha> --attest human`), always paired with `method="heuristic"`
  (enforced at `make_provenance` construction). Captured by a `PostToolUse` hook
  (buffers edits per session) resolved at a `post-commit` git hook
  ([gitcommithook.py](cage/gitcommithook.py), installed by `cage setup`/`agents.install`
  alongside the Claude Code hooks) into the highest-trust `hooked` row, with a
  `SessionEnd`-time transcript fallback ([transcript.py](cage/transcript.py)
  `parse_provenance`) for what the live hook missed. The local jsonl is a **buffer
  only**; canonical storage is `refs/notes/cage-provenance`, merged by row id
  (never overwritten) and **written only by CI** (`CAGE_NOTES_WRITE=1`) — a dev
  machine's `cage notes-sync` defaults to a dry-run print. `cage verify` is
  **report-only and always exits 0** (never a CI gate). Widens the PII surface to
  repo-relative file *paths* (vs. `tasks.jsonl`'s top-level-dirs-only) — justified
  in plan §3.5 — but counts-never-content still holds: no diff bodies, no commit
  messages, paths validated repo-relative at construction time.

## Must-Know Rules

- **$0 / stdlib only** — `dependencies = []`. ML is opt-in extras (`[embeddings]`,
  `[ml]`), never imported on the default path.
- **Fail-open everywhere on the write path** — `ledger.append` returns `False`, it
  never raises; `meter()` swallows errors in cleanup. Metering is best-effort.
- **Determinism** — no clocks/random in derived views; ids carry the only entropy.
  Same ledger + same policy ⇒ same tables. Tests assert exact plan numbers.
- **`method` is sacred** — never let a projection read as `measured`. Tag every cell.
- Keep modules small and single-purpose (fux spirit). Tests live in `tests/`.

## Dev

```bash
just test          # python -m pytest -q   (112 passing)
just demo          # seed §4.4 + print attrib/matrix
cage --version
```

## Adapters & agents (one ledger, many surfaces)

Cage targets the **wire protocol**, so the meter and read surface are universal and
each agent only needs thin idiomatic wiring (`agents.py` orchestrates):

- **Meter:** `metering.py` (library), `proxy.py` + `usageparse.py` (any client you
  point a base URL at), `transcript.py` (Claude Code / Codex session logs).
- **Read:** `mcpserver.py` (MCP, every agent), `report/attrib/matrix/budget/roi`,
  plus the Tier-1 human axis (`human`/`trend`, `matrix --human`) and authorship
  (`origin`/`notes-sync`/`verify`, plan §3.5).
- **Wiring:** `claudewire.py` (hooks+MCP), `codexwire.py` (TOML MCP), `pointers.py`
  (copilot/kiro steering+MCP), `setupcmd.py` (`/cage` skill), `gitcommithook.py`
  (local `post-commit`/`prepare-commit-msg` git hooks, riding along with
  `claudewire.py` inside `agents.install`). All idempotent.
- **§8 features:** `quality.py`, `regression.py`, `recommend.py`, `forecast.py`.
- **Tier-0 savings:** `compress.py`, `responsecache.py` (emit receipts).

## Integrations

- **AlphaForge Anton (Orff)** — first consumer. Anton's `LLMGateway` records each
  `ProviderResponse` via a fail-open `cage_meter` adapter (`anton/docs/cage.md`).
  Cage is wired there as an optional `[cage]` extra (uv path source).

<!-- cage:start -->
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage attrib` · budget: `cage budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/policy.toml`.
<!-- cage:end -->
