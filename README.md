# Cage

> **Cost dashboards tell you what your AI stack *spent*. Cage tells you what each tool in it actually *saved* you — **gross and net of the cost of using it** — with a `method` tag on every number.**

[![PyPI](https://img.shields.io/pypi/v/cage-flux.svg)](https://pypi.org/project/cage-flux/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#the-0-guarantee)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

You're paying for an agent, a graph tool, a rules engine, maybe Copilot. At the end of the month someone asks *"is any of this worth it?"* — and the honest answer is a shrug and a Slack thread. Cage meters every LLM call, collects a **savings receipt** from each tool in the stack, and turns the raw stream into an **attribution ledger**: what you spent, what each tool saved you — **gross and net of what using it cost you** — what *every other combination* of tools would have cost, and which tools your agents actually *adopt* when offered. **`$0`, deterministic, zero dependencies, no model in the maintenance path.**

**Named after *John Cage*.** · Python ≥ 3.11 · stdlib only · MIT · sits beside `fux`, `bach`, `wagner`, `orff`.

**Platforms:** macOS is field-validated (real extension sessions, the full manual capture matrix); Linux and Windows are CI-tested across the whole suite + scenario runner. **One honest gap:** the graphify PATH interceptor is a bash shim, so on Windows the shim route doesn't exist yet — graphify savings there arrive via the transcript route only (a Windows-native twin is planned). On Windows, run `cage doctor --paths` first — it shows every log location cage probes on your machine and why any missed. Locked-down endpoint (AppLocker/WDAC blocks the exe, or no pip)? `cage setup --python-launcher` wires everything through the interpreter instead, and every release ships a single-file `cage.pyz`.

<p align="center"><em>▶ Demo GIF coming soon.</em></p>

## The story

> *Another README story. Yeah. Because nobody ever walked out of a meeting humming a feature table, and you will not remember mine. So forget the table. Here's ninety seconds about a conference room, a pile of money, and a bunch of people who have no idea what they're talking about. One of them is you. — Arpit*

You ever notice how *everybody's* saving money now? Everybody. The agent's saving money. The graph tool's saving money. Copilot's saving money. Two tools you built over a weekend — saving money. Add it all up and you should be getting a check in the mail. Funny thing about that. The bill went *up*.

Here's the con. Nobody — and I mean *nobody* — can show you the number. They got slides. They got a roadmap. They got a guy named Kevin who "feels like it's a game-changer." What they don't got is one honest figure that says *this* tool saved *this much* on *this* task, and here's what it would've cost to do the boring old way, by hand. Ask for *that* number and watch the room go quiet and somebody suggest we "circle back."

And the kicker — you built half of it. So when finance points at you and says "is this worth it," you, the expert, the one who's supposed to *know* — you got a screenshot and a feeling. You're not in trouble for spending the money, folks. You're in trouble because you bought the same fog everybody else did.

**Cage is the thing that ruins the fog.** It's the itemized receipt nobody asks for and everybody needs: the graph tool saved 27,000 tokens here, fux saved 6,400 there — **and what invoking them cost you, netted against it** — plus every other combo you *could've* run, priced out, each number stamped so you know which ones are real and which ones are some computer's best guess. It doesn't do synergy. It does arithmetic.

And when cage's own numbers came back saying a session *with* the graph tool cost **more** than one without? It printed that too, labelled, instead of burying it. A savings tool you can't catch lying about savings is just the fog with a logo. ([The finding.](docs/regression/2026-08-01-finding-saved-is-gross.md))

## See it

```bash
$ cage insights matrix --task fix-handover-bug
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

*(The table above is the seeded `cage demo` example. Where does cage's own evidence stand? Lab-validated capture across Claude Code, Copilot and Kiro on macOS — and the measured verdict on whether a graph tool nets positive is honestly **still open**: the first paired A/B run found the ON arm costing more, gross savings notwithstanding, at n=1. `cage insights verdict` refuses to call that a saving. Most tools in this space would not show you that sentence.)*

## Quickstart

```bash
pip install cage-flux           # the CLI, zero third-party deps
cd your-project
cage setup                      # guided wizard: defaults to all agents, wires skill + hooks + graphify
# non-interactively: cage setup --all   (or --claude / … for just one)
cage demo                       # seed the worked example
cage insights matrix                     # the counterfactual permutation table
cage task quality                    # cost per *successful* task
cage query "how is attribution calculated"  # explain any number — live formula, $0
```

> **Adopting into a project** — `cage setup` is the single front door: it offers Claude Code / Copilot / Kiro and **defaults to wiring all of them** (any agent's hook captures the whole stack, so there's no reason to pick just one). Drive it non-interactively with `cage setup --all` — or `cage setup --claude` for a single agent (`--no-skill` / `--no-project` / `--no-graphify` to skip parts). For finer control: `cage setup --project-only` scaffolds `.cage/` + the `bin/graphify` interceptor without the global skill (agent wiring opt-in via `--<agent>`), `cage setup --wire-only --claude` wires just one agent's hooks + MCP, and `cage setup --status` reports what's already wired.
>
> **What gets committed vs what stays local.** The project-wired files (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`, `.kiro/hooks/`) are committed with the repo and contain **no absolute paths** — they reference the committed shim `.cage/bin/cage-run` (identical bytes on every machine), which resolves cage at runtime and **exits 0 silently when cage isn't installed** (a teammate's clone gets working agents, no noise, no capture). Commit `.cage/` as-is: its own `.gitignore` already excludes the machine-local parts (`ledger/`, `out/`, `state/`). Per-machine configs stay absolute and are never cloned: `~/.copilot/hooks/`, `.git/hooks/` — plus the one committed exception, `.kiro/settings/mcp.json` (Kiro can't launch MCP servers portably; add it to your `.gitignore` — `cage doctor` reminds you). Re-running `cage setup` migrates any pre-0.20 absolute entries and prints what moved; `cage doctor` has a portability check.

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

**Cage is the chart on the fridge.** It writes down what each robot chore cost, what the robot's little gadgets saved — *and what switching the gadgets on cost you, taken off the total* — so you can see, in real tokens and real dollars, which helper earned its place and which one just made noise. And it's careful to mark which numbers it actually counted and which ones are its best guess, so nobody gets fooled by a confident-looking total. It does all of this for free, without ever phoning a friend for the answer.

## Why it's different

It's not another cost dashboard. The difference is a set of *properties*, not features:

- **Deterministic.** Every derived view — report, attribution, the counterfactual matrix, ROI — is pure parse/arithmetic over an append-only log. Same ledger + same policy ⇒ identical tables, every time. The numbers never drift because nothing guesses.
- **Honest by construction.** Every figure carries a `method`: `measured` (a real invoice), `modeled` (a reconstructed counterfactual), or `estimated` (a guess, labelled as one). A projection can never read as an invoice — the one property a "trust me, it paid off" slide can't offer.
- **`$0` and zero-dependency.** Stdlib-only Python, `dependencies = []`. Heavy ML is an opt-in, off-by-default tier (`[embeddings]`, `[ml]`), never on the default path. Portable as a tarball, auditable line by line.
- **Agent-native.** Every read command takes `--json`; the ledger is served over MCP. Built so an agent can pull its own cost numbers *and verify them*, not just read a chart.

The "so what" chain: deterministic → so the numbers never hallucinate → so each one carries a defensible `method` → so you can put the savings claim in front of finance, or an auditor. That last clause is the one a dashboard can't say.

## Honest attribution — the part that survives the room

Anyone can sum a bill. Cage's job is to divide credit **without lying about it**, and it does that with three rules (full design: [docs/PLAN.md](docs/PLAN.md) §4):

- **Marginal-by-fixed-order.** Each tool's receipt reports the saving it produced *given the tools upstream of it*; the marginals sum exactly to the total — no overlap, no double-counting, `$0` to compute, the order fixed and visible (not a black-box Shapley pass).
- **The counterfactual matrix.** Cage enumerates the 2ⁿ tool on/off permutations and prices each at the task's model. Only the configuration actually run is `measured`; every reconstructed cell is `modeled` (or `estimated`).
- **Quality-adjusted.** Cost alone is dishonest — you can "save" by degrading answers and paying for the redo. `cage task outcome <task>` closes a task with its outcome, and `cage task quality` reports cost per ***successful*** task, the metric that stops false economies.

```
Counterfactual matrix · task t_9f31 · base model anthropic/claude-sonnet-4-6

compress  graphify  fux    input tok      cost   source
   ✗         ✗       ✗        24,900   $0.0972   modeled
   ✓         ✗       ✗        18,200   $0.0771   modeled
   ✓         ✓       ✗        11,400   $0.0567   modeled
   ✓         ✓       ✓         8,600   $0.0483   measured

full stack vs all-off: ✓ cheaper ($0.0972 → $0.0483)
```

The savings are anchored to the commit they produced — Cage snapshots a git-aware task record (SHA, branch, diff size, wall-clock) at task close, so a number can always be traced back to the change that earned it.

## Authorship — who wrote which commit, and how sure are we

A different question than *what did this cost*: **who is accountable for this diff.** `cage authorship origin <sha>` answers it from the same append-only substrate — which agent wrote which files in which commit, with the same honesty discipline (`hooked` > `transcript` > `heuristic` method ranks; `unknown` derived from absence, never stored; `origin=human` only by explicit attestation; CI the sole git-notes writer; counts-never-content — paths and line counts, never a diff body or commit message). Full design: [docs/PLAN.md](docs/PLAN.md) §3.5.

## Every number is reviewable — and you can ask it

Cage keeps its numbers in **three layers, never mixed**, so any figure is auditable in exactly one place:

| Layer | Holds | Lives in |
| ----- | ----- | -------- |
| **Contract** | the closed enums (`UNITS`, `METHODS`) — the substrate's shape | `schema.py` |
| **Policy** | user-tunable economics: prices, budgets, pipeline order, routing | `cage.toml` — *the only place economic numbers live* (previously `policy.toml`; still read as a fallback) |
| **Constants** | code heuristics not meant as config but that must be reviewable: the token divisor, the matrix ceiling, the provenance ranks, the confidence fallback | `constants.py` |

And because the math should explain itself, **`cage query`** prints the real formula for any value with its numbers read *live* from policy + constants — never a hard-coded literal, so an explanation can't drift from the code:

```
$ cage query "how is attribution calculated"
marginal-attribution · how per-tool savings sum to the total with no double-count
  formula:  walk tools in policy order (graphify → fux → router → compressor → cache
  → response-cache); each receipt is its marginal saving given the tools upstream of
  it, so Σ(marginals) = total, no overlap.
  method:   per-row method = the least-trusted receipt for that tool (honest worst-case).
  code:     cage/attribution.py · cage/matrix.py · cage.toml [tools.order]
```

Reorder `[tools] order` in `cage.toml` and that printed pipeline changes — proof it's the code's actual value, not a slide. It's deterministic and `$0`: a curated explainer registry, no LLM, no network. `cage query` also explains *how cage itself works* (`cage query "how does cage work"` walks the data flow, attribution, method tags — same live-fact guarantee); `cage query --list` for every topic, `--json` for the agent-as-user.

### Pricing is managed, and $0 is never silent

A call whose model has no price row bills **$0 and says so** — `report`, `compare`, and `study report` all print `⚠ N calls (X tokens) UNPRICED — totals understated` rather than letting an analyst publish an understated number; the fix is one pasted `cage prices set`/`alias` line. Family matching absorbs route prefixes, dotted ids, and effort tiers; prices are derive-time, so fixing the table re-prices every historical row (including imported fleet bundles) retroactively — the ledger stores counts, never conclusions, and cage never fetches a price. The full design — how a call prices · the unpriced workflow · policy versioning and `cage prices sync` · fleet repricing · the Copilot approximation · credits vs prices — is walked live by `cage query prices-cli`.

## How it works

![Cage architecture — sources → capture → append-only ledger → deterministic derive → read/export surfaces](docs/assets/architecture.svg)

The same flow as a maintained diagram: [docs/architecture-flow.mermaid](docs/architecture-flow.mermaid) (renders on GitHub).

One append-only log in, every view derived from it for `$0`:

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks,provenance}.jsonl  (append-only)
        (meter, fail-open)                    │
                                              ▼  derive ($0, no model)
   cage.toml (prices/order/budgets/rates) → report · attrib · matrix · roi
                                             · budget · why · origin
```

You meter at the provider boundary (library adapter, a reverse proxy for clients you can't edit, or by parsing a Claude Code transcript). Everything downstream is a deterministic projection. The ledger carries token **counts**, never prompt bodies — PII-safe by construction; point `CAGE_LEDGER` at a private store to keep even the counts off-disk.

A tool earns rows in `attrib`/`matrix`/`roi` by filing a **savings receipt**, and there are two ways in, by who owns the tool:

- **In-tool (you own it) — e.g. fux** carries a fail-open `cage_receipt.py` and emits its own `tool="fux"` receipt. Cage stays optional; fux runs unchanged with cage absent.
- **External adapter (third-party) — e.g. graphify:** `cage data graphify -- graphify query "…"` runs graphify unmodified, passes its output through byte-for-byte, and files a `tool="graphify"` receipt by parsing the cited `source_file`s. graphify is never edited; a metering error never alters its result.

The full command surface (30+ subcommands: ledger · attribution · task outcomes · fleet study · ops · agents) is grouped in `cage --help`, which points at `cage query` for any "how is this computed". Every read command takes `--json` for the agent-as-user. The doc map — design of record, subsystem docs, operations, archive — starts at [docs/README.md](docs/README.md).

## Works with any agent — explicit capture over one global ledger

Cage meters whatever speaks the wire format, so all three agents share **one** ledger contract. Capture is **pull-based and universal**: `cage import` reads each agent's on-disk usage log into the ledger, and `cage data export` refreshes then emits it — they need no hooks, no project, and work the same whether you run a CLI or a VS Code extension.

```bash
cage import                 # capture every agent's spend into the active ledger
cage data export --format csv    # refresh, then emit (jsonl | csv | json)
cage report                 # where the spend went
cage data watch                  # optional: a foreground loop you Ctrl-C (no daemon)
```

The ledger resolves **`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`** — so a user with no project captures into the global ledger (`cage setup --global` to seed it). cage installs **no background job** (no launchd/systemd/cron); automate it, if you like, with your own cron line calling `cage import`.

Nonstandard install, a network home, or a custom tool that writes a supported format? Add import paths in `cage.toml` — `[sources.<agent>] paths = ["~/alt/logs"]` (or a custom `[sources.<name>] format = "claude"`), and declare `surface = "cli"` when a non-IDE store would otherwise be mislabelled; `cage doctor --paths` shows every location with its provenance and surface, and `cage query sources` explains the schema.

| Agent | Capture (universal) | Optional real-time | Read |
| ----- | ------------------- | ------------------ | ---- |
| **Claude Code** | `cage import` (transcript) | Stop hook (CLI only) | `cage` MCP |
| **Copilot** | `cage import` (session log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Kiro** | `cage import` (token log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Your code / Orff** | `cage.meter()` library | — | `cage` CLI / MCP |

Hooks are an **optional** real-time add-on — they fire only under a CLI client, never under a VS Code extension — so `cage import`/`cage data export` is the path that always works. `cage report --project <name>` slices the global ledger by working dir (exact for Claude; Copilot/Kiro logs carry no project, so they're excluded from that filter). Committed wired files never embed a machine's absolute cage path — they reference the repo-local shim `.cage/bin/cage-run` (see the Quickstart note).

**An agent's spend isn't showing up?** `cage doctor` shows the active ledger, each agent's real capture state, and "last import: N ago"; the metadata-only debug log says per agent whether a hook fired or raised (`CAGE_DEBUG=1`).

## Reporting — CSV out of every read view

Every read view also renders as CSV for spreadsheets/BI: `--csv` streams to stdout (pipe-friendly), `--csv <path>` writes a file. The same data structure feeds the text table and the CSV, so the numbers can't disagree — and the honesty ships with them: **method tags are columns** (`measured` vs `estimated` survives into the sheet), refusals and the UNPRICED counts stay visible, line endings are LF on every OS (byte-identical, deterministic).

```bash
cage report --csv --since 7d > weekly-spend.csv   # last week's spend, flat
cage insights attrib --csv                                  # per-tool savings, method column kept
cage data export --csv calls --since 30d -o calls.csv   # raw ledger rows for a pivot table
```

`--csv` works on `report` · `attrib` · `roi` · `compare` · `study report` · `calibration`; raw rows come from `cage data export --csv calls|receipts|tasks`. CSV is one-way reporting — never an import source; the re-importable fleet bundle stays jsonl (`cage data export --study`). The `cage` skill on all four agents knows the recipes — ask your agent for "my weekly cost report as CSV".

## The `$0` guarantee

Every derived view is parse / arithmetic over the log — **no LLM call, ever, on the read or maintenance path.** The only model spend is whatever your agent already does; Cage just meters it. The semantic cache and learned compressor ship behind opt-in `[embeddings]` / `[ml]` extras; the default install is model-free and dependency-free. 962 tests; `cage demo` reproduces the worked attribution example against a real ledger.

**Honest limits.** Marginal-by-fixed-order is defensible and `$0`, but it is an *ordering convention*, not a Shapley value (that's a deferred audit mode). And a counterfactual cell is an honest reconstruction, never an invoice — the `method` column says so on every row, on purpose.

## What's new

Latest release below — full history and detail in [CHANGELOG.md](CHANGELOG.md).

- **v0.37.2 (2026-08-01) — the README tells the truth.** Docs and repo hygiene only; `cage/` is unchanged from v0.37.1 apart from the version string. The pitch had been selling the Tier-1 human axis ("money *and time* versus a person", chores "in real minutes") — amputated wholesale back in v0.36.0 — so it now describes what cage actually does: per-tool savings gross **and net of what invoking the tool cost you**, counterfactual stacks, tool adoption, plus an honest note that cage's own net-positive verdict is still open at n=1 and the Windows graphify shim gap (**WIN-GF**). The graphify knowledge graph is also now committed (`graphify-out/`) so agents and CI can read it without regenerating. See [CHANGELOG.md](CHANGELOG.md) for the full accounting.

## The name

Named after *John Cage*, whose *4′33″* framed four and a half minutes of "silence" so an audience would finally *hear* the ambient cost they'd been ignoring. Cage the tool does the same to your AI stack: it takes the spend and the savings everyone assumed were free or unknowable, and makes them something you can actually account for. It's part of a family of deterministic *substrate → derived views* tools — [fux](https://github.com/arpitarya/fux) (decisions → rules) — and now Cage (LLM traffic + receipts → ledger). The names are deliberate, and they sit beside `bach`, `wagner`, and `orff`.

---

If you've ever been the one in the room with no numbers, run `cage demo` — `pip install cage-flux`.

## License

MIT — see [LICENSE](LICENSE).
