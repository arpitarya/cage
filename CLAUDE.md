# CLAUDE.md — Context for Claude Code

**Cage** — a *flux*: a deterministic attribution ledger for LLM token traffic and
tool savings. In the family alongside **fux** (decisions→rules). `$0`, stdlib-only,
deterministic, independent of any AI tool.

Design of record: [the ADR set](docs/adr/README.md). Read it before changing
the substrate contract or the attribution engine.

Maintainer handoff: [work/INTERVIEW.md](work/INTERVIEW.md)
— the outgoing model's exit interview (intent, scar tissue, how to work with the
human). **Every agent maintaining this repo reads it after this file; a departing
maintainer appends its own lessons there.** It is context, never spec — where it
disagrees with this file or the plan, this file and the plan win.

**Build log: [IMPLEMENTATION.md](work/IMPLEMENTATION.md) — always maintained.** After
**every small milestone** (a green checkpoint, a commit, a phase step — not just a
release), append an entry: date · milestone · what was implemented · files touched ·
test status · next step. Create the file if absent; newest entries first. It is a
running log of *what is actually built*, never spec — where it disagrees with this
file or the plan, they win. An agent ending a work session without updating
IMPLEMENTATION.md has left the milestone unrecorded — treat that like a missing
changelog entry.

## Architecture (the one-way data flow)

```
record_call / record_receipt  →  .cage/ledger/  — ONE DIRECTORY PER PRODUCER (v0.51)
        (meter, ADR-CONSUMERS)    │   claude/ copilot/ kiro/   (agent usage, per chat)
                                  │   consumer/                (cage.meter — dual-written)
                                  │   graphify/ fux/ compress/ responsecache/  (savings)
                                  │   provenance/              (authorship, monthly)
                                  │   receipts-*.jsonl · tasks-*.jsonl
                                  │   READABLE HISTORY, no longer written:
                                  │     calls-*.jsonl (retired agents) · credits-*.jsonl
                                  │     savings/<tool>/ · provenance.jsonl · imports.jsonl
                                  │   state/imports.jsonl (capture manifest) · integrity.json
                                              ▼  derive ($0, no model)
  cage.toml (pipeline order / capture)   → report · attrib · adoption · chats
                                             · graphify · compare · estimate
                                             · calibration · why · origin
                                             · commits · commit
                                             + --scope (monorepo slice)   [--team/ledger-sync: deleted v0.50]
                                             + --export → .cage/output/<view>-<stamp>/  (stamped artifact)
```

**Cage measures token and credit USAGE, never cost** ([ADR 0011](work/archive/adr/0011-cage-measures-usage-not-cost.md)).
There is no price table, no rate card and no currency on any surface. A leftover
`.cage/prices.toml` from a pre-0.51 project is never read and never deleted — `cage
doctor` names it. Do not reintroduce pricing without reversing that ADR; its veto
condition is numbered and reopenable only by a *measurement*, never an argument.

**The v0.51 shape, and the rule that comes with it.** Every producer owns exactly one
directory under `ledger/`. **Nothing on disk was ever moved:** each migration is *stop
writing here, start writing there, read both forever*, so every legacy path still resolves.
`calls` in particular can never be fully retired — retired-agent rows (codex, 373 in one
real ledger) have no other home, and `ledger.calls` is permanent. **No built-in leg writes a
`calls` row any more.** Claude's and copilot's went in P5 (for claude the row was a second
copy of the same traffic, inflated 1.979×, that no view resolved from). **Kiro's went with
KIRO-CALLS-LEG (ratified 2026-08-15) — but its store was RELOCATED, not dropped**: kiro IDE
has no metric twin, so `tokens_generated.jsonl` is now read into `ledger/kiro/` as
`source="ide-log"` rather than losing its only reader. The rows gained by moving: as `calls`
they were spend every total had to exclude by name; as metrics they are capture-only by kind
(ADR-KIRO). `transcript.parse_calls` and its
three siblings survive as the `[sources.<name>] format` custom-source contract — a source
declaring `format = "claude"` inherits CLAUDE-DEDUP/SUBAGENT-KEY, which ADR-CONSUMERS states.
`ledger/` is a flat namespace shared by agents, consumers and tools, so a colliding tool name
is refused at write time (`paths.reserve_tool_name`).

- **Integrity** ([integrity.py](cage/integrity.py), [ADR-INTEGRITY](docs/adr/0010_integrity.md))
  — a hash chain over appended segments (`sha256(prev ‖ appended)`), **checkpointed once per
  import sweep** so `ledger.append_row` is untouched, verified by replaying the recorded
  segmentation so a change *anywhere* in a file is detectable. **Report-only, always exit 0**
  (the `cage authorship verify` precedent) — it surfaces in `cage doctor` and never refuses a
  read, blocks a write, or changes an exit code. **Two verdicts, never blended:**
  `altered-history` (a recorded prefix changed — never legitimate under append-only) and
  `damaged` (truncated, which `ledger.read` tolerates *by design*). Designed churn
  (`cursors.json`, the logs) is classified `expected`, because a report its reader learns to
  ignore is worse than none. **A lock miss marks a segment `unverified` and never breaks the
  chain** — `lockutil` proceeds unlocked by contract and must not become load-bearing.
  Detects **accident and drift, not an adversary**: whoever can write the ledger can rewrite
  `state/integrity.json`. Never read by a derived view; in `cleanup.NEVER`; excluded from its
  own hashing.

Three capture-only per-chat metrics siblings — `.cage/ledger/{copilot,kiro,claude}/`
— hold vendor-verbatim usage facts `calls`/`credits` deliberately don't widen to
carry; never priced, read by no derived view yet (their own OPEN-WORK read-surface
items).

Long-lived logs are month-partitioned (writers append to a dated shard chosen from
the row's own `ts`; readers glob + concatenate, legacy single files still read; `--since`
skips below-cutoff months). provenance.jsonl is a local buffer only — canonical storage
is refs/notes/cage-provenance, written by CI alone (ADR-AUTHORSHIP). The calls/receipts/tasks
rows likewise aggregate to refs/notes/cage-ledger (CI-sole-writer) for the team view
(`--team`, ADR-LAWS; [ADR 0001](work/archive/adr/0001-ledger-team-aggregation-notes-not-external-sink.md)
— why a git ref, not an external sink).

- **Substrate** ([schema.py](cage/schema.py)) — `make_call` / `make_receipt` stamp
  ids + validate the closed enums. Rows are plain JSON. Prompt bodies are never a
  field (counts only). Change here = change the contract; update the plan §3. Calls/
  receipts also carry an additive optional `scope` (top-level changed dir, same PII
  guard as tasks; empty = the legacy contract, ADR-LAWS); calls additionally carry an
  additive optional `project` (working-dir basename, same PII guard; empty = legacy) — a
  **recorded fact with no reader** — its `cage report --project` view was deleted in
  v0.50; the field is still stamped, deliberately distinct from `scope`'s monorepo
  axis (ADR-LAWS Law 2). The long-lived logs are month-partitioned behind
  `ledger.append_row`/`read_kind` (ADR-LAWS). Calls also carry an additive optional
  `credits` (the provider's own billed figure, verbatim) — the one additive field whose
  default is a `None` sentinel rather than zero, because absence and a recorded `0.0` are
  different billing facts (ADR-LAWS) — and `billed_with`, the id of the row carrying
  **this** row's billing when the provider computed one figure over a *group* of calls
  (REV-CREDITS defect 2). `billed_with` is a recorded structural fact, never a derived
  number, and is empty for every row that bills for itself.
- **Config file** ([paths.py](cage/paths.py) `Footprint.policy`, [ADR-CONFIG](docs/adr/0012_config.md)) — the project config
  is `.cage/cage.toml` (the policy layer). It was `policy.toml` through v0.35; the
  rename is **non-breaking** — `policy.toml` is still read as a fallback and migrated
  to `cage.toml` on `cage setup` (idempotent, non-destructive), and with both present
  `cage.toml` wins (`cage doctor` names the ignored leftover; a one-line stderr warning
  fires at load). The resolved name lives in **ONE place**, `Footprint.policy`; writers
  (`tomledit`/`policysync`) and `cleanup.NEVER` (which protects **both** names) follow
  it. Bundled default `data/cage.toml`, read-only at runtime. `cage query config-file` explains it.
- **Constants** ([constants.py](cage/constants.py)) — the *third audit layer*. Cage
  keeps its numbers in three places, never mixed: **contract** = the enums in
  `schema.py`; **policy** = user settings in `cage.toml`; **constants** = code
  heuristics not meant as config but that must be reviewable (`CHARS_PER_TOKEN`,
  `METHOD_TRUST`, `DEFAULT_CONFIDENCE`,
  `GRAPHIFY_RECEIPT_CONFIDENCE`, `SINCE_WINDOW_DAYS`,
  `PARTITION_GRANULARITY`, and the
  ledger-size threshold `LEDGER_WARN_BYTES` — derived from `LEDGER_ROW_BYTES` ×
  `LEDGER_HEAVY_ROWS_PER_DAY` × `LEDGER_WARN_MONTHS`, a policy-preferred fallback like
  `DEFAULT_CONFIDENCE` (`cage.toml [ledger] warn_mb` wins)). `compress`/`prices`/
  `matrix`/`attribution`/`origin`/`ledger`/`graphifymeter` import from here.
  `DEFAULT_CONFIDENCE` is a *fallback ladder* — a row's own `confidence` wins. The
  third-party shims (`fux/cage_receipt.py`, graphify) keep a local `len/4` copy
  because they're zero-dep; it's an intentional duplicate of `CHARS_PER_TOKEN`.
- **Explain** ([explain.py](cage/explain.py) engine,
  [explain_data.py](cage/explain_data.py) registry) — `cage query` answers both
  "how is X calculated" (`kind="calculation"` — formulas interpolate **live**
  values from policy + constants; reorder `[tools] order` ⇒ the printed pipeline
  changes, never a hard-coded literal) and "how does cage work"
  (`kind="concept"` — `overview`/`data-flow`/`metering`/`attribution`/
  `matrix-concept`/`method-law`/`receipts`/`savings-axis`/`determinism`/
  `pii-safety`/`numbers-layers`; structural facts interpolate live too — ledger
  paths from `paths.Footprint`, pipeline order from `policy.tool_order(pol)`,
  agent surfaces from `agents.SURFACES`, subcommand count from the CLI parser —
  and every concept entry carries a `code_refs` + `plan_ref` anchor). Matching is
  stdlib token-overlap across both kinds; **no LLM, no network** (cage law). No
  match ⇒ suggest closest ids, never guess. `--list --kind concept|calculation`
  filters; `cage --help` groups subcommands and points at `cage query`.
- **Ledger** ([ledger.py](cage/ledger.py)) — the only mutation is append; reads
  tolerate a truncated tail. Everything else derives.
- **Meter** ([metering.py](cage/metering.py)) — the library adapter. **Fail-open**:
  a metering error must never propagate into a request path. The public name is
  `cage.meter` (a context manager); the *module* is `cage.metering` — keep them
  distinct or the package attribute shadows the submodule. The push path resolves its
  sink through `paths.canonical_ledger()` (the ONE resolver push and pull share,
  capture-architecture §3.1) — never `resolve_root` directly — and stamps a non-PII
  `route_key` (a hash of the resolved ledger-root path, never a basename; additive/
  optional, never in an id) on pushed receipts so a read can reclaim a stray saving by
  exact key. **Capture observability (F6):** an always-on `state/capture.log` breadcrumb
  (`cage/capturelog.py`, one line per agent per real import run — counts only, never
  read by any derived view) proves capture ran at all; a `CAGE_DEBUG`-gated
  produce/skip log at every receipt push site (graphifymeter/record_receipt/
  responsecache/compress) makes a silently-skipped savings receipt diagnosable.
- **Attribution** ([attribution.py](cage/attribution.py))
  — the differentiator (ADR-LAWS). Marginal-by-fixed-order; a reconstructed
  counterfactual cell is `modeled`/`estimated`, never `measured` (only the recorded
  run is an invoice). `cage demo` must keep reproducing the plan's §4.4 tables.
- **The Tier-1 human axis is GONE (v0.36)** — `human.py`/`humanview.py`/`trend.py`/
  `attention.py`, `cage human`, `cage insights trend`, `matrix --human`,
  `calibration --human`, `[human.*]`, `CAGE_HUMAN_RATE`, `IDLE_CAP_MINUTES`, the
  `gap_ms` call field and the `minutes` unit were all removed together, substrate
  included — a clean amputation, reconsidered from scratch after the release, never a
  `# v2:` stub. **Do not reintroduce any part of it without a proposal doc.** Two
  things survive and must not be confused with it: (a) provenance `origin="human"`
  ([origin.py](cage/origin.py), `schema.ORIGINS`) is *authorship*, a different
  question and a different enum; (b) `cage task outcome` never belonged to the
  axis — it sat in the `human` command group by filing accident and moved to the `task`
  group (its sibling `cage task quality` was money and went with ADR 0011); `outcome` is the **task-close verb** the whole
  cost-impact surface (`compare`/`estimate`/`calibration`) depends on. **Old ledgers
  still read**: a pre-0.36 `gap_ms` call or `tool="human"`/`unit="minutes"` receipt
  parses fine and is excluded from money views by `report._is_legacy_human`, with the
  exclusion **counted and footnoted** on `cage insights chats` (it was `cage report`
  until v0.50) — silently dropping it from a total was the one option ruled out. `cage query savings-axis` explains it;
  `tests/test_legacy_ledger.py` pins it. **A v2 exists and it is a different question
  (v0.43).** `cage insights commits` / `commit <sha>` rebuilt agent-vs-human **per
  commit**, and nothing amputated came back: no rate, no USD, no `gap_ms`, no `minutes`
  unit, no derived attention, no `cage human`. What it adds is *line-level evidence* and
  a human that is an explicitly-labelled residual. **The standing guard is the
  load-bearing part: no USD, rate or valuation appears on any authorship surface** —
  structurally, not by policy (`commitview.py` imports no pricing module, asserted by AST
  in the suite). Hours exist only as an attestation (`cage task time`, rendered `*`) or a
  guarded `~` estimate that **refuses four ways** rather than print fog — including when
  no agent span joined, where `wall − nothing` would render the raw commit gap as effort.
  That last refusal is v1's exact mistake, caught in this build by smoking the real repo.
- **Task record** ([tasks.py](cage/tasks.py)) — `tasks.jsonl`, one row per task
  (last-write-wins by `id`), git-snapshotted at task close (SessionEnd / `cage
  outcome`). **Shelled out to git, never imported; fail-open** (non-repo/detached ⇒
  omit fields). PII guard: SHA + diff *counts* + top-level dirs only — never the
  commit message, author identity, or file paths.
- **Provenance (authorship attribution)** ([schema.py](cage/schema.py) `make_provenance`,
  [originrecord.py](cage/originrecord.py) write side, [origin.py](cage/origin.py) read
  surface, [notessync.py](cage/notessync.py) distribution, [verifycmd.py](cage/verifycmd.py))
  — *who wrote which files in which commit* (ADR-AUTHORSHIP), a fourth append-only file
  (`provenance.jsonl`) answering a different question than calls/receipts/tasks. Its
  own closed enums, deliberately separate from `METHODS`/`UNITS`: `method ∈
  {hooked, transcript, heuristic}` (ranked by `constants.PROVENANCE_METHOD_TRUST`,
  a parallel ladder to `METHOD_TRUST`) and `origin ∈ {human, agent,
  agent-autonomous, unknown}`. **`unknown` is a read-time default, never a written
  row** — a sha with no signal has no row at all; `origin.explain` derives unknown
  from absence. `origin="human"` is reachable only via explicit attestation
  (`cage authorship origin <sha> --attest human`), always paired with `method="heuristic"`
  (enforced at `make_provenance` construction). Captured at `SessionEnd` from the
  transcript ([transcript.py](cage/transcript.py) `parse_provenance`); the
  hook-based `post-commit` capture path was removed in the hookless rebuild, so
  `hooked` rows are legacy-only and new capture is `transcript`. The local jsonl is
  a **buffer only**; canonical storage is `refs/notes/cage-provenance`, merged by row id
  (never overwritten) and **written only by CI** (`CAGE_NOTES_WRITE=1`) — a dev
  machine's `cage authorship notes-sync` defaults to a dry-run print. `cage authorship verify` is
  **report-only and always exits 0** (never a CI gate). Widens the PII surface to
  repo-relative file *paths* (vs. `tasks.jsonl`'s top-level-dirs-only) — justified
  in plan §3.5 — but counts-never-content still holds: no diff bodies, no commit
  messages, paths validated repo-relative at construction time. The line-match counts
  are omitted at 0 with **one deliberate exception**: `residual_lines` is written
  **including 0** (`schema.PROVENANCE_ZERO_BEARING_COUNTS`) because **presence of the key
  is the version gate** for `agent%` — absent means the row predates the count, a
  recorded `0` means everything matchable matched the agent, and frozen rows are never
  backfilled.
- **Authorship, per commit** ([linematch.py](cage/linematch.py) matcher,
  [commitjoin.py](cage/commitjoin.py) windows + call join,
  [authorcapture.py](cage/authorcapture.py) the pass,
  [commitview.py](cage/commitview.py) the views;
  [ADR 0008](work/archive/adr/0008-line-match-authorship-counts-persisted-content-transient.md),
  FORMULAS §2.14) — the agent-vs-human axis, rebuilt at a unit you can `git show`.
  **Never observe the human; observe the agent precisely and let the human be the
  residual.** A Claude transcript records the exact text an `Edit`/`Write`/
  `MultiEdit`/`NotebookEdit` block proposed; at import that text is matched
  **transiently, in memory** against the added lines of the commit whose *window*
  contains the edit. **Only counts persist — no line body and no line *hash*** (a hash
  is a membership oracle over the source; it is named because it is the obvious "safe"
  shortcut and is not one). Five additive-optional provenance counts, omitted at 0, so
  `schema_ver` stays 1. **Windows, never `HEAD`-at-import**: commit *i* owns
  `(ts_{i-1}, ts_i]`, upper bound inclusive, and work after the newest commit is left
  **unrecorded** this sweep — idempotency picks it up exactly once when its commit
  exists, and guessing a commit that does not exist yet would be wrong forever.
  Every bound and probe is in **ONE UTC normal form** (`YYYY-MM-DDTHH:MM:SSZ`,
  sub-seconds truncated; `commitjoin.norm_ts`), normalized at `Window` construction so
  a raw `%cI` bound cannot be built — git renders each commit in the *committer's own*
  offset, and the compare is a string compare. **Seconds, not milliseconds:** `%cI`
  has no sub-second, so finer precision would push an edit made inside the commit's
  own second out of it and break the inclusive bound
  ([finding](work/regression/2026-08-02-finding-commit-window-timestamp-skew.md)).
  **FOUR line buckets, never three, and none is redistributed:** `agent` (matched a
  proposal — read from the row, *never* re-matched at render time) · `human~` (in a
  file that session *did* propose, matching nothing — a real human tweak, `estimated`
  by construction) · `unattributed` (in a file **no** session proposed: a person, a
  vendored tree, or generated output — cage does not guess) · `unknown` (sub-gate or
  binary). The fourth bucket exists **because it was measured**: a single `human`
  bucket printed 76.6% on cage's own repo, 89% of it one commit of generated JSON
  ([dogfood](work/regression/2026-08-02-p1-authorship-dogfood.md)) — a residual
  presented as a finding is the v1 mistake in new clothes. **Coverage is per-agent and
  stated** (`authorcapture.COVERAGE_GAPS`): claude only; copilot and kiro persist no
  edit payload and render `—` with the reason, never `0%`. The call→commit join reuses
  `taskgroup.join_rows` (task-id first, window fallback) and **never forks a second
  join**; a task closed on a **dirty tree** is not trusted (its sha is the *prior*
  commit), and a call with **no `project` stamp is *unconfirmable*, not adopted** —
  otherwise a global ledger would pull every other repo's spend onto these commits.
  **`[authorship] capture` / `CAGE_AUTHORSHIP` is its own consent switch**, separate
  from `[capture] enabled`: this is the one path that reads a repository's *diffs*,
  and metering spend is a different permission from reading code. **The list view's
  read is bounded by the row cap** (`commitview.summarize(limit=…)`, COMMITS-WINDOW):
  every row costs one `git show` subprocess, so the text path reads only the newest
  `COMMITS_DEFAULT_ROWS` commits and footnotes the rest as *not read*; `--csv`/`--json`
  stay complete, `--all` lifts it, and the detail view is never capped. A default
  relative `--since` was rejected — a wall clock in the default path. `cage query
  agent-authorship` explains it.
- **Usage-impact surface** ([taskgroup.py](cage/taskgroup.py), [compare.py](cage/compare.py),
  [estimate.py](cage/estimate.py), [calibration.py](cage/calibration.py)
  — the usage-impact roadmap) — the closed-task join
  (task-id first, session-window fallback; overlaps → smallest task id) yields
  *observed* stack signatures (`human` excluded; empty ⇒ `agent-only`).
  **⚠ THE WHOLE USAGE-IMPACT SURFACE WAS DELETED IN v0.50 (SURFACE-CUT)** — `compare`,
  `estimate` and `calibration` are gone, along with the `INSUFFICIENT DATA` refusal and
  the `MIN_COMPARE_N`/`MIN_ESTIMATE_N` blocking gates as *user-facing* behaviour. What
  survives is the **writer**: `tasks.jsonl` still records outcomes and the additive
  `est_*` fields, and `taskgroup.join_rows` is still the one closed-task join.
  `MIN_COMPARE_N` gated the fleet study until STUDY-CUT and is now read by nothing —
  it stays only because ADR-GRAPHIFY's veto condition cites the number.
  **Nothing reads the task-grain fields**
  (UNREAD-FACTS). A deleted reader never licensed deleting its writer — see the rule
  below. Task `label` (via `cage task outcome
  --label`) is one validated token, never a path or free text. Diagnostics: `cage
  doctor --bundle` ([doctorbundle.py](cage/doctorbundle.py)) writes one redacted,
  counts-never-content archive; every capture-path swallow-site logs under
  `CAGE_DEBUG=1` — audited by `tests/test_debug_coverage.py` ("fail-open but never
  silent" is tested, not aspirational). Validation harness: the fixture corpus
  `tests/fixtures/transcripts/` (4 agents × cli/vscode, exact expected rows,
  VS Code stand-ins flagged `UNVERIFIED-FORMAT`) + `python -m tools.dummyrepo`
  (S1–S18 scenario runner; S10 retired with the human axis, S9 with the fleet study;
  build-time only, never in the wheel).
- **⚠ THE P5 FLEET STUDY WAS DELETED WHOLE IN v0.51 (STUDY-CUT)** — the six `cage study`
  verbs, `study.py`, `machine.py`, the phase markers in `ledger/study.jsonl`, the opaque
  per-machine id in `state/machine.json`, the additive **`machine` row field** every
  `calls`/`receipts`/`tasks`/consumer-metric writer stamped, the one-file zip bundle, and
  the `cage import BUNDLE` merge that read it. **Cage no longer aggregates across
  machines by any route.** Two things survive on purpose and must not be mistaken for
  debt: rows already carrying `machine` still parse and are simply unread (append-only —
  the recorded past is never rewritten), and **`machine.json`/`study.jsonl` stay in
  `cleanup.NEVER`** so a future `state/` class cannot eat what is already on disk.
  `policy.import_before_export` and its `[capture]` key also survive **unread** — their
  last surface was the bundle export (UNREAD-FACTS). Do not reintroduce a cross-machine
  axis without a proposal doc; the `machine` field in particular is a substrate change.
- **CSV output (ADR-CLI)** ([csvout.py](cage/csvout.py)) — `--csv` on
  `cage insights chats`/`graphify`/`commits`/`commit` and `authorship summary`
  (the raw-row CSV export and
  `exportcmd.RAW_CSV_FIELDS` went with `cage data` in v0.50; `study report` and the
  fleet bundle went with STUDY-CUT). One shared
  data structure per view feeds text AND csv (`render_csv` beside each
  `render_*`) — never compute twice. LF pinned (`lineterminator="\n"` +
  `newline=""` writes), RFC-4180, method/match tags are columns, refusals/
  caveats/UNPRICED survive into rows. CSV is one-way REPORTING — never an import
  source, and since STUDY-CUT it is the only export shape cage has. MCP mirrors it (`format: csv` on
  report/attrib/roi).
  **Text-output contracts: the golden fixtures** (`tests/fixtures/goldens/`,
  asserted by `tests/test_output_spec.py`) are the per-command, per-state output
  contract. Change a rendered shape ⇒ re-bless the golden (`CAGE_BLESS_GOLDENS=1
  pytest tests/test_output_spec.py`). (The generated `docs/cli-output-spec.md` and
  its `tools/docgen` generator were removed in the hookless rebuild; the goldens
  remain the contract.)
- **OTel GenAI export** ([otelout.py](cage/otelout.py), plan/handoff
  `work/archive/v0.39-otel-export.handoff.md`) — **DELETED in v0.50 with the `data`
  group (`otelout.py` is gone).** Kept below as the record of a mapping that was
  carefully chosen and may be wanted again; it describes no live surface.
  It was `cage data export --otel`, a one-way REPORTING format (never an import source;
  the re-importable fleet bundle it was contrasted with is gone too — STUDY-CUT). Calls map to `gen_ai.system` / `gen_ai.request.model` /
  `gen_ai.usage.input_tokens` / `output_tokens` / `gen_ai.client.operation.duration`
  (omitted, never a fabricated zero, when `latency_ms` is unknown). **The GenAI
  semantic conventions are pre-stable** (own repo, no 1.0, names can still change) —
  the targeted version is pinned in `constants.OTEL_SEMCONV_VERSION` and stamped in
  every document's `cage.meta` block; a spec bump is a deliberate, changelog'd
  change, same discipline as `prices_version`. **The pin states what it pins**
  (OTEL-SEMCONV-PIN, 2026-08-11): `1.42.0` is the *last main-repo release that defined
  `gen_ai.*`* — on 2026-06-12 they were deprecated there and moved to
  `open-telemetry/semantic-conventions-genai`, which carries **no tagged release** and is
  `Status: Development` throughout, so cage stamps the repo and the maturity rather than
  inventing a version for it; the pin re-points when that repo cuts its first tag. The
  provider attribute is `gen_ai.provider.name` — `gen_ai.system` was renamed in semconv
  v1.37.0, *before* the pinned release. Emitting **both** was rejected: a consumer that
  sums rather than coalesces would double-count. **Receipts/savings have no GenAI
  equivalent** — cage-namespaced under `cage.savings[].cage.*`, never an invented
  `gen_ai.*` name; `cage.saved` is GROSS, `cage.saved_usd` prices through the same
  receipt's own `unit` (named in `cage.unit`, converted by nothing — there is no
  `cage.saved_usd` since ADR 0011); `cage.method` always survives. `dependencies
  = []` unchanged — stdlib `json` only, no OTel SDK. `cage query otel-export`
  explains it.
- **Adoption** ([adoption.py](cage/adoption.py), FORMULAS §2.12) — `cage insights
  adoption`: do the agents you wired actually *invoke* the tools? A derived view whose
  entire value is a boundary between three unknowns — **never invoked** · **invoked, cage
  filed nothing** · **invoked, cage cannot say by whom** — so it is **two halves that are
  never blended**. **A · invocations**: the usage breadcrumb, exact but **agent-blind** (a
  usage row is `ts · op · args_hash · exit · ms · outcome · route` — there is no `agent`
  field); per-outcome counts are **read** from the recorded `outcome`, never re-derived
  from the receipts. **B · per-agent**: savings rows joined to `calls.agent` — linked
  `call` id first (exact), else a `session` **exactly one** agent's calls carry (a shared
  session stays unknown, never resolved to an arbitrary name). Agent-unknown splits by
  cause and is **never an "other" bucket, never attributed by timestamp proximity**:
  `no-link` is structural (the interceptor is a subprocess and stamps an empty session on
  purpose), `unjoined` is a capture gap. **"Never invoked" is never asserted, and has two
  strengths** — *no evidence of invocation* is sound only at 100% attribution, else the
  claim drops to *no savings row attributed to them*, because an unattributed row could
  be theirs. **An empty half B renders its refusal, never vanishes** (suppressing it would
  make *cannot attribute* read like *no answer exists*). **No currency anywhere** — this
  is the first reader of the `state/` usage log and the diagnostic-only invariant is
  re-asserted from it (`tests/test_adoption.py`). Surface is deliberately not a dimension
  (K4). CSV/MCP/`--since` like report/attrib/roi; `cage query tool-adoption` explains it.
- **Chats view** ([chats.py](cage/chats.py), FORMULAS §2.13) — `cage insights
  chats`: one row per chat, titled where the store has a title. Pure derive over
  `calls`, grouped by `(agent, surface, session)` — the same bucket key the import
  manifest uses. **The law amendments are now TWO, and both are scoped**: `manifest.py`'s
  "never read by a derived view" contract is read for a **title** (display label only),
  and `provenance.jsonl` is read for **counts** by the `agent%` column. Both hold on the
  same terms — deleting either file moves **zero** numeric cells (pinned by
  `tests/test_chats.py`). Kiro-IDE's constant session id
  already collapses every run into one row (`kiro (no session identity)`, never a
  fabricated per-chat identity); kiro-CLI conversations are `credits` rows and don't
  appear here. Top-20 by `tokens_in`, `--all` lifts it (footnoted cut, no silent
  caps); CSV never truncated. Local-only by construction — no `--team`, no MCP tool.
  · **`agent%`** is per chat the share of *evidenced lines in files that chat touched*
  that matched the agent's own proposals — `agent_lines / (agent_lines + residual_lines)`
  over the provenance rows sharing `(agent, session)`; **read, never re-derived** (no
  matcher, no git at render), so it can never disagree with the commit view. It
  **refuses three ways** and `—` is never 0% (coverage · no landed evidence · pre-upgrade
  rows), while a *measured* `0%` renders `0%`. Scope is not a share of the chat's work —
  `unattributed` is commit-scoped and outside the denominator; per chat there is no diff
  to clamp against, so **the commit view stays the arbiter for any single sha**. No
  USD/rate/minutes ever touches it. · **No `premium` column** (COPILOT-PREMIUM-DEAD,
  2026-08-11): it is `floor(credits)`, so it stood beside `credits` as a lossy duplicate
  that printed `0` for every row cage writes. The *field* is untouched and still in the
  payload, so `--json` keeps the recorded fact — precision in the data, brevity in the
  display. `cage query chats-view` explains it.
- **Graphify per-chat view** ([graphifychat.py](cage/graphifychat.py), FORMULAS
  §2.15) — `cage insights graphify`: one row per chat — recorded tokens (the
  with-graphify world), the modeled without-graphify counterfactual (`tokens +
  Σsaved`), and the GROSS saved share. Reuses `chats.summarize` verbatim for the
  chat universe and joins `ledger.savings` (`tool="graphify"`) onto it by
  `session` alone — a savings row carries no agent field at all. `tokens` is a
  fact independent of graphify use and always renders; only the graphify-derived
  cells (`gfx uses`/`without gfx`/`saved`/`saved%`) dash for a zero-receipt chat,
  and only under `--all-chats` (the default view is receipt-bearing chats only).
  A measured `saved == 0` still renders `0%`, never a dash. `saved` is never
  clamped — a negative value (and the `without gfx` it produces) renders
  honestly. Two tallies never redistribute into a chat row: `unassignable` (the
  native shim's honest-empty `session=""`, GC3) and `unmatched` (a savings
  session joining no chat bucket). Tokens-only — no `--usd` (the v0.36
  no-blend law). `cage query graphify-chats` explains it.
- **Display honesty** ([display.py](cage/display.py)) — the ONE display-context
  home (plan Phases 1+2). `Display` carries the resolved presentation switches
  (`usd`: tokens are the default, dollars opt-in — flag > env `CAGE_USD` >
  policy `[display] usd`; `all_columns`: the signal-gating escape hatch);
  `Footer` collects the below-table lines (footnotes/caveats/⚠/gating/advice),
  dedupes them, and renders one fixed-order block. `report`/`overview`/`matrix`
  thread it; gating/dedupe logic lives here once, never per-view. Presentation
  only — pricing always computes underneath, money-native views never consult
  it, and CSV never gates (`—` never enters CSV data; `$0.0000` is always a
  real zero). `constants.IMPORT_STALE_HOURS` gates the `last import` advice line
  (policy `[capture] import_stale_hours` wins).
- **View export + the run stamp** ([viewexport.py](cage/viewexport.py),
  [runstamp.py](cage/runstamp.py), compare doc
  [view-export-and-run-stamp](work/compare/view-export-and-run-stamp.compare.md);
  `cage query view-export`) — `--export` on **every** `cage insights`
  leaf (17 views) writes the rendered view to disk: bare ⇒
  `<ledger>/.cage/output/<view>-<stamp>/` holding **every format that view has** (text ·
  csv where it owns a `render_csv` · json), a path with a known suffix ⇒ that exact file
  in that format, any other path ⇒ a per-run folder under it (**a directory destination
  always gets one** — two runs of a view must never clobber each other). A format a view
  cannot produce is a **typed refusal**, never an empty file (an empty CSV reads as *no
  rows*). **`runstamp` is the ONE place a wall clock reaches a read surface**, and it is
  admitted on terms that leave the determinism law exactly as strong: the stamp is never
  an input to a cell (delete every stamp, no derived figure moves), **stdout stays
  clock-free by default** so the goldens and `test_floor` keep pinning a surface no flag
  can perturb (`tests/test_view_export.py::test_export_never_changes_stdout` is the
  binding gate), and it is **mandatory in an artifact** with no suppression flag —
  a file outlives its terminal, and a number with no as-of is unreadable. `--stamp` is
  the opt-in stdout half. One block, three renderings (`# cage: k=v` for text/CSV, a
  `cage` object for JSON) — never re-worded per format; it names the DATA filters and
  never the presentation switches. `CAGE_RUN_STAMP` pins the clock. **`--csv`/`--json`
  are untouched, on stdout AND to a path** — a `--csv PATH` is a stream redirected to a
  file, `--export` is an artifact, and only the artifact grows the block; a preamble in
  `--csv` would break the pinned column contract. `cliutil.emit` is the ONE chokepoint
  (export → then exactly one of csv/json/text) — never a second per-handler csv branch.
  **`.cage/output/` is deliberately NOT `.cage/out/`**: that one *was* `cage data
  serve`'s docroot, with a stdlib `http.server` pointed straight at it. **The server was
  deleted in v0.50 and the separation is kept anyway** — a directory that was once
  web-served is the wrong place to write artifacts, and re-merging them would be
  invisible until something served it again. **No cleanup class prunes
  it** — cage never deletes an artifact it wrote (OUTPUT-GROWTH carried the
  volume-gated reopen and was closed unactioned 2026-08-12, no size number ever
  measured: [archive/v0.49-output-growth.item.md](work/archive/v0.49-output-growth.item.md)). Bare `cage` (the overview) has **no** `--export`: a
  root-level optional-value flag would swallow the following subcommand. Adding a view =
  `_export_flags(<parser>, "<verb path>")`; the fan-out is gated by
  `test_every_report_and_insight_is_exportable` — **wire it in, never relax the set.**

## Must-Know Rules

- **No behaviour change lands without its ADR updated in the same change (Arpit,
  2026-08-14).** The ADRs are the durable *why*, and they are kept **up to date**, not
  reconciled later. Update the owning record when a change alters behaviour a record
  describes (a parser, a store, a routing decision, a schema field, a unit, a rendered
  refusal, an interceptor behaviour, a CLI command or flag), makes/reverses/narrows a
  decision **including one taken by deletion**, or invalidates a veto condition, a stated
  gap, or a *deliberately not taken* item. **A change that touches no recorded decision
  says `no ADR affected` out loud** — that sentence is the rule working, not an exemption
  from it, because a rule demanding an edit per keystroke decays into ritual edits and a
  doc nobody trusts is worse than none. **Which record owns which module is a table, not
  a judgement call** ([docs/adr/README.md](docs/adr/README.md) *Which record owns what*),
  and `tests/test_adr_ownership.py` fails when a module in `cage/` is claimed by no
  record — precisely the moment a new decision is being made with nothing to hold it.
  **A stale ADR is a defect of the same class as a missing changelog entry.** The half no
  test can see — *was the record edited in the same commit?* — is carried by review, and
  the test says so rather than implying coverage it does not have.
- **A reader may be deleted; the writer it read is a separate decision (SURFACE-CUT,
  2026-08-14).** Capture is cheap, append-only, and irreversible to lose. When a view
  goes, the fields it read **stay recorded by default**, and the gap is *filed* rather
  than tidied away — v0.50 left six such recorded-but-unread facts (UNREAD-FACTS), and
  the tempting cleanup, stopping their writers, would silently narrow what any future
  view could ever answer. **Stopping a writer needs its own justification, its own ADR
  update, and its own line in `work/OPEN-WORK.md`.**
- **Triage before work: a human-blocked queue STOPS the session (Arpit, 2026-08-12).**
  Before doing anything, read `work/OPEN-WORK.md` and ask: *is any item agent-closable
  right now?* If everything remaining needs Arpit — his hands, a ratification, a
  decision, a push — the session's **first** output is the blocked-on-Arpit list in
  ≤3 lines, and then it stops. No invented scope, no doc polishing, no "discovered
  work" to fill the hours. "Next: Arpit reviews…" as the *closing* line of a long
  session is the failure mode this rule exists to prevent; as the *opening* line it
  is the rule followed. His time and tokens are money — cage itself can price a
  session — **but see the `Cost:` rule below: the command that did it was deleted in
  v0.50**; say the cost out loud rather than running long against a
  blocked queue. Applies to Cowork and Claude Code alike.
- **Probe before claiming impossibility (Arpit, 2026-08-12).** Any claim of the form
  "item X needs hardware/tooling that isn't here" must cite a dated row in
  [work/MACHINE.md](work/MACHINE.md); if the row is missing, the probe is the next
  action, not the assumption. Born of a real failure: nine queue items were called
  hardware-blocked while Copilot and Kiro were installed the whole time.
- **Two strikes → a gate (Arpit, 2026-08-12).** A failure class the WORKLOG records
  twice becomes a test or mechanical gate in the same change that records the second
  occurrence. The OPEN-WORK header went stale **seven times** before
  `tests/test_queue_honesty.py` existed; the lesson tax is capped at two from now on.
- **Every WORKLOG entry ends with a `Cost:` line (Arpit, 2026-08-12)** — the session's
  spend, measured with cage itself. **⚠ The command this rule named, `cage report`, was
  deleted in v0.50 (SURFACE-CUT) and the rule has no replacement source yet**: the
  surviving reader, `cage insights chats`, is per-*chat* and cannot isolate a session.
  Until one exists, `Cost: unmeasured — <why>` is the honest entry and the naming of a
  dead command is itself the open item (UNREAD-FACTS).* Waste that is priced gets stopped;
  waste that is prose gets repeated.
- **Cage measures usage, never cost** ([ADR 0011](work/archive/adr/0011-cage-measures-usage-not-cost.md)).
  No price table, no rate card, no currency on any surface, and **no conversion between
  units in either direction** — tokens↔credits↔anything. `tests/test_usage_only.py`
  AST-scans every module for a returning currency identifier or a rendered `$N` and fails
  the suite. Reintroducing pricing is an **ADR reversal, not a feature**: the veto
  condition names the one thing that reopens it (a provider exposing a per-request billed
  amount in a store cage already parses, on ≥80% of rows, written up in `work/research/`
  first) and rules out the rest by name.
- **A basis change is a fixture migration, and the tests will not tell you politely.**
  When `ledger.spend()`'s resolution changes, every test seeding the old basis starts
  asserting over an *empty* ledger — it keeps passing while pinning nothing. Found the
  hard way retiring the spend cutover (~80 tests). `tests/conftest.py::metric_twin` is
  the ONE helper that dual-writes a metric row beside a `calls` row, exactly as real
  capture does; use it rather than a per-file copy.
- **$0 / stdlib only** — `dependencies = []`. ML is opt-in extras (`[embeddings]`,
  `[ml]`), never imported on the default path.
- **Fail-open everywhere on the write path** — `ledger.append` returns `False`, it
  never raises; `meter()` swallows errors in cleanup. Metering is best-effort.
- **Determinism** — no clocks/random in derived views; ids carry the only entropy.
  Same ledger + same policy ⇒ same tables. Tests assert exact plan numbers.
- **`method` is sacred** — never let a projection read as `measured`. Tag every cell.
- **Usage rows are diagnostic-only** ([usagelog.py](cage/usagelog.py)) — one row per
  graphify run in `state/`, never priced and never read by a derived money view (like
  all `state/`, they cannot move a reported number — tested byte-identical); `args_hash`
  never carries the query text.
- **Three agents, always** — Cage supports **Claude Code · Copilot · Kiro**
  (`agents.SURFACES = ("claude", "copilot", "kiro")`). Never drop or silently
  break one: every wiring/read surface (`agents.py`, `mcpserver.py`, `cage
  setup`, the skill/steering data) must keep all three first-class, and new
  surface work fans out to all three. This is a product invariant, not a
  default — Codex was removed completely in v0.33.0 (a product/scope decision,
  not a capture-quality one — see work/archive/*-codex-removal.handoff.md).
- **A renamed or removed verb is a wiring migration, not just a CLI change.**
  Renaming/removing a top-level verb must add an entry to `verbmap.REMOVED`
  ([verbmap.py](cage/verbmap.py)) so the old spelling prints a direction instead of
  exiting 1 silently — and it must be swept everywhere the old spelling could still be
  hard-coded: every wire module, `install.sh`, `justfile`, and `tools/dummyrepo`. `just demo` and `install.sh` shipped broken from v0.28.0 to
  v0.32.0 because the rename touched the CLI and nothing else, and nothing checked.
  `tests/test_cli_tiering.py` grep-gates source, assets, **and dev tooling**
  (`justfile`/`install.sh`) for a stale `cage <old-verb>` spelling — treat a failure
  there as a wiring bug, not a lint nit. See the wiring-liveness paragraph above: a
  verb deleted outright (never added to `REMOVED`) is the harder case the live-parser
  detector exists to catch. **It is also a documentation migration:**
  [docs/adr/0003_cli.md](docs/adr/0003_cli.md) is the complete command reference and
  `tests/test_cli_reference.py` gates it against the live parser, so the rename lands
  in the doc in the same change or the suite goes red.
- **`paths.py` splits on contact, never wholesale.** The next change that touches one
  of its concerns moves that concern out *with* it. Named seams: `routing.py`
  (`kiro_routed` + `canonical_ledger` + `resolve_root` precedence) · `logsources.py`
  (registry + `resolve_log_sources` + drift) · `agenthomes.py` (`claude_home` /
  `copilot_home` / `kiro_home` + the doctor-bundle env allowlist) · `footprint.py`.
  Pure moves with re-exports from `paths` — no behaviour change, no import breakage.
  **A deletion and a move never share a diff** (CODEX-OUT's verdict): if the touching
  change is a removal, do the removal, and leave the seam for the next one.
- **`[meta] cage_version` is the package version, always** — it is *printed* by
  *copied into every newly scaffolded project*, so a stale literal propagates. Derive it from `cage.__version__` (the `manifest.py` pattern), never
  hand-maintain it; a project's existing stamp is history and is never rewritten.
  **`policy_version` is deliberately NOT coupled to the release** — it is a content
  counter driving the `cage policy sync` recommendation, and bumping it per release would
  tell every project its defaults are stale when nothing changed.
- **Every release updates the changelog** — bump `__version__`, add the full release
  notes to `CHANGELOG.md` (newest first, don't skip versions) and a **1–2 line**
  summary to the README "What's new" section — which keeps **only the latest
  version's entry** (replace, don't append; the README points at `CHANGELOG.md` for
  history — full prose lives in the changelog), and refresh the
  "N tests passing" count in the README `$0` section + this file's `just test`
  comment. A shipped version with no changelog entry is a release bug. Nothing to
  hand-edit for `[meta] cage_version` — it derives from `__version__` at read time
  (`policy._bundled`). The `tests/test_prices_split.py` drift-guard this line used to
  name went with the prices file (ADR 0011).
- **Never publish from local. Every release ships a GitHub release, and the GitHub
  release *is* the publish trigger.** The one true release flow: bump `__version__`
  + changelog, commit + push `main`, tag `vX.Y.Z`, push the tag, then
  `gh release create vX.Y.Z` with notes drawn from the README "What's new" entry.
  Creating that GitHub release fires `.github/workflows/publish.yml` (`on: release:
  published`), which builds and publishes to PyPI via **OIDC trusted publishing**
  (no stored token, nothing to leak). **Do not run `uv publish` / `twine` / `cage`'s
  own publish by hand — ever.** The CI pipeline is the sole publisher
  (`skip-existing: true` makes it idempotent). A version on PyPI with no matching
  GitHub release/tag — or published from a laptop — is a release bug. `uv build`
  locally is fine for a smoke check, but never upload the artifacts.
  The same trigger runs the independent `build-pyz` → `smoke-pyz` (3-OS) →
  `release-pyz` chain that attaches `cage.pyz` + `SHA256SUMS` to the release —
  it must never gain a `needs` link to (or from) `publish-pypi`, and the pyz is
  CI-built only (local `python -m tools.buildpyz` / `just pyz` is a smoke
  check, never an upload). `cage --version`/doctor label a zipapp run
  (`(zipapp)`); bundled data reads via `paths.bundled_data()`
  (importlib.resources Traversable — never `Path(__file__)`), so it works from
  inside the archive; `paths.distribution()` is the detector.
- **Two error regimes, never mixed.** Write paths stay **fail-open** (return `False` /
  swallow, traceable under `CAGE_DEBUG`, never raise into a request/turn). The read/CLI
  boundary is **typed**: an expected user-facing failure raises the single `CageError`
  (`cage/errors.py`) → `cli.main` renders `error: <msg>` + exit 1. Exit codes: `0` ok ·
  `1` error (full traceback only under `CAGE_DEBUG=1`) · `2` argparse usage · `130`
  interrupt; `cage authorship verify` stays exit 0. Don't add an exception hierarchy or convert a
  write path into a raising one.
- **Transcript call ids are deterministic.** A usage row with no stable source id (a Claude
  turn lacking `uuid`) derives its `call_id` from `(agent, session, model, tokens_in,
  tokens_out, cached_in, ts)` (`transcript._composite_id`) so re-imports dedupe in
  `hooks.append_new` — never a random id. uuid-present rows stay byte-identical.
- **TOML writes are text surgery** ([tomledit.py](cage/tomledit.py)) — the ONE module
  that writes project config text (formerly `pricestoml.py`; its price-specific setters
  went with ADR 0011, the generic writer did not, so it was renamed rather than deleted).
  In-place value edits marked `# cage:custom`, or a deterministic cage-managed block —
  never a whole-file rewrite, because the stdlib has no comment-preserving TOML
  serializer. Locked, atomic, and it **re-parses the candidate text before replacing the
  file**: a duplicate table header would make the whole config unparseable and capture
  would silently fall back to the bundle. Callers: `policysync` · `initcmd` ·
  `cage setup --python-launcher`. `cage policy sync` is unambiguously `cage.toml`-only.
- **⚠ "Export imports everything first" NOW HAS NO SURFACE.** The rule — an export runs
  the full all-agent sweep before emitting, so a capture-only machine still ships a
  complete artifact — was carried by `cage data export` (deleted v0.50) and then by the
  fleet bundle export (deleted v0.51, STUDY-CUT). Cage has no export that bundles a
  ledger. `policy.import_before_export` and the `[capture] import_before_export` key are
  **still there and read by nothing** (UNREAD-FACTS) — kept because a reader's deletion
  never licensed deleting the setting, and removing the key would orphan it in every
  scaffolded project. A future bundling export re-inherits the rule; it is not repealed.
- **State cleanup is a closed allowlist, and deletion is manual-only (v0.37)**
  ([cleanup.py](cage/cleanup.py), ADR-LAWS) — aged debug.log/hooks-seen rows, stale
  `pending-*` buffers, orphan cursors, `*.tmp`; never ledger/ (tool savings included —
  see below), cage.toml (and legacy policy.toml), limits.json, and the fleet study's two
  leftovers — machine.json and study.jsonl, unwritten since STUDY-CUT and *still*
  undeletable, because a deleted reader never licensed deleting recorded state
  (by construction). **⚠ NOTHING PRUNES `state/` ANY MORE.** The one deletion path was
  `cage data cleanup --apply`, deleted in v0.50; `cleanup.py` is kept and its auto path
  still *warns*, but the explicitly-typed command that was the only thing allowed to
  delete is gone. This is **STATE-RETENTION** in `work/OPEN-WORK.md`, stated here rather
  than left as a rule naming a dead verb. The auto path (piggybacked on `importcmd.run`/session-end,
  throttled, fail-open, `cleanup.prune` debug context) only ever **warns**, once per
  throttle interval, on stderr — count, reclaimable size, and the runnable fix, silent
  when nothing is eligible — and never deletes. `[cleanup] enabled` (`CAGE_CLEANUP`
  overrides) gates the auto path outright — `false` means no automatic anything, not
  even the reminder; `[cleanup] warn` (`CAGE_CLEANUP_WARN`) silences just the reminder
  text without disabling the gate. Retention default is `[cleanup] days = 90`
  (`constants.CLEANUP_DEFAULT_DAYS`; 30 proved tighter than a real usage gap). State
  files are never read by derived views — cleanup can't change a reported number (tested
  byte-identical), and stdout never carries the reminder (stderr only, also tested).
  **Tool savings (`ledger/savings/<tool>/`) may never get a dedicated cleanup class** —
  today they're unreachable only because they sit under `ledger/`; a per-tool class must
  never be added, since a savings row is unrecoverable (tested at `days=0`).
- **Compare on a fork; propose an idea — before the plan.** When a decision has
  multiple viable options, write a *compare doc* in [work/compare/](work/compare/)
  **first** — debate, matrix, grounded references, a proposed verdict Arpit accepts
  or overrides, and a reopen-trigger — before committing to a plan. This is a
  standing rule. **`docs/proposals/` no longer exists** — on 2026-08-12 Arpit closed
  every parked idea unbuilt and the directory was archived, so an idea worth keeping
  but not being built now gets **one line in [work/OPEN-WORK.md](work/OPEN-WORK.md)**
  with its trigger, not a file of its own (this still keeps a `# v2:` idea out of the
  code). If a parked-idea home is ever re-established, the four-rule format contract to
  copy is in [archive/v0.49-proposals-readme.md](work/archive/v0.49-proposals-readme.md).
  A settled fork graduates to a plan entry and, on ship, an ADR; the compare doc stays
  as the evidence behind it.
- **Research gets its own doc, always — in [work/research/](work/research/).**
  Whenever a session does research — an external-source investigation, a store/format
  probe, a competitive or ecosystem survey, anything whose output is *findings rather
  than a decision* — the findings are written up as a separate dated research doc in
  `work/research/` in that same session, never left as chat-only knowledge or inlined
  into a proposal. Research docs are **evidence, not spec**: proposals, compare docs,
  plan entries, and IMPLEMENTATION.md entries *link* to them as their grounding
  (the same role `regression/` plays for measured evidence — research/ is the
  sourced-findings twin). Cite sources (URLs, code paths, versions probed) so a
  future agent can re-verify. First occupant:
  [research/copilot-vscode-token-sources.md](work/research/copilot-vscode-token-sources.md).
- **Deleting a doc is a citation migration, not just a file removal** — the prose
  twin of the removed-verb rule. Source comments cite docs by path (`docs/x.md`), and
  a deleted doc leaves those pointers dangling **silently**: nothing fails, and a
  reader chasing a "column contract" or a "design of record" finds nothing. The v0.36
  hookless sweep deleted five design docs and swept none of their citations; the rot
  surfaced twice, a week apart. So: **removing a doc must, in the same change, either
  re-point every citation at the surviving home (`cage query <id>`, the owning module,
  a CLAUDE.md section) or state inline that the doc was removed and why.** A citation
  that is deliberately historical ("the generated `docs/cli-output-spec.md` was
  removed in the hookless rebuild") is correct and must read as past tense. Sweep with:
  `grep -rho "docs/[a-z0-9-]*\.md" cage/*.py | sort -u` and test each target exists.
- **A proposal has a lifecycle too — and as of 2026-08-12 there is nowhere to park
  one.** `docs/proposals/` was emptied and archived when Arpit closed the whole queue;
  the five parked ideas are `work/archive/v0.49-*.proposal.md`, each headed *closed by
  decision, never built*. **This rule is retained because the archive lifecycle still
  binds**: where an archived proposal disagrees with the living spec, **the spec wins** —
  implementation routinely corrects the proposal that motivated it, and that correction
  is the valuable part (see
  [v0.38-windows-graphify-interceptor.proposal.md](work/archive/v0.38-windows-graphify-interceptor.proposal.md),
  wrong on both the packaging source and the recursion guard). Should the directory be
  re-established, the full four-state lifecycle (proposed → picked up → implemented →
  archived) and the archive-on-implement checklist are preserved verbatim in
  [archive/v0.49-proposals-readme.md](work/archive/v0.49-proposals-readme.md).
- **Handoff/prompt docs have a lifecycle — active in `work/`, archived once
  IMPLEMENTED.** New feature work is specced as a pair: `work/<feature>.handoff.md`
  + `work/<feature>.prompt.md`. While the work is unbuilt they live in `work/` root
  and are listed under *Active work* in `docs/README.md`. **The change that
  completes the work (suite green — NOT necessarily a release; cage often builds
  several features before committing/tagging) must, in that same change: (1) move
  the pair to `work/archive/vX.Y-<feature>.{handoff,prompt}.md` naming the version
  the work rides, (2) prepend the one-line archive header — say "implemented for
  vX.Y (unreleased)" when the release is still pending, (3) link them from that
  version's CHANGELOG entry ("Built from: …"), (4) update the `docs/README.md` and
  `work/archive/README.md` indexes, and (5) promote any still-true design content
  into the living design doc or plan section — the archive is history and must
  never be cited as current spec.** An implemented feature whose handoff/prompt
  still sits in `work/` root is a bug, same class as a missing changelog entry:
  `work/` root must read as *work not yet done*, so the next agent can trust it as
  the live queue. Archive-on-implement (not on release) is deliberate — it keeps
  that queue honest across the long uncommitted stretches this repo works in.
- **Every prompt doc declares the model tier that should execute it.** A
  `work/*.prompt.md` starts with a `**Model:**` line naming the tier and the
  one-line reason. Work in this repo spans mechanical git hygiene to
  multi-hypothesis diagnosis across a fail-open capture path, and running the
  wrong tier fails in both directions — an over-powered model on a scripted
  cleanup burns budget and invents scope, an under-powered one on a deletion
  with hidden entanglements (Phase 2's five, `hooks.py`'s four subsystems)
  misses what it can't see. The rubric:
  - **Haiku** — fully scripted, zero judgment: run a command, read a file back,
    mechanical find/replace with an exact target. Rare here.
  - **Sonnet** — a decided plan with an explicit change-map: git hygiene,
    docs, additive well-specced features, wide-but-mechanical refactors, and
    executing a handoff whose decisions are already made.
  - **Opus** — anything where the *diagnosis* is the work, or where a wrong
    call is expensive/irreversible: root-causing a silent capture failure,
    deleting code with entanglements, design/architecture, debate gates,
    writing the handoff itself, and any change to the substrate contract,
    determinism law, or method tagging.
  When in doubt on a *destructive or diagnostic* task, choose Opus; on an
  *additive, fully-specced* one, choose Sonnet. State the tier when handing a
  prompt to a human, too — not just in the file.
- **Every prompt doc also declares how much of the work is already done.**
  Directly under the `**Model:**` line, a `work/*.prompt.md` carries a
  `**Progress:**` line — the phases of that feature or program already built, over
  its total, as a percentage, with the phases named:
  `**Progress:** 75% — P0·P1·P2 built (2026-08-02), P3 remaining.`
  A reader (or an executing agent) then knows *where in the program it is standing*
  before it reads a line of spec — the same reason every plan doc opens with a phase
  index. Three constraints make the number worth printing:
  - **The denominator is that program's own phases** — never the OPEN-WORK queue
    (which has no fixed total, so the ratio drifts every time work is discovered)
    and never an effort guess. It must be *countable*, so a reader can check it.
  - **Count against evidence, not against ticks** — the phase index,
    [IMPLEMENTATION.md](work/IMPLEMENTATION.md), `work/archive/` and the code decide
    what is built. A ✅ in the prompt itself is an assertion, not proof; this is the
    same trap the OPEN-WORK rule names, and it bites hardest here because a prompt
    is read by an agent that will act on the number.
  - **A partial phase does not count** — built-and-green or not built. Round to
    whole phases; if a phase is half-done, say so in words after the percentage
    rather than inventing a fraction (`50% — P0·P1 built, P2 in flight`).
  A single-phase prompt says `**Progress:** 0% — not started` and reaches `100%`
  in the change that archives it. Update the line in the same change as the work,
  like every other doc here — a stale Progress line is a lying doc, not a rounding
  error. State the percentage when handing a prompt to a human, too.
- Keep modules small and single-purpose (fux spirit). Tests live in `tests/`.

## Documentation discipline (required)

### Archived documents are NAMED, never CITED (Arpit, 2026-08-14)

**Nothing under `work/archive/` or `docs/archive/` may back a claim.** An archived file
is history: it may have been edited, rewritten, corrected or overwritten since it was
archived, and nothing checks that it still says what it said. A live doc that rests on one
is resting on a source whose integrity is not guaranteed.

**Naming it is fine and often right** — *"ratified as archived ADR 0008"*, *"the v0.36
human-removal handoff"* — so the trail stays followable. **Linking it as evidence is not.**
If a claim needs grounding, ground it in a live source: the code, a live ADR,
[work/regression/](work/regression/) (measured), [work/research/](work/research/) (sourced),
or a reproducible command. If no live source exists, **say the claim is ungrounded** and
file it — an archive link that looks like evidence is worse than an admitted gap, because
it reads as checked.

**The one carve-out is narration.** WORKLOG, IMPLEMENTATION and INTERVIEW record what
happened, and what happened includes archived pairs; linking them there is a history
entry, not a citation. The rule binds anywhere a doc **asserts something is true now**:
every ADR (especially its *Reference* section), FORMULAS, PLAN, GLOSSARY, compare docs,
and regression findings.

**On contact, repoint — don't just delink.** Every archived record has a live successor
(`work/archive/adr/README.md` maps all eleven). Moving the citation to the live home is
strictly better than deleting it, and it is usually the same edit.

**Every change updates the docs in the same change** — this holds whether or not
the change touched code; a decision, a scope change, or a plan is documentation
too. A task is not done until the docs are true. When a doc goes stale, fix it on
contact, not later. The maintained set, each with a standing owner-trigger (the
freshness tracker is [work/DOC-REGISTRY.md](work/DOC-REGISTRY.md) — a change that
fires a trigger updates the doc *and* bumps its row):

- **[work/OPEN-WORK.md](work/OPEN-WORK.md)** — the **single index of pending work**, and
  the only place unfinished work is tracked. **One line per item, one screen.**
  `docs/open/` held that detail one-file-per-item from 2026-08-11 until 2026-08-12,
  when Arpit closed the whole queue and the directory was archived — so **an item is now
  one line here**, with detail inline or in a handoff/prompt pair in `work/` root.
  The standing constraints that lived beside it did **not** lapse with the directory:
  [archive/v0.49-open-queue-constraints.md](work/archive/v0.49-open-queue-constraints.md)
  names which are enforced mechanically and which are now carried by prose alone.
  `work/` root carries no loose handoff/prompt pairs; a pair is created only when a
  phase there is picked up, and archived on implement.
  **The header's checkable claims are test-gated** ([tests/test_queue_honesty.py](tests/test_queue_honesty.py)):
  a version, tag, or clean-and-pushed assertion that contradicts git fails the suite. It
  fails **only on a contradiction**, is silent when the header claims nothing, and skips
  when git ground truth is unavailable — asserting `HEAD == origin/main` outright was
  pre-mortem-**rejected**, because a gate that reddens on every legitimate in-flight
  change trains its maintainer to ignore it, which is worse than no gate. **Counts are
  deliberately NOT gated** ("8 commits ahead", "47 staged files"): they are true only at
  the instant of writing, and the handoff that specified this gate was itself wrong about
  one. A number true only when written is not a claim worth gating — it is a claim worth
  not making.
  **Maintained continuously — always up to date, never rebuilt from memory later.**
  It is updated in the *same* change as the work, on every one of these triggers:
  an item is finished (remove it) · new work is discovered or a defect is found
  (add it, the moment it's known, even mid-task) · scope, verdict, owner, or
  priority changes · an item is blocked or unblocked · the order changes · a
  standing constraint is added or lifted. **Discovering work and not filing it is
  the same defect as finishing work and not removing it** — both make the file lie
  about what is left. A session that changed the shape of pending work and ended
  without touching this file has left the queue stale; treat that like a missing
  changelog entry.
  **A completed item is REMOVED from OPEN-WORK, never left ticked** — the file must read
  as *what is still to do*, so a reader can trust its length. Removal is only legal once
  the work is recorded elsewhere: **before deleting an item, append its outcome to
  [IMPLEMENTATION.md](work/IMPLEMENTATION.md)** (what was built · files · tests · next
  step) **and, if it produced evidence, publish it to [regression/](work/regression/)**.
  Carry forward anything still live — a residual limit, an open decision, a follow-up —
  as its own item rather than losing it with the parent. A ticked-but-present item and a
  deleted-but-unrecorded one are the same bug in opposite directions: the first inflates
  the queue, the second loses the history.
  **Never trust its own status markers as ground truth when reconciling** — a ✅ in a
  plan file is an assertion, not evidence. Verify against `work/regression/`,
  `IMPLEMENTATION.md`, and **the code** before declaring an item pending or done.
  `work/archive/` may *point* at what once happened, but under
  *Archived documents are named, never cited* it settles nothing — a pair archived as
  "built" is a claim from the past, not a check on the present. On 2026-08-01 this file listed two already-built items as
  pending precisely because its markers had gone stale.
- **[work/IMPLEMENTATION.md](work/IMPLEMENTATION.md)** — the build log. Append at
  **every small milestone** (green checkpoint, commit, phase step): date ·
  milestone · what was built · files · test status · next step. Green/in-progress/
  failed/blocked all get an entry — an execution that skips it left the milestone
  unrecorded. Newest first. It lives under root `work/`, alongside the other
  session-tracking docs — not under `docs/`, which stays the design/reference tree.
- **[work/WORKLOG.md](work/WORKLOG.md)** — the running per-session handoff. Append
  every substantive exchange: asked · done · decided/open · single next step.
  Newest first. **This covers every working surface — Claude Code executions AND
  Cowork/chat strategy sessions alike**: a decision made in conversation (a scope
  call, a directive, a plan revision) is worklog material even when no code moved;
  the agent in that conversation appends the entry before the session ends.
- **[work/INTERVIEW.md](work/INTERVIEW.md)** — the **exit interview**: notes from
  the outgoing maintainer-model to every future one (read it after this file).
  Write it the way a departing engineer briefs their replacement — not a status
  page, but *what I learned, what I'd warn you about, what I'd do next and why*.
  Four standing sections: **state of play** (where things actually are, including
  the uncommitted/in-flight truth) · **in-flight work + the single next step** ·
  **standing constraints** (the human's active directives) · **lessons / scar
  tissue** (the traps that cost time, written so the next model doesn't re-pay).
  **Maintained continuously, not just at departure** — any session can be the
  last one before a model switch, so it must always read as if handed over right
  now. Update it in the same session whenever direction, strategy, standing
  constraints, or state of play change, and add yourself to the maintainer line
  with the one lesson you'd want inherited. A model handing off with a stale
  INTERVIEW.md has broken succession — treat it like a missing changelog entry.
- **[docs/FORMULAS.md](docs/FORMULAS.md)** — every computed number in one place:
  formula · code home · method tag · the knobs that move it. Update in the same
  change as any formula, constant, or method-tag change; it must agree with the
  live explainer registry ([explain_data.py](cage/explain_data.py)), which is the
  copy that ships in the binary.
- **Every plan doc opens with a phase index.** The first section after the title
  block of any plan (`docs/*plan*.md`) is a
  numbered list of every phase/step with **one line each** — what it does and its
  gate/status — so a reader (or an executing agent) sees the whole shape before
  any detail, and a stale plan is spottable at a glance. Existing plans gain the
  index on contact (the fix-on-contact rule), new plans start with it.
- **[docs/adr/0008_graphify.md](docs/adr/0008_graphify.md)** — the graphify interceptor
  behaviour contract: one spec, two twins. Update in the same change as **any** twin
  edit, marker-set change, or new tool interceptor (every future one implements this
  same shape). Two implementations of an unwritten contract drift.
- **[docs/adr/0003_cli.md](docs/adr/0003_cli.md)** — **the complete CLI reference**: every command,
  group, action, flag and choice list, the removed-verb migration table, and the
  surface's known gaps. Update it in the *same change* as any CLI surface change — a
  command added/renamed/removed, a flag added/dropped, a choice list changed. It is
  **not** a promise: [tests/test_cli_reference.py](tests/test_cli_reference.py) gates it
  bidirectionally against `cli.build_parser()` — every command and flag named there
  must exist, and every leaf and flag the parser knows must appear there — so a rename
  that misses the doc turns the suite red instead of leaving a dead verb in prose (the
  F1 class, in documentation form; same detector, same reason as `wiringscan`). A
  single-owner flag must additionally sit in its own command's section, so a shared
  vocabulary can't paper over a misfiled one.
- **[docs/GLOSSARY.md](docs/GLOSSARY.md)** — every recurring term, defined once
  against the code that owns it.
- **[work/DOC-REGISTRY.md](work/DOC-REGISTRY.md)** — the freshness tracker itself; a
  new maintained doc gets a new row, same change.
- **[docs/architecture-flow.mermaid](docs/architecture-flow.mermaid)** — the
  one-way data flow as a diagram; update when a stage/sink/read-surface changes.
  Linked from the README's *How it works*.
- **ADRs** authored from **[docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md)** — see
  *Decision records* below.
- **[docs/example/](docs/example/)** — copy-from contracts (cli · debug · setup ·
  toml-config), one per file; update the matching one when that surface changes.
- **[work/research/](work/research/)** — dated research docs, one per investigation
  (see the *Research gets its own doc* rule in Must-Know Rules): sourced findings
  that proposals/plan/IMPLEMENTATION link to as evidence, never spec.

Note: ALL-CAPS entry-point/tracker files (CLAUDE.md, CHANGELOG.md, README.md and
AGENTS.md at root; GLOSSARY.md, DOC-REGISTRY.md, FORMULAS.md under `docs/`;
IMPLEMENTATION.md, INTERVIEW.md, MACHINE.md, OPEN-WORK.md, WORKLOG.md under `work/`)
carry no frontmatter; lowercase docs may.

**Documentation style — no large paragraphs.** Authored docs (guides, handoffs,
prompts, examples, ADRs, compare/proposal docs) are written in **short points**,
one idea each, roomy, takeaway first; keep paragraphs to 3–4 lines and use tables
for option/field comparisons. Fix a wall of text on contact — the docs law applies
to *form*, not just facts. (CLAUDE.md and the design docs are the
deliberate exception: dense reference prose, packed on purpose.)

**Document size discipline — ⏳ TRIAL, expires 2026-09-01.** Four composing rules on
every authored doc. Full spec, worked examples and the fix procedure:
[work/doc-size-discipline.md](work/doc-size-discipline.md).

1. **Lead with the answer** — first ~5 lines say what's next, what's blocked, what
   changed. A reader who stops there has the useful part.
2. **One audience per doc** — a plan carries only what the *decider* needs; build
   detail → handoff/prompt, rationale → ADR/design doc, evidence → `regression/`.
3. **Evidence lives elsewhere, always** — state the claim, link the proof. Never
   inline the numbers or reasoning; `regression/`, `archive/`, `IMPLEMENTATION.md`
   and the ADRs already hold them.
4. **A hard budget** — a plan fits one screen (~40 lines); a table row is *genuinely*
   one line (≤120 chars). Over budget ⇒ move content out, never compress in place.
   **Reference docs (this file, the design docs) are exempt from rule 4
   only** — dense on purpose; 1–3 still bind them.

**On 2026-09-01 this rule must be explicitly retained, amended, or removed — it
lapses if unreviewed**, so it cannot become permanent by neglect. Review criteria and
the retain/remove call live in the spec doc. Tracked in
[work/DOC-REGISTRY.md](work/DOC-REGISTRY.md).

**Every prompt/handoff also names the model tier** that should execute it, and
**every prompt doc carries a `Progress:` percentage** of that program's phases — see
the two prompt-doc rules and the Haiku/Sonnet/Opus rubric in *Must-Know Rules* above;
don't restate them, apply them.

## Decision records (ADRs)

**The set is FIFTEEN records — one per thing cage meters, plus one for what binds them all,
one for the map of what each surface can and cannot yield, one for the surface it is all
read through, one for the cross-agent question of who wrote which lines, one for
proving nothing already recorded has changed, one for what may ever be deleted, one
for the file that holds every decision you get to make, one for the layers an
agent reaches all of it through, one for how measured tool combinations compare
without ever faking the one that has no receipts yet, and one for which ledger a run's
captured rows land in** —
[ADR-LAWS](docs/adr/0001_laws.md) · [ADR-COVERAGE](docs/adr/0002_coverage.md) ·
[ADR-CLI](docs/adr/0003_cli.md) · [ADR-CLAUDE](docs/adr/0004_claude.md) ·
[ADR-COPILOT](docs/adr/0005_copilot.md) · [ADR-KIRO](docs/adr/0006_kiro.md) ·
[ADR-CONSUMERS](docs/adr/0007_consumer.md) · [ADR-GRAPHIFY](docs/adr/0008_graphify.md) ·
[ADR-AUTHORSHIP](docs/adr/0009_authorship.md) · [ADR-INTEGRITY](docs/adr/0010_integrity.md) ·
[ADR-CLEANUP](docs/adr/0011_cleanup.md) · [ADR-CONFIG](docs/adr/0012_config.md) ·
[ADR-LADDER](docs/adr/0013_ladder.md) · [ADR-MATRIX](docs/adr/0014_matrix.md) ·
[ADR-LEDGER](docs/adr/0015_ledger.md) —
ADR-MATRIX ratified 2026-08-15, **nothing built yet** (`cage/matrixview.py` does not
exist); ADR-LEDGER ratified **and shipped** 2026-08-15 (reverses ADR-KIRO's Kiro-IDE
machine-ledger routing — see that record for the accepted cost).
Index, the ownership table and the standing rule: [docs/adr/README.md](docs/adr/README.md).
Author new ones from [docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md).

**Cite them BY NAME — `ADR-KIRO`, never "ADR 0005".** The numbers belong to the eleven
**superseded** records now frozen in [work/archive/adr/](work/archive/adr/README.md),
which are **history and must never be cited as current spec**. "ADR 0001" meant *team
ledger aggregation via `refs/notes`* for six weeks, and ~90 references to the numeric
names still exist.

**Each record has two sections:** **§1 for humans** (one screen, a Mermaid diagram and a
hand-paired ASCII twin — both required, changed in the same edit) and **§2 for agents**
(context · decision · consequences · alternatives rejected · reference · veto condition).

**The five laws live in ADR-LAWS and nowhere else** — pull-only · one sink · append-only ·
counts-never-content · usage-never-cost. **A record that restates a law is a bug, not
redundancy**: a second copy can drift, and drift there is invisible until it produces a
wrong number. Determinism, the method law, fail-open-but-never-silent and `$0`/stdlib-only
bind equally, live in *this* file, and are named-but-not-restated in ADR-LAWS.

An ADR-worthy decision is one where a wrong call is expensive to reverse and the reasoning
isn't obvious from the code. A one-line dated call goes in the plan's decisions log
instead.

**Every ADR carries a reference** (fux's rule) — a measurement, a probe, or a concrete
worked example that grounds *why*. An ADR that only asserts is incomplete.

**Every ADR ends with a `## Veto condition (when to revisit)`** — cage's own anti-rot
device. Three parts, each load-bearing:

- **A falsifiable trigger, numbered** where the decision is volume- or measurement-gated.
  Name the number **and where the change lands**, so revisiting cannot quietly become a
  redesign. A veto reopenable only by a *measurement*, never an *argument*, pre-empts a
  future agent re-litigating a rejected option from first principles. **Say so explicitly
  when a trigger is not yet instrumented** — a veto you cannot compute is aspirational
  (ADR-GRAPHIFY's double-count rate is the worked example: named, and stated UNMEASURED
  rather than assumed zero).
- **Contingent vs. invariant, labelled.** Contingent auto-revisits on evidence; invariant
  moves only by ratified reversal. Pretending every decision is revisitable-on-evidence
  lies about the ones that are values.
- **A "deliberately not taken" record** where there's meaningful negative space — an option
  declined but *not* dogmatically rejected, with its own future threshold. Records the
  omission as a choice, so the next agent doesn't mistake it for an oversight and ship it
  as a `# v2:` half-build.


## Dev

```bash
just test          # python -m pytest -q   (1563 tests; +10 Windows-only skips, +1 opt-in dogfood-age skip)
just demo          # seed §4.4 + print attrib/matrix
cage --version
```

## Claude Code subagents (.claude/agents/)

**Three agents (Arpit, 2026-08-15): `queue-auditor` · `adr-verifier` · `doc-reconciler`.**
They are context compressors, not a speed-up on writing code — cage's bottleneck is
judgment against this file, not typing, and fanning out code-writers here produces merge
conflicts and confident law violations. The win is isolating the read-heavy reconciliation
tax (WORKLOG/IMPLEMENTATION/OPEN-WORK/ADRs vs. git-and-code ground truth) out of the main
context, so a session doesn't burn its window reading 13k lines of history to write 20.

- **`queue-auditor`** (read-only) — re-derives every `work/OPEN-WORK.md` item against
  `git log origin/main..HEAD` → `regression/` → `IMPLEMENTATION.md` → code.
- **`adr-verifier`** (read-only, one instance per ADR, fanned out) — verifies §2 claims
  against code, flags illegal archive citations and law restatements.
- **`doc-reconciler`** (writes `WORKLOG.md`/`IMPLEMENTATION.md`/`DOC-REGISTRY.md`; drafts
  only, unapplied, for `OPEN-WORK.md`/`INTERVIEW.md`; never touches `CLAUDE.md` or
  `docs/adr/`) — the session-close doc tax from *Documentation discipline* above.

**Auto-invoke — do not wait to be asked.** Each agent's `description` frontmatter states
its trigger conditions in Claude-Code-routable form; a session ending without the
`doc-reconciler` pass has left the docs stale, the same defect as a missing changelog
entry (see *Documentation discipline*).

**Known gap, not yet closed:** read-only on `queue-auditor`/`adr-verifier` is
prompt-enforced, not tool-enforced — `Bash` is unscoped in their frontmatter. A
`.claude/settings.json` deny rule would make it hard; not added.

**No ADR affected** — this is Claude Code tooling for working the repo, not a cage
product behaviour.

## Regression & capture reports (do this after every testing run)

The sibling repo **cage-lab** (`../cage-lab`) is the out-of-tree, **black-box**
regression suite + per-agent capture labs (it installs the shipped `cage` and never
imports it; the in-tree suite can't see packaging, entry points, or bundled data).
Its numbers are validated against a hand-derived reference, and its labs slice the
**real** `~/.cage` ledger per agent to surface capture gaps.

**Rebuild manual: [work/cage-lab/](work/cage-lab/README.md)** — cage-lab is disposable;
that directory is what recreates it from nothing (setup · run · verify · publish ·
manual cells).

**Standing rule: every lab runs in its own `.venv`, always.** A lab whose `cage`/
`graphify` come from whatever is globally installed is not reproducible, and its PATH
order is decided by the machine's shell rc rather than the experiment — a stale
interceptor in an unrelated project once won on PATH from *inside* cage-lab and
silently unmetered every graphify run. So: `python3 -m venv .venv`, install cage +
graphify into it (pinned; local `-e ../cage` only while a release is pending, recorded
as a declared deviation from the black-box rule), and **set PATH explicitly in the
driver** — `export PATH="$LAB/bin:$LAB/.venv/bin:$PATH"` — never relying on shell
activation. The run **proves its own PATH** (`command -v graphify` written into the run
manifest) and `SETUP.md` names the exact builds. This does **not** cover VS Code
extension subprocesses, which inherit VS Code's launch environment — those stay
per-machine-verified.

**Standing rule: after every cage-lab testing/capture run, publish the findings into
[`work/regression/`](work/regression/) here, dated** — so they live with cage, are
diffable release-to-release, and any agent working on cage can read them without the
test repo checked out. The runner does it automatically:

```bash
CAGE_REAL_LEDGER=~/.cage python ../cage-lab/labs/run_all.py   # writes work/regression/<date>-{capture-report.md,.json,fixes.md} + latest-*
```

When you (an agent) run cage-lab by hand, still drop the dated report + a prioritized
`*-fixes.md` into `work/regression/` and add the row to its README index. The latest
findings and their fix checklist are the input for the next round of cage fixes; see
`work/regression/latest-capture-report.md`.

## Dogfood snapshot (refresh periodically)

`work/dogfood/` publishes cage's own real `~/.cage` ledger numbers so the README
never has to chase them — design of record:
[dogfood-report.handoff.md](work/archive/v0.44-dogfood-report.handoff.md) (archived
on implement; the living pattern is `work/dogfood/README.md`).

To refresh: on the dev machine, run the surviving allowlisted commands — **`cage
insights chats` is the only one left; `cage report`, `insights attrib` and `insights
adoption` were deleted in v0.50** — over the same absolute window
(all-time, no `--since`), paste the output verbatim (method tags intact) into a new
`work/dogfood/<YYYY-MM-DD>.md`, and copy it over `latest.md`. **Never**
publish a snapshot containing chat titles or working-dir basenames — they leak private
project names, and this repo is public. (The old prohibition named `cage insights chats`
and `cage report --project`; the second is deleted, the first is now the *only* reader,
so the rule is stated against the **data**, not the command.)
**Never author a number** — if a command has nothing real to show (an empty task
ledger, say), the snapshot states that instead of fabricating one.
`tests/test_dogfood_freshness.py` fails once `latest.md` is >60 days old or its
`snapshot_date` disagrees with the newest filename; `CAGE_SKIP_DOGFOOD_FRESHNESS=1`
is the bisect/old-tag escape hatch.

## Adapters & agents (one ledger, many surfaces)

Cage targets the **wire protocol**, so the meter and read surface are universal and
each agent only needs thin idiomatic wiring (`agents.py` orchestrates):

- **Meter:** `metering.py` (library), `proxy.py` + `usageparse.py` (any client you
  point a base URL at), `transcript.py` (Claude Code / Copilot CLI / Kiro session
  logs — `LOG_BEARING` is now all three of `agents.SURFACES`; Kiro's `tokens_generated.jsonl`
  is coarse so the proxy stays its higher-fidelity fallback. A capture-only sibling
  ledger, `.cage/ledger/kiro/` (KIRO-METRICS), records what that log's timestamped
  SQLite twin `devdata.sqlite` and the CLI store's per-turn metadata carry beyond
  `calls`/`credits` — never priced, not yet read by any derived view, an
  upgrade-watch armed for the CLI's still-NULL token slots). transcript.py also feeds
  a THIRD capture-only sibling, `.cage/ledger/claude/` (CLAUDE-METRICS): one row per
  Claude Code chat, correctly folded — THE DEDUP LAW (fold duplicate assistant rows
  per `(requestId, message.id)`, last wins) plus a subagent-to-parent join via each
  row's own `sessionId` — deliberately dodging, not fixing, two open calls-path
  defects (CLAUDE-DEDUP inflates `calls` ~2-3×; CLAUDE-SUBAGENT-KEY mis-keys
  subagent spend there). No credits field — none exists for Claude Code on disk.
  Capture is **pull-based and
  global** (ADR-LAWS Law 2): `cage import` over a **resolved** ledger
  (`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`, via `paths.resolve_root`)
  is the universal path that works with no hooks and no project.
  **Kiro was the ONE exception to one-sink-per-sweep, from 2026-08-01 to 2026-08-15 —
  reversed by [ADR-LEDGER](docs/adr/0015_ledger.md).** Its *IDE* log is a single global
  file with no project/session/ts; through 2026-08-15 those rows were a **machine fact**
  routed unconditionally to `~/.cage` (`paths.kiro_routed(root)` returning the machine
  ledger). **ADR-LEDGER made Law 2 exceptionless**: `paths.kiro_ledger(root)` now always
  returns `root` itself, `paths.kiro_routed(root)` now always returns `None`, and
  `importcmd._kiro_leg`/`_drop_routed_kiro_state` — the routed leg's own lock/cursors/
  health/manifest/`import_id` machinery — are deleted, not just unreachable. Kiro's IDE
  rows now capture through the same `run_agent(root, "kiro", ...)` path as claude and
  copilot, into this run's one resolved ledger. **The accepted cost, named rather than
  hidden**: the same underlying turn, imported from two different projects, is now
  stored as a separate row in each ledger — ADR-LEDGER's Reference section carries the
  field-probe measurement (22 of 28 rows in one workspace were actually another
  workspace's turns) that this cost is weighed against. **`_import_rollup` excludes
  kiro's collected rows unconditionally** (a fix that shipped in the same change): kiro's
  metrics rows now reach the sweep's shared `collected` list like every other agent's,
  and without that exclusion the rollup's `total` line would silently sum kiro's
  not-summable IDE tokens into every project's report — a live regression this reversal
  would otherwise have introduced, caught by `tests/test_kiro_routing.py` before it
  shipped. Kiro's *CLI* store keeps the **opposite** fix, unaffected by this reversal:
  `conversations_v2` is keyed by cwd, so it is read scoped to the project **tree**
  (`paths.kiro_cli_workspace`, prefix-matched on a separator boundary, symlink-resolved —
  the real store keys `/tmp/x` as `/private/tmp/x`) and stamps the additive-optional
  `project` on the credit row. Pre-existing duplicated rows are never rewritten
  (append-only); `chats.kiro_routed_line` now always returns `""` (there is nothing left
  to explain — kiro rows are simply in the ledger you're looking at) but is kept as a
  stable call site rather than deleted. Hooks are an optional
  CLI-only real-time add-on (they don't fire under a VS Code extension). **Capture-on-read**
  (capture-architecture Phase 1) makes a *read* the primary trigger: `report`/`insights *`/
  the MCP read tools call `importcmd.ensure_captured` before rendering (throttled on
  `_last_import`, gated by `[capture] on_read` / `CAGE_CAPTURE_ON_READ`, suppressible with
  `--no-import`, fail-open) — so a number is never staler than the instant it's shown, with
  no hook. It writes the ledger only, so derived numbers stay a pure function of it, and the
  determinism/golden suites pin it OFF. Confirmations go to **stderr** (`· captured N new …`,
  silent when zero); the graphify/fux push prints `✔ cage: … captured` to stderr too; MCP
  returns the summary as `structuredContent.capture`. `cage doctor` does **not** sweep (it
  diagnoses capture) but gains a per-source, per-**mode** (pull/push) timeline. Phase 1 is
  additive — **no hook file touched**; deleting the token-capture hooks is Phase 2. `importcmd.run`
  honors the **consumer capture switch** — `policy.capture_enabled(pol)`: env `CAGE_CAPTURE`
  (0/1) overrides `cage.toml [capture] enabled` (default on), so a consumer can pause
  metering without unwiring hooks. It **no longer guards on a cwd `.cage/`**: a hook firing
  outside any project lands in the global ledger (the resolver prevents stray local
  footprints), and a per-agent high-water cursor (`state/cursors.json`, last-seen
  `(size, mtime)`) keeps re-imports incremental (the shared `seen` set bounds the ledger
  read to once per run). **cage installs no OS scheduler** ([ADR 0002](work/archive/adr/0002-universal-capture-global-ledger-explicit-import-export.md)
  — a product invariant, not volume-gated) — no launchd/systemd/cron/
  schtasks, no `cage scheduler`; hands-off automation is the user's own cron/schtasks
  line calling `cage import` (the hint `render.scheduler_hint()` prints is OS-aware,
  never installed). `cage data watch` was that hint's foreground companion and was
  deleted in v0.50 — capture is now `cage import` plus capture-on-read (CONTINUOUS-CAPTURE
  in `work/OPEN-WORK.md`). Per-agent log locations live in **one registry**,
  `paths.agent_log_sources()` — per-OS candidates behind it (env overrides always
  win; the Windows Kiro layout is labeled UNVERIFIED-LAYOUT until pinned on a real
  install), probed read-only by `cage doctor --paths` ([pathprobe.py](cage/pathprobe.py),
  exported in the doctor bundle as `paths.txt`). A project `cage.toml [sources]`
  table extends/replaces it (`paths` + optional per-source `glob` + optional
  `surface` (`cli|vscode|ide`, table-level or per-entry; `importcmd._surface_restamp`
  restamps the imported rows' surface **only when declared** — so a non-IDE store
  isn't left with the parser's hardcoded value, e.g. Kiro's `ide`; absent ⇒ the
  parser's own value, byte-identical), or the `[[sources.<x>]]` array-of-tables form;
  `resolve_log_sources` is the one resolution point) — additive, empty/absent = the
  built-in registry byte-for-byte.
  The built-in defaults are also emitted into every project's `.cage/cage.toml`
  as an **inert comment block** (the bundle ships no active
  `[sources]` table — defaults live in code and upgrade with the package).
  Cross-process locking is the single
  fail-open helper [lockutil.py](cage/lockutil.py) (fcntl → msvcrt → proceed-unlocked,
  debug-logged) — never hand-roll another `fcntl` block.
- **Read:** `mcpserver.py` (MCP, every agent), `report/attrib/matrix/budget/roi`,
  plus `task outcome`, authorship
  (`origin`/`notes-sync`/`verify`, ADR-AUTHORSHIP), and the ledger-scale surface
  (`--scope`; **`--team` and `ledger-sync` were deleted in v0.50** — `mergeutil.union_by_id`
  survives and is still `notes-sync`'s merge core, ADR-LAWS).
- **The agent surface is a four-layer ladder, and L0 is the floor**
  ([ADR-LADDER](docs/adr/0013_ladder.md); `cage query agent-layers`). **L0 hookless** (pull capture + interceptor + every CLI
  view — *this is cage*, never optional) → **L1 hooks+steering** (`cage setup --hooks`) →
  **L2 MCP** → **L3 skills** (`--skills`). Everything above L0 is **opt-in and two-way**:
  a plain `cage setup` both declines to wire a layer and *removes* one already wired.
  **The binding rule, and it is a test:** adding or removing any layer changes **no
  number** — [tests/test_floor.py](tests/test_floor.py) installs every layer cage ships
  onto an already-captured project, asserts the ledger shards *and* seven views' stdout
  byte-identical, strips it all, and asserts again, per agent. **A new layer is wired
  into that test by adding its artifacts to `_WIRING_ARTIFACTS` — never by relaxing an
  assertion.** If a phase cannot meet the gate, the phase is wrong; the number is never
  what gets adjusted.
- **L1 is NOT for capture** ([hookcmd.py](cage/hookcmd.py), [attest.py](cage/attest.py))
  — capture already works with no hooks, and a second write path would be a
  double-capture risk for no gain. L1 buys exactly three things: (a) **agent identity,
  stamped not inferred** — a hook runs *inside* the agent, so `cage hook <event> --agent
  X` states it as a fact; attestations land in `state/attest.jsonl` and join the usage
  breadcrumb on `args_hash` (an **exact** key). **Its only consumer, `cage insights
  adoption`, was deleted in v0.50 — the attestation is still written and now read by
  nothing** (the sharpest of the six UNREAD-FACTS). It does **not** fix half B — a graphify savings row's
  id folds in an *answer* hash no attestation can reconstruct, so `NO_LINK` stays
  structurally true and is not quietly narrowed. (b) **auto task-close** at the session
  boundary, on the **exact session id** — never the most recent task, never by proximity.
  (There was a third — `budget.check`'s first real caller, `cage hook budget` exiting
  `BLOCK` (2) — and it went with the money subsystem: `hookcmd.BLOCK` is gone and **every
  hook event now exits 0**. The `cli.main` guard that catches an argparse `2` from `cage
  hook` **outlived it and matters more, not less**: `2` is the HOST's "block this tool
  call" code, so an accidental one from a stale wired event name would block every Bash
  call in the session — and there is now no path where blocking is ever intended.) **Auto-close never claims success:** `tasks.jsonl`'s
  `outcome` and the quality store (`.cage/outcomes.json`, ok|redo) are *different axes*,
  so the hook writes `outcome="auto"` — closed for compare/estimate/calibration,
  **invisible to the outcome store** ([outcomes.py](cage/outcomes.py) — relocated out of
  the deleted `quality.py`). Stamping `ok` would inflate the success rate of
  every session that merely ended. **Fail-open is absolute** (every event exits 0 on any
  internal failure; the sole non-zero is the deliberate budget block), and **hooks are
  CLI-only** — they do not fire under a VS Code extension, so every L1 fact carries that
  limit (`attest.LIMIT`). Per-agent capability is **ONE table**, `agents.HOOK_EVENTS`,
  and **every gap is named in output** via `agents.HOOK_GAPS` (kiro has no session-start
  ⇒ its `agentStop` hook attests but **declines** to auto-close; copilot has no verified
  pre-tool event ⇒ no attestation, no budget block — **and its two wired event names are
  cage's own, unverified against any vendor doc, while cage reads no session id from a
  Copilot payload, so it attests without a session and declines auto-close the same way
  kiro does**). A limit that is **not per-agent** goes in one of the two all-agents lines
  instead, never smuggled into `HOOK_GAPS` — which structurally cannot hold it, since a
  full-event-set agent must stay disjoint from that table: `HOOK_SURFACE_LIMIT` (hooks
  are CLI-only) and `HOOK_SHELL_LIMIT` (every wired command is POSIX shell, so Windows
  needs Git Bash/WSL; kiro's hook schema names no interpreter at all). The shell limit is
  **named, not twinned** — the hook files are committed and byte-compared, so a per-OS
  command would churn a diff on every `cage setup` in a mixed-OS team, the same trade
  already settled for kiro's path-free MCP entry; and it costs no tokens, because L1 is
  not for capture. **Any surface printing an installed-hook *count* must qualify it from
  that same one table** (`clicmds`'s `L1 hooks ×N (limited …)`): the count reads file
  *contents* and is otherwise independent of the gap text, so rewording `HOOK_GAPS` alone
  left `cage setup --status` printing an unqualified `copilot … [L1 hooks ×2]`.
  **No unverified host event name is
  ever invented** — an invented one fails silently, the class this project has already
  paid for twice. Every wired hook command is checked against the **live parser** by
  `wiringscan` (F1, applied before the fact). **A wired file cage did not write is
  refused, never coerced:** a `hooks` value of an unreadable shape leaves the file
  untouched (a non-dict entry is *foreign by construction* — cage only ever writes
  `{"bash": …}`), because "nothing left to preserve" and "a shape I don't understand" are
  different branches; conflating them deleted a user's whole file on the *default* setup
  path.
- **Steering/skills are one source, three deliveries** ([steering.py](cage/steering.py))
  — a `Doc` is authored once and rendered into `.claude/skills/<id>/SKILL.md` ·
  `.github/prompts/<id>.prompt.md` · `.kiro/steering/<id>.md`; only the ~10-line host
  wrapper differs. **Rendered from a Python literal at `cage setup` time, never as a
  bundled asset** — that removes the drift-check/`--bless`/committed-copy machinery
  `tools/skillgen` needed, and is why `cage/data/{skills,prompts,steering}/` must stay
  absent. **The governing content rule: a cage document never computes a number — it
  runs cage and quotes it.** Method tags verbatim, refusals relayed unsmoothed, no
  arithmetic. `steering.lint` enforces it mechanically, and `tests/test_skills_layer.py`
  additionally checks every `cage …` a document names against the **live parser** — a
  skill teaching a dead verb is the F1 class in prose. L1 ships one steering doc
  (`cage-context`); **L3 ships seven skills**: task-closer · analyst · doctor-triage ·
  honesty-reviewer · release · lab-runner · windows-shim. Adding a document = adding one
  `Doc` to `steering.DOCS`; there is no second copy to keep in step, nothing to re-bless,
  and **a document on one agent and not the others is not done**.
- **MCP surface = 1 read tool + exactly ONE write tool** ([mcpserver.py](cage/mcpserver.py),
  L2 of the agent-surface ladder). It was nine, then five (USAGE-ONLY took
  `matrix`/`budget`/`roi`/`verdict` with the money subsystem, ADR 0011), and SURFACE-CUT
  took `report`/`attrib`/`adoption`/`compare` with the ledger rollup and the
  task-comparison family — what survives is the one read no other surface answers,
  **`cage_why`** (full provenance for one call id), and the one write the whole ladder
  depends on. **The refusals are the point** — every view that prints a saving carries
  the GROSS caveat, and each renders through the CLI's *own* renderer so the text
  crosses **byte-identically** (`tests/test_mcp_layer.py` asserts equality with the CLI,
  not substring presence): an agent reads an empty result as **zero**, the one thing a
  refusal never means. **Never add a summarizing layer between a composer and a tool.**
  The write tool is **`cage_task_outcome`** and it is the *only* mutation in the whole
  ladder (`mcpserver.WRITE_TOOLS`) — it exists because every starved surface
  (`compare`/`estimate`/`calibration`/net) is starved for one reason, nobody closes
  tasks. It goes through `clicmds.close_task`, the **one** task-close path the CLI verb
  also uses, so the single-token label guard cannot be laxer on the agent-facing side.
  **Do not add a second write tool by analogy** — the asymmetry is the design.
- **Wiring — one `<agent>wire.py` per agent (a standing convention):** `claudewire.py`
  (`.mcp.json`), `copilotwire.py` (`.vscode/mcp.json`), `kirowire.py`
  (`.kiro/settings/mcp.json`). **MCP is the only *required* surface** — capture is
  pull-based, so `install(root, hooks=False)` is the default and it *strips* every cage
  hook entry it finds, whichever version wrote it. That single path is both the
  pre-v0.36 heal and the `--hooks` **off-switch**: foreign entries are never touched, an
  emptied `hooks` table is dropped rather than left as `{}`, and a file cage reduced to
  `{}` is removed. `install(root, hooks=True)` wires the opt-in L1 layer. Each module
  exposes `install`/`status`/`hook_status`; `agents.py` dispatches via the `_WIRE` map
  (add a row + a `SURFACES` entry for a new agent). **Per-agent hook shapes are
  load-bearing, not incidental:** Claude uses a `hooks[]` container in
  `.claude/settings.json` with a `matcher` per event; Copilot uses **repo-level**
  `.github/hooks/cage.json` (`{"hooks": {"<event>": [{"bash": …}]}}`) — repo-level so a
  teammate gets it on clone, and the **user-level** `~/.copilot/hooks/cage.json` is
  always deleted because both sources *combine* and would double-fire; Kiro's file is
  **one hook per file** (`{name,version,description,when:{type},then:{type,command}}`)
  and Kiro has **no session-start trigger**. Copilot and Kiro get the
  `runshim.selflocating_command` git-root one-liner (neither documents a repo variable
  or a guaranteed hook cwd); Claude gets `${CLAUDE_PROJECT_DIR:-.}`.
  **Committed wiring is portable (ADR-GRAPHIFY):** every project-committed wired
  file (`.mcp.json`, `.vscode/mcp.json`) references the committed
  runtime-resolving shim `.cage/bin/cage-run` ([runshim.py](cage/runshim.py) —
  written by `agents.install`, identical bytes on every machine, resolution:
  PATH → ~/.local/bin/pipx/$VIRTUAL_ENV → `python3 -m cage` → exit 0 silently,
  fail-open) — **never** `paths.cage_bin()`'s absolute path. Per-host reference
  mechanism is documented in each wire module's docstring (Claude:
  `$CLAUDE_PROJECT_DIR` / `${CLAUDE_PROJECT_DIR:-.}`; VS Code:
  `${workspaceFolder}`). User-level configs, when a future layer writes any
  (`~/.copilot/hooks`, `.git/hooks`), stay absolute — per-machine by nature.
  **`.kiro/settings/mcp.json` was the ONE exception and no longer is (v0.41):** Kiro
  resolves neither the shim nor a variable (it spawns MCP servers from its install dir,
  #6525/#5659), so the entry is **path-free** — `python3 -m cage mcp`, `kirowire.PATH_FREE`,
  the one enumeration the writer/migration/doctor all read. Committed, byte-identical,
  no gitignore exception; `wiringscan`'s kiro spec is `required=True` again. **The trade
  is named, not buried:** it depends on *which* `python3` resolves, so doctor's
  **`kiro-mcp`** check asks that interpreter to `import cage` and fails with the fix when
  it can't (a venv miss is otherwise a *silent* no-MCP — the F1 class one layer up).
  Windows is a **stated limit**: `python3` is often absent there and a committed file can
  carry one spelling, so the default is `python3` and doctor points at `cage setup
  --python-launcher` (which writes `py -3` — machine-specific, gitignore that one file on
  a mixed-OS team).
  Re-running setup migrates legacy absolute entries (idempotent, printed).
  `cage doctor` has a `portability` check; `cage query portable-wiring`
  explains the design. A new committed file must never embed a machine path —
  `tests/test_agents.py::test_committed_wiring_never_carries_resolved_path` and
  `tests/test_mcp_layer.py` grep for this and must stay green. (CLAUDE.md and the
  agent-surface prompt both cited a `tests/test_portable_wiring.py`; **no such file has
  ever existed** — the assertions live in the two files named above.)
  **Restricted endpoints (work/restricted-environments.md):** opt-in
  python-launcher mode — `cage setup --python-launcher` persists `[wiring]
  python_launcher = true` (project policy, `policy.python_launcher`, written via
  `tomledit.set_wiring`); `agents.install` re-reads it every run and fans it
  out to `runshim.write(python_launcher=)` (interpreter-only `_SH_PY`/`_CMD_PY`
  shim pair — nothing exe-shaped, grep-tested in
  `tests/test_launcher_mode.py` + dummyrepo S12) and to every wire module's
  `install(root, python_launcher=)` (copilot hook bash/powershell, kiro
  MCP `command = "python3"|"py"`, git commit hooks — user-level files carry
  interpreter commands instead of `paths.cage_bin()`; claudewire accepts and
  ignores the kwarg, its files reference the shim). `CAGE_RUN_PYTHON=1` is the
  runtime-only override on the standard shim (never read by cage Python code —
  it lives in the shim text). `paths.cage_command_tail` also recognizes
  `python3 -m cage …` / `py -3 -m cage …` so mode switches collapse stale
  entries. Doctor's `portability` check names the mode + warns on policy↔shim
  drift; `cage query restricted-env` explains the tiers.
  All writes are idempotent and byte-identical (two teammates running `cage setup`
  must not churn a committed diff). **No skill/steering/pointer asset ships** — the
  rendered assets and `tools/skillgen` went with the hook machinery; `pointers.py` and
  `setupcmd.py` no longer exist. Capture is the all-agent sweep
  (`paths.cage_import_all`), reached by `cage import` / capture-on-read, so any one
  wired agent meters the whole stack with no hook.
- **Wiring liveness** ([wiringscan.py](cage/wiringscan.py), v0.32.0) — is an installed
  artifact's cage command still a command? A wiring artifact written before a verb was
  renamed still names the OLD verb, so it exits 1 — and because hook/shim output goes
  nowhere and both shims fail open to `exit 0`, a dead verb is indistinguishable from
  cage not being installed at all. A real machine's `bin/graphify` probed a pre-rename
  verb and silently exec'd the unmetered binary for 9 days while `cage doctor` reported
  OK, because the interceptor check tested existence + PATH, not liveness — the root
  cause behind F1's empty receipts. **The detector is the live parser
  (`cli.build_parser()`), never `verbmap.REMOVED`** — the parser is the same code the
  CLI runs, so it's ground truth for "will this exit 1"; `REMOVED` only supplies the
  replacement tail for the fix-hint. The distinction is load-bearing: a verb deleted
  outright rather than renamed (`cage adopt`) is dead, still installed on real
  machines, and **absent from `REMOVED`** — a grep against it would miss the artifact
  entirely. Scanning covers **user-level** artifacts too (`~/.copilot/hooks`,
  `~/.codex/config.toml`, `.git/hooks`, the global skill/prompt/steering copies) — both
  real-world failures were user-level, so a check that skipped them would miss its own
  reason to exist — and is **read-only and side-effect-free by construction**: nothing
  is ever executed, no `cage import` runs. Severity is tiered: a dead **wired** command
  is a doctor failure (capture is silently off); a stale **asset** (skill/prompt/
  steering prose) is advisory only (the agent sees a wrong verb, errors, adapts) and
  never gates the `report` footer. `cage setup` heals a dead verb via `verbmap.REMOVED`
  alongside its existing path migration, and refreshes a stale `bin/graphify`;
  idempotent, foreign (non-cage) artifacts are never touched, and a dead verb with no
  known replacement is reported, never guessed at. `cage query stale-wiring` explains
  the mechanism; `cage doctor`'s `wiring` check names each fault and its fix.
  `cage doctor --wiring` (v0.34.0) renders the same scan as a browsable per-artifact
  inventory — scope + agent + status (current/stale/dead/foreign) + a per-agent
  fully/partially/not-wired/needs-healing verdict, never forking the liveness logic;
  `cage query wiring-inventory` explains it.
- **The graphify interceptor is a TWIN PAIR against ONE written contract**
  ([docs/adr/0008_graphify.md](docs/adr/0008_graphify.md), v0.38.0) — `data/shims/graphify`
  (POSIX sh) and `data/shims/graphify.cmd` (Windows). Windows resolves a bare name only
  through `PATHEXT`, which has **no extensionless entry**, so the sh shim alone could
  never be *found* there and the shim capture route was structurally absent. The
  contract is binding on both: **B1–B8** (re-entry guard both directions · PATH scan
  skipping *every* interceptor · self-identification by **content, never filename** ·
  no-real-binary ⇒ **127**, never a bare-name fallback · meter only if `cage data
  graphify --help` succeeds · transparent passthrough · no leaked state · a bounded
  walk) and **D1–D7**, the divergences that cannot be removed — chiefly **cmd has no
  `exec`**, so the real binary runs as a *child* (`call` + `exit /b` on its own line;
  the one-line `& exit /b %ERRORLEVEL%` form expands at parse time and reports the wrong
  code). **Change a twin ⇒ change the contract, the other twin, and
  `pathshim._INTERCEPTOR` together** — the marker set has three copies by necessity
  (sh `grep -E`, cmd `findstr /C:`, Python regex) and drift there silently disables
  liveness detection *and* re-enables the stacked-shim recursion. `cage setup` installs
  **both twins on every OS** (a committed `bin/` must be byte-identical across
  machines); `adoptcmd.refresh_shim` *completes* the pair when either exists — the
  POSIX→Windows upgrade path. The one enumeration is `paths.GRAPHIFY_SHIMS` /
  `graphify_shims()`, shared by the writer and every read surface so none can see only
  one twin. A root carrying only the twin **this OS cannot resolve** is a doctor
  *failure*, not a green tick: that is F1's lesson applied to a new OS. **Hand-paired,
  not templated, on purpose** ([ADR 0007](work/archive/adr/0007-graphify-twin-pair-hand-paired-not-templated.md)
  — templating stays off the table until a *third* interceptor exists and shares a
  syntax family with an existing one). Known gap, stated not half-fixed: under
  `--python-launcher` there is no `cage` on PATH, so **neither** twin meters (contract
  B5) — `cage doctor`'s `launcher-gap` check names it (GF-LAUNCHER,
  [work/restricted-environments.md](work/restricted-environments.md)); a fix must move
  both twins together.
- **graphify savings file from FOUR of five agent surfaces, and the fifth says why not**
  ([graphifytx.py](cage/graphifytx.py), `cage query graphify-coverage`) — the interceptor
  above is invocation-gated, so every store-side route exists to catch what it misses. One
  counterfactual, one id scheme, one ADR-0005 deferral: claude transcripts · copilot **CLI**
  `events.jsonl` · copilot **VS Code** `chatSessions` (`run_in_terminal` → `commandLine.original`
  + `cwd.path` + output) · kiro **CLI** `conversations_v2` (`execute_bash`, [ADR 0009](work/archive/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md)
  — bodies read **transiently**, hashes only, the one carve-out on that store's key whitelist).
  **Kiro IDE structurally cannot** (its store persists no assistant output — 26/26 empty
  completions when probed) and that is **named in `cage doctor` + the explainer, never a
  silent zero**. `GRAPHIFY_COVERAGE` is the ONE table both read.
  **Two refusals are load-bearing, not gaps:** kiro caps tool stdout at ~2000 tokens, so a
  truncated answer under-counts `actual` and files **nothing** (a lower confidence would
  dress up a number wrong in a known direction); and the VS Code guard matches **no marker
  string** — all 23 `truncat` hits across 1,132 real parts were the command's own clippy
  output, so it keys only on a missing output carrier or a non-zero exit.
  **The cursor is right for calls and wrong for savings** — a route shipping after a session
  was ingested can never see it again — so `cage import --rescan-graphify` walks the full
  match set, detection only, idempotent.
- **CI has a graphify axis (CI-GF, v0.38.0)** — `python-package.yml`'s `build` job is
  the `absent` leg (cage must never *require* graphify); the `graphify` job is the
  `present` leg on all three OSes: pinned real graphify (PyPI **`graphifyy`**, not npm),
  a graph over `tests/fixtures/cicorpus/`, and a **bare `graphify query` through the
  platform shell** asserting a savings row lands. It costs **$0** — graphify is AST-only.
  Checks live in `tools/cigraphify.py` (build-time only, never in the wheel). Two rules
  it encodes: the corpus must stay **large enough that a query is cheaper than the files
  it cites**, or every run is honestly `unmeasurable` and the leg asserts nothing while
  passing; and `graphify query` emits its lines in a **different order every run**, so
  comparisons are by content, never bytes. It skips loudly (never fails) if the pinned
  install flakes — flake-immunity over coverage; `build` is the gate that always runs.
- **§8 features:** `quality.py`, `regression.py`, `recommend.py`, `forecast.py`.
- **Tier-0 savings:** `compress.py`, `responsecache.py` (emit receipts).

## Integrations

- **AlphaForge Anton (Orff)** — first consumer. Anton's `LLMGateway` records each
  `ProviderResponse` via a fail-open `cage_meter` adapter (`anton/docs/cage.md`).
  Cage is wired there as an optional `[cage]` extra (uv path source).

<!-- cage:start -->
## Cage — LLM usage & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Per chat: `cage insights chats` · graphify savings: `cage insights graphify` · per commit: `cage insights commits`
- Tokens and credits are recorded as *counts* — cage measures usage, never cost.
- The ledger carries token counts, never prompt text — PII-safe by construction.
- Edit pipeline order / capture switches in `.cage/cage.toml`.
<!-- cage:end -->

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
