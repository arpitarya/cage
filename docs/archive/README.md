# Archive — shipped handoffs, prompts, and superseded drafts

**History, not spec. The living design of record is in `docs/` root and [`docs/cage-plan.md`](../cage-plan.md).**

Every file here drove work that has since shipped (or was superseded). Files keep
their original text verbatim plus a one-line archive header; names sort by the
release that shipped the work: `vX.Y-<feature>.{handoff,prompt}.md`.

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

## Superseded drafts & research inputs

| Version | File | Why archived |
| ------- | ---- | ------------ |
| v0.9 | [v0.9-ledger-scale.plan-draft.md](v0.9-ledger-scale.plan-draft.md) | Plan amendment draft — merged into `cage-plan.md` §3.6 |
| v0.12 | [v0.12-universal-capture-scheduler-draft.prompt.md](v0.12-universal-capture-scheduler-draft.prompt.md) | Earlier draft of universal capture — the shipped design dropped the scheduler (cage installs no OS job) |
| v0.15 | [v0.15-meter-competitive-lessons.md](v0.15-meter-competitive-lessons.md) | Landscape research (2026-06-30) that fed the v0.15 meter work |
| v0.15 | [v0.15-meter-modification-plan.md](v0.15-meter-modification-plan.md) | Code-grounded plan superseded by the v0.15 handoff |
| v0.7 | [v0.7-org-gateway-zero-setup.prompt.md](v0.7-org-gateway-zero-setup.prompt.md) | The org-gateway phase was never shipped as specced — superseded by the proxy + universal capture (v0.12) |

## Mapping notes (where the version was ambiguous)

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
