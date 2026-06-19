# CLAUDE.md — Context for Claude Code

**Cage** — a *flux*: a deterministic attribution ledger for LLM token traffic and
tool savings. Third in the family after **graphify** (code→graph) and **fux**
(decisions→rules). `$0`, stdlib-only, deterministic, independent of any AI tool.

Design of record: [docs/cage-plan.md](docs/cage-plan.md). Read it before changing
the substrate contract or the attribution engine.

## Architecture (the one-way data flow)

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks}.jsonl  (append-only)
        (meter, plan §5)                      │
                                              ▼  derive ($0, no model)
  policy.toml (prices/order/budgets/human) → report · attrib · matrix · budget
                                             · roi · human · trend · why
```

- **Substrate** ([schema.py](cage/schema.py)) — `make_call` / `make_receipt` stamp
  ids + validate the closed enums. Rows are plain JSON. Prompt bodies are never a
  field (counts only). Change here = change the contract; update the plan §3.
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
just test          # python -m pytest -q   (78 passing)
just demo          # seed §4.4 + print attrib/matrix
cage --version
```

## Adapters & agents (one ledger, many surfaces)

Cage targets the **wire protocol**, so the meter and read surface are universal and
each agent only needs thin idiomatic wiring (`agents.py` orchestrates):

- **Meter:** `metering.py` (library), `proxy.py` + `usageparse.py` (any client you
  point a base URL at), `transcript.py` (Claude Code / Codex session logs).
- **Read:** `mcpserver.py` (MCP, every agent), `report/attrib/matrix/budget/roi`,
  plus the Tier-1 human axis (`human`/`trend`, `matrix --human`).
- **Wiring:** `claudewire.py` (hooks+MCP), `codexwire.py` (TOML MCP), `pointers.py`
  (copilot/kiro steering+MCP), `setupcmd.py` (`/cage` skill). All idempotent.
- **§8 features:** `quality.py`, `regression.py`, `recommend.py`, `forecast.py`.
- **Tier-0 savings:** `compress.py`, `responsecache.py` (emit receipts).

## Integrations

- **AlphaForge Anton (Orff)** — first consumer. Anton's `LLMGateway` records each
  `ProviderResponse` via a fail-open `cage_meter` adapter (`anton/docs/cage.md`).
  Cage is wired there as an optional `[cage]` extra (uv path source).
