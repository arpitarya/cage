# Changelog

Full release notes. The README keeps a one-line summary per version; the detail lives here.

## v0.48.0 (2026-08-10) — every report and insight is an artifact

Two asks, one collision with cage's determinism law, and the split that resolves it.

**A number on a terminal and a number in a file are not the same object.** A terminal
number is read now, in context, by the person who typed the command. A file outlives
that context — so an exported table with no as-of is a number nobody can safely re-read.
That is why the generated-at stamp is **mandatory in an artifact and optional on a
terminal**, and it is the whole reason a wall clock can exist on a read surface at all
without touching *no clocks in derived views*.

### Added — `--export` on `cage report` and every `cage insights` view (17 views)

- Bare `--export` writes **every format that view has** — text, CSV where it owns a
  `render_csv`, JSON — into `<ledger>/.cage/output/<view>-<stamp>/`.
- `--export PATH.csv` / `.json` / `.md` / `.txt` writes exactly that file in exactly that
  format. Any other `PATH` gets a per-run folder under it: **two runs of one view never
  clobber each other**, because an artifact whose job is to be the as-of record is
  worthless once the previous as-of is gone.
- A format a view cannot produce is a **typed refusal naming the gap**, never an empty
  file — an empty CSV reads as *this view has no rows*, the one thing it must not be able
  to say.
- New: `cage/viewexport.py` (destinations, formats, confirmation) and `cage/runstamp.py`
  (the ONE clock call on a read surface; `CAGE_RUN_STAMP` pins it). `--stamp` puts the
  same block on stdout. `cage query view-export` explains it.

### The determinism split, stated as a test

`tests/test_view_export.py::test_export_never_changes_stdout` asserts stdout is
**byte-identical with and without `--export`**, across six views. That is what keeps
`tests/test_output_spec.py`'s goldens and `tests/test_floor.py`'s byte-identical
assertions meaningful: they pin the default surface, and the default surface has no clock
in it. The stamp is metadata *about the run* — delete every stamp and no derived figure
moves. `--csv`/`--json` keep their existing byte contract on stdout **and to a path**: a
`--csv PATH` is a stream redirected to a file, `--export` is an artifact, and only the
artifact grows the block.

The fan-out is gated too: `test_every_report_and_insight_is_exportable` walks the live
parser, so a new insight that forgets `_export_flags` fails the suite instead of shipping
un-exportable. Wire the new command in — never relax the set.

### Fixed — `cage insights chats --agent kiro` blamed the filter for an architectural fact

`No chats match agent 'kiro' — the filter is empty, not the ledger` is a true sentence
about the filter and a **misleading one about kiro**, whose absence has two structural
causes cage already knows: its CLI conversations are recorded as **credits** (a row shape
with no tokens and no call, so no chat row can exist for them) and its IDE rows are a
machine fact routed to `~/.cage` ([ADR 0006](docs/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)).
Saying *filter* when the answer is *architecture* sends a reader to check their typing
instead of the ledger they actually want — the same class of failure as an agent showing
no rows because capture silently broke.

- The empty view now names the structural reasons it can evidence, and only for the agent
  actually asked about; a filter that really *is* the reason still gets the old message,
  unchanged.
- The kiro-routing line was **computed and then dropped** on the empty path — it is
  threaded through now. `report.kiro_routed_line` grew a `verb` parameter so the one
  phrasing can name the right runnable fix per view (one owner, never re-worded).
- A **non-empty** chats view footnotes credits usage it cannot show (no-silent-omission:
  a table that just doesn't show it reads as *there is none*).
- Reading `ledger.credits` here is the **third** money-independent carve-out, on the same
  terms as the manifest-title and provenance-count ones: read for a refusal, never for a
  cell. `test_reading_credits_moves_no_number` pins it.

### Also

- `.cage/output/` is deliberately **not** `.cage/out/` — that one is `cage data serve`'s
  docroot, and a stdlib `http.server` is pointed straight at it, so sharing a directory
  would mean starting the dashboard quietly published every report anyone had ever
  exported. `cage setup` gitignores the new dir and heals older footprints.
- **No cleanup class prunes `.cage/output/`** — cage never deletes an artifact it wrote,
  the same standing `ledger/savings/` has. Revisit only with a named volume number
  (`docs/OPEN-WORK.md`).
- Bare `cage` (the headline) has no `--export`: a root-level optional-value flag would
  swallow the following subcommand (`cage --export report`). Named in the compare doc as a
  choice, not left as an oversight.

Built from: [docs/compare/view-export-and-run-stamp.compare.md](docs/compare/view-export-and-run-stamp.compare.md).
Suite **1503 → 1541**.

## v0.47.2 (2026-08-08) — the same Windows class, one syntax layer over

v0.47.1 fixed 25 of 26 Windows failures. The last one was **the same defect in TOML** that
v0.47.1 had just fixed in JSON: `tests/test_graphify_kiro.py` wrote a `[sources]` path as
`paths = ["{proj / "data.sqlite3"}"]`, and on Windows that is `C:\Users\…` inside a TOML
**basic** string, where `\U` is an escape — `tomllib` raises `Invalid hex value`, so the
source silently never resolves and the sweep files nothing.

### Fixed

- The E2E kiro test now uses **`.as_posix()`** — which is not a new idea, it is the
  convention **six other `[sources]` tests here already follow**, and the reason they pass
  on Windows. This test was the only one in the suite not following it.

### Added — a gate, so this class cannot buy a third release

- `tests/test_sources.py::test_no_test_writes_a_raw_path_into_a_toml_basic_string` greps
  every test for a `[sources]` path interpolated into a TOML basic string without
  `.as_posix()`. Mutation-checked: reintroducing the v0.47.1 spelling fails it on macOS.
- Its first pattern had the same blind spot as the bug: a quote-excluding character class
  skipped `paths = ["{proj / "data.sqlite3"}"]` — the exact form that shipped — so it is
  non-greedy now.

**The rule the two patches share, stated once:** *a filesystem path crossing into any
escape-processing syntax — JSON, a TOML basic string, a shell — needs an explicit
conversion, never `str()`.* Product code is untouched in this release. Suite **1502 → 1503**.

## v0.47.1 (2026-08-08) — Windows: the VS Code report-read route filed nothing

**v0.47.0's `build` job went red on both Windows legs** (26 failures; every POSIX leg and
all three graphify legs were green). Two distinct bugs, one of them a real product defect
that would have been silent for Windows users.

### Fixed

- **`graphifytx._repo_of` rejected every Windows path.** It gated on `startswith("/")`, but
  a Windows path is `C:/…`, so it returned `""` — the graph then resolved against the
  process CWD instead of the repo, and **the copilot VS Code report-read route filed
  nothing on Windows**. No error, no warning; just an absent receipt, which is
  indistinguishable from "graphify was never used". It now accepts both conventions.
  `Path.is_absolute()` is deliberately *not* used: on POSIX it calls `C:/x` relative, and
  on Windows it calls `/tmp/x` relative (no drive), so each OS would reject exactly the
  form the other produces.
- **The new fixture tests substituted a temp path into raw JSON text.** On Windows
  `str(tmp_path)` is `C:\Users\…`, whose backslashes become invalid escapes inside a JSON
  string literal — hence 26 `JSONDecodeError`s. Fixture loading moved to
  `tests/gfxfixture`, which parses first and re-serializes, so a path separator can never
  reach a JSON literal unescaped again.

### The gap that let it ship

Both faults were **Windows-only**, and every test that could have caught them was itself
Windows-only. The two new regression tests run on **every** OS by construction — one
asserts `_repo_of` against both absolute conventions directly, the other round-trips a
`C:\Users\…` root through the loader — so the POSIX legs alone would now fail. Verified by
mutation: restoring the v0.47.0 predicate makes the new test fail on macOS.

No behaviour change on POSIX; no schema, id or pricing change. Suite **1500 → 1502**.

## v0.47.0 (2026-08-07) — graphify savings now file from copilot VS Code and kiro

**The graphify savings ledger was dark on two of three agents, and the reason was an
assumption nobody had checked.** copilot's VS Code store was skipped by name in
`_detect_graphify_copilot` because it was believed to carry the command but no tool
result. kiro had no route at all. So every "does graphify pay" reading cage produced was
structurally claude + copilot-CLI only — narrower than it read, silently.

**A field probe of the real stores retired the assumption.** Across 157 real chat-session
files and 1,132 `run_in_terminal` parts, VS Code persists the command
(`toolSpecificData.commandLine.original`), the cwd **per command**, *and* the output. The
evidence, the exact keys, and the versions probed are in
[docs/research/2026-08-07-graphify-store-evidence.md](docs/research/2026-08-07-graphify-store-evidence.md).

### Added

- **copilot VS Code graphify route** — `chatSessions` files now file query receipts (from
  `run_in_terminal`) and report-read receipts (from `copilot_readFile`). Same
  counterfactual, same deterministic ids, same ADR-0005 cross-route deferral as every
  other route — no forked formula and no new confidence constant.
- **kiro CLI graphify route** — `conversations_v2` `execute_bash` runs and `fs_read`
  report-reads. Receipts land in the sweep's own sink, scoped by the same workspace tree
  the credits leg resolved (ADR 0006) — never a second resolver.
- **`cage import --rescan-graphify`** — a cursor-blind backfill. The import cursor skips
  an unchanged log, which is right for calls and wrong for savings: a route that ships
  *after* a session was ingested can otherwise never see it again. Detection only (no call
  or credit re-ingest), idempotent by receipt id. **Run it once after upgrading** to
  backfill the two new routes.
- **`cage doctor` gains a `graphify-coverage` check** and **`cage query
  graphify-coverage`** — which surfaces file receipts and, for the one that cannot, the
  measured reason. Both read one table (`graphifytx.GRAPHIFY_COVERAGE`), so a gap can
  never be worded two ways.
- **[ADR 0009](docs/adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md)**
  — kiro-CLI tool-run bodies are read **transiently**; nothing but hashes and counts
  persists. It does not re-argue the principle ([ADR 0008](docs/adr/0008-line-match-authorship-counts-persisted-content-transient.md)
  ratified that already, and more strictly); it records where the boundary falls in the
  one store whose law is a written key whitelist.

### Honesty, not coverage

- **kiro caps tool stdout at ~2000 tokens** and appends its own truncation marker, cutting
  mid-token. A truncated answer under-counts `actual`, which would *inflate* the modeled
  saving — so a truncated run files **nothing**. Expect kiro query receipts to be sparse;
  that is the guard working. `fs_read` report-reads need no result body and are unaffected.
- **The VS Code truncation guard matches no marker string, deliberately.** A sweep of
  1,132 real terminal runs found zero VS Code-inserted markers — all 23 candidate hits
  were the command's *own* output (rust clippy's `cast_possible_truncation`). A substring
  guard would have refused good receipts while never catching a real elision, so the guard
  keys only on what the store states: a missing output carrier, or a non-zero exit.
- **Kiro IDE cannot file, and now says so.** Its `workspace-sessions/` store persists no
  assistant output at all (26/26 `promptLogs` completions were the empty string when
  probed). That is a structural limit of the client, named out loud in doctor and the
  explainer rather than left as a silent zero.

### Notes

- No schema change, no id-scheme change, no pricing change. Existing receipts are
  byte-stable; the claude and copilot-CLI routes are untouched.
- Suite **1462 → 1500** (`tests/test_graphify_vscode.py`, `tests/test_graphify_kiro.py`,
  plus rescan and coverage tests).
- **Both new routes are verified on real data, not just fixtures** —
  [kiro CLI](docs/regression/2026-08-07-gfx-cov-kiro-field-run.md) (1 filed, 1 refused as
  truncated) and [copilot VS Code](docs/regression/2026-08-08-gfx-cov-vscode-field-run.md)
  (146,261 tokens saved across 72 cited files). The VS Code capture **falsified two
  assumptions in the fixture it replaced**: a real agent emits `cd <repo> && graphify …`
  (nothing had exercised the `&&` split) and the real part carries no `resultDetails`
  (so the fallback carrier is the one that runs in the field). Both now tested.
- Built from: [handoff](docs/archive/v0.47-graphify-agent-coverage.handoff.md) ·
  [prompt](docs/archive/v0.47-graphify-agent-coverage.prompt.md) ·
  [store evidence](docs/research/2026-08-07-graphify-store-evidence.md).

## v0.46.1 (2026-08-03) — CI green again: S18 asserted the pre-hookless heal

**The `build` job had been red on all nine platform legs since v0.45.0**, and both
releases shipped through it — `publish-pypi` fires on `release: published` and has no
`needs` link to `build` (deliberate, CLAUDE.md), so the published artifacts were never
in question. But a red gate that stays red teaches everyone to ignore it.

**It was the scenario harness, not the product.** S18 plants a stale pre-v0.36 cage hook
in `.claude/settings.json`, heals it with `cage setup`, then re-read the file to assert
the dead verb was gone. Cage plants nothing else there, so stripping its entry empties
the object — and `claudewire` then drops the emptied `hooks` table and **unlinks a file
it alone reduced to `{}`**, because otherwise every off-switch leaves a permanent
committed diff. The scenario died with `FileNotFoundError` **on the correct outcome**.

- S18 now **asserts the removal** instead of tolerating it — an absent file is the
  strongest form of "the dead verb is gone", and this is documented behaviour that no
  other scenario covered. A file left behind is now a named failure with its contents.
- The idempotency check reads absent as `b""` on both sides, so a re-heal must not
  resurrect an empty file either.
- Product code is **untouched**: no `cage/` module changed in this release.

## v0.46.0 (2026-08-03) — `agent%`: did this chat's tokens become code?

Built from: [handoff](docs/archive/v0.46-chats-author.handoff.md) ·
[prompt](docs/archive/v0.46-chats-author.prompt.md) ·
[proposal](docs/archive/v0.46-chats-author.proposal.md).

### `cage insights chats` gains an `agent%` column

The chats view could say a conversation spent 2.1M tokens. It could not say whether any
of it became code. The per-commit surfaces answered that per **sha**; nothing answered
it per **conversation** — the unit the view exists for.

- **Per chat: of the evidenced lines in files this chat touched, the share that matched
  the agent's own proposals.** A pure ledger join — the v2 authorship rows already carry
  `(sha, agent, session_id)`, and for claude-code both sides stamp the same session id
  (the transcript stem), so **no git runs at render time** and the view stays a pure
  derive.
- **Read, never re-derived.** The counts are whatever capture recorded. Re-matching at
  render would be a second matcher, free to disagree with the one that wrote the row —
  a chat's sums are asserted equal to the per-commit buckets across that seam.
- **The scope is narrower than the column head, and the footnote says so**: lines in
  files no session proposed are commit-scoped (`unattributed`) and sit outside the
  denominator. It is never "a share of this chat's work".
- CSV gains `agent_lines` · `residual_lines` · `agent_pct` (0–100, 1dp).

### It refuses three ways, and `—` never means 0%

**coverage** (copilot/kiro persist no edit text — the reason is named verbatim from
`authorcapture.coverage_note()`) · **no landed evidence** (nothing committed yet,
committed in another repo/ledger root, or nothing matchable landed — "nothing landed"
is not "the agent wrote nothing") · **pre-upgrade** (rows predating the new count are
excluded from *both* sums and counted in a footnote). A **measured** `0%` still renders
`0%` — which is precisely why the dash is never spent on absence of evidence. All three
carry their reason below the table; none is ever a silent omission.

### Substrate: one new count, and the one deliberate deviation

`residual_lines` joins `schema.PROVENANCE_COUNT_FIELDS` — matchable added lines in a
row's **own landed files** minus its `agent_lines`, floored at 0, computed in
`authorcapture` step 4 from the diff already in hand (**no extra git call**).

The other five counts are omitted at 0. This one is **written at 0**
(`schema.PROVENANCE_ZERO_BEARING_COUNTS`), and **presence of the key is the version
gate**: absent means the row predates the count and renders `—` forever — provenance
rows are frozen by the idempotency key and are **never backfilled** — while a recorded
`0` is the real finding that everything matchable matched the agent. Omitting it would
make the most flattering true result indistinguishable from no data at all. Same
absent-vs-recorded-zero law as `credits`' `None` sentinel. A caller that does not
line-match supplies nothing and writes the pre-v2 row byte-for-byte.

### The guards this had to answer

- **The v0.36 human axis stays dead.** No rate, no minutes, no USD touches an authorship
  number; `agent%` never combines with `cost`, and `--usd` moves no authorship cell. The
  guard is asserted **per formula**, not per import (this module legitimately prices the
  `cost` column).
- **Counts, not a score** — no acceptance rate (`kept/suggested`) is derived anywhere.
- **A second money-independent carve-out**, on the first one's exact terms: `agent%`
  reads `provenance.jsonl` for counts only, and deleting that file moves **zero**
  pre-existing cell — only the authorship cells fall to `—`. Pinned by a test.
- **Counts-never-content is untouched** — `residual_lines` is an integer; no line body
  and no line hash reaches disk, and the plant-string test stands unmodified.

**Two stated limits, not fixed.** A provenance row carries no `surface`, so a session
split across surfaces attaches its counts to every such row (footnoted — they are not
independent evidence). And per chat there is no diff to clamp against the way the commit
view clamps per sha, so two chats that proposed the same landed file each count its
lines: **for any single sha, the commit view remains the arbiter.**

## v0.45.0 (2026-08-03) — a correctness pass: nothing here was caught by a test

Ten fixes from the v0.37.0→v0.44.0 review, none of which the (green) suite detected.
Two wrote **append-only rows a later fix is forbidden to rewrite**, so every day they
stayed open cost real data; two were armed to fire later — one on a calendar date, one
on the next hook-event rename; the rest were numbers that were simply wrong, or honest
in a total and fabricated as a field. Two items were routed to decisions rather than
patched: the copilot multi-model billing **basis**, and the OTel GenAI **semconv pin**.

### Copilot billing integrity (REV-CREDITS defect 1 + the guard gaps)

Evidence: [proposal](docs/proposals/copilot-credits-integrity.proposal.md).

**A shutdown's credit delta was dropped whenever the first-listed model had idled.**
`prev_cred` advances once per shutdown, before the per-model loop; a model whose token
counters did not move emits no row; and the delta was pinned to index 0. So a resumed
session that used only its *second* model lost the billing figure entirely — no row
carried it, the cursor had already moved, nothing was logged. Billed spend, permanently
undercounted, with `modelMetrics`' dict order deciding whether it happened.

- **The delta now lands on a row the loop actually emits** — the largest token mover,
  ties broken by model name. Deterministic (a re-parse is byte-identical) and
  independent of dict order. It is *not* an attribution claim: GitHub computes the
  counter over the whole shutdown, so **no** single row truly owns it. Splitting it
  across rows is a genuine basis fork and stays filed for
  [the compare doc](docs/compare/copilot-pricing-basis.compare.md) — defect 2 was
  deliberately **not** decided inside a fix commit.
- **When every model idled and credits still arrived**, a zero-token carrier row keeps
  the figure. That row is a true statement — this shutdown billed N credits and moved
  no tokens — and dropping it is the defect being fixed.
- **A counter that goes backwards is a reset, not a refund.** Stored verbatim it was a
  negative delta quietly shrinking every USD total; the new cumulative value is now
  read as the delta. Clamping to 0 was the other option and is worse — it discards real
  spend.
- **Non-finite counters no longer cost the whole file.** `json` accepts bare
  `NaN`/`Infinity` and `int()` **raises** on both, so one bad field threw out of the
  parser and lost every row in it — worse than the review recorded. They now read as
  *absent* (never a fabricated `0.0`), and the tokens beside them still land.
- **`cage insights compare` stops calling credit-priced dollars `measured`.** A credit
  dollar is a recorded count times a rate *you* configured, which is `modeled` by the
  feature's own law; `report`/`chats` already degraded, compare printed an invoice.
  `taskgroup.stats` now carries `credit_calls`, and both the CSV cells and the text
  header degrade together — a header saying `measured` above a modeled row is the same
  lie as a mislabelled cell.

### Honest refusals (REV-HARDEN P2)

- **`cage insights adoption --since` answered two different questions in one table.**
  Half A row-filters; half B used `read_kind`'s `since`, which skips whole **month
  shards** and applies no row filter. Half B now double-filters like roi/report/chats.
- **A shared session is no longer described as a capture gap.** A savings row whose
  session belongs to more than one agent was filed as `unjoined`, whose sentence reads
  *"the agent turn behind it was not captured — a capture gap worth chasing"*. That is
  a **false fact**: nothing was missed and there is nothing to chase. New `ambiguous`
  reason with its own sentence. A view whose whole value is a boundary between three
  unknowns cannot describe one of them as another.
- **An unpriced saving is omitted, never exported as `$0`.** `policy.price` returns a
  zero row for a model it cannot price, so `prices.input_cost_usd` produced a hard
  `0.0` indistinguishable from a real zero — fine in a sum, a fabricated figure when
  emitted as an OTel field. New `convert.saved_usd_opt` owns the unpriced-vs-zero
  distinction **in `convert`**, where unit dispatch already lives; the review pointed at
  `otelout`, but fixing it there would have put a second copy of the pricing ladder in
  it, and the credits rung already drifted between two copies once.
- **Unwiring hooks leaves nothing behind.** The `--hooks` off-switch routed through a
  stripper that left `"hooks": {}` and the file itself on disk, so turning the layer off
  showed up as a permanent committed diff. It now uses the path that already dropped an
  emptied table and removed a file cage alone reduced to nothing — same predicate for
  "is this cage's entry", so *which* entries get removed is unchanged.
- **Not fixed, deliberately:** `gen_ai.system` is deprecated (renamed to
  `gen_ai.provider.name` in semconv **v1.37.0**, before cage's pinned 1.42.0). Verifying
  it surfaced a second problem that makes this a fork rather than a fix — the GenAI
  conventions moved to their own repository, so the pinned version string may not name
  what cage thinks it names. Findings and the three options:
  [research](docs/research/2026-08-03-otel-genai-semconv-pin.md).

### `cage --help` advertised six of `data`'s eight commands (CLI-GAPS a)

`migrate-savings` and `graphify` ran while being invisible to anyone reading the help —
the same failure class as a dead verb in prose, so it gets the same treatment: the front
door is now **gated bidirectionally against the live parser**
(`tests/test_cli_tiering.py`), so a command that exists but is unnamed, or a name with no
command behind it, fails the suite. Also found while fixing it: each group's `help=`
string duplicated those lists and is **rendered nowhere at all** — noted at
`cli._group` rather than left to rot as a second source of the same drift.

### `cage hook` can no longer block your session by failing (REV-HARDEN P1)

**Exit `2` is the block verdict** (`hookcmd.BLOCK`, wired to `PreToolUse`/`Bash`) —
and it is also what argparse exits on any usage error. So an unknown event name, which
is exactly what renaming an event against stale committed wiring produces, would have
blocked **every Bash call in the session**. Silently: a blocked tool call reads as the
agent refusing, not as cage failing. Fail-open was absolute *inside* `hookcmd.run` and
absent at the boundary standing in front of it.

- `cage hook <anything argparse rejects>` now exits **0**, prints the accepted events
  and `cage setup --hooks` on stderr, and traces under `CAGE_DEBUG`. The deliberate
  budget block still returns `2` — asserted through `cli.main`, the path a host
  actually invokes, since that is where both codes travel.
- **Scoped to `hook` alone.** Every other verb keeps argparse's exit `2`, and
  `cage hook --help` still exits `0`.
- **The fix-hint is derived from the live `EVENTS`, not a hand-maintained map of old
  spellings** — a map like that goes stale in the very release that renames an event,
  which is the same reason `wiringscan` detects against the live parser rather than
  `verbmap.REMOVED`.

### The dogfood freshness guard stops being a calendar bomb (REV-HARDEN P0)

`tests/test_dogfood_freshness.py` compared the committed snapshot date to the wall
clock with a 60-day ceiling, unconditionally. On ~2026-10-02 the suite would have gone
red **on every machine with no code change** — and a fork could not have healed it at
all, because the snapshot derives from the maintainer's own `~/.cage`. Under "green, or
no release", every release would have blocked on a docs refresh one person could
perform.

- The guard is now **two halves, gated differently**. *Structural* (directory exists ·
  `latest.md` exists · parseable `snapshot_date` · it agrees with the newest dated
  filename) runs **always, everywhere** — it is date-independent, fixable from the repo
  alone, and it is the half with teeth. *Age* runs only when `CAGE_DOGFOOD_FRESHNESS`
  opts in, which this repo's CI sets and nobody else does.
- Opt-in rather than skip-on-fork because the failure modes are asymmetric: a guard
  silently off for the maintainer is a stale snapshot; a guard wrongly on for a
  contributor is a red suite they cannot fix.
- `CAGE_SKIP_DOGFOOD_FRESHNESS=1` remains the local bisect/old-tag escape. The split
  itself is now a test, so the bomb cannot be re-armed by removing a comment.

### Row ids get 32 bits of randomness (ID-ENTROPY)

Evidence: [finding](docs/regression/2026-08-02-finding-call-id-collisions.md).

**`ids.new_id` had 16 bits of randomness per millisecond, and every merge path dedupes
by id — so a collision was a silently dropped row, not a retry.** Measured on a real
machine: **874 duplicates in 200,000** sequential ids (~1 in 229). It turned `main` red
once (`test_study`, 37 calls where 38 were seeded) and the test was right; the generator
was wrong.

- **`secrets.randbelow(0x100000000):08x`** — 32 bits, ~65,000× safer. Re-measured the
  same way immediately after: **0 duplicates in 200,000**. The millisecond field is
  untouched, so ids stay lexicographically time-sortable; bodies go 15 → 19 chars.
- **Entropy width is now a contract test, not a statistic** — `tests/test_substrate.py`
  asserts `randbelow` is called with `0x100000000`, because a statistical test for a
  1-in-4-billion event is either vacuous or flaky and neither would notice the field
  getting narrower again.
- **Ids already written are never rewritten** and keep their old 16-bit risk — which is
  the argument for doing this now rather than later, not for backfilling. Old and new
  shapes coexist because **nothing parses an id**.
- `mergeutil.union_by_id`'s docstring asserted *"call/receipt ids never legitimately
  collide"*; the measured rate falsified it. Widening makes an invariant the merge layer
  already relied on actually true, and the docstring now names the generator as its
  precondition. `transcript._composite_id`'s "same 15-char shape" parity note corrected
  in the same change — the two *deterministic* paths still agree at 15; the random path
  is deliberately wider.

### One UTC normal form for the authorship join (REV-TS)

Built from: [proposal](docs/archive/v0.45-rev-ts.proposal.md) ·
[handoff](docs/archive/v0.45-rev-ts.handoff.md) +
[prompt](docs/archive/v0.45-rev-ts.prompt.md) ·
[finding](docs/regression/2026-08-02-finding-commit-window-timestamp-skew.md).

**Every authorship join on a non-UTC machine was placing edits and calls on the wrong
commit.** `commitjoin` built commit windows from raw `git log --format=%cI` strings —
the *committer-local* offset — and compared them **lexicographically** against UTC
`…Z` transcript and call timestamps. Ordering strings across different offset
representations is meaningless.

- **One normal form, `YYYY-MM-DDTHH:MM:SSZ`**, sub-seconds **truncated, never
  rounded** (`commitjoin.norm_ts`). One parse (`as_utc`, always UTC-aware, naive input
  assumed UTC); `commitview._iso` is now that function rather than a second copy of it
  — it could previously return a *naive* datetime, one input away from a `TypeError`
  against `ledger.since_cutoff`'s aware cutoff.
- **Bounds normalize at construction.** `Window` is a `collections.namedtuple`
  subclass whose `__new__` normalizes, so a window holding a raw git string cannot be
  built — in the module or in a test. The skew was invisible for exactly as long as it
  depended on every caller remembering. Probes normalize on entry to `window_for`, and
  `authorcapture._uncovered` normalizes before the coverage-cursor compare. **The
  comparison itself is still a string compare** — the determinism law keeps datetime
  objects out of stored rows.
- **Seconds, not milliseconds, is deliberate.** `%cI` carries no sub-second, so a
  commit stamped `10:00:00` happened somewhere in `[10:00:00, 10:00:01)`. Millisecond
  precision would push an edit at `10:00:00.500` — plausibly *before* the commit —
  into the next window on precision cage does not have, breaking the documented
  inclusive bound.
- **Pure-UTC repos were never affected.** Git renders `%cI` as `Z` when the offset is
  zero, so their bounds already shared the probes' shape. The review's third claimed
  failure shape (a same-second bug in pure-UTC repos) assumed a `+00:00` bound git
  never emits, and was **falsified** during the build — it is the reason the normal
  form is seconds rather than milliseconds. Details in the finding.
- **Pre-fix provenance rows are suspect and are NOT rewritten.** `originrecord` freezes
  a row by `(sha, agent, session_id, method)`, so rows written on a non-UTC machine
  keep their wrong sha forever; the log is append-only. Worse and stated plainly: a
  corrected sweep can *add* rows on the corrected sha **beside** the wrong ones, so
  those lines count on two commits. The `_authorship` cursor is therefore deliberately
  **not** invalidated (an unchanged, already-covered transcript stays unread); files
  still marked uncovered will be re-read and can produce the double-presence anyway.
  No repair or purge verb was added — that would violate the append-only law.
- **`cage insights commits --csv` `ts` is now UTC.** It emitted the raw window bound,
  which on a non-UTC machine was *local* time. Text output is unchanged (it slices the
  offset away), and **no golden fixture moved** — which is what verified the blast
  radius.
- The suite was green over this bug for its whole life because every fixture commit was
  pinned `+00:00` and the one boundary test probed with byte-identical strings: it never
  left UTC and never sat on a boundary.

**Together: 1401 → 1441 tests**, 0 fail, 11 skipped (the new skip is the opt-in dogfood
age check), and **no golden fixture moved** — which is what verified the blast radius.
The one re-blessed fixture is `tests/fixtures/cli-help.txt`, the front door itself.

## v0.44.1 (2026-08-02) — golden fixture drift fix

CI on `main` failed after the v0.44.0 release: `[meta] cage_version` derives from
`cage.__version__` (by design — see CLAUDE.md's `[meta] cage_version` rule), so
`cage prices list`'s output changed to `0.44.0`, and the golden fixture
`tests/fixtures/goldens/P1.txt` still asserted `0.43.0`. This is the drift-guard
class the release checklist exists to catch.

- Re-blessed `tests/fixtures/goldens/P1.txt` (`CAGE_BLESS_GOLDENS=1`). No
  behavior change — output was already correct, only the fixture was stale.
- No other code changes. 1401 tests passing, 10 skipped.

## v0.44.0 (2026-08-02) — Copilot's own billing number, and the pricing ladder

Built from: [proposal](docs/archive/v0.44-copilot-credits.proposal.md) ·
[handoff](docs/archive/v0.44-copilot-credits.handoff.md) +
[prompt](docs/archive/v0.44-copilot-credits.prompt.md) ·
[compare verdict C](docs/compare/copilot-pricing-basis.compare.md) ·
[store evidence](docs/research/2026-08-02-copilot-credit-fields-real-stores.md).

**`copilot/auto` prices exactly now — with GitHub's own number, not a guess.** Copilot
persists the credits it billed for each request; cage was dropping them, which is why
the router id that no price row can match was the largest UNPRICED hole in a real
ledger. Cage now records that figure verbatim and resolves every copilot dollar by a
three-rung ladder at the single pricing choke point.

- **New additive call field `credits`** — the billed figure, recorded verbatim from VS
  Code's chatSessions store (`copilotCredits`) and the CLI's `totalPremiumRequests`.
  Old ledgers parse and re-render byte-identically. Never derived from tokens in either
  direction; **absence and a recorded `0.0` are different facts** and stay that way.
- **The ladder** (`cage query copilot-credits`, FORMULAS §1.1a): `credits × rate` →
  `tokens × price table` → loudly UNPRICED. It lives in **one** place
  (`creditprice.resolve`, reached from `prices.call_usd_match`), so report · budget ·
  chats · compare · verdict · roi · study · forecast all inherit it with no per-view
  fork. Rung 1 is **`modeled`, never `measured`** — the count is fact, the dollar is a
  rate you configured.
- **`[billing.copilot] usd_per_credit` in `cage.toml`**, unset by default. No rate ⇒
  credits render as a **count**, never a dollar, and those rows price by token × table.
  It is *not* filed under `[credits]` (the vendor rate card in `prices.toml`) on
  purpose: your overage rate must survive `cage prices sync` — vendor facts move,
  routing decisions stay.
- **Nothing is blended silently.** A total spanning both bases prints the split; the ⚠
  UNPRICED block gains a second runnable fix when the unpriced rows carry credits; CSV
  names the winning basis per row in `priced_via`, and any view containing a
  credits-priced row reports `modeled` rather than `measured`.
- **`cage insights chats`** gains a `credits` column (`—` = not recorded; never in CSV)
  and `priced_via`. **`cage doctor`** gains an advisory `credits` coverage line —
  never a warning, because coverage is the vendor's logging, not your setup.
- **Fixed, by widening:** copilot-CLI `totalPremiumRequests` is fractional (`0.33`) and
  the int `premium` field floored every real value to 0 and dropped the key — 13 CLI
  rows in a real ledger, not one carrying it. `credits` carries it as a float;
  `premium` is untouched. [Finding](docs/research/2026-08-02-copilot-credit-fields-real-stores.md).

## v0.43.0 (2026-08-02) — agent-vs-human, rebuilt per commit

Built from: [proposal](docs/archive/v0.43-agent-vs-human-v2.proposal.md) ·
[handoff](docs/archive/v0.43-agent-vs-human-v2.handoff.md) +
[prompt](docs/archive/v0.43-agent-vs-human-v2.prompt.md) ·
[ADR 0008](docs/adr/0008-line-match-authorship-counts-persisted-content-transient.md) ·
[dogfood evidence](docs/regression/2026-08-02-p1-authorship-dogfood.md).

The Tier-1 human axis was removed in v0.36 for inventing precision — a turn-gap
heuristic priced at an hourly rate, rendered so it read as measured. This is its
replacement, and it answers a different question at a unit you can `git show`.

**Capture was dead, and now it isn't.** `transcript.parse_provenance` and
`originrecord.record_transcript` had **zero callers** since the hookless rebuild
removed their SessionEnd trigger, so `cage authorship origin` answered `unknown` for
every commit while working perfectly. The import sweep now writes provenance rows.

**How the agent is measured, and why the human isn't.** A Claude transcript records the
exact text an `Edit`/`Write`/`MultiEdit`/`NotebookEdit` block proposed. At import that
text is compared — transiently, in process memory — against the added lines of the
commit whose window contains the edit. **Only counts are persisted: no line body, and
no line hash** (a hash is a membership oracle over your source). The human is never
observed; it is what is left over, and the label says so.

**Windows, never `HEAD`.** Commit *i* owns `(ts_{i-1}, ts_i]`. Work after the newest
commit is left **unrecorded** and picked up exactly once by the next import — guessing
a commit that does not exist yet would be wrong forever.

**Four line buckets, not three.** Measured on cage's own repo, a single `human` bucket
printed **76.6%** — 89% of it one commit of generated JSON. So the residual splits:
`agent` (matched a proposal) · `human~` (in a file that session *did* propose — a real
human tweak) · `unattributed` (in a file **no** session proposed: a person, a vendored
tree, or generated output — cage does not guess) · `unknown` (below the content gate or
binary). Nothing is redistributed.

### Added

- `cage insights commits` — one row per commit: tokens, human hours, the four-way split.
- `cage insights commit <sha>` — tokens · origin + confidence · line buckets ·
  suggested-vs-kept counts · per-file table · wall/agent/human time.
- `cage authorship summary` — **unknown-rate first**: how much of this repo's history
  cage can speak to at all.
- `cage task time <duration>` — attest your own time (`45m` · `2h` · `1h30m`). Always
  outranks the estimator; parsing is strict, not fail-open.
- `[authorship]` policy table: `capture` (its **own** consent switch — reading your
  diffs is a different permission from metering spend), `estimate_hours`, `max_est_gap`.
  Env: `CAGE_AUTHORSHIP`, `CAGE_AUTHORSHIP_ESTIMATE`.
- Five additive-optional provenance counts (`suggested`, `kept`, `kept_modified`,
  `dropped`, `agent_lines`) — omitted at 0, `schema_ver` stays 1.
- `cage query agent-authorship` explains the whole mechanism with live values.

### Guarantees this release makes

- **No USD, rate or valuation on any authorship surface** — structural, not a policy:
  `commitview.py` imports no pricing module, asserted by AST in the suite.
- **Refusals render.** A commit with no joinable call shows `—`, never `0`; so does the
  Σ row. The hours estimator refuses four ways, each with the reason named — including
  when no agent span joined, where `wall − nothing` would print the raw commit gap as
  effort (v1's exact mistake).
- **Exclusions are counted, never merged.** Per-agent joinability is a stated table:
  copilot-CLI (one shutdown timestamp per session) and kiro (import-time timestamps)
  cannot be window-joined; an unrecognised source is excluded rather than assumed.
- **An unstamped `project` is *unconfirmable*, not adopted** — otherwise a global ledger
  would pull every other repo's spend onto these commits.
- A task closed on a **dirty tree** is not trusted for either calls or hours: its
  snapshot sha is the *prior* commit.

## v0.42.0 (2026-08-02) — `cage insights chats`: one row per chat, titled where the store has a title

Built from: [proposal](docs/archive/v0.42-chats-view.proposal.md) ·
[handoff](docs/archive/v0.42-chats-view.handoff.md) +
[prompt](docs/archive/v0.42-chats-view.prompt.md).

A new derived view, no substrate change: `cage insights chats` groups the ledger's
`calls` by `(agent, surface, session)` — the same bucket key the import manifest
uses — and sums tokens in/out, cached, cache-write and premium per chat, repricing
each call via the existing `call_usd_match` (UNPRICED counted, never a silent `$0`).

**The one law amendment: a scoped, tested carve-out.** `imports.jsonl`'s contract has
always said "never read by a derived view" — this view reads it for exactly one thing,
a **display label**, never a number. `manifest.py`'s docstring now states the carve-out
in one sentence, and `tests/test_chats.py` pins it: deleting `imports.jsonl` moves
**zero** numeric cells, only titles fall back to session ids.

Kiro-IDE's constant session id already collapses every run into one bucket by
construction, so it renders as the honest `kiro (no session identity)` rather than a
fabricated per-chat identity; kiro-CLI conversations are recorded as `credits` (no
`tokens_in`/`tokens_out`) and don't appear here at all — out of scope for v1, same as
Copilot's uncaptured cached/credits columns (COPILOT-CREDITS owns those). Top 20 by
`tokens_in`, `--all` lifts it (the cut is footnoted, no silent caps); `--csv` is never
truncated. Local-only by construction — no `--team`, no MCP tool. `cage query
chats-view` explains it.

## v0.41.0 (2026-08-02) — the agent surface: four layers, three agents, no number moved

Cage's agent integration is now a **ladder**, built end to end in one program. **L0**
hookless capture is unchanged and is still the whole product; **L1** hooks, **L2** MCP
and **L3** skills each sit on top of it, each opt-in, each two-way, and **none of them
able to move a number**.

Built from: [proposal](docs/archive/v0.41-agent-surface-layers.proposal.md) ·
[handoff](docs/archive/v0.41-agent-surface.handoff.md) +
[prompt](docs/archive/v0.41-agent-surface.prompt.md).

### The gate, which is the actual story

**Adding or removing any layer changes no derived number.**
[`tests/test_floor.py`](tests/test_floor.py) installs *every* layer cage ships onto an
already-captured project, asserts the ledger shards **and seven views' stdout
byte-identical**, then strips it all and asserts again — per agent. Three layers landed
across this release and not one figure moved, in either direction. A future layer is
added to `_WIRING_ARTIFACTS`; **an assertion there is never relaxed.** `cage query
agent-layers` explains the contract.

### L2 · MCP — the refusals are the point

- **`cage_verdict` and `cage_compare`** join the read tools. They were the two views
  that answer *"is this tool worth keeping"*, and they were the two an agent could not
  see.
- Both render through the **CLI's own renderer over the CLI's own composer**, so
  `INSUFFICIENT DATA`, `SAVING (GROSS)` and the `MIN_COMPARE_N` block cross the boundary
  **byte-identically** — asserted as *equality with the CLI's stdout*, never as
  substring presence, because a wrapper that printed the phrase and dropped the note
  beneath it would pass a substring test. An agent reads an empty result as **zero**,
  the one thing a refusal never means.
- **`cage_task_outcome` is the only write tool in the entire ladder**
  (`mcpserver.WRITE_TOOLS`, and the module docstring says so where the next reader will
  look). It exists because every starved surface — `compare`, `estimate`, `calibration`,
  the net saving — is starved for one reason: nobody closes tasks. It goes through the
  new `clicmds.close_task`, the **one** task-close path the CLI verb also uses, so the
  single-token label guard cannot be laxer on the agent-facing side.

### Kiro's MCP config is committable at last — the last portability exception, closed

Kiro spawns MCP servers from its *install directory* and substitutes no variables, so
`.kiro/settings/mcp.json` had to carry the wiring machine's absolute cage path and be
gitignored. It now carries **no path at all** — `python3 -m cage mcp` — so the file is
byte-identical on every machine and committed like the other two agents'.

**The price is named, not buried:** that depends on *which* `python3` resolves, so a new
**`kiro-mcp` doctor check** asks that interpreter to import cage and fails with the fix
when it cannot. A venv miss would otherwise be a *silent* no-MCP — the failure class
this project has already paid for twice. **Windows is a stated limit:** `python3` is
often absent there and a committed file can carry one spelling, so the default is
`python3` and doctor points a Windows machine at `cage setup --python-launcher`.

### L1 · hooks + steering (`cage setup --hooks`) — not for capture

Capture already works with no hooks, and a second write path would be a double-capture
risk for no gain. L1 buys exactly three things pull capture structurally cannot:

- **Agent identity, stamped rather than inferred.** A hook runs *inside* the agent, so
  `cage hook <event> --agent X` states it as a fact. Attestations land in
  `state/attest.jsonl` and join the usage breadcrumb on `args_hash` — an **exact** key —
  turning `cage insights adoption`'s half A from agent-blind into per-agent. **A hash
  two agents both claim resolves to unknown, never to a pick.** Commands are **hashed,
  never stored**.
- **Auto task-close** at the session boundary, on the **exact session id** — never the
  most recent task, never by proximity. It writes **`outcome="auto"`, never `ok`**:
  `tasks.jsonl`'s outcome and the quality store (`.cage/outcomes.json`, ok|redo) are
  different axes, so the task is closed for `compare`/`estimate`/`calibration` and stays
  **invisible to `cage task quality`**. Stamping `ok` would silently inflate the success
  rate of every session that merely ended.
- **`budget.check`'s first real caller.** `cage hook budget` exits 2 under `[budgets]
  on_exceed = "block"` — the only place in cage that can stop a paid call *before* it
  happens.

**Fail-open is absolute** (every event exits 0 on any internal failure; the sole
non-zero is the deliberate budget block), and **hooks are CLI-only** — they do not fire
under a VS Code extension, so every L1 fact carries that limit wherever it is shown.

**Every gap is named in output, never left to be discovered.** Per-agent capability is
one table (`agents.HOOK_EVENTS`), and `cage setup --status` prints the shortfalls:
Kiro has no session-start trigger, so its single `agentStop` hook attests the agent but
**declines** to auto-close a task; Copilot has no *verified* pre-tool event, so it gets
no per-tool attestation and no budget block. **No unverified host event name was
invented** — an invented one fails silently. Two-of-three named beats three-of-three
guessed.

### L3 · skills (`cage setup --skills`) — one source, three deliveries

Seven skills — **task-closer · analyst · doctor-triage · honesty-reviewer · release ·
lab-runner · windows-shim** — authored once and rendered into `.claude/skills/<id>/
SKILL.md`, `.github/prompts/<id>.prompt.md` and `.kiro/steering/<id>.md`. Only the
~10-line host wrapper differs; the bodies are byte-identical, asserted rather than
eyeballed.

**Rendered from a Python literal at `cage setup` time, never as a bundled asset** — that
removes the drift-check, `--bless` gate and committed second copy the deleted
`tools/skillgen` needed. **The governing rule: a skill never computes a number — it runs
cage and quotes it.** Method tags verbatim, refusals relayed unsmoothed, no arithmetic.
`steering.lint` enforces it mechanically, and every `cage …` a document names is checked
against the **live parser** — a skill teaching a dead verb is the F1 class in prose.

### Also

- **Residue cleared:** the README claimed a `cage` skill three times, once on *"all four
  agents"* — wrong twice over, and live on PyPI since v0.36. `CLAUDE.md`'s wiring bullet
  and `docs/example/setup.md` described hooks, skills and git hooks that `cage setup`
  has not written since the hookless rebuild.
- New `attest-log` cleanup class; `wiringscan` now scans hook artifacts too, so a
  renamed verb cannot silently kill L1; `cage query agent-layers`.
- **1024 → 1125 tests.**

### Known limits, stated

- **ADOPT-COV is not closed by this.** Attestation resolves adoption's half **A** only —
  a graphify savings row's id folds in an *answer* hash no attestation can reconstruct,
  so half B's `no-link` remains structurally true.
- The L1 hook shapes and the path-free Kiro MCP entry are unit- and CI-tested but have
  **not** been run on a real Claude Code / Copilot / Kiro install. Tracked as
  **L1-FIELD** and **KIRO-MCP-FIELD** in [OPEN-WORK.md](docs/OPEN-WORK.md).

## v0.40.0 (2026-08-02) — tool-adoption view

Does the tool you installed actually get *used*? One new derived view answers it. No
substrate change, no schema change, no new capture path — and no currency anywhere in
it.

Built from: [proposal](docs/archive/v0.40-insights-adoption.proposal.md) ·
[handoff](docs/archive/v0.40-insights-adoption.handoff.md) +
[prompt](docs/archive/v0.40-insights-adoption.prompt.md).

`cage insights adoption` — do the agents you wired actually **invoke** the tools you
gave them? A derived view only: no new capture, no schema change, no new field. Its
whole value is a boundary between three unknowns — *never invoked* · *invoked and cage
filed nothing* · *invoked and cage cannot say by whom* — so it renders **two halves that
are never blended into one number**.

#### Added

- **A · invocations + outcomes** — from the usage breadcrumb, exact and **agent-blind**:
  a usage row is `ts · op · args_hash · exit · ms · outcome · route` and carries no
  `agent` field. Broken down by `op` and by `route`. The per-outcome tally **reads** each
  row's recorded `outcome` (`receipt` / `unmeasurable` / `empty` / `non-measured` /
  `error`); "ran and cage filed nothing" is a written verdict, never re-derived from the
  receipts — re-deriving it would produce a second, disagreeing answer.
- **B · per-agent attribution** — savings rows joined to `calls.agent`: a linked `call`
  id first (exact), else a `session` that **exactly one** agent's calls carry. Each row
  is labelled with which link carried it, so the two joins are never passed off as one
  another. A session shared by two agents stays **unknown** rather than resolving to an
  arbitrary name.
- `--csv` (the `section`/`dimension` columns keep the halves apart when flattened; a cell
  that does not apply is **empty**, never a `0`), `--json`, `--since`, an MCP mirror
  (`cage_adoption`), and `cage query tool-adoption`.

#### Decided — an empty half B renders its refusal, it never vanishes

If every invocation came through the interceptor, nothing is attributable. The half still
prints, as an explicit refusal naming the count and the cause. Suppressing it would make
*cage cannot attribute these* indistinguishable from *cage has no per-agent answer at
all* — the exact conflation the view exists to prevent.

#### Decided — agent-unknown is split by cause, and is never an "other" bucket

`no-link` (no call, no session) is **structural**: the interceptor runs as a subprocess
and genuinely cannot know which agent spawned it, so it stamps an empty session on
purpose. `unjoined` (a link nothing in the ledger matches) is a **capture gap**.
Different facts, different fixes, so they are never merged — and neither is ever
attributed by timestamp proximity.

#### Decided — "never invoked" is never asserted, and has two strengths

*No evidence of invocation* is sound **only when every savings row found an agent**. With
even one agent-unknown row on the table, that row could belong to the very agent being
named, so the claim drops to *no savings row attributed to them*. Neither form is ever
stated as proof of non-use. (This corrected both the proposal, which said *never
invoked*, and its handoff, which softened it only one step.)

#### Unchanged — deliberately

- **No currency anywhere in the view.** This is the first reader of the `state/` usage
  log, so it is the one place a count could quietly become a price. It never does, and
  the diagnostic-only invariant is now asserted from this new caller too.
- **Surface is not a dimension.** Claude Code's CLI and its VS Code extension share one
  store with no marker, so splitting by surface would invent a fact.

## v0.39.0 (2026-08-02) — OTel GenAI export; Codex agent residue removed

Two independent tracks landed the same day: a new one-way export format, and a
cleanup of what the v0.33.0 Codex-agent removal left behind. No substrate or
determinism-law change in either.

Built from: [OTel handoff](docs/archive/v0.39-otel-export.handoff.md) +
[prompt](docs/archive/v0.39-otel-export.prompt.md) · [Codex-purge
handoff](docs/archive/v0.39-codex-purge.handoff.md) +
[prompt](docs/archive/v0.39-codex-purge.prompt.md).

### OTel GenAI export (OTEL)

`cage data export --otel` — a one-way export of the ledger as OpenTelemetry
GenAI-conformant JSON, alongside the existing `--csv` / `--study` / jsonl formats.
Cage stays the `$0` local ledger and feeds the enterprise stack (Langfuse, Helicone,
any OTLP sink) instead of competing with it.

#### Added

- **Calls map to GenAI attributes**: `gen_ai.system` (provider) ·
  `gen_ai.request.model` · `gen_ai.usage.input_tokens` / `output_tokens` ·
  `gen_ai.client.operation.duration` (seconds, from `latency_ms`) — omitted, never a
  fabricated zero, when a call's latency was never captured.
- **`cage query otel-export`** explains the mapping, the pre-stable caveat, and the
  receipts/savings decision below.

#### Decided — the GenAI conventions are pre-stable

As of semconv v1.42.0 (June 2026) the `gen_ai.*` attributes live in a dedicated repo,
carry no 1.0, and names can still change between releases — which collides with
cage's determinism law (same ledger + policy ⇒ same output). So the targeted version
is **pinned in one constant** (`constants.OTEL_SEMCONV_VERSION`) and **stamped in
every emitted document's `cage.meta` block**; a spec bump is a deliberate,
changelog'd change, exactly like `prices_version`. Help text and docs say
"pre-stable".

#### Decided — receipts/savings have no GenAI equivalent

No `gen_ai.*` name is invented for cage-only data. Every receipt/savings row lands
in a separate `cage.savings` array under `cage.*` keys (`cage.tool`, `cage.saved`,
`cage.method`, `cage.confidence`, …). `cage.saved` is always GROSS
(`netsaved.GROSS_NOTE`); `cage.saved_usd` prices through the same `receiptprice`
resolution ladder every other view uses and is **omitted, never `$0`**, on an
UNPRICED ladder refusal or a non-money unit (`ms`/`gco2`). `cage.method` always
survives so a `modeled`/`estimated` figure can never arrive at a vendor looking
measured. Legacy Tier-1 human-axis rows (axis removed v0.36) are excluded, counted
in `cage.meta.legacy_human_excluded`.

#### Unchanged — deliberately

- **`dependencies = []`** — stdlib `json` only; no `opentelemetry-*`, no HTTP client,
  no OTLP SDK. Not an OTLP exporter — cage writes a file, the user's collector
  ingests it.
- **One-way REPORTING, exactly like `--csv`** — never an import source. The fleet
  bundle (`--study`) stays jsonl.

### Codex residue removed (CODEX-OUT)

Support for the Codex **agent** ended in v0.33.0; this removes what was left behind.

#### Removed

- **`paths.codex_home()` and the `CODEX_HOME` env read**, `wiringscan`'s
  `~/.codex/config.toml` scan and its `.codex/hooks.json` enumeration, doctor's
  `.codex/hooks.json` read, and `CODEX_HOME` from the `cage doctor --bundle` env
  allowlist.
- **The trade this makes, stated rather than buried: cage can no longer detect a stale
  `cage` verb in a pre-v0.33 `~/.codex/config.toml`.** A machine still holding one keeps
  a dead verb forever, undetected — the user-level F1 class the wiring-liveness check
  exists to catch. Accepted (Arpit, 2026-08-01): Codex has been unsupported for five
  releases, nobody on a supported upgrade path starts from a pre-0.33 install, and
  carrying scan code for a product cage will never support again is its own liability.

#### Unchanged — deliberately

- **`data/prices.toml` is byte-identical.** `gpt-5.3-codex`, `gpt-5.2-codex`,
  `gpt-5.1-codex{,-max,-mini}`, `gpt-5-codex` and `codex-mini-latest` are **OpenAI model
  ids that Copilot emits**, not the removed agent — the file has said so at the row since
  v0.33. Deleting them would silently UNPRICE real Copilot traffic.
  `policy.normalize_model`'s `…-codex-high` → `…-codex` effort fold stays for the same
  reason. A new regression guard
  (`test_pricing.test_codex_model_ids_are_not_the_codex_agent`) prices a Copilot call on
  every one of those ids, so the next blind `grep -i codex` fails loudly instead of
  costing money.

## v0.38.0 (2026-08-01) — graphify is metered on Windows; CI grows a graphify axis

Closes the gap v0.37.2 disclosed. The graphify PATH interceptor was a single
extensionless bash script, and Windows resolves a bare `graphify` **only** through
`PATHEXT` — which has no extensionless entry — so on Windows cage's interceptor could
never be *found*. The shim capture route was structurally absent there, and no amount
of PATH ordering could rescue it.

Built from: [handoff](docs/archive/v0.38-win-graphify-shim.handoff.md) ·
[prompt](docs/archive/v0.38-win-graphify-shim.prompt.md) ·
[CI harness handoff](docs/archive/v0.38-ci-graphify-matrix.handoff.md).

- **A `graphify.cmd` twin ships as bundled data.** Plain text — no `.exe`, nothing
  compiled, no new dependency, and it works from `cage.pyz`. PowerShell was ruled out on
  a hard fact: `.ps1` is absent from the default `PATHEXT`, so a `graphify.ps1` could
  never be found by a bare `graphify` — the exact bug being fixed.
- **One written behaviour contract, two implementations**
  ([docs/shim-contract.md](docs/shim-contract.md)). Eight binding behaviours (re-entry
  guard, PATH scan skipping *every* interceptor, content-based self-identification, the
  127 rule, the capability probe, transparent passthrough, no leaked state, a bounded
  walk) and seven documented divergences. **cmd has no `exec`**, so the real binary runs
  as a child process via `call` + `exit /b` — Ctrl-C prompts `Terminate batch job
  (Y/N)?`. That is recorded as a divergence, not papered over as parity.
- **Recursion is impossible by four independent mechanisms**, and the twins are
  *structurally* incapable of selecting each other: the cmd twin only ever considers
  `PATHEXT` candidates and the sh twin only ever considers the extensionless name. Both
  stacked pairings (`bash + cmd`, `cmd + cmd`) are tested.
- **`cage setup` installs both twins on every OS**, mirroring `runshim.write` — a
  committed `bin/` that is byte-identical on every machine is what lets a project
  scaffolded on macOS keep working when it is opened on Windows. `refresh_shim` now
  *completes* the pair when either twin is present, which is the upgrade path for a
  project scaffolded before the `.cmd` existed.
- **Liveness before the flip** (the F1 lesson, on a new OS). `pathshim` no longer treats
  the extensionless name as a Windows candidate — it could never run there, and counting
  it produced a false ✅. `cage doctor` gained the twin check: an interceptor that
  exists, sits on PATH and names live verbs but that **this OS cannot resolve** is now a
  *failure* with a runnable fix, not a green tick. `wiringscan` scans both committed
  copies and names the offending file.
- **CI grows a graphify axis (CI-GF).** `python-package.yml` keeps its `absent` leg
  byte-identical and adds a `present` job on all three OSes: install real graphify
  (pinned), build a graph over the new committed `tests/fixtures/cicorpus/`, invoke a
  **bare `graphify query` through the platform shell**, and assert a savings row lands.
  Also asserted: passthrough, doctor `live`, a deliberately killed shim reporting `dead`
  and being healed, and determinism. graphify is AST-only, so the whole leg costs **$0**.
  It skips loudly (never fails) if the pinned install flakes.
- **Two handoff assumptions corrected by contact with reality.** graphify is a **PyPI**
  distribution (`graphifyy`), not npm — on Windows it installs as `Scripts\graphify.exe`,
  so the twin never shares a filename with the real binary, but `.EXE` precedes `.CMD` in
  the default `PATHEXT`, so the twin must never share a *directory* with it. And
  `graphify query` emits its lines in a different order every run, so the CI passthrough
  check compares content, not bytes — a byte comparison would have flaked forever.
- **Known gap, stated rather than half-fixed:** under `cage setup --python-launcher`
  there is no `cage` command on PATH, so the interceptor degrades to correct *unmetered*
  passthrough. That is true of both twins; fixing one alone is exactly the drift the
  contract exists to prevent.
- **GF-DEBT, same change:** restored the deleted `docs/restricted-environments.md` (8
  citing files), stated the python-launcher/graphify-metering conflict (GF-LAUNCHER) in
  the README, that doc, and a new `cage doctor` `launcher-gap` check, added the
  `cage query graphify-shims` explainer, filed [ADR 0007](docs/adr/0007-graphify-twin-pair-hand-paired-not-templated.md)
  for the hand-paired-twin decisions, updated cage-lab to state POSIX-twin-only
  coverage, and wrote + regression-tested the CI-corpus sizing rule (a too-small corpus
  makes every query honestly `unmeasurable`, which had let an early draft of the
  `present` leg pass while proving nothing).
- **Two real bugs, found by actually running this on Windows CI before release — five
  pushes to get to a correct diagnosis.** Every attempt hit the identical cmd.exe abort
  (`Recursion Count=335, Stack Usage=90 percent, BATCH PROCESSING IS ABORTED`), which
  made the first two hypotheses wrong: rewriting the walk from `call :subroutine` +
  `goto` back-edge to a flat nested `for` (directories × PATHEXT) is a real correctness
  improvement — provably terminating, no subroutine call — but did **not** fix the
  observed failure, and neither did switching the test harness's invocation from an
  argv list to `shell=True`, nor from a quoted absolute path to bare-name PATH
  resolution. The actual causes, found by comparing against the `present` CI leg
  (which passed the whole time, against the identical committed file):
  1. **In the shim itself:** a `rem` comment sitting *inside* the nested `for` block
     read `"<candidate>"` — cmd.exe's parser still tokenizes redirection characters
     inside a comment when that comment is nested inside a multi-line `(...)` block,
     and the `<`/`>` corrupted the block's parsing. Fixed by moving every comment
     outside of every parenthesized block.
  2. **In the test harness, not the shim:** `tests/test_win_graphify_shim.py`'s `_run()`
     wiped `PATH` down to just the test's tmp directories, so the shim's own calls to
     `findstr.exe`/`where.exe` (living in `System32`) had nothing to resolve them
     through. Fixed by prepending the test directories onto just enough real system
     directories, never the whole inherited `PATH` (which would risk exposing a real
     `cage` and defeating the tests' "cage absent" assumption) and never nothing.
  All 12 CI jobs (6 OSes × leg combinations, including the Windows behaviour tier and
  the `present` axis on all three OSes) are green as of the tag.

## v0.37.2 (2026-08-01) — README tells the truth; the knowledge graph is committed

A documentation and repo-hygiene release. **No code, substrate, schema, or CLI change**
— `cage/` is byte-identical to v0.37.1 apart from the version string, so upgrading
changes nothing you run. It ships because the README *is* the PyPI project description,
and the old one was selling a capability that no longer exists.

- **README no longer sells the removed Tier-1 human axis.** The pitch claimed cage
  shows "how much money *and time* the agent saved versus a person" and that it
  measures chores "in real minutes" — the axis was amputated wholesale in v0.36.0
  (`human.py`/`trend.py`/`[human.*]`/the `minutes` unit, substrate included) and is
  not coming back without a proposal doc. The lede and the plain-language section now
  describe what cage actually does: per-tool savings **gross and net of what invoking
  the tool cost you**, counterfactual stacks, and which tools agents actually adopt.
- **The gross-vs-net honesty is now in the pitch, not just the code.** The story
  section states outright that cage's own paired run came back with the graph-tool arm
  costing *more*, and that it printed that rather than burying it, linking
  [the finding](docs/regression/2026-08-01-finding-saved-is-gross.md). A new
  parenthetical under the worked table marks it as seeded demo data and says where
  cage's own evidence actually stands — lab-validated capture on macOS across all
  three agents, and a net-positive verdict that is honestly **still open at n=1**,
  which `cage insights verdict` refuses to call a saving.
- **The Windows graphify gap is disclosed in the platform line**, not only in the
  changelog and OPEN-WORK: the interceptor is a bash shim, so on Windows the shim
  route does not exist and graphify savings arrive via the transcript route only.
  Tracked as **WIN-GF**; a `.cmd` twin is specced.
- **The graphify knowledge graph is now committed** (`graphify-out/`,
  `docs/graphify-out/`). `.gitignore` narrowed from the whole tree to
  `**/graphify-out/cache/`, so `GRAPH_REPORT.md` + `graph.json` + the manifests are
  tracked and any agent or CI job can read the graph without regenerating it —
  which is what this repo's `CLAUDE.md` already instructs agents to do before
  answering architecture questions. Deliberate trade: ~10 MB of generated blobs
  enter history, and `graphify update .` will produce large diffs.

## v0.37.1 (2026-08-01) — Windows dev-CI: graphify subprocess + test fixes

A second same-day follow-up: v0.37.0 fixed the release-critical Windows crash (a
malformed `cage.toml`), but the broader dev-CI matrix (`python-package.yml`, which
runs pytest directly on all three OSes — a surface `publish.yml`'s zipapp-only smoke
chain doesn't cover) was still red on `windows-latest` across ~15 tests. None of these
affect the shipped v0.37.0 package; they're either a real subprocess-execution gap or
Windows-only test-assertion bugs, both exposed by v0.36.0's new graphify-integration
test files (`test_graphify_copilot.py`/`test_graphify_transcript.py`/
`test_graphify_usage.py`/`test_hookbypass.py`) running on Windows CI for the first time.

- **Fix: `cage data graphify` crashed on Windows (`WinError 193`) when the target was
  a shebang script without a native-executable extension.** `subprocess.run`/
  `CreateProcess` never honors `#!` — that's POSIX kernel behavior — so a non-`.exe`/
  `.cmd`/`.bat` target failed outright even though a real npm-installed `graphify.cmd`
  is unaffected. `graphifymeter._resolve_argv` now peeks the shebang on Windows and
  prepends its interpreter (a `python`/`python3` shebang resolves to `sys.executable`
  rather than trusting a same-named PATH binary).
- **Fix: `hookbypass._tokens`' Windows tokenizer left quote marks in a token.**
  `shlex.split(..., posix=False)` (needed so an unquoted native `C:\...` path keeps its
  backslashes) doesn't strip surrounding quotes the way posix mode does — a quoted
  path with a space was never recognized as a graphify hook invocation. Now unquoted
  after non-posix tokenization.
- **Two tests asserted an absolute sink path** (`test_kiro_routing.py`,
  `test_import_unified.py`) where the printed line correctly uses the tilde-relative
  form (`importcmd._tilde`, deliberately "machine-portable in tests" per its own
  docstring) — true on Windows CI because `%TEMP%` sits under `%HOME%` there, unlike
  the POSIX runners' sandbox temp dirs. Both now compare against `_tilde(...)`.
- **One test wrote a raw Windows path into a TOML string** (`test_kiro_routing.py`'s
  `test_cli_credits_import_is_scoped_and_stamped`) — the same backslash-escape bug
  v0.37.0 fixed in `paths.sources_toml`, here in test setup. Fixed with `.as_posix()`.
- **Filed, not fixed:** `cage`'s own graphify interceptor (`cage/data/shims/graphify`)
  is a bash script with no extension, so it can never be *found* via a bare `graphify`
  PATH lookup on Windows (PATHEXT requires a recognized extension) — independent of
  today's subprocess fix, which only helps once something has already located the
  shim by an exact path. A real fix needs a Windows-native twin with equivalent
  PATH-scan/recursion-guard logic — a feature-sized project, tracked as **WIN-GF** in
  [docs/OPEN-WORK.md](docs/OPEN-WORK.md), not attempted here.

No substrate, schema, or CLI-surface change.

## v0.37.0 (2026-08-01) — Windows sources.toml crash + dummyrepo sync

A same-day follow-up to v0.36.0: the release-CI smoke chain (which only runs the exact
built `cage.pyz` against three OSes, never the wheel) caught a real Windows-only crash
in the config materialized by `cage setup`, plus a batch of stale assertions in the
out-of-tree `tools/dummyrepo` scenario suite that v0.36.0's own pytest-suite update
never propagated to. `just test` (962 tests) was green through both — this class of
gap only shows up in the black-box smoke chain, which is exactly why it exists.

- **Fix: `cage setup` wrote an unparseable `cage.toml` on Windows.** `paths.sources_toml`
  rendered a built-in agent log path straight into a TOML basic string — a raw Windows
  `\` there is an escape character (`\A`, `\U`… aren't valid TOML escapes), so every
  fresh Windows project's materialized `[sources]` block failed to parse. Because
  `metering.record_call`'s policy load isn't wrapped for this (a separate, narrower gap
  than the write-path fail-open law — tracked, not touched here), the first metered call
  after `cage setup` — e.g. `cage demo` — crashed outright. Fixed by normalizing every
  written `path`/`glob`/`path_globs` value to `/` (the same normalization `path_globs`
  already applies on *read*; Python's `pathlib`/`Path.glob` accept `/` on every OS).
- **`tools/dummyrepo` resynced to v0.36.0's actual behavior** (10 of 18 scenarios were
  failing): the `cage.toml` rename (6 literal `policy.toml` paths), kiro's IDE-log rows
  now routing to the machine ledger instead of the project one (ADR 0006 — `assert_exact_rows`
  now asserts kiro's rows against `$CAGE_HOME` instead of folding them into the project
  comparison), Directive A's "no `[sources]` ⇒ captures nothing" (a fleet-simulation
  machine that never ran `cage setup` now does, before the scenario exercises its import
  sweep), the `[prices]`/`[meta] prices_version` split (a stray write landed in the wrong
  file), `[budgets]` going opt-in/commented-out (BUD-V — the sync-mechanics scenario now
  exercises `[quality] signal`, mirroring `tests/test_policysync.py`'s own re-point), and
  the new `import_id` manifest FK (minted fresh every sweep — now always volatile in the
  row-equality check, not just fixture-declared fields).
- **`imports.jsonl`'s scenario PII scan false-positived on a documented, deliberate
  design decision** (import-ledger plan §7): the manifest always captures a
  best-available human-authored session title now, a conscious widening scoped to that
  one local audit file. `assert_pii_clean` excludes it from the generic
  counts-never-content marker scan.

No substrate, schema, or CLI-surface change — every fix above is either a Windows
write-path correctness fix or test-scaffold debt from v0.36.0's own changes.

## v0.36.0 (2026-07-25) — hookless rebuild + import ledger (Phases 0–4)

A two-part release: **finish the conversion to pull-only capture** (remove all hook
machinery and rendered agent assets), then build the **import-ledger plan** on the
simplified base. Every new row field is additive-optional (absent ⇒ byte-identical
legacy row); the determinism/method laws are untouched.

Built from: [docs/archive/v0.36-hookless-rebuild.handoff.md](docs/archive/v0.36-hookless-rebuild.handoff.md)
+ [docs/archive/v0.36-hookless-rebuild.prompt.md](docs/archive/v0.36-hookless-rebuild.prompt.md)
· and [docs/archive/v0.36-names-and-savings-migration.handoff.md](docs/archive/v0.36-names-and-savings-migration.handoff.md)
+ [docs/archive/v0.36-names-and-savings-migration.prompt.md](docs/archive/v0.36-names-and-savings-migration.prompt.md)
· plan of record [docs/archive/v0.36-import-ledger-savings.plan.md](docs/archive/v0.36-import-ledger-savings.plan.md).

### Phase 0 — hookless (the removal, finished)

- **Capture is pull-only.** All hook writers (`hooks.py`, `gitcommithook.py`), the agent
  hook wiring, the rendered skill/prompt/steering assets, `tools/skillgen`/`tools/docgen`,
  and the wizard/`setupcmd` are gone. `cage import` + capture-on-read is the universal
  path; **MCP is the only wired surface** (`.mcp.json` / `.vscode/mcp.json` /
  `.kiro/settings/mcp.json`). `cage setup` now scaffolds + wires MCP + the graphify shim.
- **A stale hook is healed, not left firing.** Old `cage hook-*` invocations print a
  direction and exit 1 (`verbmap.REMOVED`); `cage setup` strips stale cage hook entries
  from `.claude/settings.json` and deletes cage-owned copilot/kiro hook files (foreign
  hooks untouched). The three dead-wiring mitigations (verbmap entries, wire-module
  heal-by-removal, `wiringscan` leftover detection) are kept.

### Phase 1 — enriched call row + loud import summary

- **`cage import` prints the numbers.** A per-agent×surface rollup — calls, tokens_in,
  cached, tokens_out, **cost** — with rows the price table can't match (`copilot/auto`,
  kiro `agent`) surfaced as **UNPRICED**, never a silent `$0`.
- **Additive call-row fields:** `surface` (`cli`/`vscode`/`ide`/`""` — derivable for
  copilot & kiro, honestly empty for claude's shared store), `cache_write_in` (Claude's
  cache-creation tokens split out; `tokens_in` semantics unchanged), `premium` (copilot
  CLI `totalPremiumRequests`), `import_id` (the capture-manifest FK).

### Phase 2 — dedicated savings tree

- Tool savings now land in **`savings/<tool>/savings-YYYY-MM.jsonl`** (graphify first),
  written through `savings.record()`. `ledger.receipts()` reads the tree unioned with
  legacy `receipts.jsonl`, so every attribution/roi/report surface reads them unchanged.
  (Revised below to an **id-deduped** union so a migrated row in both stores counts once.)

### Phase 3 — capture manifest

- A new **`imports.jsonl`** records one audit row per import sweep and per graphify run —
  what cage captured, when, from where (tilde-relative, PII-safe), and how much.
  `import_id` is threaded onto every call/savings row it produced. (Revised below: the
  import row is now **per-session** and **always** carries the session name.)

### Phase 4 — task correlation (gated, disabled-by-default)

- A best-effort `task` backfill (`cage/taskcorr.py`) correlates import-sourced calls to
  closed tasks by the `taskgroup` session-window join, tagged `estimated` — **derive-time
  only, never mutating the ledger.** Ships **disabled** (`[capture] task_correlation`)
  behind a blocking min-n gate until validated on real data (plan §7 decisions log).

### Revisions (Arpit, 2026-07-25) — session names always-on + precise savings migration

- **Session names are always captured.** The `[capture] session_names` opt-in (and
  `policy.session_names_enabled` / `CAGE_SESSION_NAMES`) is **removed** — `imports.jsonl`
  now emits **one row per (agent, surface, session)**, each with a cage-minted
  `session_uid` and the best-available `session_name`: claude ← the transcript `summary`
  record (fallback the cwd basename); copilot VS Code ← the chat `customTitle` (else the
  auto `generatedTitle`); copilot CLI / kiro ← `""` (honest empty, never fabricated);
  graphify ← the task. The name is a deliberate PII widening for this **local audit file
  only** — it never touches a call/receipt/savings row and is never read by a derived view.
- **`cage data migrate-savings`** consolidates historical graphify receipts into
  `savings/graphify/` **precisely — not wrong, not duplicated.** Dry-run by default (prints
  per-store row count + Σ`saved` and exactly what would copy); `--apply` **copies** each
  `tool="graphify"` row verbatim (original id, own-`ts` shard) and **refuses** if the two
  stores disagree on a shared id's `saved`. `receipts.jsonl` is never rewritten.
  `ledger.receipts()` is now an **id-deduped union** (tree wins), so a row in both stores
  counts exactly once: re-runs are no-ops, a half-completed migration still reads correct
  totals, and attrib/report/roi are byte-identical before/after. `cage query
  migrate-savings` explains why the number stays exact.

### Config surfaces + `cage.toml` rename (2026-07-27)

Two config changes, each additive and byte-identical when unused. Built from:
[docs/config-surfaces-and-rename.handoff.md](docs/archive/v0.36-config-surfaces-and-rename.handoff.md)
+ [docs/config-surfaces-and-rename.prompt.md](docs/archive/v0.36-config-surfaces-and-rename.prompt.md).

- **A source can now declare its `surface`.** `[sources.<x>] surface = "cli|vscode|ide"`
  (both the table and array-of-tables shapes) restamps every imported row's `surface` —
  so pointing cage at a **non-IDE** store no longer inherits the parser's hardcoded value
  (a Kiro CLI log was silently stamped `ide`). Validated against the closed set; an
  out-of-set value is a `problems` entry (the sweep stays fail-open), and **absent ⇒ the
  parser's own value stands, byte-identical**. `cage doctor --paths` gains a `surface`
  column (declared / `parser`); `cage query sources` documents the key.
- **The config file is now `cage.toml`** (was `policy.toml`). **Never a breaking rename:**
  `policy.toml` is still read as a fallback (releases ≤ v0.35 wrote it), `cage setup`
  migrates a lone legacy file (idempotent, non-destructive if both exist), and when both
  sit side by side **`cage.toml` wins** — `cage doctor` names the ignored leftover and a
  one-line stderr warning fires at load (stdout unchanged). One resolution point
  (`paths.Footprint.policy`); `cleanup` never touches either name.

### Model prices split into `prices.toml` (2026-07-28)

Vendor prices get their own file, apart from your policy. Built from:
[docs/archive/v0.36-prices-toml.handoff.md](docs/archive/v0.36-prices-toml.handoff.md)
+ [docs/archive/v0.36-prices-toml.prompt.md](docs/archive/v0.36-prices-toml.prompt.md)
· plan of record [docs/archive/v0.36-prices-toml.plan.md](docs/archive/v0.36-prices-toml.plan.md).
**The money does not move** — `report`/`insights attrib`/`insights roi` are
byte-identical before and after, verified on a real 40k-row ledger.

- **`.cage/prices.toml`** now holds every `[prices.<provider>.<model>]` row, `[credits]`,
  and the `[meta] prices_version/prices_date` counters — the **vendor rate card**, which a
  wholesale `cage prices sync` can replace without touching your policy. `cage.toml` keeps
  everything else, including the **routing decisions** (`[alias]`, `[tools.<tool>]
  price_at`) and `[meta] cage_version/policy_version`. The governing rule: **vendor facts
  move, routing decisions stay.** `[meta]` splits *per key* so a staleness check can't
  quietly stop firing.
- **Never a breaking change.** A legacy project with prices still inline in `cage.toml`
  is **read untouched** via the fallback; `cage setup` **migrates** it to `prices.toml`
  **money-neutrally** (rows equal to the bundle drop and re-resolve from it; customizations
  become `# cage:custom` overrides), idempotent and non-destructive. With both carrying
  prices, **`prices.toml` wins** — `cage doctor` names the ignored in-`cage.toml` block and
  a one-line stderr warning fires at load. Applies to the global `~/.cage` config too.
- **One resolution point** (`paths.Footprint.prices`), one merged dict from `policy.load`
  (no consumer changed), the bundle split into `data/cage.toml` + `data/prices.toml` (both
  resolve from the zipapp), and `cleanup` now protects `prices.toml` alongside `cage.toml`.
  `cage prices set`/`sync` write `prices.toml`; `alias`/`route-tool` write `cage.toml`.
  `cage query prices-file` explains the split.

### Removed — the Tier-1 agent-vs-human axis, substrate included (2026-08-01) ⚠ BREAKING

The whole-task *agent vs human* baseline is **gone**, deliberately and completely —
not deprecated. It will be reconsidered from scratch after this release
(a proposal doc, not a `# v2:` stub in the tree).

Built from: [docs/archive/v0.36-human-removal.handoff.md](docs/archive/v0.36-human-removal.handoff.md)
+ [docs/archive/v0.36-human-removal.prompt.md](docs/archive/v0.36-human-removal.prompt.md).

**Note the *other* "human" is untouched.** Provenance `origin="human"`
(`cage authorship origin|verify`, `schema.ORIGINS`) answers *who wrote a commit*,
never *what a person would have cost*. It shares a word and nothing else.

- **Commands removed:** `cage human show` · `cage human record` · `cage insights trend`
  · `--human` on `insights matrix` and `insights calibration` · `--agent-only` on
  `insights compare` / `insights verdict` / `study report` (it suppressed a line that
  no longer exists). The `Agent vs human` and `Savings trend` blocks leave the
  `cage data serve` dashboard.
- **Commands MOVED, not removed:** `cage human outcome` → **`cage task outcome`** and
  `cage human quality` → **`cage task quality`**. Neither was ever the human axis —
  they lived in that group by filing accident. `outcome` is the **task-close verb**
  every cost-impact view depends on (`compare`/`estimate`/`calibration` read only
  closed tasks) and `quality` is cost-per-successful-task (§8.2); deleting them would
  have amputated the §4.7–§4.8 surface. A new `task` group replaces `human` in the
  front door. `cage task outcome` loses only its `--minutes` attestation flag.
- **Modules deleted:** `human.py` · `humanview.py` · `trend.py` · `attention.py`.
- **Substrate contract change (plan §3.1, §4.10):** call rows no longer carry
  `gap_ms` (turn-gap capture is out of `transcript.py`), `"minutes"` is out of
  `schema.UNITS`, `IDLE_CAP_MINUTES` is out of `constants.py`, and every `[human.*]`
  table is out of the bundled `cage.toml`. `policy.human_rates` /
  `policy.human_rate_source` / `metering.record_human` / `cage.record_human` are gone,
  and `CAGE_HUMAN_RATE` is no longer read.
- **Old ledgers still read — and the exclusion is *stated*, never silent.** Rows are
  append-only and are never rewritten, so pre-0.36 `gap_ms` calls and
  `tool="human"` / `unit="minutes"` receipts are still on disk. They parse fine and are
  **excluded from every money view**, because there is no longer a rate to price them
  at. That exclusion is a decision, so `cage report` **counts and footnotes it**:
  `· N legacy human-axis receipt(s) excluded from savings …`. Dropping them quietly
  from a total was the one option ruled out. `cage query savings-axis` explains it;
  `tests/test_legacy_ledger.py` pins the whole contract.
- **Wiring migration:** `cage human`, `cage human-record` and `cage trend` print a
  written direction and exit 1 (`verbmap.REMOVED` + the new `_BODIES` map, for verbs
  whose removal needs a sentence rather than a "is now" tail); `cage outcome` /
  `cage quality` redirect to their `task` spellings. `tests/test_cli_tiering.py`'s
  grouped-verb allowlist dropped `human` — which immediately surfaced five stale
  `cage human …` strings the looser pattern had been hiding.
- Dummyrepo scenario **S10** (derived attention) is removed with the feature.

### Kiro capture routing — two stores, two opposite fixes (2026-08-01) ⚠ BEHAVIOUR CHANGE

Kiro is a paid tool and its cost was being counted more than once. Decision + veto
condition: [ADR 0006](docs/adr/0006-kiro-rows-are-machine-facts-not-project-facts.md).
Built from: [docs/archive/v0.36-kiro-routing.handoff.md](docs/archive/v0.36-kiro-routing.handoff.md)
+ [docs/archive/v0.36-kiro-routing.prompt.md](docs/archive/v0.36-kiro-routing.prompt.md).
Evidence: [the double-count finding](docs/regression/2026-08-01-finding-kiro-rows-double-count-across-ledgers.md).

- **Kiro IDE rows now land in the machine ledger (`~/.cage`), never a project `.cage/`.**
  `tokens_generated.jsonl` is ONE global append-only file carrying no project, no session
  and no timestamp, so every ledger that imported it read the same turns — a per-project
  kiro cost was never a fact. One copy now exists per machine, so double-counting is
  impossible **by construction** rather than by warning. An explicit `--ledger`/`CAGE_BASE`
  still wins (cage never routes around a sink you named), which is what keeps cage-lab
  isolated.
- **Kiro CLI credits get the opposite fix: scoped, not routed.** `conversations_v2` is
  keyed by the cwd it ran in and carries a real conversation id, so it *is*
  project-attributable. It is now read **scoped to the project's directory tree** (the
  tree, so a conversation started in `repo/sub` still counts) and stamps the additive
  optional `project` on the credit row. The double-count there came from the opposite
  defect — the importer read with no workspace filter at all.
- **Already-recorded rows are NOT rewritten.** Append-only holds: a project ledger that
  collected duplicated kiro rows before this change keeps every one of them and simply
  gains no new ones. **This fixes the future only** — if you read "kiro double-counting
  fixed" and your old numbers look unchanged, that is the fix working as specified, not
  failing.
- **A project report explains kiro's absence rather than showing nothing** — silence is
  indistinguishable from broken capture. New footer line naming the machine ledger,
  `cage doctor`'s capture timeline and `cage doctor --paths` name kiro's sink, and
  `cage query kiro-routing` explains the whole split.
- **The two HONEST-LIMITs are now stated where they could be misread** — kiro rows carry
  no per-turn time, session or project (called out by name under `--since`, where the
  import-time `ts` makes a window *wrong* rather than merely coarse), and a blank
  `surface` reads as "the source does not say", never "cli".
- **Internals:** `paths.kiro_ledger`/`kiro_routed`/`kiro_cli_workspace` are the single
  home of both rules. The routed leg is fully contained (own lock, `seen`, cursors,
  health, capture-log breadcrumb and manifest) and completes before the sweep's own lock
  is taken, so no process ever holds two import locks. The capture switches compose as
  **AND** — the project's and the machine ledger's must both be on. claude/copilot capture
  is asserted byte-identical, and the import summary is asserted never to count a row that
  landed in another ledger (`tests/test_kiro_routing.py`).

### Gross vs net savings — `saved` says what it is (2026-08-01) ⚠ OUTPUT + CSV CHANGE

Cage's headline number was labelled more broadly than it was computed, in the one
direction that flatters the tools cage exists to evaluate. Built from:
[docs/archive/v0.36-net-savings.handoff.md](docs/archive/v0.36-net-savings.handoff.md)
+ [docs/archive/v0.36-net-savings.prompt.md](docs/archive/v0.36-net-savings.prompt.md).
Evidence: [the gross-vs-net finding](docs/regression/2026-08-01-finding-saved-is-gross.md).

- **`saved` is GROSS, and now says so everywhere.** `saved = raw_alternative − actual`
  is a per-query counterfactual — the *avoided read cost*. It never subtracted the cost
  of **using** the tool (the invoking turn, the round-trip, a hook's injected context),
  so cage could truthfully print "27,658 tokens saved" for a session that cost more than
  its unassisted twin. **No arithmetic changed**; the label did. Columns: `report`
  `gross tok` / `gross` / `net vs spend`, `attrib` `gross tok` / `gross $`, `roi`
  `gross saved` / `net of own cost`, the bare-`cage` headline `gross saved`, and
  graphify's repo ceiling + history band. One phrasing for all of them
  (`netsaved.GROSS_NOTE`) — they cannot drift apart.
- **CSV column renames** (one-way reporting, no importer reads these): `saved_usd` →
  `gross_saved_usd` · report `net_usd` → `net_vs_spend_usd` · roi `net_usd` →
  `net_of_own_cost_usd` · attrib `saved_tokens` → `gross_saved_tokens`.
- **`cage insights verdict` no longer over-claims.** graphify is AST-only and honestly
  declares `tool_cost_usd = 0`, so `net = gross − 0` printed a bare **SAVING**. A
  non-negative net with no complete cost-of-use figure now reads **`SAVING (GROSS)`** /
  **`BREAK-EVEN (GROSS)`** with a ⚠ naming the exclusion and pointing at
  `cage insights compare`. **COSTING is still asserted plainly** — the omitted term is
  ≥ 0, so it can only make a negative net more negative. `verdict` remains a pure
  composer: this is a refusal rule, not a new statistic.
- **New: task-level net saved** (`cage/netsaved.py`), rendered *beside* gross in
  `verdict`, never instead of it. `net = gross − attributable cost of use`, where
  attributable = the **distinct** calls joined to the receipt's task whose `ts` falls
  within **±120s** of any of that tool's receipts on it (union per task, so an adjacent
  call is charged once). Symmetric because the invoking turn precedes the receipt and the
  consuming turn follows it. Per-query netting is **impossible** — shim receipts carry a
  `task` but no `call` — and is not faked.
- **It refuses rather than approximates.** A task with no in-window call is *uncovered*:
  its net reads unavailable, never `= gross`. `verdict` subtracts the cost of use only
  when it covers every receipt in the window. Net is `modeled` at its own lower
  confidence (`NET_SAVED_CONFIDENCE = 0.4`) — never `measured`; the subtrahend alone is.
- **Explained live:** `cage query gross-vs-net`. Spec:
  [FORMULAS §2.1 / §2.1a / §2.6](docs/formulas.md). Constants:
  `NET_ATTRIB_WINDOW_S`, `NET_SAVED_CONFIDENCE`.
- **Still open (NET-1):** whether graphify actually made those sessions more expensive.
  `cage insights compare` already answers it and only lacks data (`MIN_COMPARE_N = 5`;
  leg D produced 1) — a lab run, deliberately not a second comparison path in code.

### Cleanup becomes advisory — 90d default, warn-only, never per-tool (2026-08-01) ⚠ BEHAVIOUR CHANGE

Cage no longer deletes state automatically. Built from:
[docs/archive/v0.36-cleanup-safety.handoff.md](docs/archive/v0.36-cleanup-safety.handoff.md)
+ [docs/archive/v0.36-cleanup-safety.prompt.md](docs/archive/v0.36-cleanup-safety.prompt.md).

- **The auto sweep (piggybacked on `cage import`) only ever warns.** It computes what
  would go and prints one stderr reminder — count, reclaimable size, and the runnable
  fix — silent when nothing is eligible, throttled to one check per 24h. It never
  deletes. Deletion now only ever happens via an explicit `cage data cleanup --apply`.
- **Retention default: 30 → 90 days** (`constants.CLEANUP_DEFAULT_DAYS`, `cage.toml
  [cleanup] days`) — 30 proved tighter than a real usage gap.
- **New switch `[cleanup] warn`** (env `CAGE_CLEANUP_WARN`), default on — silences the
  reminder text without disabling the gate.
- **`[cleanup] enabled` semantics decided:** `false` means no automatic anything, not
  even the reminder — but a manually-typed `cage data cleanup` / `--apply` always runs
  regardless. An explicit command is never silently ignored because a switch is off.
- **Never a per-tool cleanup class.** Tool savings (`ledger/savings/<tool>/`) are
  unreachable today only because they sit under `ledger/`, which is on the never-list —
  now stated explicitly in code and tested surviving `prune` at `days=0`.
- **Accepted trade-off:** `state/` can grow unbounded for anyone who ignores the
  reminder — unrecoverable deletion is the worse failure. The reminder keeps firing
  every throttle interval while items remain, rather than warning once and going quiet.
- stdout is untouched (the reminder is stderr-only); derived views stay byte-identical.
  `cage query cleanup` explains the new shape.

## v0.35.0 (2026-07-24) — capture-report follow-ups: Kiro visibility, cache honesty, gap_ms observability

Closes the three low-priority findings the 2026-07-22 capture report parked (F3,
F5, F7) — none a capture-loss bug, each small and additive.

- **F3 — `cage doctor` distinguishes "capturing but token-thin" from healthy**
  (`doctorcmd._capture_quality`). Any agent with calls captured but
  `tokens_out == 0` across all of them now warns and points at the higher-fidelity
  proxy path (`cage data meter -- <cmd>` / `cage data proxy`). Deliberately
  **separate** from the existing "installed but capturing nothing" gate (files==0)
  — a genuinely-empty log stays silent as designed; this is the narrower, distinct
  signal for a log that IS matching rows but they're nearly worthless. Verified
  against this machine's real Kiro log (16 calls, 198 input, 0 output — an exact
  match to the report's evidence). Also resolves the report's open path question:
  the macOS Kiro CLI (`/usr/local/bin/kiro`) is a launcher for the same `Kiro.app`
  (a VS Code fork) — there is no separate CLI-Kiro data store, so the existing
  `~/Library/Application Support/Kiro/...` path is correct and unambiguous.
  Import-time visibility added too: one `debuglog.event(event="kiro-src", ...)`
  per import run, read **unconditionally** (independent of the incremental
  cursor) so "found but thin" never hides behind a no-op cursor-skipped run.
- **F5 — `report --usd` shows the cache-vs-fresh split.** One new footer line:
  `· cache: N% of input tokens were cache reads, M% of cost ($x of $y)`. The cost
  split uses the model's real `cache_read` price row (resolved via
  `policy.price`, `report._cache_read_usd`) — never a hardcoded 0.1× — so it
  stays correct if pricing changes. No table/column/CSV structure change; a
  `$7,046` headline that's 98% prefix-cache re-reads no longer reads as alarming
  without the split that explains it.
- **F7 — `gap_ms` coverage was measured, not fixed** (there was nothing to fix).
  The 2026-07-22 report's "~1% of rows" reads as under-coverage but compares
  against the wrong denominator: only the first call after a genuine human turn
  is ever eligible, and most call rows are tool-call iterations inside one
  agentic turn that were never supposed to carry a gap. Reimplemented the gap
  logic as a probe and ran it against all 141 real Claude transcripts on the
  reporting machine — reproduces the evidence exactly (371/36,322) and traces
  every human turn's fate: legitimate first-turn skips, genuine clock-disorder
  skips, or a fresher human turn correctly superseding an unconsumed gap. Nothing
  is unexplained. `transcript.parse_calls` gains optional `root`/`pol` params
  (both `None` by default — every existing caller stays byte-identical); when
  set, one summary `debuglog.event(event="gap_ms", ...)` per parsed file records
  `human_turns`/`stamped`/every named skip reason, reconciling exactly
  (`human_turns == stamped + Σ skip_*`, proven on a real transcript). No gap is
  ever fabricated to raise the number — the report's own line in the wall
  against exactly that stays intact.
- `docs/regression/2026-07-22-capture-report.md`: F3/F5/F7 marked ✅ resolved
  in place, with F7's corrected framing (recommended coverage denominator:
  `stamped / (human_turns − skip_first_turn − skip_negative_gap)` ≈ 88% on the
  measured machine, not "~1%").
- Built from
  [docs/archive/v0.35-phase3-deferred-findings.handoff.md](docs/archive/v0.35-phase3-deferred-findings.handoff.md).

## v0.34.0 (2026-07-24) — `cage doctor --wiring`: the installed-artifact inventory

A browsable itemization of every cage-installed artifact — project **and**
global/user scope — so a user can see what was installed, what wasn't, and what's
out of date, with nothing tracked by git. Renders `wiringscan.py`'s existing
enumeration + liveness (v0.32.0's F1 fix); forks none of it.

- **`cage doctor --wiring`** (`cage/wiringscan.py`, `cage/doctorcmd.py`): lists every
  artifact grouped by scope (project vs global/user) and agent (always driven off
  `agents.SURFACES`, never a hand-written list — the codex-removal-safe design the
  handoff asked for). Each row carries a **status**: `current` (a live verb / asset
  hash matches the bundle), `stale` (·, an installed skill/prompt/steering copy
  differs from the bundled original), `dead` (✗, a wiring command names a removed
  verb, with the same fix-hint `wiringscan.remediation` already computes), or
  `foreign` (○, a non-cage artifact at a cage location — shown, never judged; e.g.
  a `.git/hooks/post-commit` without the `# cage-managed-hook` marker).
- **Per-agent rollup** — four mutually-exclusive verdicts: `needs healing (N dead,
  M stale)` (takes priority whenever something present is broken) → `not wired`
  (nothing present — purely informational, never a warning) → `partially wired
  (missing: …)` (some but not all of the agent's *required* pieces present) →
  `fully wired`. "Required" excludes the two documented exceptions that are normal
  to be missing: Kiro's project `.kiro/settings/mcp.json` (gitignore-advised,
  `kirowire.py`) and the best-effort git hooks (`gitcommithook.py`). Skill/prompt/
  steering asset copies render as informational rows but never gate the verdict —
  `cage setup` (assets) and `cage setup --wire-only` (hooks/MCP) are separate
  invocations, and folding one into the other would misreport someone who
  deliberately ran only one.
- **No fabricated per-artifact version** — artifacts are stampless (the
  stale-wiring investigation confirmed this); a version footer instead prints the
  running `cage` version (+ `(zipapp)` tag), the bundled `[meta]` (`prices_version`/
  `policy_version`), and the project `policy.toml [meta]` if one exists — the
  honest "what's installed" answer without inventing data. Phase B
  (version-stamping artifacts) stays a separate, later, not-yet-decided change.
- **`--json` parity** — one data structure (`doctorcmd.wiring_report`), two
  renderers (`render_wiring_text` / `json.dumps`), the house pattern. Plain `cage
  doctor` is byte-unchanged (an additive flag; golden-covered in
  `tests/test_output_spec.py`). Read-only and side-effect-free by construction —
  nothing is ever executed or healed (`cage setup` still owns healing); a fresh
  scan over `wiringscan.run()`'s scan, not a fork of it.
- New `cage query wiring-inventory` concept entry.
- Built from [docs/archive/v0.34-wiring-inventory.handoff.md](docs/archive/v0.34-wiring-inventory.handoff.md).

## v0.33.0 (2026-07-24) — Codex removed: cage is Claude Code · Copilot · Kiro

A product/scope decision, **not** a capture-quality one — in the real ledger Codex was one
of the *healthier* captured agents (373 rows, $17.94 captured, second only to Claude Code),
unlike Kiro (near-empty) and Copilot (40% UNPRICED). This retires the "four agents, always"
invariant; `agents.SURFACES` is now `("claude", "copilot", "kiro")`. Derived views for
existing `agent="codex"` ledger rows are untouched — old data reads exactly as before, cage
simply stops producing new codex rows.

- **Core removal:** `agents.py` (`SURFACES` + `_WIRE` map), `codexwire.py` deleted outright,
  every codex leaf in `importcmd.py`/`transcript.py`/`paths.py`. The `format="codex"`
  custom-tool transcript parser is deleted too, not kept selectable — a half-removed agent
  still reachable via `[sources.<tool>] format = "codex"` was exactly the ambiguity the
  four-agents rule warned against. `paths.codex_home()` and `wiringscan`'s codex scanning
  stay deliberately: they back detection of a pre-existing `.codex/hooks.json` left on an
  upgraded machine — an orphan the current liveness scanner can't yet flag correctly (a known
  gap, not fixed here; see below).
- **`cage data limits` removed with it.** Codex's `rate_limits` block was the sole writer of
  `state/limits.json` anywhere in the tree; no other supported agent's session log carries a
  quota signal. A live command whose only data source is gone is dead surface waiting to
  rot, so `limits.py`, `credits.py`, `Footprint.limits` and the `data limits` subcommand go
  with it. A future provider that writes a quota block reintroduces the mechanism generically
  then, rather than keeping it dormant now.
- **`verbmap.REMOVED["import-codex"]` dropped** — its heal target, `import --agent codex`, is
  itself dead now, which the property test asserting every `REMOVED` entry heals to a
  parser-valid command correctly caught. (`import-claude`'s entry stays: its target verb,
  `import`, remains live even though `--agent codex` alone wouldn't — a different shape of
  the same class of problem.)
- **The 7 `-codex`-named openai price rows in the bundled `policy.toml` stay** — there is no
  codex route prefix; Copilot keeps the entire openai price table alive via its own
  gpt-family model mapping, so nothing is orphaned. Dropping the `-codex` rows is optional
  cosmetic cleanup, not part of this change.
- **Known follow-up, explicitly deferred:** a pre-existing `.codex/hooks.json` on an upgraded
  machine still runs `cage import --agent codex`, which the parser now rejects (`--agent`
  `choices` no longer include `codex`) — the hook fails, the shim swallows it to `exit 0`,
  and capture silently does nothing. The current wiring-liveness scanner can't see this: it
  checks verb tokens, and `import` itself is still a live verb. Fixing it needs a new
  *orphaned-surface* check class (an artifact whose command targets an agent no longer in
  `SURFACES`) — its own design pass, not bundled into this release.
- Regenerated: `docs/formulas.md`, `docs/cli-output-spec.md` (the capture-health warning
  golden moved its example from codex to kiro — same triple-gate logic, exercised over a
  still-supported agent), the bundled `policy.toml`'s `[sources]` comment block, and the
  `cage` skill asset (byte-identical — claude alone still renders it).
- Tests: 23 codex-only tests deleted (the parser, the standalone import path, the fixture
  corpus's `codex/{cli,vscode}` dir); every other codex-dependent test re-pointed at a real
  surface. `tools/dummyrepo`'s `AGENTS` tuple drops codex; S11/S15's incidental
  `agent="codex"` pricing-scenario stamps move to `agent="copilot"`. `python -m
  tools.dummyrepo` all-green (S1-S18).

Built from: [docs/archive/v0.33-codex-removal.handoff.md](docs/archive/v0.33-codex-removal.handoff.md)
+ [docs/archive/v0.33-codex-removal.prompt.md](docs/archive/v0.33-codex-removal.prompt.md).

858 tests passing.

## v0.32.0 (2026-07-24) — stale-wiring liveness: detect + heal orphaned wiring

Closes the root cause behind F1. No derived number changes (`report`/`attrib`/`matrix` are
byte-identical, asserted); no ledger, schema, enum or method-tagging change.

**The failure.** v0.28.0 renamed 31 top-level verbs. Every wiring artifact written before it
still names the old verb, so the command exits 1 — and because hook/shim stdout goes nowhere
and both shims fail open to `exit 0`, **a dead verb is indistinguishable from cage not being
installed**. On a real machine `bin/graphify` probed the pre-rename verb and silently exec'd
the unmetered binary for 9 days while `cage doctor` reported ✅, because the interceptor check
tested existence + PATH, not liveness. Diagnosed in
[docs/regression/2026-07-24-f1-root-cause.md](docs/regression/2026-07-24-f1-root-cause.md).

- **New `cage/wiringscan.py` — detection against the live parser.** Every installed
  artifact's command tail is resolved to its verb and checked against `cli.build_parser()`,
  the same code the CLI runs and therefore ground truth for "will this exit 1".
  `verbmap.REMOVED` is **not** the detector — it only supplies the replacement tail. The
  distinction is load-bearing: `adopt` was deleted outright rather than renamed, so it is
  dead, still installed on real machines, and absent from `REMOVED`; a grep against that
  table would miss it entirely. Detection is read-only and side-effect-free — nothing is
  executed, no import runs (executing a probe could not distinguish "verb dead" from "cage
  absent" anyway, which is the whole bug).
- **User-level artifacts are scanned.** `~/.copilot/hooks`, `~/.codex/config.toml`,
  `.git/hooks` and the global skill/prompt/steering copies, alongside the committed files —
  both real-world failures were user-level, so a liveness check that skipped them would miss
  its own reason to exist. `doctor`'s `portability` check stays committed-only; it answers a
  different question (what ships to a teammate).
- **`cage doctor` gains a `wiring` check**, rendered above the receipts check: it names each
  dead command **and** its remediation, `✗` for a wired artifact (capture is silently off),
  `·` for a stale agent asset (the agent sees a wrong verb, errors, and adapts). Assets are
  prose rather than commands, so they are hash-compared against the bundled originals.
- **`interceptor` now tests liveness, not existence.** The exact false ✅ from F1: the shim
  existed and was on PATH the entire time it was dead.
- **`cage setup` heals a dead verb**, rewriting it to the current form via `verbmap.REMOVED`
  in the same pass as the existing absolute-path→shim migration, and refreshing a stale
  `bin/graphify` (on `--wire-only` too, not only `--project-only`). Idempotent; foreign
  (non-cage) artifacts are never touched; a dead verb with no known replacement is reported,
  never guessed at.
- **Bundled F1 Fix 3 — the deferred receipts check.** `receipts: 0` now reads
  "the graphify interceptor is dead (see wiring above); fix it before concluding the tools
  are unused" when that is the actual cause. Shipped *with* its prerequisite, because alone
  it would have misread a dead shim as "you never used the savings tools".
- **The `" import"` substring predicate is retired.** `claudewire._is_stale_import` and
  `paths.is_cage_import_command` healed `import-claude`/`import-codex` only because those
  strings happen to contain `" import"`. The wiring filters now take the union of an *exact*
  import-verb rule (collapse the superseded form) and a *parser* dead-verb rule (heal the
  orphan) — same commands healed, non-accidental reason, and explicitly pinned by
  `test_import_claude_still_heals` / `test_import_codex_still_heals`.
- **Fixed: copilot duplicate hook entries.** A dead-verb entry matched neither old test, so
  `_wire_hooks` kept it *and* appended a correct one — leaving the dead command firing on
  every event.
- **Fixed: `just demo` and `install.sh` had been broken since v0.28.0** — the same rename,
  the same class of failure, in the repo's own dev tooling (`cage attrib`/`cage matrix`,
  and an `install.sh` line telling every new user to run `cage init`). A guard test now
  covers dev tooling too.
- **Safety net: a `verbmap.REMOVED` → parser round-trip property test.** Every remediation
  must be a command the CLI accepts, and no key may still be live. This would have caught
  the whole class at the rename commit.
- `cage query stale-wiring` explains the design; `docs/debugging-capture.md` documents the
  symptom, the doctor output and the fix. dummyrepo **S18** covers detect → heal →
  idempotence black-box through the shipped CLI.

Built from: [docs/archive/v0.32-stale-wiring.handoff.md](docs/archive/v0.32-stale-wiring.handoff.md)
+ [docs/archive/v0.32-stale-wiring.prompt.md](docs/archive/v0.32-stale-wiring.prompt.md).

881 tests passing.

## v0.31.4 (2026-07-24) — fix: capture-debug went silent under `--ledger`/`CAGE_BASE`

Observability only — no derived number changes (`report`/`attrib`/`matrix` are byte-identical
with debug on or off, asserted).

- **`debuglog` no longer suppresses every event under an explicit ledger override.**
  `_may_write_under_cage` gated the default log path on `root/.cage` existing — the anti-scatter
  guard that stops a stray footprint appearing beside an arbitrary cwd. But under
  `--ledger`/`CAGE_BASE`, `paths.resolve_root` returns the *cwd* while `paths.Footprint`
  re-bases ledger + state + debug log onto the override, so the guard inspected a directory
  with nothing to do with the active sink and silently dropped every event — including the F6
  receipt produce/skip trace shipped one release earlier. That is precisely the setup a capture
  diagnosis runs in (a scratch ledger, so the real one is never mutated), so the instrument was
  blind exactly where it was needed; the F1 diagnosis had to fall back to `CAGE_DEBUG_LOG` to
  see anything. An explicit `CAGE_BASE` now authorizes the write (new `_explicit_base()`,
  alongside the existing `_explicit_log()`); the log still lands *inside* the sink the user
  named, never beside the cwd. **The guard is not otherwise widened** — a bare cwd with neither
  `.cage/` nor an override is still refused, so debug never scatters.
- **New tests** in [tests/test_debuglog.py](tests/test_debuglog.py) — confirmed failing before
  the fix, passing after: an event written under a `CAGE_BASE` override (with no `.cage/`
  scattered beside the cwd), the bare-cwd refusal preserved, and a determinism assertion that a
  rendered `cage report` is byte-identical with debug-under-`CAGE_BASE` on vs off.
  `test_debug_coverage` unchanged and green.
- **Regression correction published:**
  [docs/regression/2026-07-24-f1-root-cause.md](docs/regression/2026-07-24-f1-root-cause.md) —
  corrects §F1 of the 2026-07-22 capture report (the 07-22 report itself is unchanged, per the
  never-rewrite convention). Two corrections matter: "no real savings has ever been captured" is
  false machine-wide (5 real receipts live in a *project* ledger while the 36k calls live in the
  *global* one — the report's numerator and denominator came from different sinks), and the real
  cause is a **dead** interceptor rather than a missing one — the v0.28.0 verb rename left the
  installed shim's `cage graphify --help` probe exiting 1, so it falls through to the raw
  unmetered binary, silently. That is a class failure across every wiring artifact written
  before the rename (the global `SessionStart` hook's `cage import-claude` fails identically).
  The stale-wiring class fix and the loud "receipts: 0 — attribution has no data" doctor check
  are **deferred to a design pass** and deliberately not in this release.

## v0.31.3 (2026-07-23) — F6: capture observability — the instrument for F1

Built from: [docs/f6-capture-observability.prompt.md](docs/f6-capture-observability.prompt.md).
Logging only — no derived number changes (`report`/`attrib`/`matrix` are byte-identical with
or without the breadcrumb writing).

- **New always-on capture breadcrumb: `state/capture.log`.** One line per agent per real
  import run — `ts · agent · files_seen · rows_new · rows_total · src` — counts-only, never
  gated on `CAGE_DEBUG` (unlike `debug.log`). A throttled/no-op capture-on-read (or capture
  switched off) never reaches it — only a real sweep appends. New `Footprint.capture_log`
  (`cage/paths.py`), written by the new `cage/capturelog.py`, wired into `importcmd.run` at
  the existing `_record_health` call site (no second ledger read — `rows_total` is derived
  from the already-shared `all_rows`/`captured` read plus this run's own `imported` delta).
  Fail-open: a write failure never breaks an import, traced under `CAGE_DEBUG` at
  `context="capture.log"`. Size-managed by a new `capture-log` cleanup class (`cleanup.py`) —
  prunable state, not permanent record, never in the `NEVER` allowlist. Included in
  `cage doctor --bundle` (`state/capture.log`) alongside `debug.log`.
- **Receipt produce/skip logging — the F1 instrument, `CAGE_DEBUG`-gated.** Every receipt
  push/skip site now logs `event=receipt` with `tool`, `produced` (bool), and a `skip_reason`
  when nothing was produced: `graphifymeter.py` (`non-measured-op` /
  `no-source-file-parsed` / `no-saving-to-claim` / `linked-receipt-skipped`),
  `metering.record_receipt` (`push-sink-unresolved` on a failed ledger append),
  `responsecache.lookup`/`hit_receipt` (`cache-miss`), and `compress.receipt`
  (`no-saving-to-claim`). Before this, a skipped receipt was completely silent — F1 (zero
  real savings receipts) is now diagnosable from the debug log instead of a guess.
- **New tests:** [tests/test_capture_log.py](tests/test_capture_log.py) (breadcrumb
  content, no-op silence, cleanup pruning, fail-open, doctor-bundle inclusion) plus new
  produce/skip coverage in [tests/test_debug_coverage.py](tests/test_debug_coverage.py) and
  a cross-check against the F2 fix in
  [tests/test_capture_health.py](tests/test_capture_health.py).
- **Docs:** [docs/debugging-capture.md](docs/debugging-capture.md) documents `capture.log`
  and the receipt skip-reason vocabulary; `cage query capture` mentions both.

## v0.31.2 (2026-07-23) — fix: capture-health false negative on an agent's first-ever import

- **Fix: `_health.captured` now reads true on a surface's very first import, same run.**
  `_record_health`'s `captured` set is snapshotted from `ledger.calls(root)` **before**
  `run_agent` appends this run's newly-imported rows — a snapshot-ordering off-by-one that
  left a brand-new agent's very first import reading `captured:false` until a *second* import
  self-healed it. `run_agent` now records the row count it imported this run
  (`health[agent]["imported"]`), and `_record_health` unions that against the lifetime
  `captured` set (`a in captured or info.get("imported", 0) > 0`). New regression test:
  `test_first_ever_import_marks_the_agent_captured_same_run`
  ([tests/test_capture_health.py](tests/test_capture_health.py)), confirmed failing before the
  fix and passing after; verified against a real ledger (one `cage import` flipped all four
  surfaces to `captured:true`).
- **Correction to the 2026-07-22 regression report's F2 finding.** That report's stated root
  cause — "`captured` tracks this-run delta, not lifetime" — didn't match the code, which has
  read the lifetime `ledger.calls(root)` set since v0.30.0. The real defect and the corrected
  blast radius (this never produced a false "installed but capturing nothing" warning) are
  documented in [docs/regression/2026-07-23-f2-correction.md](docs/regression/2026-07-23-f2-correction.md)
  — a new dated entry per this repo's never-rewrite-history convention; the 07-22 report is
  unchanged.
- **New Must-Know Rule:** every `docs/*.prompt.md` must declare the model tier that should
  execute it (`**Model:**` line + one-line reason), with a Haiku/Sonnet/Opus rubric.

## v0.31.1 (2026-07-21) — docs: the Phase 2 field gate, made runnable

Documentation and repo-hygiene only — **no code changed**; the runtime is byte-identical to
v0.31.0 (same 814 tests, same derived numbers). This release ships the paperwork the v0.31.0
capture-architecture Phase 1 left in the working tree, so the Phase 2 waiting period is
measurable instead of prose.

- **The Phase 2 field gate is now a runnable procedure, not a sentence.**
  [docs/phase2-field-gate.md](docs/phase2-field-gate.md) turns the handoff §10 gate into a
  concrete comparison: build a hooks-on ledger and a hooks-off (`CAGE_CAPTURE_ON_READ`-only)
  ledger over the same span of work, compare them **by row id** (`mergeutil.union_by_id`
  semantics), and pass **iff** capture-on-read's row set is a **superset** of the hooks-on set
  — no row that only the hooks caught. References the exact switches (`CAGE_CAPTURE`,
  `CAGE_CAPTURE_ON_READ`, `--no-import`) and the `importcmd.ensure_captured` path. It is an
  acceptance test, not a runner — no `cage/**` code, no Phase 2 work. Linked from the handoff
  §10 and `docs/README.md` Active work.
- **Phase 2 decisions record.** `docs/capture-architecture.handoff.md` gained §9.7 (the
  verified Phase 2 change-map) and §10 (five resolved decisions plus the field gate), so the
  Phase 2 branch can be written later against fixed decisions rather than re-derived.
- **Repo hygiene.** `.gitignore` now ignores the regenerable `graphify-out/` tree in full (the
  prior partial rule left ~7MB unignored) and the machine-local `.claude/settings.local.json`.

Built from: [docs/capture-architecture.handoff.md](docs/capture-architecture.handoff.md) §9.7+§10
and [docs/phase2-field-gate.md](docs/phase2-field-gate.md). Phase 2 itself is unshipped — the
capture-architecture handoff/prompt/plan pairs stay **active in `docs/`**, not archived.

## v0.31.0 (2026-07-19) — capture-on-read: capture without hooks, made visible

Built from: [docs/capture-architecture.handoff.md](docs/capture-architecture.handoff.md) ·
[docs/capture-architecture.prompt.md](docs/capture-architecture.prompt.md) — **Phase 1** of
the phased [docs/capture-architecture.plan.md](docs/capture-architecture.plan.md) (Phase 2,
which deletes the token-capture hooks, is a separate later release; the docs stay active in
`docs/` until it ships). Additive — **no hook file or wiring module was touched**.

Capture no longer depends on a hook firing. **Every read that matters — `cage report`,
`cage insights *`, and the MCP read tools — lazily runs the incremental import sweep before
it answers**, so a number is never staler than the instant it's shown. No daemon, no
scheduler (the "cage installs no scheduler" invariant holds), no project required. The
sweep is throttled on the existing `_last_import` cursor (~60s, policy `[capture]
read_throttle_secs`), so back-to-back reads don't re-sweep; a warm cache is a `stat` per
source file. Fail-open: a capture error is traced under `CAGE_DEBUG` and never blocks a read.

- **One canonical ledger for push and pull.** `paths.canonical_ledger()` is the single
  resolver both the push path (graphify/fux/proxy `record_receipt`/`record_call`) and every
  read call — no direct `resolve_root` left in a push path, and every resolution is traced
  under `CAGE_DEBUG` ("which ledger + why"). A pushed receipt now carries a **non-PII project
  routing key** — a hash of the resolved ledger-root path (never the basename), OS-stable,
  additive/optional (absent = the legacy row, never part of any id). A project read
  **reclaims** a stray graphify/fux saving (one pushed to the global `~/.cage` because the
  tool ran outside the tree) by **exact key match only** — never a blind global→project
  union that would over-attribute two repos sharing a basename.
- **Capture is now visible.** A `graphify`/`fux` saving prints one `✔ cage: graphify saving
  captured — ~N tokens` line to **stderr** (never stdout — the tool's parseable output stays
  clean). A read that captures new rows prints `· captured N new calls (claude, codex) + M
  graphify savings since last read` (also stderr; **zero new ⇒ silent**). The MCP read tools
  return the same summary as a **structured field**, never stray stdout. `cage doctor` gains
  a **per-source, per-mode (pull/push) capture timeline** — and deliberately does **not**
  sweep first, so it never masks the breakage it diagnoses. `--why-ledger` prints the
  resolution decision on demand; `--quiet` / `CAGE_QUIET=1` silences the confirmations.
- **Suppressible and deterministic.** `--no-import` (this read), `CAGE_CAPTURE_ON_READ=0`
  (standing), or `CAGE_CAPTURE=0` (all capture) turn it off. Derived numbers stay a pure
  function of the ledger — capture-on-read changes *when* rows arrive, never how a number is
  computed — and the golden/determinism suites run with it **off** against a fixed ledger, so
  a warm read is byte-identical to before. CSV never gates: no confirmation text ever enters
  a CSV stream.
- **Prerequisite refactors (reviewable first commit).** `hooks.append_new` — the documented
  "correctness backstop" — moved to `ledger.py` (the universal import path must not depend on
  the Claude-specific hook module; a re-export shim keeps `hooks.append_new` working). The
  `cage doctor` "never imported" message was rewritten: under capture-on-read an empty
  capture-health record means capture is **off or errored**, not "you haven't run `cage
  import`".

## v0.30.0 (2026-07-16) — capture health: make silent zero-capture loud

Built from: [docs/archive/v0.30-capture-health.handoff.md](docs/archive/v0.30-capture-health.handoff.md) ·
[docs/archive/v0.30-capture-health.prompt.md](docs/archive/v0.30-capture-health.prompt.md).

When an agent is **installed but its log source matched nothing**, cage now says so —
instead of quietly capturing zero and printing confident totals from the agents that
still work. A wrong path (a vendor moved its store, a nonstandard install, the
`UNVERIFIED-LAYOUT` Windows Kiro path) produces zero rows, which used to be
indistinguishable from "I don't use that agent." Now `cage report` and `cage doctor`
carry a footer warning:

```
⚠ codex: ~/.codex exists but ~/.codex/sessions matched 0 files — capture is off for this agent.
  cage doctor --paths      (if you don't use codex: [sources.codex] replace=true, paths=[] )
```

- **Triple-gated so it can never become a false-positive nag.** It fires for an agent
  only when **all three** hold: its home marker exists, its log matched **0 files** at
  the last import, and it has **never contributed a row** to the ledger. The third
  clause makes it **self-silencing** — one captured row and it can never warn again, so
  it only ever names an agent that is genuinely capturing nothing.
- **Self-healing.** Fix the path (or the agent starts writing logs) → the next import
  rewrites the verdict and the warning clears, no other action.
- **Opt-out reuses the existing knob.** An agent you don't use, declared
  `[sources.<agent>] replace = true, paths = []` (already "disabled by policy"), stays
  silent — no new config key.
- **No new I/O on any read path.** The gate inputs are recorded at import time into
  `cursors.json["_health"]` (from facts the scan + the one shared ledger read already
  compute — zero extra reads) and rendered from that cache. `cage report`'s
  **render stays a pure function of its arguments**; its tables are byte-identical and
  the warning **never enters CSV**. No new state file (rides beside `_last_import` in
  the cursor map, cleanup-safe).
- `cage doctor` surfaces the same verdict (a fresh install with no import yet just says
  "never imported — run `cage import`"; no live probe).

## v0.29.0 (2026-07-16) — visible source paths + per-source globs

Built from: [docs/archive/v0.29-sources-defaults.handoff.md](docs/archive/v0.29-sources-defaults.handoff.md) ·
[docs/archive/v0.29-sources-defaults.prompt.md](docs/archive/v0.29-sources-defaults.prompt.md) —
Phase 4 follow-on of [docs/output-and-simplification.plan.md](docs/output-and-simplification.plan.md).

Two independent pieces, one release. Both **capture-side only** — no derived view
changes by one byte, determinism untouched, and an empty/absent `[sources]` stays
byte-identical to the built-in registry.

- **Per-source `glob` (the real capability gap).** A `[sources.<agent>]` entry may
  now declare its own filename pattern: `glob = "usage-*.ndjson"`. Absent ⇒ the
  format's canonical glob (unchanged); an empty `glob = ""` is an **error**, never a
  silent fallback. A glob character (`*?[`) in a `path` is still rejected — but the
  message now **names the fix** ("put the pattern in `glob = `"). This makes a tool
  whose layout isn't the canonical shape capturable at all.
- **Array-of-tables form.** `[[sources.<agent>]]` with one `{path, glob?}` block per
  location — a per-path glob, vs. the table form's one `glob` for every `path`.
  `resolve_log_sources` branches on the parsed TOML type (dict ⇒ legacy table, list ⇒
  array); **different agents may use different shapes in one file**. A custom tool in
  array form carries `format` on each entry.
- **`cage doctor --paths`** shows the declared glob per source (it already rendered
  the pattern column — now it reflects your `glob`).
- **A generated, commented `[sources]` block in the bundled `policy.toml`.** The
  built-in defaults (paths, globs, redirect env vars, per-OS locations, the Windows
  Kiro `UNVERIFIED-LAYOUT` label) are now **visible in every project's
  `.cage/policy.toml`** — as a comment block between `# cage:sources-start` /
  `# cage:sources-end`, regenerated by `tools/docgen --target policy` from
  `paths.builtin_source_docs()` and drift-gated in CI. **Every line is a comment**, so
  `tomllib` sees no `sources` key, capture resolves the built-ins byte-for-byte, and
  `policy sync` still has nothing to touch. The defaults live in code and upgrade with
  the package; uncommenting a block into a real table is an **explicit pin**. The block
  is emitted `~`-relative and env-independent, so it is identical bytes on every
  machine.

Design note: an *active* `[sources]` default in the bundle was deliberately **not**
built — `initcmd` copies the bundle verbatim, `policy.load` lets a project table
shadow it, and `policysync` skips `sources`, so a shipped active default could never
be fixed for an existing project (silent zero capture). The commented block delivers
the visibility with none of that freeze risk. See the handoff for the full debate.

`tools/docgen`'s `policy` target now owns two regions of the bundled file (the
`# formula:` comment lines and the `[sources]` sentinel block); `docgen --check`
gates drift on both.

## v0.28.0 (2026-07-15) — configurable import paths: `[sources]` in policy.toml

Built from: [docs/archive/v0.28-policy-sources.handoff.md](docs/archive/v0.28-policy-sources.handoff.md) ·
[docs/archive/v0.28-policy-sources.prompt.md](docs/archive/v0.28-policy-sources.prompt.md) —
Phase 4 of [docs/output-and-simplification.plan.md](docs/output-and-simplification.plan.md).

**This release also ships the previously-unreleased v0.26.0 (output honesty) and
v0.27.0 (CLI tiering) work** — the three phases were developed as one stack and cut
as a single release; their full notes are the two entries below.

A `[sources]` policy table that adds — or replaces — the log locations `cage
import` probes: one or more paths per agent, plus custom tools that reuse a
declared parser format. For a nonstandard install, a network home, a side-by-side
log copy, or an in-house emitter that writes an already-supported format. **Additive
by construction — an empty or absent `[sources]` is byte-identical to the built-in
registry**, so capture is unchanged for everyone who doesn't use it. Capture-side
only: no derived view changes, determinism untouched.

- **Schema.** `[sources.<agent>] paths = ["~/…", "$VAR/…"]` extends one of the four
  agents (claude · codex · copilot · kiro); `replace = true` drops that agent's
  built-ins first (empty `paths` ⇒ **disabled by policy** — a clean way to silence a
  never-installed agent's probe). A custom tool is any table whose name is *not* one
  of the four agents: it must declare `format = "claude|codex|copilot|kiro"` (the
  parser to reuse) and its rows import with `agent = <name>`, so `cage report` /
  `cage insights attrib` split it out. `~`/`$VAR` expand; a glob-shaped entry
  (`*?[`) is rejected. New log *formats* stay out of scope by construction.
- **One resolution point.** `paths.resolve_log_sources(pol)` returns the
  provenance-tagged candidate list the import sweep **and** `cage doctor --paths`
  both consume — no second resolver. Precedence: **env home override > policy
  `[sources]` > built-in registry**; a policy path equal to a built-in path is
  deduped to the built-in tag.
- **Same capture contract.** Policy paths sweep with the same incremental cursors
  (keyed on each resolved file path), the same id-dedupe, and the same per-file
  fail-open (a missing/unreadable path is a debug-logged skip, never an error) as the
  built-ins. `cage data export`'s import-first sweep includes them; `CAGE_CAPTURE=0`
  disables them with everything else.
- **`cage doctor --paths`.** Every candidate now names its **provenance** —
  `built-in | env | policy` — custom tools appear as their own sections, a
  `disabled by policy` label shows a replace+empty agent, cross-agent path overlaps
  are flagged, and a **committed project policy** carrying a machine-absolute source
  path warns ("teammates' clones will probe a path that doesn't exist — move it to
  ~/.cage/policy.toml or use ~/…"). A `~`/`$VAR` path and the global `~/.cage`
  policy are exempt. Malformed entries render as loud `⚠ ignored:` lines.
- **`cage query sources`.** A new concept entry: the schema, precedence, portability
  rule, and your **live resolved sources**.
- **`policy sync` ownership.** `[sources]` is entirely user-owned — the bundled
  `policy.toml` ships none — so `cage policy sync` never adds, updates, or
  orphan-warns it (asserted by test).
- **Docs.** New [docs/sources.md](docs/sources.md) (indexed) + a README capture
  one-liner. Two must-never-skip tests: empty-`[sources]` byte-identity and the full
  env>policy>built-in precedence matrix; plus expansion, custom-tool end-to-end
  (fixture log at a policy path → rows split by the tool name), cursor
  incrementality, portability warn/no-warn, and sync ownership. Dummyrepo **S15**.

## v0.27.0 (shipped in v0.28.0, 2026-07-15) — CLI tiering: five daily verbs, grouped rooms, a clean pre-1.0 verb break

Built from: [docs/archive/v0.27-cli-tiering.handoff.md](docs/archive/v0.27-cli-tiering.handoff.md) ·
[docs/archive/v0.27-cli-tiering.prompt.md](docs/archive/v0.27-cli-tiering.prompt.md) —
Phase 3 of [docs/output-and-simplification.plan.md](docs/output-and-simplification.plan.md).

**⚠ BREAKING — this release removes ~30 top-level verbs and regroups them.** The
daily loop is five verbs; everything else is one group deep. Nothing lost from
*capability* — only from the front door. For one release, an old verb name errors
with a direction (`error: 'attrib' is now 'cage insights attrib'`, exit 1) instead
of running; it never silently aliases. Recorded ledgers, CSV/JSON schemas, MCP tool
names, and `hook-*` plumbing are untouched — only the CLI door moved.

- **Tier-1 front door.** `cage --help` now renders five daily verbs
  (`report` · `import` · `setup` · `doctor` · `query`) + seven group names, one
  screen, no usage/options noise. Bare `cage` still prints the overview.
- **Groups (run any group name for its commands).**
  `cage insights <attrib|matrix|roi|verdict|budget|compare|estimate|calibration|trend|why|forecast|regression|recommend>` ·
  `cage human <show|record|outcome|quality>` ·
  `cage authorship <origin|verify|notes-sync|ledger-sync>` ·
  `cage data <export|cleanup|limits|watch|serve|proxy|meter|graphify>`.
  `prices`/`study`/`policy` are unchanged. Group subcommands keep their exact
  flags and output — behavior is frozen (proven by an old-vs-new golden byte-diff
  per verb; the only diffs are the usage/program line and renamed hint strings).
- **`init` merged into `setup`.** `cage init` is gone; `cage setup` scaffolds
  `.cage/` unconditionally as step one, then wires. `cage setup --global` unchanged.
- **Hidden but callable.** `mcp` (spawned by wired configs), `debug` (diagnostic),
  `demo` (README-referenced), `graphify` (interceptor seam, under `data`), and the
  `hook-*` entrypoints stay callable — just off `cage --help`.
- **Seams migrated.** The graphify interceptor shim now routes through
  `cage data graphify`; re-running `cage setup` migrates a committed Claude
  SessionStart hook from the removed `import-claude` to `import --agent claude`
  (grep-tested like portable wiring). No argparse prefix-matching — an old
  abbreviation is an invalid choice, not a silent hit.
- **World regenerated.** All four agents' skill/prompt/steering assets, the
  `cage query` concept text, `docs/formulas.md`, the bundled `policy.toml` comments,
  and every emitted hint string now name the grouped verbs (a `render.cmd()` helper
  centralizes the spelling); a grep gate proves zero stale `cage <old-verb>` in
  source, rendered assets, or committed wiring.

**Old → new verb map** (the removed-verb error handler and this table are both
generated from `cage/verbmap.py`):

| removed verb | now |
| --- | --- |
| `cage init` | `cage setup` |
| `cage import-codex` | `cage import --agent codex` |
| `cage import-claude` | `cage import --agent claude` |
| `cage attrib` | `cage insights attrib` |
| `cage matrix` | `cage insights matrix` |
| `cage roi` | `cage insights roi` |
| `cage verdict` | `cage insights verdict` |
| `cage budget` | `cage insights budget` |
| `cage compare` | `cage insights compare` |
| `cage estimate` | `cage insights estimate` |
| `cage calibration` | `cage insights calibration` |
| `cage trend` | `cage insights trend` |
| `cage why` | `cage insights why` |
| `cage forecast` | `cage insights forecast` |
| `cage regression` | `cage insights regression` |
| `cage recommend` | `cage insights recommend` |
| `cage human-record` | `cage human record` |
| `cage outcome` | `cage human outcome` |
| `cage quality` | `cage human quality` |
| `cage origin` | `cage authorship origin` |
| `cage verify` | `cage authorship verify` |
| `cage notes-sync` | `cage authorship notes-sync` |
| `cage ledger-sync` | `cage authorship ledger-sync` |
| `cage export` | `cage data export` |
| `cage cleanup` | `cage data cleanup` |
| `cage limits` | `cage data limits` |
| `cage watch` | `cage data watch` |
| `cage serve` | `cage data serve` |
| `cage proxy` | `cage data proxy` |
| `cage meter` | `cage data meter` |
| `cage graphify` | `cage data graphify` |

## v0.26.0 (shipped in v0.28.0, 2026-07-15) — output honesty: tokens by default, `—` for unpriced, signal-gated columns, generated docs

Built from: [docs/archive/v0.26-output-honesty.handoff.md](docs/archive/v0.26-output-honesty.handoff.md) ·
[docs/archive/v0.26-output-honesty.prompt.md](docs/archive/v0.26-output-honesty.prompt.md) —
plan Phases 1+2+5.6 of
[docs/output-and-simplification.plan.md](docs/output-and-simplification.plan.md).

**⚠ This release deliberately changes the rendered text of most read views in
one go** — driven by field output where `saved $0.0000 / net -$16.11` rendered
in a receipt-less project and `$0.0000` meant "couldn't price". Every new
rendering is pinned by a golden test and documented in
[docs/cli-output-spec.md](docs/cli-output-spec.md) (now generated from those
same goldens). **CSV schemas and values are byte-frozen** — if you scripted
against `--csv` or `--json`, nothing moved; if you scraped the text tables,
read on.

- **Tokens by default; dollars opt-in (plan Phase 2.5).** `cage report` (every
  `--by` view), `cage matrix`, and the bare `cage` headline render tokens-only
  until asked for currency: per-invocation `--usd` > env `CAGE_USD` > policy
  `[display] usd = true` (new bundled section; `policy_version` bumped —
  `cage policy sync` carries it into projects). Pricing footnotes
  (family/alias/ladder-rung) and the full ⚠ UNPRICED block render only in the
  `--usd` view; the token view carries one muted pointer (`· N calls unpriced —
  matters when you view $`). Money-native views (`budget`, `roi`, `verdict`,
  `compare`, `estimate`, `human`, `trend`) keep dollars unconditionally.
  Pricing always computes underneath — budget guards and UNPRICED detection
  are display-independent.
- **`—` is the only rendering of "couldn't price".** A group whose every call
  refused to price shows `—`, never `$0.0000`; the TOTAL carries
  `(+ unpriced)`; a net over a dashed cost is itself `—`; roi/attrib rows whose
  receipts all refused the ladder dash their $ cells. `$0.0000` now always
  means a real zero. CSV keeps explicit empty + `priced_via=none` — the glyph
  never enters data. The report's ⚠ block now prints one **runnable fix line
  per unpriced model** (the `cage prices unpriced` builder, one wording).
- **Signal-gated saved/net (plan Phase 2.1).** saved/net (and the token view's
  `saved tok`) columns render only when ≥1 savings receipt exists in the
  window; otherwise the table is spend-only plus one line pointing at
  `cage query receipts`. `--all-columns` restores the fixed shape. **Hard
  line, tested by name: a negative net with real receipts renders
  unconditionally** (`test_negative_net_with_receipts_always_renders`).
- **Matrix: the token grid always renders (spec I7/I8).** The old whole-view
  `$0→$0` table and the unpriced-model refusal are both gone: the default is a
  token grid; `--usd` adds the cost column when a model prices (task join, or
  a unanimous `[tools.<tool>] price_at` route — matrix is now a ladder
  consumer) and otherwise appends one line naming the reason plus a runnable
  fix. `--human` implies `--usd` (the anchor is a dollar row).
- **Tidiness (plan Phase 1).** 0-call receipt-only bucket rows never render
  (their savings stay in TOTAL); footnotes/⚠/advice dedupe to one each in a
  fixed bottom order (the new `cage/display.py` Footer — one implementation,
  no per-view copies); the kiro input-only caveat renders once, per-view
  wording (`tok out not recorded` / `cost understated`); `last import: N ago`
  is staleness-gated (`[capture] import_stale_hours`, default
  `constants.IMPORT_STALE_HOURS` = 24; `0` restores always-on); the generic
  kiro model bucket renders `agent (kiro)`; the empty ledger prints next-step
  lines (`cage import` / `cage doctor`), and an empty *filtered slice* names
  the active filters instead of pretending the ledger is empty (the `--scope`
  papercut).
- **Three generated doc surfaces with CI drift gates (plan Phase 5.6,
  `tools/docgen` — build-time, stdlib, never in the wheel).**
  `docs/cli-output-spec.md` code blocks ← the golden fixtures
  (`tests/fixtures/goldens/`, asserted by `tests/test_output_spec.py`; status
  flipped to LIVE, README-linked beside the CSV contracts) ·
  `docs/formulas.md` ← the `explain_data.py` calculation registry (every
  calculation entry must be catalogued — the check fails otherwise; three
  pricing entries and trend/budget added) · bundled policy.toml `# formula:`
  comments ← the same registry. `python -m tools.docgen --check` runs in CI
  beside skillgen's; `tests/test_docgen.py` gates it locally too.
- **Goldens.** 30 byte-pinned fixtures across report/overview/matrix/verdict/
  compare/estimate/prices/study/policy states; `study join`'s output is
  machine-dependent by design (wiring + doctor) so it is shape-asserted, not
  byte-pinned. `cage demo`'s matrix table re-pins once to the new rendering
  (same numbers, new shape).
- **Query surface.** New `display` concept entry (`cage query display`);
  `unpriced` teaches the `—` convention and the `--usd` placement; skill/
  prompt/steering assets regenerated (they teach `--usd` and the gating).

Breaking (text only): scripts parsing `cage report`/`cage matrix`/bare-`cage`
text output must add `--usd` (or set `[display] usd = true`) to see dollar
columns; the empty-ledger message changed; the report title separator is now
`·`. Use `--csv`/`--json` for stable machine surfaces — that's what they're
for.

## v0.25.0 (2026-07-14) — policy sync: upgrade a project policy.toml to the installed bundle

Built from: [docs/archive/v0.25-policy-sync.handoff.md](docs/archive/v0.25-policy-sync.handoff.md) ·
[docs/archive/v0.25-policy-sync.prompt.md](docs/archive/v0.25-policy-sync.prompt.md)

A project inited at v0.16 has a policy.toml missing everything the bundle
gained since (`[meta]`, `[cleanup]`, `capture.import_before_export`).
`policy.load` defaults them all, so nothing breaks — but the user never
*discovers* tunables, and a stale un-customized default can drift from the
bundle's improved one. `cage prices sync` solved exactly this for pricing
tables; **`cage policy sync` generalizes it to the whole file** (plan §3.10).

- **`cage policy sync`** — dry-run categorized diff (the default surface;
  `cage policy diff` is the same view by name). Four categories with counts:
  **add** (in the bundle, missing here → `--apply` writes bundled defaults as
  plain text with one provenance comment `# added by cage policy sync (vX.Y)`
  — never into the managed block, never `# cage:custom`-marked, so a synced
  default stays sync-updatable), **update** (equal to a recorded *old*
  default whose bundled value changed → refreshed, old→new shown), **keep**
  (customized — structurally owned, or differing where no default ever
  changed: the user's edit, never touched), **orphan** (the bundle dropped it
  → warned with version context, never deleted). A user's own sections are
  invisible to sync entirely.
- **The versioned-defaults record** (`policysync.DEFAULT_CHANGES` /
  `REMOVED_KEYS`) — empty today, and empty is load-bearing: no non-pricing
  default has ever changed (verified against the git history of
  `data/policy.toml`), so a differing un-marked value can only be the user's
  edit — classified *keep*, never clobber-able drift. Where a default *does*
  change someday and the file predates `policy_version`, the row falls to a
  per-key confirm bucket (`--yes section.key` / `--yes all`) — honest over
  clever, the prices-sync stance. Maintenance rule documented in the module:
  a release changing/removing a bundled non-pricing default appends the old
  value and bumps `[meta] policy_version`.
- **`[meta] policy_version`** — new bundled key (compared as a version
  *tuple*, not a date), stamped by `cage init` (verbatim copy) and restamped
  on every `--apply` — but only once the confirm bucket is decided: stamping
  earlier would re-era the file and silently reclassify pending rows as
  customized. `prices_version` is never touched by policy sync.
- **Two safety invariants, tested and scenario-verified:**
  behavior-neutrality (zero-customization project: `--apply` then every
  derived view — report/attrib/budget/human/trend/matrix — byte-identical:
  adds only pin defaults `policy.load` was already merging in) and idempotent
  apply (second `--apply` is a byte-identical no-op, "already in sync").
- **One merge brain per family:** `[prices]`/`[credits]`/`[alias]` and
  `[tools.<name>]` routes are never diffed here — the `cage prices sync`
  summary embeds in the output, and `--apply` never touches a pricing row.
  The scalar `[tools] order` pipeline key *is* policy and syncs here.
- **Hints split by drift kind:** doctor gains a `policy-version` check and the
  post-commit note carries the `cage policy sync` recommendation
  (`freshness.policy_line`, opt-in) — but the `cage report` footer never
  does: price drift can make the report's *dollars* stale; policy drift
  changes no derived number. Pure price drift keeps the `cage prices sync`
  hint verbatim. Nothing anywhere auto-applies either sync.
- **Writer extensions, not forks** (`pricestoml`): `add_table` (plain-text
  append outside the managed block, provenance comment, idempotent),
  `set_table(..., mark_custom=False)` (a refreshed default must not start
  reading as user-owned), list values in `_fmt_value` (`[tools] order`).
  Same lock + re-parse + temp-write/atomic-replace: exotic TOML refuses per
  file with a typed `CageError`, never a mangled write; git-tracked policies
  get a "review with git; no .bak files" note.
- `cage init` prints a one-time pointer (new tunables ship in future versions
  — `cage policy sync` shows them); `cage query policy-sync` explains the
  categories + neutrality invariant with live version stamps; dummyrepo
  **S16** drives the whole arc end-to-end (strip to v0.16 shape → exact
  categories → neutral apply → no-op second apply → hints flip clean).

New: `cage/policysync.py`, `policy` CLI group, doctor `policy-version`,
`freshness.policy_line`, `cage query policy-sync`, dummyrepo S16,
`[meta] policy_version = "0.25.0"`. 34 new tests (657 passing).

## v0.24.0 (2026-07-14) — pricing freshness: the per-commit staleness note + complete vendor tables

Built from: [docs/archive/v0.24-pricing-freshness.handoff.md](docs/archive/v0.24-pricing-freshness.handoff.md) ·
[docs/archive/v0.24-pricing-freshness.prompt.md](docs/archive/v0.24-pricing-freshness.prompt.md)

Pricing is derive-time, so a stale price table quietly mis-prices *all* history —
and nothing checked freshness at the moment work is committed, or watched the
bundle's own age (a project faithfully synced to a six-month-old bundle was
confidently stale). cage never fetches a rate (no network on any cage code
path), so the answer is **three local signals, one implementation, three
surfaces** (`cage/freshness.py`):

1. **sync drift** — project `[meta]` older than the installed bundle →
   the existing `cage prices sync` recommendation, verbatim.
2. **bundle age** — the bundle's own `[meta] prices_date` more than
   `stale_days` old → `bundled prices are N days old — check for a newer cage
   release`. Threshold: policy `[prices] stale_days`
   (`constants.PRICES_STALE_DAYS` fallback, 45; `0` disables — documented
   opt-out).
3. **UNPRICED presence** — calls / call-less token receipts billing $0 → the
   existing runnable fix hints, byte-for-byte (never re-phrased).

Surfaces: the **git post-commit hook** prints the actionable lines
(`cage:`-prefixed headline, print-only, fail-open, exit 0, silent when clean —
never gates a commit; its own swallow-site, `hook.post_commit.freshness`,
debug-logged and audit-tested); **`cage doctor`** gains a `prices-age` check
beside `prices-meta`/`pricing` (all three signals now render there); the
**`cage report` footer** appends actionable lines only — and, determinism law:
the footer's age math anchors on the **newest ledger `ts`** (data-relative,
clock-free; byte-identical across runs on the same ledger; empty ledger ⇒
report silent, doctor carries the age), while hook/doctor use wall-clock
today. Never in `--csv` (CSV consumers get the UNPRICED columns already).
`cage query prices-freshness` explains with live values.

**Complete Anthropic + OpenAI tables** (build-time research, every row cited
`# source: URL (retrieved 2026-07-14)`): 24 new rows — Anthropic recent-history
(`claude-sonnet-4`, `claude-3-7-sonnet`, `claude-3-5-sonnet`,
`claude-3-5-haiku` legacy-order twin, `claude-3-opus`, `claude-3-sonnet`,
`claude-3-haiku`; retired-but-billable in 2025–26 ledgers, so historical rows
keep repricing at what they actually billed) and OpenAI GA + recent-history
(`gpt-5.2`, `gpt-5.2-codex`, `gpt-5.1`, `gpt-5.1-codex` — the codex fixture id,
now exact — `gpt-5.1-codex-max`, `gpt-5.1-codex-mini`, `gpt-5-codex`,
`gpt-5-nano`, `gpt-5-pro`, `gpt-4.1`, `gpt-4.1-mini`, `gpt-4.1-nano`,
`gpt-4o-mini`, `o3`, `o3-mini`, `o4-mini`, `codex-mini-latest`). Every
anthropic/openai id in the fixture corpus now exact- or family-matches
(tested: zero `none`). `[meta]` bumped to 2026-07-14.

**Maintainer-side CI nag** (`.github/workflows/prices-freshness-nag.yml`, new
file — publish workflow untouched): weekly cron reads the bundled
`prices_date` with stdlib and, past `stale_days`, upserts ONE pinned issue
("bundled prices are N days old — re-verify against the cited sources") —
reopens if human-closed, never duplicates, never fetches a vendor page (a
wrong auto-parsed rate is the worst outcome; the workflow nags a human).

Also fixed: a scalar key under `[prices]` (e.g. `stale_days`, or any user
typo) crashed `prices list`/`prices sync` provider iteration — the sites now
skip non-table values (regression-tested).

New: `cage/freshness.py` · `ledger.newest_ts` · `policy.prices_stale_days` ·
doctor `prices-age` · `cage query prices-freshness` · dummyrepo S15 (backdated
meta → post-commit note; sync silences; data-relative 100-day footer exact +
byte-identical; `stale_days = 0` opt-out) · 22 new tests (623 passing).

## v0.23.0 (2026-07-14) — tool-receipt pricing: dollars for call-less token receipts

Built from: [docs/archive/v0.23-tool-receipt-pricing.handoff.md](docs/archive/v0.23-tool-receipt-pricing.handoff.md) ·
[docs/archive/v0.23-tool-receipt-pricing.prompt.md](docs/archive/v0.23-tool-receipt-pricing.prompt.md) ·
[docs/archive/v0.23-prices-route-tool.handoff.md](docs/archive/v0.23-prices-route-tool.handoff.md) ·
[docs/archive/v0.23-prices-route-tool.prompt.md](docs/archive/v0.23-prices-route-tool.prompt.md)

Graphify's interceptor and fux-style shims file token-savings receipts with a
`task` but **no call id** — the saved tokens belong to future calls the shim
can't know. Those receipts rendered tokens but priced $0. They now resolve a
model at derive time via a deterministic **pricing ladder**
(`cage/receiptprice.py`, one implementation for every consumer):

1. **`[tools.<tool>] price_at = "provider/model"`** — explicit policy routing,
   written by the managed verb **`cage prices route-tool <tool> --to
   <provider>/<model>`** (`--remove` deletes; idempotent, before/after printed,
   bundled policy untouched — completes the debated spec's rung-1 surface).
   Validated against `policy.price_match` at use time: a dangling target
   *writes with a warning* (set-route-then-add-price works; unlike `alias`,
   which refuses), prices nothing, and never falls through (the dangling-alias
   rule); `cage prices list` and `cage doctor` flag it.
2. **task model** — the dominant model of the calls joined to the receipt's
   task (task-id + session-window calls, the `taskgroup` join): max summed
   `tokens_in`, ties → call count → lexicographic `provider/model` (a total
   order, tested).
3. **refusal** — UNPRICED, loudly: `roi` and `report` print the ⚠ headline
   plus one **runnable** fix line per affected tool — `run: cage prices
   route-tool <tool> --to <provider>/<model>  (or run in a metered session)` —
   with the real tool name substituted (the fix-hint contract, tested
   literally: copy the line, substitute the target, run it, dollars appear).

Method law holds: the USD keeps the receipt's own `method` (`modeled`, never
upgraded); the rung is footnoted in `roi`/`attrib` text (`≈ graphify priced at
task model (anthropic/…)`), named by `cage verdict <tool>`, and is a
`priced_via` column in `roi`/`attrib` CSV. A receipt whose call id doesn't
resolve (a fleet bundle missing that call) enters the ladder instead of
silently pricing $0.

**Historical derived numbers change (that's the feature):** ledgers with
call-less token receipts now show non-zero dollars in `roi`, `attrib`,
`verdict`, `report --by task/agent` saved columns, and the bare-`cage`
overview. Receipts with a resolvable call id — and `cage demo`'s §4.4
tables — are byte-identical to before. Derive-time only: no ledger row is
ever written or rewritten, so setting `price_at` re-prices history.

Also: `cage query receipt-pricing` explains the ladder with live policy
values; `docs/pricing.md` gains the "Tool receipts" section; plan §4.5 notes
the shape; dummyrepo scenario S14 sets its route via the verb and exercises
all three rungs + the tie-break end-to-end through the CLI. Routes are user
intent: the bundled policy ships none (tested) and `prices sync` never
touches them; a hand-added `[tools.<tool>]` table is edited in place with a
`# cage:custom` mark, exactly like `prices set`.

## v0.22.2 (2026-07-12) — capture correctness: three bugs from the v0.22.1 full test run

The full sibling-repo test plan (`docs/full-test-plan-sibling-repo.md`) was executed
end-to-end against v0.22.1 — real Claude Code CLI + VS Code extension, Codex VS Code
extension, Copilot CLI + VS Code chat, and the Kiro IDE. All seven parts passed; the
run surfaced three capture-correctness bugs, all fixed here with regression tests.

- **Live-capture duplicate rows (hook race)** — a machine with both user-level
  (legacy) and project-level Claude hook wiring fires two `cage hook-*` processes per
  Stop/SessionEnd; both loaded the dedupe `seen` set before either write landed, so
  **every live turn was double-appended and live Claude spend double-counted**.
  `lockutil`'s docstring named exactly this scenario but the hook path never took the
  lock. `hooks._capture_calls` now wraps its read-check-append in
  `lockutil.locked(state/import.lock)` — the same lock the import path holds — fail-open
  with a `hook.capture.lock` debug line on a lock miss. Regression test drives a real
  cross-process interleave (verified fail-before/pass-after). One-shot imports were
  never affected (single writer under `import.lock`).
- **graphify double-metering** — graphify ≥ 0.5.0 natively files a cage receipt per
  query when `.cage/` exists, so `cage graphify -- …` (and the setup-installed
  `bin/graphify` interceptor) filed a second receipt for the same saving → roi/verdict
  inflated 2×. The wrapper now snapshots the ledger's graphify receipt ids before the
  child runs and defers when the child self-metered (one saving, one receipt); the
  child gets `CAGE_GRAPHIFY_METERED=1`, a forward handshake a graphify version can
  respect to skip its native receipt (task binding then returns to the wrapper). Old
  graphify versions keep the wrapper's task-bound receipt exactly as before.
- **`cage meter -- <cmd>` separator** — argparse REMAINDER keeps the `--`, so the
  documented form tried to exec `'--'` itself. The separator is now stripped
  (mirroring `cage graphify`); the child's exit code propagates as before.

Also in this release: the v0.22.1 run record is archived at
[docs/archive/v0.22.1-full-test-run.md](docs/archive/v0.22.1-full-test-run.md)
(58 findings rows: capture matrix per agent×surface, PII canary sweep, determinism
double-runs, offline sweep, portable-wiring clone-sim, launcher-mode round-trip,
zipapp parity, fleet study); the evergreen test plan gains the run's four drift
fixes (`--since <window>` not date; `cage outcome` has no `--ok` — success is the
default; export manifest wording; a network-denied sandbox as the Wi-Fi-off
equivalent); the reusable driver prompt is indexed under Operations
(`docs/cage-claude-code-prompt-full-test-run.md`). Suite: **574 tests passing**
(three new regression tests).

Built from: [test run record](docs/archive/v0.22.1-full-test-run.md) · [driver prompt](docs/cage-claude-code-prompt-full-test-run.md) · plan: [docs/full-test-plan-sibling-repo.md](docs/full-test-plan-sibling-repo.md)

## v0.22.1 (2026-07-11) — docs lifecycle: the archive, the storybook spine, the rule

Docs-only release: `docs/` (41 loose files, most of them shipped-work exhaust) is restructured so a future reader — human or agent — can tell live spec from historical build instruction, and the discipline is made durable as a CLAUDE.md rule.

- **`docs/archive/`** — every shipped handoff/prompt/build-prompt (all of the old `docs/prompts/`, now removed, plus the root-level pairs) moved and renamed to sort by the release that shipped the work: `vX.Y-<feature>.{handoff,prompt}.md`, text verbatim plus a one-line "Archived — history, not spec" header. Superseded drafts (the ledger-scale plan amendment, the meter research pair, the dummy-repo trio) archived under the same convention; the applied `claude-md-proposal-*.md` trio deleted (verified applied; git history preserves them). Index: `docs/archive/README.md` (version · feature · handoff · prompt · CHANGELOG anchor, with explicit mapping notes where a version was ambiguous).
- **The storybook spine** — new `docs/README.md` (Start here → Subsystem design docs → Operations → Active work → Archive); CHANGELOG entries v0.16.0–v0.22.0 each gained a trailing "Built from: …" line linking their archived pair; `docs/full-test-plan-sibling-repo.md` reset to an evergreen template (`<version under test>` placeholder, boxes unticked) with the ticked v0.16.0 run record archived as `docs/archive/v0.16-full-test-run.md`.
- **The rule (CLAUDE.md, Must-Know Rules)** — handoff/prompt docs have a lifecycle: active in `docs/` root (listed under *Active work*) while unshipped; **the release that ships the work must, in the same change, move the pair to the archive, link it from the CHANGELOG entry, update both indexes, and promote any still-true design content into the living docs.** A shipped feature whose handoff/prompt still sits in `docs/` root is a release bug, same as a missing changelog entry. (This release dogfoods it: its own build prompt is archived below.)
- **README trimmed (307 → 235 lines), nothing lost** — the pricing wall-of-text became the new design doc `docs/pricing.md` (how a call prices · the unpriced workflow · policy versioning/`cage prices sync` · fleet repricing · the Copilot approximation · credits vs prices); the 44-line command listing, the Authorship section, and a third of Honest attribution now live behind links (`cage --help`, plan §3.5, plan §4). The keep-untouched sections (story, See it, Quickstart, agents table, `$0` guarantee) are byte-identical.
- Zero behavior change: comment/docstring path updates only (`tests/test_bundled_data.py`, `tools/buildpyz.py`, `tools/dummyrepo/run.py`); every relative link in README/CHANGELOG/CLAUDE.md/docs verified resolving; suite unchanged (569 passing), skillgen `--check` clean.

Built from: [prompt](docs/archive/v0.22.1-docs-lifecycle.prompt.md)

## v0.22.0 (2026-07-11) — restricted environments: python-launcher mode + cage.pyz (plan §5)

Cage as a first-class citizen on locked-down (finance/enterprise) endpoints where unknown exes are blocked (AppLocker/WDAC) or pip/PyPI is unreachable. Design of record: `docs/restricted-environments.md` (+ `docs/portable-wiring.md`, extended); handoff: `docs/archive/v0.22-restricted-env.handoff.md`.

- **Python-launcher wiring mode (opt-in)** — `cage setup --python-launcher` persists `[wiring] python_launcher = true` in project policy and (re)writes the shim pair + every user-level wired file (copilot hook, codex MCP, kiro MCP, git commit hooks) to resolve cage **through the interpreter only** (`python3 -m cage` / `py -3 -m cage`) — nothing exe-shaped is probed or executed, grep-tested. Committed files are unchanged (they reference the shim; the shim *is* the mode). Same fail-open exit-0 contract; plain `cage setup` re-runs preserve the persisted mode byte-identically; flip the key to `false` + re-run to revert. Mode-switch re-wiring collapses stale entries (`paths.cage_command_tail` now recognizes the interpreter forms); `cage doctor`'s portability check names the active mode and warns on policy↔shim drift.
- **`CAGE_RUN_PYTHON=1`** — runtime-only override on the **standard** shim: skips the exe probe and goes straight to the interpreter without rewiring (the standard shim texts changed once to carry the branch — behavior with the env unset is test-pinned identical, and the next `cage setup` rewrites the file).
- **`cage.pyz` release asset** — every GitHub release now also carries a single-file stdlib zipapp + `SHA256SUMS`, built and smoke-tested by CI (new `build-pyz` → `smoke-pyz` 3-OS matrix → `release-pyz` jobs on the same `release: published` trigger, fully independent of — and never touching — the PyPI trusted-publishing job). Run it as `py cage.pyz import/export/report`; the pyz story is pull-based capture — shims never embed a pyz path, hooks need an importable install. Local smoke build: `python -m tools.buildpyz` (`just pyz`); never attach from a laptop.
- **importlib.resources migration (the pyz prerequisite)** — all bundled-data reads go through the new `paths.bundled_data()` Traversable (`policy` default/prices, skill/prompt/steering asset copies, the graphify shim, doctor-bundle provenance display); wheel behavior byte-identical (tested), and every asset read is exercised over a real built pyz (`tests/test_zipapp.py`). `paths.bundled_data_dir()` is gone (repo-internal, 5 call sites).
- **Distribution honesty** — `cage --version` prints `cage X.Y.Z (zipapp)` under the pyz; `cage doctor`'s tool check labels the zipapp run and states the pull-based-capture posture instead of a spurious not-on-PATH warn.
- **Docs + query** — `docs/restricted-environments.md` (three tiers: launcher mode · pyz · internal mirror; the WDAC script-host caveat stated honestly; a first-endpoint validation checklist), README platforms link, `docs/portable-wiring.md` launcher-mode section, new `cage query restricted-env` concept + `portable-wiring` extended.
- Validation: launcher-mode grep contract + shim runtime + `CAGE_RUN_PYTHON` precedence + doctor mode/drift tests; bundled-data wheel byte-identity + full pyz asset/determinism suite; dummyrepo **S12** (launcher wiring end-to-end) and **S13** (pyz wheel↔zip report parity, `$CAGE_PYZ` reuses the exact CI artifact). +26 tests (543→569).

Built from: [handoff](docs/archive/v0.22-restricted-env.handoff.md) · [prompt](docs/archive/v0.22-restricted-env.prompt.md)

## v0.21.0 (2026-07-11) — CSV output + agent reporting recipes (plan §3.9)

CSV as a one-way **reporting** surface — never blurred with the re-importable fleet bundle (`cage export --study`, jsonl, merge-by-id), never an import source. Design of record: plan §3.9 + `docs/csv-output.md` (per-view column contracts).

- **`--csv` on the read views** — `report` · `attrib` · `roi` · `compare` · `study report` · `calibration` (incl. `--human`) · `human` · `trend`. Bare `--csv` streams to stdout (pipe-friendly; confirmations go to stderr), `--csv <path>` writes a file. One shared data structure per view feeds the text table AND the CSV (`render_csv` beside each `render_*`) — same numbers by construction, no view computes twice. New shared renderer `cage/csvout.py`: stdlib `csv`, RFC-4180 quoting, LF pinned on every OS (`lineterminator="\n"` + `newline=""` file writes), one canonical cell rendering (bool → `true`/`false`, floats trimmed fixed-point, lists `;`-joined, dicts as sorted JSON).
- **Honesty survives into the spreadsheet** — method/match tags are **columns** (`estimated` never silently drops; roi rows now carry the least-trusted receipt method, the attrib rule); compare deltas stay `estimated` with the observational caveat verbatim in a `note` column; min-n refusals keep the reason and **no numbers**; the UNPRICED gap rides as per-group `unpriced_calls`/`unpriced_tokens` columns on `report` and as an `unpriced` row on compare/study. `cage human`/`cage trend` keep attested vs derived as separate `kind` rows — never blended, same as the text sections.
- **Raw-row CSV** — `cage export --csv calls|receipts|tasks [--since …]`: flattened ledger rows for pivot tables, the ledger's own PII surface (counts and ids, never content); honors import-before-export; closed per-kind column contracts (`exportcmd.RAW_CSV_FIELDS` — the schema tuples + the additive fleet `machine` stamp; tasks pin identity/outcome/label/estimate/git-snapshot fields). `--format csv` is now the legacy spelling of `--csv calls` and inherits the LF/canonical-cell fixes (it previously emitted CRLF). Bad combinations are typed `CageError`s: `--csv`+`--json`/`--html`/`--format`, `--study`+`--csv`, `--agent`/`--project` on non-call kinds, `--csv` on non-report study actions.
- **Skill: reporting recipes on all four hosts** — the rendered `cage` assets (claude/codex SKILL.md · copilot prompt · kiro steering · generic agents skill) teach "generate my cost report / CSV / summary": weekly spend (`cage report --csv --since 7d`), per-tool savings (`cage attrib --csv`), worth-it (`cage verdict <tool>`, quoted verbatim), fleet number (`cage study report --csv`), estimate accuracy (`cage calibration --csv`) — plus the summarization rules: quote cage's numbers verbatim, keep method tags and UNPRICED/observational caveats, never fill a refusal (INSUFFICIENT DATA stays in the summary), default save path `./cage-report-<view>-<since>.csv`. Edited via `tools/skillgen/fragments/` only; rendered + blessed; `--check` clean.
- **MCP parity** — `format: "csv"` on `cage_report`/`cage_attrib`/`cage_roi` returns the same `render_csv` output, so extension-hosted agents without shell access can still produce the CSV content.
- **`cage query csv-output`** — new concept entry: which views, the column law, same-numbers guarantee, bundle-vs-CSV distinction; the export help text documents the distinction too.
- Validation: golden byte-exact CSVs over the seeded §4.4 demo ledger, determinism double-runs, text-vs-CSV same-numbers assertions, method-tag column on every view, PII grep on raw CSVs, RFC-4180 round-trip (and the label/phase single-token guard that keeps commas out of grouping keys), MCP parity vs the goldens; dummyrepo **S8** adds `report --csv`/`attrib --csv` to the byte-identical + CAGE_DEBUG-no-drift sweep. +34 tests (509→543).

Built from: [prompt](docs/archive/v0.21-csv-and-report-skill.prompt.md)

## v0.20.0 (2026-07-11) — portable wiring (no absolute paths in committed files)

Fixes a sharing bug: wired hook/MCP entries embedded the wiring machine's **absolute cage path**, and several wired files are committed to git (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`, `.codex/hooks.json`, `.kiro/hooks/*.kiro.hook`) — so one developer's filesystem layout shipped to the whole team and every clone got broken wiring. Setup-time path resolution is replaced by a **committed runtime-resolving shim**. Design of record: `docs/portable-wiring.md`.

- **The shim (`cage/runshim.py`)** — `cage setup` writes `.cage/bin/cage-run` (plain POSIX sh, no bash-isms) + the Windows twin `cage-run.cmd`: identical bytes on every machine, intended to be committed (`.cage/.gitignore` excludes only `ledger/`/`out/`/`state/`). At runtime it resolves cage in documented order: `command -v cage` → `~/.local/bin/cage` / pipx / an active `$VIRTUAL_ENV/bin/cage` → `python3 -m cage` if importable → **exit 0 silently**. A clone without cage installed = working agents, no noise, no capture — fail-open extended to wiring (doctor diagnoses; the hook path never complains). All args pass through. The `.cmd` twin mirrors the order (`where cage` → `%USERPROFILE%` installs → `Scripts\` venv → `py -m cage`), labelled UNVERIFIED on a real Windows agent host. Execute bit set at write time, fail-open for `core.fileMode=false` clones (doctor runs the shim via `sh`, so the answer never depends on the bit).
- **Committed wiring references the shim, never a binary path** — per-host mechanism verified against each host's docs and recorded in each wire module's docstring: Claude hooks use the documented `$CLAUDE_PROJECT_DIR` placeholder (hook cwd is NOT guaranteed to be the project root); `.mcp.json` uses documented `${CLAUDE_PROJECT_DIR:-.}` env expansion (the `:-.` default is a documented requirement); `.vscode/mcp.json` uses documented `${workspaceFolder}` substitution; Codex + Kiro hooks get a **self-locating one-liner** (`git rev-parse --show-toplevel` → exec the shim → `exit 0` if either is missing) because Codex documents hook cwd as the *session* cwd (its docs themselves recommend git-root resolution) and Kiro documents neither cwd nor variables.
- **The ONE exception, documented not silent** — `.kiro/settings/mcp.json` stays machine-absolute by necessity: Kiro spawns MCP servers from its *install directory* (kirodotdev/Kiro #6525) and supports no variable substitution in `command` (open FR #5659), so a relative/variable form provably breaks. Doctor advises gitignoring it. **User-level configs unchanged**: `~/.copilot/hooks/cage.json`, `~/.codex/config.toml` MCP, and `.git/hooks/*` are per-machine by nature — the resolved absolute path stays the robust choice there (the "bare `cage` fails under a GUI PATH" constraint still holds; the shim now carries that resolution for committed files).
- **Migration** — re-running `cage setup --wire-only --<agent>` detects legacy absolute/bare entries in committed files, rewrites them to the shim form (foreign hooks never touched; custom flags on a cage command survive), and prints what it migrated. Setup twice ⇒ byte-identical, still. Legacy absolute entries keep working until the user re-runs setup — the shim path is additive.
- **Doctor `portability` check** — flags any committed wired file carrying a machine-absolute cage path (teammates' clones break — re-run setup), a missing or execute-bit-less shim, and runs `cage-run --version` to verify resolution succeeds on this machine; prints the kiro-MCP gitignore advice.
- **`cage query portable-wiring`** — new concept entry: why the shim exists, the resolution order, fail-open-when-absent, committed vs user-level, the one-exception host.
- Validation: dummyrepo **S1** now clone-simulates (copies the wired testbed sans `.git`/gitignored dirs to a new path → doctor portability clean there → the committed shim actually resolves and passes args through). New `tests/test_portable_wiring.py` pins the never-rot invariant (grep every committed wired file for absolute paths), the shim resolution order incl. absent-cage → silent exit 0, cleanup-allowlist unreachability of `.cage/bin/`, migration exactly-once, and the doctor flags. +13 tests (496→509).

Built from: [prompt](docs/archive/v0.20-portable-wiring.prompt.md)

## v0.19.0 (2026-07-11) — pricing management (the unpriced workflow, `cage prices`, policy versioning)

A ledger is only as honest as its price table. This release makes the price table a managed surface: find what's billing $0, fix it with one pasted line, know when the bundled rates have moved on — plus two riders (self-refreshing exports, state-dir cleanup) that keep fleet bundles complete and footprints tidy. Driven by a real field report: copilot-served Claude models (`copilot/claude-opus-4.6`, dotted ids, `provider="anthropic"`) and the router pseudo-model `copilot/auto` (empty provider) silently billing $0.

- **`cage prices` command group (plan §3.3)** — `unpriced` scans the resolved ledger for `none`-match calls and prints call count, token volume, and a ready-to-run fix line per key; `set <provider> <model> --input --output [--cache-read]` is an idempotent insert-or-update of a project row (validated: non-negative, `cache_read ≤ input`; `--cache-read` defaults to 0.1× input, announced); `alias - copilot/auto --to anthropic/claude-sonnet-4-6` routes a router pseudo-model explicitly (`-` = the empty provider such rows stamp; target must be an exact row — never a guess, and a dangling alias surfaces UNPRICED); `list` shows every visible row with bundled-vs-project origin and which wins; `sync` diffs the project against the installed bundle (dry-run; `--update --yes <prov>/<model>` applies per confirmed row). Typed `CageError`s at the boundary; `--json` uses the `cage.v1` envelope.
- **The write layer (`cage/pricestoml.py`)** — the bundled policy is read-only at runtime; all writes land in the project policy.toml as text surgery, never a whole-file rewrite: in-place value edits for hand-written tables (comments survive, header marked `# cage:custom`) or a deterministic cage-managed block (sorted; two inserts in either order ⇒ identical bytes). Every mutation re-parses before an atomic `os.replace` — a bad write can never leave an unparseable policy behind.
- **Bundled prices refreshed (researched 2026-07-11, source URLs cited in the file)** — Anthropic: Opus 4.7/4.6/4.5 rows added (the explicit 4-5 row is load-bearing against a tie-break onto retired `claude-opus-4` at 15/75), deprecated Opus 4.1/4 kept so historical rows reprice at what they actually billed, Sonnet 5 (standard rate; the intro-window override documented in place), Sonnet 4.5, Haiku 3.5. OpenAI: the gpt-5.6 trio and 5.5-pro/5.4-mini/5.4-nano/5.4-pro added; **two cache-read fixes** (gpt-5.5 1.25→0.50, gpt-5.4 0.625→0.25 per the official page). `copilot/auto` ships UNPRICED with a commented-out alias example — a router priced silently is a wrong number.
- **Effort-tier + punctuation + route-prefix normalization** — family matching now canonicalizes before segment comparison: known router prefixes strip (`copilot/` — a closed list, unknown routers stay UNPRICED), `.` folds to `-` (`claude-sonnet-4.6` family-matches the `claude-sonnet-4-6` row), and trailing effort tiers (`low|medium|high|max`) drop — both vendors bill every tier at the same per-token rate (verified 2026-07-11), so tiers price at the base row with the family footnote, never `exact` (method law). Behavior change: a dotted minor with no exact row (`gpt-5.7`) now family-prices at its base row instead of UNPRICED — footnoted, and current minors ship exact rows.
- **Merge-granularity fix** — `policy.load` now merges `prices`/`credits`/`alias` per provider *and* per model: a partial project `[prices.anthropic."x"]` table no longer silently wipes the bundled anthropic siblings.
- **Policy versioning (`[meta]`)** — the bundle stamps `prices_version`/`prices_date`/`cage_version`; `cage init` copies (and a first `prices set` stamps) it into the project policy. `cage doctor` and `prices list` print one recommendation line when the bundle is newer — never auto-applied; `sync --update` preserves customized rows by construction and requires per-row confirmation for unmarked drift (cage can't reconstruct which old bundle a row came from — honest over clever).
- **UNPRICED is now loud on every publishing surface** — `report`, the bare-`cage` overview, `compare`, and `study report` print `⚠ N calls (X tokens) UNPRICED — totals understated; run 'cage prices unpriced'` whenever `none`-match calls exist, so a fleet analyst can't publish a total without seeing the gap. Repricing is derive-time (the ledger stores counts, not conclusions): fixing policy.toml re-prices every imported bundle row retroactively; self-costed rows and receipts keep their stored figures. Report also gains a `≈ priced by alias` footnote.
- **Rider: export imports everything first (plan §3.7)** — `cage export` (plain and `--study`) runs the full all-agent sweep before emitting (`--agent` now filters output only, never the capture), so a capture-only machine ships a complete bundle from one command. `--no-import` keeps the as-is snapshot; new `[capture] import_before_export` policy toggle (precedence: flag > `CAGE_CAPTURE` env > policy); the sweep is fail-open (a broken parser warns and export proceeds); the study manifest records `refresh: {ran, new_calls}` (counts only) and the analyst's import surfaces it (`swept +N at export`).
- **Rider: state-dir cleanup (`cage/cleanup.py`, plan §3.6.4)** — a closed allowlist over `.cage/state/`: aged `debug.log`/`hooks-seen.jsonl` rows, stale `pending-*` provenance buffers, cursors whose source log is gone, `*.tmp`. Never — by construction: `ledger/`, policy.toml, the machine id, `study.jsonl`, `limits.json`. `[cleanup] enabled/days` (default on/30; env `CAGE_CLEANUP` overrides); the auto path piggybacks on `cage import`/hook sweeps (throttled, fail-open, debug-logged under `cleanup.prune`); manual `cage cleanup` is dry-run until `--apply`. State files are never read by derived views — cleanup can't change a reported number (tested byte-identical).
- **`cage query` coverage** — nine new entries, all live-interpolated: calculations `pricing-match`, `unpriced`, `repricing`; concepts `prices-cli`, `effort-tiers`, `policy-versioning`, `copilot-pricing` (copilot-served Claude at Anthropic list rates ≈ GitHub's own AI-Credits metering basis since 2026-06-01; `[credits]` stays a separate layer), `cleanup`, `import-before-export`. The UNPRICED report line points at `cage query unpriced`. `cage doctor` gains `prices-meta` and `state` checks.
- **Validation** — dummyrepo scenario **S11** (seeded unpriced calls → exact `prices unpriced` output → `set`+`alias` → report re-prices to exact expected USD with the ledger untouched → stale `[meta]` → sync recommendation → restamp clears it) and an 8th fleet machine in **S9** that never runs `cage import` — its bundle is complete purely via export's sweep and the analyst's totals stay exact. +55 tests (441→496).

Built from: [prompt](docs/archive/v0.19-pricing-management.prompt.md)

## v0.18.0 (2026-07-11) — derived human attention (passive minutes from turn gaps)

Total cost's missing half: what the agent costs in **human time**, derived passively from the session logs cage already imports — with the manual axis as the ground truth that calibrates the heuristic (plan §4.10; `docs/human-baseline.design.md` §5c).

- **`gap_ms` on the call row (additive, optional)** — at import, where a transcript carries per-turn timestamps, each call row gains the wall-clock gap between the previous assistant turn's end and the human turn that led to this call. Per-agent availability is documented, never guessed: **claude yes** (every record timestamped; tool-result / meta / sidechain records correctly never count as human turns); **codex / copilot / kiro no** — their pinned log formats lack a usable timestamp pair, so their rows omit the field (**no signal ⇒ no field, never fabricated**). Composite ids unchanged (`gap_ms` never enters an id); an unstamped row is byte-identical to the legacy contract; re-imports stay idempotent.
- **Read-time derivation, one module** (`cage/attention.py`) — derived attention minutes = `Σ min(gap_ms, idle cap)`; every consuming view calls in here, none computes gaps itself. The idle cap guards against billing walked-away time as supervision: policy `[human] idle_cap_minutes` wins, `constants.IDLE_CAP_MINUTES` (10, rationale in the file) is the fallback — changing it re-derives, the ledger is never rewritten. Deterministic: same ledger + policy ⇒ same minutes.
- **Method honesty** — derived minutes are always `estimated`, labelled `derived (turn-gaps, capped)`. **Attested** minutes (`cage human-record`, or the new friction-drop `cage outcome <task> --minutes N` — the same fail-open, idempotent receipt path) rank above derived: per task **attested wins, derived renders as reference, the two are never summed**.
- **Views** — `cage human` and `cage trend` show attested vs derived as separate blocks (absence of gap data is an explicit line). `cage compare`, `cage verdict`, and `cage study report` gain one **total-cost line** — agent $ + human minutes × rate, tagged with the human component's method — suppressed by `--agent-only`. `matrix --human` is byte-identical (a different question).
- **`cage calibration --human`** — over tasks with BOTH attested and derived minutes, the derived/attested ratio distribution (median + IQR) is the heuristic's **measured** accuracy; below `MIN_ESTIMATE_N` it refuses. The heuristic never self-reports confidence.
- **Explainers** — new `cage query` calculation entry `attention-minutes` ("how are human minutes derived", live cap value) and an extended `human-axis` concept entry.
- **The watcher guard** — deliberately NOT built: no editor plugins, activity trackers, keystroke or focus monitoring. Transcript timestamps only; PII surface unchanged (timestamp arithmetic, counts-never-content).
- Validation: dummyrepo scenario **S10** (seeded transcript gap → exact derived minutes across human/compare/verdict; attest → precedence + exact calibration ratio; `--agent-only` clean; byte-identical re-runs). +23 tests (418→441).

Built from: [prompt](docs/archive/v0.18-human-attention.prompt.md)

## v0.17.1 (2026-07-09) — dead-code cleanup

A systematic AST sweep (unused imports, unreferenced functions/methods/constants, tracked junk, wheel-content audit) after the parity release:

- Removed `humanview`'s unused `quality` import (leftover from when the redo-guard moved to `tasks.read`) and the unreferenced `Footprint.out_file()` helper (`serve` uses the `out` property directly, which stays).
- `schema.PROVENANCE_FIELDS` was unreferenced but is the documented substrate contract (plan §3.5) — instead of deleting a contract constant, a new shape test pins `make_provenance` rows to exactly those keys in that order (additive-only schema, enforced). +1 test (417→418).
- Everything else suspected came back wired and in use (`serve`/`adoptcmd`/`metercmd`/`usageparse`/`wizard`/`cfgio`/`pointers`, the legacy `import-claude`/`import-codex` subcommands, `data/shims/`); no tracked junk, no orphaned fixtures. The brand images stay bundled (`data/assets/*` in package-data) by choice.

## v0.17.0 (2026-07-08) — Windows/mac parity + the path probe

- **Three-OS CI gate** — the workflow matrix is now `ubuntu/macos/windows-latest` × Python 3.11–3.13, running the suite, the skillgen drift check, **and** the S1–S9 scenario runner (`PYTHONUTF8=1`; the runner pins subprocess decoding to UTF-8 so cp1252 consoles can't corrupt output). macOS stays field-validated; **Windows is CI-tested** — the honest wording until someone runs `docs/windows-manual-checklist.md` (new) on a real Windows machine.
- **Per-OS log locations, one registry** — `paths.agent_log_sources(agent)` is the single table of candidate `(location, glob)` pairs `cage import` scans and the probe reports. `vscode_user_candidates()` gains `%APPDATA%\Code\User` (documented VS Code location); `kiro_data_candidates()` gains `%APPDATA%\Kiro\User\globalStorage\kiro.kiroagent` — labeled **UNVERIFIED-LAYOUT** (inferred from VS Code-family, not pinned on a real Windows Kiro; the probe report carries the same label). Env overrides win everywhere, unchanged. A missing source dir no longer scans as a phantom `[src]` candidate.
- **One fail-open lock helper** (`cage/lockutil.py`) — `fcntl.flock` → `msvcrt.locking` → proceed-unlocked, replacing the two copied blocks in `importcmd`/`originrecord`; the no-primitive tier is debug-logged, id-dedupe stays the correctness backstop.
- **Windows-shaped wiring** — hook commands quote the resolved cage path (`"C:\…\Scripts\cage.exe" import …` would otherwise split at the space); `reresolve_cage_command` heals `cage.exe`/backslash/quoted forms; Codex's TOML MCP block writes forward slashes (backslashes are TOML escapes); git hooks keep the POSIX-minimal `#!/bin/sh` wrappers — Git-for-Windows always runs hooks under its bundled sh, making that the provably portable choice.
- **Console safety** — `cli.main` degrades the ✔/·/⚠ glyphs on non-UTF consoles (`errors="replace"`) instead of dying with UnicodeEncodeError on cp1252; the scheduler hint is OS-aware (cron line on POSIX, a `schtasks /create` example on Windows — printed, never installed).
- **`cage doctor --paths` + probe events (the exportable path diagnostic)** — `cage/pathprobe.py` renders one read-only screen per agent × candidate location: found/missing, files matched, parseable row count, cursor state, one why-line per miss ("location absent", "no files match <glob>", "cursor: already imported", "parse: 0 rows — see debug.log"), env overrides and UNVERIFIED-LAYOUT candidates labeled, ending with the active sink + precedence chain. It writes nothing. The same facts stream to `debug.log` as metadata-only `probe` events during `CAGE_DEBUG=1 cage import`, and `cage doctor --bundle` now ships the report as `paths.txt` (home-prefix redaction applies). New explain entry: `cage query "why is nothing being captured"`. +16 tests (401→417).

Built from: [prompt](docs/archive/v0.17-windows-and-path-probe.prompt.md)

## v0.16.0 (2026-07-08) — cost-impact roadmap: validate · diagnose

Accumulating release for the cost-impact roadmap phases (`docs/archive/v0.16-cost-impact-roadmap.handoff.md`); each phase lands as a subsection below. Suite 318→401 across P0–P5 + the manual validation (roadmap complete).

### Manual validation (full-test-plan, 2026-07) — real-extension capture bugs

Findings from executing `docs/full-test-plan-sibling-repo.md` (run record: `docs/archive/v0.16-full-test-run.md`) against real Claude Code / Codex / Copilot VS Code extensions and the Kiro IDE (`../cage-testbed`):

- **Codex call ids no longer collide across sessions** (`transcript.parse_codex_calls`) — the id carried `session[:8]`, but every rollout stem starts with `rollout-`, so all Codex sessions shared one id namespace and `hooks.append_new` silently dropped colliding line indexes: on the validation machine **150 of 368 real calls (41%, ≈$11) were lost as false "dupes"**. The session component is now `sha1(session)[:8]` — deterministic per (session, line), unique across sessions. Existing ledger rows keep their old ids (append-only); unchanged rollouts are cursor-skipped, so historical undercount persists unless the ledger is rebuilt.
- **Codex rows carry the event's own timestamp** — `parse_codex_calls` stamped rows at import time, filing a May rollout in the import month's shard and breaking `--since`/month partitioning. The row `ts` is now the `token_count` event's `timestamp` (fallback to write-time when absent). Codex fixtures drop `ts` from `volatile`.
- **Derive-time repricing everywhere** — `regression`, `forecast`, `quality`, `trend`, `cage human` (humanview), and `cage why` summed the *stored* `est_cost_usd`, which is 0.0 for every transcript-sourced call — a $3,800 ledger read as "$0 drift / no spend / agent-side free". All six now route through `prices.call_usd` (tokens × policy at derive time), exactly like `report`/`budget`.
- **Provenance writes are race-safe and file-deduped** (`originrecord.record`) — two hook processes firing at once (SessionEnd delivered to two VS Code windows) could both pass the `_already_recorded` check before either appended (observed: duplicate rows 0.6 ms apart); an exclusive `state/provenance.lock` (same fail-open pattern as `importcmd._import_lock`) closes the window, and repeated files within one row (`["a.py","a.py"]` from two Write events) are kept once.
- **Fixtures: two of three `UNVERIFIED-FORMAT` cells closed with real sanitized captures** — `codex/vscode` (the `openai.chatgpt` extension writes the *same* `~/.codex/sessions` rollout store/format as the CLI) and `kiro/vscode` (this machine's real `tokens_generated.jsonl`, counts-only by construction). `copilot/vscode` stays a stand-in: the extension's real log was located (`…/workspaceStorage/<hash>/GitHub.copilot-chat/transcripts/<session>.jsonl`, same event stream as the CLI) but carries no usage-bearing `session.shutdown` event in a live session, and cage's default scan doesn't cover that location yet.
- **The real `~/.cage` is never a project root, even under a `CAGE_HOME` redirect** (`paths.find_project_root`) — the prep fix excluded only `global_base()`, which *moves* with `CAGE_HOME`, so a redirected run (tests, `tools.dummyrepo`) saw the real `~/.cage` as a project and resolved every dir under `$HOME` to the home — the scenario runner wrote its sandbox fixture/fleet rows into the user's **real global ledger**. Both the active global sink and the default `~/.cage` are now excluded; the runner leaves the real global byte-untouched (verified by checksum).
- **`render.ago` floors at "just now", never per-second** — "0s ago" → "2s ago" made back-to-back runs of the same view byte-different, which is exactly what the determinism sweeps (plan Part G, runner S8) compare.
- Carried from the prep session: `paths.find_project_root` no longer treats the global `~/.cage` sink as a project root; a malformed `--since` is a typed `CageError` (was silently ignored).
- **Copilot VS Code extension capture works** (`transcript.parse_copilot_vscode_calls` + a second scan root in `importcmd.import_copilot`) — the extension's `GitHub.copilot-chat/transcripts/` event stream never carries a usage event (no `session.shutdown`, even after quitting VS Code; pinned v0.54.0/1.126), so the per-request token counts are read from **VS Code's chat-session store** (`<vscode-user>/workspaceStorage/*/chatSessions/*.jsonl`, `CAGE_VSCODE_USER` override): requests merge last-write-wins by `requestId` (the store rewrites its array as the session grows), ids derive from the requestId (idempotent re-import), non-copilot chat providers are filtered, and only counts/ids/model/ts are ever read — titles and message bodies never. The third `UNVERIFIED-FORMAT` fixture cell is closed with a real sanitized session; all 8 agent×surface cells are now `format_verified`. The virtual `copilot/auto` model stays unpriced (doctor flags it) — a wrong number is worse than none.
- **A hook firing outside any project captures into the global ledger** — `hooks._root`, `hooks.post_commit`, `hooks.prepare_commit_msg`, `metering._resolve_root`, and `mcpserver._root` all fell back to the *cwd* when no project `.cage/` existed, growing a stray `.cage/` in whatever dir the session ran from and splitting the ledger (observed live in the resolver-precedence check). All five now use `paths.resolve_root` (override → project → global, plan §3.7).
- **`cage watch` exits 130 on Ctrl-C** per the CLI exit-code contract (was a deliberate 0; ruled against).
- **`cage doctor --bundle` redacts the home prefix** — `$HOME` → `~` in every member, including Claude's slug-escaped project dir names (`-Users-me-…`): machine-local paths stay diagnostic, the account username no longer ships in a bundle meant to be shared.
- +12 tests across the validation passes (389→401).

### P5 — `cage study`: the fleet study (N laptops, two phases, one analyst)

- **Opaque machine id** (`cage/machine.py`) — a random id generated once into `.cage/state/machine.json` (never hostname/username/anything derivable — the analyst keeps the name↔id mapping offline), stamped as an additive optional `machine` field on calls/receipts/tasks at the one write chokepoint (`ledger.append_row`). **Opt-in by existence**: only an enrolled ledger stamps; unenrolled ledgers stay byte-identical to the legacy contract (every pre-P5 exact-byte test passes unchanged). Plan §3.4 updated.
- **Recorded phases, not remembered dates** (`cage/study.py`) — `cage study start <phase>` / `stop` append marker rows (phase = one validated token, the `label` PII guard) to a fifth small append-only file, `ledger/study.jsonl`. Derive assigns each row by its own `ts` against **that machine's own markers** — deterministic, no derive clocks, and cross-machine clock skew cannot cross-assign (tested). Last marker wins forward in time; a `start` without `stop` extends; rows before any marker are *unphased* — excluded from deltas, visibly counted.
- **One-file collection** — `cage export --study` writes one zip per machine (raw rows + markers + a **counts-only manifest**: version, machine id, span, row counts per kind); `cage import bundle1 bundle2 …` merges into a fresh analysis ledger by row identity — calls/receipts by id, tasks/markers by whole-row content so task *updates* (the close!) survive the merge — idempotent on re-import (tested byte-for-byte). The refs/notes team path stays for git-fluent teams; bundles are the capture-only fleet path.
- **Coverage before conclusions** — `cage study report` opens with per-machine days-with-rows per phase and **flags gap days** (the silent-mid-week laptop is the #1 study-killer), then the number: the sample unit is the **machine-day** (a capture-only fleet closes no tasks; the study's question is what a week costs), per-machine-day totals **measured**, and the **paired-by-machine delta** — median over machines of (phase-B median daily − phase-A median daily), controlling between-machine variance — tagged **`estimated`** with the different-work-mix caveat. Below `MIN_COMPARE_N` machines with both phases the delta refuses; coverage always renders.
- **One-command enrollment** — `cage study join <phase>`: scaffold → wire all four agents → start the phase → `cage doctor` + the cron hint (cage installs no scheduler). Plus `cage study id` to read the opaque id.
- **Explainability + validation** — new `study-pairing` explain entry (`cage query "how does the fleet study pair machines"`); flagship skill regenerated; `--json` uses the `cage.v1` envelope. Runner scenario **S9**: 7 simulated machines (5 complete, 1 mid-week gap, 1 missing phase 2 — the handoff's 3-machine sketch predates the min-n gate, the S5 precedent) → real-CLI bundles → import-merge → exact coverage, gap flagged, pairs 6, exact −7,000 tok/day paired delta, double-import idempotent. +13 tests (376→389).

### P4 — `cage verdict <tool>`: the one-line answer, composed not computed

- **`cage verdict <tool> [--since]`** (`cage/verdict.py`) — `VERDICT: graphify is SAVING ≈ $X/mo net (modeled)` / `COSTING` / `INSUFFICIENT DATA`, as a **pure composer**: net = roi saved − roi own-cost (its sign *is* the verdict); marginal saving from attribution's latest task-linked receipt; direction from trend (the ledger-wide human axis, labelled as such); drift from regression; redo-rate from quality; break-even = net per receipt. It computes **no new statistics** — the ≈$/mo line is plain arithmetic scaling net by the receipts' own time-span (row timestamps, no clock) and refuses below a 7-day span rather than project from noise.
- **Every input renders its own method tag** — modeled attribution/roi (roi's tag is the least-trusted method among the tool's receipts, attribution's worst-case rule), estimated trend, measured drift and redo-rate — and any unavailable input prints `INSUFFICIENT DATA — <reason>` on its line, never an approximation. A tool with no receipts gets the honest headline refusal (and no numbers alongside it).
- **Explainability + surfaces** — `cage query "how is the verdict calculated"` (new `verdict-composition` entry); flagship skill regenerated with the "is tool X worth keeping" pointer; `--json` uses the `cage.v1` envelope. Runner scenario **S7** seeds a clearly net-positive tool and a clearly net-negative one (own cost $0.50/receipt vs $0.005 saved) and asserts SAVING, COSTING, the insufficient-data path, rendered tags, and byte-identical re-runs — completing the S1–S8 matrix. +6 tests (370→376), including a composer-honesty test pinning verdict's numbers to roi's exactly.

### P3 — `cage estimate` + `cage calibration`: estimate before, measure the gap after

- **`cage estimate [--scope] [--label] [--agent]`** (`cage/estimate.py`, on the shared `taskgroup` core) — a pre-task cost band: **median + IQR of measured totals over closed tasks matching the exact keys** (no similarity scoring, no ML — cage law), tagged **`modeled`** because history applied to an unrun task is a reconstruction, never an invoice. Below the new `constants.MIN_ESTIMATE_N = 5` it refuses with the reason — a band over noise is worse than no band. Deterministic; distinct from `forecast` (monthly projection, untouched).
- **`--record <task>`** stamps the estimate onto the **open** task row as additive fields — the spec'd `est_tokens` / `est_usd` / `est_n` plus the token band bounds `est_tokens_q1` / `est_tokens_q3` (decided at review: calibration must score against the band *as it was at estimate time*; recomputing over grown history would score a different band). Fail-open write; recording onto an already-closed task is refused at the CLI boundary (a retroactive estimate is exactly what calibration must never count). Plan §3.4 updated; empty = legacy contract.
- **`cage calibration`** (`cage/calibration.py`) — the estimator's empirical confidence: over closed tasks with recorded estimates, the actual/estimate **ratio distribution** (median + IQR) and the **in-band hit-rate**, both tagged **`measured`** (an observed frequency of recorded numbers). Open, zero-actual, and band-less (legacy) estimates are skipped with a visible count, never silently dropped. Ends with the plain-English line — "estimates landed in-band N% of the time (n=…)" — the estimator itself never self-reports confidence.
- **Explainability + surfaces** — `cage query "how is the estimate calculated"` answers from live values (`MIN_ESTIMATE_N` interpolated; new `estimate-band` + `calibration-hit-rate` registry entries); flagship skill regenerated (all four agents); `--json` on both commands uses the `cage.v1` envelope. Runner scenario **S6** drives the full loop through the real CLI — estimate (exact band) → refusal on thin history → `--record` ×2 → tasks run → `cage outcome` → calibration exact 50% hit-rate, byte-identical re-run. +10 tests (360→370).

### P2 — `cage compare`: measured stack comparison (observed groups, honest delta)

- **`cage compare`** (`cage/compare.py` + the shared `cage/taskgroup.py` P3 will reuse) — groups **closed** tasks by their *observed* stack signature (sorted joined-receipt tools; `human` excluded — the Tier-1 anchor is not a pipeline tool; empty ⇒ `agent-only`) and prints per group `n · median · IQR` of **measured** totals: recorded `tokens_in+tokens_out`, USD recomputed per call via `prices.call_usd`. Join precedence documented in the module: task-id first, then a session-window fallback (a task-less row joins when its session matches and its `ts` falls inside the task's call span — overlaps resolve to the smallest task id, a stable order). Median/IQR via stdlib inclusive quartiles; cross-month tasks read through the shard glob.
- **The delta is `estimated`, never `measured`** — median(stack) − median(agent-only baseline sharing every non-stack key), rendered with its method tag and the always-printed caveat: *observed difference across different tasks — not a controlled experiment*. No causal language anywhere.
- **Min-n gate, blocking** — new `constants.MIN_COMPARE_N = 5` (rationale comment in the third numbers-layer): a smaller group renders `insufficient data (n=X < 5)` and joins no delta. The command explains; it never numbers.
- **Additive task `label`** — `cage outcome <task> --label <word>` tags a task with one short token (letters/digits/`._-`, ≤32 chars, validated at the CLI boundary — never a path or free text; the `scope` PII spirit). `cage compare --by label` / `--label` group and filter on it; empty = legacy contract, plan §3.4 updated.
- **Explainability + surfaces** — `cage query "how does compare work"` answers from live values (`MIN_COMPARE_N` interpolated, new `compare-delta` registry entry); the flagship skill (all four agent renderings, via skillgen) points agents at `cage compare` for "did the tool actually cost less"; `--json` uses the `cage.v1` envelope. Runner scenario **S5** seeds 5 agent-only + 5 graphify (one cross-month pair) + a 2-task group and asserts exact medians, the estimated delta + caveat, the refusal, and byte-identical re-runs (the handoff's 3+3 sketch predates min-n = 5). +12 tests (348→360).

### P1 — diagnostics: `cage doctor --bundle` + "fail-open but never silent", audited

- **`cage doctor --bundle [path]`** (`cage/doctorbundle.py`) — one redacted diagnostics archive for capture bug-reports, under the ledger's own PII rule (**counts-never-content**): doctor output (text + json), the metadata-only `debug.log` + `hooks-seen.jsonl` (when present), cage/python/platform versions, resolved footprint paths with per-shard **row counts** (never a row body), policy **provenance** (bundled default vs project file, which cage env overrides are set), and the import cursor state. Per-member fail-open — an unreadable member lands in the manifest's `skipped` map with its reason, never aborting the bundle — while an unwritable *target* raises the one `CageError` (the read/CLI boundary). Archive bytes are deterministic (fixed zip epoch + member order).
- **Every capture-path swallow-site now leaves an attributable `debug.log` line under `CAGE_DEBUG=1`** — previously-silent sites got ADD-only trace lines (no control-flow change, all guarded so tracing can never break capture): a failed `ledger.append_row` (the unwritable-ledger case — the one failure that loses a row) records `ledger.append/write-failed` with the shard + row id; `hooks.prepare_commit_msg`'s bare swallow and a failed pending-edit buffer write now log; `importcmd`'s lock-unavailable, corrupt-cursor-load, and cursor-save failures log; and a **non-empty log parsing to 0 rows** — the upstream format-drift signature — records `skip=parsed-zero-rows` with the file + byte count.
- **Coverage audit test** (`tests/test_debug_coverage.py`) — 14 tests, one per swallow-site, each forcing exactly that failure and asserting fail-open holds (exit 0 / `False`, never a raise) *and* the named debug event appears: "fail-open but never silent" is now tested, not aspirational.
- **Runner scenarios S3 + S4** — `python -m tools.dummyrepo` now exercises the broken setups end-to-end (malformed policy degrades + logs + doctor flags it; unwritable ledger fails open + logs; truncated shard tail still reads; empty log imports 0) and produces + PII-greps a real bundle. +20 tests (328→348).

### P0 — capture validation harness

Before comparing or estimating anything, prove capture actually works on every agent × surface combination. No behavior change to cage itself — this phase adds the harness that pins existing behavior. +10 tests (318→328).

- **Fixture corpus** — `tests/fixtures/transcripts/<agent>/<surface>/` for all four agents (claude / codex / copilot / kiro) × (cli / vscode): sanitized session-log samples in each agent's real on-disk shape (realistic token counts, all content stripped), each with an `expected.json` freezing the exact call rows `cage import` must produce — deterministic ids included, `ts` excluded only for codex/kiro whose logs carry no per-row timestamp (the parser stamps write time). `tests/test_fixture_corpus.py` parametrizes over the corpus, plants each log into an isolated fake agent home at its real relative location, runs the real default (pathless) import scan, and asserts exact rows + idempotent re-import. A structural test fails if any agent × surface directory ever goes missing (the four-agent invariant, enforced).
- **`UNVERIFIED-FORMAT` stand-ins, never invented formats** — the codex/copilot/kiro VS Code-extension fixtures are CLI-format stand-ins until real extension logs are captured (handoff §10 open question); they are flagged `format_verified: false` in `expected.json` and marked `UNVERIFIED-FORMAT` in the corpus README, and a test asserts the flagging discipline (only vscode fixtures may be stand-ins; every CLI format is pinned against a real client log).
- **Dummy sibling-repo scenario runner** — `python -m tools.dummyrepo` (build-time only, stdlib-only, never in the wheel — the `tools/skillgen` rules): scaffolds a disposable repo beside the checkout, sandboxes every agent home + `CAGE_HOME` via env overrides (nothing touches real machine data), and runs the automatable scenario matrix from `docs/archive/v0.16-dummy-repo-test.plan.md` §9: **S1** (all four agents wire, planted CLI logs import to exact rows, doctor exits 0), **S2** (extension-format logs import with hooks unwired, re-import byte-identical via the cursor), **S8** (six derived views byte-identical across runs, and `CAGE_DEBUG=1` changes no derived output), plus a counts-never-content PII grep of everything the ledger wrote. S3–S7 render `PENDING` with the phase that ships them (P1–P4); live-agent steps print as an explicit `MANUAL` checklist, never silently skipped. Exits 1 on any failure and keeps the sandbox for inspection; cleans up on success.

Built from: [handoff](docs/archive/v0.16-cost-impact-roadmap.handoff.md) · [prompt](docs/archive/v0.16-cost-impact-roadmap.prompt.md) · validation: [dummy-repo](docs/archive/v0.16-dummy-repo-test.handoff.md) · [test run record](docs/archive/v0.16-full-test-run.md)

## v0.15.2 — Fable 5 / Mythos 5 pricing + two doc/interpolation papercuts

A second validation-pass batch, found by re-testing v0.15.1 against a real cross-project ledger. Additive; fail-open preserved; +1 regression test (suite 317→318).

- **`claude-fable-5` and `claude-mythos-5` now priced.** Real Fable 5 usage was costing out at **$0** with an `⚠ UNPRICED` warning: `claude-fable-5` shares only the `claude` segment with the opus/sonnet/haiku rows (< 2 segments), so `policy.price_match`'s family fallback can't reach it — it needs its own exact row. Added `[prices.anthropic."claude-fable-5"]` and `[prices.anthropic."claude-mythos-5"]` at **$10 / $50 per MTok, $1 cache-read** (Anthropic's published Fable/Mythos tier). A regression test pins that the bundled policy prices both exactly.

- **`cage query overview` / `data-flow` show the real on-disk paths.** The concept text interpolated the legacy unpartitioned `calls.jsonl` / `receipts.jsonl`, but the ledger is month-partitioned — that single file doesn't exist on a fresh ledger. It now shows the shard glob `calls-*.jsonl` / `receipts-*.jsonl`, matching what's actually on disk.

- **Test-plan doc drift corrected.** `docs/archive/v0.16-dummy-repo-test.plan.md` §5 listed `cage report --html PATH` (no such flag — the HTML surface is `cage serve`) and `cage export --json` as a stand-in for the summary; both lines now match the real CLI (`cage export --json` is a first-class alias as of v0.15.1).

## v0.15.1 — validation-pass fixes (concurrent-import dedup + three CLI/setup papercuts)

Fixes surfaced by an end-to-end validation pass on a disposable repo. All additive: no `CALL_FIELDS`/`make_call` change, no ledger rewrite, fail-open contract preserved. +6 regression tests (`tests/test_validation_fixes.py`), one per finding.

- **Concurrent-import double-count closed (the one real correctness bug).** Two capture sweeps racing on the same ledger — a Stop hook and a SessionStart sweep firing at once — could *both* snapshot the `seen` id-set before either appended, landing one turn twice (observed: an identical `call_id` written twice, doubling that call in `cage report`). `importcmd.run` now holds an exclusive `flock` on `.cage/state/import.lock` across the read-check-append section, so the second sweep rebuilds `seen` only after the first commits and `hooks.append_new`'s id-dedupe catches it. **Fail-open**: no `fcntl` (Windows) or an unwritable state dir ⇒ the lock is a no-op and the id-dedupe stays the backstop, exactly as before. Sequential re-import was already idempotent; this closes the concurrent window.

- **`cage demo` is now idempotent.** Re-running `cage demo` used to append a *second* §4.4 worked example onto the same ledger, doubling `cage attrib`/`cage matrix` totals (82,800 tok vs the canonical 41,400). `demo.seed` now returns the existing call id and appends nothing when the demo task is already present — the tables reproduce §4.4 exactly however many times it runs.

- **`cage setup --project-only` scaffolds standalone.** Its `--help` promises "scaffold `.cage/` + graphify + PATH only", but with no agent flag it fell through to the "pick an agent" wiring path and no-op'd (scaffolding nothing). It now runs the agent-independent scaffold (`adoptcmd.run(..., surfaces=None)`) and stops; wiring an agent stays the separate, explicit `cage setup --wire-only --<agent>` step.

- **`cage export --json` added as an alias for `--format json`.** `cage report --json` worked but `cage export --json` errored with `unrecognized arguments`; the export summary is now reachable by the same flag both commands share.

## v0.15.0 — meter dedup correctness + `cage limits` (Codex quota + estimated AI-credits)

Two gaps closed, scoped tightly per a devil's-advocate/pre-mortem debate: a meter dedup correctness fix, and a new `cage limits` view for provider quota + token-derived **estimated** credits. Every credit/quota figure is labelled `estimated`, sourced, and reconcilable — a shape-mismatch yields *nothing*, never a wrong number. **Additive: no `CALL_FIELDS`/`make_call` change, no ledger rewrite, no new ledger substrate.**

- **Dedup correctness (defensive — disproven in practice, still landed).** `transcript._usage_to_row` no longer passes `call_id=None` for a Claude turn with no `uuid`; it derives a *deterministic* id from `(agent, session, model, tokens_in, tokens_out, cached_in, ts)` so a re-import dedupes in `hooks.append_new` instead of minting a random id each run. **Reproduce-first finding:** across 29,714 usage-bearing Claude turns in real transcripts, **zero** lacked a `uuid` — so this is a defensive close of the one random-id path, not a corrective fix. **uuid-present rows render byte-identical to before** (test-asserted). Old random-id duplicates already in a ledger are not healed by this change (a `--dedupe` compaction is a possible follow-on).

- **`cage limits` — provider quota + estimated AI-credits.** A new read view showing, per agent: Codex rate-limit windows (`remaining_pct` + reset time + snapshot age) and **estimated** AI-credit consumption (tokens × a per-model multiplier) for token-based providers only. Every figure is tagged `estimated`, names its source, and ends with a "reconcile against your provider dashboard" note. Kiro/Copilot credit numbers are **not** fabricated from tokens (units-of-work ≠ token multiples) — they show "—".

- **Codex quota is a latest-only state snapshot, NOT a ledger substrate.** `transcript._codex_rate_limits` reads the `rate_limits` block Codex already writes (probed against a real rollout: it's a *sibling* of `payload.info`, with `primary`/`secondary` windows — observed `10080`=weekly and `43200`=monthly, labels derived from `window_minutes`, not assumed). `limits.snapshot_codex` (called fail-open from `import_codex`) persists only the **latest** snapshot per `(agent, window)` to a machine-local `.cage/state/limits.json` — overwritten not appended, **never synced to refs/notes**. A renamed/missing block writes nothing, no error.

- **Credits multipliers ship OFF by default.** `[credits.<provider>."<model>"] per_mtok = N` in `policy.toml` (economics layer) drives a single tokens→credits dispatch (`credits.py`, mirroring `convert.saved_usd`). No active rows ship — only a commented example — because a wrong credit number is worse than none and the precise per-token rates aren't published; turn it on by setting `per_mtok` from your provider dashboard. Exact model-id match only (no family fallback — a borrowed estimate is a different wrong number); unknown multiplier ⇒ tokens only.

- **`cage.v1` JSON envelope.** `cage limits --json` emits a versioned `{"schemaVersion":"cage.v1","generatedAt":…,"command":…,"data":…}` envelope (one helper in `render.py`); `generatedAt` is wall-clock metadata, the `data` payload stays deterministic. Introduced here for `limits` only — a wider rollout is a separate packet.

No schema/contract (`CALL_FIELDS`/`make_call`), MCP tool contract, attribution/provenance engine, or `cage verify` exit-0 behavior changed. The dedup change is additive (id derivation only); quota/credits live outside the ledger entirely. 312 tests pass (was 299).

## v0.14.0 — typed CLI errors + a documented exit-code contract (fail-open preserved)

cage's error handling was already mature — ~64 fail-open markers on write paths, every broad `except` carrying a `# noqa: BLE001 — <reason>`, hooks all `try/except → exit 0`, and `main()` already mapping `KeyboardInterrupt → 130`. The one real gap: `main()` had no typed/expected-error path, so an expected failure (a malformed `policy.toml`) or any unexpected exception dumped a raw traceback. This release closes that gap — **additive and boundary-only; not one fail-open block was rewritten.**

- **One typed error.** New `cage/errors.py` = a thin `CageError(Exception)` (no hierarchy, no logging framework, no retries — stdlib only). It is for surfacing an expected, user-facing failure at the read/CLI boundary; it is never raised on a fail-open write path.

- **`cli.main()` renders cleanly.** Keeping `KeyboardInterrupt → 130`, it now maps `CageError → "error: <msg>"` + exit 1 (no traceback — it's an expected failure), and any other unexpected exception → terse `error: <msg>` + exit 1 with the **full traceback only under `CAGE_DEBUG=1`** (reusing the existing switch — no new env var).

- **Exit-code contract, documented + tested.** `0` ok · `1` error (`CageError`/unexpected) · `2` argparse usage error (stdlib default — e.g. an unknown subcommand) · `130` interrupted. `cage verify` stays report-only **exit 0** (never a build gate), unchanged.

- **One leak converted.** A malformed project `policy.toml` hit by a read command now surfaces as `error: policy.toml: <parse error>` (exit 1) instead of a `tomllib.TOMLDecodeError` traceback — converted at the single `_policy()` read chokepoint, leaving the policy layer itself untouched. `cage query <unknown>` and `cage why <bad-id>` were already clean; bad `--since`/`--scope` keep their existing exit-0 "no filter" behavior (no behavior change).

- **Fail-open verified, not rewritten.** New tests prove a forced internal error in `ledger.append` / `metering.meter` / the Stop hook never propagates, and that the swallow is reachable via `debuglog` (not truly silent). The audit found exactly one genuinely-silent broad swallow — `meter`'s cleanup — and it gets an **ADD-only** `CAGE_DEBUG` trace (the same pattern `hooks.py` already uses), fully guarded so the metered call's no-raise guarantee stays absolute. The MCP boundary was already crash-proof (`isError` on any tool error, malformed JSON lines skipped); tests now lock that in. 299 tests pass (was 284).

No schema/contract, MCP tool contract, metering/ledger/attribution/provenance engine logic, policy/constants layers, or four-agents wiring changed — only error *surfacing* at the boundary. MCP contract docs: N/A (behavior on malformed input is clarified, not changed). (This release also folds in the docs-only scrub of graphify from cage's marketing/lineage prose — code, the graphify meter/shim, and the worked example are unchanged.)

## v0.13.0 — skillgen: the flagship `cage` skill is rendered from one source

cage shipped the same flagship `cage` pitch four ways — a Claude/Codex slash-command `SKILL.md`, a Copilot `.prompt.md`, and a Kiro steering doc — hand-authored and free to drift. This release single-sources them.

- **`tools/skillgen/` (build-time, stdlib-only, never shipped).** A ~250-line renderer (`tomllib`/`re`/`pathlib`/`argparse` only — no runtime dependency, no LLM, no network) reads `fragments/core/core.md` plus a handful of per-host slots (frontmatter, header, intro framing, metering note) declared in `platforms.toml`, and renders every host's committed asset. `python -m tools.skillgen` renders, `--check` byte-diffs the render against both the committed files and `expected/` (exit 1 on drift), `--bless` refreshes `expected/`. Nothing under `tools/skillgen/` is imported by the `cage` package at runtime or packaged in the wheel (`[tool.setuptools.packages.find] include=["cage*"]` already excludes it; a test asserts it).

- **Five hosts, four sacred agents preserved.** Renders to the existing source paths so `cage setup` / `<agent>wire.py` keep working unchanged: `cage/data/skills/cage/SKILL.md` (Claude **and** Codex — they share one file, rendered byte-identical and asserted), `cage/data/prompts/cage.prompt.md` (Copilot), `cage/data/steering/cage.md` (Kiro), plus a **new** generic `cage/data/skills/agents/cage/SKILL.md` (Agent Skills) target to prove breadth. The four-agents invariant is test-asserted; editing one shared line in `core.md` updates every host in a single `--bless`.

- **Normalized shared body.** The three structurally-different wrappers (the Claude numbered runbook vs. the Copilot/Kiro bullet lists) now share one command block (`report`/`attrib`/`roi`/`matrix`/`budget`/`why`, `--json`) and one counts-never-content / PII-safe clause; only the frontmatter shape, header, intro framing, and metering note differ per host. Each host's `description` (its firing trigger) is preserved **verbatim** from `platforms.toml`.

- **Drift guard wired in.** `python -m tools.skillgen --check` runs in the `Python package` CI job and as a local `pre-commit` hook (`.pre-commit-config.yaml`). New tests (`tests/test_skillgen.py`) cover byte-determinism, all five hosts + the four sacred agents, per-host anchor lines, no surviving `@@` slot, `--check` clean/drift, the shared-path byte-identity guard, and wheel exclusion — 284 tests pass (was 262).

No schema/contract, MCP, metering/ledger/attribution/provenance, or `cage setup` behavior changed — only the *source* of the (reviewed-at-the-bless-gate) skill assets, plus the new generic `agents` asset. Design of record: [docs/skillgen.md](docs/skillgen.md).

## v0.12.1 — green CI: tests no longer depend on ambient git identity or pathlib internals

A bug-fix release: the `Python package` workflow was red on `main` (the publish workflow was unaffected — releases still shipped). Three `tests/test_ledger_scale.py` cases passed locally but failed on the CI matrix because they leaned on the developer's environment rather than asserting the contract:

- **Git-notes writes assumed a global git identity.** `test_ledger_sync_writes_under_env` and `test_team_read_uses_merged_ref` drive `ledgersync.sync(..., write=True)`, which shells `git notes add` through production's env-less `_git`. A dev machine has a global `user.email`/`user.name`; a CI runner has none, so the write failed and `wrote` came back `False`. The shared `_git_init` helper now pins identity **on the repo itself** (`git config user.email/user.name`), matching how CI configures the sole-writer — the tests are hermetic instead of borrowing ambient config.

- **A size-warning test clobbered global `pathlib.Path.stat`.** `test_size_warning_swallows_stat_error` monkeypatched `Path.stat` to raise, intending to prove the ledger-size byte-sum never breaks a read. On 3.14 `Path.exists()` doesn't route through `Path.stat`, so it passed; on the CI 3.11/3.12 it does, so the `OSError` escaped `ledger.read()`'s own `exists()` check (which the warning's try/except never covered) — and the wrong `boom()` signature even crashed pytest's traceback formatter. The byte-sum is now a discrete `ledger._shard_bytes(shards)` helper; the test patches *that* (version-independent), asserting the real contract: even a total failure to size the shards never perturbs the read.

No behavior change to any shipped surface — counts-never-content, determinism, and the $0/stdlib-only invariants are untouched; 262 tests pass across Python 3.11–3.13.

## v0.12.0 — universal capture: global ledger + explicit `import`/`export`

Capture was hook-led and project-local, and in the field that left whole classes of users uncaptured: hooks are client-specific and mostly don't fire (a VS Code extension never runs `.codex/hooks.json` / `.kiro/hooks/*.hook` / `~/.copilot/hooks` — only Claude Code's extension honors its hooks), and the importer no-oped outside a project `.cage/`. A Copilot-only user, or anyone in a VS Code extension, could run for days with an empty ledger and a `cage doctor` that cheerfully reported their unfireable hook as "capture wired." This release makes capture **pull-based and universal** — `cage import` (capture) and `cage export` (import-then-emit) are the canonical verbs over a **global ledger**, hooks are demoted to an optional real-time add-on, and **cage installs nothing in the background**.

**Global ledger + resolution.** One active sink per run, resolved `--ledger`/`CAGE_BASE` → nearest project `.cage/` from cwd → global `~/.cage` (`paths.resolve_root`/`active_ledger_source`). The global ledger mirrors a project `.cage/` (its own `ledger/`, `state/`, `policy.toml`), is month-partitioned like any other, and is created on first write or by **`cage setup --global`**. A user with no project now captures into `~/.cage` instead of getting a no-op; a hook firing in a random dir lands in the global ledger rather than scattering a stray local `.cage/` (the resolver prevents scatter, so the old cwd-`.cage` guard is gone). `--ledger DIR` re-bases the whole footprint via `CAGE_BASE`; the legacy `CAGE_LEDGER` (a ledger-*dir* override, e.g. Orff's elgar store) keeps its meaning, honored independently.

**`cage export`** runs import first (unless `--no-import`), prints `↻ imported N new call(s)` to stderr, then emits the active ledger: `--format jsonl` (raw rows, lossless/re-ingestable — the default), `csv` (flat, stdlib `csv`), or `json` (a structured summary whose totals match `cage report`). Honors `--since`/`--project`/`--agent` and `-o FILE` (else stdout). Counts-never-content (no prompt bodies); deterministic byte-identical output for the same `--since` window (rows emitted in ledger order); an empty ledger still yields a valid artifact (csv header / zero-total summary / no jsonl lines), never a crash.

**`project` field (the derived attribution axis).** An additive optional `project` field on the call record (empty = legacy contract, basename-only — the same PII guard as `scope`, which is untouched). Stamped on Claude imports from the transcript's `cwd` basename; Copilot/Kiro/Codex logs carry no cwd, so it stays empty for them (a named follow-up). `cage report --project <name>` (or `--project .`/bare = current dir) slices the global ledger to a project view — exact for Claude, and the output says so when other agents' projectless rows are excluded. Per-project *capture* is impossible for the non-Claude agents, so project is only ever a derived *view*, never a capture scope.

**`cage watch`** is an optional **foreground** poll loop: import every `--interval` seconds until Ctrl-C, a plain stdlib `sleep` (no filesystem-watch dependency). It registers nothing and stops with the terminal — **cage installs no OS scheduler** (no launchd/systemd/cron/schtasks, no `cage scheduler` command). Hands-off automation, if wanted, is the user's own cron line calling `cage import`, which `cage doctor` may mention but never creates.

**Incremental import (scale).** With no daemon, manual `cage import`, `export`'s refresh, and the `watch` loop are the hot paths; re-parsing every transcript and reloading the whole 22k+-row ledger per run is O(all logs × ledger). A per-agent high-water **cursor** (`.cage/state/cursors.json`, last-seen `(size, mtime)` per source file) skips unchanged files before parsing, and the ledger `seen` set is built once per run and shared across agents (`hooks.append_new` gained an optional shared `seen`); id-dedupe stays the correctness backstop. The cursor also stamps `_last_import`, surfaced as "last import: N ago".

**Honest `cage doctor`.** Infers each agent's capture state from the debug heartbeat (fired recently ⇒ real-time active; never ⇒ a *wired* hook is not a *firing* one — warns it won't fire under a VS Code extension); names the active ledger sink, shows "last import: N ago", and points at `cage import`/`cage export` as the universal path. No hook is labelled "capture wired"; there is no scheduler row.

Fail-open hardening on the capture path: a malformed `policy.toml` (e.g. a duplicate `[debug]` table that makes `tomllib` raise) now degrades to the bundled default with a recorded debug event, never a traceback. The substrate change is limited to the one additive `project` field (plan §3.1, §3.7); the attribution/matrix math and the §4.4 demo numbers are unchanged. 262 tests passing. See [docs/debugging-capture.md](docs/debugging-capture.md).

## v0.11.0 — observable capture (`CAGE_DEBUG`): per-hook heartbeat + recorded tracebacks

The capture path is fail-open and silent *everywhere* — every hook entrypoint and import wraps its work in `except Exception: pass`, and the skip-reason strings `importcmd.run` returns are discarded when a hook calls it (hook stdout goes nowhere). In the field this meant capture could silently do nothing for days across all four agents with no way to tell whether a hook even fired, whether the `.cage` cwd guard skipped it, or whether a parser raised — we diagnosed it only by hand-instrumenting hooks with marker files. This release bakes that observability in permanently, **without changing capture**: it is strictly observational (a logging error is swallowed, the ledger is never touched, no hook is ever blocked), off by default, and metadata-only.

New `cage/debuglog.py` (stdlib, $0) writes one structured JSON line per capture event to `.cage/state/debug.log`, gated by `policy.debug_enabled` — env `CAGE_DEBUG=1` overrides `policy.toml [debug] enabled` (default **off**). When off, no file is written and the only added cost is one tiny policy read per hook firing; **the ledger is byte-identical with debug on or off** (the log is local state, never read by a derived view, so determinism holds). It records agent, event, cwd, resolved root, `.cage` present?, capture-enabled?, `transcript_path` *presence* (a bool, never contents), files scanned, rows parsed/appended/deduped, the exact skip reason, and — the core fix — every previously-swallowed exception's **type + traceback** instead of letting it vanish. Counts-never-content still holds: no prompt/response bodies, no token text.

Every hook entrypoint (`session_start`/`stop`/`session_end`/`post_tool_use`/`post_commit`) and the umbrella `importcmd.run` + each adapter (`import_claude`/`codex`/`copilot`/`kiro`) is instrumented, so all four agents are first-class. Each firing also stamps a **per-`(agent,event)` heartbeat** to `.cage/state/hooks-seen.jsonl` (append-only, last-write-wins on read), which finally answers "did this agent's hook ever fire?" without manual marker files. `cage doctor` gains a `trace` row: with debug off it says how to turn it on; with debug on it shows, per agent, the last hook fired (event + how long ago, or `never fired`) plus the last skip/error. New `cage debug [--tail N]` prints recent events. Skips are recorded with stable, greppable codes — `skip=no-cage`, `skip=capture-disabled`, `skip=since-filtered` (the last fires when `--since` dropped every candidate file, a common "why is nothing captured?" cause). To observe a hook firing in a dir that has no `.cage/`, point `CAGE_DEBUG_LOG` at a fixed file — debug logging never *creates* a `.cage/` footprint (which `find_project_root` would then mistake for a project). Enable with `CAGE_DEBUG=1`; see [docs/debugging-capture.md](docs/debugging-capture.md) (and the short section in `docs/agents.md`).

Also in this release: **`cage` exits cleanly on Ctrl-C** instead of dumping a `KeyboardInterrupt` traceback — aborting the `cage setup` wizard (or any command) now prints `aborted.` and returns 130.

## v0.10.2 — Kiro hook format fixed (it never fired before)

Kiro's Agent Hook file is **one hook per file** — the file *is* the hook object (`{name, version, description, when:{type}, then:{type, command}}`), not the `{"version":"v1","hooks":[…]}` container with `trigger`/`action` keys that Cage was writing. That wrong shape (plus a `SessionStart` trigger **Kiro doesn't have** — its events are `agentStop`/`promptSubmit`/`pre|postToolUse`/`file*`/`pre|postTaskExecution`/manual) meant the Kiro hook silently never ran. `cage setup` now writes a single **`agentStop`** hook in the correct format; because each fire re-imports Kiro's whole usage log (deduped by call id), that one hook is both the real-time and the backfill path — the next turn covers anything the prior one missed (the same self-backfilling pattern Copilot uses). The file is cage-owned, so re-running setup overwrites it wholesale and heals any old-format install. Re-run `cage setup --wire-only` to pick up the working hook.

## v0.10.1 — release process codified: GitHub release is the publish trigger, never publish from local

Releases now ship a **GitHub release**, and the GitHub release *is* the PyPI publish: creating it fires `.github/workflows/publish.yml` (`on: release: published`), which builds and uploads via **OIDC trusted publishing** (no stored token, nothing to leak). The one true flow — bump `__version__` + changelog, push `main`, tag `vX.Y.Z`, push the tag, `gh release create vX.Y.Z` — is now a durable rule in `CLAUDE.md`. **No more `uv publish`/`twine` from a laptop;** CI is the sole publisher (`skip-existing: true` keeps it idempotent). A version on PyPI with no matching GitHub release/tag is a release bug.

## v0.10.0 — real-time per-turn capture (Stop hook), repo-level skills, `state/` gitignored

Claude Code **and Codex** spend now lands *as each turn ends*, not only when you open the next chat. For Claude, `cage setup` wires a **Stop** hook (`cage hook-stop`) that imports the just-finished turn from the live transcript; for Codex it wires a turn-scoped **Stop** hook in `.codex/hooks.json` that re-imports the rollouts Codex writes to disk. Both are idempotent (deduped by call id / turn uuid), so they stack safely on top of the SessionStart-backfill safety net and (Claude) the best-effort SessionEnd. Before this, the only reliable trigger was the *next* session's SessionStart-backfill, so a session's tokens stayed "pending" until you started a new chat. `cage doctor`'s metering matrix now shows `real-time Stop + backfill ✔` for both log-bearing agents.

**Copilot CLI is now metered too** — it persists a per-session usage log (`~/.copilot/session-state/*/events.jsonl`, whose `session.shutdown` event carries `modelMetrics`), so `cage import --agent copilot` records its spend (per-model usage nests under `modelMetrics.<model>.usage`; on this machine Copilot runs `claude-haiku-4.5`) and `cage setup` wires `agentStop`/`sessionStart`/`sessionEnd` hooks at the **user level** (`~/.copilot/hooks/cage.json` — verified the only location the local CLI fires from; repo `.github/hooks/` does not fire even when committed), moving Copilot off proxy-only onto a real import path. Because Copilot writes its `session.shutdown` (the usage) *after* its own hooks fire, a session's tokens land on the **next** Copilot run — its `sessionStart`/`agentStop` import picks up the prior session's shutdown (the standard backfill pattern; cage never sweeps another agent's data from a hook).

**Kiro is now metered too, completing the four-agent set** — Kiro persists a coarse usage log (`kiro.kiroagent/dev_data/tokens_generated.jsonl`: one object per call, prompt tokens reliable, output often 0, model the generic `"agent"`) and supports Agent Hooks, so `cage setup` wires a real-time **Stop** Agent Hook (`.kiro/hooks/cage.kiro.hook` → `cage import --agent kiro`) and `cage import --agent kiro` records it. With this, **every surface in `agents.SURFACES` is now log-bearing** — none is proxy-only. And the hook coverage is now **symmetric across all four**: each agent gets both a real-time per-turn hook (Claude/Codex/Kiro `Stop`, Copilot `agentStop`) *and* a SessionStart-style backfill safety net, so `cage doctor`'s matrix reads `real-time Stop + backfill ✔` for every one.

**Hooks and MCP servers are now wired with the *resolved absolute* `cage` path, not a bare `cage`** — GUI-launched agents (the Kiro IDE, the Copilot extension, a Codex app) run hooks with a minimal PATH that omits `~/.local/bin`, so a bare `cage` failed silently with "command not found" and nothing was captured (only Claude Code, terminal-launched, worked). `cage setup` now resolves the binary at wire time and **heals** an existing bare-`cage` install in place (no duplicate entries) — re-run `cage setup` once to upgrade.

**Each agent's hook imports only its own log** (`cage import --agent <itself>`) — cage never sweeps another agent's data from a hook, so capture stays scoped and predictable (re-running setup migrates any older all-agent-sweep command back to the per-agent import). The `cage setup` wizard now **defaults to setting up *all* agents** (`cage setup --all` non-interactively) rather than making you pick one — wiring every agent is a single step. Internally, agent wiring is now **one `<agent>wire.py` per agent** (`claudewire`/`codexwire`/`copilotwire`/`kirowire`, each exposing `install`/`status`/`backfill_status`/`realtime_status`), dispatched from `agents.py` — a standing convention so integrating a new agent means adding one wire file, nothing more.

Finally, a **consumer on/off switch for auto-capture**: `[capture] enabled = false` in `policy.toml` (or `CAGE_CAPTURE=0`, which overrides policy) makes the hook-driven `cage import` a no-op — pause metering without unwiring any hooks; `CAGE_CAPTURE=1` forces it back on for a single run. The proxy stays the higher-fidelity fallback where Kiro's log is too thin.

**Pricing refreshed for all four agents' models** — the bundled `policy.toml` now carries current Anthropic rates (Opus 4.8 corrected from a stale $15/$75 to $5/$25; Sonnet 4.6, Haiku 4.5) for Claude Code + Kiro, and the OpenAI `gpt-5` family (`gpt-5`, `gpt-5-mini`, `gpt-5.5`, `gpt-5.4`, `gpt-5.3-codex`) for Codex + Copilot, so their traffic costs out instead of reading `UNPRICED`. Two Codex metering bugs fixed in the same pass: the model id (declared once in a `turn_context` record) is now carried onto the usage events instead of coming through empty, and per-turn usage reads `last_token_usage` instead of summing the cumulative `total_token_usage` — which had inflated a real ~12M-token session to a bogus 210M.

**The /cage skill can now be installed repo-level instead of machine-wide** — `cage setup --repo-skill` (or pick "project" in the wizard) writes the skill into the repo (`.claude/skills/`, `.codex/skills/`, `.github/prompts/`, `.kiro/steering/`) so it's committed and the whole team gets it, with nothing in your home dir; global stays the default. Also: the `.cage/.gitignore` now excludes `state/` (machine-local hook buffers — pending edits, session state), and `cage init`/`cage setup` heals older footprints that were missing it. Re-run `cage setup --wire-only` in an existing project to pick up the Stop hook.

## v0.9.0 — ledger scale: partitions, scope, team aggregation

The ledger now survives heavy/multi-dev/monorepo use. Writers append to month-partitioned shards (`calls-YYYY-MM.jsonl`, same for receipts/tasks) chosen from each row's own `ts`; readers glob + concatenate (legacy single files still read), and `--since` skips whole below-cutoff months instead of re-scanning a year. Calls/receipts carry an optional counts-safe `scope` (top-level changed dir, same PII guard as tasks); `report`/`attrib`/`budget`/`matrix --scope <dir>` slice a monorepo component (no flag ⇒ byte-identical). `cage ledger-sync` distributes local rows into `refs/notes/cage-ledger` (dry-run by default, CI-sole-writer like `notes-sync`), and `report`/`attrib --team` read the merged team view (falling back to local when empty) — rolled up by `scope`, never per-person. A one-line stderr warning fires when the ledger crosses a derived size (≈2 heavy solo-years; `[ledger] warn_mb` overrides) — warn-only, never blocks a derive.

Also in this release: **reliable hookless capture is now the default** — `cage setup` wires a **SessionStart-backfill** for the two transcript agents (Claude Code's `.claude/settings.json` and Codex's `.codex/hooks.json`, which share a hook schema) that imports the *previous* session on the next start, ordered before the spend banner. SessionEnd stays wired but is best-effort (it never fires on a killed/crashed/idle session); running both is safe because `cage import` dedupes by call id. Copilot/Kiro have no transcript, so their reliable path stays the proxy. `cage doctor`'s metering matrix now names the mechanism actually wired per agent (SessionStart-backfill / SessionEnd / proxy) and flags any log-bearing agent left without a reliable trigger. All four agents stay first-class.

## v0.8.0 — one hookless front door for all four agents

`cage import [--agent claude|codex|copilot|kiro|all]` (default `all`) unifies hookless metering: Claude Code and Codex import the usage transcripts they write to disk, while Copilot and Kiro — which expose no usage log — print their supported proxy fallback (`cage meter -- <cmd>`) instead of being silently skipped. Additive to hooks/MCP and deduped by call id (a turn seen by both a hook and an import counts once); the old `import-claude`/`import-codex` stay as aliases. `cage doctor` now renders a four-agent metering matrix (hook / import / proxy per agent).

## v0.7.1 — docs + the four-agents invariant

README "What's new" and test counts brought current, and a durable rule recorded for every agent (`CLAUDE.md` + `AGENTS.md`): Cage keeps **Claude Code · Codex · Copilot · Kiro** first-class on every surface, and each release must update this changelog.

## v0.7.0 — one front door + hookless metering

`cage setup` is now the single onboarding command: `--project-only` (scaffold + graphify, no global skill), `--wire-only` (agent wiring only), and `--status` (report wiring) absorb the old `adopt`/`hooks` verbs, which are gone. Internal `hook-*` entrypoints are hidden from `--help`. Ships alongside hookless transcript metering (`cage import-claude`), a per-call pricing fallback, and the bare-`cage` spent-and-saved headline. All four agents (Claude Code · Codex · Copilot · Kiro) stay first-class.

## v0.6.0 — authorship attribution

`cage origin <sha>` answers *who wrote which files in which commit* — a fourth append-only record captured by a `PostToolUse` hook (transcript fallback), with `hooked`/`transcript`/`heuristic` method ranks and `human`/`agent`/`agent-autonomous` origins. `unknown` is read-derived from absence, never a stored row; `origin=human` only via explicit attestation. Distributed over `refs/notes/cage-provenance` (CI is the sole writer); `cage verify` is report-only and never gates the build.

## v0.5.0 — DX + concept explainers

A constants/query-help layer and `cage query` concept topics: ask *how cage works*, not just *how a number is computed*, all deterministic and `$0`.

## v0.3.0 — the Tier-1 human axis

`cage human` / `cage trend` price agent-vs-human in **dollars and hours**, anchored to a git-aware task record; a `minutes` unit, a `[human]` rate table with confidence laddering, and `CAGE_HUMAN_RATE`. Third-party tools join via the external adapter (`cage graphify`).

## v0.2.0 — attribution + the counterfactual matrix

Marginal-by-fixed-order attribution, the 2ⁿ permutation table, ROI per tool, and the `measured`/`modeled`/`estimated` discipline — the differentiator.

## v0.1.0 — substrate + meter

The call/receipt contract, the append-only ledger, `policy.toml`, and `cage report`.
