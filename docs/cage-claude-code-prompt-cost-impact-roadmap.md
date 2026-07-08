# Claude Code prompt: Cage cost-impact roadmap (P0–P5)

You are implementing the cage cost-impact roadmap: validation harness, diagnostics
bundle, `cage compare`, `cage estimate`/`cage calibration`, `cage verdict`, and the
multi-laptop fleet study (`cage study`). The
full spec is in **`docs/cage-handoff-cost-impact-roadmap.md`** — read it first and
treat its Definition of Done and Non-negotiables as binding. **Do not commit,
tag, push, or publish anything** — leave all changes in the working tree for my
review.

## Context to load first

- Read: `docs/cage-handoff-cost-impact-roadmap.md`, then `CLAUDE.md`, then
  `docs/cage-plan.md` §3, §3.7, §4.
- Then the code the phases touch: `cage/schema.py`, `cage/tasks.py`,
  `cage/constants.py`, `cage/transcript.py`, `cage/importcmd.py`,
  `cage/doctorcmd.py`, `cage/debuglog.py`, `cage/attribution.py`, `cage/roi.py`,
  `cage/trend.py`, `cage/regression.py`, `cage/quality.py`, `cage/prices.py`,
  `cage/cli.py` + `cage/clicmds.py`, `cage/explain_data.py`,
  `docs/dummy-repo-test-plan.md`.
- Follow existing view-module patterns (small module → `render.py` → grouped CLI
  help) and the three numbers-layers (schema enums / policy / constants).

## Task

Build phases **in order**, each left green before the next:

1. **P0 — validation harness:** fixture corpus
   `tests/fixtures/transcripts/<agent>/<surface>/` for all four agents × (cli,
   vscode) with parametrized exact-row parse tests; build-time-only
   `tools/dummyrepo/run.py` scenario runner (S1–S8 per handoff §9) scaffolding a
   disposable sibling repo. Where a real VS Code-extension log sample is missing,
   use the CLI format as stand-in and mark it clearly `UNVERIFIED-FORMAT` in the
   fixture README — do not invent formats.
2. **P1 — diagnostics:** `cage doctor --bundle` (redacted, counts-never-content
   archive) + a coverage test asserting every capture-path swallow-site logs a
   `debuglog` event under `CAGE_DEBUG=1`.
3. **P2 — `cage compare`:** derive-time stack signatures from receipts (task-id
   join, session-window fallback), measured group totals via `prices.call_usd`,
   `n · median · IQR` per group, delta tagged `estimated` with the observational
   caveat, refusal below `MIN_COMPARE_N` (new constant, default 5). Additive
   optional task `label` set via `cage outcome --label` (single-token PII guard).
   Shared key-matching helpers in a small new module (e.g. `cage/taskgroup.py`).
4. **P3 — `cage estimate` + `cage calibration`:** band (median+IQR) from matching
   closed tasks, tagged `modeled`, refusal below `MIN_ESTIMATE_N`; `--record`
   stamps additive `est_tokens`/`est_usd`/`est_n` on the open task row
   (fail-open); calibration reports ratio distribution + in-band hit-rate over
   closed tasks with estimates.
5. **P4 — `cage verdict <tool>`:** pure composer over attribution/roi/trend/
   regression/quality + break-even line; computes no new statistics; prints every
   input with its method tag; explicit INSUFFICIENT DATA path.
6. **P5 — fleet study (`cage study`):** opaque random `machine` id in
   `.cage/state/` (never hostname/username) stamped as an additive optional field;
   `cage study start/stop <phase>` appends markers to `study.jsonl` (phase =
   single validated token); derive assigns rows to phases per-machine by row `ts`
   vs that machine's own markers; `cage export --study` one-file bundle with a
   counts-only manifest; `cage import <bundles…>` merges by id (idempotent);
   `cage study report` = per-machine coverage with gaps flagged first, then
   paired-by-machine phase deltas (median of per-machine deltas) + pooled
   n/median/IQR, delta tagged `estimated`, refusal below `MIN_COMPARE_N` complete
   machines; `cage study join <phase>` = wire all agents + start phase + doctor +
   print the cron line. No server, no auto-upload — bundles are plain files.

## Required workflow

1. **Explore** the listed files before writing anything; don't assume structure.
2. **Plan** — before each phase, lay out the files you'll add/change and pause
   for my confirmation.
3. **Implement incrementally** — small coherent changes, suite kept green.
4. **Update docs to match, per phase** (handoff §9.5): README "What's new" +
   test count, CHANGELOG entry (in-tree only), plan-doc sections,
   `explain_data.py` entries for every new calculation, dummy-repo test-plan
   S5–S8, and skillgen fragments (`python -m tools.skillgen && python -m
   tools.skillgen --bless` — never hand-edit rendered assets). For **CLAUDE.md**:
   propose the edit and flag it for my review — do not silently rewrite it.
5. **Verify** after each phase: `just test` · `cage demo` still reproduces the
   plan §4.4 tables byte-identically · `python -m tools.skillgen --check` ·
   `python tools/dummyrepo/run.py` scenarios for that phase green · a PII grep
   over everything new code writes. Do not report a phase done until all pass.

## Constraints (hard)

- $0 / stdlib-only: `dependencies = []` stays empty; no new imports outside the
  stdlib on the default path.
- Determinism: no clocks/random in any derived view; same ledger + policy ⇒
  byte-identical output; tests assert exact numbers.
- `method` is sacred: compare deltas and estimates are `estimated`/`modeled` and
  render their tag; nothing new ever reads as `measured` unless recorded.
- Four agents, always: claude · codex · copilot · kiro first-class in every
  fixture set and surface; never special-case one.
- Two error regimes: write paths fail-open (return False/swallow, `CAGE_DEBUG`
  traceable); read/CLI raises `CageError` only; exit codes unchanged.
- Schema changes additive-only (`label`, `est_*`, `machine` optional; empty =
  legacy); never rewrite the ledger.
- Machine id is opaque and random — never hostname, username, MAC, or anything
  derivable; the manifest is counts-never-content.
- Min-n gates are blocking: below threshold the command explains, never numbers.
- Do NOT touch: `.github/workflows/publish.yml`, the release flow,
  `metering.py`'s fail-open contract, provenance enums.
- Do NOT commit, tag, push, release, or run any publish command.

## Acceptance criteria (self-check before finishing)

- [ ] All Definition-of-done boxes in handoff §2 satisfied.
- [ ] S1–S9 scenario runner passes on the phases built; manual-only steps
      printed as a checklist, not skipped silently.
- [ ] S9: 3 simulated machines / 2 phases / one gap + one missing phase →
      coverage flags both, pairing uses only complete machines, double-import
      idempotent, exact paired delta asserted.
- [ ] Compare delta and estimate outputs visibly carry `estimated`/`modeled`
      tags and the observational caveat; n<min renders a refusal.
- [ ] `cage query` answers "how is the estimate calculated" and "how does
      compare work" from live values.
- [ ] Tests added with exact-number assertions; `just test` green; demo tables
      unchanged.
- [ ] Docs updated per §9.5 (CLAUDE.md as a *proposed* diff); or explicitly
      noted N/A with reason.
- [ ] Working tree left uncommitted.

## Tests

Extend `tests/` per phase: fixture parse exactness (P0), debuglog coverage audit
(P1), golden outputs over seeded ledgers for compare/estimate/calibration/verdict
including cross-month tasks, truncated-tail tolerance, refusal paths, and
determinism double-runs (P2–P4), and the S9 fleet-study merge/coverage/pairing
cases incl. phase-marker edge cases — start-without-stop, pre-enrollment rows,
overlapping labels (P5). Run: `just test`.

## Guardrails

- Ask before: changing any public CLI output format an existing test asserts,
  adding any schema field beyond those specified, or touching capture wiring.
- The handoff's OPEN QUESTIONS (§10) are decisions for me — surface them when
  reached; don't resolve them unilaterally.
- If a requirement conflicts with what you find in the code (e.g. a join field
  that doesn't behave as documented), STOP and ask rather than guessing.
