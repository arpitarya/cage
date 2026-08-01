# Archive — shipped handoffs, prompts, and superseded drafts

**History, not spec. The living design of record is in `docs/` root and [`docs/cage-plan.md`](../cage-plan.md).**

Every file here drove work that has since been **implemented** (or was superseded).
Files keep their original text verbatim plus a one-line archive header; names sort
by the release that carries the work: `vX.Y-<feature>.{handoff,prompt}.md`.

**Archive trigger is implementation, not release** (rule amended 2026-07-25): a pair
moves here once its work is built and green, tagged with the version it rides. The
v0.36 pairs were archived while that release was still pending — their header says
so. This keeps `docs/` root as a true list of *work not yet done*.

## 2026-07-28 — the v0.36 consolidation

The whole v0.36 cycle (24 files: import-ledger · cage-lab · capture-precision ·
golden-set · phase1-closeout · report-per-run · graphify-ab-steering ·
graphify-capture, plus their handoffs and prompts) was archived in one sweep and
replaced by a single living plan, **[`docs/OPEN-WORK.md`](../OPEN-WORK.md)**.

Each archived file carries the standard header naming what was built and where its
*pending* remainder went. Durable rules from those plans were **promoted into
OPEN-WORK.md** rather than left here — the archive stays history, never spec.

**Those 24 files are indexed by this section, deliberately, not by rows in the table
below** — they were one sweep with one outcome (replaced by `OPEN-WORK.md`), and 24
near-identical rows would bury the pairs that carry distinct work. Everything archived
*after* 2026-07-28 gets its own row. If you are looking for a v0.36 cycle plan
(import-ledger · cage-lab · capture-precision · golden-set · phase1-closeout ·
report-per-run · graphify-ab-steering · graphify-capture), it is here on disk with its
header intact.

## Handoff / prompt pairs by release

| Version | Feature | Handoff | Prompt | CHANGELOG |
| ------- | ------- | ------- | ------ | --------- |
| v0.3 | Tier-1 human baseline | — | [prompt](v0.3-human-baseline.prompt.md) | [v0.3.0](../../CHANGELOG.md#v030--the-tier-1-human-axis) |
| v0.3 | graphify/fux savings receipts | [handoff](v0.3-tool-receipts-graphify-fux.handoff.md) | [prompt](v0.3-tool-receipts-graphify-fux.prompt.md) | [v0.3.0](../../CHANGELOG.md#v030--the-tier-1-human-axis) |
| v0.5 | Constants + query-help DX layer | [handoff](v0.5-dx-constants-query-help.handoff.md) | [prompt](v0.5-dx-constants-query-help.prompt.md) | [v0.5.0](../../CHANGELOG.md#v050--dx--concept-explainers) |
| v0.5 | `cage query` concept layer | [handoff](v0.5-cage-query-concepts.handoff.md) | [prompt](v0.5-cage-query-concepts.prompt.md) | [v0.5.0](../../CHANGELOG.md#v050--dx--concept-explainers) |
| v0.5 | Fix: Claude Code cost renders $0 | — | [prompt](v0.5-fix-cost-rendering.prompt.md) | [v0.5.0](../../CHANGELOG.md#v050--dx--concept-explainers) |
| v0.7 | CLI surface cleanup (`cage setup` front door) | [handoff](v0.7-cli-surface.handoff.md) | — | [v0.7.0](../../CHANGELOG.md#v070--one-front-door--hookless-metering) |
| v0.7 | `report` spent-and-saved + bare-`cage` banner | [handoff](v0.7-report-spent-and-saved.handoff.md) | — | [v0.7.0](../../CHANGELOG.md#v070--one-front-door--hookless-metering) |
| v0.7 | `cage import-claude` hookless metering | — | [prompt](v0.7-import-claude-hookless.prompt.md) | [v0.7.0](../../CHANGELOG.md#v070--one-front-door--hookless-metering) |
| v0.7 | Model-pricing family fallback | — | [prompt](v0.7-model-pricing-fallback.prompt.md) | [v0.7.0](../../CHANGELOG.md#v070--one-front-door--hookless-metering) |
| v0.8 | Unified hookless metering, all four agents | [handoff](v0.8-hookless-and-gateway.handoff.md) | [prompt](v0.8-unified-hookless-all-agents.prompt.md) · [impl](v0.8-implement-hookless-metering.prompt.md) · [kickoff](v0.8-kickoff-hookless-and-gateway.prompt.md) | [v0.8.0](../../CHANGELOG.md#v080--one-hookless-front-door-for-all-four-agents) |
| v0.8 | ELI5 `--help` + `cage query` examples | [handoff](v0.8-eli5-help-and-query.handoff.md) | [prompt](v0.8-eli5-help-and-query.prompt.md) | [v0.8.0](../../CHANGELOG.md#v080--one-hookless-front-door-for-all-four-agents) |
| v0.9 | Ledger scale (partitions · scope · team) | [handoff](v0.9-ledger-scale.handoff.md) | [prompt](v0.9-ledger-scale.prompt.md) | [v0.9.0](../../CHANGELOG.md#v090--ledger-scale-partitions-scope-team-aggregation) |
| v0.9 | Hookless backfill as the setup default | — | [prompt](v0.9-hookless-backfill-default.prompt.md) | [v0.9.0](../../CHANGELOG.md#v090--ledger-scale-partitions-scope-team-aggregation) |
| v0.11 | Capture observability (`CAGE_DEBUG`) | — | [prompt](v0.11-capture-debug-observability.prompt.md) | [v0.11.0](../../CHANGELOG.md#v0110--observable-capture-cage_debug-per-hook-heartbeat--recorded-tracebacks) |
| v0.12 | Universal capture (global ledger, import/export) | [handoff](v0.12-universal-capture.handoff.md) | [prompt](v0.12-universal-capture.prompt.md) | [v0.12.0](../../CHANGELOG.md#v0120--universal-capture-global-ledger--explicit-importexport) |
| v0.14 | Error handling (typed `CageError`, exit codes) | [handoff](v0.14-error-handling.handoff.md) | [prompt](v0.14-error-handling.prompt.md) | [v0.14.0](../../CHANGELOG.md#v0140--typed-cli-errors--a-documented-exit-code-contract-fail-open-preserved) |
| v0.15 | Meter dedup + Codex quota + `cage limits` | [handoff](v0.15-meter-quota-credits.handoff.md) | [prompt](v0.15-meter-quota-credits.prompt.md) | [v0.15.0](../../CHANGELOG.md#v0150--meter-dedup-correctness--cage-limits-codex-quota--estimated-ai-credits) |
| v0.16 | Cost-impact roadmap (P0–P5) | [handoff](v0.16-cost-impact-roadmap.handoff.md) | [prompt](v0.16-cost-impact-roadmap.prompt.md) | [v0.16.0](../../CHANGELOG.md#v0160-2026-07-08--cost-impact-roadmap-validate--diagnose) |
| v0.16 | Dummy-repo validation (plan · handoff · prompt) | [handoff](v0.16-dummy-repo-test.handoff.md) | [prompt](v0.16-dummy-repo-test.prompt.md) · [plan](v0.16-dummy-repo-test.plan.md) | [v0.16.0](../../CHANGELOG.md#v0160-2026-07-08--cost-impact-roadmap-validate--diagnose) |
| v0.16 | Manual test prep / verify + run record | — | [prep](v0.16-manual-test-prep.prompt.md) · [verify](v0.16-manual-test-verify.prompt.md) · [run record](v0.16-full-test-run.md) | [v0.16.0](../../CHANGELOG.md#v0160-2026-07-08--cost-impact-roadmap-validate--diagnose) |
| v0.17 | Windows/mac parity + path probe | — | [prompt](v0.17-windows-and-path-probe.prompt.md) | [v0.17.0](../../CHANGELOG.md#v0170-2026-07-08--windowsmac-parity--the-path-probe) |
| v0.18 | Derived human attention (turn gaps) | — | [prompt](v0.18-human-attention.prompt.md) | [v0.18.0](../../CHANGELOG.md#v0180-2026-07-11--derived-human-attention-passive-minutes-from-turn-gaps) |
| v0.19 | Pricing management (`cage prices`) | — | [prompt](v0.19-pricing-management.prompt.md) | [v0.19.0](../../CHANGELOG.md#v0190-2026-07-11--pricing-management-the-unpriced-workflow-cage-prices-policy-versioning) |
| v0.20 | Portable wiring (the committed shim) | — | [prompt](v0.20-portable-wiring.prompt.md) | [v0.20.0](../../CHANGELOG.md#v0200-2026-07-11--portable-wiring-no-absolute-paths-in-committed-files) |
| v0.21 | CSV output + reporting recipes | — | [prompt](v0.21-csv-and-report-skill.prompt.md) | [v0.21.0](../../CHANGELOG.md#v0210-2026-07-11--csv-output--agent-reporting-recipes-plan-39) |
| v0.22 | Restricted environments (launcher mode + pyz) | [handoff](v0.22-restricted-env.handoff.md) | [prompt](v0.22-restricted-env.prompt.md) | [v0.22.0](../../CHANGELOG.md#v0220-2026-07-11--restricted-environments-python-launcher-mode--cagepyz-plan-5) |
| v0.22.1 | Docs lifecycle (this archive + the rule) | — | [prompt](v0.22.1-docs-lifecycle.prompt.md) | [v0.22.1](../../CHANGELOG.md#v0221-2026-07-11--docs-lifecycle-the-archive-the-storybook-spine-the-rule) |
| v0.22.1 | Full test run record (58 findings, 3 bugs → v0.22.2) | — | [run record](v0.22.1-full-test-run.md) | [v0.22.2](../../CHANGELOG.md#v0222-2026-07-12--capture-correctness-three-bugs-from-the-v0221-full-test-run) |
| v0.23 | Tool-receipt pricing ladder (call-less receipts → $) | [handoff](v0.23-tool-receipt-pricing.handoff.md) | [prompt](v0.23-tool-receipt-pricing.prompt.md) | [v0.23.0](../../CHANGELOG.md#v0230-2026-07-14--tool-receipt-pricing-dollars-for-call-less-token-receipts) |
| v0.24 | Pricing freshness (per-commit note + complete vendor tables) | [handoff](v0.24-pricing-freshness.handoff.md) | [prompt](v0.24-pricing-freshness.prompt.md) | [v0.24.0](../../CHANGELOG.md#v0240-2026-07-14--pricing-freshness-the-per-commit-staleness-note--complete-vendor-tables) |
| v0.23 | `prices route-tool` managed writer + runnable hint | [handoff](v0.23-prices-route-tool.handoff.md) | [prompt](v0.23-prices-route-tool.prompt.md) | [v0.23.0](../../CHANGELOG.md#v0230-2026-07-14--tool-receipt-pricing-dollars-for-call-less-token-receipts) |
| v0.25 | Policy sync (project policy.toml → installed bundle) | [handoff](v0.25-policy-sync.handoff.md) | [prompt](v0.25-policy-sync.prompt.md) | [v0.25.0](../../CHANGELOG.md#v0250-2026-07-14--policy-sync-upgrade-a-project-policytoml-to-the-installed-bundle) |
| v0.26 | Output honesty (tokens-default, `—` unpriced, signal-gated columns, doc generators) | [handoff](v0.26-output-honesty.handoff.md) | [prompt](v0.26-output-honesty.prompt.md) | [v0.26.0](../../CHANGELOG.md#v0260-shipped-in-v0280-2026-07-15--output-honesty-tokens-by-default--for-unpriced-signal-gated-columns-generated-docs) |
| v0.27 | CLI tiering (five daily verbs, grouped rooms, `init`→`setup`) | [handoff](v0.27-cli-tiering.handoff.md) | [prompt](v0.27-cli-tiering.prompt.md) | [v0.27.0](../../CHANGELOG.md#v0270-shipped-in-v0280-2026-07-15--cli-tiering-five-daily-verbs-grouped-rooms-a-clean-pre-10-verb-break) |
| v0.28 | Configurable import paths (`[sources]` per agent + custom tools) | [handoff](v0.28-policy-sources.handoff.md) | [prompt](v0.28-policy-sources.prompt.md) | [v0.28.0](../../CHANGELOG.md#v0280-2026-07-15--configurable-import-paths-sources-in-policytoml) |
| v0.29 | Visible source paths (generated commented `[sources]` block) + per-source globs | [handoff](v0.29-sources-defaults.handoff.md) | [prompt](v0.29-sources-defaults.prompt.md) | [v0.29.0](../../CHANGELOG.md#v0290-2026-07-16--visible-source-paths--per-source-globs) |
| v0.30 | Capture health (triple-gated "installed but capturing nothing" warning) | [handoff](v0.30-capture-health.handoff.md) | [prompt](v0.30-capture-health.prompt.md) | [v0.30.0](../../CHANGELOG.md#v0300-2026-07-16--capture-health-make-silent-zero-capture-loud) |
| v0.32 | Stale-wiring liveness (detect + heal an orphaned dead verb) | [handoff](v0.32-stale-wiring.handoff.md) | [prompt](v0.32-stale-wiring.prompt.md) | [v0.32.0](../../CHANGELOG.md#v0320-2026-07-24--stale-wiring-liveness-detect--heal-orphaned-wiring) |
| v0.33 | Codex removal (cage is claude/copilot/kiro) | [handoff](v0.33-codex-removal.handoff.md) | [prompt](v0.33-codex-removal.prompt.md) | [v0.33.0](../../CHANGELOG.md#v0330-2026-07-24--codex-removed-cage-is-claude-code--copilot--kiro) |
| v0.34 | Installed-artifact inventory (`cage doctor --wiring`) | [handoff](v0.34-wiring-inventory.handoff.md) | — | [v0.34.0](../../CHANGELOG.md#v0340-2026-07-24--cage-doctor---wiring-the-installed-artifact-inventory) |
| v0.35 | Capture-report follow-ups (F3 Kiro visibility, F5 cache split, F7 gap_ms observability) | [handoff](v0.35-phase3-deferred-findings.handoff.md) | [prompt](v0.35-phase3-deferred-findings.prompt.md) | [v0.35.0](../../CHANGELOG.md#v0350-2026-07-24--capture-report-follow-ups-kiro-visibility-cache-honesty-gap_ms-observability) |
| v0.36 | Hookless rebuild + import ledger (Phases 0–4: pull-only capture, loud import summary, savings tree, capture manifest, gated task correlation) | [handoff](v0.36-hookless-rebuild.handoff.md) | [prompt](v0.36-hookless-rebuild.prompt.md) | [v0.36.0](../../CHANGELOG.md#v0360-2026-07-25--hookless-rebuild--import-ledger-phases-04) |
| v0.36 | Session names always-on (+ `session_uid`, per-session manifest rows) + precise savings migration (`cage data migrate-savings`, id-deduped `receipts()` union) | [handoff](v0.36-names-and-savings-migration.handoff.md) | [prompt](v0.36-names-and-savings-migration.prompt.md) | [v0.36.0](../../CHANGELOG.md#v0360-2026-07-25--hookless-rebuild--import-ledger-phases-04) |
| v0.36 | Config surfaces + `cage.toml` rename (`[sources] surface` restamp key; `policy.toml` → `cage.toml` with read fallback + `cage setup` migration) | [handoff](v0.36-config-surfaces-and-rename.handoff.md) | [prompt](v0.36-config-surfaces-and-rename.prompt.md) | [v0.36.0](../../CHANGELOG.md#v0360-2026-07-25--hookless-rebuild--import-ledger-phases-04) |
| v0.36 | Model prices split into `prices.toml` (vendor rate card apart from policy; money byte-identical; `cage setup` migration money-neutral; `[meta]` splits per key; plan of record: [plan](v0.36-prices-toml.plan.md)) | [handoff](v0.36-prices-toml.handoff.md) | [prompt](v0.36-prices-toml.prompt.md) | [v0.36.0](../../CHANGELOG.md#v0360-2026-07-25--hookless-rebuild--import-ledger-phases-04) |
| v0.36 | Phase 1 BENCHMARK — *what cage captures, how correct* (the third artifact type, one phase; closes golden-set Phase 1). Deliverable: [PHASE-1-BENCHMARK](../regression/2026-07-28-phase-1-benchmark.md) (sha256 `58948469192c`) | — | [prompt](v0.36-phase1-benchmark.prompt.md) | benchmark doc (unreleased; no changelog anchor — see mapping note) |
| v0.36 | Shim integrity — the PATH-**winning** graphify interceptor (`live`/`dead`/`shadowed`/`foreign`, dead = doctor failure), the heal boundary (cage-managed root only), and the absolute-path hook bypass (advisory). Also published the three Phase-I lab artifacts, hashed | [handoff](v0.36-shim-integrity.handoff.md) | [prompt](v0.36-shim-integrity.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | `[sources] path_globs` — the **root-agnostic** `--path`/`--project` discovery patterns, declared in `cage.toml` beside the anchored `glob` (two keys, two jobs). Closes leg-D finding K1 (copilot `--path` could never reach the VS Code `chatSessions` store); no glob literal survives in any import branch (AST-gated), absent patterns are a **loud** no-op, and the zero-match ⚠ now names what it tried | [handoff](v0.36-path-globs.handoff.md) | [prompt](v0.36-path-globs.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | `[meta] cage_version` drift — the bundled value was a hand-maintained literal, eleven releases stale (`0.25.0` vs package `0.36.0`), printed by `cage prices list` and copied into every new project. Now derived live from `cage.__version__` (`policy._bundled`); a scaffolded project's copy stays a historical stamp, never rewritten. `policy_version` untouched (a content counter, not a release counter) | — | [prompt](v0.36-meta-version.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.38 | **Proposal (implemented)** — Windows-native graphify interceptor. Motivated the `graphify.cmd` twin; superseded as spec by [shim-contract.md](../shim-contract.md), which corrected two of its claims (graphify is PyPI `graphifyy`, not npm; the re-entry guard skips metering only) | [proposal](v0.38-windows-graphify-interceptor.proposal.md) | — | unreleased (v0.38 in tree) |
| v0.36 | OPEN-WORK A→I runner — executed the consolidated queue (A ceiling · B VS Code probe + B-fix-1/2/3 · C folded into I · F capture reach · G honesty debts + G4 · I scripted legs and published artifacts), leaving only leg D and the release | — | [prompt](v0.36-open-work-runner.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | cage-lab three-agent parity — `cage setup --all` in both workspaces plus all three graphify installers, so Claude · Copilot · Kiro are first-class in the lab. Law 0 now lives in [`docs/cage-lab/`](../cage-lab/README.md) | — | [prompt](v0.36-three-agent-parity.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | Leg D publication — six manual VS Code/IDE cells turned into published evidence: the run report, five finding docs (incl. the blocking gross-vs-net finding) and the phase benchmark superseding 07-29, all hashed into [`regression/`](../regression/) | — | [prompt](v0.36-legd-publish.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | Budget opt-in **verification** — confirmed the bundle change needs no code fix and that `cage policy sync` does not re-add `[budgets]` (an active table buckets as `project_own`). Verdict: keep as-is; goldens P5/P6a/P6b re-blessed | — | [prompt](v0.36-budget-optin-verify.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **Removed** the Tier-1 agent-vs-human axis, substrate included (`human.py`/`humanview.py`/`trend.py`/`attention.py`, the `cage human` group, `cage insights trend`, `--human`/`--agent-only` flags, `gap_ms`, the `minutes` unit, `[human.*]`, `CAGE_HUMAN_RATE`, `IDLE_CAP_MINUTES`). A clean amputation — no stub, no revert path. `cage human outcome`/`quality` **moved** to the new `task` group (never part of the axis); provenance `origin="human"` untouched; legacy rows read and are excluded with a counted footnote | [handoff](v0.36-human-removal.handoff.md) | [prompt](v0.36-human-removal.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **Kiro capture routing (K2)** — two stores, two *opposite* fixes. IDE `tokens_generated.jsonl` (one global file, no project/session/ts) routes to the machine ledger, so a turn exists once per machine; CLI `conversations_v2` (keyed by cwd) is scoped to the project tree and stamps `project`. `--ledger`/`CAGE_BASE` wins for both; pre-existing rows are never rewritten. Also placed the two HONEST-LIMITs (K3 kiro time/session/project · K4 blank surface ≠ "cli"). Decision: [ADR 0006](../adr/0006-kiro-rows-are-machine-facts-not-project-facts.md) | [handoff](v0.36-kiro-routing.handoff.md) | [prompt](v0.36-kiro-routing.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **Gross vs net savings (K · NET-2 · NET-3)** — `saved` is a per-query counterfactual that excludes the cost of *using* a tool, so graphify's self-declared `$0` own cost made `verdict` print a bare **SAVING** on sessions leg D measured costing ~31% more. Relabelled GROSS on every surface (text + CSV, one phrasing in `netsaved.GROSS_NOTE`); `verdict` now reads `SAVING (GROSS)` and names the exclusion when the cost of use is unknown, while **COSTING stays assertible** (the omitted term is ≥ 0); new `netsaved.by_tool` nets it at task level via the ±120s receipt-window union, refusing rather than reporting `net = gross`. Evidence: [finding](../regression/2026-08-01-finding-saved-is-gross.md) | [handoff](v0.36-net-savings.handoff.md) | [prompt](v0.36-net-savings.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **SUITE — green the last two red causes (G-SAV + BUD-V-TEST)** — `savings.record()` was missing `ts` from its signature (`**_ignore` silently swallowed a caller's value, stamping every row *now* regardless of the work's real date); added and forwarded, plus a kwarg-parity guard test so the next such drop fails loudly. Five `test_policysync` mechanics tests (keep-customized, marked/block-owned, update-stale-default, update-known-version-customized, confirm-bucket) had borrowed `[budgets]` as their worked example; re-pointed at `[quality] signal` — a table the bundle actually ships — same mechanics, different example. 949/6 ⇒ 956/0. Neither cause was a shipped-behaviour regression. Follow-up (a synthetic bundle fixture so these tests stop coupling to product content) filed as `SYNC-FIXTURE` in [OPEN-WORK.md](../OPEN-WORK.md) | [handoff](v0.36-suite-green.handoff.md) | [prompt](v0.36-suite-green.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **Cleanup becomes advisory (CLEAN)** — cage no longer deletes state on its own. Retention default 30 → 90 days; the auto sweep (piggybacked on `cage import`) now only warns on stderr (count, reclaimable size, the runnable fix — silent when nothing's eligible, throttled), never deletes; deletion is `cage data cleanup --apply` only, which runs regardless of `[cleanup] enabled` (an explicit command is always honored). New `[cleanup] warn` switch (env `CAGE_CLEANUP_WARN`) silences just the reminder. Tool savings (`ledger/savings/<tool>/`) get an explicit never-per-tool invariant, tested surviving `prune` at `days=0`. 956/0 ⇒ 961/0 | [handoff](v0.36-cleanup-safety.handoff.md) | [prompt](v0.36-cleanup-safety.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.36 | **Sync-tests guard (SYNC-GUARD)** — the five `test_policysync` mechanics tests that borrow `[quality] signal` as their generic worked example now derive it from one named constant (`_EXAMPLE_TABLE, _EXAMPLE_KEY`), so a future re-point (after `[budgets]`, `[quality]` is a **second** occurrence) is a one-line edit. Added a guard test asserting the key still exists in `policy.bundled_raw()`, failing with the exact fix. The synthetic-bundle fixture stays parked as a [proposal](../proposals/policysync-synthetic-bundle.md) behind a third-occurrence trigger. 961/0 ⇒ 962/0 | — | [prompt](v0.36-sync-guard.prompt.md) | unreleased (tree uncommitted) — see mapping note |
| v0.38 | **CI graphify axis (CI-GF)** — `python-package.yml` keeps its `absent` leg byte-identical and gains a `present` job on all three OSes: pinned real graphify (PyPI `graphifyy`, **not** npm as the handoff assumed), a graph over the new committed `tests/fixtures/cicorpus/`, and a **bare `graphify query` through the platform shell** asserting a savings row lands. Also asserts passthrough, doctor `live`, a killed shim reporting `dead` then healing, and determinism. `$0` — graphify is AST-only. Checks live in `tools/cigraphify.py`; skips loudly if the pinned install flakes | [handoff](v0.38-ci-graphify-matrix.handoff.md) | — | [v0.38.0](../../CHANGELOG.md#v0380-2026-08-01--graphify-is-metered-on-windows-ci-grows-a-graphify-axis) |
| v0.38 | **Windows graphify interceptor (WIN-GF)** — a `graphify.cmd` twin (plain text, no `.exe`) against one written [behaviour contract](../shim-contract.md): B1–B8 binding, D1–D7 divergences documented (cmd has no `exec`). `cage setup` installs both twins everywhere; `refresh_shim` completes the pair; `pathshim` stops treating the extensionless name as a Windows candidate; doctor fails a twin this OS cannot resolve. Recursion impossible by four mechanisms, both stacked pairings tested. 962/0 ⇒ 979/0 (+10 Windows-only) | [handoff](v0.38-win-graphify-shim.handoff.md) | [prompt](v0.38-win-graphify-shim.prompt.md) | [v0.38.0](../../CHANGELOG.md#v0380-2026-08-01--graphify-is-metered-on-windows-ci-grows-a-graphify-axis) |
| v0.38 | **Honesty debts (GF-DEBT)** — six gaps WIN-GF/CI-GF left: restored the deleted `docs/restricted-environments.md` (8 stale citations, now current) plus its new GF-LAUNCHER section; stated GF-LAUNCHER in the README Platforms line and a new `cage doctor` `launcher-gap` check; added the `cage query graphify-shims` explainer; filed [ADR 0007](../adr/0007-graphify-twin-pair-hand-paired-not-templated.md) (both twins on every OS · hand-paired · contract lives in `docs/`); `docs/cage-lab/{01-setup,03-verify}.md` now state POSIX-twin-only coverage; the corpus-sizing rule is written into `tools/cigraphify.py` and pinned by 4 new tests in `tests/test_cigraphify.py`. GF-LAUNCHER itself stays open (documented, not fixed). 979/0 ⇒ 983/0 | [handoff](v0.38-graphify-honesty-debts.handoff.md) | [prompt](v0.38-graphify-honesty-debts.prompt.md) | [v0.38.0](../../CHANGELOG.md#v0380-2026-08-01--graphify-is-metered-on-windows-ci-grows-a-graphify-axis) |
| v0.39 | **CLAUDE.md sync (CMD-SYNC)** — one parked proposal applied, one declined. Applied [claude-md-prices-file](v0.39-claude-md-prices-file.proposal.md) verbatim: the flow diagram + Must-Know bullets now name `prices.toml` as the vendor rate card home, `cage.toml` keeping order/budgets/routing (governing sentence: **vendor facts move, routing decisions stay**). Declined [claude-md-sources-authority](v0.39-claude-md-sources-authority.proposal.md), independently re-verified against `paths.resolve_log_sources`'s docstring — an empty/absent `[sources]` is fully additive, byte-identical to the built-in registry, which is what CLAUDE.md already said; the proposal described a Directive A end-state that never shipped. Zero code changes | [handoff](v0.39-claude-md-sync.handoff.md) | [prompt](v0.39-claude-md-sync.prompt.md) | unreleased (v0.39 in tree) |
| v0.39 | **Codex purge (CODEX-OUT)** — removed the residue of the Codex *agent* (support ended v0.33.0): `paths.codex_home()` + `CODEX_HOME`, `wiringscan`'s `~/.codex/config.toml` scan and `.codex/hooks.json` enumeration, doctor's read of it, the doctor-bundle env entry, and the stale agent word in six prose enumerations. **The trade is named in the CHANGELOG, not buried:** a pre-v0.33 `~/.codex/config.toml` can no longer be checked for a dead `cage` verb. **Category 2 held — `data/prices.toml` is byte-identical**: `gpt-5.x-codex` are OpenAI model ids Copilot emits, and a new guard prices a Copilot call on every one of them. `paths.py` was deliberately **not** split; `agenthomes` is a named seam, and CODEX-OUT's earned clause *a deletion and a move never share a diff* is now a rule in [CLAUDE.md](../../CLAUDE.md). 983/0 ⇒ 982/0 (2 codex cases deleted, 1 guard added) | [handoff](v0.39-codex-purge.handoff.md) | [prompt](v0.39-codex-purge.prompt.md) | unreleased (v0.39 in tree) |
| v0.39 | **OTel GenAI export (OTEL)** — `cage data export --otel`: one-way GenAI-conformant JSON alongside `--csv`/`--study`. Calls map to `gen_ai.system`/`gen_ai.request.model`/`gen_ai.usage.input_tokens`/`output_tokens`/`gen_ai.client.operation.duration` (omitted, never zero, when `latency_ms` is unknown). **Decision: receipts/savings have no GenAI equivalent** — cage-namespaced under `cage.savings[].cage.*` (`cage.saved` GROSS, `cage.saved_usd` priced via the existing `receiptprice` ladder and omitted, never `$0`, on an UNPRICED refusal or a non-money unit); no `gen_ai.*` name invented. **The convention is pre-stable** (semconv v1.42.0, June 2026, own repo, no 1.0) — pinned in `constants.OTEL_SEMCONV_VERSION` and stamped in every document's `cage.meta` block; a spec bump is a deliberate, changelog'd change. New module `cage/otelout.py`; `cage query otel-export` explains it. 982/0 ⇒ 995/0 | [handoff](v0.39-otel-export.handoff.md) | [prompt](v0.39-otel-export.prompt.md) | unreleased (v0.39 in tree) |

## Superseded drafts & research inputs

| Version | File | Why archived |
| ------- | ---- | ------------ |
| v0.9 | [v0.9-ledger-scale.plan-draft.md](v0.9-ledger-scale.plan-draft.md) | Plan amendment draft — merged into `cage-plan.md` §3.6 |
| v0.12 | [v0.12-universal-capture-scheduler-draft.prompt.md](v0.12-universal-capture-scheduler-draft.prompt.md) | Earlier draft of universal capture — the shipped design dropped the scheduler (cage installs no OS job) |
| v0.15 | [v0.15-meter-competitive-lessons.md](v0.15-meter-competitive-lessons.md) | Landscape research (2026-06-30) that fed the v0.15 meter work |
| v0.15 | [v0.15-meter-modification-plan.md](v0.15-meter-modification-plan.md) | Code-grounded plan superseded by the v0.15 handoff |
| v0.7 | [v0.7-org-gateway-zero-setup.prompt.md](v0.7-org-gateway-zero-setup.prompt.md) | The org-gateway phase was never shipped as specced — superseded by the proxy + universal capture (v0.12) |

## Mapping notes (where the version was ambiguous)

- **v0.36-phase1-benchmark** — a *doc deliverable*, not a code feature, so it has
  no CHANGELOG anchor. The reference is the published, hashed benchmark itself
  ([PHASE-1-BENCHMARK](../regression/2026-07-28-phase-1-benchmark.md), sha256
  `58948469192c`) plus the IMPLEMENTATION.md entry. Archived under v0.36 as the
  in-flight (unreleased) tree it rode; solo prompt, no handoff pair.

- **v0.36-shim-integrity** — no CHANGELOG anchor yet: implemented and green
  (2026-07-30) while the cage tree stays uncommitted under Arpit's standing
  no-commit directive, so the release entry is written at the v0.36 cut. Archived
  on *implement*, per the lifecycle rule — the archive date is not the release date.

- **v0.36-meta-version** — no CHANGELOG anchor yet, same reason as shim-integrity:
  implemented and green (2026-08-01) under the standing no-commit directive; the
  release entry is written at the v0.36 cut. Solo prompt, no handoff pair — the
  diagnosis was small enough that the prompt carried the full change-map.

- **v0.36-sync-guard** — no CHANGELOG anchor yet, same reason as meta-version:
  implemented and green (2026-08-01) under the standing no-commit directive. Solo
  prompt, no handoff pair — CLAUDE.md's pair rule exempts a change this small.

- **v0.34-wiring-inventory** — no archived prompt: the executing prompt
  self-declared itself throwaway ("delete this file when done") and was deleted
  per its own instruction; the handoff alone carries the decided design.
- **v0.5-fix-cost-rendering** — no dedicated changelog entry; mapped to the release
  whose commit introduced it (v0.5.0). The derive-time repricing rule it fixed is
  documented in `CLAUDE.md` (Per-call cost).
- **v0.8-eli5-help-and-query** — no dedicated changelog entry; mapped by commit date
  (added in the v0.8.0 commit). The shipped surface is the grouped `cage --help` +
  `cage query` worked examples.
- **v0.3-tool-receipts-graphify-fux** — mapped to v0.3.0 ("graphify/fux savings
  receipts" in its release commit).
- **v0.16 manual-test prompts** — the prep/verify pair executed
  `docs/full-test-plan-sibling-repo.md` against 0.16.0; findings landed in the
  v0.16.0 "Manual validation" changelog subsection. The evergreen plan template
  stays live in `docs/` root; the ticked run record is
  [v0.16-full-test-run.md](v0.16-full-test-run.md).
