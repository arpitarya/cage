# Finding — `gap_ms` (human-attention axis) barely populated (`gap-ms-sparse`)

**Severity:** LOW · **Status:** ✅ RESOLVED (**v0.34.0**) — **reframed, not a parser
bug**: the "~1%" denominator was wrong, and instrumentation (not a stamping change)
shipped · **Surface:** `transcript.parse_calls` / human-attention axis

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) (371 of 36,451 rows, ~1%) |
| Fix shipped | **v0.34.0** — per-file `gap_ms` skip-reason instrumentation |

## Status now — read this before citing "1%" again

RESOLVED as a **reframing**. The observation (371 of 36,451 rows carry `gap_ms`,
~1%) was measured *correctly* but framed against the wrong population. `gap_ms` can
only be stamped on the *first* call row after a genuine human turn — every other
call row in that turn (tool-call iterations inside one agentic loop, which is most
of them) correctly has no gap to carry. Comparing 371 stamped rows against **all**
36,451 call rows compares against a population that was never eligible. **Every
human turn is accounted for; there is no unexplained loss.** Nothing about *what*
gets stamped changed — instrumentation shipped so the accounting is provable.

## Evidence (as observed 2026-07-22)

371 of 36,451 rows carried `gap_ms` (~1%) — see [lab-run-001](2026-07-22-lab-run-001.md).
The passive human-attention axis (turn-gap → attention minutes) needs `gap_ms`,
stamped at import where per-turn timestamps exist; at ~1% coverage the
derived-attention view looked to have almost no data.

## The reframing (v0.34.0)

Reimplemented `parse_calls`'s gap logic as an instrumented probe and ran it against
every real Claude transcript on the reporting machine — **141 files, 632 human
turns, 36,322 call rows** (near-exact match to the run's denominator): **371
stamped**, reproducing the evidence line exactly. Every human turn that did *not*
end up stamped was traced:

| outcome | count | why |
|---|---|---|
| stamped | 371 | ✓ |
| `skip_first_turn` | 194 | session's first turn — no prior assistant ts, by design |
| `skip_negative_gap` | 16 | genuine clock disorder — dropped, never fabricated |
| `skip_bad_ts` | 0 | — |
| residual (superseded + dangling-at-eof) | 51 | arithmetic remainder — not itemized at aggregate scale by this probe |

The residual 51 is **not unexplained loss** — it is the two legitimate cases the
shipped `skip_superseded` / `skip_dangling_eof` counters name: either a second
human turn arrived before any call consumed the first (the *fresher* gap wins,
correctly), or the transcript ended before a pending gap found a call row. Both
confirmed exactly on the single largest real transcript: 15 eligible gaps → 12
consumed + 3 superseded + 0 dangling, zero residual. (The aggregate 51 was not
re-broken-down per-reason across all 141 files with the shipped counters — that
would need re-running every file with `CAGE_DEBUG=1`; the per-file identity is what
matters and what's tested by `test_real_transcript_reconciles_exactly`.)

## What shipped (instrumentation, not a parser fix)

- `transcript.parse_calls` gains optional `root`/`pol` params (both default `None`
  — every existing caller byte-identical). When set, one summary
  `debuglog.event(event="gap_ms", ...)` per parsed file records `human_turns`,
  `stamped`, and every skip reason by name: `skip_first_turn`, `skip_bad_ts`,
  `skip_negative_gap`, `skip_superseded`, `skip_dangling_eof`. The five reconcile
  exactly: `human_turns == stamped + Σ skip_*` — proven in unit tests and against a
  real transcript.
- Nothing about *what* gets stamped changed. No gap is fabricated to raise the
  percentage.
- **Recommendation for future capacity reads:** report `gap_ms` coverage as
  `stamped / (human_turns − skip_first_turn − skip_negative_gap)`, not `stamped /
  call_rows`. On this measurement that is 371/422 ≈ **88%**, not "~1%" — and even
  that 12% isn't lost data: it's turns whose gap was legitimately superseded by a
  fresher one, or dangling at end-of-transcript.

## History

**2026-07-22 (observed, lab-run-001):** 371/36,451 (~1%). Proposed verifying
`transcript.parse` stamps `gap_ms` across the whole transcript and logging skips.

**v0.34.0 (RESOLVED — reframed):** the ~1% denominator was wrong; per-file
skip-reason instrumentation shipped; correct coverage on this data is ~88%.
