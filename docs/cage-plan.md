# Cage — a *flux*

> **Cage** is a *flux*: a deterministic engine for the **flow of tokens and
> calls** through an AI tool stack. It meters every LLM call, collects a
> **savings receipt** from each tool in the stack (Claude vs. not, graphify vs.
> not, fux vs. not, cache vs. not…), and turns the raw stream into an
> **attribution ledger** — what you spent, what each tool saved you, and what
> any *other* combination of tools would have cost. `$0`, stdlib-only,
> deterministic, and independent of any single AI tool.

Status: **design of record (v0.1)**. Nothing built yet. This document defines
the category, the substrate, the attribution engine, and the build order.

---

## 1. The category: what a *flux* is

The family already has two deterministic "substrate → derived views" tools:

| Tool          | Substrate (what you own)            | Derived views                  | Runtime cost |
| ------------- | ----------------------------------- | ------------------------------ | ------------ |
| **graphify**  | code structure (AST)                | knowledge graph, wiki, paths   | `$0` (AST)   |
| **fux**       | decisions, rules, memory (frontmatter) | INDEX, graph, recall, savings  | `$0` (parse) |
| **Cage** *(new)* | **LLM traffic + savings receipts** (event log) | ledger, attribution, counterfactuals, budgets | `$0` (accounting) |

A **flux** is the third instance of the same philosophy, pointed at a new
substrate — *the economics of LLM traffic* — instead of code or knowledge:

1. **A substrate you own** — an append-only event log of calls and receipts.
2. **Derived views built deterministically** — ledger, attribution table,
   counterfactual matrix, dashboard. No model in the maintenance path.
3. **`$0`, stdlib-only, deterministic** — same constitution as fux. Heavy ML is
   an *optional, off-by-default* tier, never a requirement.
4. **Agent-aware** — hooks + MCP, like fux, so an agent can read its own spend.
5. **Improvable by AI, independent of it** — the deterministic core is the
   product; AI is a tier you can switch on, never a coupling you inherit.

The lineage is explicit: graphify inspired fux; fux's skeleton (CLI dispatch,
hooks, MCP, optional-extras, plugin packaging) is forked to seed Cage. The rule
logic is *not* carried over — Cage's substrate and lifecycle are different
(runtime/in-path vs. build-time/on-disk), which is exactly why it's a sibling
and not a fux feature.

---

## 2. Why a new tool, not headroom and not a fux feature

**Not headroom.** headroom couples to named tools (`headroom wrap copilot`),
and ships a Rust core + ONNX runtime + HuggingFace models — the opposite of the
`$0`/stdlib constitution. Its *ideas* (prefix-stable caching, JSON folding,
reversible truncation) are Apache-2.0 and worth reimplementing cleanly; its
*packaging* is rejected.

**Not a fux feature.** fux's defining property is that it **never sits in the
request path and never calls anything at runtime**. A cost engine *must* sit at
the call boundary to meter it. Grafting that into fux would destroy the exact
guarantee that makes fux auditable and `$0`. Different lifecycle → different
tool.

**The design principle that keeps Cage tool-independent:** *target the wire
protocol, never the tool.* Cage speaks the message format
(OpenAI/Anthropic chat-completions) and the receipt schema. Anything that
speaks the protocol works; nothing is named, nothing is required. That is what
"independent of the AI tool" means in practice.

---

## 3. The substrate (two files + an append-only log)

Everything derives from three artifacts Cage owns. They are plain text,
diffable, and stdlib-parseable.

### 3.1 The call record — ground-truth spend

One row per real LLM call, emitted by the **meter** at the provider boundary.
This is the invoice-grade truth; provider `usage` fields are authoritative.

```jsonc
// .cage/ledger/calls.jsonl   (append-only)
{
  "id": "c_01J...", "ts": "2026-06-14T10:22:03Z",
  "session": "claude-code:4f1a", "task": "fix-handover-bug",
  "agent": "claude-code", "route": "code-edit",
  "provider": "anthropic", "model": "claude-opus-4-8",
  "tokens_in": 8600, "tokens_out": 1500,
  "cached_in": 3200,            // provider cache-read tokens (billed at discount)
  "est_cost_usd": 0.0483,
  "latency_ms": 5120, "ok": true, "retries": 0
}
```

### 3.2 The savings receipt — what a tool claims it saved

One row per tool intervention, emitted by **each tool in the stack**. This is
the heart of attribution: every tool that reduced what reached the model
declares its own *raw alternative* vs. *actual*, plus the **method** by which it
knows (so honest measurement is separable from estimate).

```jsonc
// .cage/ledger/receipts.jsonl   (append-only)
{
  "id": "r_01J...", "ts": "2026-06-14T10:22:01Z",
  "call": "c_01J...", "task": "fix-handover-bug",
  "tool": "fux",               // fux | graphify | compressor | cache | router | response-cache
  "unit": "tokens",            // tokens | usd | ms | gco2
  "raw_alternative": 8000,     // what the input WOULD have been without this tool
  "actual": 1600,              // what it was with this tool
  "saved": 6400,
  "method": "estimated",       // measured | modeled | estimated  (see §4.3)
  "confidence": 0.8,
  "meta": { "rule": "handover-prepare", "index_amortized": 1200 }
}
```

A tool that *eliminates a call entirely* (a response-cache hit, a skipped
deterministic answer) emits a receipt with `actual: 0` and the full alternative
cost — Cage's "4′33″" case, the highest-value receipt there is.

### 3.3 The policy file — prices, tools, budgets, quality

Versioned config, the only place numbers like price tables live. Deterministic.

```toml
# .cage/policy.toml
[prices.anthropic."claude-opus-4-8"]   # USD per million tokens
input = 3.00
output = 15.00
cache_read = 0.30                       # 90% off → makes cache-align measurable

[tools]                                 # canonical pipeline order (see §4.2)
order = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]

[budgets]
session_usd = 2.00
daily_usd  = 25.00
on_exceed  = "warn"                     # warn | block

[quality]                               # cost is only honest when paired with outcome
signal = "task_ok"                      # did the task succeed without human redo?

[human]                                 # Tier-1 human baseline (§4.6) — rates only
rate_usd_per_hr = 80                    # blended default; CAGE_HUMAN_RATE overrides
default_minutes = 60                    # fallback when a task has no type/minutes
[human.tasks.feature]                   # per-type lookup + [human.confidence] ladder
minutes = 120
rate_usd_per_hr = 90
```

### 3.4 The task record — `tasks.jsonl` (third append-only file)

A `task` was only a foreign-key string; nothing described the task itself. A third
append-only file carries one row per task (last-write-wins by `id` at derive time),
referenced by the calls/receipts that already carry `task`. It is **auto-collected
from git at task close** (SessionEnd hook / `cage outcome`) by *shelling out* — never
importing git — and is **fail-open**: a non-repo / no-git / detached HEAD omits those
fields and never raises (write-path discipline, like `ledger.append`). PII guard
(carried from "prompt bodies are never a field"): it stores the **short SHA, branch,
numeric diff counts, and top-level changed dirs only** — never the commit *message*,
author name/email, or file contents. It absorbs the existing `outcome` signal and
powers `cage trend` and the diff-informed confidence bump.

---

## 4. The attribution engine (the part that's actually novel)

The question Cage answers is not "what did I spend" (any meter does that). It's
**"what did each tool save me, and what would any other stack have cost?"** —
across the full permutation of {Claude vs. not, graphify vs. not, fux vs. not,
compression vs. not, cache vs. not}.

### 4.1 Two sources of truth, never blurred

- **Measured** — configurations you actually ran. The ledger has real rows.
  Honest, but you'll never run all 2ⁿ combinations.
- **Counterfactual** — configurations you *didn't* run, reconstructed from
  receipts. Each tool already knows its raw alternative (fux knows the whole
  governed file it spared you; graphify knows the file-reads it replaced), so
  Cage can *add back* a tool's savings to model "what if this had been off,"
  and use a tool's modeled estimate to project "what if this had been on."

Every cell in a Cage table is tagged `measured` / `modeled` / `estimated`. You
always know which numbers are invoices and which are projections.

### 4.2 Marginal attribution by fixed pipeline order

Savings interact — compression after fux-trimming saves fewer tokens than
compression on raw context. To avoid double-counting, each receipt reports its
**marginal** saving *given the tools upstream of it in the canonical order*
(`policy.toml → tools.order`). Walk the pipeline once; each tool's receipt is
the delta it produced at its position. Sum of marginals = total saving, exactly,
with no overlap. (When tools contend for the *same* slice of context and you
want order-independent credit, a Shapley mode over the receipts is the
principled-but-combinatorial upgrade — deferred, §9.)

### 4.3 `method`: how a receipt knows its alternative

- **measured** — the same task was run both ways; the delta is observed.
- **modeled** — the tool reconstructs the alternative deterministically from
  what it replaced (fux: byte-count of the governed file; graphify: token-count
  of the files a graph query stood in for). This is fux's existing
  `savings.py` logic, generalized and made *per-call* instead of static.
- **estimated** — a heuristic when neither is available (lowest confidence).

### 4.4 Worked example — one task, the full permutation

A single agent task ("explain why handover does X, then fix it"). Context
decomposes into four slices; three deterministic tools each shrink a different
slice. Output held constant at 1,500 tok. Prices from §3.3.

| Slice                    | without tool | with tool | tool        |
| ------------------------ | -----------: | --------: | ----------- |
| base prompt (sys+user)   |        2,000 |     2,000 | — (always)  |
| code understanding       |       30,000 |     3,000 | graphify    |
| rule / intent lookup     |        8,000 |     1,600 | fux         |
| tool outputs (logs/JSON) |       10,000 |     2,000 | compressor  |

The 2³ permutation of the three tools, input-token total `= 2,000 + g + f + c`,
costed at Opus (`$3` in / `$15` out; output = $0.0225 flat):

| graphify | fux | compress | input tok | cost (USD) | source     |
| :------: | :-: | :------: | --------: | ---------: | ---------- |
|    ✗     |  ✗  |    ✗     |    50,000 |   $0.1725  | measured   |
|    ✓     |  ✗  |    ✗     |    23,000 |   $0.0915  | measured   |
|    ✗     |  ✓  |    ✗     |    43,600 |   $0.1533  | modeled    |
|    ✗     |  ✗  |    ✓     |    42,000 |   $0.1485  | modeled    |
|    ✓     |  ✓  |    ✗     |    16,600 |   $0.0723  | modeled    |
|    ✓     |  ✗  |    ✓     |    15,000 |   $0.0675  | modeled    |
|    ✗     |  ✓  |    ✓     |    35,600 |   $0.1293  | modeled    |
|  **✓**   | **✓** | **✓**  | **8,600** | **$0.0483**| measured   |

Marginal attribution along the canonical order (graphify → fux → compressor),
starting from the all-off baseline of 50,000 input tokens:

| step       | tokens after | marginal saved | $ saved |
| ---------- | -----------: | -------------: | ------: |
| graphify   |       23,000 |         27,000 | $0.0810 |
| fux        |       16,600 |          6,400 | $0.0192 |
| compressor |        8,600 |          8,000 | $0.0240 |
| **total**  |              |     **41,400** | **$0.1242** |

The full stack cut this task's context **83%** (50,000 → 8,600) and its cost
**72%** ($0.1725 → $0.0483). Across a month of calls, the same machinery rolls
up to "graphify saved you $N for $0 of its own cost; fux saved $M; the optional
ML compressor saved $K but added 600 ms median latency" — ROI per tool, not just
a total.

### 4.5 Two more receipt shapes the schema must handle

- **Price-savings, not token-savings (cache-align).** Cache alignment doesn't
  remove tokens; it makes the stable prefix billable at the cache-read price.
  Receipt is in `unit: "usd"`: `raw_alternative` = prefix at full price,
  `actual` = prefix at `cache_read`. This is why fux's INDEX must stay
  byte-stable across sessions — churn it and you forfeit this receipt.
- **Eliminated calls (response-cache / skipped).** `actual: 0`, full
  alternative cost saved, `method: "measured"`. The biggest wins are here.

### 4.6 Tier-1 — the human baseline (agent vs human)

§4.2–4.4 are **Tier-2**: tool-vs-tool *within* the agent path. **Tier-1** is the
orthogonal axis — *what a person would have cost* for the whole task. It is one more
baseline layer in the same ledger, not a parallel subsystem: a human alternative is
a receipt whose `tool` is `"human"`, in `unit: "minutes"` (or `"usd"` for a quote).
Money **derives** at read time — minutes are the ground-truth quantity for human
labor exactly as tokens are for the agent path, so a rate change re-prices the
backlog with no ledger rewrite. The full design is `docs/human-baseline.design.md`.

- **Resolver** (`human.py`) — one precedence chain: explicit usd → per-receipt
  minutes → task-type table → global default, each with a `confidence` rung
  (0.9 / 0.7 / 0.5 / 0.3). Cost is **`estimated`** unless a real timesheet/quote
  (`measured`); never `modeled`. Rates live in `[human]` in `policy.toml`;
  `CAGE_HUMAN_RATE` overrides at derive time with visible provenance.
- **Unit→USD** (`convert.py`) — the single dispatch (`usd`/`tokens`/`minutes`/0),
  so `roi`, `attribution`, `human` all agree. Human never enters the 2ⁿ matrix as a
  tool; it sits **above** the stack as a single anchor (`matrix --human`).
- **Two clocks (`§5b.1`)** — every surface that prints *saved $* also prints *saved
  time*: `time_saved = human_minutes − agent_active_minutes`, where
  `agent_active_minutes` = the task's call-span wall-clock floored by `Σ latency_ms`,
  tagged `estimated`. It can go **negative** (agent thrashed) — the metric must be
  able to embarrass the agent. `cage trend` turns `ts` into a cost+time time-series.

---

## 5. Architecture

```
   Your agents / apps                         Cage  (.cage/, $0, local)
   ┌───────────────┐    protocol-targeted     ┌──────────────────────────────┐
   │ Claude Code   │──► OpenAI-compat proxy ──►│  meter  → calls.jsonl         │
   │ Orff gateway  │──► meter() library ──────►│  receipts ← fux/graphify/...  │
   │ any OAI/Anthropic client │                │                              │
   └───────────────┘                           │  derive ($0):                │
            ▲                                   │   ├─ ledger report           │
   tools emit receipts                          │   ├─ attribution + Δ table   │
   (fux, graphify, compressor, cache, router) ─►│   ├─ counterfactual matrix   │
                                                │   ├─ budget / Cage guard     │
                                                │   └─ dashboard (serve)       │
                                                │  MCP server · hooks · plugin │
                                                └──────────────────────────────┘
```

**Two adapters, both protocol-targeted (this is the tool-independence):**

- **Library** — `with cage.meter(route="code-edit"): resp = client.create(...)`.
  Orff drops this into the `LLMGateway` (record from `ProviderResponse` right
  where `CostGuard` already computes cost) and into `Handover.prepare` for the
  compressor. Tool-agnostic; you call it, it doesn't wrap you.
- **OpenAI-compat proxy** — `cage proxy --port 8788` for clients you can't edit
  (Claude Code). Targets the *protocol*, so it is not "wrap claude" — any
  OpenAI/Anthropic-compatible client is metered, none is named.

---

## 6. Tiers — `$0` core, AI strictly optional

| Tier | Extra            | What it adds                                                      | Needs a model? |
| ---- | ---------------- | ---------------------------------------------------------------- | -------------- |
| 0    | (always, stdlib) | meter, price table, ledger, **attribution + counterfactuals**, cache-align, structural JSON/tool-output compression, regex routing policy, budgets, dashboard | **No** |
| 1    | `[embeddings]`   | semantic **response cache** (local embeddings — fux already ships this optional dep) | local only |
| 2    | `[ml]`           | learned text compressor (local model), off by default            | local only |

Tier 0 is ~80% of the real savings and is pure substrate work. **Do not
reinvent Kompress** — Tier 2 is a pluggable adapter you may never switch on.
"Improved by AI, independent of it" is enforced by this table.

---

## 7. CLI / views

```
cage meter -- <cmd>           # run a command through the proxy, record calls
cage report [--since 7d]      # ledger: spend by agent / route / model / day
cage attrib [--task ID]       # per-tool marginal savings (the §4.2 table)
cage matrix [--task ID] [--human]  # counterfactual permutation table; --human = anchor (§4.4/§4.6)
cage budget                   # current session/day spend vs. policy ceilings
cage roi [--since 30d]        # saved $ vs. each tool's own cost + latency (tool-only)
cage human [--task|--agent|--since] [--html]   # Tier-1 agent-vs-human: $ and hours saved (§4.6)
cage human-record --task ID (--type T | --minutes N | --usd N)  # record a human alternative
cage trend [--by week|month] [--metric cost|time|both]  # savings as a time-series (§4.6)
cage serve                    # dashboard (reuse fux's serve/assets pattern)
cage why <call-id>            # full provenance: call + every receipt against it
cage query "how is X computed" [--list] [--all] [--json] [--kind calc|concept]  # explain
```

Every command is `$0`, deterministic, and emits JSON with `--json` for the
agent-as-user (machine-readable, typed, no hidden state).

`cage query` is the math's self-documentation: a curated registry
([explain_data.py](../cage/explain_data.py), rendered by the engine in
[explain.py](../cage/explain.py)) of `Explanation` entries, each tagged
`kind="calculation"` or `kind="concept"`. **Calculation** entries (the original
12 — `cost`, `human-cost`, `matrix`, …) read their numbers **live** from policy +
constants at render time, so an explanation can't drift from the code (set
`CAGE_HUMAN_RATE` ⇒ the printed rate moves). **Concept** entries (`overview`,
`data-flow`, `metering`, `attribution`, `matrix-concept`, `method-law`,
`receipts`, `human-axis`, `determinism`, `pii-safety`, `numbers-layers`) answer
"how does cage work" instead of "how is X computed" — they interpolate
*structural* facts the same way: live ledger paths from `paths.Footprint`, live
pipeline order from `policy.tool_order(pol)`, live agent surfaces from
`agents.SURFACES`, and a live subcommand count from the CLI parser, plus a
`code_refs` + `plan_ref` anchor back to this document. Matching is deterministic
stdlib token-overlap — **no LLM, no network** — across both kinds at once; on a
miss it suggests the closest topic ids rather than guessing, and `--list --kind
concept` filters to just the how-it-works topics. This is the third *audit
layer* made interrogable: contract (`schema.py` enums) · policy (`policy.toml`
economics) · constants (`constants.py` heuristics).

`report` and `budget` **recompute** each call's cost from `tokens × policy` at
derive time (like `attrib`/`matrix`/`roi`/`human`), falling back to the stored
`est_cost_usd` only when the model is unpriced — so a meter that records tokens
but no cost (e.g. the Claude Code transcript meter, which never sets
`est_cost_usd`) still costs out, while a self-costing provider Cage can't
tokenize (a search API) keeps its reported figure. The ledger is never rewritten;
counts stay ground truth. A call only prices if its `(provider, model)` is in the
price table — the transcript meter stamps `provider="anthropic"`, so that key must
carry the Claude rows.

---

## 8. What else Cage should do

Beyond track-and-attribute, the substrate unlocks:

1. **Cage guard (the namesake).** Budget ceilings per session/day/route from
   `policy.toml`; `warn` or `block` on exceed. Orff already has a `CostGuard` —
   Cage subsumes it behind one ledger so dev and app share one budget brain.
2. **Quality-adjusted cost.** Cost is dishonest alone — you can "save" by
   degrading answers. Pair every call with the `quality.signal` (task succeeded
   without human redo) and report **cost per *successful* task**, not per call.
   This is the metric that stops false economies.
3. **Regression detection.** Alert when cost-per-task drifts up — e.g. a prompt
   edit broke prefix-cache hits, or a route silently fell back to a pricier
   model. Deterministic threshold on the ledger.
4. **Cheapest-path recommender.** Given a route, recommend the tool combination
   that historically minimized quality-adjusted cost — turn the matrix from a
   report into a policy suggestion.
5. **Forecast.** Project monthly spend from the current trajectory; flag when a
   budget will blow before month-end.
6. **Secondary ledgers, same substrate.** `unit` already generalizes — swap
   USD for `ms` (latency) or `gco2` (carbon) and every view works unchanged.
7. **Per-feature cost (Orff).** Roll up by `route`/`query_type` to see which
   Orff intents cost the most — the input to where compression/caching pays off.

---

## 9. Build order

The leverage is in the **spec and the contract**, so lock those first.

1. **Substrate contract** — finalize the receipt + call-record schemas and
   `policy.toml`. Everything derives from these; nail them before any code.
2. **Tier-0 meter + ledger** — record real calls via the library adapter; get
   honest `cage report` working against Orff's gateway first (one integration
   point, real traffic).
3. **Receipt emitters** — teach fux and graphify to emit receipts (fux:
   generalize `savings.py` from static estimate to per-call modeled receipt;
   graphify: emit the file-reads a query replaced). Now attribution has inputs.
4. **Attribution + matrix** — `cage attrib` / `cage matrix` over the receipts
   (§4.2). This is the differentiator; ship it early to prove the thesis.
5. **Adapters** — add the OpenAI-compat proxy for Claude Code; wire the
   SessionEnd hook. Both protocol-targeted.
6. **Plugin** — repoint the `cost-ledger` plugin at Cage (skill = `cage report`
   /dashboard, hook = receipt/ledger writer, MCP = Cage server). Dev surface +
   app middleware share the one ledger contract.
7. **Tier 1/2 + §8 features** — response cache, then guard/quality/regression as
   the ledger matures.

---

## 10. Risks & open questions

- **Attribution honesty.** Marginal-by-fixed-order is defensible and `$0`;
  Shapley is fairer but combinatorial. Default to ordered; offer Shapley as an
  opt-in audit mode. Always tag `measured`/`modeled`/`estimated` so no
  projection masquerades as an invoice.
- **PII / secrets in the ledger.** Calls and receipts can carry prompt
  fragments and, for Orff, holdings data. **Store the ledger in elgar** (the
  private store), redact prompt bodies by default (keep token *counts*, not
  text), and never log secrets. This is a fintech reflex, not optional.
- **Receipt trust.** A tool could over-claim savings. Reconcile the sum of
  receipts against the measured call total; surface the **residual** (unexplained
  saving) rather than silently absorbing it.
- **Proxy in the path.** The proxy is the only in-path component; keep it thin,
  fail-open (never block a call because Cage hiccuped), and optional — the
  library path needs no proxy at all.
- **Name.** `Cage` (control/silence) vs. `Glass` (transparency). Pick before the
  repo is git-init'd; everything else is rename-safe.
```
