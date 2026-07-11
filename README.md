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

**Platforms:** macOS is field-validated (real extension sessions, the full manual capture matrix); Linux and Windows are CI-tested across the whole suite + scenario runner. On Windows, run `cage doctor --paths` first — it shows every log location cage probes on your machine and why any missed ([manual checklist](docs/windows-manual-checklist.md) to help upgrade the wording). Locked-down endpoint (AppLocker/WDAC blocks the exe, or no pip)? `cage setup --python-launcher` wires everything through the interpreter instead, and every release ships a single-file `cage.pyz` — see [Restricted environments](docs/restricted-environments.md).

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
>
> **What gets committed vs what stays local.** The project-wired files (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`, `.codex/hooks.json`, `.kiro/hooks/`) are committed with the repo and contain **no absolute paths** — they reference the committed shim `.cage/bin/cage-run` (identical bytes on every machine), which resolves cage at runtime and **exits 0 silently when cage isn't installed** (a teammate's clone gets working agents, no noise, no capture). Commit `.cage/` as-is: its own `.gitignore` already excludes the machine-local parts (`ledger/`, `out/`, `state/`). Per-machine configs stay absolute and are never cloned: `~/.copilot/hooks/`, `~/.codex/config.toml`, `.git/hooks/` — plus the one committed exception, `.kiro/settings/mcp.json` (Kiro can't launch MCP servers portably; add it to your `.gitignore` — `cage doctor` reminds you). Re-running `cage setup` migrates any pre-0.20 absolute entries and prints what moved; `cage doctor` has a portability check. Design and rationale: [Portable wiring](docs/portable-wiring.md).

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

### Pricing is managed, and $0 is never silent

A call whose model has no price row bills **$0 and says so** — `report`, `compare`, and `study report` all print `⚠ N calls (X tokens) UNPRICED — totals understated` rather than letting an analyst publish an understated number. The fix is a paste, not a hunt (real field example — the VS Code Copilot extension stamps dotted, route-prefixed model ids and an empty-provider router):

```
$ cage prices unpriced
  —/copilot/auto   38 calls   412,000 tokens
    fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly
$ cage prices alias - copilot/auto --to anthropic/claude-sonnet-4-6
  ✔ —/copilot/auto → anthropic/claude-sonnet-4-6 — .cage/policy.toml
    renders as an alias footnote (approximate routing), never exact.
    derived views re-price immediately — the ledger is never rewritten.
$ cage prices set anthropic claude-sonnet-5 --input 2 --output 10 --cache-read 0.20
  ✔ [prices.anthropic."claude-sonnet-5"] updated — derived views re-price immediately
```

Copilot-served Claude ids (`copilot/claude-opus-4.6`) need no fix at all: family matching normalizes the route prefix, `.`↔`-` punctuation, and effort-tier suffixes (`low|medium|high|max` — vendors bill every tier at the same per-token rate), so they price at the Anthropic rows with a footnote — which is also GitHub's own AI-Credits metering basis since June 2026. Only the bare router `copilot/auto` stays loudly unpriced until *you* route it: a router priced silently is a wrong number. Prices are derive-time — fix the table and every historical row (including imported fleet bundles) re-prices retroactively; the ledger stores counts, never conclusions. The bundled table carries `[meta] prices_version` (source URLs cited row by row): when a newer cage ships newer rates, `cage doctor` and `cage prices list` say `bundled prices are newer — run 'cage prices sync'` and never auto-apply. cage itself never fetches a price — no network on any cage code path; the research step is yours (`cage query prices-cli` walks it). And `cage export` now imports everything first, so one command from a hook-less machine still ships a complete bundle (`--no-import` for a frozen snapshot; the manifest records which you did).

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
cage compare [--by label]      # measured: closed tasks by observed stack (n·median·IQR; delta estimated)
cage estimate [--label W] [--record TASK]  # modeled pre-task band from matching history (refuses thin n)
cage calibration               # measured: do recorded estimates land in-band? (the confidence level)
cage verdict graphify          # one line: SAVING / COSTING / INSUFFICIENT DATA (pure composer, tagged inputs)
cage study join baseline       # fleet study: enroll this laptop (opaque id) + wire + start phase
cage export --study            # one bundle per machine → analyst: cage import bundle*.zip
cage study report              # coverage (gaps flagged) first, then the paired-by-machine delta
cage human [--agent claude]    # agent-vs-human: $ AND hours saved, per agent
cage human-record --task ID --type feature   # record a Tier-1 human alternative
cage trend --by week --metric both           # cost + time savings as a time-series
cage why <call-id>             # full provenance: a call + every receipt against it
cage origin <sha> [--attest human]   # who wrote which files in a commit (authorship)
cage notes-sync [--write]      # distribute authorship → refs/notes/cage-provenance (CI writes)
cage verify                    # report-only consistency pass over the ledger (always exits 0)
cage quality / cage outcome ID [--label WORD]  # cost per *successful* task (+ compare grouping tag)
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

Wired files that get **committed** (`.mcp.json`, `.vscode/mcp.json`, `.kiro/hooks/*`) never embed a machine's absolute cage path — they reference a small repo-local launcher, `.cage/bin/cage-run`, that resolves cage at run time on whatever machine it's on and exits silently if cage isn't installed, so teammates' clones just work. Design and rationale: [Portable wiring](docs/portable-wiring.md).

**An agent's spend isn't showing up?** `cage doctor` shows the active ledger, each agent's real capture state, and "last import: N ago"; the metadata-only debug log says per agent whether a hook fired or raised — see [Debugging capture](docs/debugging-capture.md).

## Reporting — CSV out of every read view

Every read view also renders as CSV for spreadsheets/BI: `--csv` streams to stdout (pipe-friendly), `--csv <path>` writes a file. The same data structure feeds the text table and the CSV, so the numbers can't disagree — and the honesty ships with them: **method tags are columns** (`measured` vs `estimated` survives into the sheet), refusals and the UNPRICED counts stay visible, line endings are LF on every OS (byte-identical, deterministic).

```bash
cage report --csv --since 7d > weekly-spend.csv   # last week's spend, flat
cage attrib --csv                                  # per-tool savings, method column kept
cage export --csv calls --since 30d -o calls.csv   # raw ledger rows for a pivot table
```

`--csv` works on `report` · `attrib` · `roi` · `compare` · `study report` · `calibration` · `human` · `trend`; raw rows come from `cage export --csv calls|receipts|tasks`. CSV is one-way reporting — never an import source; the re-importable fleet bundle stays jsonl (`cage export --study`). Column contracts: [docs/csv-output.md](docs/csv-output.md); `cage query csv-output` explains the design. The `cage` skill on all four agents knows the recipes — ask your agent for "my weekly cost report as CSV".

## The `$0` guarantee

Every derived view is parse / arithmetic over the log — **no LLM call, ever, on the read or maintenance path.** The only model spend is whatever your agent already does; Cage just meters it. The semantic cache and learned compressor ship behind opt-in `[embeddings]` / `[ml]` extras; the default install is model-free and dependency-free. 569 tests passing; `cage demo` reproduces the worked attribution example against a real ledger.

**Honest limits.** Cage doesn't decide your human rate — it prices minutes at a blended rate you set, and labels the result `estimated` so it never pretends to be a timesheet. Marginal-by-fixed-order is defensible and `$0`, but it is an *ordering convention*, not a Shapley value (that's a deferred audit mode). And a counterfactual cell is an honest reconstruction, never an invoice — the `method` column says so on every row, on purpose.

## What's new

Latest release below — full history and detail in [CHANGELOG.md](CHANGELOG.md).

- **v0.22.0 — restricted environments: python-launcher mode + cage.pyz.** For locked-down endpoints: `cage setup --python-launcher` wires everything through the interpreter (`python3 -m cage` / `py -3 -m cage`) — nothing exe-shaped probed or executed, persisted in policy, doctor names the mode (`CAGE_RUN_PYTHON=1` is the no-rewire runtime override); every release now also ships a CI-built single-file `cage.pyz` + `SHA256SUMS` for machines without pip (bundled data reads via importlib.resources, `--version` labels the zipapp, derived views byte-identical to a wheel install). See [docs/restricted-environments.md](docs/restricted-environments.md); `cage query restricted-env`.

## The name

Named after *John Cage*, whose *4′33″* framed four and a half minutes of "silence" so an audience would finally *hear* the ambient cost they'd been ignoring. Cage the tool does the same to your AI stack: it takes the spend and the savings everyone assumed were free or unknowable, and makes them something you can actually account for. It's part of a family of deterministic *substrate → derived views* tools — [fux](https://github.com/arpitarya/fux) (decisions → rules) — and now Cage (LLM traffic + receipts → ledger). The names are deliberate, and they sit beside `bach`, `wagner`, and `orff`.

---

If you've ever been the one in the room with no numbers, run `cage demo` — `pip install cage-flux`.

## License

MIT — see [LICENSE](LICENSE).
