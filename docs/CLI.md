# CLI

**Every `cage` command in one place.** 16 top-level entries — 5 daily verbs, 7 groups,
4 hidden plumbing commands — resolving to **55 addressable commands**. The front door
(`cage --help`) shows only the curated five plus the group names; this file is the
whole surface.

Fast path: `cage report` (the daily number) · `cage import` (pull usage in) ·
`cage setup` (wire a project) · `cage doctor` (is capture healthy?) ·
`cage query` (how is any number computed?).

This file is **checked against the live parser** by
[`tests/test_cli_reference.py`](../tests/test_cli_reference.py) — every command and
flag named here must exist, and every command and flag the parser knows must appear
here. A rename that misses this file turns the suite red. See
[Maintaining this file](#maintaining-this-file).

---

## Conventions

- **`cage <group> <command>`** — the four real subparser groups (`insights`, `task`,
  `authorship`, `data`) accept `--help` at both levels.
- **`cage <group> <action>`** — `prices`, `study` and `policy` take their action as a
  **positional choice**, not a subparser, so their `--help` is the group's, not the
  action's. See [Known gaps](#known-gaps).
- **No argparse abbreviation.** Shortening `report` to `rep` is an error, not a
  prefix match.
- **Exit codes:** `0` ok · `1` error (`error: <msg>`; full traceback only under
  `CAGE_DEBUG=1`) · `2` argparse usage · `130` interrupt. `cage authorship verify` is
  report-only and **always exits 0**; `cage hook budget` exits `2` on a deliberate
  budget block. **`cage hook` is the one verb that does NOT exit `2` on a usage
  error** — for it, `2` already means *block the tool call*, so an argparse failure
  exits `0` with the fix on stderr (see the `hook` section).
- **Two error regimes, never mixed.** Write paths are fail-open (return `False`,
  swallow, never raise into a request). Only the read/CLI boundary raises.

### Capture-on-read flags

Every read view takes these three, so they are documented once here rather than
repeated in each table:

| Flag | Meaning |
|---|---|
| `--no-import` | skip the capture-on-read pre-sweep for this read |
| `--quiet` | silence capture confirmations (or set `CAGE_QUIET=1`) |
| `--why-ledger` | print which ledger resolved and why (to stderr) |

They are global too, so `cage --no-import report` works. The one exception is
**`cage data export --no-import`**, which is a *different* flag with a different
meaning — it skips the export's own import-first refresh and emits the ledger exactly
as-is.

### Export flags

`cage report`, every `cage insights` view, and the three other report-shaped views —
`cage authorship summary`, `cage study report`, `cage task quality` — take these two, so
they are documented once here rather than repeated in each table
([`cage/viewexport.py`](../cage/viewexport.py), `cage query view-export`):

| Flag | Meaning |
|---|---|
| `--export [PATH]` | write this view to disk. Bare = `<ledger>/.cage/output/<view>-<stamp>/` holding every format the view has; `PATH.txt` / `.md` / `.csv` / `.json` = exactly that file; any other `PATH` = a per-run folder under it |
| `--stamp` | prepend the generated-at metadata block to **stdout** too |

Three rules make this safe to rely on:

- **`--export` never changes stdout.** The view prints byte-for-byte what it would
  have printed without the flag; the write confirmation goes to stderr. Pinned by
  [`tests/test_view_export.py`](../tests/test_view_export.py).
- **Every artifact carries the stamp; stdout does not unless you ask.** Mandatory in a
  file (a number with no as-of outlives its terminal), optional on a terminal. Set
  `CAGE_RUN_STAMP` to pin the clock for a byte-reproducible artifact.
- **`--csv` and `--json` are unchanged**, on stdout *and* to a path — a `--csv PATH` is
  a stream redirected to a file, `--export` is an artifact, and only the artifact grows
  the block.

A format the view cannot produce (`--export x.csv` on a view with no CSV renderer) is
a refusal, not an empty file. Bare `cage` (the headline) has **no** `--export`: a
root-level optional-value flag would swallow the following subcommand. `.cage/output/`
is not `.cage/out/` (that one is `cage data serve`'s docroot), and no cleanup class
prunes it — cage never deletes an artifact it wrote.

---

## Global

`cage` with no command prints the headline.

| Flag | Meaning |
|---|---|
| `--version` | print the version (labels `(zipapp)` when run from `cage.pyz`) |
| `--json` | machine-readable output (bare `cage`: the headline dict) |
| `--usd` | bare `cage`: add dollar figures to the headline (tokens are the default; `[display] usd = true` for always-on) |
| `--ledger DIR` | use this cage base dir as the active ledger, overriding project/global resolution (the `.cage`-equivalent holding `ledger/`, `state/` and the policy file) |
| `--help` | the curated front door |
| `--no-import` · `--quiet` · `--why-ledger` | see [Capture-on-read flags](#capture-on-read-flags) |

Ledger resolution order: `--ledger` / `CAGE_BASE` → project `.cage/` → global
`~/.cage`. `cage --why-ledger` prints which won and why.

---

## Daily verbs

### `cage report`

Where the spend went. Tokens are the default view; dollars are opt-in.

| Flag | Meaning |
|---|---|
| `--by {route,agent,model,provider,day,task}` | group dimension |
| `--since WINDOW` | window like `7d` / `24h` / `2w` |
| `--scope DIR` | filter to one monorepo top-level dir (plan §3.6.2) |
| `--project [NAME]` | filter to one project (working-dir basename; `.` or the bare flag = current dir). Exact for Claude only (plan §3.7) |
| `--team` | read the merged `refs/notes/cage-ledger` team view (plan §3.6.3) |
| `--usd` | add dollar columns |
| `--all-columns` | force the full column grid even without savings signal (for scripts wanting a fixed shape; CSV never gates) |
| `--json` | machine-readable output |
| `--csv [PATH]` | emit as CSV (stdout, or to `PATH`) |

Plus the [export two](#export-flags) (`--export [PATH]` · `--stamp`) and the
[capture-on-read three](#capture-on-read-flags).

Savings printed here are **GROSS** — `raw_alternative − actual`, excluding the cost of
*using* the tool. The word `gross` appears on every surface that prints the number;
`cage query gross-vs-net` explains why.

### `cage import`

Pull every agent's usage into the resolved ledger. Idempotent and incremental (a
per-agent high-water cursor). Works with no hooks and no project.

| Argument / flag | Meaning |
|---|---|
| `BUNDLE …` | study bundle zip(s) from `cage data export --study` — merged by row identity, idempotent (plan §4.9) |
| `--agent {claude,copilot,kiro,all}` | which agent to meter (default: `all`) |
| `--path PATH` | a transcript file or dir to scan (log-bearing agents only) |
| `--project PROJECT` | restrict to one repo's sessions (Claude only) |
| `--since WINDOW` | only transcripts modified within a window like `7d` / `24h` / `2w` |
| `--rescan-graphify` | re-run graphify savings detection over every matched log, ignoring the incremental cursor |

`--rescan-graphify` is a **backfill**, and it exists because the cursor is right for
calls and wrong for savings: an unchanged log is skipped, so a graphify route that ships
*after* a session was ingested can never see that session again. Detection only — it
re-ingests no call or credit rows — and idempotent by receipt id, so re-running it files
nothing the second time. Use it once after upgrading into a release that adds a route
(v0.47 added copilot VS Code and kiro CLI).

Kiro's IDE log is a machine fact, not a project fact, so those rows route to `~/.cage`
even during a project sweep
([ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)); the summary
line names the sink, and a total never includes a row that landed elsewhere.

### `cage setup`

Scaffold `.cage/` and wire agents. Idempotent and byte-identical across machines — two
teammates running it must not churn a committed diff.

| Flag | Meaning |
|---|---|
| `--claude` · `--copilot` · `--kiro` | set up that agent |
| `--all` | set up all three agents |
| `--project-only` | scaffold `.cage/` + graphify + PATH only; skip MCP wiring |
| `--wire-only` | wire agent(s) only; skip scaffold and graphify |
| `--status` | report which agents are wired (no changes) |
| `--global` | initialize the global ledger (`~/.cage`) for project-less capture, then exit |
| `--no-project` | skip the per-project `.cage/` scaffold + MCP wiring |
| `--no-graphify` | skip the graphify interceptor |
| `--python-launcher` | persist `[wiring] python_launcher = true` and wire everything via `python3 -m cage` / `py -3 -m cage` — no exe probed or executed (`cage query restricted-env`) |
| `--hooks` | also wire the opt-in **L1** lifecycle hooks (agent identity at capture, auto task-close, budget blocking). OFF by default; re-running without it **removes** them. CLI sessions only — hooks do not fire under a VS Code extension |
| `--skills` | also install the opt-in **L3** skills — one source text delivered as a Claude skill, a Copilot prompt and a Kiro steering doc. OFF by default; re-running without it removes them |
| `--no-hooks` | explicitly assert the hookless floor (the default) — for a script that wants to state the intent rather than rely on it |
| `--sync-sources` | refresh the cage-managed `[sources]` block in `cage.toml` from the built-in defaults, preserving user-added entries; run after upgrading cage |

The agent surface is a four-layer ladder — **L0** hookless (this is cage, never
optional) → **L1** `--hooks` → **L2** MCP (wired by default) → **L3** `--skills`.
Adding or removing any layer changes **no number**; `tests/test_floor.py` proves it.

### `cage doctor`

Is capture healthy? Never sweeps — it diagnoses.

| Flag | Meaning |
|---|---|
| `--json` | machine-readable output |
| `--bundle [PATH]` | write one redacted diagnostics archive (counts-never-content): doctor output, path probe, debug log + heartbeats, version/platform, footprint paths + row counts, policy provenance, cursor state |
| `--paths` | read-only path probe: every candidate log location per agent on this OS — found/missing, files matched, parseable rows, cursor state, and why a location missed (writes nothing) |
| `--wiring` | installed-artifact inventory: every wired file (project + global/user), its status (`current`/`stale`/`dead`/`foreign`), and a per-agent fully/partially/not-wired verdict (read-only) |

### `cage query`

Ask cage how any number or mechanism works. Stdlib token-overlap matching over a
curated registry — **no LLM, no network**. No match ⇒ it suggests the closest ids
rather than guessing.

| Argument / flag | Meaning |
|---|---|
| `question` | a question in prose, or an exact topic id |
| `--list` | list every explainer topic |
| `--kind {calculation,concept}` | filter `--list` to one kind |
| `--all` | show the top matches, not just the best |
| `--json` | machine-readable output |

---

## `cage insights` — 17 derived views

| Command | What it answers |
|---|---|
| `cage insights attrib` | per-tool marginal savings for a task (plan §4.2) |
| `cage insights matrix` | counterfactual permutation table for a task (plan §4.4) |
| `cage insights roi` | saved $ per tool vs its own cost + latency |
| `cage insights adoption` | do your agents actually invoke the tools you wired? (counts only — nothing here is priced) |
| `cage insights chats` | per-chat detail: tokens/cached/cost by `(agent, surface, session)`, titled where the store has a title (local-only — no `--team`) |
| `cage insights graphify` | per-chat graphify usage & GROSS saving: recorded tokens · the modeled without-graphify counterfactual · saved% (tokens-only — no `--usd`) |
| `cage insights commits` | one row per commit: tokens, human hours, and the `agent / human~ / unattr / unkn` line split. **No USD on this surface, by design** (the v1 veto, kept) |
| `cage insights commit SHA` | one commit in detail: tokens · origin + confidence · the four line buckets · suggested-vs-kept counts · per-file table · wall/agent/human time |
| `cage insights verdict` | one-line answer: is this tool saving or costing? A pure composer over attrib/roi/regression/quality — computes no new statistics and refuses (`INSUFFICIENT DATA`) over approximating |
| `cage insights budget` | session/day spend vs policy ceilings (plan §8.1) |
| `cage insights compare` | **measured** comparison of closed tasks grouped by stack (n · median · IQR; the delta is `estimated` + observational) |
| `cage insights estimate` | pre-task cost band (median + IQR) from matching closed tasks — `modeled`, refuses thin history |
| `cage insights calibration` | **measured** hit-rate of recorded estimates vs actuals — the estimator's only confidence source |
| `cage insights why` | full provenance: a call + every receipt against it |
| `cage insights forecast` | project monthly spend vs the budget (plan §8.5) |
| `cage insights regression` | alert when cost-per-call drifts up (plan §8.3) |
| `cage insights recommend` | cheapest-path: which tools to enable/skip (plan §8.4) |

Flags, beyond the [capture-on-read three](#capture-on-read-flags) and the
[export two](#export-flags) — **every view in this group takes `--export`/`--stamp`**
([`tests/test_view_export.py`](../tests/test_view_export.py) gates the fan-out, so a
new insight cannot ship un-exportable):

| Command | Flags |
|---|---|
| `cage insights attrib` | `--task ID` (default: most recent) · `--scope DIR` · `--team` · `--json` · `--csv [PATH]` |
| `cage insights matrix` | `--task ID` · `--scope DIR` · `--usd` (adds the cost column; the token grid always renders) · `--json` · `--html PATH` (standalone page, no CDN) |
| `cage insights roi` | `--since WINDOW` · `--json` · `--csv [PATH]` · `--export [PATH]` · `--stamp` |
| `cage insights adoption` | `--since WINDOW` · `--json` · `--csv [PATH]` |
| `cage insights chats` | `--since WINDOW` · `--agent {claude,copilot,kiro,all}` · `--all` (every chat; default is top 20 by `tokens_in`) · `--usd` · `--json` · `--csv [PATH]` |
| `cage insights graphify` | `--since WINDOW` · `--agent {claude,copilot,kiro,all}` · `--all` (every receipt-bearing chat; default is top 20 by `saved`) · `--all-chats` (include chats with no graphify receipts too) · `--json` · `--csv [PATH]` |
| `cage insights commits` | `--since WINDOW` · `--all` (every commit; default is the 20 newest) · `--json` · `--csv [PATH]` |
| `cage insights commit SHA` | positional `SHA` (short or full) · `--files` (every file; default is the 8 largest) · `--json` · `--csv [PATH]` |
| `cage insights verdict TOOL` | positional `TOOL` (name as it appears on receipts, e.g. `graphify`) · `--since WINDOW` (default: all history) · `--json` |
| `cage insights budget` | `--session ID` · `--scope DIR` · `--json` |
| `cage insights compare` | `--scope DIR` · `--label WORD` · `--by KEYS` (comma-separated from `stack,scope,label`; `stack` always included) · `--json` · `--csv [PATH]` |
| `cage insights estimate` | `--scope DIR` · `--label WORD` · `--agent NAME` · `--record TASK` (stamp the band onto that **open** task row so calibration can score it at close) · `--json` |
| `cage insights calibration` | `--json` · `--csv [PATH]` |
| `cage insights why CALL_ID` | positional `CALL_ID` · `--json` |
| `cage insights forecast` | `--json` |
| `cage insights regression` | `--since WINDOW` (recent window vs the baseline before it) · `--tolerance F` (drift fraction that trips the flag) · `--json` |
| `cage insights recommend` | `--since WINDOW` · `--json` |

`compare`, `estimate` and `calibration` are gated by `MIN_COMPARE_N` /
`MIN_ESTIMATE_N` in `constants.py` — below the gate they **explain, never number**.

`commits` / `commit` carry **no dollar figure at all** — not gated, absent. They are
the rebuilt agent-vs-human axis (v1 died pricing an inferred gap), so tokens and hours
are the whole vocabulary; valuation stays in your spreadsheet. A commit with no
joinable call renders `—`, never `0`: *nothing joined here* and *this cost nothing* are
different claims. See `cage query agent-authorship`.

---

## `cage task` — 3 commands

| Command | What it does | Flags |
|---|---|---|
| `cage task outcome TASK` | close a task with its outcome (`ok` by default) | `--redo` (mark as needing a redo) · `--label WORD` (one short token: letters/digits/`._-`, ≤32 chars, for `cage insights compare` grouping — never a path or free text) |
| `cage task time DURATION` | attest how long **you** spent on a task — `45m` · `2h` · `1h30m` · a bare number of minutes. Written as `human_minutes` + `human_minutes_method = "attested"` | `--task ID` (default: the most recent) |
| `cage task quality` | quality-adjusted cost: cost per *successful* task (plan §8.2) | `--json` · `--export [PATH]` · `--stamp` |

`cage task time` is the **only** unmarked human number cage will ever print: it always
outranks the wall-clock estimator in `cage insights commits` (rendered `*`, versus the
estimator's `~`), and **no rate, hourly figure or dollar amount is derived from it,
anywhere** — that pairing is what killed the v1 axis. Parsing is strict, not fail-open
(a typo is refused, never silently a different number), and `0` is rejected because the
absence of an attestation already means unknown.

`cage task outcome` is the **task-close verb** the whole cost-impact surface
(compare / estimate / calibration / net savings) depends on. It is also the single
write tool exposed over MCP (`cage_task_outcome`), through the same code path — so the
label guard cannot be laxer on the agent-facing side.

---

## `cage authorship` — 5 commands

Who wrote which files in which commit (plan §3.5). Its own closed enums, separate from
the ledger's: `method ∈ {hooked, transcript, heuristic}`, `origin ∈ {human, agent,
agent-autonomous, unknown}`.

| Command | What it does | Flags |
|---|---|---|
| `cage authorship origin SHA` | authorship attribution for a commit | `--attest {human,agent,agent-autonomous}` (record a human-triage attestation) · `--agent NAME` (attach to `--attest`) · `--json` |
| `cage authorship summary` | how much of this repo's history cage can speak to at all — **unknown-rate first**, then the recorded rows by agent/method and the suggested-vs-kept counts | `--since WINDOW` · `--json` · `--csv [PATH]` |
| `cage authorship verify` | report-only consistency check over the provenance ledger — **never fails the build, always exits 0** | — |
| `cage authorship notes-sync` | merge the buffered provenance into `refs/notes/cage-provenance` | `--write` (push; default is dry-run unless `CAGE_NOTES_WRITE=1`) · `--json` |
| `cage authorship ledger-sync` | merge local call/receipt rows into `refs/notes/cage-ledger` for the team view (plan §3.6.3) | `--write` · `--json` |

`origin = "human"` is reachable **only** via explicit attestation, and is always paired
with `method = "heuristic"` (enforced at construction). `unknown` is a read-time
default, never a written row. Automated rows are written by the **import sweep**
(`cage/authorcapture.py`, [ADR 0008](adr/0008-line-match-authorship-counts-persisted-content-transient.md)),
gated by its own consent switch `[authorship] capture` / `CAGE_AUTHORSHIP` — this is
the one path that reads your diffs, and that is a different permission from metering
spend. Both sync commands are **CI-sole-writer**: a dev machine
defaults to a dry-run print.

---

## `cage prices` — 6 actions

Manage the project's rate card. Writes are text surgery, never a whole-file rewrite,
and split by lifecycle: `set`/`sync` write **`prices.toml`** (vendor facts);
`alias`/`route-tool` write **`cage.toml`** (routing decisions).

| Action | What it does |
|---|---|
| `cage prices list` | every visible row: bundled vs project, plus origin and `[meta]` |
| `cage prices unpriced` | what's billing `$0`, with a runnable fix line each |
| `cage prices set PROVIDER MODEL` | insert/update a project price row |
| `cage prices alias PROVIDER MODEL` | route a router pseudo-model to a real price row |
| `cage prices route-tool TOOL` | price a tool's call-less receipts (plan §4.5) |
| `cage prices sync` | diff vs the installed bundle (dry-run by default) |

Each action is a **real subparser** since 2026-08-11 (CLI-GAPS(b)), so it owns its own
flags and its own `--help`; a flag named below appears on that action alone.

| Flag | Owner |
|---|---|
| `--input F` · `--output F` · `--cache-read F` | `set` — USD per MTok of input / output / cached input (cache-read defaults to 0.1× input) |
| `--to P/M` | `alias` · `route-tool` — target price row as `<provider>/<model>` |
| `--remove` | `route-tool` — delete the tool's route from the managed block |
| `--update` | `sync` — apply bundled values to rows confirmed via `--yes`; restamp `[meta]` |
| `--yes PROV/MODEL` | `sync` — confirm one drifted row (repeatable; `all` confirms every one) |
| `--since WINDOW` | `unpriced` — window like `7d` / `2w` |
| `--json` | every action |

Positionals: `set`/`alias` take `PROVIDER MODEL` (`-` means the empty provider some
router rows stamp; the model exactly as `cage prices unpriced` printed it);
`route-tool` takes the tool name. Bare `cage prices` prints the action list.

**cage never fetches a price** — research is yours, off the code path. Repricing is
derive-time, so fixing the table re-prices every historical row; the ledger is never
rewritten.

---

## `cage study` — 5 actions

The P5 fleet study (plan §4.9). Opaque random machine id, **opt-in by enrollment** — an
unenrolled ledger stamps nothing and stays byte-identical to legacy.

| Action | What it does |
|---|---|
| `cage study join PHASE` | enroll this machine: wire + start + doctor |
| `cage study start PHASE` | switch phase (one short token) |
| `cage study stop` | end the current phase |
| `cage study report` | coverage first, then the paired delta — the **only** study action that is a rendered view, and so the only one carrying `--csv`/`--export`/`--stamp`. A marker verb does not have those flags at all (argparse usage error, exit 2); it used to reach them from the group and refuse at runtime |
| `cage study id` | print the opaque machine id (never a hostname) |

Flags: `--json` on every action; `--csv [PATH]` · `--export [PATH]` · `--stamp` on
`report` only. Bare `cage study` prints the action list. The sample unit is the
**machine-day**; the paired
delta is `estimated` with a work-mix caveat, gated on `MIN_COMPARE_N`
machines-with-both-phases.

---

## `cage policy` — 2 actions

| Action | What it does |
|---|---|
| `cage policy diff` | dry-run categorized view (add / update / keep / orphan) |
| `cage policy sync` | the same view; `--apply` writes |

| Flag | Owner |
|---|---|
| `--apply` | `sync` — write adds/updates and stamp `[meta] policy_version`. **Not a flag on `diff`** (CLI-GAPS(b)): passing it there is an argparse usage error, not a runtime refusal |
| `--yes SECTION.KEY` | `sync` — confirm one non-reconstructable row (repeatable; `all` confirms every one shown) |
| `--json` | every action |

Customized values are never modified and orphans never deleted; pricing tables delegate
to `cage prices sync`. **Nothing ever auto-applies this** — hints recommend, humans run.

---

## `cage data` — 8 commands

### `cage data export`

Import (refresh) first, then emit. `--agent` filters the *output* only — the sweep is
always all-agent.

| Flag | Meaning |
|---|---|
| `--format {jsonl,csv,json}` | `jsonl` = raw rows, re-ingestable (default) · `csv` = flat call rows · `json` = summary |
| `--csv {calls,receipts,tasks}` | flat one-way CSV of raw ledger rows for a pivot table; same PII surface as the ledger — counts and ids, never content |
| `--json` | alias for `--format json` |
| `--otel` | one-way OpenTelemetry GenAI-conformant JSON (calls as `gen_ai.*`, receipts cage-namespaced as `cage.*`). **Pre-stable spec** — the semconv version is pinned and stamped in the output (`cage query otel-export`) |
| `--since WINDOW` | window like `7d` / `24h` / `2w` |
| `--project NAME` | filter to one project (basename; `.` = current dir). Claude-exact (plan §3.7) |
| `--agent {claude,copilot,kiro}` | filter to one agent |
| `--no-import` | skip the import-first refresh; emit the ledger exactly as-is |
| `-o, --output FILE` | write to `FILE` (default: stdout) |
| `--study [PATH]` | write one fleet-study bundle instead (rows + phase markers + counts-only manifest; default name `cage-study-<machine>.zip`) |

CSV and OTel are **one-way reporting formats — never an import source**. The
re-importable fleet bundle stays jsonl.

### The other seven

| Command | What it does | Flags |
|---|---|---|
| `cage data cleanup` | prune aged `.cage/state/` files (closed allowlist; dry-run by default). **Deletion only ever happens here, with `--apply`** — the automatic path only warns | `--apply` · `--days N` (default: `[cleanup] days`, else 90) · `--json` |
| `cage data migrate-savings` | consolidate historical graphify receipts into `savings/graphify/` | `--apply` (default: dry-run print) · `--json` |
| `cage data watch` | foreground poll loop: import every interval until Ctrl-C (**no OS job** — cage installs no scheduler) | `--agent {claude,copilot,kiro,all}` · `--interval SECONDS` (default 60) · `--since WINDOW` |
| `cage data serve` | local dashboard over the ledger (`$0`) | `--port N` |
| `cage data proxy` | metering reverse-proxy for clients you can't edit | `--port N` · `--upstream URL` |
| `cage data meter` | run a command under the metering proxy | `--upstream URL` · then `--` and the command |
| `cage data graphify` | meter a third-party graphify call without touching it | `--task ID` (default: project dir name) · then `--` and the graphify invocation |

`cage data cleanup` never touches `ledger/` (tool savings included),
`cage.toml`/`policy.toml`, `prices.toml`, `machine.json`, `study.jsonl` or
`limits.json` — by construction.

---

## Hidden plumbing

Callable but deliberately absent from `cage --help`.

| Command | What it does | Flags |
|---|---|---|
| `cage mcp` | run the MCP server over stdio — 9 read tools + exactly one write tool (`cage_task_outcome`). Wired automatically by `cage setup` | — |
| `cage demo` | seed the plan §4.4 worked example and print the attribution and matrix tables | — |
| `cage debug` | tail the metadata-only debug log (`CAGE_DEBUG=1` to populate) | `--tail N` (default 20) · `--json` (one JSON event per line) |
| `cage hook EVENT` | the opt-in **L1** lifecycle entry point, invoked by wired agents, not by hand | positional `EVENT ∈ {session-start, session-end, tool, budget}` · `--agent NAME` (required — stamped, never inferred) · `--session ID` · `--command CMD` (hashed for attestation, never stored) |

`cage hook` is **fail-open absolute**: every event exits `0` on any internal failure.
The sole non-zero is `cage hook budget` returning `2` when
`[budgets] on_exceed = "block"`.

**That absoluteness extends to the argparse boundary, and it is the reason `hook` is
exempt from the usual exit `2`.** Exit `2` is the block verdict, wired to
`PreToolUse`/`Bash` — so an unknown event name (what a rename against stale committed
wiring produces) would otherwise block **every** Bash call in the session, silently: a
blocked tool call reads as the agent refusing, not as cage failing. Instead cage exits
`0` and prints the live event list plus `cage setup --hooks` on stderr. The direction
is derived from the accepted events, never a hand-kept map of old spellings — the same
reason `wiringscan` detects against the live parser.

---

## Removed and renamed verbs

Every old spelling below still **prints a direction and exits 1** rather than failing
silently — the map is [`cage/verbmap.py`](../cage/verbmap.py) `REMOVED`. Renaming or
removing a top-level verb is a **wiring migration**, not just a CLI change: add the
entry to `verbmap`, update this file, then sweep every wire module, `install.sh`,
`justfile` and `tools/dummyrepo`.

| Old spelling | Now |
|---|---|
| `init` | `cage setup` |
| `import-claude` | `cage import` with `--agent claude` |
| `attrib` · `matrix` · `roi` · `verdict` · `budget` | the same name under `cage insights` |
| `compare` · `estimate` · `calibration` · `why` | the same name under `cage insights` |
| `forecast` · `regression` · `recommend` | the same name under `cage insights` |
| `outcome` · `quality` | the same name under `cage task` |
| `origin` · `verify` · `notes-sync` · `ledger-sync` | the same name under `cage authorship` |
| `export` · `cleanup` · `watch` · `serve` · `proxy` · `meter` · `graphify` | the same name under `cage data` |
| `human` · `human-record` · `trend` | **removed outright** — the Tier-1 human axis was amputated in v0.36 and does not return without a proposal doc |
| `hook-session-start` · `hook-stop` · `hook-session-end` · `hook-post-tool-use` · `hook-post-commit` · `hook-prepare-commit-msg` | **removed outright** — replaced by the single `cage hook EVENT` |

---

## Known gaps

Recorded here rather than quietly worked around; tracked in [OPEN-WORK.md](../work/OPEN-WORK.md).

**None open.** Both entries that stood here are closed:

1. ~~`cage data migrate-savings` missing from the front door~~ — fixed 2026-08-03
   (CLI-GAPS(a)); `cage --help` now lists all eight of `data`'s commands, and the front
   door is gated bidirectionally against the live parser.
2. ~~`prices`/`study`/`policy` take their action as a positional choice~~ — converted to
   real subparsers 2026-08-11 (CLI-GAPS(b)). Each action now owns its `--help` and its
   own flags, so an inapplicable flag is an argparse usage error (exit 2) instead of a
   flat union plus a runtime refusal. Every group in cage now behaves the same way.

---

## Maintaining this file

**Trigger: any change to the CLI surface** — a new command, a renamed or removed verb,
an added or dropped flag, or a changed choice list. Update this file *in that same
change*, and bump its row in [DOC-REGISTRY.md](../work/DOC-REGISTRY.md).

The gate is [`tests/test_cli_reference.py`](../tests/test_cli_reference.py), which is
**bidirectional** against `cli.build_parser()`:

- every leaf command the parser knows appears here (no silently undocumented surface);
- every command path named in a code span here resolves in the parser (no dead verbs in
  prose — the F1 failure class, in documentation form);
- every long flag named here exists somewhere in the parser, and every flag the parser
  knows is named here — except the three shared capture-on-read flags, declared once
  above;
- a flag that exists on exactly **one** command must be documented in that command's
  section, so a shared vocabulary can't paper over a misfiled flag.

A doc that only *promises* to stay current is the class of doc this repo has already
watched go stale twice. This one fails the suite instead.
