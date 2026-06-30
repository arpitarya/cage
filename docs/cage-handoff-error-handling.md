# Handoff: cage error-handling hardening

**One-liner:** Add the one thing cage's otherwise-mature error handling lacks — a typed `CageError` rendered cleanly at the CLI boundary (so an expected failure is an `error:` line, not a raw traceback) and a documented+tested exit-code contract — while *verifying and locking down* (not rewriting) the existing constitutional fail-open write paths and the agent/MCP boundary.
**Owner / executor:** Claude Code
**Status:** Ready to build
**Stress-tested:** Challenged hard on "cage's error handling is already mature/constitutional — don't regress 30 tuned fail-open blocks for cosmetic gain." **Survives only as additive work:** add the typed-error path at the CLI boundary + tests + docs; do NOT rewrite existing fail-open `except` blocks. Typed-error ceremony risk → constrained to ONE `CageError` class, no hierarchy. Scope ("IDE/agent errors") → bounded to verifying the existing agent boundary (hooks already fail-open; MCP returns isError; wiring fails gracefully) and adding tests, not reworking it. Residual risk: near-zero — this packet mostly formalizes + tests what cage already does, plus the CLI typed-error gap.

## 1. Context & background
cage already has strong, deliberate error handling: ~64 documented fail-open markers on write paths, every broad `except` carries `# noqa: BLE001 — <reason>`, hooks are all `try/except → exit 0`, `cli.py main()` catches `KeyboardInterrupt → 130`, and `CAGE_DEBUG`/`cage debug` exists for tracing. The one real gap: `main()` has **no typed/expected-error path** — an unexpected exception (or an expected failure like a bad `--since`, a malformed policy, an unknown query id) dumps a raw traceback at the user instead of a clean `error:` line. This packet closes that gap and formalizes the exit-code contract with tests, and verifies the agent/MCP boundary is crash-proof — *without disturbing the constitutional fail-open surface*. Sibling packet: `fux-handoff-error-handling.md` (fux has the bigger gap — its hooks aren't fail-open; cage's already are).

## 2. Definition of done
- [ ] **One typed error**, `CageError(Exception)`, defined once (e.g. `cage/errors.py`, ≤ a few lines). Expected user-facing failures raise `CageError("<clear message>")`.
- [ ] **`cli.py main()` renders it cleanly**: extend the existing try (which already handles `KeyboardInterrupt → 130`) so `CageError → "error: <msg>"` to stderr → `1`, and any other unexpected exception → terse `error: <msg>` → `1` with the full traceback shown only under `CAGE_DEBUG=1`.
- [ ] **Expected-failure sites raise `CageError`** instead of leaking raw exceptions: a malformed/missing policy surfaced to a *read* command, an unknown `cage query` id (today it suggests closest ids — keep that, but ensure no traceback), a bad `--since`/`--scope` value, a non-repo for a git-dependent read. Enumerate during Explore; confirm the list before wiring.
- [ ] **Exit-code contract documented + enforced**: `0` ok · `1` error (CageError/unexpected) · `2` reserved if/where cage uses a blocking gate (confirm; cage's `verify` is report-only exit 0 — do not change that) · `130` interrupted. Document in the README/`docs` + propose for `CLAUDE.md`; assert with tests.
- [ ] **Fail-open write paths verified (not rewritten)**: a test/audit confirms the write-path entrypoints (`ledger.append`, `meter`/`metering`, hooks, `originrecord`, `notessync`, `proxy`) return/exit without raising on a forced internal error, AND that the swallow is reachable via `CAGE_DEBUG` (no truly silent swallow). Add tests where missing; only ADD a `CAGE_DEBUG` trace if a swallow site currently has none.
- [ ] **Agent/MCP boundary verified**: `cage/mcpserver.py` returns `isError` tool results (not a crash) on malformed input across all dispatch paths; `<agent>wire.py` install/uninstall and `setupcmd.py` surface failures as a clear message + nonzero return with no half-written settings/`.mcp.json`. Add tests.
- [ ] `just test` green (update the "N passing" count in README + the `CLAUDE.md` `just test` comment); CHANGELOG entry added.
- [ ] Docs updated (see §9.5).

## 3. Scope
**In scope:** new `cage/errors.py` (`CageError`); `main()` typed-error + unexpected-error rendering (additive to the existing KeyboardInterrupt handling); raising `CageError` at the confirmed expected-failure sites; exit-code contract doc + tests; a *verification* pass + tests over existing fail-open write paths and the MCP/wiring boundary; `CAGE_DEBUG` trace added only at any swallow site currently lacking one.

**Out of scope (explicit) — do NOT do:**
- Do **not** rewrite, "clean up", or restructure existing fail-open `except` blocks. They are constitutional and tuned. Touch one only if it has a genuinely silent swallow with no `CAGE_DEBUG` path — and then only ADD the trace, nothing else.
- Do **not** change `cage verify`'s report-only-always-exit-0 contract, or convert any write path into a raising path.
- Do **not** add an exception hierarchy, logging framework, retries, or new deps (`dependencies = []` is sacred).
- Do **not** alter the four-agents wiring behavior, the ledger/attribution/provenance engine logic, or policy/constants/contract layers — only their *error surfacing* at the boundary, and only where it leaks a traceback today.
- Do **not** touch the skillgen renderer packet's work.

## 4. Current state
- Repo: `/Users/arpitarya/my_programs/cage`
- Read first: `cage/cli.py` (`main`, ~line 340, already has the `KeyboardInterrupt` handler), `cage/hooks.py` (fail-open reference), `cage/mcpserver.py`, `cage/metering.py`, `cage/ledger.py`, `cage/proxy.py`, `cage/originrecord.py`, `cage/doctorcmd.py`, `cage/setupcmd.py`, `cage/agents.py` + a `<agent>wire.py`, `CLAUDE.md`, `docs/cage-plan.md`, `README.md`, `CHANGELOG.md`.
- Today: `dependencies = []`, stdlib-only, deterministic, fail-open write paths, `CAGE_DEBUG=1` + `cage debug` for tracing, `cage doctor` for setup health, four agents always.

## 5. Technical approach (decided)
- **Additive, boundary-only.** The only structural change is `cage/errors.py` + the `main()` render path. Everything else is raising `CageError` at leak sites + tests + docs.
- **`CageError`** = thin `class CageError(Exception): pass`. `main()` (keep the existing KeyboardInterrupt → 130) gains: `except CageError as e: print(f"error: {e}", file=sys.stderr); return 1` and a final `except Exception as e:` → terse `error:` + 1, full traceback only under `CAGE_DEBUG`.
- **Reuse `CAGE_DEBUG`** as the single debug switch for both the CLI traceback and any newly-added swallow trace — no new env var.
- **Verification over rewrite** for fail-open: prove with tests that forced internal errors don't propagate and aren't silent; leave the working code alone.

## 6. Non-negotiables / constraints
- **Style/patterns:** cage house style; three-audit-layers discipline; every broad catch keeps its `# noqa: BLE001 — <reason>`; follow `CLAUDE.md`.
- **Use:** stdlib only (`os`, `sys`, `traceback`). **Avoid:** any runtime dep (`dependencies = []`), logging framework, retries, LLM/network.
- **Constitutional fail-open is preserved and untouched** except additive `CAGE_DEBUG` traces at genuinely-silent sites.
- **Determinism:** no change to derived views/numbers; tests still assert exact plan figures.
- **Four agents always:** boundary error work must keep claude/codex/copilot/kiro first-class.
- **Release discipline:** add a CHANGELOG entry; bump `__version__` ONLY if cutting a release, and never publish locally (CI/GitHub-release is the sole publisher).
- **Do not touch:** the metering/ledger/attribution/provenance engine logic, policy/constants/contract layers, `cage verify`'s exit-0 contract, the skillgen work.

## 7. Dependencies & prerequisites
- Python ≥3.11. No env/services/secrets. `CAGE_DEBUG` already exists (reused, not new).

## 8. Edge cases & risks
- **Malformed `policy.toml`** hit by a read command → `CageError("policy.toml: <parse error>")`, exit 1, no traceback (note: `doctorcmd` already reports policy parse errors — keep that; this is for *other* read commands).
- **Unknown `cage query` id** → keep the closest-id suggestion, ensure exit 1 + no traceback.
- **Bad `--since`/`--scope`** → `CageError`, exit 1.
- **Git-dependent read in a non-repo** (origin/verify already fail-open/report-only) → no change; confirm no traceback.
- **Forced error inside a write path** (ledger/meter/hook) → must NOT propagate; test it; confirm `CAGE_DEBUG` surfaces it.
- **Malformed MCP request** → `isError`, server stays up.
- **Unwritable `.mcp.json`/settings during wiring** → clear message + nonzero, no partial file.
- RISK: over-eager `CageError` conversion swallows a real bug as a "clean error." Mitigate by keeping the unexpected-exception branch (full traceback under `CAGE_DEBUG`) and only converting confirmed user-facing sites.

## 9. Testing & validation
- **Must test:** (a) `main()` maps `CageError`→1, `KeyboardInterrupt`→130, unexpected→1 (traceback only under `CAGE_DEBUG`); (b) a read command on a malformed policy / bad `--since` exits 1 with `error:` and no traceback; (c) forced internal error in `ledger.append`/`meter`/a hook does not raise and (where applicable) traces under `CAGE_DEBUG`; (d) MCP dispatch returns `isError` on malformed input; (e) `cage verify` still exits 0 (unchanged).
- **Verify locally:** `just test` (update count) · `just demo` (engine untouched, plan numbers intact) · `cage --version` · manually `cage query nonsense` and `CAGE_DEBUG=1 cage query nonsense`.
- **Manual check:** force an exception in a hook path and confirm the session/turn is unaffected (exit 0), with a `CAGE_DEBUG` trace.

## 9.5 Documentation impact
- [x] **CHANGELOG.md** — required (cage constitution): add the error-handling entry, newest first.
- [x] **README** — required: brief "What's new" line + the exit-code contract / `CAGE_DEBUG` note; update the "N tests passing" count.
- [x] **docs/cage-plan.md** — required: note the typed-error/exit-code contract (boundary-only, fail-open preserved).
- [x] **AI agent files (CLAUDE.md)** — required, ⚠️ PROPOSE for review (do not auto-write): add "expected failures raise `CageError` → clean `error:` + exit 1; exit codes 0/1/130; fail-open write paths unchanged; `CAGE_DEBUG` for traces". Surface the diff.
- [ ] **MCP/contract docs** — N/A: no tool contract change (behavior on malformed input is clarified, not changed) — state this.
- [ ] **ADR** — optional one-liner: "error surfacing is boundary-only; fail-open internals preserved."

## 10. Open questions
- OPEN QUESTION: does cage use exit `2` anywhere as a blocking gate today? (`verify` is exit-0 report-only.) Confirm during Explore so the documented contract is accurate — don't invent a `2` that isn't used.
- OPEN QUESTION: enumerate the exact expected-failure sites that should raise `CageError` vs already handled by `doctor`/fail-open — confirm the list before wiring; keep it minimal and user-facing.
- OPEN QUESTION: are there any genuinely-silent swallow sites (broad `except` with no `CAGE_DEBUG`/`_trace_entry` path)? If yes, list them — adding the trace is in scope; rewriting the block is not.
