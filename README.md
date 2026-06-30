<p align="center">
  <img src="https://raw.githubusercontent.com/arpitarya/cage/main/docs/assets/cage-lockup.png" alt="Cage — Alpha Forge · Value Ledger" width="460">
</p>

# Cage

> **Cost dashboards tell you what your AI stack *spent*. Cage tells you what each tool actually *saved* you — and what a human would have cost instead.**

[![PyPI](https://img.shields.io/pypi/v/cage-flux.svg)](https://pypi.org/project/cage-flux/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#the-0-guarantee)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

You're paying for an agent, a graph tool, a rules engine, maybe Copilot. At the end of the month someone asks *"is any of this worth it?"* — and the honest answer is a shrug and a Slack thread. Cage meters every LLM call, collects a **savings receipt** from each tool in the stack, and turns the raw stream into an **attribution ledger**: what you spent, what each tool saved you, what *every other combination* of tools would have cost, and **how much money *and time* the agent saved versus a person** doing the same task. **`$0`, deterministic, zero dependencies, no model in the maintenance path.**

**Named after *John Cage*.** · Python ≥ 3.11 · stdlib only · MIT · sits beside `fux`, `bach`, `wagner`, `orff`.

<p align="center"><em>▶ Demo GIF coming soon.</em></p>

## The story

> *Another README story. Yeah. Because nobody ever walked out of a meeting humming a feature table, and you will not remember mine. So forget the table. Here's ninety seconds about a conference room, a pile of money, and a bunch of people who have no idea what they're talking about. One of them is you. — Arpit*

You ever notice how *everybody's* saving money now? Everybody. The agent's saving money. The graph tool's saving money. Copilot's saving money. Two tools you built over a weekend — saving money. Add it all up and you should be getting a check in the mail. Funny thing about that. The bill went *up*.

Here's the con. Nobody — and I mean *nobody* — can show you the number. They got slides. They got a roadmap. They got a guy named Kevin who "feels like it's a game-changer." What they don't got is one honest figure that says *this* tool saved *this much* on *this* task, and here's what it would've cost to do the boring old way, by hand. Ask for *that* number and watch the room go quiet and somebody suggest we "circle back."

And the kicker — you built half of it. So when finance points at you and says "is this worth it," you, the expert, the one who's supposed to *know* — you got a screenshot and a feeling. You're not in trouble for spending the money, folks. You're in trouble because you bought the same fog everybody else did.

**Cage is the thing that ruins the fog.** It's the itemized receipt nobody asks for and everybody needs: the graph tool saved 27,000 tokens here, fux saved 6,400, the agent did in four minutes what a person does in two hours — plus every other combo you *could've* run, priced out, each number stamped so you know which ones are real and which ones are some computer's best guess. It doesn't do synergy. It does arithmetic.

## See it

```bash
$ cage matrix --task fix-handover-bug
```

```
Counterfactual matrix · task 'fix-handover-bug' · anthropic/claude-opus-4-8
  base 2,000 tok + output 1,500 tok held constant

graphify  fux  compressor   input tok    cost    source
   ✗       ✗       ✗           50,000   $0.1725   modeled
   ✓       ✗       ✗           23,000   $0.0915   modeled
   ✓       ✓       ✗           16,600   $0.0723   modeled
   ✓       ✓       ✓            8,600   $0.0483   measured   ← the run you actually made

  full stack vs all-off: 72% cheaper ($0.1725 → $0.0483)
```

Per-tool savings any meter can attempt. The part no cost dashboard does is the rest of that table — **what each stack you *didn't* run would have cost** — and the `source` column, so you always know which row is an invoice and which is a reconstruction. Only the configuration you actually ran is `measured`; **no projection ever masquerades as an invoice.** That discipline is the whole product.

## Quickstart

```bash
pip install cage-flux           # the CLI, zero third-party deps
cd your-project
cage setup                      # guided wizard: defaults to all agents, wires skill + hooks + graphify
# non-interactively: cage setup --all   (or --claude / --codex / … for just one)
cage demo                       # seed the worked example
cage matrix                     # the counterfactual permutation table
cage human                      # agent-vs-human: $ and hours saved
cage query "how is human cost calculated"   # explain any number — live formula, $0
```

> **Adopting into a project** — `cage setup` is the single front door: it offers Claude Code / Codex / Copilot / Kiro and **defaults to wiring all of them** (any agent's hook captures the whole stack, so there's no reason to pick just one). Drive it non-interactively with `cage setup --all` — or `cage setup --claude` for a single agent (`--no-skill` / `--no-project` / `--no-graphify` to skip parts). For finer control: `cage setup --project-only` scaffolds `.cage/` + the `bin/graphify` interceptor without the global skill (agent wiring opt-in via `--<agent>`), `cage setup --wire-only --claude` wires just one agent's hooks + MCP, and `cage setup --status` reports what's already wired.

Metering from your own code is the library adapter — it targets the *protocol*, not any named client, and is fail-open (a metering error never breaks your call):

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

## Explain it like I'm five

You and a robot helper did the chores. At the end of the day someone wants to know: did the robot actually help, or did it just look busy?

**Cage is the chart on the fridge.** It writes down how long each chore took with the robot, and how long it *would* have taken if you'd done it yourself — so you can see, in real minutes and real dollars, which helper earned its place and which one just made noise. And it's careful to mark which numbers it actually timed and which ones are its best guess, so nobody gets fooled by a confident-looking total. It does all of this for free, without ever phoning a friend for the answer.

## Why it's different

It's not another cost dashboard. The difference is a set of *properties*, not features:

- **Deterministic.** Every derived view — report, attribution, the counterfactual matrix, ROI, the human axis — is pure parse/arithmetic over an append-only log. Same ledger + same policy ⇒ identical tables, every time. The numbers never drift because nothing guesses.
- **Honest by construction.** Every figure carries a `method`: `measured` (a real invoice), `modeled` (a reconstructed counterfactual), or `estimated` (a human/labor guess). A projection can never read as an invoice — the one property a "trust me, it paid off" slide can't offer.
- **`$0` and zero-dependency.** Stdlib-only Python, `dependencies = []`. Heavy ML is an opt-in, off-by-default tier (`[embeddings]`, `[ml]`), never on the default path. Portable as a tarball, auditable line by line.
- **Agent-native.** Every read command takes `--json`; the ledger is served over MCP. Built so an agent can pull its own cost numbers *and verify them*, not just read a chart.

The "so what" chain: deterministic → so the numbers never hallucinate → so each one carries a defensible `method` → so you can put the savings claim in front of finance, or an auditor. That last clause is the one a dashboard can't say.

## Honest attribution — the part that survives the room

Anyone can sum a bill. Cage's job is to divide credit **without lying about it**, and it does that with three rules:

- **Marginal-by-fixed-order.** Each tool's receipt reports the saving it produced *given the tools upstream of it* in the canonical pipeline. The marginals sum exactly to the total — no overlap, no double-counting, `$0` to compute, and defensible because the order is fixed and visible (not a black-box Shapley pass; that's a deferred opt-in audit mode).
- **The counterfactual matrix.** For a task whose tools each shrank a slice of context, Cage enumerates the 2ⁿ on/off permutations and prices each at the task's model — so "what would graphify-off + fux-on have cost?" is a row, not a hand-wave. Only the configuration actually run is `measured`; every reconstructed cell is `modeled` (or `estimated` if it leans on an estimate).
- **Tier-1 — agent vs human.** Beyond tool-vs-tool, Cage models the whole-task counterfactual: what a *person* would have cost in time and money. A human receipt is just a receipt whose `tool` is `"human"`, priced in minutes → money at a configured rate (`[human]` in `policy.toml`, or `CAGE_HUMAN_RATE`). It is `estimated` unless you supply a real timesheet, and carries a **confidence** so round task-type guesses *read* as low-credibility instead of masquerading as precise. The time metric can go **negative** — if the agent thrashed longer than a human would have, the table says so.

```
Agent vs human · 14 tasks · rate source: policy ($80/hr)

agent     tasks   human $    agent $    saved $   saved hrs   conf   method
claude       9    $1,140.00    $4.12    $1,135.88     13.2     0.51   estimated
codex        3      $260.00    $1.55      $258.45      3.1     0.50   estimated
TOTAL       14    $1,530.00    $6.55    $1,523.45     17.9     0.51
```

The savings are anchored to the commit they produced — Cage snapshots a git-aware task record (SHA, branch, diff size, wall-clock) at task close, so a number can always be traced back to the change that earned it.

## Authorship — who wrote which commit, and how sure are we

A different question than *what did this cost*: **who is accountable for this diff.** `cage origin <sha>` answers it from the same append-only substrate — a fourth record type that records *which agent wrote which files in which commit*, captured by a `PostToolUse` hook with a transcript fallback, never blocking an edit or a commit:

```
$ cage origin HEAD
sha 9f3c1a2 · origin: agent (claude-code) · confidence 0.83 · method hooked
  cage/origin.py        +118  -0
  cage/originrecord.py   +97  -0
```

The same honesty discipline as everywhere else, in a parallel namespace: a row carries a `method` (`hooked` > `transcript` > `heuristic`, never upgraded when fragments merge) and an `origin` (`human` / `agent` / `agent-autonomous`). **`unknown` is never a stored row** — a commit with no cage signal is `unknown` *by absence*, derived at read time, so the ledger stays sparse and pre-Cage history reads honestly without bloating it. `origin=human` is reachable only through an explicit human attestation (`cage origin <sha> --attest human`). Distribution is git-notes (`refs/notes/cage-provenance`, **CI is the sole writer**); `cage verify` is **report-only and always exits 0** — visibility in CI, never a gate. Counts-never-content holds: file paths and line counts only, never a diff body or a commit message.

## Every number is reviewable — and you can ask it

Cage keeps its numbers in **three layers, never mixed**, so any figure is auditable in exactly one place:

| Layer | Holds | Lives in |
| ----- | ----- | -------- |
| **Contract** | the closed enums (`UNITS`, `METHODS`) — the substrate's shape | `schema.py` |
| **Policy** | user-tunable economics: prices, the human rate, default minutes, budgets, pipeline order, confidence | `policy.toml` — *the only place economic numbers live* |
| **Constants** | code heuristics not meant as config but that must be reviewable: the token divisor, the matrix ceiling, the provenance ranks, the confidence fallback | `constants.py` |

And because the math should explain itself, **`cage query`** prints the real formula for any value with its numbers read *live* from policy + constants — never a hard-coded literal, so an explanation can't drift from the code:

```
$ cage query "how is human cost calculated"
human-cost · how a human alternative is priced
  formula:  usd = minutes / 60 × rate     (rate = $80/hr, source: policy)
  chain: explicit usd > per-receipt minutes > task-type table > global default
  confidence: measured 0.9 · estimated 0.7 · type-table 0.5 · default 0.3
  method:   estimated — a labor guess; never 'measured' unless a real timesheet/quote.
  code:     cage/human.py · cage/convert.py · policy.toml [human]
```

Set `CAGE_HUMAN_RATE=200` and that printed rate changes — proof it's the code's actual number, not a slide. It's deterministic and `$0`: a curated explainer registry, no LLM, no network. Try `cage query --list` for every topic, or `--json` for the agent-as-user.

`cage query` also explains *how cage itself works*, not just how a value is computed — `cage query "how does cage work"` walks the data flow, fail-open metering, attribution, method tags, receipts, and the rest, with the same live-fact guarantee (the printed ledger paths, pipeline order, and subcommand count are read from the running code, never typed in). `cage query --list --kind concept` lists just those topics.

## How it works

One append-only log in, every view derived from it for `$0`:

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks,provenance}.jsonl  (append-only)
        (meter, fail-open)                    │
                                              ▼  derive ($0, no model)
   policy.toml (prices/order/budgets/rates) → report · attrib · matrix · roi
                                             · human · trend · budget · why · origin
```

`provenance.jsonl` is a local buffer only — canonical authorship lives in `refs/notes/cage-provenance`, written by CI alone.

You meter at the provider boundary (library adapter, a reverse proxy for clients you can't edit, or by parsing a Claude Code / Codex transcript). Everything downstream is a deterministic projection. The ledger carries token **counts**, never prompt bodies — PII-safe by construction; point `CAGE_LEDGER` at a private store to keep even the counts off-disk.

A tool earns rows in `attrib`/`matrix`/`roi` by filing a **savings receipt**, and there are two ways in, by who owns the tool:

- **In-tool (you own it) — e.g. fux** carries a fail-open `cage_receipt.py` and emits its own `tool="fux"` receipt. Cage stays optional; fux runs unchanged with cage absent.
- **External adapter (third-party) — e.g. graphify:** `cage graphify -- graphify query "…"` runs graphify unmodified, passes its output through byte-for-byte, and files a `tool="graphify"` receipt by parsing the cited `source_file`s. graphify is never edited; a metering error never alters its result.

<details>
<summary><strong>The full command surface</strong> (ledger · attribution · human axis · ops · agents)</summary>

```bash
cage init                      # scaffold .cage/ (policy + gitignored ledger)
cage setup [--claude]          # guided onboarding: skill + init + wiring + graphify for one agent
cage setup --project-only --claude   # scaffold + graphify + PATH only (no global skill)
cage setup --wire-only --claude      # wire just one agent's metering hooks + MCP
cage setup --status            # report which agents are wired (changes nothing)
cage doctor --json             # verify this project's setup is correct (non-zero on failure)
cage report --by model         # ledger rollup: spend by route / model / day / agent
cage attrib --task ID          # per-tool marginal savings (sum of marginals = total)
cage matrix --task ID          # the counterfactual permutation table (2ⁿ on/off)
cage matrix --task ID --human  # …with a human anchor row + vs-human columns
cage roi --since 30d           # saved $ per tool vs its own cost + added latency
cage human [--agent claude]    # agent-vs-human: $ AND hours saved, per agent
cage human-record --task ID --type feature   # record a Tier-1 human alternative
cage trend --by week --metric both           # cost + time savings as a time-series
cage why <call-id>             # full provenance: a call + every receipt against it
cage origin <sha> [--attest human]   # who wrote which files in a commit (authorship)
cage notes-sync [--write]      # distribute authorship → refs/notes/cage-provenance (CI writes)
cage verify                    # report-only consistency pass over the ledger (always exits 0)
cage quality / cage outcome ID # cost per *successful* task (cost is honest with outcome)
cage regression                # alert when cost-per-call drifts up
cage recommend                 # cheapest-path: which tools to enable / skip
cage forecast                  # project monthly spend vs the budget
cage graphify -- graphify …    # meter a third-party graphify call (transparent passthrough)
cage setup                     # install /cage + /cage-doctor into every agent home
cage proxy --port 8788         # the universal meter for clients you can't edit
cage mcp                       # serve the ledger to agents over MCP (stdio)
cage serve                     # local dashboard over the ledger
cage query "how is X computed"  # explain any number deterministically, with live values
cage query "how does cage work" # …or the mechanism itself: data flow, attribution, method tags…
cage demo                      # seed the worked example that proves the thesis
```
Every read command takes `--json` for the agent-as-user (machine-readable, typed).
</details>

## Works with any agent — explicit capture over one global ledger

Cage meters whatever speaks the wire format, so all four agents share **one** ledger contract. Capture is **pull-based and universal**: `cage import` reads each agent's on-disk usage log into the ledger, and `cage export` refreshes then emits it — they need no hooks, no project, and work the same whether you run a CLI or a VS Code extension.

```bash
cage import                 # capture every agent's spend into the active ledger
cage export --format csv    # refresh, then emit (jsonl | csv | json)
cage report                 # where the spend went
cage watch                  # optional: a foreground loop you Ctrl-C (no daemon)
```

The ledger resolves **`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`** — so a user with no project captures into the global ledger (`cage setup --global` to seed it). cage installs **no background job** (no launchd/systemd/cron); automate it, if you like, with your own cron line calling `cage import`.

| Agent | Capture (universal) | Optional real-time | Read |
| ----- | ------------------- | ------------------ | ---- |
| **Claude Code** | `cage import` (transcript) | Stop hook (CLI only) | `cage` MCP |
| **Codex** | `cage import` (rollouts) | Stop hook (CLI only) | `cage` MCP |
| **Copilot** | `cage import` (session log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Kiro** | `cage import` (token log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Your code / Orff** | `cage.meter()` library | — | `cage` CLI / MCP |

Hooks are an **optional** real-time add-on — they fire only under a CLI client, never under a VS Code extension — so `cage import`/`cage export` is the path that always works. `cage report --project <name>` slices the global ledger by working dir (exact for Claude; Copilot/Kiro/Codex logs carry no project, so they're excluded from that filter).

**An agent's spend isn't showing up?** `cage doctor` shows the active ledger, each agent's real capture state, and "last import: N ago"; the metadata-only debug log says per agent whether a hook fired or raised — see [Debugging capture](docs/debugging-capture.md).

## The `$0` guarantee

Every derived view is parse / arithmetic over the log — **no LLM call, ever, on the read or maintenance path.** The only model spend is whatever your agent already does; Cage just meters it. The semantic cache and learned compressor ship behind opt-in `[embeddings]` / `[ml]` extras; the default install is model-free and dependency-free. 299 tests passing; `cage demo` reproduces the worked attribution example against a real ledger.

**Honest limits.** Cage doesn't decide your human rate — it prices minutes at a blended rate you set, and labels the result `estimated` so it never pretends to be a timesheet. Marginal-by-fixed-order is defensible and `$0`, but it is an *ordering convention*, not a Shapley value (that's a deferred audit mode). And a counterfactual cell is an honest reconstruction, never an invoice — the `method` column says so on every row, on purpose.

## What's new

Latest releases below — full notes in [CHANGELOG.md](CHANGELOG.md).

- **Unreleased — typed CLI errors + a documented exit-code contract.** An expected failure (a malformed `policy.toml`) or any unexpected exception now renders a clean `error: <msg>` line instead of a raw traceback; the full traceback shows only under `CAGE_DEBUG=1`. Exit codes: `0` ok · `1` error · `2` usage (argparse) · `130` interrupted. Additive and boundary-only — the constitutional fail-open write paths are verified (and tested), never rewritten.
- **v0.13.0 — skill assets are rendered, not hand-edited.** The flagship `cage` skill is single-sourced: `tools/skillgen` (build-time, stdlib-only, never shipped) renders the Claude/Codex SKILL.md, the Copilot prompt, the Kiro steering doc, and a new generic `agents` target from one fragment set, drift-guarded by `python -m tools.skillgen --check` in CI. **Contributors:** edit `tools/skillgen/fragments/`, then `python -m tools.skillgen && python -m tools.skillgen --bless` — never hand-edit `cage/data/skills/cage/`, `cage/data/prompts/cage.prompt.md`, or `cage/data/steering/cage.md`. See [docs/skillgen.md](docs/skillgen.md).
- **v0.12.1 — green CI.** Bug-fix only: three ledger-scale tests passed locally but failed on the CI matrix (3.11–3.13) because they leaned on a global git identity and on `pathlib.Path.stat` internals. The tests now pin identity on the repo and target a discrete `ledger._shard_bytes` helper — no shipped behavior change.
- **v0.12.0 — universal capture: global ledger + explicit `import`/`export`.** Capture is now pull-based and works for any agent, any client, and the no-project user: `cage import` captures into a resolved ledger (`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`), `cage export` emits jsonl/csv/json, `cage watch` is an optional foreground loop. A new additive `project` field gives `cage report --project` (Claude-exact); incremental file-stat cursors keep import cheap; `cage doctor` is honest about hooks (CLI-only) and shows "last import: N ago". cage installs **no** OS scheduler.
- **v0.11.0 — observable capture (`CAGE_DEBUG`).** The fail-open capture path now records a metadata-only per-hook heartbeat + previously-swallowed tracebacks to `.cage/state/debug.log`; `cage doctor` shows per-agent last-fired, `cage debug` tails events. Off by default, $0, counts-never-content, ledger byte-identical on/off. See [Debugging capture](docs/debugging-capture.md).
- **v0.10.2 — Kiro hook format fixed (it never fired before).** Kiro hooks are one-hook-per-file (`when`/`then`); Cage now writes a single `agentStop` hook in the correct shape (the old container shape + a nonexistent `SessionStart` trigger meant it silently never ran).
- **v0.10.1 — release process codified.** GitHub release is the publish trigger (OIDC trusted publishing); never publish from a laptop. CI is the sole publisher.
- **v0.10.0 — real-time per-turn capture + four log-bearing agents.** Stop-hook capture for Claude/Codex (spend lands as each turn ends); Copilot and Kiro now metered too; resolved-absolute `cage` path fixes silent GUI-launch failures; refreshed pricing; repo-level `/cage` skill.
- **v0.9.0 — ledger scale.** Month-partitioned shards, optional `scope` slicing, `--team` aggregation over `refs/notes/cage-ledger`, and SessionStart-backfill as the default reliable hookless path.
- **v0.8.0 — one hookless front door.** `cage import [--agent …]` unifies hookless metering across all four agents; `cage doctor` renders a four-agent metering matrix.
- **v0.7.x — one setup front door + the four-agents invariant.** `cage setup` absorbs `adopt`/`hooks`; Cage keeps Claude Code · Codex · Copilot · Kiro first-class on every surface.
- **v0.6.0 — authorship attribution.** `cage origin <sha>` answers *who wrote which files in which commit*, distributed over `refs/notes/cage-provenance` (CI sole writer); `cage verify` never gates the build.
- **v0.5.0 — DX + concept explainers.** `cage query` concept topics: ask *how cage works*, not just *how a number is computed*.
- **v0.3.0 — the Tier-1 human axis.** `cage human` / `cage trend` price agent-vs-human in dollars and hours.
- **v0.2.0 — attribution + the counterfactual matrix.** Marginal-by-fixed-order attribution, the 2ⁿ permutation table, ROI per tool, and the `measured`/`modeled`/`estimated` discipline.
- **v0.1.0 — substrate + meter.** The call/receipt contract, the append-only ledger, `policy.toml`, and `cage report`.

## The name

Named after *John Cage*, whose *4′33″* framed four and a half minutes of "silence" so an audience would finally *hear* the ambient cost they'd been ignoring. Cage the tool does the same to your AI stack: it takes the spend and the savings everyone assumed were free or unknowable, and makes them something you can actually account for. It's part of a family of deterministic *substrate → derived views* tools — [fux](https://github.com/arpitarya/fux) (decisions → rules) — and now Cage (LLM traffic + receipts → ledger). The names are deliberate, and they sit beside `bach`, `wagner`, and `orff`.

---

If you've ever been the one in the room with no numbers, run `cage demo` — `pip install cage-flux`.

## License

MIT — see [LICENSE](LICENSE).
