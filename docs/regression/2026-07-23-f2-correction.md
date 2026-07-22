# 2026-07-23 — Correction to F2 (`captured:false` while rows exist)

This is a correction to a finding in
[2026-07-22-capture-report.md](2026-07-22-capture-report.md) §F2. Per this repo's
convention, dated regression reports are historical records and are never rewritten —
corrections are published as new, dated entries. The 07-22 report is unchanged.

## What the 07-22 report claimed

> **Root cause:** `captured` records "did *this* import run add new rows for the
> agent," not "has this agent ever captured."

## Why that was wrong

The code has read the **lifetime** set of captured rows since v0.30.0 (`f1fb99d`), not
a this-run delta: `_record_health` builds `all_rows = ledger.calls(root)` (the whole
ledger) and derives `captured = {row_surface(...) for row in all_rows}` from it. The
stated mechanism — "this run's delta vs. all-time" — does not match what the code does
and never did in the version under test.

## The actual root cause

A snapshot-ordering off-by-one. `captured` is computed from `ledger.calls(root)`
**before** `run_agent` appends this run's newly-imported rows to the ledger. So the
very first import for a given surface isn't in `captured` yet at the moment
`_record_health` reads it, and that first run records `captured:false` — even though
the rows it just imported are sitting in the ledger a moment later.

It self-heals on the *next* import (by then the ledger contains those rows, so they're
in the lifetime set). The 07-22 report caught it because no import ran for 3 days
after 2026-07-19 — which was itself the first sweep to capture codex/copilot/kiro — so
the `false` from that first run had nothing to overwrite it until the report ran.

## Corrected blast radius (do not overclaim)

The 07-22 report's severity framing ("high", implying a broad health-signal defect)
overstates it. This did **not** cause false "installed but capturing nothing"
warnings — that gate also requires `files == 0`, and a first-ever import always has
`files > 0` (the log file exists and was read). What was actually wrong was narrower:
the `_health.captured` flag itself, and downstream, `cage doctor`'s summary line
reading it — both understated freshness for exactly one run per agent, on that
agent's first-ever capture.

## Fix + verification

Two-line fix in [`cage/importcmd.py`](../../cage/importcmd.py): `run_agent` now
records the count of rows imported this run onto `health[agent]["imported"]`, and
`_record_health` treats `captured` as `a in captured or info.get("imported", 0) > 0`
— unioning the lifetime set with this run's own appends closes the snapshot-ordering
gap.

New regression test:
`test_first_ever_import_marks_the_agent_captured_same_run` in
[`tests/test_capture_health.py`](../../tests/test_capture_health.py) — confirmed
failing before the fix, passing after. Additionally verified against the real ledger:
one `cage import` flipped all four surfaces (claude-code, codex, copilot, kiro) to
`captured:true`.

## Process note

The cage-lab loop worked as intended: it surfaced a real defect by slicing the live
ledger, even though its stated diagnosis of *why* was wrong. Evidence beat hypothesis.
Keep publishing reports — and keep correcting them in the open, as new dated entries,
when the diagnosis needs revision.
