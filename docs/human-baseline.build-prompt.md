# Build prompt — human baseline + tracking (hand to Claude Code)

> Copy everything below the line into Claude Code, run from the `cage/` repo root.

---

Implement the human-baseline + tracking feature for cage. The complete spec is
**`docs/human-baseline.design.md`** — read it in full first; it is the source of
truth and all section refs (§N) below point into it. Do not re-litigate the
decisions in §9 (A–F are settled); implement them as written.

## Non-negotiable constraints (cage law — violating any is a failed change)

- **`$0` / stdlib only.** `dependencies = []`. No new runtime dependency. Git is
  *shelled out to*, never imported as a library.
- **Deterministic derived views.** No clocks/RNG/network in any read path. Same
  `(ledger, policy, env)` ⇒ identical tables. `CAGE_HUMAN_RATE` is explicit config,
  and its provenance must print in output (§3.2).
- **`method` is sacred.** No estimate may render as `measured`. Human cost is
  `estimated` unless a real quote/timesheet; reconstructed cells stay `modeled`;
  `agent_active_minutes` is `estimated` (§5b.1).
- **Fail-open on every write path.** `ledger.append`-style: the git snapshot and
  any metering error return/omit, never raise (§5b.2).
- **Small modules.** ≤100 lines per module (≤50 for `*utils`-style). One job each.
- **PII / fintech guard (§5b.5).** Receipts/tasks store rates, SHA, diff *counts*,
  top-level dirs only — never commit messages, author name/email, file contents,
  or any human's comp/identity. No PII in error strings either.
- **Doc-sync in the same change (§8).** A change isn't done until `cage-plan.md`,
  `README.md`, `CLAUDE.md`, and `docs/human-baseline.design.md` status reflect it.

## Build in stages — after each stage run `just test` (or `python -m pytest -q`) and stop if red

**Stage 1 — substrate + converter (the safe refactor first).**
- `schema.py`: add `"minutes"` to `UNITS` (§2.1).
- New `cage/convert.py` (≤40 lines): single `saved_usd(receipt, call, pol)`
  dispatcher — `usd`→passthrough, `tokens`→model price, `minutes`→human rate,
  `ms`/`gco2`→`0.0` (§2.3).
- Refactor `roi.py` and `attribution.py` to route through `convert.saved_usd`;
  their output must be **byte-identical** before/after (snapshot test, criterion 2a).

**Stage 2 — human resolver + policy.**
- New `cage/human.py`: `human_alternative_usd(receipt, pol) -> (usd, method,
  confidence)` with the §3 precedence chain + confidence ladder; `minutes_to_usd`;
  per-agent rollup. `minutes_to_usd` honours `CAGE_HUMAN_RATE` (§3.2).
- `policy.py`: add `"human"` to merge sections, `human_rates()`, env override read.
- `data/policy.toml`: add `[human]`, `[human.tasks.*]`, `[human.confidence]` (§3.1).
- Tests: criteria 1, 2, 2b.

**Stage 3 — task record + git snapshot.**
- New `cage/tasks.py`: `tasks.jsonl` read/write (last-write-wins by `id`) + a
  fail-open git snapshot (`git rev-parse --short HEAD`, `--abbrev-ref HEAD`,
  `git diff --shortstat`); non-repo/detached ⇒ omit fields, never raise (§5b.2).
- Wire the snapshot into task close (`hooks.py` SessionEnd / `cage outcome`).
- Tests: criterion 10.

**Stage 4 — read surfaces (cost + time).**
- `cage human`: per-agent table with `saved $` **and** `saved hrs`, `conf`, and a
  `rate source: …` header; `--since/--task/--agent/--json/--html` (§4.1, §5b.1).
  `time_saved = human_minutes − agent_active_minutes`; allow negative.
- New `cage/trend.py` + `cage trend [--by week|month] [--metric cost|time|both]`
  (§5b.4) — pure derive over `ts`.
- `matrix.py`: human anchor row + `vs human` columns **behind `--human`**; without
  the flag, output is identical to today (snapshot vs `cage demo`, criterion 4).
- `serve.py`: "Agent vs human" + "Savings trend" panels; standalone `--html` writer
  (inline CSS, no CDN).
- `cli.py`/`clicmds.py`: wire `human`, `human-record`, `trend`, `matrix --human`,
  `--html`.
- Tests: criteria 3, 4, 5, 9.

**Stage 5 — verify + doc-sync.**
- Confirm all 10 criteria in §6 pass; `roi` stays tool-only (no `--include-human`).
- Run `just test`, `fux check` if present, and `cage demo` (its §4.4 tables must be
  unchanged).
- Update `cage-plan.md` (§4.5 + tasks.jsonl/time-saved), `README.md` (add `human`,
  `trend`), `CLAUDE.md` (architecture map: `human.py`, `convert.py`, `tasks.py`,
  `trend.py`; `[human]` policy; `CAGE_HUMAN_RATE`), and flip this design doc's
  status to *implemented*.

## Working rules

- Plan before code: show me the stage-1 file diffs and your test list before
  writing stage 2. Don't proceed past a red bar.
- Touch only what the spec names. No drive-by refactors, no speculative fields
  (the §5b.5 guard and §9 "still open" items are explicitly out of scope).
- Each new module gets a one-line docstring matching the house style, and lands
  with its test in the same stage.
- If anything in the spec is ambiguous or you'd deviate, stop and ask — don't guess.

Acceptance = all 10 criteria in §6 green, `cage demo` unchanged, docs synced, and
no new dependency in `pyproject.toml`.
