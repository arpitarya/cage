# Claude Code prompt: run the test plan up to the manual phase

You are executing `docs/full-test-plan-sibling-repo.md` (cage 0.16.0) **up to and
including Part B, plus everything that makes my manual Parts C–G friction-free** —
then you STOP. I do the manual extension testing myself; a later session picks up
my findings. Read the test-plan doc first and treat it as binding. **Do not
commit, tag, push, or publish anything — in the cage repo or the testbed.**

## Context to load first

- `docs/full-test-plan-sibling-repo.md` (the plan you're executing)
- `CLAUDE.md`, `tools/dummyrepo/run.py` + its README,
  `tests/fixtures/transcripts/README.md` (the three `UNVERIFIED-FORMAT` cells my
  manual run will close), `cage/paths.py` (agent log locations + env overrides),
  `cage/doctorcmd.py`.

## Task

**1. Part A — automated baseline, all green:**
- `just test` · `python -m tools.dummyrepo` (S1–S9) ·
  `python -m tools.skillgen --check` · fresh no-extras venv `import cage` ·
  `cage demo` vs plan §4.4.
- Any failure: diagnose and fix it (test-plan findings-table row + the fix in the
  working tree), then re-run until green. A red baseline invalidates my manual
  run — do not proceed past A with anything red. If a fix would change the
  substrate contract or attribution numbers, STOP and ask instead.

**2. Part B — scaffold the sibling testbed at `../cage-testbed`:**
- Exactly per the plan: git init + seed files + first commit (this commit is
  allowed — it's the testbed's own history, not cage's), `cage init`,
  `cage setup`, `cage doctor` (record every warn), setup run twice →
  idempotency verified (diff the wired files), `doctor` snapshot saved.
- Verify from inside the testbed that all four agents' wiring exists exactly as
  `cage setup` claims (hook files, `.mcp.json`/`mcp.json` variants, steering
  pointers) — read the files, don't trust the success message.

**3. Manual-run aids (create these in `../cage-testbed/manual/`):**
- `findings.md` — the plan's findings table, pre-seeded with one row per
  Part C cell (agent × surface) marked TODO, plus empty sections for D–G.
- `checklist.md` — Parts C–G flattened into a copy-paste command sequence per
  cell: the exact session-log path for THIS machine (resolve `~`, the real
  Claude project slug via `paths.claude_project_slug`, the real Kiro
  globalStorage path for this OS), the per-cell verify commands, and the PII
  grep with a placeholder phrase.
- `sanitize_log.py` — small stdlib-only helper: takes a captured extension
  session log + agent name, strips ALL content fields (prompt/response text,
  file paths where the fixture README says counts-only), keeps structure +
  token counts + ids/ts, writes a fixture-ready file plus a diff-style summary
  of what it stripped so I can eyeball before it ever lands in
  `tests/fixtures/`. Refuse (with a message) on formats it doesn't recognize
  rather than guessing — an unrecognized format is itself the finding.
- Seed Part E's prerequisite: enough closed labeled tasks in the testbed ledger
  (via cage's own row factories, label `docfix`) that `cage estimate --label
  docfix` clears `MIN_ESTIMATE_N` on my first manual try — and note in
  `checklist.md` that these are seeded rows, listed by id, so I can tell them
  from my real ones.

**4. Pre-verify the read surface won't waste my time:** run every Part D command
once against the seeded testbed ledger, expecting rendered output or a correct
refusal/INSUFFICIENT DATA — not a traceback. Any traceback = fix in cage (working
tree) + findings row. Determinism double-run (Part G first bullet) on the five
newest views (compare/estimate/calibration/verdict/study report) now, since a
diff there blocks everything manual.

**5. STOP and hand off:** print a summary — baseline counts, fixes made (files
touched, uncommitted), testbed path, doctor warns, exactly which manual cells
await me (installed vs N/A where detectable), and the three fixture cells my
manual run should close. Do not start Part C; do not run any real agent session.

## Constraints (hard)

- No commits/tags/pushes in the **cage** repo; testbed gets only its init commit.
- Fixes stay within existing law: $0/stdlib, determinism, fail-open write path,
  `CageError`-only read path, four agents, additive-only schema, no scheduler.
- `tests/fixtures/` gains nothing in this session — fixtures come from MY
  sanitized captures later.
- Don't modify `docs/full-test-plan-sibling-repo.md` except to tick Part A/B
  boxes; the aids live in the testbed, not in cage's docs.
- Ask before any fix that changes CLI output an existing test asserts.

## Acceptance criteria (self-check before finishing)

- [ ] Part A fully green (fixes uncommitted in the tree, each with a findings row).
- [ ] `../cage-testbed` scaffolded, wired, doctor-snapshotted, idempotency proven.
- [ ] `manual/findings.md`, `manual/checklist.md` (real resolved paths, not
      `<placeholders>`), `manual/sanitize_log.py` exist and run.
- [ ] Part E history seeded past MIN_ESTIMATE_N; seeded ids listed.
- [ ] Part D sweep + determinism double-run clean or fixed.
- [ ] Handoff summary printed; nothing manual attempted.
