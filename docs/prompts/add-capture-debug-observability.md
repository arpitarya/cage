# Claude Code prompt — add capture debugging/observability to cage

Self-contained. Paste into Claude Code from the cage repo root.

## Why (the actual problem)

Cage's capture path is **fail-open and silent everywhere** — every hook entrypoint and
import wraps its work in `except Exception: pass`, and `importcmd.run` returns
skip-reason strings that get discarded when a hook calls it (hook stdout is dropped).
Field reality: across four agents, capture silently did nothing for days and there was
**no way to tell whether a hook even fired**, whether the `.cage` cwd guard skipped it,
or whether a parser raised. We diagnosed it only by hand-instrumenting hooks with marker
files. Bake that observability into cage permanently. Read `cage/hooks.py`,
`cage/importcmd.py`, `cage/doctorcmd.py`, `cage/paths.py` (the `Footprint.state` dir),
`cage/policy.py`, and `CLAUDE.md` first.

## Hard invariants

- **Debugging must never change capture.** It's strictly observational: fail-open
  itself (a logging error is swallowed), never alters the ledger, never blocks a hook.
  Same ledger + same policy ⇒ byte-identical derived tables with debug on or off.
- **Counts-never-content.** The debug log records *metadata only* — agent, event, cwd,
  resolved root, `.cage` present?, capture-enabled?, transcript_path *presence* (bool,
  not contents), files scanned (paths/counts), rows parsed/appended/deduped, skip
  reason, exception type+traceback. **Never** prompt/response bodies, never token-text.
- **Off by default, $0/stdlib.** No file written, no overhead unless explicitly enabled.
  All four agents first-class.

## What to build

1. **A debug logger** (`cage/debuglog.py`), stdlib only, gated by
   `policy.debug_enabled` (env `CAGE_DEBUG=1` overrides `policy.toml [debug] enabled`,
   default off). Writes one structured JSON line per event to `$CAGE_DEBUG_LOG`
   (default `.cage/state/debug.log`). Self-fail-open: if logging raises, swallow it —
   capture must survive a broken logger. Provide `debuglog.event(**fields)` and
   `debuglog.exception(context, exc)`.

2. **Instrument every hook entrypoint** in `hooks.py` (`session_start`, `stop`,
   `session_end`, `post_tool_use`, `post_commit`) and the umbrella `importcmd.run` +
   each adapter (`import_claude/codex/copilot/kiro`): log entry (agent, event, cwd,
   resolved root, guard outcomes), and the import result (src scanned, #files, #parsed,
   #appended, #deduped, or the exact skip reason — `no .cage` / `capture disabled` /
   `no files` / `since-filtered`). **Replace every silent `except Exception: pass` with
   `except Exception as e: debuglog.exception(<where>, e)`** — still fail-open (swallow),
   but the traceback is now recorded instead of vanishing. This is the core fix.

3. **Per-agent hook heartbeat.** Each hook firing stamps a last-seen record
   (`.cage/state/hooks-seen.jsonl`: agent, event, ts, cwd) — append-only, last-write-
   wins by (agent,event). This makes "did this agent's hook ever fire?" answerable
   without manual marker files.

4. **Surface it.** Add `cage doctor` rows (or `cage doctor --trace`) showing, per agent,
   **last hook fired** (event + how long ago, or "never") and the last skip/error from
   the debug log. Optionally a `cage debug [--tail N]` to print recent debug events.
   When debug is off, doctor says how to turn it on.

5. **Docs.** Short "Debugging capture" section in the agents/wiring doc: enable with
   `CAGE_DEBUG=1`, where the log lives, what the heartbeat answers, and that it's
   metadata-only.

## Acceptance

- `tests/`: with `CAGE_DEBUG=1`, a simulated hook payload writes the expected structured
  event line(s); a parser that raises produces a `debuglog.exception` entry **and** the
  hook still returns 0 (fail-open preserved); the heartbeat updates per (agent,event);
  `cage doctor` shows per-agent last-fired incl. "never"; the debug log is asserted to
  contain **no** prompt/body fields; with debug **off**, no debug file is created and the
  ledger output is byte-identical to a debug-on run.
- `just test` green; no existing plan-number assertion changes. Bump `__version__`, add
  a README "What's new" line, refresh the test count (CLAUDE.md release-hygiene rule).

## Working agreement

Plan before code (files touched, the `debuglog` API, the exact fields logged per
hook/adapter, the heartbeat format, the doctor surface, the test list) and stop for my
review. Do not write code until I approve.

## Out of scope

No telemetry/network, no always-on logging, no logging of prompt content, no change to
capture behavior itself — this only makes the existing path observable.
