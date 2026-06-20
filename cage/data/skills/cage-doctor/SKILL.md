---
name: cage-doctor
description: Verify the Cage cost/savings ledger is set up correctly and working in this project ($0, deterministic). Trigger when the user asks to check, verify, diagnose, or "is cage working / set up", or before relying on cage numbers.
---

# /cage-doctor — verify Cage is set up and working

Cage is a *flux*: a deterministic, $0 ledger of LLM cost and per-tool savings. Before
trusting its numbers (or when the user asks "is cage set up / working"), confirm the
setup with the built-in health check — never eyeball files yourself.

## How to respond

1. Run `cage doctor` from the project root and show its output verbatim — it is a
   pre-formatted, line-per-check report. Add `--json` if you need to branch on the
   result programmatically.
2. The command exits **non-zero only on a hard failure** (`✗`), so you can gate on it.
   Read the per-check levels:
   - `✔ ok` — that check passed.
   - `· warn` — optional/expected-missing (e.g. graphify interceptor not installed, or
     `bin/` not yet on PATH in this shell). Cage still works.
   - `✗ fail` — broken (no `.cage/`, policy won't parse, ledger not writable).
3. **Map each finding to the fix**, don't just relay it:
   - `footprint ✗ no .cage/` → run **`cage adopt`** (full setup) or `cage init`.
   - `hooks · none wired` → `cage adopt` or `cage hooks install`.
   - `interceptor · bin/ not on PATH` → tell the user to open a new shell (the PATH
     line was added to their shell rc).
   - `policy ✗` / `ledger ✗` → surface the exact error string from the detail.
4. If everything is `✔`/`·`, say Cage is working and point at `cage report` /
   `cage matrix` / `cage doctor` for ongoing use.

## Don't

- Don't guess setup state by reading `.cage/` or `settings.json` by hand — run
  `cage doctor`; it is the single source of truth and writes nothing (its ledger
  round-trip uses a throwaway temp dir).
- Don't claim Cage is working if any check is `✗`.
