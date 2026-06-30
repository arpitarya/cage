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
  "latency_ms": 5120, "ok": true, "retries": 0,
  "scope": "",                  // optional monorepo top-level dir (§3.6.2)
  "project": "cage"             // optional working-dir basename — derived attribution axis (§3.7)
}
```

`scope` and `project` are both optional and basename-only (the counts-never-content PII
guard); empty is the legacy contract. They are **different axes**: `scope` is the
monorepo top-level changed dir (§3.6.2); `project` is the working directory a call ran
under (§3.7), a derived `cage report --project` view of the global ledger. Only logs that
expose the cwd populate `project` (Claude transcripts do; Copilot/Kiro/Codex leave it
empty).

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

### 3.5 The provenance record — `provenance.jsonl` (fourth append-only file, v1)

A fourth, separate substrate answering a different question than §3.1–3.4: not
"what did this cost" but **"which agent wrote which files, in which commit, and how
sure are we?"** — authorship attribution, not spend attribution. It is a new record
type and read surface (`cage origin`), never a new tool; it reuses the same
append-only-buffer + git-shell-out + fail-open idioms as `tasks.jsonl`.

```jsonc
// .cage/ledger/provenance.jsonl   (append-only, local buffer only — see below)
{
  "schema_ver": 1, "id": "p_01J...", "ts": "2026-06-14T10:22:03Z",
  "sha": "a1b2c3d", "agent": "claude-code",
  "files": ["cage/origin.py", "cage/originrecord.py"],   // repo-relative, never absolute
  "lines_added": 142, "lines_removed": 3,
  "method": "hooked",        // hooked | transcript | heuristic — see below
  "origin": "agent",         // human | agent | agent-autonomous | unknown
  "confidence": 0.83,
  "session_id": "claude-code:4f1a"
}
```

**Two closed enums, deliberately separate from `UNITS`/`METHODS` (§3.1–3.2).**
`METHODS = (measured, modeled, estimated)` answers "how do we know a *saving*";
provenance answers "how do we know *who wrote it*" — a different question, so it
gets its own vocabulary rather than overloading the existing one:

- `method ∈ {hooked, transcript, heuristic}` — `hooked` is a live `PostToolUse`
  capture (sees `tool_input`'s file path as the agent acts — the highest-trust
  signal); `transcript` is parsed after the fact from a session log (the same
  idiom as `transcript.py`'s call-metering path, lower trust because it can't see
  in-process line counts); `heuristic` is inferred with no agent-side signal at
  all (git alone, or a human attestation — see below). Ranked by
  `constants.PROVENANCE_METHOD_TRUST` (`hooked=2 > transcript=1 > heuristic=0`), a
  parallel ladder to `METHOD_TRUST` for this different enum. **`method` is sacred
  here too**: a union of two fragments that disagree on the same file never reads
  as a stronger method than its weakest real input.
- `origin ∈ {human, agent, agent-autonomous, unknown}` — defaults to `unknown` and
  is **never written as `human` automatically**. The only way `origin="human"`
  reaches the ledger is through an explicit attestation (`cage origin <sha>
  --attest human`), which is always `method="heuristic"` by construction (a person
  looked at it; no automated signal fired) — `schema.make_provenance` enforces
  this pairing at construction time, not just by convention.

**`unknown` is a read-time default, never a written row.** A commit with zero
cage signal (no hook, no transcript, no attestation) gets **no row at all** —
`cage origin <sha>` derives `origin="unknown", confidence=0.0` from the *absence*
of any fragment, computed at read time in `origin.explain`. This keeps the ledger
sparse (facts only) and avoids materializing a row for cage's entire pre-adoption
git history. The one way a not-otherwise-signaled commit gets a row is a human
attesting to it — a genuinely new fact, worth appending.

**Confidence and corroboration.** Base confidence derives from the method rank
(`originrecord.confidence_for`); it's bumped by `PROVENANCE_CORROBORATION_BONUS`
when a *second, independent* capture path (e.g. both the live hook and the
transcript fallback) reports an overlapping file for the same `(sha, session)` —
two paths agreeing is stronger evidence than either alone, the same spirit as
`human.py`'s confidence ladder, applied to a different signal.

**Widened PII surface — repo-relative file *paths*, not just top-level dirs.**
`tasks.jsonl` (§3.4) deliberately stored only top-level changed *directories*,
never full paths, as its PII guard. Provenance needs more: "who wrote which
*file*" is meaningless without the file. The guard that holds instead:
counts-never-content — `files` are repo-relative paths and line *counts* only,
validated at `schema.make_provenance` construction time (reject any absolute path
or `..` segment) — never diff bodies, never commit messages, never author
name/email. This is a deliberate, narrow widening of the existing PII line, not a
relaxation of it.

**Distribution: local buffer → `refs/notes/cage-provenance`.** The local
`provenance.jsonl` is a buffer only (gitignored, machine-local, exactly like
`.cage/ledger/`); the canonical record is `refs/notes/cage-provenance`, and **CI is
the sole writer to it** (`cage notes-sync` defaults to a dry-run print of the
merge plan; it only pushes when `CAGE_NOTES_WRITE=1`, which CI sets). Merge policy
is **append/merge by row id, never overwrite** — `notessync.merge_rows` unions
fragments from possibly-multiple CI runs touching the same sha, resolving any
disagreement on the same file by `PROVENANCE_METHOD_TRUST` rank.

**Read surface.** `cage origin <sha>` (`origin.py`) reports the highest-confidence
row(s) for a sha, or the derived unknown default. `cage verify` (`verifycmd.py`)
is a **report-only** consistency pass (shas exist in git, `origin=human` rows are
all attestations, methods are in the closed enum) that **always exits 0** — a
hard constraint, never wired as a CI gate.

**Capture.** A `PostToolUse` Claude Code hook (`hooks.post_tool_use`) buffers
file-level diffs per session as edits happen; a local `post-commit` git hook
(`gitcommithook.py`, installed alongside the Claude Code hooks by `cage adopt`)
resolves that buffer against the just-made commit's sha and writes the `hooked`
row. A `SessionEnd`-time transcript fallback (`transcript.parse_provenance`)
covers agents/edits the live hook missed, tagged `transcript`. A
`prepare-commit-msg` git hook stamps `Co-authored-by`/`Change-Origin`/
`Agent-Session` commit trailers from the same buffer as a bypassable ergonomic
convenience — never the ledger's source of truth.

**Out of scope (v1).** Signed notes, hunk-range fingerprinting, build-blocking in
`cage verify`, and transcript archival are explicitly deferred — each has a
one-line `# v2:` marker at its natural call site rather than being half-built.

---

## 3.6 Ledger scale — partitions, scope, team aggregation

§3.1–3.5 each describe a single append-only file. That shape is correct for one
developer on one machine; three pressures break it — **volume** (a heavy agent user
emits 1–2k call rows/day, so every derive re-scans full history), **monorepo** (one
`.cage/` at repo root spans many sub-projects with no component key), and **team view**
(machine-local ledgers never combine). The fix for all three reuses idioms already in
the plan, and changes only *how the append-only files are laid out / combine* — never a
new mutation of derived state.

### 3.6.1 Time-partitioned ledger files (read-path layout)

Each long-lived log (`calls`/`receipts`/`tasks`) is partitioned by UTC month: the
writer appends to `calls-YYYY-MM.jsonl` (`ledger.append_row` picks the shard from the
row's own `ts`, `paths.Footprint.shard`); readers glob the set + any legacy single file
and concatenate (`ledger.read_kind`). Paired with `SINCE_WINDOW_DAYS`, a `--since`
query *skips* whole shards whose month is entirely below `since_cutoff`
(`ledger._month_entirely_below`) rather than filtering rows it already loaded — the
point of the partition. **Determinism:** the shard name derives from the row's `ts`,
never a write-time clock; same rows ⇒ same shards ⇒ byte-identical reads.
**Backward-compatible:** a legacy `calls.jsonl` is still globbed (read first, oldest);
migration is "new writes go to the dated file," never a rewrite of the past (the ledger
is never rewritten). `provenance.jsonl` is exempt — it is a buffer flushed to notes
(§3.5), not a long-lived store. Granularity (`constants.PARTITION_GRANULARITY="month"`)
lives in the third audit layer — reviewable, not user-config.

### 3.6.2 The `scope` dimension (additive contract change)

Calls and receipts gain one optional field, `scope` — the **top-level changed dir** of
the work, reusing `tasks.jsonl`'s "top-level-dirs-only, never full paths" PII guard
(§3.4). `schema.make_call`/`make_receipt` gain `scope: str = ""` (appended to
`CALL_FIELDS`/`RECEIPT_FIELDS`); empty string is the default and the non-monorepo case.
It is resolved the same way tasks resolve theirs — `tasks.scope_for` reads
`git_snapshot`'s top-level `dirs` (single dir ⇒ that component, ambiguous/none ⇒ `""`),
fail-open, no new git path; the meter resolves it best-effort and cached
(`metering._scope_for`), never a git shell-out per call. `report`/`attrib`/`budget`/
`matrix` gain an optional `--scope <dir>` filter (`ledger.by_scope`); no flag ⇒
byte-identical to today (the §3.5 no-flag invariant).

### 3.6.3 Team aggregation via `refs/notes`, not a backend

The ledger stays gitignored and machine-local (committing per-dev per-task cost into
permanent shared git history is a surveillance surface even counts-only). The team view
reuses the **exact** §3.5 distribution model rather than an external collector (which
would break `$0`/stdlib/no-infra): each machine's `.cage/ledger/` is the local buffer;
`cage ledger-sync` unions local call/receipt rows into a single
`refs/notes/cage-ledger` ref **by row id** (`mergeutil.union_by_id`, the pure core
shared with provenance's `merge_rows` — ledger uses plain first-by-id, no method
tie-break, since ulids never legitimately collide), written **only by CI**
(`CAGE_NOTES_WRITE=1`; a dev's `ledger-sync` is a dry-run). Rows live in one note on the
repo's empty-tree object (a universal, deterministic anchor — ledger rows have no commit
to attach to). `report`/`attrib --team` read the merged ref and degrade to the local
view when it's empty/missing (fail-open); the rollup dimension is `scope`, **never
per-developer identity** (opt-in per-person attribution is deferred — a `# v2:` marker
in `ledgersync.read_team`).

> **DECISION (flag for review):** team aggregation uses `refs/notes/cage-ledger`, not an
> external sink. Rationale: keeps `$0`/stdlib/no-infra, reuses the proven merge-by-id
> law, and the aggregate travels with the repo on clone. **Veto point:** if call/receipt
> volume per repo genuinely exceeds what notes should hold (single-digit GB/yr is fine;
> 100s of GB is not), revisit with an `export` shard to an out-of-repo store — but only
> then, and only with a named volume number.

### 3.6.4 Ledger-size warning (read-path, warn-only)

On the read path (`ledger.read_kind`), the byte size of the globbed shards is summed and,
past a threshold, **one** line is printed to **stderr** (never stdout — stdout is the
deterministic table surface; a warning there would break byte-identity) pointing at the
remedy (archive old `*-YYYY-MM.jsonl` shards / `ledger-sync` then prune). The threshold
resolves policy-first (`policy.toml [ledger] warn_mb`, MB) then the derived
`constants.LEDGER_WARN_BYTES` fallback (≈24 healthy monthly shards ≈ 2 heavy solo-years
— tied to the partition mechanic, not a magic MB). Warn-only and fail-open: fires at most
once per dir per process, swallows a `stat` error, never blocks or raises. **A `block`
mode is deliberately absent on the read/derive path** — a derive never refuses (the flux
invariant); a write-path block (cf. `[budgets] on_exceed = warn|block`, the CI
disk-quota case) is a separate, un-taken decision (see ADR).

### 3.6.5 Invariants this amendment must not break

`$0`/stdlib-only (glob, datetime, git shell-out — never `import git`); determinism
(shard names from `ts`, no clock/random on read); ledger never rewritten (new write
targets only); four agents always (`scope` + `ledger-sync` fan out to all four); method
is sacred (aggregation is a row union, not a re-derivation); no-flag byte-identity
(`--scope`/`--team`/partitioning all default off ⇒ output identical to pre-amendment).

## 3.7 Universal capture — global ledger + explicit import/export

cage is a package any user installs, often using **only** Copilot, only Codex, only Kiro,
or any mix, in a CLI **or a VS Code extension**. Field-proven: hooks are client-specific
and mostly don't fire (a VS Code extension never runs `.codex/hooks.json` /
`.kiro/hooks/*.hook` / `~/.copilot/hooks`; only Claude Code's extension honors its hooks),
yet the on-disk import works for all four, always. So capture **leads with explicit
`cage import` / `cage export`** over a global ledger, and cage installs **nothing in the
background**.

**Capture is pull-based.** Nothing runs on its own. `cage import` (capture) and
`cage export` (import-then-emit) are the canonical verbs; hooks are demoted to an optional
real-time add-on. cage installs **no OS scheduler** — no launchd/systemd/cron/schtasks,
no `cage scheduler` command. Hands-off automation, if wanted, is the user's own cron line
calling `cage import` (documented, never installed). `cage watch` is an optional
*foreground* `sleep` poll loop the user starts and Ctrl-Cs; it registers nothing.

**Ledger resolution (one active sink per run, never a double-write):**
`--ledger`/`CAGE_BASE` → nearest project `.cage/` from cwd → global `~/.cage`
(`paths.resolve_root`/`active_ledger_source`). The global ledger mirrors a project
`.cage/` (its own `ledger/`, `state/`, `policy.toml`), is month-partitioned like any other
(§3.6.1), and is created on first write or by `cage setup --global`. `--ledger PATH`
re-bases the whole footprint via `CAGE_BASE`; the legacy `CAGE_LEDGER` (a *ledger-dir*
override, e.g. Orff's elgar store) keeps its meaning, honored independently by
`Footprint.ledger`. The cwd-`.cage` guard is gone: a hook firing outside any project now
lands in the **global** ledger rather than scattering a stray local `.cage/` (the resolver
prevents scatter structurally), so a Copilot-only user is captured even via the hook.

**Project as a derived view (the `project` field, §3.1).** Per-project *capture* is
impossible for Copilot/Kiro/Codex (their logs carry no cwd), so project is only ever a
derived *attribution view*, exact where the log supports it. `cage report --project <name>`
(or `--project .`/bare = cwd basename) filters the global ledger by the `project` field;
the view is exact for Claude and silently excludes the projectless rows of the other
agents (surfaced in the output). `scope` (§3.6.2) is untouched.

**Incremental import (scale).** With no daemon, the hot paths are manual `cage import`,
`export`'s import-first refresh, and the `cage watch` loop — each would otherwise re-parse
every transcript and reload the whole 22k+-row ledger per run. A per-agent high-water
**cursor** (`.cage/state/cursors.json`, last-seen `(size, mtime)` per source file) skips
unchanged files before parsing, and the ledger `seen` set is built once per run and shared
across agents; `hooks.append_new`'s id-dedupe stays the correctness backstop. The cursor
also stamps `_last_import`, surfaced as "last import: N ago" by `cage doctor`/`cage report`
(the pull-based staleness nudge).

**Honest doctor.** `cage doctor` infers each agent's capture state from the debug
heartbeat (fired recently ⇒ real-time active; never ⇒ a hook that's *wired* is not one
that *fires*, e.g. under a VS Code extension); it never labels an unfireable hook "capture
wired," names the active ledger sink, shows last-import staleness, and points at
`cage import`/`cage export` as the universal path. No scheduler row (cage installs none).

**Invariants:** `$0`/stdlib (`csv`/`json` only; no fs-watch lib, no network on the
capture/read path); counts-never-content (no prompt bodies in any export; `project`/`scope`
basename-only); deterministic byte-identical export for the same `--since` window;
fail-open + idempotent (a malformed `policy.toml` degrades to the bundled default, never a
traceback); additive (the one new optional `project` field; hooks, MCP, and the
project-local `.cage/` ledger all unchanged); four agents always.

---

## 3.8 Provider quota + estimated credits — `cage limits` (a state snapshot, NOT a ledger)

cage meters tokens; it has no view of provider **quota/credits**. Two things are
recoverable from data cage already touches: Codex's rollout JSONL carries a `rate_limits`
block (remaining-% windows), and post-2026 GitHub/Codex plans consume credits as a function
of tokens, so a credit estimate is derivable. `cage limits` surfaces both — under a hard
**a wrong number is worse than no number** rule. (Debated devil's-advocate + pre-mortem;
see the ADR — the substrate-vs-snapshot and credits-scope verdicts below were forced there.)

**Quota is a decaying live gauge, not durable truth — so it is deliberately *not* a ledger
substrate.** There is **no `limits.jsonl`**, no partitioning, no `refs/notes` sync. The
**latest** snapshot per `(agent, window)` is written to a machine-local
`.cage/state/limits.json` (`Footprint.limits`) — **overwritten, never appended**. The
write side, `limits.snapshot_codex`, is called **fail-open** from `import_codex` and reads
`transcript._codex_rate_limits(rec)`: the `rate_limits` block is a *sibling* of
`payload.info` (probed against a real rollout — `primary`/`secondary` windows; observed
`window_minutes` 10080=weekly and 43200=monthly, labels derived from the size, not assumed).
A renamed/missing/non-numeric block yields **no snapshot and no error**.

**Credits are `estimated`, never measured, token-based providers only.** A per-model
`[credits.<provider>."<model>"] per_mtok` multiplier (policy — the economics layer) drives
a single tokens→credits dispatch (`credits.py`, the `convert.saved_usd` analogue):
credits = tokens × per_mtok ÷ 1e6. **No active rows ship** — only a commented example —
because the precise per-token rates aren't published and a wrong number is worse than none;
the operator opts in from their provider dashboard. Match is **exact model-id only** (no
family fallback — a borrowed estimate is a *different* wrong number); an unknown multiplier
⇒ tokens shown, no credit number. **Kiro/Copilot credits are never fabricated from tokens**
(units-of-work ≠ token multiples) — they show "—". Every figure is tagged `estimated`,
names its source, and the view ends with a "reconcile against your provider dashboard" note.

**`cage.v1` JSON envelope.** `cage limits --json` debuts a versioned envelope —
`{"schemaVersion":"cage.v1","generatedAt":…,"command":…,"data":…}` (`render.envelope`).
`generatedAt` is wall-clock metadata; the `data` payload stays deterministic (same ledger +
policy ⇒ same `data`). Introduced for `limits` only; a wider rollout is a separate packet.

**Dedup correctness (related, additive).** `transcript._usage_to_row` no longer passes
`call_id=None` for a Claude turn with no `uuid`; it derives a deterministic id from
`(agent, session, model, tokens_in, tokens_out, cached_in, ts)` so a re-import dedupes in
`hooks.append_new` instead of minting a random id. Reproduce-first finding: **0 of 29,714**
usage-bearing real Claude turns lacked a `uuid`, so this is a defensive close of the one
random-id path — uuid-present rows render **byte-identical**. No `CALL_FIELDS`/`make_call`
change; old random-id duplicates are not healed (a `--dedupe` compaction is a follow-on).

**Invariants:** `$0`/stdlib, no network, no LLM; counts-never-content (percentages + reset
epoch only); deterministic `data` payload + reproducible ids; quota/credits live **outside**
the ledger (a state file + an on-read derive), never a row; fail-open capture; four agents
always (only Codex reports quota locally today; the others show "—").

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

### 5.1 Build-time assets — `tools/skillgen` (renders the per-host skill, $0)

The flagship `cage` skill ships four ways for the four agents — a Claude/Codex
slash-command `SKILL.md`, a Copilot `.prompt.md`, and a Kiro steering doc (plus a
generic `agents` Agent-Skills target). The *content* is the same pitch; only the
host wrapper (frontmatter shape, header, trigger framing, metering note) differs.
Hand-maintaining four files lets the wording drift. `tools/skillgen/` single-
sources them: one shared `fragments/core/core.md` body with a few `@@SLOT@@`s
filled per host from `platforms.toml`, rendered to the existing
`cage/data/skills|prompts|steering/` paths (so `cage setup` / `<agent>wire.py` are
unchanged). `python -m tools.skillgen --check` byte-diffs the render against the
committed files **and** a tracked `expected/` snapshot and is wired into CI +
pre-commit; `--bless` refreshes the snapshot.

This is **build-time only** and holds the same constitution as the engine:
stdlib-only (`tomllib`/`re`/`pathlib`/`argparse`), no runtime dependency, no
LLM/network, deterministic (same fragments ⇒ byte-identical render, LF-normalized).
Nothing under `tools/skillgen/` is imported by the `cage` package at runtime or
shipped in the wheel (the `include=["cage*"]` packaging filter excludes it). The
four-agents invariant is preserved and test-asserted — every host renders, none is
dropped. Design of record: [skillgen.md](skillgen.md).

### 5.2 Error surfacing — typed CLI error + exit-code contract (fail-open preserved)

Two error regimes, kept strictly separate. **Write paths are fail-open** (constitutional,
§5/§9): `ledger.append` returns `False`, `meter()` swallows cleanup errors, hooks
`try/except → exit 0` — a metering failure never propagates into a request/turn, and the
swallow is reachable under `CAGE_DEBUG` (no truly silent swallow). **The read/CLI boundary
is typed**: an expected, user-facing failure raises the single `CageError` ([errors.py](../cage/errors.py)),
which `cli.main` renders as a clean `error: <msg>` line. There is exactly one error type —
no hierarchy, no logging framework, no retries (stdlib-only).

The exit-code contract: **`0`** ok · **`1`** error (`CageError` or an unexpected exception —
full traceback only under `CAGE_DEBUG=1`) · **`2`** argparse usage error (stdlib default, e.g.
an unknown subcommand) · **`130`** interrupted (`KeyboardInterrupt`). `cage verify` is
report-only and always exits `0` — visibility, never a build gate. This is additive and
boundary-only: the fail-open internals are verified by tests, never rewritten.

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
cage limits [--json]          # provider quota windows (Codex) + estimated AI-credits (§3.8); --json = cage.v1
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
