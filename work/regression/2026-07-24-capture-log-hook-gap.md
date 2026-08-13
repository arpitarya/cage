# 2026-07-24 — Diagnosis of the capture.log/hook-append anomaly

This resolves the anomaly flagged at the end of
[2026-07-24-f1-root-cause.md](2026-07-24-f1-root-cause.md) ("Anomaly flagged for
separate diagnosis"): `state/capture.log` had gone quiet even though calls kept
landing in `~/.cage/ledger/calls-2026-07.jsonl`. Diagnosis run against the real
machine (`~/.cage`, read-only inspection) with cage 0.33.0.

## The anomaly, confirmed with numbers

```
$ cat ~/.cage/state/capture.log   # one entry set, all four agents, ts = 2026-07-23T21:02:14Z
$ python3 -c "json.load(open('~/.cage/state/cursors.json'))['_last_import']"
2026-07-23T21:02:14.698077+00:00
$ ls -la ~/.cage/ledger/calls-2026-07.jsonl
... Jul 24 08:55 ...   # 6+ hours newer than the last capture.log entry
```

Rows with `ts` after the last recorded import: **1,690**, of which **1,674 are
`agent=claude-code`** (the remaining 16 are `kiro`, same-run write-time-stamp noise
around the cutoff instant — not a second live path). `_last_import` and
`capture.log` are both silent for this entire window.

## Root cause — confirmed, not just diagnosed

`capture.log` is written by exactly one function, `importcmd._record_capture_log`,
called from exactly one site, `importcmd.run` (grepped, confirmed single call site).
Any ledger append that doesn't go through `run` leaves no line.

The real global `~/.claude/settings.json` wires `Stop` to `cage hook-stop`
([`cage/cli.py:610`](../../cage/cli.py)) → `lambda a: hooks.stop()` →
`hooks._capture_calls` → `ledger.append_new` directly
([`cage/hooks.py`](../../cage/hooks.py), by the module's own docstring: "Claude's
real-time hooks bypass `importcmd.run`"). That path has never called
`_record_capture_log` — this is not a regression, it's how F6 was scoped from the
start: the breadcrumb instruments the *pull/import* path only, never the *real-time
hook* path.

**Why it surfaced now:** v0.32.0's stale-wiring heal re-livened the same machine's
previously-dead global Claude hook (see the F1 root-cause report above — the exact
`~/.claude/settings.json` this diagnosis re-inspected). Once live, it fires on every
turn and appends silently with respect to capture.log — hence the sudden 6-hour gap
with no breadcrumb, immediately following that fix.

Capture-on-read (`ensure_captured`) was the prior session's lead and is **ruled
out**: it calls `run(root, "all", ...)`, which does reach `_record_capture_log`. If
capture-on-read had produced these rows there would be a line.

## A second, independent finding on the same machine

The same `~/.claude/settings.json` inspection turned up a live instance of the F1
class bug it was originally about: the `SessionStart` hook still ran the pre-v0.28.0
verb `import-claude --project .`:

```
$ cage import-claude --project .
error: 'import-claude' is now 'cage import --agent claude'   (exit 1)
```

Confirmed dead, confirmed silent (fail-open swallows the exit 1). Not yet healed
because `cage setup` had not been re-run against this global config since v0.32.0
shipped the heal. Healed in this session: `cage setup --wire-only --claude` run with
`root=$HOME` (this file's actual wiring root — `~/.claude/settings.json` is a
project-scoped `claudewire` write where the "project" happens to be the home
directory, not a Claude Code built-in). Verified: `import-claude` → `import --agent
claude --project .`, 6 legacy absolute-path entries migrated to the committed shim
form. Backed up before the change.

**Side effect worth flagging, not a bug:** migrating this file to shim-relative
(`$CLAUDE_PROJECT_DIR/.cage/bin/cage-run`) form narrows the hook's real-time reach —
it now only fires meaningfully in projects that have their own local `cage setup`
(the shim exists there), versus the previous absolute-path form which fired
everywhere on the machine unconditionally. This matches cage's own designed
posture (hooks are an optional, best-effort real-time add-on; `cage import`/
capture-on-read is the universal, reliable path — Claude Code always writes its
transcript regardless of hook wiring, so nothing is lost, only delayed for
un-set-up projects), but it is a real behavior change from this particular
machine's prior (non-standard, absolute-path) global setup, so it's recorded here
rather than silently absorbed into the heal.

## Deferred, deliberately

**Extending the F6 breadcrumb to the hook append path** (`hooks.py`'s
`_capture_calls`) so `capture.log` proves capture ran regardless of which path did
it — pull or real-time. Needs its own scoped design pass (where does the shared
breadcrumb-writing helper live so both `_record_capture_log` and `hooks.py` call the
same thing; does a per-turn hook write get its own line or aggregate). Not started
this session per this repo's investigate → debate → build discipline — logged here,
not implemented.

## Process note

Same discipline as the F1/F2 corrections: read the real machine, cite exact
evidence, rule candidates out by trace rather than by assumption (capture-on-read
was cleanly exonerated, not just deprioritized). The fix is scoped and deferred
rather than rushed, and the one live side effect of the day's actual change (the
hook heal) is written down rather than left implicit.
