# CLAUDE.md — Context for Claude Code

**Cage** — a *flux*: a deterministic attribution ledger for LLM token traffic and
tool savings. In the family alongside **fux** (decisions→rules). `$0`, stdlib-only,
deterministic, independent of any AI tool.

Design of record: [docs/PLAN.md](docs/PLAN.md). Read it before changing
the substrate contract or the attribution engine.

Maintainer handoff: [docs/INTERVIEW.md](docs/INTERVIEW.md)
— the outgoing model's exit interview (intent, scar tissue, how to work with the
human). **Every agent maintaining this repo reads it after this file; a departing
maintainer appends its own lessons there.** It is context, never spec — where it
disagrees with this file or the plan, this file and the plan win.

**Build log: [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) — always maintained.** After
**every small milestone** (a green checkpoint, a commit, a phase step — not just a
release), append an entry: date · milestone · what was implemented · files touched ·
test status · next step. Create the file if absent; newest entries first. It is a
running log of *what is actually built*, never spec — where it disagrees with this
file or the plan, they win. An agent ending a work session without updating
IMPLEMENTATION.md has left the milestone unrecorded — treat that like a missing
changelog entry.

## Architecture (the one-way data flow)

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks}-YYYY-MM.jsonl  (+ legacy *.jsonl)
        (meter, plan §5)                      │           · provenance.jsonl (unpartitioned buffer)
                                              ▼  derive ($0, no model)
  cage.toml (order/budgets/routing)      → report · attrib · matrix · budget · roi
  + prices.toml (model prices, [credits])   · compare · verdict · why · origin · chats
                                             + --scope (monorepo slice) · --team · ledger-sync (§3.6)
```

Prices live in `prices.toml`; a legacy in-`cage.toml` prices block still reads via the
fallback. **Vendor facts move, routing decisions stay.**

Long-lived logs are month-partitioned (writers append to a dated shard chosen from
the row's own `ts`; readers glob + concatenate, legacy single files still read; `--since`
skips below-cutoff months). provenance.jsonl is a local buffer only — canonical storage
is refs/notes/cage-provenance, written by CI alone (plan §3.5). The calls/receipts/tasks
rows likewise aggregate to refs/notes/cage-ledger (CI-sole-writer) for the team view
(`--team`, plan §3.6.3; [ADR 0001](docs/adr/0001-ledger-team-aggregation-notes-not-external-sink.md)
— why a git ref, not an external sink).

- **Substrate** ([schema.py](cage/schema.py)) — `make_call` / `make_receipt` stamp
  ids + validate the closed enums. Rows are plain JSON. Prompt bodies are never a
  field (counts only). Change here = change the contract; update the plan §3. Calls/
  receipts also carry an additive optional `scope` (top-level changed dir, same PII
  guard as tasks; empty = the legacy contract, plan §3.6.2); calls additionally carry an
  additive optional `project` (working-dir basename, same PII guard; empty = legacy) — a
  *derived* `cage report --project` view, deliberately distinct from `scope`'s monorepo
  axis (plan §3.7). The long-lived logs are month-partitioned behind
  `ledger.append_row`/`read_kind` (plan §3.6.1).
- **Config file** ([paths.py](cage/paths.py) `Footprint.policy`) — the project config
  is `.cage/cage.toml` (the policy layer). It was `policy.toml` through v0.35; the
  rename is **non-breaking** — `policy.toml` is still read as a fallback and migrated
  to `cage.toml` on `cage setup` (idempotent, non-destructive), and with both present
  `cage.toml` wins (`cage doctor` names the ignored leftover; a one-line stderr warning
  fires at load). The resolved name lives in **ONE place**, `Footprint.policy`; writers
  (`pricestoml`/`policysync`) and `cleanup.NEVER` (which protects **both** names) follow
  it. Bundled default `data/cage.toml`, read-only at runtime. `cage query config-file`
  explains it.
- **Prices file** ([paths.py](cage/paths.py) `Footprint.prices`) — model prices are a
  **vendor rate card** with the opposite lifecycle to policy (replaced wholesale by
  `cage prices sync`, never hand-preserved), so they live in `.cage/prices.toml`:
  every `[prices.<provider>.<model>]` row, `[credits]`, and the `[meta]
  prices_version/prices_date` counters. `cage.toml` keeps the **routing decisions**
  (`[alias]`, `[tools.<tool>] price_at`) and `[meta] cage_version/policy_version` —
  **vendor facts move, routing decisions stay.** The split is **non-breaking**:
  `prices.toml` → legacy in-`cage.toml` prices → bundled default, resolved in ONE
  place (`Footprint.prices`); `cage setup` migrates a legacy inline block
  **money-neutrally** (idempotent, non-destructive); both present ⇒ `prices.toml`
  wins (`cage doctor` names the shadowed block, one-line stderr warning at load).
  `policy.load` still returns ONE merged dict, so every pricing consumer
  (`prices.call_usd`, `policy.price_match`, `convert`, `receiptprice`) is unchanged.
  `[meta]` splits **per key** — a mis-split silently stops a staleness check firing.
  `cage query prices-file` explains it.
- **Constants** ([constants.py](cage/constants.py)) — the *third audit layer*. Cage
  keeps its numbers in three places, never mixed: **contract** = the enums in
  `schema.py`; **policy** = user-economics in `cage.toml` (routing) + `prices.toml`
  (the vendor rate card half of that layer); **constants** = code
  heuristics not meant as config but that must be reviewable (`CHARS_PER_TOKEN`,
  `TOKENS_PER_MILLION`, `MAX_MATRIX_TOOLS`, `METHOD_TRUST`, `DEFAULT_CONFIDENCE`,
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
- **Attribution** ([attribution.py](cage/attribution.py), [matrix.py](cage/matrix.py))
  — the differentiator (plan §4). Marginal-by-fixed-order; a reconstructed
  counterfactual cell is `modeled`/`estimated`, never `measured` (only the recorded
  run is an invoice). `cage demo` must keep reproducing the plan's §4.4 tables.
- **Gross vs net savings** ([netsaved.py](cage/netsaved.py)) — **every `saved` in the
  ledger is GROSS**: `raw_alternative − actual` is the *avoided read cost* and excludes
  the cost of **using** the tool (the invoking turn, a hook's injected context), so a big
  `saved` and a session that cost more are both true
  ([finding](docs/regression/2026-08-01-finding-saved-is-gross.md)). Two rules follow.
  (a) The word `gross` appears on every surface that prints the number — report/attrib/
  roi/overview/ceiling, text **and** CSV (`gross_saved_*`) — from ONE phrasing,
  `netsaved.GROSS_NOTE`; never re-word it per view. (b) `netsaved.by_tool` nets it at
  **task level only** — per-query is impossible, shim receipts carry a `task` but no
  `call`, and inventing that link is forbidden. The attributable-cost rule is the **±120s
  receipt-window union** (`constants.NET_ATTRIB_WINDOW_S`; symmetric because the invoking
  turn precedes the receipt and the consuming turn follows it), a deliberate *lower
  bound*. Net is `modeled` at `NET_SAVED_CONFIDENCE` — **never `measured`** — and a task
  with no in-window call is *uncovered*: its net reads unavailable, never `= gross`.
  `cage insights verdict` therefore prints **`SAVING (GROSS)`** when no complete
  cost-of-use figure exists, but still asserts a bare **COSTING** — the omitted term is
  ≥ 0, so only the positive side can be wiped out by it. `cage query gross-vs-net`
  explains it; FORMULAS §2.1/§2.1a is the spec.
- **Unit→USD** ([convert.py](cage/convert.py)) — the single dispatch for a receipt's
  `saved` in dollars: `usd` passthrough · `tokens` at model price · `ms`/`gco2` → `$0`
  (`minutes` was a unit through v0.35 and is now excluded, never priced). `roi`/`attribution` route through it (one place
  unit semantics live). A **call-less token receipt** (graphify/fux shims — a `task`
  but no `call`) prices via the ladder in [receiptprice.py](cage/receiptprice.py)
  (plan §4.5): `[tools.<tool>] price_at` (managed by `cage prices route-tool <tool>
  --to <provider>/<model>`, `--remove` to delete; dangling targets write with a
  warning, never priced) → dominant task model (ties: tokens_in → call count →
  lexicographic) → loudly UNPRICED with a **runnable** per-tool fix line. One
  implementation; roi/report/attrib/verdict thread the once-per-view `build()` join
  through it; rung footnoted in text, `priced_via` in CSV; USD keeps the receipt's
  method. Linked receipts never enter the ladder.
- **Per-call cost** ([prices.py](cage/prices.py) `call_usd`) — `report`/`budget`
  **recompute** each call from `tokens × policy` at derive time, falling back to the
  stored `est_cost_usd` only when the model is unpriced. A token-only meter (the
  transcript meter never sets `est_cost_usd`) thus still costs out, and a
  self-costing provider Cage can't tokenize keeps its figure. Derive-time only — the
  ledger is never rewritten. A call prices only if `(provider, model)` is in the
  table; the transcript meter stamps `provider="anthropic"`, so that key must carry
  the Claude rows (the bundled `data/cage.toml` does; a project policy must too).
- **The Tier-1 human axis is GONE (v0.36)** — `human.py`/`humanview.py`/`trend.py`/
  `attention.py`, `cage human`, `cage insights trend`, `matrix --human`,
  `calibration --human`, `[human.*]`, `CAGE_HUMAN_RATE`, `IDLE_CAP_MINUTES`, the
  `gap_ms` call field and the `minutes` unit were all removed together, substrate
  included — a clean amputation, reconsidered from scratch after the release, never a
  `# v2:` stub. **Do not reintroduce any part of it without a proposal doc.** Two
  things survive and must not be confused with it: (a) provenance `origin="human"`
  ([origin.py](cage/origin.py), `schema.ORIGINS`) is *authorship*, a different
  question and a different enum; (b) `cage task outcome` / `cage task quality` never
  belonged to the axis — they sat in the `human` command group by filing accident and
  moved to the `task` group; `outcome` is the **task-close verb** the whole
  cost-impact surface (`compare`/`estimate`/`calibration`) depends on. **Old ledgers
  still read**: a pre-0.36 `gap_ms` call or `tool="human"`/`unit="minutes"` receipt
  parses fine and is excluded from money views by `report._is_legacy_human`, with the
  exclusion **counted and footnoted** on `cage report` — silently dropping it from a
  total was the one option ruled out. `cage query savings-axis` explains it;
  `tests/test_legacy_ledger.py` pins it.
- **Task record** ([tasks.py](cage/tasks.py)) — `tasks.jsonl`, one row per task
  (last-write-wins by `id`), git-snapshotted at task close (SessionEnd / `cage
  outcome`). **Shelled out to git, never imported; fail-open** (non-repo/detached ⇒
  omit fields). PII guard: SHA + diff *counts* + top-level dirs only — never the
  commit message, author identity, or file paths.
- **Provenance (authorship attribution)** ([schema.py](cage/schema.py) `make_provenance`,
  [originrecord.py](cage/originrecord.py) write side, [origin.py](cage/origin.py) read
  surface, [notessync.py](cage/notessync.py) distribution, [verifycmd.py](cage/verifycmd.py))
  — *who wrote which files in which commit* (plan §3.5), a fourth append-only file
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
  messages, paths validated repo-relative at construction time.
- **Cost-impact surface** ([taskgroup.py](cage/taskgroup.py), [compare.py](cage/compare.py),
  [estimate.py](cage/estimate.py), [calibration.py](cage/calibration.py),
  [verdict.py](cage/verdict.py) — plan §4.7–§4.8, §8.8) — the closed-task join
  (task-id first, session-window fallback; overlaps → smallest task id) yields
  *observed* stack signatures (`human` excluded; empty ⇒ `agent-only`). `cage
  compare`: **measured** group totals (`prices.call_usd` repriced), the delta always
  `estimated` + the observational caveat. `cage insights estimate`: a `modeled` median+IQR
  band from exact-key history; `--record` stamps additive `est_*` fields **plus the
  token band bounds** on the *open* task row (plan §3.4) so `cage insights calibration` can
  score in-band hits against the band as recorded — that **measured hit-rate is the
  only confidence source; the estimator never self-reports**. `cage insights verdict <tool>`:
  a pure composer over attrib/roi/regression/quality + break-even — computes
  no new statistics, refuses (`INSUFFICIENT DATA`) over approximating. The min-n
  gates `MIN_COMPARE_N`/`MIN_ESTIMATE_N` live in `constants.py` and **block** —
  below them the command explains, never numbers. Task `label` (via `cage task outcome
  --label`) is one validated token, never a path or free text. Diagnostics: `cage
  doctor --bundle` ([doctorbundle.py](cage/doctorbundle.py)) writes one redacted,
  counts-never-content archive; every capture-path swallow-site logs under
  `CAGE_DEBUG=1` — audited by `tests/test_debug_coverage.py` ("fail-open but never
  silent" is tested, not aspirational). Validation harness: the fixture corpus
  `tests/fixtures/transcripts/` (4 agents × cli/vscode, exact expected rows,
  VS Code stand-ins flagged `UNVERIFIED-FORMAT`) + `python -m tools.dummyrepo`
  (S1–S18 scenario runner, S10 retired with the human axis; build-time only, never in the wheel).
  P5 fleet study ([machine.py](cage/machine.py), [study.py](cage/study.py), plan
  §4.9): opaque random machine id (**opt-in by enrollment** — unenrolled ledgers
  stamp nothing, byte-identical legacy), recorded phase markers in
  `ledger/study.jsonl` (resolved per machine against its own clock), one-file
  bundles (`cage data export --study` → `cage import bundle*.zip`; merge by row
  identity — calls/receipts by id, tasks/markers by whole-row so task updates
  survive), the **machine-day** as sample unit, paired delta `estimated` with the
  work-mix caveat, gate = `MIN_COMPARE_N` machines-with-both-phases (blocking).
- **CSV output (plan §3.9)** ([csvout.py](cage/csvout.py)) — `--csv` on
  report/attrib/roi/compare/`study report`/calibration, plus raw rows via
  `cage data export --csv calls|receipts|tasks`
  (`exportcmd.RAW_CSV_FIELDS`; `--format csv` = legacy `--csv calls`). One shared
  data structure per view feeds text AND csv (`render_csv` beside each
  `render_*`) — never compute twice. LF pinned (`lineterminator="\n"` +
  `newline=""` writes), RFC-4180, method/match tags are columns, refusals/
  caveats/UNPRICED survive into rows. CSV is one-way REPORTING — never an import
  source; the fleet bundle stays jsonl. MCP mirrors it (`format: csv` on
  report/attrib/roi).
  **Text-output contracts: the golden fixtures** (`tests/fixtures/goldens/`,
  asserted by `tests/test_output_spec.py`) are the per-command, per-state output
  contract. Change a rendered shape ⇒ re-bless the golden (`CAGE_BLESS_GOLDENS=1
  pytest tests/test_output_spec.py`). (The generated `docs/cli-output-spec.md` and
  its `tools/docgen` generator were removed in the hookless rebuild; the goldens
  remain the contract.)
- **OTel GenAI export** ([otelout.py](cage/otelout.py), plan/handoff
  `docs/archive/v0.39-otel-export.handoff.md`) — `cage data export --otel`, a third
  one-way REPORTING format beside `--csv`/`--study` (never an import source; the
  fleet bundle stays jsonl). Calls map to `gen_ai.system` / `gen_ai.request.model` /
  `gen_ai.usage.input_tokens` / `output_tokens` / `gen_ai.client.operation.duration`
  (omitted, never a fabricated zero, when `latency_ms` is unknown). **The GenAI
  semantic conventions are pre-stable** (own repo, no 1.0, names can still change) —
  the targeted version is pinned in `constants.OTEL_SEMCONV_VERSION` and stamped in
  every document's `cage.meta` block; a spec bump is a deliberate, changelog'd
  change, same discipline as `prices_version`. **Receipts/savings have no GenAI
  equivalent** — cage-namespaced under `cage.savings[].cage.*`, never an invented
  `gen_ai.*` name; `cage.saved` is GROSS, `cage.saved_usd` prices through the same
  `receiptprice` ladder every other view uses and is omitted (never `$0`) on an
  UNPRICED refusal or a non-money unit; `cage.method` always survives. `dependencies
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
  manifest uses. **The one law amendment**: `manifest.py`'s "never read by a derived
  view" contract gains a single scoped carve-out — a title is joined from
  `imports.jsonl` for a **display label only**; deleting the manifest moves **zero**
  numeric cells (pinned by `tests/test_chats.py`). Kiro-IDE's constant session id
  already collapses every run into one row (`kiro (no session identity)`, never a
  fabricated per-chat identity); kiro-CLI conversations are `credits` rows and don't
  appear here. Top-20 by `tokens_in`, `--all` lifts it (footnoted cut, no silent
  caps); CSV never truncated. Local-only by construction — no `--team`, no MCP tool.
  `cage query chats-view` explains it.
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

## Must-Know Rules

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
  not a capture-quality one — see docs/archive/*-codex-removal.handoff.md).
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
  [docs/CLI.md](docs/CLI.md) is the complete command reference and
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
  `cage prices list` and *copied into every newly scaffolded project*, so a stale literal
  propagates. Derive it from `cage.__version__` (the `manifest.py` pattern), never
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
  (`policy._bundled`); just confirm `tests/test_prices_split.py`'s drift-guard test is
  still green (the checklist item that was missing when it drifted eleven releases).
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
- **Pricing is managed** ([pricescmd.py](cage/pricescmd.py), [pricestoml.py](cage/pricestoml.py),
  plan §3.3) — `cage prices list|unpriced|set|alias|sync` manages the project
  `[prices]`/`[alias]` tables; writes are text surgery (in-place value edits marked
  `# cage:custom`, or a deterministic cage-managed block) — never a whole-file rewrite.
  Writes are a **two-file** split: `cage prices set`/`sync` write **`prices.toml`**
  (vendor facts); `alias`/`route-tool` write **`cage.toml`** (routing decisions).
  `cage prices sync` replaces the cage-managed region of `prices.toml` while
  `# cage:custom` rows survive; `cage policy sync` is unambiguously `cage.toml`-only.
  The bundled defaults are read-only at runtime and ship split as `data/cage.toml`
  + `data/prices.toml` (both resolve from the zipapp via `paths.bundled_data()`).
  `policy.price_match`
  resolves exact → alias → family over *normalized* ids (`copilot/` route-prefix strip —
  a closed list; `.`↔`-` folding; effort suffixes low/medium/high/max drop); a normalized
  match renders `family`, an alias renders `alias`, **never `exact`** (method law), and a
  dangling alias is `none` — a router is never silently defaulted. `policy.load` merges
  `prices`/`credits`/`alias` two levels deep (per provider *and* model). The bundle
  carries `[meta] prices_version` (source URLs cited per row); `doctor`/`prices list`
  recommend `cage prices sync` when the bundle is newer — never auto-applied. Repricing
  is derive-time; UNPRICED prints a ⚠ summary on report/overview/compare/study report.
  cage never fetches a price — research is build-time/user work, not a code path.
- **Export imports everything first** (plan §3.7) — `cage data export` (plain and `--study`)
  runs the full all-agent sweep before emitting (`--agent` filters output only);
  `--no-import` flag > `CAGE_CAPTURE` env > `[capture] import_before_export` policy;
  fail-open; the study manifest records `refresh: {ran, new_calls}`.
- **State cleanup is a closed allowlist, and deletion is manual-only (v0.37)**
  ([cleanup.py](cage/cleanup.py), plan §3.6.4) — aged debug.log/hooks-seen rows, stale
  `pending-*` buffers, orphan cursors, `*.tmp`; never ledger/ (tool savings included —
  see below), cage.toml (and legacy policy.toml), prices.toml, machine.json,
  study.jsonl, limits.json (by construction). **Deletion only ever happens via an explicit `cage data cleanup
  --apply`**, which runs regardless of `[cleanup] enabled` — an explicitly-typed command
  is always honored. The auto path (piggybacked on `importcmd.run`/session-end,
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
  multiple viable options, write a *compare doc* in [docs/compare/](docs/compare/)
  **first** — debate, matrix, grounded references, a proposed verdict Arpit accepts
  or overrides, and a reopen-trigger — before committing to a plan. This is a
  standing rule. An idea worth keeping but not being built now gets a *proposal
  doc* in [docs/proposals/](docs/proposals/) (`status: proposed`, same rigor) —
  parked, not lost; it graduates to a compare doc or plan entry when picked up
  (and keeps a `# v2:` idea out of the code). A settled fork graduates to a plan
  entry and, on ship, an ADR; the compare doc stays as the evidence behind it.
- **Research gets its own doc, always — in [docs/research/](docs/research/).**
  Whenever a session does research — an external-source investigation, a store/format
  probe, a competitive or ecosystem survey, anything whose output is *findings rather
  than a decision* — the findings are written up as a separate dated research doc in
  `docs/research/` in that same session, never left as chat-only knowledge or inlined
  into a proposal. Research docs are **evidence, not spec**: proposals, compare docs,
  plan entries, and IMPLEMENTATION.md entries *link* to them as their grounding
  (the same role `regression/` plays for measured evidence — research/ is the
  sourced-findings twin). Cite sources (URLs, code paths, versions probed) so a
  future agent can re-verify. First occupant:
  [research/copilot-vscode-token-sources.md](docs/research/copilot-vscode-token-sources.md).
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
- **A proposal has a lifecycle too — parked in `proposals/`, ARCHIVED once
  IMPLEMENTED.** `docs/proposals/` must read as *ideas not yet built*, exactly as
  `docs/` root reads as *work not yet done*. The four states:
  **proposed** (`status: proposed`, awaiting accept or a trigger) → **picked up**
  (a handoff/prompt pair is written; the proposal gains a one-line pointer to it and
  stays put — it is still the rationale) → **implemented** (the work is built and
  green) → **archived**.
  **The change that implements a proposal must, in that same change:** (1) move it to
  `docs/archive/vX.Y-<name>.proposal.md`, (2) prepend the archive header naming the
  version and **where the living spec now lives** (contract, ADR, plan section — a
  built proposal is never the spec), (3) record the outcome in
  [IMPLEMENTATION.md](docs/IMPLEMENTATION.md), (4) move its index entry in
  `proposals/README.md` to the **Graduated** list with links to the archived proposal
  and the living spec, and (5) carry forward anything still unbuilt as its own
  proposal or OPEN-WORK item. A **declined** proposal is treated the same way, with
  the decision and decider in the header; a *superseded* one names its successor.
  **Where an archived proposal disagrees with the living spec, the spec wins** —
  implementation routinely corrects the proposal that motivated it, and that
  correction is the valuable part (see
  [v0.38-windows-graphify-interceptor.proposal.md](docs/archive/v0.38-windows-graphify-interceptor.proposal.md),
  wrong on both the packaging source and the recursion guard).
  An implemented proposal still sitting in `proposals/` is a bug of the same class as a
  ticked-but-present OPEN-WORK item: it inflates the queue of open ideas and makes the
  directory lie about what is still on the table.
- **Handoff/prompt docs have a lifecycle — active in `docs/`, archived once
  IMPLEMENTED.** New feature work is specced as a pair: `docs/<feature>.handoff.md`
  + `docs/<feature>.prompt.md`. While the work is unbuilt they live in `docs/` root
  and are listed under *Active work* in `docs/README.md`. **The change that
  completes the work (suite green — NOT necessarily a release; cage often builds
  several features before committing/tagging) must, in that same change: (1) move
  the pair to `docs/archive/vX.Y-<feature>.{handoff,prompt}.md` naming the version
  the work rides, (2) prepend the one-line archive header — say "implemented for
  vX.Y (unreleased)" when the release is still pending, (3) link them from that
  version's CHANGELOG entry ("Built from: …"), (4) update the `docs/README.md` and
  `docs/archive/README.md` indexes, and (5) promote any still-true design content
  into the living design doc or plan section — the archive is history and must
  never be cited as current spec.** An implemented feature whose handoff/prompt
  still sits in `docs/` root is a bug, same class as a missing changelog entry:
  `docs/` root must read as *work not yet done*, so the next agent can trust it as
  the live queue. Archive-on-implement (not on release) is deliberate — it keeps
  that queue honest across the long uncommitted stretches this repo works in.
- **Every prompt doc declares the model tier that should execute it.** A
  `docs/*.prompt.md` starts with a `**Model:**` line naming the tier and the
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
  Directly under the `**Model:**` line, a `docs/*.prompt.md` carries a
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
    [IMPLEMENTATION.md](docs/IMPLEMENTATION.md), `docs/archive/` and the code decide
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

**Every change updates the docs in the same change** — this holds whether or not
the change touched code; a decision, a scope change, or a plan is documentation
too. A task is not done until the docs are true. When a doc goes stale, fix it on
contact, not later. The maintained set, each with a standing owner-trigger (the
freshness tracker is [docs/DOC-REGISTRY.md](docs/DOC-REGISTRY.md) — a change that
fires a trigger updates the doc *and* bumps its row):

- **[docs/OPEN-WORK.md](docs/OPEN-WORK.md)** — the **single plan of pending work**, and
  the only place unfinished work is tracked. `docs/` root carries no loose
  handoff/prompt pairs; a pair is created only when a phase there is picked up, and
  archived on implement.
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
  [IMPLEMENTATION.md](docs/IMPLEMENTATION.md)** (what was built · files · tests · next
  step) **and, if it produced evidence, publish it to [regression/](docs/regression/)**.
  Carry forward anything still live — a residual limit, an open decision, a follow-up —
  as its own item rather than losing it with the parent. A ticked-but-present item and a
  deleted-but-unrecorded one are the same bug in opposite directions: the first inflates
  the queue, the second loses the history.
  **Never trust its own status markers as ground truth when reconciling** — a ✅ in a
  plan file is an assertion, not evidence. Verify against `docs/regression/`,
  `docs/archive/`, `IMPLEMENTATION.md`, and the code before declaring an item
  pending or done. On 2026-08-01 this file listed two already-built items as
  pending precisely because its markers had gone stale.
- **[docs/IMPLEMENTATION.md](docs/IMPLEMENTATION.md)** — the build log. Append at
  **every small milestone** (green checkpoint, commit, phase step): date ·
  milestone · what was built · files · test status · next step. Green/in-progress/
  failed/blocked all get an entry — an execution that skips it left the milestone
  unrecorded. Newest first. It lives under `docs/` alongside the plan and the other
  maintained docs.
- **[docs/WORKLOG.md](docs/WORKLOG.md)** — the running per-session handoff. Append
  every substantive exchange: asked · done · decided/open · single next step.
  Newest first. **This covers every working surface — Claude Code executions AND
  Cowork/chat strategy sessions alike**: a decision made in conversation (a scope
  call, a directive, a plan revision) is worklog material even when no code moved;
  the agent in that conversation appends the entry before the session ends.
- **[docs/INTERVIEW.md](docs/INTERVIEW.md)** — the **exit interview**: notes from
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
- **[docs/PLAN.md](docs/PLAN.md)** — the design of record (the PLAN).
  Update before building; keep its status truthful when scope or a contract changes.
- **Every plan doc opens with a phase index.** The first section after the title
  block of any plan (`docs/*plan*.md`, and PLAN.md's own major sections) is a
  numbered list of every phase/step with **one line each** — what it does and its
  gate/status — so a reader (or an executing agent) sees the whole shape before
  any detail, and a stale plan is spottable at a glance. Existing plans gain the
  index on contact (the fix-on-contact rule), new plans start with it.
- **[docs/shim-contract.md](docs/shim-contract.md)** — the graphify interceptor
  behaviour contract: one spec, two twins. Update in the same change as **any** twin
  edit, marker-set change, or new tool interceptor (every future one implements this
  same shape). Two implementations of an unwritten contract drift.
- **[docs/CLI.md](docs/CLI.md)** — **the complete CLI reference**: every command,
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
- **[docs/DOC-REGISTRY.md](docs/DOC-REGISTRY.md)** — the freshness tracker itself; a
  new maintained doc gets a new row, same change.
- **[docs/architecture-flow.mermaid](docs/architecture-flow.mermaid)** — the
  one-way data flow as a diagram; update when a stage/sink/read-surface changes.
  Linked from the README's *How it works*.
- **ADRs** authored from **[docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md)** — see
  *Decision records* below.
- **[docs/example/](docs/example/)** — copy-from contracts (cli · debug · setup ·
  toml-config), one per file; update the matching one when that surface changes.
- **[docs/research/](docs/research/)** — dated research docs, one per investigation
  (see the *Research gets its own doc* rule in Must-Know Rules): sourced findings
  that proposals/plan/IMPLEMENTATION link to as evidence, never spec.

Note: ALL-CAPS entry-point/tracker files (CLAUDE.md, CHANGELOG.md, README.md and
AGENTS.md at root; IMPLEMENTATION.md, PLAN.md, INTERVIEW.md, GLOSSARY.md, WORKLOG.md,
DOC-REGISTRY.md under `docs/`) carry no frontmatter; lowercase docs may.

**Documentation style — no large paragraphs.** Authored docs (guides, handoffs,
prompts, examples, ADRs, compare/proposal docs) are written in **short points**,
one idea each, roomy, takeaway first; keep paragraphs to 3–4 lines and use tables
for option/field comparisons. Fix a wall of text on contact — the docs law applies
to *form*, not just facts. (CLAUDE.md, the plan, and the design docs are the
deliberate exception: dense reference prose, packed on purpose.)

**Document size discipline — ⏳ TRIAL, expires 2026-09-01.** Four composing rules on
every authored doc. Full spec, worked examples and the fix procedure:
[docs/doc-size-discipline.md](docs/doc-size-discipline.md).

1. **Lead with the answer** — first ~5 lines say what's next, what's blocked, what
   changed. A reader who stops there has the useful part.
2. **One audience per doc** — a plan carries only what the *decider* needs; build
   detail → handoff/prompt, rationale → ADR/design doc, evidence → `regression/`.
3. **Evidence lives elsewhere, always** — state the claim, link the proof. Never
   inline the numbers or reasoning; `regression/`, `archive/`, `IMPLEMENTATION.md`
   and the ADRs already hold them.
4. **A hard budget** — a plan fits one screen (~40 lines); a table row is *genuinely*
   one line (≤120 chars). Over budget ⇒ move content out, never compress in place.
   **Reference docs (this file, PLAN.md, the design docs) are exempt from rule 4
   only** — dense on purpose; 1–3 still bind them.

**On 2026-09-01 this rule must be explicitly retained, amended, or removed — it
lapses if unreviewed**, so it cannot become permanent by neglect. Review criteria and
the retain/remove call live in the spec doc. Tracked in
[docs/DOC-REGISTRY.md](docs/DOC-REGISTRY.md).

**Every prompt/handoff also names the model tier** that should execute it, and
**every prompt doc carries a `Progress:` percentage** of that program's phases — see
the two prompt-doc rules and the Haiku/Sonnet/Opus rubric in *Must-Know Rules* above;
don't restate them, apply them.

## Decision records (ADRs)

Architecturally load-bearing decisions live as numbered ADRs in
[docs/adr/](docs/adr/), authored from [docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md)
— the durable *why* behind a design that a future agent would otherwise "fix" back. They are the standing record; cite them inline in this
file and in the plan at the rule they explain, the way a `plan §` reference is
cited. Current set: [0001](docs/adr/0001-ledger-team-aggregation-notes-not-external-sink.md)
(team aggregation via `refs/notes`, not an external sink) ·
[0002](docs/adr/0002-universal-capture-global-ledger-explicit-import-export.md)
(universal pull-based capture, global ledger, no OS scheduler). An ADR-worthy
decision is one where a wrong call is expensive to reverse and the reasoning isn't
obvious from the code — the substrate contract, the determinism/method law, the
`$0`/no-infra wedge, a capture-architecture choice. A one-line dated call goes in
the plan's decisions log instead.

**Every ADR carries a reference** (fux's rule) — a plan section, a paper, or a
concrete example that grounds *why*. An ADR that only asserts is incomplete.

**Every ADR ends with a `## Veto condition (when to revisit)`** — cage's own
device, and the anti-rot mechanism the rest of the fleet lacks. Three parts, each
load-bearing:

- **A falsifiable trigger, numbered where the decision is volume- or
  measurement-gated.** 0001's is the model: "single-digit GB/yr is fine; 100s of
  GB is not… **only then, and only with a named volume number**." A veto you can
  only reopen with a *measurement*, never an *argument*, pre-empts a future agent
  re-litigating a rejected option from first principles. Name **where** the change
  lands, too (0001: a new `export` command, notes stays default), so revisiting
  can't quietly become a redesign.
- **Contingent vs. invariant, labelled.** Split the parts that auto-revisit on
  evidence from the parts that are product values and move only by ratified
  reversal. 0002 does this explicitly: `project` capture returns when a client
  exposes the cwd; "no OS scheduler" is *not* volume-gated and changes only by
  reversing the ADR. Pretending every decision is revisitable-on-evidence lies
  about the ones that are values.
- **A "deliberately not taken" record** where there's meaningful negative space —
  an option considered and declined but *not* dogmatically rejected, with its own
  future threshold (0001's write-path size block). Records the omission as a
  choice, so the next agent doesn't mistake it for an oversight and doesn't ship it
  as a `# v2:` half-build.

Author every ADR from [docs/adr/TEMPLATE.md](docs/adr/TEMPLATE.md), which bakes in
the three veto devices; the two existing records ([0001](docs/adr/0001-ledger-team-aggregation-notes-not-external-sink.md),
[0002](docs/adr/0002-universal-capture-global-ledger-explicit-import-export.md)) are
the worked examples to copy.

## Dev

```bash
just test          # python -m pytest -q   (1503 tests; +10 Windows-only skips, +1 opt-in dogfood-age skip)
just demo          # seed §4.4 + print attrib/matrix
cage --version
```

## Regression & capture reports (do this after every testing run)

The sibling repo **cage-lab** (`../cage-lab`) is the out-of-tree, **black-box**
regression suite + per-agent capture labs (it installs the shipped `cage` and never
imports it; the in-tree suite can't see packaging, entry points, or bundled data).
Its numbers are validated against a hand-derived reference, and its labs slice the
**real** `~/.cage` ledger per agent to surface capture gaps.

**Rebuild manual: [docs/cage-lab/](docs/cage-lab/README.md)** — cage-lab is disposable;
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
per-machine-verified. (docs/OPEN-WORK.md §I.2a)

**Standing rule: after every cage-lab testing/capture run, publish the findings into
[`docs/regression/`](docs/regression/) here, dated** — so they live with cage, are
diffable release-to-release, and any agent working on cage can read them without the
test repo checked out. The runner does it automatically:

```bash
CAGE_REAL_LEDGER=~/.cage python ../cage-lab/labs/run_all.py   # writes docs/regression/<date>-{capture-report.md,.json,fixes.md} + latest-*
```

When you (an agent) run cage-lab by hand, still drop the dated report + a prioritized
`*-fixes.md` into `docs/regression/` and add the row to its README index. The latest
findings and their fix checklist are the input for the next round of cage fixes; see
`docs/regression/latest-capture-report.md`.

## Adapters & agents (one ledger, many surfaces)

Cage targets the **wire protocol**, so the meter and read surface are universal and
each agent only needs thin idiomatic wiring (`agents.py` orchestrates):

- **Meter:** `metering.py` (library), `proxy.py` + `usageparse.py` (any client you
  point a base URL at), `transcript.py` (Claude Code / Copilot CLI / Kiro session
  logs — `LOG_BEARING` is now all three of `agents.SURFACES`; Kiro's `tokens_generated.jsonl`
  is coarse so the proxy stays its higher-fidelity fallback). Capture is **pull-based and
  global** (plan §3.7): `cage import`/`cage data export` over a **resolved** ledger
  (`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`, via `paths.resolve_root`)
  is the universal path that works with no hooks and no project.
  **Kiro is the ONE exception to one-sink-per-sweep** ([ADR 0006](docs/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)):
  its *IDE* log is a single global file with no project/session/ts, so those rows are a
  **machine fact** and route to `~/.cage` — `paths.kiro_routed(root)` is the one predicate
  (`None` ⇒ no routing; an explicit `--ledger`/`CAGE_BASE` or `CAGE_LEDGER` collapses the
  two sinks, so the override wins for free). The leg (`importcmd._kiro_leg`) rebuilds every
  per-root object against the sink — own `seen`, cursors, lock, health, capture-log,
  manifest, `import_id` — and **completes before the sweep's own lock is taken**, so no
  process ever holds two import locks; it deliberately does *not* write the sink's
  `_last_import` (a partial leg is not a sweep, and it would throttle a later global
  capture-on-read) and does not run cleanup there. Capture switches compose as **AND**
  (project's *and* sink's). The summary line names the sink and the rollup counts only
  local rows — a total never includes a row that landed elsewhere. Kiro's *CLI* store gets
  the **opposite** fix: `conversations_v2` is keyed by cwd, so it is read scoped to the
  project **tree** (`paths.kiro_cli_workspace`, prefix-matched on a separator boundary,
  symlink-resolved — the real store keys `/tmp/x` as `/private/tmp/x`) and stamps the
  additive-optional `project` on the credit row. Pre-existing duplicated rows are never
  rewritten (append-only); the read side says why kiro is absent
  (`report.kiro_routed_line`, doctor's timeline, `--paths`, `cage query kiro-routing`)
  rather than showing nothing. Hooks are an optional
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
  read to once per run). **cage installs no OS scheduler** ([ADR 0002](docs/adr/0002-universal-capture-global-ledger-explicit-import-export.md)
  — a product invariant, not volume-gated) — no launchd/systemd/cron/
  schtasks, no `cage scheduler`; hands-off automation is the user's own cron/schtasks
  line calling `cage import` (the hint `render.scheduler_hint()` prints is OS-aware,
  never installed), and `cage data watch` is an optional foreground `sleep` loop they
  Ctrl-C (exit 130). Per-agent log locations live in **one registry**,
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
  plus `task outcome`/`task quality`, authorship
  (`origin`/`notes-sync`/`verify`, plan §3.5), and the ledger-scale surface
  (`--scope` / `--team` filters, `ledger-sync` into refs/notes/cage-ledger via the
  shared `mergeutil.union_by_id` core, plan §3.6).
- **The agent surface is a four-layer ladder, and L0 is the floor**
  ([archive/v0.41-agent-surface-layers.proposal.md](docs/archive/v0.41-agent-surface-layers.proposal.md);
  `cage query agent-layers`). **L0 hookless** (pull capture + interceptor + every CLI
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
  breadcrumb on `args_hash` (an **exact** key), turning `cage insights adoption`'s half A
  from agent-blind into per-agent. It does **not** fix half B — a graphify savings row's
  id folds in an *answer* hash no attestation can reconstruct, so `NO_LINK` stays
  structurally true and is not quietly narrowed. (b) **auto task-close** at the session
  boundary, on the **exact session id** — never the most recent task, never by proximity.
  (c) `budget.check`'s **first real caller**: `cage hook budget` exits `BLOCK` (2) when
  `[budgets] on_exceed = "block"`. **Auto-close never claims success:** `tasks.jsonl`'s
  `outcome` and the quality store (`.cage/outcomes.json`, ok|redo) are *different axes*,
  so the hook writes `outcome="auto"` — closed for compare/estimate/calibration,
  **invisible to `cage task quality`**. Stamping `ok` would inflate the success rate of
  every session that merely ended. **Fail-open is absolute** (every event exits 0 on any
  internal failure; the sole non-zero is the deliberate budget block), and **hooks are
  CLI-only** — they do not fire under a VS Code extension, so every L1 fact carries that
  limit (`attest.LIMIT`). Per-agent capability is **ONE table**, `agents.HOOK_EVENTS`,
  and **every gap is named in output** via `agents.HOOK_GAPS` (kiro has no session-start
  ⇒ its `agentStop` hook attests but **declines** to auto-close; copilot has no verified
  pre-tool event ⇒ no attestation, no budget block). **No unverified host event name is
  ever invented** — an invented one fails silently, the class this project has already
  paid for twice. Every wired hook command is checked against the **live parser** by
  `wiringscan` (F1, applied before the fact).
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
- **MCP surface = 9 read tools + exactly ONE write tool** ([mcpserver.py](cage/mcpserver.py),
  L2 of the agent-surface ladder). Reads: `report`/`attrib`/`matrix`/`budget`/`roi`/
  `adoption`/`why`/**`verdict`**/**`compare`**. **The refusals are the point** — the two
  product-question tools routinely decline (`INSUFFICIENT DATA` · `SAVING (GROSS)` · the
  `MIN_COMPARE_N` block), and each renders through the CLI's *own* renderer so the text
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
  **Committed wiring is portable (plan §5.3):** every project-committed wired
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
  **Restricted endpoints (docs/restricted-environments.md):** opt-in
  python-launcher mode — `cage setup --python-launcher` persists `[wiring]
  python_launcher = true` (project policy, `policy.python_launcher`, written via
  `pricestoml.set_wiring`); `agents.install` re-reads it every run and fans it
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
  ([docs/shim-contract.md](docs/shim-contract.md), v0.38.0) — `data/shims/graphify`
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
  not templated, on purpose** ([ADR 0007](docs/adr/0007-graphify-twin-pair-hand-paired-not-templated.md)
  — templating stays off the table until a *third* interceptor exists and shares a
  syntax family with an existing one). Known gap, stated not half-fixed: under
  `--python-launcher` there is no `cage` on PATH, so **neither** twin meters (contract
  B5) — `cage doctor`'s `launcher-gap` check names it (GF-LAUNCHER,
  [docs/restricted-environments.md](docs/restricted-environments.md)); a fix must move
  both twins together.
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
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage insights attrib` · budget: `cage insights budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/cage.toml`.
<!-- cage:end -->

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- For cross-module "how does X relate to Y" questions, prefer `graphify query "<question>"`, `graphify path "<A>" "<B>"`, or `graphify explain "<concept>"` over grep — these traverse the graph's EXTRACTED + INFERRED edges instead of scanning files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)
