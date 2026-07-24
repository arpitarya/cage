# docs/regression/ — capture reports & fixes from cage-lab

This folder is where the **cage-lab** sibling repo publishes its findings so they
live *with cage* and can be analysed and acted on here. It is populated
automatically after every regression/capture testing run.

## Convention (do this after every testing run)

After running cage-lab against the real ledger (or the regression suite), publish
the results here, **dated**:

```
docs/regression/
  <YYYY-MM-DD>-capture-report.md      # narrative findings + fixes + logging proposals
  <YYYY-MM-DD>-capture-report.json    # machine-readable findings (for scripts/agents)
  <YYYY-MM-DD>-fixes.md               # actionable, prioritized fix checklist
  latest-capture-report.md/.json      # stable path = a copy of the newest report
```

The cage-lab runner does this for you:

```bash
CAGE_REAL_LEDGER=~/.cage python ../cage-lab/labs/run_all.py     # writes the dated + latest files here
```

(Set `CAGE_REPO` if cage isn't at `../cage` relative to cage-lab.)

Why publish into cage and not just cage-lab: the findings are *about cage* and drive
*cage's* fixes, so they belong in cage's own history — diffable release to release,
and readable by any agent working on cage without needing the test repo checked out.

## Reports

| date | calls analyzed | headline |
|------|---------------:|----------|
| [2026-07-22](2026-07-22-capture-report.md) · [fixes](2026-07-22-fixes.md) | 36,451 | 0 real receipts; capture-health mislabels 3/4 agents; kiro ~empty; `copilot/auto` UNPRICED; no debug.log |

Latest always at [`latest-capture-report.md`](latest-capture-report.md).

### Corrections

| date | corrects | what changed |
|------|----------|--------------|
| [2026-07-23](2026-07-23-f2-correction.md) | 2026-07-22 §F2 | real root cause was a snapshot-ordering off-by-one (`captured` read before this run's appends), not a this-run-vs-lifetime confusion; blast radius corrected to first-import-only, never a false "capturing nothing" warning. Fixed in `cage/importcmd.py`, shipped v0.31.2. |
| [2026-07-24](2026-07-24-f1-root-cause.md) | 2026-07-22 §F1 | "no real savings ever captured" is false machine-wide — 5 real receipts live in a *project* ledger while the 36k calls live in the *global* one. Real cause is a **dead** interceptor, not a missing one: the v0.28.0 verb rename left the installed shim's `cage graphify --help` probe exiting 1, so it falls through to the unmetered binary — a class failure across every pre-rename shim/hook. Instrument gap (`debuglog` silent under `CAGE_BASE`) fixed in v0.31.4; the stale-wiring class fix is deferred to a design pass. |
| [2026-07-24](2026-07-24-capture-log-hook-gap.md) | 2026-07-24 anomaly (flagged in the F1 report above) | Resolves, not corrects — no prior report was wrong. `capture.log` only ever instrumented the pull/import path; the real-time Claude Stop/SessionEnd hook (`hooks.py`) appends directly and always bypassed it. Confirmed live with 1,674 un-breadcrumbed `claude-code` rows. Surfaced now because v0.32.0 re-livened this exact machine's previously-dead global hook. Bonus: that same global config's `SessionStart` hook still ran the dead pre-v0.28.0 `import-claude` verb — healed this session. Extending F6 to the hook path is deferred to its own design pass. |

### Follow-ups shipped

Findings above are historical records and are never rewritten; what shipped from them
is tracked here.

| finding | shipped in | what landed |
|---------|-----------|-------------|
| [2026-07-24](2026-07-24-f1-root-cause.md) — stale-wiring class fix (deferred there to a design pass) | **v0.32.0** | Detection of any installed artifact naming a verb the live CLI parser rejects (`cage/wiringscan.py`, user-level files included), healing on `cage setup`, `interceptor` upgraded from existence+PATH to liveness, and the deferred `receipts: 0` check shipped with it so the two report the true cause together. |

## What cage-lab is

A black-box regression suite + per-agent capture labs for the cage-flux package
(sibling repo `../cage-lab`). It never imports cage — it installs and runs the
shipped artifact, validates the numbers against a hand-derived reference, and (in
the labs) slices the real ledger per agent to surface capture gaps. See
`../cage-lab/TEST_PLAN.md` and `../cage-lab/CAPTURE_REPORT.md`.
