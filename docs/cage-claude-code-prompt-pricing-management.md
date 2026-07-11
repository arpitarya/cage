# Claude Code prompt: pricing management — unpriced workflow, prices CLI, policy versioning, fleet repricing

You are building cage's pricing-management surface: a `cage prices` command
group, bundled price rows for the models seen in the field (copilot-served
Claude models, `copilot/auto`, current OpenAI/Anthropic lineup), effort-tier
normalization, policy-file versioning with upgrade recommendation, and deep
`cage query` coverage for all of it. Run AFTER the current tree is
reviewed/committed (ask if dirty). **No commits, tags, pushes, publishes.**

## Context to load first

- `CLAUDE.md`; `cage/prices.py` (`call_usd_match`: `exact|family|self|none`) and
  `cage/policy.py` (`price`, `price_match`); `cage/data/policy.toml` (bundled
  rows + comments); `cage/report.py` (how UNPRICED renders); `cage/credits.py`
  (the premium-request layer — do NOT blur it into per-token prices);
  `cage/explain_data.py`; `cage/cfgio.py` (TOML write helpers if any);
  `cage/doctorcmd.py`; `tools/dummyrepo/run.py`.

## Field report driving this (from my real ledger)

`cage report` showed: `UNPRICED — counted as $0, add a price row to policy.toml`
for `anthropic/copilot/claude-opus-4.6`, `anthropic/copilot/claude-sonnet-4.6`,
and `copilot/auto`. Read the exact `(provider, model)` keys from the ledger —
don't trust my transcription; build `cage prices unpriced` first and use its
output.

## Task

**1. `cage prices` command group (project policy.toml is the write target;
bundled is never modified at runtime):**
- `cage prices list` — every price row visible to this project: bundled vs
  project origin, which wins, `[meta]` version/date of each (see §4).
- `cage prices unpriced` — scan the resolved ledger for `none`-match calls:
  distinct `(provider, model)`, call count, token volume, and the exact
  ready-to-run fix line for each (see example below).
- `cage prices set <provider> <model> --input <usd/Mtok> --output <usd/Mtok>
  [--cache-read <usd/Mtok>]` — idempotent insert-or-update of a project
  policy.toml row, validated (non-negative, cache_read ≤ input), printing the
  before/after row and a reminder that all derived views re-price immediately.
- `cage prices alias <provider> <model> --to <provider>/<model>` — explicit
  routing for router pseudo-models (`copilot/auto`): priced at the target row,
  match kind rendered as `alias→family-style footnote`, never a silent default.
- `cage prices sync` — compare project rows against the bundled table: adds
  missing rows, lists differing rows as a diff, `--update` applies bundled
  values over rows the user hasn't customized (see §4 for how "customized" is
  known); default is dry-run print (house pattern).
- Typed errors (`CageError`) at the CLI boundary; TOML writes preserve
  comments where feasible or document that project price rows live in a
  cage-managed block.

**2. Bundled price rows — research then populate.** Use web search against the
vendors' official pricing pages (Anthropic, OpenAI, GitHub Copilot docs) to get
CURRENT per-Mtok list prices — cite the source URL + retrieval date in a comment
above each row. Add/verify: the copilot-served rows for the Claude models the
field report names (at the underlying Anthropic API rate, with the bundled-file
comment stating this is an approximation of subscription billing — the honest
number for token-flow comparison, while `[credits.copilot]` remains the
premium-request layer); the current Anthropic lineup; the current OpenAI lineup
including `gpt-5.3-codex` (row exists — verify the rate) and any newer codex
variants; leave `copilot/auto` UNPRICED in the bundle but ship a commented-out
alias example — pricing a router silently is a wrong number.

**3. Effort tiers (`low|medium|high|max`).** Reasoning-effort variants change
token consumption (already measured), not unit price. Make family matching
normalize effort suffixes/segments and `.`↔`-` punctuation (`claude-sonnet-4.6`
must family-match a `claude-sonnet-4-6` row) so tier variants price at the base
row with the existing family footnote. Add tests for both normalizations. If a
provider's effort tiers are billed at genuinely different per-token rates
(verify while researching §2), give those tiers their own explicit rows instead
— never normalize away a real price difference.

**4. Policy versioning + upgrade recommendation.**
- Bundled `policy.toml` gains `[meta]`: `prices_version` (monotonic or date),
  `prices_date`, `cage_version`. `cage init` stamps the copied project policy
  with the bundled meta it derived from.
- `cage doctor` and `cage prices list` compare project meta vs the installed
  bundle: newer bundle ⇒ one-line recommendation: `bundled prices are newer
  (2026-07 > 2026-05) — run 'cage prices sync'`. Never auto-apply.
- "Customized" detection for `sync --update`: a project row differing from the
  bundled value of ITS recorded `prices_version` is user-customized (preserve);
  a row equal to its old bundled value is stale-bundled (safe to update). If
  the old bundle isn't reconstructable, fall back to listing the diff and
  requiring per-row confirmation. Keep it simple and honest over clever.

**5. Fleet/export repricing semantics — confirm, surface, document.** Pricing
is derive-time (`prices.call_usd` recomputes from tokens × policy), so an
analyst fixing policy.toml re-prices every imported bundle row retroactively —
the ledger stores counts, not conclusions. Make this visible: `cage report`,
`cage compare`, and `cage study report` print an UNPRICED summary line when
`none`-match calls exist (`⚠ 214 calls (1.2M tokens) UNPRICED — totals
understated; run 'cage prices unpriced'`) so a fleet analyst can't publish a
final number without seeing the gap. Caveat documented: `self`-costed rows
(stored `est_cost_usd`) and receipts' recorded values don't re-derive.

**6. Rider — export imports everything first.** `cage export` (plain and
`--study`) currently bundles whatever the ledger already holds; on a machine
where hooks don't fire (any VS Code extension), that silently omits every
session since the last manual `cage import`. Fix: export runs the same
all-agent sweep the hooks run (`paths.cage_import_all` semantics over the
resolved ledger) BEFORE bundling, so a capture-only user's single `cage export
--study` always ships a complete bundle.
- The sweep honors the capture switch (`CAGE_CAPTURE=0` / `[capture] enabled` ⇒
  skip the sweep, export what exists) and stays **fail-open**: a sweep error is
  debug-logged and export proceeds with the pre-sweep ledger — a broken parser
  must never block a fleet participant from sending their bundle.
- `--no-import` flag for a pure as-is snapshot.
- The bundle manifest records whether the sweep ran and how many rows it added
  (counts only) — so the analyst can see "this machine's export was self-
  refreshing" vs "snapshot only".
- Tests: plant fresh un-imported fixture log rows → `cage export` → bundle
  contains them; `--no-import` → it doesn't; sweep failure (unreadable log) →
  export still succeeds + debug line. Extend the dummyrepo fleet scenario so
  one simulated machine relies solely on export's sweep (no prior import) and
  the analyst's totals still come out exact.
- Docs: fleet section of the plan doc + README one-liner + a `cage query`
  concept note under the export/study entry ("export self-refreshes; use
  --no-import for a frozen snapshot").

**7. Rider — state auto-cleanup + policy toggles.** `.cage/state/` accumulates
files that never get pruned: `debug.log` / `hooks-seen.jsonl` grow unbounded,
per-session provenance edit buffers go stale when a session never commits,
cursors outlive deleted source logs, tmp/bundle leftovers linger. Add:
- **`[cleanup]` in policy.toml:** `enabled` (default `true`), `days` (default
  `30`), honored everywhere policy is; env `CAGE_CLEANUP` (0/1) overrides, the
  capture-switch pattern.
- **What may be cleaned (closed allowlist, by construction):** aged `debug.log`
  rotation (keep current, drop >`days`), `hooks-seen.jsonl` rows >`days`, stale
  pending provenance session buffers >`days` (their transcript fallback already
  ran at SessionEnd), cursors whose source path no longer exists, tmp files.
  **Never cleanable — enforced by the allowlist, not convention:** anything in
  `ledger/`, `policy.toml`, `outcomes.json`, the machine id (fleet pairing
  breaks without it), `study.jsonl`.
- **Auto path:** piggybacked on `cage import` / hook sweeps (cage installs no
  scheduler) — a cheap staleness check, then fail-open cleanup (an error is
  debug-logged, never blocks capture). Deleting a cursor is safe by design:
  the next import re-reads the whole log and the id dedupe absorbs it.
- **Manual path:** `cage cleanup` — dry-run print by default (house pattern),
  `--apply` to execute, listing each file, its age, and its class.
- **Determinism unaffected:** state files are never read by derived views;
  assert with a test (cleanup then byte-identical report/compare/verdict).
- **`[capture] import_before_export`** (default `true`) — the policy-level
  toggle for §6's sweep; `--no-import` still wins per-invocation. Precedence:
  flag > env > policy, documented in the query entry.
- `cage doctor` reports state-dir size + pending/stale counts so bloat is
  visible before it's a problem.
- Tests: each allowlist class ages out correctly; never-list survives an
  aggressive `days=0` run; dry-run touches nothing; auto path fail-open;
  `import_before_export=false` skips the sweep and the manifest says so.

**8. `cage query` — deep coverage.** New/extended entries, all interpolating
LIVE values (rates from the resolved policy, match counts from the ledger where
cheap): calculation entries for `pricing-match` (exact→family→alias→self→none,
with this project's actual row count), `unpriced` (what $0 means, the fix
workflow), `repricing` (derive-time semantics, the fleet answer from §5);
concept entries for `prices-cli` (each subcommand + the §1 example), the
research workflow (how to find a price: vendor pricing page or a web search for
"<vendor> <model> API pricing", then `cage prices set ...` — cage itself never
fetches, network stays off the read path), `effort-tiers`, `policy-versioning`
(meta, sync, when to run it), the copilot-approximation caveat, plus `cleanup`
(what's cleanable vs never-cleanable, the `[cleanup]` props, why the ledger is
untouchable) and `import-before-export` (the §6/§7 toggles, flag > env > policy
precedence). Wire the UNPRICED report line to point at `cage query unpriced`.

**Worked example (must appear in README pricing section, the bundled policy
comments, and the `prices-cli` query entry):**
```
$ cage prices unpriced
  copilot/claude-sonnet-4.6   38 calls   412k tokens
    fix: cage prices set copilot claude-sonnet-4.6 --input 3.00 --output 15.00 --cache-read 0.30
  copilot/auto                 7 calls    51k tokens
    fix: cage prices alias copilot auto --to copilot/claude-sonnet-4.6
$ cage prices set copilot claude-sonnet-4.6 --input 3.00 --output 15.00 --cache-read 0.30
  [prices.copilot."claude-sonnet-4.6"] written to .cage/policy.toml — derived views re-price immediately
```
(Replace the illustrative rates with the researched real ones.)

## Required workflow

Explore → plan (files touched, pause for confirmation) → implement
incrementally → docs (README pricing section, CHANGELOG in-tree, plan-doc note,
CLAUDE.md proposed-not-applied, skillgen fragments regenerated + `--bless`) →
verify: `just test`, dummyrepo scenario **S11** (seed unpriced calls → `prices
unpriced` exact output → `set` + `alias` → report re-prices to exact expected
USD → sync recommendation appears when meta is older), determinism double-runs,
skillgen `--check`.

## Constraints (hard)

- $0/stdlib; **no network on any cage code path** — web research is YOUR
  build-time task, its results land as static bundled rows with source
  comments.
- Determinism; `method` sacred (family/alias matches keep their footnote —
  never render as exact); fail-open write path untouched; `CageError` reads;
  four agents; additive-only; never rewrite the ledger.
- Bundled policy is read-only at runtime; all runtime writes go to the project
  policy.toml; `prices set` must be idempotent and re-runnable.
- Credits stay separate from prices (a Copilot premium-request multiplier is
  not a per-token rate — don't merge the layers).
- A wrong number is worse than none: no silent default for `auto`/unknown
  routers; unpriced stays loudly unpriced until the user acts.
- No commits; working tree only.

## Acceptance criteria (self-check)

- [ ] `prices list/unpriced/set/alias/sync` all working, typed-error clean,
      idempotent; the field report's three keys price correctly end-to-end on a
      seeded ledger.
- [ ] Bundled rows updated with cited current prices; copilot approximation
      + auto-alias example documented in the file itself.
- [ ] Effort-tier + punctuation normalization tested; real per-tier price
      differences (if any) get explicit rows.
- [ ] `[meta]` versioning + sync recommendation in doctor and prices list;
      user-customized rows never clobbered.
- [ ] UNPRICED summary line in report/compare/study report; repricing semantics
      documented + query-answerable.
- [ ] Export self-refreshes (sweep-then-bundle), `--no-import` and
      `[capture] import_before_export` both work with documented precedence,
      sweep is fail-open, manifest records sweep counts; fleet scenario with an
      import-never machine comes out exact.
- [ ] Cleanup: allowlist classes age out, never-list survives `days=0`,
      dry-run default, auto path piggybacked + fail-open, doctor shows state
      size, determinism unaffected by cleanup (tested).
- [ ] `cage query` answers every §8 topic with live values; S11 green;
      `just test` green; skillgen clean; zero commits.
