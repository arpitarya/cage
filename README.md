# Cage

> **Cost dashboards guess what your AI stack spent. Cage counts what it actually *used* — tokens and credits, straight from the vendors' own logs — and what each tool in the stack saved you, with a `method` tag on every number and no invented dollar anywhere.**

[![PyPI](https://img.shields.io/pypi/v/cage-flux.svg)](https://pypi.org/project/cage-flux/)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#the-0-guarantee)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

You're running an agent, a graph tool, a rules engine, maybe Copilot. At the end of the month someone asks *"is any of this worth it?"* — and the honest answer is a shrug and a Slack thread. Cage meters every LLM call, collects a **savings receipt** from each tool in the stack, and turns the raw stream into an **attribution ledger**: what each agent used, what each tool saved you, which conversation burned the tokens, who wrote which commit, and which tools your agents actually *adopt* when offered. **`$0`, deterministic, zero dependencies, no model in the maintenance path.**

**Cage does not price anything, on purpose.** It ships no rate card and computes no dollars — it reports the units the providers themselves record: **tokens** and **credits**. A dollar figure built from a rate card cage cannot check against your invoice is a reconstruction wearing a currency symbol, and this project would rather show you a number it can stand behind. ([ADR 0011.](work/archive/adr/0011-cage-measures-usage-not-cost.md))

**Named after *John Cage*.** · Python ≥ 3.11 · stdlib only · MIT · sits beside `fux`, `bach`, `wagner`, `orff`.

**Platforms:** macOS is field-validated (real extension sessions, the full manual capture matrix); Linux and Windows are CI-tested across the whole suite + scenario runner, plus a graphify leg that installs the real binary and meters real queries. The graphify PATH interceptor now ships as a **twin pair** — the bash shim and a `graphify.cmd` — so a bare `graphify` reaches cage on Windows too (Windows PATH lookup goes through `PATHEXT`, which has no extensionless entry, so the bash shim alone could never be found there). Windows is CI-asserted, not yet field-validated. On Windows, run `cage doctor --paths` first — it shows every log location cage probes on your machine and why any missed. Locked-down endpoint (AppLocker/WDAC blocks the exe, or no pip)? `cage setup --python-launcher` wires everything through the interpreter instead, and every release ships a single-file `cage.pyz` — **note that this turns the graphify shim route off too** (there's no `cage` command left on PATH for it to probe), so a launcher-mode project relies on the transcript route for graphify savings; see [restricted-environments.md](work/restricted-environments.md).

<p align="center"><em>Measured on itself: <a href="work/dogfood/latest.md">cage's own ledger, real numbers, refreshed periodically</a>.</em></p>

## The story

> *Another README story. Yeah. Because nobody ever walked out of a meeting humming a feature table, and you will not remember mine. So forget the table. Here's ninety seconds about a conference room, a pile of money, and a bunch of people who have no idea what they're talking about. One of them is you. — Arpit*

You ever notice how *everybody's* saving money now? Everybody. The agent's saving money. The graph tool's saving money. Copilot's saving money. Two tools you built over a weekend — saving money. Add it all up and you should be getting a check in the mail. Funny thing about that. The bill went *up*.

Here's the con. Nobody — and I mean *nobody* — can show you the number. They got slides. They got a roadmap. They got a guy named Kevin who "feels like it's a game-changer." What they don't got is one honest figure that says *this* tool saved *this much* on *this* task. Ask for *that* number and watch the room go quiet and somebody suggest we "circle back."

And the kicker — you built half of it. So when finance points at you and says "is this worth it," you, the expert, the one who's supposed to *know* — you got a screenshot and a feeling. You're not in trouble for spending the money, folks. You're in trouble because you bought the same fog everybody else did.

**Cage is the thing that ruins the fog.** It's the itemized receipt nobody asks for and everybody needs: the graph tool saved 27,000 tokens here, fux saved 6,400 there, this conversation burned 400,000 and that one burned 900 — each number stamped so you know which ones were counted and which ones are some computer's best guess. It doesn't do synergy. It does arithmetic.

**And here's the part that'll annoy you: cage used to print dollars, and it stopped.** Not because dollars don't matter — because cage was *making them up*. Multiply real tokens by a rate card some maintainer typed in by hand, and you get a confident-looking figure nobody can check against an actual invoice. That's the fog again, in a nicer font. So the rate card went in the bin, eleven commands went with it, and what's left is what the vendors themselves wrote down. A meter you can't catch lying is worth more than a dashboard you can. ([Why.](work/archive/adr/0011-cage-measures-usage-not-cost.md))

And when cage's own numbers came back saying a session *with* the graph tool used **more** tokens than one without? It printed that too, labelled, instead of burying it. ([The finding.](work/regression/2026-08-01-finding-saved-is-gross.md))

## See it

```bash
$ cage insights chats
```

```
Chats

chat  agent   surface  calls  tokens_in  cached_in  cache_write  tokens_out  credits  agent%
----  ------  -------  -----  ---------  ---------  -----------  ----------  -------  ------
demo  claude  —            1      8,600          0            0       1,500        —       —

· claude credits: — (Claude Code records no credit unit on disk)
· 1 chat(s) show agent% `—`: no landed code evidence — not committed yet, committed in
  another repo, or nothing matchable landed. `—` is never 0%

· saved is GROSS — avoided read cost; it excludes the cost of USING the tool
  (the invoking turn, the injected context). `cage query gross-vs-net`
```

Per-tool savings any meter can attempt. The parts most don't: **the marginals sum exactly to the total** — each receipt reports its saving *given the tools upstream of it*, in a fixed visible order, so nothing double-counts — and the `method` column, so you always know which row was counted and which was reconstructed. **No projection ever masquerades as a measurement.** That discipline is the whole product.

And read that footnote, because cage prints it every single time: `saved` is **gross**. It's the read cost you avoided, and it does *not* subtract the tokens spent invoking the tool. Cage will not net that for you, because it can't do it honestly at the per-query grain — so it says so instead of quietly picking a number.

*(The table above is the seeded `cage demo` example. Where does cage's own evidence stand? Lab-validated capture across Claude Code, Copilot and Kiro on macOS — and whether a graph tool comes out ahead overall is honestly **still open**: the first paired A/B run found the ON arm using more tokens, gross savings notwithstanding, at n=1. Cage prints that. Most tools in this space would not show you that sentence.)*

## Quickstart

```bash
pip install cage-flux           # the CLI, zero third-party deps
cd your-project
cage setup                      # guided wizard: defaults to all agents, wires MCP + graphify
# non-interactively: cage setup --all   (or --claude / … for just one)
cage demo                       # seed the worked example
cage import                     # pull every agent's usage into the ledger
cage insights chats             # per-chat detail: tokens + agent%, titled where the store has one
cage insights graphify          # per-chat graphify usage and its GROSS token saving
cage insights commits           # per commit: tokens, hours, and the agent/human line split
cage query "how is a saving calculated"  # explain any number — live formula, $0
```

**Every command, in one page: [docs/adr/0002_cli.md](docs/adr/0002_cli.md)** — the 4 daily verbs, the 5
groups, the hidden plumbing and every flag. It's checked against the live parser by
`tests/test_cli_reference.py`, so it can't quietly drift out of date.

> **Adopting into a project** — `cage setup` is the single front door: it offers Claude Code / Copilot / Kiro and **defaults to wiring all of them** (capture is pull-based and global, so any one of them meters the whole stack — there's no reason to pick just one). Drive it non-interactively with `cage setup --all` — or `cage setup --claude` for a single agent (`--no-project` / `--no-graphify` to skip parts). For finer control: `cage setup --project-only` scaffolds `.cage/` + the `bin/graphify` interceptor without wiring any agent (opt-in via `--<agent>`), `cage setup --wire-only --claude` wires just one agent's MCP, and `cage setup --status` reports what's already wired.
>
> **The agent surface is a ladder, and every rung above the first is optional.** **L0** is hookless capture plus every CLI view — that is cage, and it is what you get by default. **L1** (`cage setup --hooks`) adds lifecycle hooks for the two things pull capture structurally cannot do: stamping *which agent* ran something, and closing tasks at a session boundary so `compare`/`estimate`/`calibration` have anything to work with. **L2** is the MCP server (wired by default). **L3** (`cage setup --skills`) installs seven skills — one source text delivered as a Claude skill, a Copilot prompt and a Kiro steering doc. Every layer is committed, two-way (a plain `cage setup` removes what it didn't ask for), and **provably free**: a test installs all of them over a fixed ledger and asserts every number byte-identical, then strips them and asserts it again. If a layer moved a number, the layer would be wrong. Hooks are CLI-only — they don't fire under a VS Code extension, and every fact built on them says so.
>
> **What gets committed vs what stays local.** The project-wired files (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`, `.kiro/hooks/`) are committed with the repo and contain **no absolute paths** — they reference the committed shim `.cage/bin/cage-run` (identical bytes on every machine), which resolves cage at runtime and **exits 0 silently when cage isn't installed** (a teammate's clone gets working agents, no noise, no capture). Commit `.cage/` as-is: its own `.gitignore` already excludes the machine-local parts (`ledger/`, `out/`, `state/`). Kiro is committed too, by a different route: it resolves neither the shim nor `${workspaceFolder}` (it launches MCP servers from its own install directory), so its entry carries **no path at all** — `python3 -m cage mcp`, resolved through PATH like any interpreter. The trade is stated rather than buried: that depends on *which* `python3` wins, so `cage doctor`'s `kiro-mcp` check asks that interpreter to import cage and names the fix when it can't (on Windows, where `python3` is often absent, `cage setup --python-launcher` writes the `py -3` form for that machine). Re-running `cage setup` migrates any legacy absolute entries and prints what moved; `cage doctor` has a portability check.

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

**Cage is the chart on the fridge.** It writes down how much each robot chore *used up*, and how much the robot's little gadgets saved, so you can see which helper earned its place and which one just made noise. It counts in the robot's own units — never in play money it made up — and it marks which numbers it actually counted and which ones are its best guess, so nobody gets fooled by a confident-looking total. It does all of this for free, without ever phoning a friend for the answer.

## Why it's different

It's not another cost dashboard. The difference is a set of *properties*, not features:

- **Deterministic.** Every derived view — report, attribution, per-chat, authorship — is pure parse/arithmetic over an append-only log. Same ledger + same config ⇒ identical tables, every time. The numbers never drift because nothing guesses.
- **Honest by construction.** Every figure carries a `method`: `measured` (a recorded fact, read back verbatim), `modeled` (a reconstructed counterfactual), or `estimated` (a guess, labelled as one). A projection can never read as a measurement.
- **It counts; it does not convert.** Tokens and credits, in the units the vendors record. No rate card, no dollars, and no arithmetic between units — a copilot credit and a kiro credit are never added together, because they are not the same thing.
- **`$0` and zero-dependency.** Stdlib-only Python, `dependencies = []`. Heavy ML is an opt-in, off-by-default tier (`[embeddings]`, `[ml]`), never on the default path. Portable as a tarball, auditable line by line.
- **Agent-native.** Every read command takes `--json`; the ledger is served over MCP. Built so an agent can pull its own usage numbers *and verify them*, not just read a chart.

The "so what" chain: deterministic → so the numbers never hallucinate → so each one carries a defensible `method` → so you can put the claim in front of anyone who asks. That last clause is the one a dashboard can't say.

## Honest attribution — the part that survives the room

Anyone can sum a bill. Cage's job is to divide credit **without lying about it**, and it does that with three rules (full design: [docs/PLAN.md](docs/PLAN.md) §4):

- **Marginal-by-fixed-order.** Each tool's receipt reports the saving it produced *given the tools upstream of it*; the marginals sum exactly to the total — no overlap, no double-counting, `$0` to compute, the order fixed and visible (not a black-box Shapley pass).
- **Gross, and it says so.** `saved` is the read cost you avoided; it excludes the tokens spent *using* the tool. Cage prints that caveat on every view that shows the number, and reports **no net at all** — netting needs a per-query link that shim receipts structurally don't carry, so cage declines rather than picking one.
- **Outcome-aware.** Volume alone is dishonest — you can "save" by degrading answers and paying for the redo. `cage task outcome <task>` closes a task with its verdict, and `compare`/`estimate`/`calibration` read it.

```
Marginal attribution · task t_9f31 · anthropic/claude-sonnet-4-6

tool         unit    gross tok   method
-----------  ------  ---------   --------
compress     tokens      6,700   measured
graphify     tokens      6,800   modeled
fux          tokens      2,800   modeled
TOTAL        tokens     16,300

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
| **Policy** | user-tunable settings: pipeline order, capture switches, cleanup, authorship | `cage.toml` (previously `policy.toml`; still read as a fallback) |
| **Constants** | code heuristics not meant as config but that must be reviewable: the token divisor, the provenance ranks, the confidence fallback | `constants.py` |

And because the math should explain itself, **`cage query`** prints the real formula for any value with its numbers read *live* from policy + constants — never a hard-coded literal, so an explanation can't drift from the code:

```
$ cage query "how is attribution calculated"
marginal-attribution · how per-tool savings sum to the total with no double-count
  formula:  walk tools in policy order (graphify → fux → router → compressor → cache
  → response-cache); each receipt is its marginal saving given the tools upstream of
  it, so Σ(marginals) = total, no overlap.
  method:   per-row method = the least-trusted receipt for that tool (honest worst-case).
  code:     cage/attribution.py · cage/savings.py · cage.toml [tools.order]
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
   cage.toml (pipeline order / capture)   → report · attrib · chats · adoption
                                             · compare · why · origin · commits
```

You meter at the provider boundary (library adapter, a reverse proxy for clients you can't edit, or by parsing a Claude Code transcript). Everything downstream is a deterministic projection. The ledger carries token **counts**, never prompt bodies — PII-safe by construction; point `CAGE_LEDGER` at a private store to keep even the counts off-disk.

A tool earns rows in `attrib` by filing a **savings receipt**, and there are two ways in, by who owns the tool:

- **In-tool (you own it) — e.g. fux** carries a fail-open `cage_receipt.py` and emits its own `tool="fux"` receipt. Cage stays optional; fux runs unchanged with cage absent.
- **External adapter (third-party) — e.g. graphify:** cage reads graphify's use out of each agent's own session store at `cage import` and files a `tool="graphify"` receipt by parsing the cited `source_file`s. graphify is never edited, and a metering error never alters its result.

The command surface (27 subcommands: per-chat and per-commit views · task outcomes · authorship · fleet study · agents) is grouped in `cage --help`, which points at `cage query` for any "how is this computed". Every read command takes `--json` for the agent-as-user. **Cage deliberately ships no ledger rollup** — the views are per *conversation* and per *commit*, the two units you can act on. `cage insights chats` groups the ledger by `(agent, surface, session)` and titles each row where the store carries one — labels only, never a number the manifest could move. Its `agent%` column answers the question a spend rollup can't: *did this chat's tokens become code?* — per chat, the share of evidenced lines in files it touched that matched the agent's own proposals, read from the authorship rows rather than re-derived. Where cage has no evidence it prints `—` with the reason, never a `0%`. The doc map — design of record, subsystem docs, operations, archive — starts at [docs/README.md](docs/README.md).

## Works with any agent — explicit capture over one global ledger

Cage meters whatever speaks the wire format, so all three agents share **one** ledger contract. Capture is **pull-based and universal**: `cage import` reads each agent's on-disk usage log into the ledger, and every read view refreshes before it renders — they need no hooks, no project, and work the same whether you run a CLI or a VS Code extension.

```bash
cage import                 # capture every agent's spend into the active ledger
cage import                      # pull every agent's usage into the ledger
cage insights chats              # which conversation used the tokens?
cage study export                # the one-file fleet bundle, for the P5 study
```

The ledger resolves **`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`** — so a user with no project captures into the global ledger (`cage setup --global` to seed it). cage installs **no background job** (no launchd/systemd/cron); automate it, if you like, with your own cron line calling `cage import`.

Nonstandard install, a network home, or a custom tool that writes a supported format? Add import paths in `cage.toml` — `[sources.<agent>] paths = ["~/alt/logs"]` (or a custom `[sources.<name>] format = "claude"`), and declare `surface = "cli"` when a non-IDE store would otherwise be mislabelled; `cage doctor --paths` shows every location with its provenance and surface, and `cage query sources` explains the schema.

| Agent | Capture (universal) | Optional real-time | Read |
| ----- | ------------------- | ------------------ | ---- |
| **Claude Code** | `cage import` (transcript) | Stop hook (CLI only) | `cage` MCP |
| **Copilot** | `cage import` (session log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Kiro** | `cage import` (token log) | `agentStop` hook (CLI only) | `cage` MCP |
| **Your code / Orff** | `cage.meter()` library | — | `cage` CLI / MCP |

Hooks are an **optional** real-time add-on — they fire only under a CLI client, never under a VS Code extension — so `cage import` is the path that always works. Rows carry a `project` stamp (exact for Claude; Copilot/Kiro logs carry no project, so theirs is empty) — recorded today, read by no view since v0.50. Committed wired files never embed a machine's absolute cage path — they reference the repo-local shim `.cage/bin/cage-run` (see the Quickstart note).

**An agent's spend isn't showing up?** `cage doctor` shows the active ledger, each agent's real capture state, and "last import: N ago"; the metadata-only debug log says per agent whether a hook fired or raised (`CAGE_DEBUG=1`).

## Reporting — CSV out of every read view

Every read view also renders as CSV for spreadsheets/BI: `--csv` streams to stdout (pipe-friendly), `--csv <path>` writes a file. The same data structure feeds the text table and the CSV, so the numbers can't disagree — and the honesty ships with them: **method tags are columns** (`measured` vs `estimated` survives into the sheet), refusals and the UNPRICED counts stay visible, line endings are LF on every OS (byte-identical, deterministic).

```bash
cage insights chats --csv --since 7d > weekly-usage.csv  # last week per conversation, flat
cage insights graphify --csv                             # per-chat savings, method column kept
cage insights commits --csv --since 30d                  # per-commit rows for a pivot table
```

`--csv` works on `chats` · `graphify` · `commits` · `commit` · `authorship summary` · `study report`. CSV is one-way reporting — never an import source; the re-importable fleet bundle stays jsonl (`cage study export`). Every view also takes `--export` to write a stamped artifact to disk.

## The `$0` guarantee

Every derived view is parse / arithmetic over the log — **no LLM call, ever, on the read or maintenance path.** The only model spend is whatever your agent already does; Cage just meters it. The semantic cache and learned compressor ship behind opt-in `[embeddings]` / `[ml]` extras; the default install is model-free and dependency-free. 1521 tests; `cage demo` seeds a real ledger you can read with `cage insights chats`.

**Honest limits.** Marginal-by-fixed-order is defensible and `$0`, but it is an *ordering convention*, not a Shapley value (that's a deferred audit mode). And a counterfactual cell is an honest reconstruction, never an invoice — the `method` column says so on every row, on purpose.

## What's new

Latest release below — full history and detail in [CHANGELOG.md](CHANGELOG.md).

- **v0.51.0 — one shape per producer, and the ledger can prove it hasn't been edited.** Every producer now owns exactly one directory under `ledger/`: `claude/` `copilot/` `kiro/` (agents) · `consumer/` (your own code via `cage.meter`) · `graphify/` `fux/` `compress/` `responsecache/` (tool savings) · `provenance/` (authorship). The three agents' transcript→`calls` writer is **retired** — for claude it was a second copy of the same traffic, inflated **1.98×**, that no view read. Nothing on disk moved: every legacy file is still read, forever. New: a **tamper-evidence chain** ([ADR-INTEGRITY](docs/adr/0010_integrity.md)) that reports when something already written has changed — report-only, never a gate; the graphify interceptor works again after two days dead (`cage interceptor graphify`); and Copilot CLI chats finally get their names. ([the cross-check](work/regression/2026-08-14-calls-vs-metric-crosscheck.md) · [the ADR set](docs/adr/README.md))

## The name

Named after *John Cage*, whose *4′33″* framed four and a half minutes of "silence" so an audience would finally *hear* the ambient cost they'd been ignoring. Cage the tool does the same to your AI stack: it takes the usage and the savings everyone assumed were free or unknowable, and makes them something you can actually account for. It's part of a family of deterministic *substrate → derived views* tools — [fux](https://github.com/arpitarya/fux) (decisions → rules) — and now Cage (LLM traffic + receipts → ledger). The names are deliberate, and they sit beside `bach`, `wagner`, and `orff`.

---

If you've ever been the one in the room with no numbers, run `cage demo` — `pip install cage-flux`.

## License

MIT — see [LICENSE](LICENSE).
