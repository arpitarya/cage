---
inclusion: manual
---
# Cage doctor — verify Cage is set up and working

This workspace meters LLM traffic into `.cage/` (a *flux*: $0, deterministic). When the
user asks to check / verify / diagnose Cage, or before relying on its numbers, confirm
the setup with the built-in health check — never eyeball files yourself.

1. Run `cage doctor` from the project root; show its output verbatim (one line per
   check). `cage doctor --json` for machine-readable output.
2. It exits non-zero only on a hard failure (`✗`). Levels: `✔ ok` passed ·
   `· warn` optional/expected-missing (cage still works) · `✗ fail` broken.
3. Map findings to fixes:
   - `footprint ✗ no .cage/` → `cage adopt` (or `cage init`).
   - `hooks · none wired` → `cage adopt` / `cage hooks install`.
   - `interceptor · bin/ not on PATH` → open a new shell.
   - `policy ✗` / `ledger ✗` → surface the exact error in the detail.
4. All `✔`/`·` → Cage is working; point at `cage report` / `cage matrix`.

Don't guess from raw files (`cage doctor` is the source of truth and writes nothing).
Don't claim Cage works if any check is `✗`.
