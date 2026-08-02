---
doc: finding — commit windows compared timestamps across offset representations
date: 2026-08-02
status: fixed (REV-TS)
---

# Finding: the authorship window join was skewed by the committer's UTC offset

**Every authorship join on a non-UTC machine placed edits and calls on the wrong
commit.** `commitjoin` built commit windows from raw `git log --format=%cI` strings —
the *committer-local* offset — and compared them **lexicographically** against UTC
`…Z` transcript and call timestamps. String order across different offset
representations is meaningless.

The maintainer's machine is IST (`+05:30`) and is the only machine that has ever run
this, so the published v0.44 dogfood snapshot inherits the skew.

## What was verified, and what was wrong

Three failure shapes were claimed
([proposal](../archive/v0.45-rev-ts.proposal.md)). **Two reproduced. One did not, and
the difference matters** — it decided the fix's precision.

| claim | verdict | evidence |
|---|---|---|
| **Offset skew** — every edit shifts by the committer's offset | **CONFIRMED** | an edit at `05:00Z` (10:30 IST, *after* a 09:00 IST commit) buckets onto the *earlier* commit, because `"05…"` < `"09…"` |
| **Mixed-offset sort** — local commits + `+00:00` CI merges mis-sort | **CONFIRMED** | `09:00+00:00` (09:00Z) sorts *below* `12:00+05:30` (06:30Z), reversing the window list and producing bounds that run backwards |
| **Same-second boundary fails in pure-UTC repos too** | **FALSIFIED** | see below |

### The falsified claim

The claim was that `"…T10:00:00.000Z" <= "…T10:00:00+00:00"` is False (`.` = 0x2E
sorts above `+` = 0x2B), so even a pure-UTC repo violates the documented inclusive
bound. **It rests on a `+00:00` window bound that git never emits.** Measured
directly — git renders `%cI` as `Z` when the offset is zero:

```
GIT_COMMITTER_DATE input   →  %cI output
2026-07-01T09:00:00+05:30  →  2026-07-01T09:00:00+05:30
2026-07-01T10:00:00+00:00  →  2026-07-01T10:00:00Z
2026-07-01T11:00:00-08:00  →  2026-07-01T11:00:00-08:00
```

So in a pure-UTC repo the bounds already share the probes' shape, and `.` (0x2E)
sorting *below* `Z` (0x5A) makes a sub-second probe land in the earlier window —
which is exactly what the inclusive-second bound requires. **That case was correct
all along, by accident.**

The same-second bug is real, but only where a bound carries a non-zero offset: c2's
bound `14:00:00+05:30` is 08:30:00Z, and a probe of exactly `08:30:00Z` was handed to
c1 instead.

### Why the falsification changed the fix

The proposal sketched the normal form as `…THH:MM:SS[.mmm]Z` — *optional*
milliseconds, which is still not totally ordered and would have re-introduced the
bug. The falsified claim rules out the obvious repair too: **a millisecond normal
form would push `12:00:00.999Z` out of the commit stamped `12:00:00` and break the
one case that already worked.**

The shipped form is therefore fixed-precision **seconds**, sub-seconds truncated —
`%cI` carries no sub-second, so cage does not have the precision to exclude an edit
made inside the commit's own second. Pinned by
`test_a_pure_utc_repo_keeps_the_bound_it_already_gets_right`, which is a **guard on
behaviour that already held**, not a red-before-green fixture, and is labelled as
such in its docstring.

## Blast radius

- **Frozen rows are not repaired.** `originrecord`'s idempotency key is
  `(sha, agent, session_id, method)`, so pre-fix rows written on a non-UTC machine
  keep their wrong sha forever — the log is append-only and is never rewritten.
- **A corrected sweep can *add* to them.** A re-read transcript writes rows on the
  corrected sha while the wrong-sha rows persist, so those lines then count on two
  commits. The `_authorship` cursor is therefore deliberately **not** invalidated:
  a transcript with unchanged bytes and `covered` stays unread. Files still marked
  uncovered will be re-read and can produce the double-presence anyway; that is
  unavoidable without a purge, and a purge is forbidden.
- **Pure-UTC repos were never affected** — no rows to distrust there.
- `cage insights commits --csv` wrote `ts` as the raw bound, so on a non-UTC machine
  its `ts` column emitted **local** time; it is UTC now.

## Why the suite never caught it

Every `goldenseed` commit was pinned `+00:00`, and the one boundary test probed with
byte-identical `+00:00` strings. **The suite never left UTC and never sat on a
boundary** — 1401 tests green over a join that was wrong on the machine running them.

## Fix

`cage/commitjoin.py` — one parse (`as_utc`, naive⇒UTC-assumed, always aware) and one
normalizer (`norm_ts`); `Window` normalizes its bounds **at construction**, so a
window holding a raw git string cannot be built in this module or in a test.
`window_for` normalizes the probe; `authorcapture._uncovered` normalizes before the
cursor compare; `commitview._iso` re-points to the same parse (it could previously
return a **naive** datetime, one input away from a `TypeError` against
`ledger.since_cutoff`'s aware cutoff).

**12 tests added** (4 red-before-green, 1 guard, 7 normalizer units); 1401 → 1413,
0 fail, and **no existing golden moved** — `commitview._date` slices at `ts[5:16]`
and drops the offset, which made "nothing else changed" the strongest available
check on the blast radius.
