# Finding — No `debug.log` exists (`no-debug-log`)

**Severity:** MEDIUM · **Status:** ✅ RESOLVED (always-on `state/capture.log`
breadcrumb shipped; verbose trail gated on `CAGE_DEBUG`) — one follow-on
deliberately deferred (hook-path breadcrumb) · **Surface:** capture observability

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) |
| Follow-on | [2026-07-24 capture.log / hook-append gap](2026-07-24-capture-log-hook-gap.md) (on disk, cited) |
| Fix shipped | the F6 capture-observability breadcrumb ("F1/F2/F6 shipped previously") |

## Status now

RESOLVED for what it asked: an always-on, size-capped, PII-safe `state/capture.log`
breadcrumb now proves the *pull/import* path ran (one line per agent per run,
counts only), with the verbose trail gated behind `CAGE_DEBUG=1`. One follow-on is
open and deliberately deferred — the breadcrumb does **not** yet instrument the
real-time Claude hook append path (see the 07-24 follow-on below).

## Evidence (as observed 2026-07-22)

`~/.cage/state/` contained only `cursors.json` and `limits.json` — no `debug.log`;
`CAGE_DEBUG` had never been set. cage is fail-open (swallows errors on the
write/capture path) and its swallow-sites log *under `CAGE_DEBUG`* — but with no one
turning it on, every silent skip stayed silent. That is exactly why F1–F3 were
guesswork at the time.

## The fix that shipped

- A **minimal capture breadcrumb, always-on** (not gated on `CAGE_DEBUG`): one line
  per import run per agent — `agent · files_seen · rows_new · rows_total · src` —
  appended to a small, size-capped `state/capture.log` (counts only, PII-safe,
  cleanup-allowlisted).
- The *verbose* trail (per-file skip reasons, receipt push/skip, parser mismatches)
  stays behind `CAGE_DEBUG=1`.
- `cage doctor --bundle` includes the new `capture.log` so a report like this is one
  command.

## Consolidated debug-logging additions (the master list this finding asked for)

| where (file) | at | log (counts only) |
|--------------|----|-------------------|
| `importcmd.py` | end of each agent's import, where `_health` is written | `agent · files_seen · rows_parsed · rows_new_after_dedupe · rows_total · resolved_src` → **always-on** `state/capture.log` |
| `transcript.py` | per file that yields 0 rows | reason: `format-mismatch` / `no-usage-rows` / `all-deduped` (CAGE_DEBUG) |
| `graphifymeter.py`, `metering.record_receipt`, `responsecache.py`, `compress.py` | every receipt emit/skip | `tool · produced?(bool) · skip_reason` (CAGE_DEBUG) |
| `freshness.py` / capture-health | when computing `captured` | record `last_captured_ts` + `rows_total` alongside the run delta |
| `receiptprice.py` | on UNPRICED receipt/call | model, why unpriced (already partly surfaced) |

All of it stays **counts-never-content** and cleanup-allowlisted, consistent with
cage's PII discipline. None of it changes a derived number — it only explains the
capture path.

## History

**2026-07-22 (observed, lab-run-001):** no `debug.log`; `CAGE_DEBUG` never run.
Proposed the always-on breadcrumb + `CAGE_DEBUG`-gated verbose trail.

**Shipped (F6, "shipped previously" per the run's status):** the always-on
`state/capture.log` breadcrumb + the consolidated logging above.

**2026-07-24 (follow-on — [2026-07-24-capture-log-hook-gap.md](2026-07-24-capture-log-hook-gap.md)):**
diagnosed that `capture.log` instruments *only* the pull/import path
(`importcmd._record_capture_log`, single call site). The real-time Claude
`Stop`/`SessionEnd` hook (`hooks.py`) appends directly and has always bypassed it —
confirmed live with 1,674 un-breadcrumbed `claude-code` rows in a 6-hour window
(surfaced once v0.32.0 re-livened this machine's previously-dead global hook). This
is not a regression — F6 was scoped to the pull path from the start. **Extending
the breadcrumb to the hook path is deferred to its own design pass** (where the
shared breadcrumb helper lives; per-turn vs aggregate line).
