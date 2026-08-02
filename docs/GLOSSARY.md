# GLOSSARY

Every recurring cage term, defined once. Verified against the code that owns it.
When a term's meaning changes, fix it here in the same change (docs-in-sync law).

This file is an entry-point tracker: ALL-CAPS, no frontmatter.

---

**flux** — a family of tools that are `$0`, deterministic, stdlib-only, and derive
everything from an append-only substrate with no model in the loop. cage is a flux
(attribution ledger); fux is a flux (decisions→rules). "Independent of any AI tool"
is part of the definition.

**substrate** — the append-only source of truth. For cage: the JSONL ledger rows
(`calls`, `receipts`, `tasks`, `provenance`). Everything else is *derived* from it
and is a pure function of it — same ledger + same policy ⇒ same tables. Owned by
[schema.py](../cage/schema.py).

**derive** — computing a view (`report`, `attrib`, `roi`, …) from the ledger at read
time. No clocks, no randomness, no network, no model. The ledger is never rewritten
by a derive.

**meter vs. metering** — `cage.meter` is the public context manager; `cage.metering`
is the module. Kept distinct on purpose, or the package attribute shadows the
submodule. Metering is **fail-open**: an error in the meter never propagates into a
request path.

**fail-open** — the write-path error regime. `ledger.append` returns `False`, never
raises; `meter()` swallows errors in cleanup. Traceable under `CAGE_DEBUG`, never
silent by accident. Contrast the read/CLI boundary, which is **typed** (raises the
single `CageError` → `error: <msg>` + exit 1).

**call** — one recorded LLM request: token counts, model, provider, ids. Prompt
bodies are never a field — counts only, PII-safe by construction.

**receipt** — a recorded *saving* (tokens/USD/ms/gCO₂ not spent). A call-less token
receipt (graphify/fux shims) prices via the ladder in
[receiptprice.py](../cage/receiptprice.py). See **legacy human row** for the
`tool="human"` / `unit="minutes"` rows a pre-0.36 ledger still holds.

**gross saved** — every `saved` in the ledger, and the only savings figure cage measures
per query: `raw_alternative − actual`, the *avoided read cost*. It excludes the cost of
**using** the tool (the invoking turn, the round-trip, a hook's injected context), so a
large gross and a session that cost more are both true at once
([finding](regression/2026-08-01-finding-saved-is-gross.md)). Every surface says `gross`,
from one phrasing (`netsaved.GROSS_NOTE`).

**cost of use** — what invoking a tool costs, as opposed to what the tool spends on
*itself* (`meta.tool_cost_usd`, which graphify honestly declares as `$0`). Confusing the
two is what made `verdict` print a bare SAVING. See **attributable cost**.

**attributable cost** — the computable stand-in for cost of use
([netsaved.py](../cage/netsaved.py)): the **distinct** calls joined to a receipt's task
whose `ts` falls within ±`NET_ATTRIB_WINDOW_S` (120s) of *any* of that tool's receipts on
that task, unioned so an adjacent call is charged once. A lower bound by construction.

**net saved** — `gross − attributable cost`, per task. `modeled` at its own lower
confidence (0.4): it stacks a time-window join on top of gross's counterfactual, so it
is never `measured`. A task with no in-window call is **uncovered** and its net reads
*unavailable* — `net == gross` is structurally impossible, which is the point.

**usage row** (graphify-capture GC1) — a diagnostic breadcrumb, one per graphify run,
`{op, args_hash, exit, ms, outcome}` in `state/graphify-usage.jsonl`
([usagelog.py](../cage/usagelog.py)). **Never priced, never read by a derived money
view** (it lives in `state/`, so it can't move a reported number) — its job is to prove
*"graphify ran N×, R receipts, U unmeasurable"* vs *"never ran"*, the distinction the
0-real-receipts mystery lacked. Counts-never-content: `args_hash` is a hash, never the
query text.

**report-read receipt** (graphify-capture GC2) — a graphify saving from *reading*
`graphify-out/GRAPH_REPORT.md`/`wiki/**` instead of scanning the source files the graph
maps. Same `tool="graphify"` but `op="report-read"`, a weaker counterfactual (the graph's
own source-file corpus, [repoceiling.py](../cage/repoceiling.py)) ⇒ **lower confidence
(0.3), still `modeled`, footnoted apart** from a `graphify query` receipt (never
conflated). **The 0.3 is UNVALIDATED (G.1)** — a placeholder not yet scored by `insights
calibration`, and the footnote says so; it is never tuned by intuition.

**repo ceiling** (graphify-capture GC5b; **community-bounded, Phase A 2026-07-29**) — a
deterministic day-one upper bound on graphify savings, from `graph.json` alone. **Bounded
to the largest community's corpus** — `Σ toks(files of the largest community)`
([repoceiling.community_corpus](../cage/repoceiling.py) → [graphifymodel.repo_ceiling](../cage/graphifymodel.py))
— because a graph answer stands in for *one* coherent concern, not every file the graph
touches; the whole-corpus sum over-claims on a real repo (552k tokens / 249 files on cage
itself) and reads as decoration. Typical ≈ the median community; the whole corpus is kept
as context only. A pre-community graph falls back to the whole corpus, labelled `UNBOUNDED`.
`modeled`, a labelled band, the "is graphify worth installing here" number available before
a single query runs. Never summed into a measured total.

**task** — one unit of work, `tasks.jsonl`, last-write-wins by id, git-snapshotted
at close. PII guard: SHA + diff *counts* + top-level dirs only — never the commit
message, author, or file paths.

**provenance** — *who wrote which files in which commit* (a fourth append-only
file). Its own closed enums (`method ∈ {hooked, transcript, heuristic}`,
`origin ∈ {human, agent, agent-autonomous, unknown}`), deliberately separate from
call/receipt enums. `unknown` is a read-time default, never a written row.

**method** (measured / modeled / estimated) — **sacred.** The trust tag on every
derived cell. `measured` = a recorded invoice; `modeled` = a reconstructed
counterfactual; `estimated` = a heuristic (e.g. a compression ratio). Never let a
projection read as `measured`. Owned by the `METHOD_TRUST` ladder in
[constants.py](../cage/constants.py).

**marginal-by-fixed-order** — cage's attribution rule (plan §4). Each tool's saving
is its marginal contribution given a fixed pipeline order; a reconstructed
counterfactual cell is `modeled`/`estimated`, never `measured`.

**the three number layers** — cage keeps its numbers in three never-mixed places:
**contract** = the closed enums in [schema.py](../cage/schema.py); **policy** =
user-economics in `cage.toml` (budgets, pipeline order, routing) + the vendor rate card
in `prices.toml` (prices, `[credits]` — split out, prices-toml plan §3);
**constants** = code heuristics not meant as config but that must be reviewable
([constants.py](../cage/constants.py)).

**the human axis (Tier-1)** — **removed in v0.36**, substrate included. Priced
*what a person would have cost* for a whole task (`tool="human"` receipts,
`unit="minutes"`, a `[human]` rate table) plus the passive `gap_ms` turn-gap
derivation. Gone: the modules, the `cage human` group, `cage insights trend`,
the field and the unit. Not to be confused with provenance `origin="human"`
(authorship — untouched) or with `cage task outcome`/`quality`, which merely
lived in that command group. See PLAN §4.6, `cage query savings-axis`.

**legacy human row** — a `tool="human"` or `unit="minutes"` receipt written before
v0.36. Ledgers are append-only, so these persist. Every money view excludes them
([`report._is_legacy_human`](../cage/report.py)) because no rate remains to price
them, and `cage report` **counts the exclusion in a footnote** — the removal was
never allowed to make a total quietly smaller.

**scope vs. project** — two different monorepo axes. `scope` = the top-level changed
dir (§3.6.2); `project` = the working-dir basename (§3.7). Both additive, optional,
empty = legacy contract. Never conflated.

**capture: pull-based and global** — `cage import`/`cage export` over a *resolved*
ledger is the universal path; hooks are an optional real-time add-on that mostly
don't fire under VS Code extensions. cage installs **no OS scheduler** (ADR 0002).

**`glob` vs `path_globs`** — the two discovery patterns on a `[sources]` entry, doing
two different jobs. `glob` is **anchored** to that entry's declared `path`
(`*/chatSessions/*.jsonl` under `workspaceStorage`) and drives every normal import.
`path_globs` is **root-agnostic** (`**/…`) and is read *only* when `cage import
--path`/`--project` replaces the location with a directory the user names — where an
anchored pattern matches nothing, which was the copilot `--path` bug. Both are seeded in
[paths.py](../cage/paths.py), materialized into `cage.toml` by `cage setup`, and read
from there at import time (Directive A); `replace = true` covers both, extra entries
union their `path_globs`, and **absent `path_globs` means `--path` scans nothing, loudly**
— there is deliberately no code fallback. Resolved by `paths.path_globs_for`.

**route_key** — a non-PII hash of the resolved ledger-root path (never a basename)
stamped on pushed receipts, so a read can reclaim a stray saving by exact key.
Additive/optional, never in an id.

**machine ledger** — the global `~/.cage` (`$CAGE_HOME/.cage`), when it holds facts that
belong to the *machine* rather than to a project. Distinct from its older role as the
project-less **fallback** sink: kiro's IDE rows land there even from inside a project,
because their source has no project dimension to attribute by
([ADR 0006](adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)).

**routed leg** — the one place a single `cage import` sweep writes **two** ledgers: kiro's
IDE rows to the machine ledger, everything else to the active sink. Fully contained in
`importcmd._kiro_leg` (own `seen`, cursors, lock, health, manifest), completes before the
sweep's own lock is taken. `paths.kiro_routed(root)` is the only predicate; `None` means
no routing, which is what an explicit `--ledger`/`CAGE_BASE` produces.

**the ledger notes refs** — `refs/notes/cage-ledger` (team ledger) and
`refs/notes/cage-provenance` (authorship), each **CI-sole-writer**, merged by row id
(`mergeutil.union_by_id`). A dev machine's sync defaults to a dry-run print. Why a
git ref, not an external sink: [ADR 0001](adr/0001-ledger-team-aggregation-notes-not-external-sink.md).

**UNPRICED** — a call/receipt whose `(provider, model)` has no price row. Bills `$0`
and *says so* (a ⚠ summary), rather than silently understating a total. Fixed with
one pasted `cage prices set`/`alias` line; repricing is derive-time and retroactive.

**capture-on-read** — a *read* (`report`/`insights *`/MCP read tools) triggers
`ensure_captured` before rendering (throttled, fail-open, gated by policy), so a
number is never staler than the instant it's shown — with no hook. Writes the ledger
only, so determinism holds.

**state-dir cleanup** — the closed `.cage/state/` allowlist (`cage/cleanup.py`),
never the ledger. Since v0.37 deletion only ever happens via an explicit
`cage data cleanup --apply`; the auto path (piggybacked on `cage import`) only
ever **warns** on stderr, silent when nothing is eligible, and never deletes.
`[cleanup] enabled` gates the auto path outright (no reminder at all when off);
`[cleanup] warn` silences just the reminder text. Neither switch is consulted by
a manually-typed command — an explicit `cage data cleanup`/`--apply` always runs.
Tool savings (`ledger/savings/<tool>/`) can never be cleaned: they sit under
`ledger/`, which is on the never-list, and a per-tool cleanup class must never be
added (savings are unrecoverable, unlike a cursor or a debug-log row).

**wiring liveness** — is an installed artifact's cage command still a command?
Checked against the **live parser** (`cli.build_parser()`), never `verbmap.REMOVED`
— a verb deleted outright is dead *and* absent from `REMOVED`, so a grep would miss
it. `REMOVED` supplies the fix-hint tail only.
[wiringscan.py](../cage/wiringscan.py).

**PATH-winning interceptor** — the `graphify` shim that *actually runs*: whichever
one the shell resolves first (walk `PATH`, first executable wins), which may live in
a **different project's** `bin/` and outside every root cage scans. Classified
`live` · `dead` · `shadowed` · `foreign` by
[pathshim.py](../cage/pathshim.py). A **dead** one is a doctor *failure* — capture is
silently off and indistinguishable from cage not being installed. Distinct from
`foreign`, where metering is off by *absence*.

**shadowed shim** — this root installed a graphify interceptor, but a different file
wins on PATH, so the shim you installed here never runs. Advisory, and the message
names **both** paths. Not a failure on its own: if the winner is itself dead, that
outranks it.

**interceptor twin** — one of the two files implementing the graphify interceptor: the
extensionless POSIX `bin/graphify` and the Windows `bin/graphify.cmd`. Both are
installed on **every** OS (a committed `bin/` must be byte-identical across machines),
and each is inert where it cannot run. Windows resolves a bare name only through
`PATHEXT`, which has no extensionless entry — so on Windows only the `.cmd` can ever
run, and a root carrying only the other twin is a doctor **failure**, not a green tick.
Enumerated once in [paths.py](../cage/paths.py) (`GRAPHIFY_SHIMS`) so no read surface
can see only one.

**shim contract** — the written behaviour spec both interceptor twins implement and are
tested against ([docs/shim-contract.md](shim-contract.md)): behaviours **B1–B8**
(binding on every twin) and divergences **D1–D7** (real and permanent — cmd has no
`exec`, so the real binary runs as a child process). Two implementations of an unwritten
contract drift; this is the written one, and the first artifact of the
[tool-integration-contract](proposals/tool-integration-contract.proposal.md).

**hook bypass** — an agent hook that invokes graphify by **absolute path**, so the
command never traverses PATH: cage's interceptor can't see it, and a hook isn't a
Bash tool call, so the transcript route can't either. **Advisory, never a failure** —
graphify works as designed and cage merely can't observe that path; savings from an
explicit `graphify query` are unaffected. With `--strict` the read hook *denies* the
first raw read, making the avoided read unmeterable by any current route, and the
wording escalates. The hook is never modified.
[hookbypass.py](../cage/hookbypass.py).

**cage-managed root** — a `<root>/.cage/` directory beside the artifact in question;
the boundary of what `cage setup` may rewrite. A dead shim inside one is healed; a
dead shim outside one is **named with a runnable fix and never written** — cage does
not silently edit another project's files.

**chat (view)** — one row of `cage insights chats`: every call sharing an
`(agent, surface, session)` bucket, titled where `imports.jsonl` carries a name
(display label only — deleting the manifest moves zero numeric cell, `manifest.py`).
No name ⇒ the session id, never a fabricated title. Kiro-IDE's constant session id
already collapses every run into one chat; kiro-CLI conversations are `credits` rows
(no `tokens_in`/`tokens_out`) and never appear here. [chats.py](../cage/chats.py).

**credit (billed)** — the `credits` call field: what the *provider itself* billed for
one call, recorded verbatim. Copilot persists it per request in VS Code's chatSessions
store (`copilotCredits`) and per shutdown in the CLI (`totalPremiumRequests`); since
2026-06-01 it *is* GitHub's own tokens×rates computation, made with what cage cannot see
(what `copilot/auto` routed to, GitHub's current rates). Rung 1 of the pricing ladder.
**Absence and zero are different facts** — no recorded credit falls through to the token
rung, a recorded `0.0` is a real zero priced at `$0.0000` — and credits are never derived
from tokens in either direction. [creditprice.py](../cage/creditprice.py), FORMULAS §1.1a.
Not to be confused with **`[credits]`** (the vendor rate card's per-model `per_mtok`
multipliers, in `prices.toml`) or with Kiro-CLI **credit rows** (a whole different row
kind, `schema.make_credit`).

**`[billing.<agent>] usd_per_credit`** — *your* plan's rate for one billed credit, and
the switch that turns rung 1 on. Lives in `cage.toml`, not `prices.toml`, because it is
a decision about your own plan that must survive a `cage prices sync` — vendor facts
move, routing decisions stay. **Unset by default:** with no rate, credits render as a
*count* and those rows price by token × table. Unset ≠ `0.0`, which is a real rate that
prices at zero. [policy.credit_rate](../cage/policy.py).

**agent line** — an added line in a commit that exactly matches (after whitespace
normalization, above `MIN_MATCH_CHARS`) a line the agent's transcript records it having
*proposed*. Direct evidence. Read from the provenance row's `agent_lines`, never
re-matched at render time. See [ADR 0008](adr/0008-line-match-authorship-counts-persisted-content-transient.md).

**human~** — an added line in a file **that session did propose** which matched no
proposal: a real human tweak of agent work. A *residual*, so it is always `estimated`
and always carries the `~`. Distinct from `unattributed`, and never written as `human`
(that requires an attestation).

**unattributed (line)** — an added line in a file **no** session proposed. Could be
human-written, vendored, or generated output; cage has no evidence which and says so.
Introduced because a single `human` bucket printed 76.6% on cage's own repo, 89% of it
one commit of generated JSON. Distinct from **unattributed (commit)** below.

**unattributed (commit)** — a commit with no joinable call. Its token cells render `—`,
never `0`: *nothing joined here* and *this cost nothing* are different claims.

**commit window** — commit *i* owns `(ts_{i-1}, ts_i]`, upper bound inclusive. The rule
that places an edit or a call on a commit without ever consulting `HEAD`-at-import.
Its bounds are in the **UTC normal form**, normalized at construction.

**UTC normal form** — `YYYY-MM-DDTHH:MM:SSZ`, sub-seconds **truncated**, the single
shape every timestamp is converted to before any comparison in the authorship join
([commitjoin.py](../cage/commitjoin.py) `norm_ts`). It exists because git renders
`%cI` in the *committer's own* offset while calls and transcripts stamp UTC, and
ordering strings across offset representations is meaningless. **Seconds, not
milliseconds** — `%cI` has no sub-second, so finer precision would push an edit made
inside the commit's own second out of it and break the inclusive bound
([finding](regression/2026-08-02-finding-commit-window-timestamp-skew.md)).

**attested time** — minutes a person asserted with `cage task time`, stored as
`human_minutes` + `human_minutes_method="attested"`. Rendered `*`, always outranks the
`~` estimator, and **no rate or currency is ever derived from it**.

**unconfirmable (call)** — a call carrying no `project` stamp. Excluded from a commit
join as a *distinct* fact from "another project's call": adopting unstamped rows would
pull every other repo's spend onto this repo's commits.
