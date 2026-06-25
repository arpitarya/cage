# Task: unified hookless, MCP-less metering for ALL four agents

## Hard invariant (read first)

Cage is a multi-agent ledger. **Every feature must support all four agents — Claude
Code, Codex, Copilot, Kiro.** A solution that meters only one or two is incomplete
and will be rejected. This task delivers a hookless + MCP-less metering path that is
first-class for all four. Read `docs/cage-plan.md` §5 / §9.5, `CLAUDE.md`, and
`cage/pointers.py` (which already states Copilot/Kiro have no usage transcript)
before starting.

## The honest mechanism split (build around this, don't fight it)

There are two hookless mechanisms; neither alone covers four agents, so expose both
under one surface:

1. **Log/transcript import** — pull token usage from files the agent already writes
   to disk. Works only where a usage log exists:
   - Claude Code → `~/.claude/projects/**/*.jsonl` (`message.usage`) — parser exists
     (`transcript.parse_calls`).
   - Codex → `~/.codex/**/rollout-*.jsonl` — parser exists (`transcript.parse_codex_calls`,
     `cage import-codex`).
   - Copilot / Kiro → **verify empirically** whether either persists token usage
     anywhere on disk (VS Code Copilot logs, Kiro session store). If a real usage
     signal exists, write a parser for it. If it does NOT (the likely case per
     `pointers.py`), do not fake one.
2. **Proxy** (`cage proxy` / `cage meter -- <cmd>`) — wire-level, needs no hooks, no
   MCP, no on-disk log. The universal fallback that covers all four, and the *only*
   hookless option for any agent that doesn't log usage.

## What to build

1. **One unified command: `cage import --agent <claude|codex|copilot|kiro|all>`**
   (wire in `cli.py`, implement in `clicmds.py`). `--all` is the default.
   - Per agent, dispatch to a small **source adapter** (one function/class each) with
     a uniform contract: discover candidate files → parse → return call rows.
     Refactor existing `import-codex` to be the Codex adapter; add a Claude adapter
     wrapping `transcript.parse_calls` + `paths.claude_home()`. Keep `import-codex`
     working as an alias for back-compat.
   - For an agent that **has** a usable log: import via `hooks.append_new` (idempotent
     by call id — re-running must never double-count). Print
     `✔ <agent>: imported N call(s) from M file(s).`
   - For an agent with **no** importable log (Copilot/Kiro, unless you proved
     otherwise): do not error and do not silently skip. Print a clear, copy-pasteable
     instruction, e.g. `· copilot: no on-disk usage log — meter via the proxy: cage meter -- <cmd>`
     so the user is never left thinking the agent is unsupported.
   - `--path <dir|file>` override and `--project <dir>` filter (resolve the agent's
     project slug; if the slug rule is uncertain, verify it against the real
     directory before hard-coding, else default to scanning all and document it).
   - `--since <days>` bound, defaulting to `constants.SINCE_WINDOW_DAYS` (reuse the
     constant — no new literal).

2. **Per-agent status in `cage doctor`.** Show a four-row metering matrix: for each
   agent, whether it's metered via hook / proxy / import, and if none, the exact
   command to enable hookless capture. When hooks/MCP are unavailable, doctor must
   point at `cage import` and `cage proxy` rather than only flagging hooks missing.

3. **Docs.** Add a "Restricted orgs (no hooks, no MCP)" section to the agents/wiring
   doc: the two mechanisms, the per-agent coverage table (import vs proxy), and that
   losing MCP costs only the agent-facing read surface (CLI still reads the ledger).

## Constraints (cage law)

- **Additive, never a replacement.** Hooks + MCP remain the default, preferred path
  (real-time capture, `SessionStart` budget banner). Hookless `import`/proxy is a
  fallback and a convenience that runs *alongside* hooks — do NOT remove, deprecate,
  or alter the hook entrypoints. Both on at once must be safe (idempotent
  `append_new` already guarantees no double-count); add a test proving import is a
  no-op when the hook already recorded the same turns.
- **$0 / stdlib only.** `dependencies = []`. No non-stdlib imports.
- **All four are first-class.** No code path may treat Claude Code as the default and
  the rest as afterthoughts. The adapter registry must enumerate all four.
- **Fail-open + idempotent.** Malformed file → skip, never raise. Re-import → no-op.
- **Determinism.** Same inputs + same policy ⇒ byte-identical ledger. `--since` reads
  the clock for *filtering* only, never into a stored row.
- **PII / counts-only.** Token counts only, never prompt bodies — don't widen what any
  parser reads out of a log.
- **Reuse, don't fork.** Build on `transcript.parse_calls`,
  `transcript.parse_codex_calls`, `paths.*_home`, `hooks.append_new`.

## Acceptance

- `tests/` covers, **for each of the four agents**: the adapter is registered and
  reachable via `cage import --agent <x>`; agents with a log import fixture rows with
  correct token counts and are idempotent on re-import; agents without a log emit the
  proxy-instruction line (asserted) and exit 0. Plus `--project` filtering and a
  malformed-file-tolerated case.
- `just test` stays green (112 passing); no existing plan-number assertion changes.
- `cage doctor` renders the four-agent metering matrix.
- PR description includes a manual check: with hooks uninstalled, `cage import --all`
  populates the ledger for the log-bearing agents and prints proxy guidance for the
  rest; `cage report` then shows correct spend.

## Out of scope

No daemon/live-tail, no network, no fabricating a usage signal an agent doesn't emit.
If Copilot/Kiro genuinely don't log usage, the proxy instruction IS the supported
hookless path for them — make that explicit, don't paper over it.
