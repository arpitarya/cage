# Claude Code prompt — implement hookless metering for all four agents

Self-contained. Paste into Claude Code from the cage repo root. This merges both
hookless tasks (`add-import-claude-hookless-metering.md` + `unified-hookless-metering-
all-agents.md`) into one implement-ready spec. **Scope is the per-dev hookless path
only — the org gateway is NOT part of this prompt.**

---

## Context

cage is a *flux*: a $0, stdlib-only, deterministic append-only ledger for LLM token
traffic. One ledger, many agent surfaces. Read `docs/cage-plan.md` (§5, §9.5, §3,
§10) and `CLAUDE.md` before touching the metering or substrate contract.

**Hard invariant — non-negotiable:** every cage feature supports all four agents —
**Claude Code, Codex, Copilot, Kiro.** Anything that can't reach an agent must print
that agent's supported fallback, never silently skip it.

**Additive, never a replacement:** hooks + MCP stay the default path (real-time
capture, `SessionStart` budget banner). This runs *alongside* hooks — do NOT remove,
deprecate, or alter the hook entrypoints. A call metered by both a hook and an import
must dedupe by id (no double-count).

**Mechanism split (design around it):** log/transcript import only works where the
agent writes usage to disk — Claude Code (`~/.claude/projects/**/*.jsonl`) and Codex
(`~/.codex/**/rollout-*.jsonl`). Per `cage/pointers.py`, **Copilot and Kiro do not
expose a usage transcript** — verify empirically; if confirmed, their hookless path is
the proxy (`cage meter -- <cmd>`), not import.

**Reusable machinery:** `transcript.parse_calls`, `transcript.parse_codex_calls`,
`paths.claude_home()/codex_home()/kiro_home()`, `paths.claude_project_slug()`,
`hooks.append_new()` (idempotent by call id), `ledger.since_cutoff()`,
`policy.price_match()`, `agents.SURFACES`.

## Already implemented — DO NOT redo (verify, build on)

- **`cage import-claude`** — per-dev Claude hookless import from `~/.claude/projects`
  with `--path`/`--project`/`--since`, fail-open per file, idempotent. Tests:
  `tests/test_import_claude.py`.
- **`cage import-codex`** — the Codex on-disk import (separate command).
- **Pricing family-fallback** — `policy.price_match` (exact/family/none) + `report`
  surfaces UNPRICED and "≈ priced by family". Use price_match-priced model strings in
  new tests so a $0 never masks a broken import.
- **`cage doctor`** prints only a Claude-only hint today — not yet a four-agent matrix.

## What to build

1. **Umbrella `cage import [--agent claude|codex|copilot|kiro|all]`** (default `all`),
   wired in `cli.py` → `clicmds.py`. Dispatch to per-agent adapters; treat the existing
   `import-claude`/`import-codex` as the Claude/Codex adapters and keep them working as
   aliases. Pass through `--path`/`--project`/`--since` where they apply. Print one
   line per agent: `✔ <agent>: imported N call(s) from M file(s).`
2. **Copilot & Kiro — explicit fallback, never silent skip.** If (verify first) they
   have no on-disk usage log, `cage import --agent copilot` / `kiro` and the `--all`
   summary print the exact supported path, e.g.
   `· copilot: no on-disk usage log — meter via the proxy: cage meter -- <cmd>`. If
   either *does* persist usage, write a real adapter instead.
3. **`cage doctor` four-agent metering matrix** — replace the Claude-only hint with one
   row per agent (hook / proxy / import status, plus the exact command to enable
   hookless capture if none). Reuse `agents.SURFACES` so the agent list stays canonical.

## Cage law (do not violate)

- All four agents first-class — adapters + tests enumerate Claude Code, Codex, Copilot,
  Kiro.
- Additive — hooks/MCP and the existing import commands keep working unchanged.
- $0 / stdlib only — `dependencies = []`, no non-stdlib imports.
- Counts-never-content — token counts only, never prompt bodies.
- Fail-open + idempotent — malformed file skipped never raised; re-import is a no-op.
- Determinism — same inputs + same policy ⇒ byte-identical ledger; `--since` reads the
  clock for filtering only, never into a stored row. Reuse `constants.SINCE_WINDOW_DAYS`
  (no new literal).

## Acceptance

`tests/` cover, **for each of the four agents**: reachable via `cage import --agent <x>`;
log-bearing agents (claude, codex) import fixture rows with correct token counts and are
idempotent on re-import (incl. a no-op when a hook already recorded the same turns);
no-log agents (copilot, kiro unless proven otherwise) emit the asserted proxy line and
exit 0; `--all` runs every adapter; existing `import-claude`/`import-codex` tests still
pass; `cage doctor` renders the four-agent matrix. `just test` stays green (112+
passing) with no changes to existing plan-number assertions.

## Working agreement

- **Plan before code.** Write a short plan (files touched, the dispatch + adapter
  mapping, the Copilot/Kiro fallback line, the doctor matrix, the test list) and stop
  for my review. Do not write code until I approve.
- **Empirically verify** Copilot/Kiro on-disk logging before claiming none — report
  what you found.
- **Deliverable:** approved plan → implementation + tests → `just test` output and a
  `cage import --all` / `cage doctor` run on a fixture or the test repo → a summary of
  what each of the four agents resolves to (import vs proxy).

## Out of scope

The org gateway, any daemon/live-tail, any network, and fabricating a usage signal an
agent doesn't emit. If an agent can't be captured without endpoint changes you don't
control, say so — don't claim coverage.
