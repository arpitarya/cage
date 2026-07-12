# CLAUDE.md — Context for Claude Code

**Cage** — a *flux*: a deterministic attribution ledger for LLM token traffic and
tool savings. In the family alongside **fux** (decisions→rules). `$0`, stdlib-only,
deterministic, independent of any AI tool.

Design of record: [docs/cage-plan.md](docs/cage-plan.md). Read it before changing
the substrate contract or the attribution engine.

## Architecture (the one-way data flow)

```
record_call / record_receipt  →  .cage/ledger/{calls,receipts,tasks}-YYYY-MM.jsonl  (+ legacy *.jsonl)
        (meter, plan §5)                      │           · provenance.jsonl (unpartitioned buffer)
                                              ▼  derive ($0, no model)
  policy.toml (prices/order/budgets/human) → report · attrib · matrix · budget · roi
                                             · human · trend · why · origin
                                             + --scope (monorepo slice) · --team · ledger-sync (§3.6)
```

Long-lived logs are month-partitioned (writers append to a dated shard chosen from
the row's own `ts`; readers glob + concatenate, legacy single files still read; `--since`
skips below-cutoff months). provenance.jsonl is a local buffer only — canonical storage
is refs/notes/cage-provenance, written by CI alone (plan §3.5). The calls/receipts/tasks
rows likewise aggregate to refs/notes/cage-ledger (CI-sole-writer) for the team view
(`--team`, plan §3.6.3).

- **Substrate** ([schema.py](cage/schema.py)) — `make_call` / `make_receipt` stamp
  ids + validate the closed enums. Rows are plain JSON. Prompt bodies are never a
  field (counts only). Change here = change the contract; update the plan §3. Calls/
  receipts also carry an additive optional `scope` (top-level changed dir, same PII
  guard as tasks; empty = the legacy contract, plan §3.6.2); calls additionally carry an
  additive optional `project` (working-dir basename, same PII guard; empty = legacy) — a
  *derived* `cage report --project` view, deliberately distinct from `scope`'s monorepo
  axis (plan §3.7). Calls also carry an additive optional `gap_ms` (turn gap →
  derived human attention, plan §4.10; absent = legacy contract, never part of an
  id). The long-lived logs are month-partitioned behind
  `ledger.append_row`/`read_kind` (plan §3.6.1).
- **Constants** ([constants.py](cage/constants.py)) — the *third audit layer*. Cage
  keeps its numbers in three places, never mixed: **contract** = the enums in
  `schema.py`; **policy** = user-economics in `policy.toml`; **constants** = code
  heuristics not meant as config but that must be reviewable (`CHARS_PER_TOKEN`,
  `TOKENS_PER_MILLION`, `MAX_MATRIX_TOOLS`, `METHOD_TRUST`, `DEFAULT_CONFIDENCE`,
  `GRAPHIFY_RECEIPT_CONFIDENCE`, `SINCE_WINDOW_DAYS`, `IDLE_CAP_MINUTES` (a
  policy-preferred fallback like `DEFAULT_CONFIDENCE` — `policy.toml [human]
  idle_cap_minutes` wins), `PARTITION_GRANULARITY`, and the
  ledger-size threshold `LEDGER_WARN_BYTES` — derived from `LEDGER_ROW_BYTES` ×
  `LEDGER_HEAVY_ROWS_PER_DAY` × `LEDGER_WARN_MONTHS`, a policy-preferred fallback like
  `DEFAULT_CONFIDENCE` (`policy.toml [ledger] warn_mb` wins)). `compress`/`prices`/
  `matrix`/`attribution`/`human`/`ledger`/`graphifymeter` import from here.
  `DEFAULT_CONFIDENCE` is a *fallback* — `human.py` still prefers policy `[human.confidence]`. The
  third-party shims (`fux/cage_receipt.py`, graphify) keep a local `len/4` copy
  because they're zero-dep; it's an intentional duplicate of `CHARS_PER_TOKEN`.
- **Explain** ([explain.py](cage/explain.py) engine,
  [explain_data.py](cage/explain_data.py) registry) — `cage query` answers both
  "how is X calculated" (`kind="calculation"`, the original 12 — formulas
  interpolate **live** values from policy + constants; set `CAGE_HUMAN_RATE` ⇒ the
  printed rate changes, never a hard-coded literal) and "how does cage work"
  (`kind="concept"` — `overview`/`data-flow`/`metering`/`attribution`/
  `matrix-concept`/`method-law`/`receipts`/`human-axis`/`determinism`/
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
  distinct or the package attribute shadows the submodule.
- **Attribution** ([attribution.py](cage/attribution.py), [matrix.py](cage/matrix.py))
  — the differentiator (plan §4). Marginal-by-fixed-order; a reconstructed
  counterfactual cell is `modeled`/`estimated`, never `measured` (only the recorded
  run is an invoice). `cage demo` must keep reproducing the plan's §4.4 tables.
- **Unit→USD** ([convert.py](cage/convert.py)) — the single dispatch for a receipt's
  `saved` in dollars: `usd` passthrough · `tokens` at model price · `minutes` at the
  human rate · `ms`/`gco2` → `$0`. `roi`/`attribution` route through it (one place
  unit semantics live).
- **Per-call cost** ([prices.py](cage/prices.py) `call_usd`) — `report`/`budget`
  **recompute** each call from `tokens × policy` at derive time, falling back to the
  stored `est_cost_usd` only when the model is unpriced. A token-only meter (the
  transcript meter never sets `est_cost_usd`) thus still costs out, and a
  self-costing provider Cage can't tokenize keeps its figure. Derive-time only — the
  ledger is never rewritten. A call prices only if `(provider, model)` is in the
  table; the transcript meter stamps `provider="anthropic"`, so that key must carry
  the Claude rows (the bundled `data/policy.toml` does; a project policy must too).
- **Tier-1 human axis** ([human.py](cage/human.py), [humanview.py](cage/humanview.py),
  [trend.py](cage/trend.py)) — *agent vs human* (design doc `docs/human-baseline.design.md`).
  A human receipt is just `tool="human"`; `human.py` resolves minutes/type/usd → USD
  by a fixed precedence + confidence ladder. **Human cost is `estimated` by default**
  (never `measured` unless a real timesheet/quote, never `modeled`). Rates live in
  `[human]` in `policy.toml`; `CAGE_HUMAN_RATE` overrides at derive time and its
  provenance prints in the `cage human` header. `matrix --human` adds the anchor row
  behind the flag (no flag ⇒ byte-identical). `cage human`/`cage trend` show **saved
  $ and saved hrs** (time can go negative — the metric can embarrass the agent).
  The passive side of the axis (plan §4.10): call rows carry an additive
  optional `gap_ms` (previous assistant end → the human turn that led to the
  call), stamped at import only where the log has per-turn timestamps (claude
  yes; codex/copilot/kiro no — absence explicit, never fabricated; never in an
  id). [attention.py](cage/attention.py) is the ONE place gap math lives —
  derived minutes = Σ min(gap_ms, idle cap), always `estimated`, labelled
  `derived (turn-gaps, capped)`; the cap is policy `[human] idle_cap_minutes`
  with the `constants.IDLE_CAP_MINUTES` fallback. Attested minutes
  (`human-record`, `cage outcome --minutes N`) beat derived per task — never
  summed. `compare`/`verdict`/`study report` print a total-cost line (agent $ +
  human minutes × rate, `--agent-only` suppresses); `cage calibration --human`
  is the measured accuracy of the heuristic (refuses below `MIN_ESTIMATE_N`).
  No watcher-shaped capture, ever: transcript timestamps only.
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
  (`cage origin <sha> --attest human`), always paired with `method="heuristic"`
  (enforced at `make_provenance` construction). Captured by a `PostToolUse` hook
  (buffers edits per session) resolved at a `post-commit` git hook
  ([gitcommithook.py](cage/gitcommithook.py), installed by `cage setup`/`agents.install`
  alongside the Claude Code hooks) into the highest-trust `hooked` row, with a
  `SessionEnd`-time transcript fallback ([transcript.py](cage/transcript.py)
  `parse_provenance`) for what the live hook missed. The local jsonl is a **buffer
  only**; canonical storage is `refs/notes/cage-provenance`, merged by row id
  (never overwritten) and **written only by CI** (`CAGE_NOTES_WRITE=1`) — a dev
  machine's `cage notes-sync` defaults to a dry-run print. `cage verify` is
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
  `estimated` + the observational caveat. `cage estimate`: a `modeled` median+IQR
  band from exact-key history; `--record` stamps additive `est_*` fields **plus the
  token band bounds** on the *open* task row (plan §3.4) so `cage calibration` can
  score in-band hits against the band as recorded — that **measured hit-rate is the
  only confidence source; the estimator never self-reports**. `cage verdict <tool>`:
  a pure composer over attrib/roi/trend/regression/quality + break-even — computes
  no new statistics, refuses (`INSUFFICIENT DATA`) over approximating. The min-n
  gates `MIN_COMPARE_N`/`MIN_ESTIMATE_N` live in `constants.py` and **block** —
  below them the command explains, never numbers. Task `label` (via `cage outcome
  --label`) is one validated token, never a path or free text. Diagnostics: `cage
  doctor --bundle` ([doctorbundle.py](cage/doctorbundle.py)) writes one redacted,
  counts-never-content archive; every capture-path swallow-site logs under
  `CAGE_DEBUG=1` — audited by `tests/test_debug_coverage.py` ("fail-open but never
  silent" is tested, not aspirational). Validation harness: the fixture corpus
  `tests/fixtures/transcripts/` (4 agents × cli/vscode, exact expected rows,
  VS Code stand-ins flagged `UNVERIFIED-FORMAT`) + `python -m tools.dummyrepo`
  (S1–S9 scenario runner; build-time only, skillgen rules, never in the wheel).
  P5 fleet study ([machine.py](cage/machine.py), [study.py](cage/study.py), plan
  §4.9): opaque random machine id (**opt-in by enrollment** — unenrolled ledgers
  stamp nothing, byte-identical legacy), recorded phase markers in
  `ledger/study.jsonl` (resolved per machine against its own clock), one-file
  bundles (`cage export --study` → `cage import bundle*.zip`; merge by row
  identity — calls/receipts by id, tasks/markers by whole-row so task updates
  survive), the **machine-day** as sample unit, paired delta `estimated` with the
  work-mix caveat, gate = `MIN_COMPARE_N` machines-with-both-phases (blocking).
- **CSV output (plan §3.9)** ([csvout.py](cage/csvout.py)) — `--csv` on
  report/attrib/roi/compare/`study report`/calibration (incl. `--human`)/human/
  trend, plus raw rows via `cage export --csv calls|receipts|tasks`
  (`exportcmd.RAW_CSV_FIELDS`; `--format csv` = legacy `--csv calls`). One shared
  data structure per view feeds text AND csv (`render_csv` beside each
  `render_*`) — never compute twice. LF pinned (`lineterminator="\n"` +
  `newline=""` writes), RFC-4180, method/match tags are columns, refusals/
  caveats/UNPRICED survive into rows. CSV is one-way REPORTING — never an import
  source; the fleet bundle stays jsonl. MCP mirrors it (`format: csv` on
  report/attrib/roi); the rendered skills teach the recipes (skillgen fragments
  only). Column contracts: `docs/csv-output.md`; `cage query csv-output`.

## Must-Know Rules

- **$0 / stdlib only** — `dependencies = []`. ML is opt-in extras (`[embeddings]`,
  `[ml]`), never imported on the default path.
- **Fail-open everywhere on the write path** — `ledger.append` returns `False`, it
  never raises; `meter()` swallows errors in cleanup. Metering is best-effort.
- **Determinism** — no clocks/random in derived views; ids carry the only entropy.
  Same ledger + same policy ⇒ same tables. Tests assert exact plan numbers.
- **`method` is sacred** — never let a projection read as `measured`. Tag every cell.
- **Four agents, always** — Cage supports **Claude Code · Codex · Copilot · Kiro**
  (`agents.SURFACES = ("claude", "codex", "copilot", "kiro")`). Never drop or
  silently break one: every wiring/read surface (`agents.py`, `mcpserver.py`,
  `cage setup`, the skill/steering data) must keep all four first-class, and new
  surface work fans out to all four. This is a product invariant, not a default.
- **Every release updates the changelog** — bump `__version__`, add the full release
  notes to `CHANGELOG.md` (newest first, don't skip versions) and a **1–2 line**
  summary to the README "What's new" section — which keeps **only the latest
  version's entry** (replace, don't append; the README points at `CHANGELOG.md` for
  history — full prose lives in the changelog), and refresh the
  "N tests passing" count in the README `$0` section + this file's `just test`
  comment. A shipped version with no changelog entry is a release bug.
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
- **Skill/prompt/steering assets are rendered — never hand-edit them.** The flagship
  `cage` skill's per-host files (`cage/data/skills/cage/SKILL.md`,
  `cage/data/prompts/cage.prompt.md`, `cage/data/steering/cage.md`,
  `cage/data/skills/agents/cage/SKILL.md`) are generated by `tools/skillgen` from
  `tools/skillgen/fragments/`. Edit fragments, then `python -m tools.skillgen &&
  python -m tools.skillgen --bless`; CI's `--check` fails on hand-edit drift. Build-time
  only: stdlib-only, never imported at runtime, never in the wheel. See `docs/skillgen.md`.
- **Two error regimes, never mixed.** Write paths stay **fail-open** (return `False` /
  swallow, traceable under `CAGE_DEBUG`, never raise into a request/turn). The read/CLI
  boundary is **typed**: an expected user-facing failure raises the single `CageError`
  (`cage/errors.py`) → `cli.main` renders `error: <msg>` + exit 1. Exit codes: `0` ok ·
  `1` error (full traceback only under `CAGE_DEBUG=1`) · `2` argparse usage · `130`
  interrupt; `cage verify` stays exit 0. Don't add an exception hierarchy or convert a
  write path into a raising one.
- **Quota & credits are `estimated` and live outside the ledger.** `cage limits`
  ([limits.py](cage/limits.py), plan §3.8) reads Codex `rate_limits` (a *sibling* of
  `payload.info`, via `transcript._codex_rate_limits`) into a latest-only, overwrite-only
  machine-local `.cage/state/limits.json` (`Footprint.limits`) — **never** a `limits.jsonl`
  row, never partitioned, never synced to refs/notes. Credit numbers are tokens × a
  `[credits.<provider>."<model>"] per_mtok` policy multiplier ([credits.py](cage/credits.py),
  the `convert.saved_usd` analogue) — token-based providers only, **exact model-id match**,
  **off by default** (no active rows ship); an unknown multiplier ⇒ no number (a wrong
  number is worse than none), and Kiro/Copilot credits are never derived from tokens.
  `cage limits --json` uses the `cage.v1` envelope (`render.envelope`).
- **Transcript call ids are deterministic.** A usage row with no stable source id (a Claude
  turn lacking `uuid`) derives its `call_id` from `(agent, session, model, tokens_in,
  tokens_out, cached_in, ts)` (`transcript._composite_id`) so re-imports dedupe in
  `hooks.append_new` — never a random id. uuid-present rows stay byte-identical.
- **Pricing is managed** ([pricescmd.py](cage/pricescmd.py), [pricestoml.py](cage/pricestoml.py),
  plan §3.3) — `cage prices list|unpriced|set|alias|sync` manages the project
  `[prices]`/`[alias]` tables; writes are text surgery (in-place value edits marked
  `# cage:custom`, or a deterministic cage-managed block) — never a whole-file rewrite,
  and the bundled `data/policy.toml` is read-only at runtime. `policy.price_match`
  resolves exact → alias → family over *normalized* ids (`copilot/` route-prefix strip —
  a closed list; `.`↔`-` folding; effort suffixes low/medium/high/max drop); a normalized
  match renders `family`, an alias renders `alias`, **never `exact`** (method law), and a
  dangling alias is `none` — a router is never silently defaulted. `policy.load` merges
  `prices`/`credits`/`alias` two levels deep (per provider *and* model). The bundle
  carries `[meta] prices_version` (source URLs cited per row); `doctor`/`prices list`
  recommend `cage prices sync` when the bundle is newer — never auto-applied. Repricing
  is derive-time; UNPRICED prints a ⚠ summary on report/overview/compare/study report.
  cage never fetches a price — research is build-time/user work, not a code path.
- **Export imports everything first** (plan §3.7) — `cage export` (plain and `--study`)
  runs the full all-agent sweep before emitting (`--agent` filters output only);
  `--no-import` flag > `CAGE_CAPTURE` env > `[capture] import_before_export` policy;
  fail-open; the study manifest records `refresh: {ran, new_calls}`.
- **State cleanup is a closed allowlist** ([cleanup.py](cage/cleanup.py), plan §3.6.4) —
  aged debug.log/hooks-seen rows, stale `pending-*` buffers, orphan cursors, `*.tmp`;
  never ledger/, policy.toml, machine.json, study.jsonl, limits.json (by construction).
  `[cleanup] enabled/days` (`CAGE_CLEANUP` overrides); auto path piggybacks on
  `importcmd.run`/session-end (throttled, fail-open, `cleanup.prune` debug context);
  `cage cleanup` is dry-run until `--apply`. State files are never read by derived
  views — cleanup can't change a reported number (tested byte-identical).
- **Handoff/prompt docs have a lifecycle — active in `docs/`, archived on ship.**
  New feature work is specced as a pair: `docs/<feature>.handoff.md` +
  `docs/<feature>.prompt.md`. While unshipped they live in `docs/` root and are
  listed under *Active work* in `docs/README.md`. **The release that ships the
  work must, in the same change: (1) move the pair to
  `docs/archive/vX.Y-<feature>.{handoff,prompt}.md`, (2) link them from that
  version's CHANGELOG entry ("Built from: …"), (3) update the `docs/README.md`
  and `docs/archive/README.md` indexes, and (4) promote any still-true design
  content into the living design doc or plan section — the archive is history
  and must never be cited as current spec.** A shipped feature whose
  handoff/prompt still sits in `docs/` root is a release bug, same as a missing
  changelog entry.
- Keep modules small and single-purpose (fux spirit). Tests live in `tests/`.

## Dev

```bash
just test          # python -m pytest -q   (574 passing)
just demo          # seed §4.4 + print attrib/matrix
cage --version
```

## Adapters & agents (one ledger, many surfaces)

Cage targets the **wire protocol**, so the meter and read surface are universal and
each agent only needs thin idiomatic wiring (`agents.py` orchestrates):

- **Meter:** `metering.py` (library), `proxy.py` + `usageparse.py` (any client you
  point a base URL at), `transcript.py` (Claude Code / Codex / Copilot CLI / Kiro session
  logs — `LOG_BEARING` is now all four of `agents.SURFACES`; Kiro's `tokens_generated.jsonl`
  is coarse so the proxy stays its higher-fidelity fallback). Capture is **pull-based and
  global** (plan §3.7): `cage import`/`cage export` over a **resolved** ledger
  (`--ledger`/`CAGE_BASE` → project `.cage/` → global `~/.cage`, via `paths.resolve_root`)
  is the universal path that works with no hooks and no project; hooks are an optional
  CLI-only real-time add-on (they don't fire under a VS Code extension). `importcmd.run`
  honors the **consumer capture switch** — `policy.capture_enabled(pol)`: env `CAGE_CAPTURE`
  (0/1) overrides `policy.toml [capture] enabled` (default on), so a consumer can pause
  metering without unwiring hooks. It **no longer guards on a cwd `.cage/`**: a hook firing
  outside any project lands in the global ledger (the resolver prevents stray local
  footprints), and a per-agent high-water cursor (`state/cursors.json`, last-seen
  `(size, mtime)`) keeps re-imports incremental (the shared `seen` set bounds the ledger
  read to once per run). **cage installs no OS scheduler** — no launchd/systemd/cron/
  schtasks, no `cage scheduler`; hands-off automation is the user's own cron/schtasks
  line calling `cage import` (the hint `render.scheduler_hint()` prints is OS-aware,
  never installed), and `cage watch` is an optional foreground `sleep` loop they
  Ctrl-C (exit 130). Per-agent log locations live in **one registry**,
  `paths.agent_log_sources()` — per-OS candidates behind it (env overrides always
  win; the Windows Kiro layout is labeled UNVERIFIED-LAYOUT until pinned on a real
  install), probed read-only by `cage doctor --paths` ([pathprobe.py](cage/pathprobe.py),
  exported in the doctor bundle as `paths.txt`). Cross-process locking is the single
  fail-open helper [lockutil.py](cage/lockutil.py) (fcntl → msvcrt → proceed-unlocked,
  debug-logged) — never hand-roll another `fcntl` block.
- **Read:** `mcpserver.py` (MCP, every agent), `report/attrib/matrix/budget/roi`,
  plus the Tier-1 human axis (`human`/`trend`, `matrix --human`), authorship
  (`origin`/`notes-sync`/`verify`, plan §3.5), and the ledger-scale surface
  (`--scope` / `--team` filters, `ledger-sync` into refs/notes/cage-ledger via the
  shared `mergeutil.union_by_id` core, plan §3.6).
- **Wiring — one `<agent>wire.py` per agent (a standing convention):** `claudewire.py`
  (hooks+MCP), `codexwire.py` (TOML MCP), `copilotwire.py` (user-level `~/.copilot/hooks`+MCP+pointer),
  `kirowire.py` (one `agentStop` Agent Hook+MCP+steering — Kiro's hook file is
  *one hook per file*: `{name,version,description,when:{type},then:{type,command}}`,
  not a `hooks[]` container, and Kiro has no session-start trigger so the single
  `agentStop` hook self-backfills by re-importing the whole log each turn). Each exposes `install`/`status`/
  `backfill_status`/`realtime_status`; `agents.py` dispatches via the `_WIRE` map (add a
  row + a `SURFACES` entry for a new agent).
  **Committed wiring is portable (plan §5.3):** every project-committed wired
  file (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`,
  `.codex/hooks.json`, `.kiro/hooks/*.kiro.hook`) references the committed
  runtime-resolving shim `.cage/bin/cage-run` ([runshim.py](cage/runshim.py) —
  written by `agents.install`, identical bytes on every machine, resolution:
  PATH → ~/.local/bin/pipx/$VIRTUAL_ENV → `python3 -m cage` → exit 0 silently,
  fail-open) — **never** `paths.cage_bin()`'s absolute path. Per-host reference
  mechanism is documented in each wire module's docstring (Claude:
  `$CLAUDE_PROJECT_DIR` / `${CLAUDE_PROJECT_DIR:-.}`; VS Code:
  `${workspaceFolder}`; codex/kiro hooks: the `runshim.selflocating_command`
  git-root one-liner). User-level configs (~/.copilot/hooks, ~/.codex
  config.toml MCP, .git/hooks) stay absolute — per-machine by nature. The ONE
  exception: `.kiro/settings/mcp.json` stays absolute (Kiro spawns MCP servers
  from its install dir, no workspace variable) — gitignore-advised via doctor.
  Re-running setup migrates legacy absolute entries (idempotent, printed).
  `cage doctor` has a `portability` check; `cage query portable-wiring`
  explains the design. A new committed file must never embed a machine path —
  `tests/test_portable_wiring.py` greps for this and must stay green.
  **Restricted endpoints (docs/restricted-environments.md):** opt-in
  python-launcher mode — `cage setup --python-launcher` persists `[wiring]
  python_launcher = true` (project policy, `policy.python_launcher`, written via
  `pricestoml.set_wiring`); `agents.install` re-reads it every run and fans it
  out to `runshim.write(python_launcher=)` (interpreter-only `_SH_PY`/`_CMD_PY`
  shim pair — nothing exe-shaped, grep-tested in
  `tests/test_launcher_mode.py` + dummyrepo S12) and to every wire module's
  `install(root, python_launcher=)` (copilot hook bash/powershell, codex + kiro
  MCP `command = "python3"|"py"`, git commit hooks — user-level files carry
  interpreter commands instead of `paths.cage_bin()`; claudewire accepts and
  ignores the kwarg, its files reference the shim). `CAGE_RUN_PYTHON=1` is the
  runtime-only override on the standard shim (never read by cage Python code —
  it lives in the shim text). `paths.cage_command_tail` also recognizes
  `python3 -m cage …` / `py -3 -m cage …` so mode switches collapse stale
  entries. Doctor's `portability` check names the mode + warns on policy↔shim
  drift; `cage query restricted-env` explains the tiers.
  `pointers.py` is now just the shared steering
  *pointer text* both copilot/kiro embed. Plus `setupcmd.py` (`/cage` skill) and
  `gitcommithook.py` (local `post-commit`/`prepare-commit-msg` git hooks, riding along
  with `claudewire.py` inside `agents.install`). All idempotent. Every agent's hook runs
  the same all-agent sweep (`paths.cage_import_all`) so any agent captures the whole stack.
- **§8 features:** `quality.py`, `regression.py`, `recommend.py`, `forecast.py`.
- **Tier-0 savings:** `compress.py`, `responsecache.py` (emit receipts).

## Integrations

- **AlphaForge Anton (Orff)** — first consumer. Anton's `LLMGateway` records each
  `ProviderResponse` via a fail-open `cage_meter` adapter (`anton/docs/cage.md`).
  Cage is wired there as an optional `[cage]` extra (uv path source).

<!-- cage:start -->
## Cage — LLM cost & savings ledger

This project meters LLM traffic into `.cage/` (a *flux*: $0, deterministic).

- Spend so far: `cage report` · per-tool savings: `cage attrib` · budget: `cage budget`
- The ledger carries token *counts*, never prompt text — PII-safe by construction.
- Edit prices / budgets / pipeline order in `.cage/policy.toml`.
<!-- cage:end -->
