# Claude Code prompt: Cage end-to-end validation on a disposable repo

You are running a **validation pass** on cage — not fixing anything. The full spec is the
handoff at `docs/dummy-repo-test-handoff.md`, which packages the agent-executable subset of
`docs/dummy-repo-test-plan.md`. Read the handoff first and treat its Definition of Done,
Scope, and Non-negotiables as binding. Your job is to produce a ranked findings report, not
patches.

## Context to load first
- Read: `docs/dummy-repo-test-handoff.md`, then `docs/dummy-repo-test-plan.md` (§1, §2, §5,
  §6, §7 are what you execute).
- Read: `README.md` §"Works with any agent", `docs/debugging-capture.md`, `CLAUDE.md`.
- Confirm the harness: `cage --version` (expect 0.15.0), `python -c "import cage"` with no
  extras, `cage doctor` (note the active ledger path).

## Task
Execute the CLI-reachable and invariant portions of the test plan against a throwaway repo,
and write a ranked findings report. Specifically:
1. Baseline: `just test` in the cage repo — record pass/fail count.
2. Scaffold `/tmp/cage-testbed` (git init, a couple files, one commit), then
   `cage setup --project-only` and `cage setup --wire-only --<agent>` for each agent, and
   `cage setup --status`.
3. Populate the ledger: if any agent CLI is installed, do real CLI capture (plan §3) and
   confirm hook rows appear live; if none, seed synthetically (`cage demo` + a few
   hand-crafted rows for pricing/human/unpriced-model) and **label findings synthetic**.
4. Run every read/derive surface (plan §5) and record each outcome.
5. Run every invariant/adversarial check (plan §6) **with evidence** — byte-diffs for
   determinism, actual grep output for PII, actual return values for fail-open.
6. Run CLI-reachable provenance/git-hook checks (plan §7).
7. Write `/tmp/cage-testbed/CAGE-FINDINGS.md` using the plan §8 table schema, ranked
   P0/P1/P2, with a separate **"VS Code — human checklist (NOT RUN)"** section listing the
   extension steps you could not execute.

## Required workflow
1. **Explore** first — read the handoff and plan before touching anything; don't assume the
   CLI surface, confirm it against `cage --help` and the plan.
2. **Plan** — lay out the capture branch you'll take (real vs synthetic) based on which
   agent CLIs are present, list the commands you'll run, and pause for my confirmation
   before generating ledger traffic.
3. **Execute incrementally** — one plan section at a time; capture command output as you go
   so findings carry evidence, not assertions.
4. **Update docs to match** — this is a validation run, so code/docs stay unchanged. The one
   output is `CAGE-FINDINGS.md`. If a finding shows a doc (`dummy-repo-test-plan.md`,
   `debugging-capture.md`, `CLAUDE.md`) is factually wrong, PROPOSE the correction inside
   the findings file and flag it for my review — do not edit those files, and never
   silently rewrite steering files.
5. **Verify** before reporting done: every plan §5/§6 row has a verdict; every out-of-scope
   step is marked `NOT RUN` with a reason; the active ledger used was isolated (project
   `.cage/` or a scratch `CAGE_BASE`), not the real `~/.cage`.

## Constraints (hard)
- **Read-only on cage itself.** Do NOT modify cage source, the bundled `policy.toml`, or
  `tests/`. All mutation lives in `/tmp/cage-testbed` or a throwaway `CAGE_BASE`.
- **Do NOT simulate the un-runnable.** No mocking or faking a VS Code-extension run, and no
  pretending an uninstalled agent produced output. Mark it `NOT RUN` with the reason.
- **Do NOT fix bugs** — findings only. A failing check is a recorded finding, not a cue to
  patch cage or edit a test to make it pass.
- Stay offline for the $0/stdlib check. Keep `notes-sync`/`ledger-sync` dry-run; do not set
  `CAGE_NOTES_WRITE`. Do not write to `refs/notes/*`.
- Do not touch the user's real `~/.cage`, `~/.claude`, `~/.codex`, `~/.copilot`, `~/.kiro`
  (read-only for diagnosis).

## Acceptance criteria (self-check before finishing)
- [ ] `just test` result recorded.
- [ ] `/tmp/cage-testbed` scaffolded with `.cage/` and a commit.
- [ ] Ledger populated (real capture or clearly-labeled synthetic).
- [ ] Every plan §5 read surface run; outcome recorded.
- [ ] Every plan §6 invariant/adversarial check run with evidence and a pass/fail verdict.
- [ ] CLI-reachable §7 provenance checks run; `cage verify` confirmed exit 0.
- [ ] `CAGE-FINDINGS.md` written, ranked P0/P1/P2, with the VS Code human-checklist section.
- [ ] No cage source / policy / test files modified.

## Tests
The plan's checklists are the tests. Emphasize the adversarial cases in plan §6, since a
green `just test` already covers the happy path: determinism byte-diff, fail-open on a
truncated ledger shard, the unpriced-model $0 trap, `method` never reading `measured` on a
reconstructed matrix cell, PII grep of the ledger, and offline import.

## Guardrails
- Ask before: generating real agent traffic (it costs tokens), anything that could write to
  the user's global `~/.cage` or to `refs/notes`, or any irreversible action.
- If a plan step is ambiguous, or a finding contradicts a doc, STOP and ask / record it —
  do not guess or "helpfully" fix.
- If you find yourself about to modify cage source to make a check pass: stop. That's a
  finding, not a fix.
