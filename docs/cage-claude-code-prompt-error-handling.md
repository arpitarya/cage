# Claude Code prompt: cage error-handling hardening

You are hardening error handling in the **cage** repo. The full spec is in `cage-handoff-error-handling.md` — read it first and treat its Definition of Done, Scope, and Non-negotiables as binding. **This is additive, boundary-only work — cage's fail-open surface is constitutional and must NOT be rewritten.**

## Context to load first
- Read: `cage/cli.py` (`main`, ~line 340 — already handles `KeyboardInterrupt → 130`), `cage/hooks.py` (the fail-open reference), `cage/mcpserver.py`, `cage/metering.py`, `cage/ledger.py`, `cage/proxy.py`, `cage/originrecord.py`, `cage/doctorcmd.py`, `cage/setupcmd.py`, `cage/agents.py` + one `<agent>wire.py`, `CLAUDE.md`, `docs/cage-plan.md`, `CHANGELOG.md`.
- Respect `CLAUDE.md`, `dependencies = []`, stdlib-only, determinism, four-agents-always, and the release discipline (never publish locally).

## Task
1. Add `cage/errors.py` with a single thin `class CageError(Exception)`.
2. Extend `cli.py main()` (keep the existing `KeyboardInterrupt → 130`): `CageError → "error: <msg>"` + `1`; any other exception → terse `error: <msg>` + `1`, full traceback only under `CAGE_DEBUG=1`.
3. Raise `CageError("<clear message>")` at the confirmed expected-failure sites (malformed policy hit by a read command, bad `--since`/`--scope`, unknown `cage query` id while keeping the closest-id suggestion) instead of leaking tracebacks. Enumerate during Explore; confirm the list with me before wiring.
4. Document + test the exit-code contract (0/1/130; confirm whether `2` is used anywhere — `verify` is report-only exit 0, leave it).
5. VERIFY (don't rewrite) the fail-open write paths: add tests proving forced internal errors in `ledger.append`/`meter`/hooks don't propagate and aren't silently swallowed (reachable via `CAGE_DEBUG`). Only ADD a `CAGE_DEBUG` trace at a swallow site that genuinely lacks one.
6. VERIFY the agent/MCP boundary: `mcpserver.py` returns `isError` on malformed input; `<agent>wire.py`/`setupcmd.py` fail cleanly with no half-written settings. Add tests.

## Required workflow
1. **Explore** `main()`, the fail-open write paths, MCP dispatch, and wiring. Identify the expected-failure leak sites and any genuinely-silent swallow sites. Do not assume — list them.
2. **Plan** — show the `errors.py`, the `main()` extension, the `CageError` raise sites, the verification tests, and any `CAGE_DEBUG` trace additions. **Pause for my confirmation**, especially the `CageError` site list and whether `2` is a used exit code.
3. **Implement incrementally** — `errors.py` → `main()` extension → `CageError` raises → verification tests → minimal `CAGE_DEBUG` trace additions only where missing. Keep `just demo` numbers intact and the build green.
4. **Update docs to match** — CHANGELOG (newest first), README ("What's new" + exit-code/`CAGE_DEBUG` note + test count), `docs/cage-plan.md`. For `CLAUDE.md`: PROPOSE the error-contract rule as a diff for my review — do NOT auto-write it. MCP-contract docs N/A — say so.
5. **Verify** — `just test` (update the passing count in README + the `CLAUDE.md` `just test` comment), `just demo`, `cage --version`, and manually `cage query nonsense` vs `CAGE_DEBUG=1 cage query nonsense`. Don't report done until green.

## Constraints (hard)
- Use: stdlib only (`os`, `sys`, `traceback`). Do NOT use: any dependency (`dependencies = []` is sacred), logging framework, retries, or an exception hierarchy beyond `CageError`.
- **Do NOT rewrite existing fail-open `except` blocks.** Touch one only to ADD a `CAGE_DEBUG` trace if it's genuinely silent — nothing else.
- **Do NOT** change `cage verify`'s exit-0 report-only contract, convert any write path into a raising path, or alter the ledger/attribution/provenance engine, policy/constants/contract layers, or four-agents wiring behavior.
- Reuse `CAGE_DEBUG` — do not add a new debug env var.
- Every broad `except Exception` keeps/gets a `# noqa: BLE001 — <reason>` comment.
- Do NOT bump `__version__` or publish — ask if a release seems needed.
- Do NOT touch the skillgen renderer work.

## Acceptance criteria (self-check before finishing)
- [ ] `main()`: `CageError`→1, `KeyboardInterrupt`→130, unexpected→1 (traceback only under `CAGE_DEBUG`) — tested.
- [ ] A read command on malformed policy / bad `--since` exits 1 with `error:` and no traceback — tested.
- [ ] Forced internal error in `ledger.append`/`meter`/a hook does not propagate and (where applicable) traces under `CAGE_DEBUG` — tested.
- [ ] MCP dispatch returns `isError` on malformed input; `cage verify` still exits 0 — tested.
- [ ] No existing fail-open block rewritten; `just demo` numbers unchanged.
- [ ] CHANGELOG + README + cage-plan updated; `CLAUDE.md` rule proposed for review.

## Tests
Add tests covering: `main()` exit-code mapping; read-command `CageError`→clean exit 1; write-path non-propagation + `CAGE_DEBUG` trace; MCP isError; `verify` exit-0 unchanged. Run via `just test`.

## Guardrails
- Ask before: converting any site to `CageError` beyond the confirmed list, adding a trace to (let alone editing) any fail-open block, changing any exit code, or bumping the version.
- Do not auto-edit `CLAUDE.md` — propose the diff.
- If a requirement is ambiguous (is `2` used? which sites raise `CageError`? any silent swallows?), STOP and ask rather than guessing.
