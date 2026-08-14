# OPEN-WORK — the index of pending work

## Agent-closable

- **COPILOT-METRICS-CSV** — `cage data export --csv copilot` (raw-row export for the
  kind). Parked scope-out from COPILOT-METRICS §3; unaffected by METRICS-PRIMARY, which
  changed what READS the kind, not how it exports.
- **KIRO-METRICS-CSV** — `cage data export --csv kiro`. Same parked scope-out.
- **CLAUDE-METRICS-CSV** — `cage data export --csv claude`. Same parked scope-out.

- **KIRO-IDE-METRIC-ROW** — defect (found 2026-08-14 by METRICS-PRIMARY): kiro reads
  **zero** post-cutover. Its metric `ide` route parses `devdata.sqlite`, which does not
  exist on this machine, while its *calls* route parses `tokens_generated.jsonl`, which
  does — two different files for the same facts. Measured on a clean re-import: 28
  post-cutover kiro calls → 0 metric rows. Fix: emit an `ide` metric row from
  `tokens_generated.jsonl`, the file the calls route already reads. Arpit accepted the
  zero as the interim behaviour ([ADR 0010](../docs/adr/0010-metric-ledgers-are-the-spend-source-forward-only-cutover.md)
  veto condition, contingent).

- **METRICS-DUAL-WRITE-END** — decide whether `calls` capture for the three agents ever
  stops. **Do not touch before 2026-09-13** — one full transcript-retention window of
  clean metric capture, and then only with the post-cutover gap count at zero (ADR 0010
  veto condition, contingent).

## Arpit decides

**None.**

## How this file is maintained

Continuously. A new item is one line here, the moment it's known; detail goes inline
or into a handoff/prompt pair in `work/` root. A completed item is **deleted, not
ticked** — legal only once [IMPLEMENTATION.md](IMPLEMENTATION.md) records its outcome
and any evidence reaches [regression/](../work/regression/), with residual limits
carried forward as their own lines. **Its own markers are never evidence** — reconcile
against git. The header's checkable claims are gated by `tests/test_queue_honesty.py`.
Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
