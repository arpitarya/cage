# Finding — Capture-health says `captured:false` while rows exist (`health-contradiction`)

**Severity:** was HIGH as-run, **corrected to narrow** (first-import-only; never a
false "capturing nothing" warning) · **Status:** ✅ RESOLVED (fixed 2026-07-23,
shipped **v0.31.2**) · **Surface:** `importcmd` capture-health / `cage doctor`

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) |
| Corrected by | [2026-07-23 F2 correction](2026-07-23-f2-correction.md) (on disk, cited) |
| Fix shipped | **v0.31.2** — `cage/importcmd.py`; test `test_first_ever_import_marks_the_agent_captured_same_run` |

## Status now

RESOLVED. The observation was real, but its stated *root cause* was wrong; the
07-23 correction found the true cause (a snapshot-ordering off-by-one) and shipped
a two-line fix in `importcmd.py` (v0.31.2). The severity was also over-stated: it
did **not** cause false "installed but capturing nothing" warnings — it understated
freshness for exactly one run per agent, on that agent's first-ever capture.

## Evidence (as observed 2026-07-22)

| agent | `_health.captured` | rows in ledger | files seen |
|-------|:------------------:|---------------:|-----------:|
| codex | false | 373 | 20 |
| copilot | false | 60 | 152 |
| kiro | false | 16 | 1 |

`cage doctor` and the report's capture-health line read this flag; as written it
said three of four agents were capturing nothing.

## Superseded first diagnosis (2026-07-22) — kept, visibly wrong

> **Root cause:** `captured` records "did *this* import run add new rows for the
> agent," not "has this agent ever captured." On a run where an agent had nothing
> new the others flip to `false` even with a healthy history.

**This is superseded.** The code has read the *lifetime* set of captured rows since
v0.30.0 (`f1fb99d`) — `_record_health` builds `all_rows = ledger.calls(root)` and
derives `captured` from the whole ledger. The "this-run delta vs. all-time"
mechanism does not match what the code does and never did in the version tested.

## History

**2026-07-22 (observed, lab-run-001):** codex/copilot/kiro read `captured:false`
while holding 373/60/16 rows. Diagnosis (above): a this-run-delta-vs-lifetime
confusion. Severity HIGH.

**2026-07-23 (corrected — [2026-07-23-f2-correction.md](2026-07-23-f2-correction.md)):**

- **Actual root cause: a snapshot-ordering off-by-one.** `captured` is computed
  from `ledger.calls(root)` **before** `run_agent` appends this run's newly-imported
  rows. So the first-ever import for a surface isn't in `captured` yet when
  `_record_health` reads it, and that first run records `captured:false` — while
  the rows it just imported sit in the ledger a moment later. It self-heals on the
  next import. The 07-22 run caught it because no import ran for 3 days after
  2026-07-19 (itself the first sweep to capture codex/copilot/kiro), so the `false`
  had nothing to overwrite it.
- **Blast radius corrected (do not overclaim):** this did **not** trigger false
  "installed but capturing nothing" warnings — that gate also requires `files == 0`,
  and a first-ever import always has `files > 0`. What was wrong was narrower: the
  `_health.captured` flag and `cage doctor`'s summary line reading it, understated
  for exactly one run per agent on first capture.
- **Fix + verification:** two-line fix in `cage/importcmd.py` — `run_agent` records
  the count imported this run onto `health[agent]["imported"]`, and `_record_health`
  treats `captured` as `a in captured or info.get("imported", 0) > 0`. Regression
  test `test_first_ever_import_marks_the_agent_captured_same_run` — failing before,
  passing after. Real-ledger check: one `cage import` flipped all four surfaces to
  `captured:true`.

**Shipped v0.31.2.**

## Process note (from the correction, worth keeping)

The cage-lab loop surfaced a real defect by slicing the live ledger even though
its stated *why* was wrong. Evidence beat hypothesis — keep publishing reports and
correcting them in the open as new dated entries.
