# Example — debug & diagnostics

cage is **fail-open but never silent**: a swallowed error on the write path is
traceable, not lost. These are the switches that make it visible.

## Environment variables

```bash
CAGE_DEBUG=1        # trace every capture-path swallow-site (produce/skip logs)
CAGE_BASE=/path     # override the resolved ledger root
CAGE_USD=1          # dollars instead of tokens in views (flag > env > policy)
CAGE_CAPTURE=0      # pause metering without unwiring hooks (env > policy)
CAGE_CAPTURE_ON_READ=0   # disable capture-on-read
CAGE_CLEANUP=0      # disable state cleanup
```

`CAGE_DEBUG` is read-only diagnostics — it never changes a derived number. The
determinism/golden suites pin the capture switches OFF.

## cage doctor

```bash
cage doctor             # capture health: active sink, last-import age, per-source timeline
cage doctor --paths     # probe every per-agent log location (read-only)
cage doctor --wiring    # per-artifact wiring inventory (current/stale/dead/foreign)
cage doctor --bundle    # one redacted, counts-never-content archive for a bug report
```

Doctor **diagnoses** capture — it does not sweep. It is honest: it never claims an
unfireable hook is "capture wired," and names the active sink.

## Verifying a silent capture failure

- A dead **wired** verb (installed before a rename) exits 1 and, because hook output
  goes nowhere, is indistinguishable from cage-not-installed. `cage doctor --wiring`
  catches it; `cage setup` heals it.
- `state/capture.log` is an always-on breadcrumb (one line per agent per real import
  run — counts only) that proves capture ran at all.
- Under `CAGE_DEBUG=1`, every receipt push site logs produce/skip, so a silently
  skipped savings receipt becomes diagnosable.
