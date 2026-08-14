# OPEN-WORK — the index of pending work

## Agent-closable

- **COPILOT-METRICS-CSV** — `cage data export --csv copilot` (raw-row export for the
  kind). Parked scope-out from COPILOT-METRICS §3; unaffected by METRICS-PRIMARY, which
  changed what READS the kind, not how it exports.
- **KIRO-METRICS-CSV** — `cage data export --csv kiro`. Same parked scope-out.
- **CLAUDE-METRICS-CSV** — `cage data export --csv claude`. Same parked scope-out.

- **TASK-GRAIN-SPINE** — defect (found 2026-08-14 by USAGE-ONLY): a metric row carries no
  `task` field, so `cage insights compare` / `estimate` / `calibration` see **zero** for
  claude and copilot — the agents whose spend resolves from the metric ledger. The
  `taskgroup` window fallback cannot help: it builds windows from task-carrying calls,
  and there are none. Same root cause makes `report --by route` collapse to `chat`.
  Candidate fix: derive the window from `tasks.jsonl` (which carries session + ts)
  instead of from task-carrying calls. Pinned in `tests/test_compare.py`'s `_MODEL`
  comment so the seam is visible where it bites.

- **METRICS-DUAL-WRITE-END** — decide whether `calls` capture for the three agents ever
  stops. **Do not touch before 2026-09-13** — one full transcript-retention window of
  clean metric capture. The ADR 0010 gate that framed this (post-cutover gap count at
  zero) is void: there is no cutover ([ADR 0011](../docs/adr/0011-cage-measures-usage-not-cost.md)).
  The live reason to keep writing `calls` is that it is the **id namespace savings
  receipts reference** and the fallback basis for every spine-less agent.

## Arpit decides

- **Does cage keep a release-shaped version for USAGE-ONLY?** The work is committed
  under the unreleased v0.49.1 changelog heading (as METRICS-PRIMARY was). `__version__`
  is untouched at `0.49.1`. A deletion this large arguably wants its own version;
  releasing is Arpit's call and never happens from a laptop.
- **README positioning is DONE but worth a read** — cage is now described as a usage
  meter that deliberately refuses to price. If that framing is wrong, it is one file.

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `work/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../work/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
