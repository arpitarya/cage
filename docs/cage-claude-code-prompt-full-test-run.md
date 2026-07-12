# Claude Code prompt: run the full sibling test suite (reusable, any release)

You are executing `docs/full-test-plan-sibling-repo.md` end-to-end against the
current working tree. This prompt is reusable across releases: fill in nothing —
read the version from `cage --version` and stamp it into the plan's
`<version under test>` for this run's record. **Do not commit, tag, push, or
publish anything, anywhere.** All fixes and the run record stay in the working
tree for my review.

## Ground rules

- The plan is the checklist; this prompt is the driver. Read the plan fully
  first, plus `CLAUDE.md` (the invariants you're testing against) and
  `docs/README.md` (to know which design docs are the spec for each surface).
- Record every result as a findings row (the plan's template) in
  `../cage-testbed/manual/findings-v<version>.md`. Every deviation gets a row
  — pass/fail/N-A, no silent skips.
- **Fix-forward rule:** a bug found mid-run gets fixed in the cage working
  tree with a regression test IF it's blocking or clearly scoped; anything
  architectural → findings row + STOP-and-ask. After any fix, re-run the part
  it invalidates.
- **Real-ledger safety (learned the hard way in the v0.16 run):** before
  anything else, snapshot `~/.cage` row counts per file; re-check at the end —
  any delta must be explained by deliberate steps (the resolver test, the
  export sweep). Sandbox/scenario work must never touch the real global
  ledger; if it does, STOP immediately and show me.

## Execution order

**1. Part A** — automated baseline (`just test`, `python -m tools.dummyrepo`
S1–S13, skillgen `--check`, bare-venv import, `cage demo`). All green before
proceeding; fix-forward applies.

**2. Part B** — scaffold a FRESH testbed (`../cage-testbed-v<version>` if the
old one exists — don't reuse a stale testbed; note the old one for me to
delete). Setup twice → idempotency; doctor snapshot.

**3. Automatable slices of C** — everything in Part C that needs no live
agent: export-sweep check (seed via a planted fixture log), capture switch,
`doctor --paths`, gap_ms presence via a planted claude-format log. Then
**PAUSE #1**: print the manual capture matrix (which cells I should exercise,
one line each with the exact ask), and wait for my "done". When I report
back, verify each exercised cell per the plan (rows, pricing, PII grep, row
sanity, live-vs-import attribution) and the Kiro dedupe if I ran two
sessions.

**4. Parts D + E** — every read surface including the v0.17–v0.22 additions
(prices workflow with a real retroactive reprice spot-check, attention
attested-vs-derived, CSV text-parity, cleanup allowlist/never-list, exit
codes), then the cost-impact loop. Where a step needs a live agent session
(Part E step 2), fold it into **PAUSE #2** along with the resolver-precedence
session — batch my manual asks, don't dribble them.

**5. Part F** — fleet study with one simulated second machine; bundle
hostname/username grep; double-import idempotence; coverage + paired delta +
refusal below min-n; unenrolled legacy check.

**6. Part G** — all invariants: determinism double-runs, fail-open chmod,
truncated tail, corrupt policy, offline sweep, PII sweep, no-scheduler,
portable-wiring greps + clone-simulation + planted-absolute migration,
launcher-mode round-trip + `CAGE_RUN_PYTHON=1`, local pyz build + `(zipapp)`
label + report byte-parity, docs hygiene (root contents, archive links,
CHANGELOG links, CLAUDE.md lifecycle rule), version/README consistency.

**7. Close:** complete the findings file (every row resolved), tick the
plan's boxes for this run, produce the run record
(`manual/findings-v<version>.md` is the artifact I'll archive as
`docs/archive/v<version>-full-test-run.md` at the next release), verify the
real-ledger snapshot delta, and print the closing summary: pass/fail per
part, bugs fixed in tree (file list), open findings ranked, and exactly what
awaits my review.

## PAUSE discipline

At each PAUSE: stop completely, list the manual steps as a numbered
copy-paste-friendly block (exact folder, exact suggested prompt per agent,
which agents/surfaces), and wait. Never simulate a manual session or pass a
planted log off as live capture — planted logs are fine for parser checks
and are labelled as such in findings; live-capture cells they are not.

## Constraints (hard)

- No commits/tags/pushes/publishes; no `uv publish`/twine ever.
- Fixes stay within cage law ($0/stdlib, determinism, fail-open writes, typed
  `CageError` reads, four agents, additive-only schema, method sacred).
- Don't modify the test plan's checklist items mid-run — if a step is wrong
  for this version, findings row + proposed plan edit in the summary.
- Real `~/.cage` is sacred: read it, snapshot it, never write to it except
  via the plan's two deliberate steps.
- Skill/steering assets only via skillgen fragments (if a fix touches CLI
  text: regen + `--bless`).

## Acceptance criteria (self-check before finishing)

- [ ] Plan boxes ticked or N-A'd for every part; findings file complete.
- [ ] `just test` green at the END of the run (post-fixes), S1–S13 green,
      skillgen clean.
- [ ] Real-ledger snapshot delta fully explained.
- [ ] All determinism/PII/fail-open checks pass; any exception is a ranked
      finding, not a footnote.
- [ ] Closing summary printed; working tree review-ready; zero commits.
