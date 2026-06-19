# Cage — a *flux*

> **Cage** is a *flux*: a deterministic engine for the **flow of tokens and calls**
> through an AI tool stack. It meters every LLM call, collects a **savings receipt**
> from each tool in the stack, and turns the raw stream into an **attribution
> ledger** — what you spent, what each tool saved you, what any *other* combination
> of tools would have cost, and **how much money *and time* the agent saved vs a
> person** doing the task (anchored to the commit it produced). `$0`, stdlib-only,
> deterministic, and independent of any single AI tool.

Cage is the third in a family of deterministic *substrate → derived views* tools:
[graphify](https://github.com/arpitarya/graphify) (code → graph),
[fux](https://github.com/arpitarya/fux) (decisions → rules/memory), and now Cage
(**LLM traffic + savings receipts → ledger, attribution, counterfactuals**).

The full design of record is in [docs/cage-plan.md](docs/cage-plan.md).

---

## Status — v0.3 (Tier-1 human axis + tool-savings receipts)

| Build-order step (plan §9) | Status |
| -------------------------- | ------ |
| 1. Substrate contract (call record, receipt, `policy.toml`) | ✅ |
| 2. Tier-0 meter + ledger (`record_call`, `cage report`) | ✅ |
| 3. Receipt emitters (`record_receipt`, compressor, response-cache) | ✅ |
| 4. Attribution + matrix (`cage attrib`, `cage matrix`) | ✅ |
| 5. Adapters — library `meter()` · proxy · transcript hooks · `cage meter` | ✅ |
| 6. Plugin — `cage mcp` · `/cage` skill · agent hooks/wiring | ✅ |
| 7. Tier-0 savings (compressor, exact-match cache) + §8 features | ✅ |

The attribution engine (§4, the differentiator) reproduces the plan's worked
example against a real ledger — `cage demo`. 78 tests passing. The optional
`[embeddings]`/`[ml]` tiers stay off by default (semantic cache + learned
compressor are pluggable adapters over the same receipt shape).

**Tier-1 — agent vs human.** Beyond tool-vs-tool savings, Cage models the
whole-task counterfactual: what a *person* would have cost in time and money. A
human receipt is just a receipt whose `tool` is `"human"`, priced in minutes →
money at a configured rate (`[human]` in `policy.toml`, or `CAGE_HUMAN_RATE`).
Every figure is `estimated` (never `measured` unless you supply a real timesheet)
and carries a confidence so round task-type guesses *read* as low-credibility:

```
Agent vs human · 14 tasks · rate source: policy ($80/hr)
agent     tasks   human $    agent $    saved $   saved hrs   conf   method
claude       9    $1,140.00    $4.12    $1,135.88     13.2     0.51   estimated
```

---

## Quickstart

```bash
./install.sh                 # editable install → the `cage` binary ($0, stdlib only)
cd your-project && cage init # scaffold .cage/ (policy + gitignored ledger)

cage demo                    # seed the plan's §4.4 worked example
cage attrib                  # per-tool marginal savings (the §4.2 table)
cage matrix                  # the counterfactual permutation table (§4.4)
cage report --by model       # ledger rollup: spend by model
```

### Metering from your code (the library adapter)

The adapter targets the *protocol*, not any named tool — you call it, it doesn't
wrap you, and it is fail-open (a metering error never breaks your call):

```python
import cage

with cage.meter("code-edit", task="fix-bug") as m:
    resp = client.messages.create(...)            # any Anthropic/OpenAI client
    m.usage(provider="anthropic", model="claude-opus-4-8",
            tokens_in=8600, tokens_out=1500, cached_in=3200)

# A tool that shrank the context files a receipt for what it spared you:
cage.record_receipt(tool="fux", raw_alternative=8000, actual=1600,
                    call=m.call_id, task="fix-bug", method="modeled")
```

## What `cage demo` proves

The §4.4 worked example — one task, three deterministic tools each shrinking a
different slice of context — reproduced against a real ledger:

```
Marginal attribution · task 'fix-handover-bug' · anthropic/claude-opus-4-8
tool        saved tok  saved $  method
graphify       27,000  $0.0810  modeled
fux             6,400  $0.0192  modeled
compressor      8,000  $0.0240  measured
TOTAL          41,400  $0.1242

Counterfactual matrix … full stack vs all-off: 72% cheaper ($0.1725 → $0.0483)
```

Every cell is tagged `measured` / `modeled` / `estimated` — you always know which
numbers are invoices and which are projections. Only the configuration you
actually ran is `measured`; no projection masquerades as an invoice (plan §4.1).

## CLI

| Command | What it does |
| ------- | ------------ |
| `cage init` | scaffold `.cage/` (policy + gitignored ledger) |
| `cage report [--by route\|model\|day\|agent] [--since 7d]` | ledger rollup |
| `cage attrib [--task ID]` | per-tool marginal savings (§4.2) |
| `cage matrix [--task ID]` | counterfactual permutation table (§4.4) |
| `cage budget [--session ID]` | session/day spend vs `policy.toml` ceilings |
| `cage roi [--since 30d]` | saved $ per tool vs its own cost + latency |
| `cage human [--since\|--task\|--agent] [--html]` | agent-vs-human: **$ and hours saved** per agent (§4.1) |
| `cage human-record --task ID (--type T\|--minutes N\|--usd N)` | record the Tier-1 human alternative for a task (§5) |
| `cage matrix --human` | the §4.4 matrix with a human anchor row + vs-human columns |
| `cage trend [--by week\|month] [--metric cost\|time\|both]` | cost+time savings as a time-series (§5b.4) |
| `cage why <call-id>` | full provenance: a call + every receipt against it |
| `cage quality` / `cage outcome <task>` | cost per *successful* task (§8.2) |
| `cage regression` | alert when cost-per-call drifts up (§8.3) |
| `cage recommend` | cheapest-path: which tools to enable/skip (§8.4) |
| `cage forecast` | project monthly spend vs the budget (§8.5) |
| `cage graphify -- graphify <query\|path\|explain> …` | meter a third-party graphify call (transparent passthrough; files a savings receipt) |
| `cage serve` | local dashboard over the ledger |
| `cage demo` | seed the §4.4 worked example |

Every read command takes `--json` for the agent-as-user (machine-readable, typed).

## Works with any agent — target the protocol, not the tool

Cage meters whatever speaks the wire format and reads the ledger over MCP, so all
four agents share one ledger contract:

| Agent | Meter its spend | Read the ledger |
| ----- | --------------- | --------------- |
| **Claude Code** | SessionEnd hook parses the transcript (proxy-free) | `/cage` skill + `cage` MCP |
| **Codex** | `cage meter -- codex …` / `cage import-codex` | `cage` MCP (`~/.codex/config.toml`) |
| **Copilot** | `cage proxy` (point its base URL at it) | `cage` MCP (`.vscode/mcp.json`) + instructions |
| **Kiro** | `cage proxy` | `cage` MCP (`.kiro/settings/mcp.json`) + steering |
| **Your code / Orff** | `cage.meter()` library adapter | `cage` CLI / MCP |

```bash
cage setup                 # install a global /cage asset into all four agent homes
cage hooks install         # wire claude/codex/copilot/kiro in this project
cage hooks install --claude   # or one surface at a time
cage proxy --port 8788     # the universal meter for clients you can't edit
cage meter -- codex exec   # run any agent under the proxy for one shot
```

### Tool-savings receipts — owned vs third-party

A tool earns rows in `attrib`/`matrix`/`roi` by filing a *savings receipt*. Two
strategies, by who owns the tool (see [docs/agents.md](docs/agents.md) and the
[receipt contract](docs/tool-receipts.graphify-fux.handoff.md)):

- **In-tool (you own it) — e.g. fux** carries a fail-open `cage_receipt.py` and
  emits its own `tool="fux"` receipt; cage stays optional (fux runs unchanged with
  cage absent).
- **External adapter (third-party) — e.g. graphify:** `cage graphify -- graphify
  query "…"` runs graphify unmodified, passes its output through byte-for-byte, and
  files a `tool="graphify"` receipt by parsing the cited `source_file`s. graphify is
  never edited; a metering error never alters its result.

## Design constitution

- **`$0`, stdlib-only, deterministic** — no model in the maintenance path. Heavy
  ML is an *optional, off-by-default* tier (`[embeddings]`, `[ml]`), never required.
- **Target the wire protocol, never the tool** — Cage speaks the message format
  and the receipt schema. Anything that speaks them works; nothing is named.
- **PII-safe by construction** — the ledger stores token *counts*, never prompt
  bodies. Point `CAGE_LEDGER` at a private store to keep even the counts off-disk.
- **Honest attribution** — marginal-by-fixed-order ($0, defensible); every number
  carries its `method`. Shapley is a deferred opt-in audit mode (plan §9).

MIT licensed.
