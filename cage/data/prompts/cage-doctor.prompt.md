---
description: Verify the Cage cost/savings ledger is set up correctly and working ($0, deterministic)
---
# Cage doctor — is Cage set up and working?

When the user asks to check / verify / diagnose Cage, or before relying on its numbers,
confirm the setup with the built-in health check — never eyeball files yourself.

1. Run `cage doctor` from the project root and show its output verbatim (one line per
   check). Use `cage doctor --json` to branch programmatically.
2. It exits non-zero only on a hard failure (`✗`). Per-check levels:
   - `✔ ok` passed · `· warn` optional/expected-missing (cage still works) ·
     `✗ fail` broken.
3. Map findings to fixes — don't just relay them:
   - `footprint ✗ no .cage/` → run `cage setup` (or `cage init`).
   - `hooks · none wired` → `cage setup` / `cage setup --wire-only --<agent>` (opt-in).
   - `interceptor · bin/ not on PATH` → open a new shell.
   - `policy ✗` / `ledger ✗` → surface the exact error in the detail.
4. All `✔`/`·` → Cage is working; point at `cage report` / `cage matrix`.

Don't guess from raw files (`cage doctor` is the source of truth and writes nothing).
Don't claim Cage works if any check is `✗`.
