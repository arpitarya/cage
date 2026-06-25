# Task: add `cage import-claude` — meter Claude Code with no hooks and no MCP

## Why

Some orgs block Claude Code hooks and/or MCP servers by policy. Today the **only**
path that ingests Claude Code token usage is the `SessionEnd` hook
(`hooks.session_end` → `transcript.parse_calls`). If hooks are blocked, the ledger
never fills — even though Claude Code still writes its session transcripts to disk.
MCP being blocked is irrelevant to capture (it's only the read surface; the `cage`
CLI reads the ledger directly), so this task is about the hook gap only.

The fix is a standalone ingester that parses the transcripts that already exist on
disk — runnable by hand or on a schedule (cron / CI / login script) — mirroring the
existing `cage import-codex`. Almost all the machinery exists:
`transcript.parse_calls()`, `paths.claude_home()` (honors `CLAUDE_CONFIG_DIR`),
`hooks.append_new()` (idempotent by call id). Read `cmd_import_codex` in
`clicmds.py` as the template, and `docs/cage-plan.md` §5 / §9.5 before starting.

## What to build

1. **`cage import-claude` subcommand** (wire in `cli.py`, implement
   `cmd_import_claude` in `clicmds.py`), mirroring `import-codex`:
   - Default source: `paths.claude_home() / "projects"`. Each subdir is a
     slugified project path; transcripts are `<session-uuid>.jsonl`. Discover with
     a recursive glob (`**/*.jsonl`).
   - `--path <dir|file>` override (a specific transcript or a directory to scan),
     same shape as `import-codex`'s positional arg — match that ergonomics.
   - `--project <dir>` (optional): restrict to the current repo by resolving its
     Claude Code project slug, so a user can meter just this project's sessions
     instead of every project on the machine. Confirm the exact slug rule Claude
     Code uses (abs path with separators replaced) empirically against
     `~/.claude/projects/` before hard-coding it; if uncertain, default to scanning
     all and document it.
   - For each file: `hooks.append_new(root, transcript.parse_calls(f, session=<stem>))`,
     summing the count. Print `✔ imported N Claude call(s) from M transcript(s).`
     exactly in the `import-codex` style.

2. **Idempotency is the whole point.** Re-running must never double-count.
   `append_new` already dedupes by call id and `parse_calls` derives ids from each
   turn `uuid`, so this should hold for free — add a test that proves importing the
   same transcript twice yields the same ledger.

3. **Optional `--since <days>`** to bound a scan to recent transcripts, defaulting
   to `constants.SINCE_WINDOW_DAYS` (don't introduce a new literal — reuse the
   constant per the three-layer rule).

4. **Surface it as the no-hooks path.** Update `cage doctor` so that when metering
   hooks are *not* wired, it points the user at `cage import-claude` (and the proxy)
   instead of just flagging hooks missing. Add a short "Restricted orgs (no
   hooks/MCP)" note to the relevant doc (`docs/` agent/wiring section) explaining
   the two fallbacks: `cage import-claude` (pull transcripts) and `cage proxy`
   (wire-level), and that MCP loss only costs the agent-facing read surface.

## Constraints (cage law — do not violate)

- **Additive, never a replacement.** Hooks remain the default path; `import-claude`
  runs alongside them. Do not remove or change the hook entrypoints. Importing a
  transcript the hook already recorded must be a no-op (idempotent by call id).
- **$0 / stdlib only.** `dependencies = []`. No new non-stdlib imports.
- **Fail-open on ingest.** A malformed transcript line is skipped, never raises —
  `parse_calls` is already tolerant; keep the command tolerant of an unreadable
  file too.
- **Determinism.** Same transcripts + same policy ⇒ same ledger, byte-identical.
  No clocks in the recorded rows (ids carry the entropy; `--since` may read the
  clock for *filtering* only, never for a stored value).
- **PII.** Counts only — `parse_calls` already records token counts, never prompt
  bodies. Don't widen what's read out of the transcript.
- **Reuse, don't fork.** Call the existing `transcript.parse_calls`,
  `paths.claude_home`, `hooks.append_new`. Do not duplicate parsing logic.

## Acceptance

- `tests/` covers: (a) importing a fixture transcript records the expected call
  rows with correct token counts; (b) re-importing is a no-op (idempotent);
  (c) `--project` filtering selects only the matching slug; (d) a directory with a
  malformed `.jsonl` still imports the good files and doesn't raise.
- `just test` stays green (currently 112 passing); no existing plan-number
  assertion changes.
- Manual check documented in the PR description: with hooks uninstalled,
  `cage import-claude` populates `.cage/ledger/calls.jsonl` and `cage report`
  shows correct spend.

## Out of scope

No live tailing/daemon, no network, no new transcript format support beyond what
`parse_calls` already handles. Scheduling is the user's job (cron/CI) — just make
the command safe to run repeatedly.
