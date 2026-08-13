# work/dogfood/ — cage measured on itself, published so it cannot rot

This folder holds real `~/.cage` ledger numbers from the dev machine — the ledger
built by using cage to build cage. Design of record:
[the archived proposal](../archive/v0.44-dogfood-report.proposal.md) ·
[the archived handoff](../archive/v0.44-dogfood-report.handoff.md).

## Convention (append-only, mirrors `work/regression/`)

```
work/dogfood/
  <YYYY-MM-DD>.md    # one snapshot per refresh — never edited after publishing
  latest.md          # a byte-identical copy of the newest dated snapshot
  README.md          # this index
```

A snapshot is real output only — every figure is pasted verbatim from the allowlisted
commands (`cage report`, `cage insights attrib`, `cage insights adoption`), method tags
intact, gross keeps its gross note, `UNPRICED` is shown not trimmed. **Never a fabricated
or placeholder number** — if a command has nothing real to show (see the 2026-08-02
snapshot's note on `attrib`), the snapshot says so instead of inventing one.

To refresh: run the three commands on the dev machine over the **same absolute window**
each time (all-time is the default — no `--since`), write a new dated file, copy it over
`latest.md`. `tests/test_dogfood_freshness.py` fails once `latest.md` is more than 60
days old, or its `snapshot_date` disagrees with the newest filename — see that test for
the exact gate and the `CAGE_SKIP_DOGFOOD_FRESHNESS=1` bisect escape hatch.

## Snapshots

| date | headline |
|------|----------|
| [2026-08-02](2026-08-02.md) | `$9,921.4588` total (52,179 calls, 71% from cache reads); `attrib` has no real task-tagged data yet on this machine (only the `cage demo` seed) — omitted rather than faked; adoption shows 100% agent-attributable savings coverage, claude the only agent with attributed savings rows. |

Latest always at [`latest.md`](latest.md).

## Single-question deep-dives (not part of the report/adoption ritual)

Named `<date>-<topic>.md` — outside the freshness gate (`test_dogfood_freshness.py`
only scans pure `<date>.md` filenames), so these don't have to be refreshed on the
60-day cadence and don't compete with `latest.md` for "the" snapshot.

| date | topic | headline |
|------|-------|----------|
| [2026-08-03-authorship](2026-08-03-authorship.md) | authorship reconciliation (project ledger) | `cage authorship summary` shows 72% UNKNOWN (83/115 commits) because capture only started 2026-08-02, not because most commits aren't agent-authored; a fresh cursor-free re-scan of the same on-disk transcripts recovers 69 commits (60%) vs the live ledger's 32 (28%) — 41 commits are backfillable today, pointing at a cursor-freeze gap in `authorcapture.py` worth fixing. |
