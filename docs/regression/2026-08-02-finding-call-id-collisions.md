---
doc: regression — finding: `ids.new_id` collides, and a collision silently drops a row
date: 2026-08-02
severity: MEDIUM — real data loss, low per-event probability, silent
found: diagnosing a red CI run on main (test_study, one call short)
status: RESOLVED 2026-08-02 (unreleased, v0.45.0) — random field widened 16 → 32 bits
---

# `ids.new_id` has 16 bits of entropy per millisecond, and dedupe turns a collision into a lost row

> **RESOLVED 2026-08-02** (unreleased, v0.45.0). The fix proposed below was applied
> verbatim — `secrets.randbelow(0x100000000):08x`, 32 bits. Re-measured the same way
> immediately after: **0 duplicates in 200,000 sequential ids** (was 874). The two
> consequences flagged as "check before applying" both held: `transcript._composite_id`'s
> parity comment was corrected in the same change, and no test needed its width
> assertion changed (`test_transcript.py:275`'s `len == 17` exercises the
> *deterministic* uuid-less path, which does not call `new_id`). Entropy width is now a
> **contract test**, not a statistic — `tests/test_substrate.py` asserts `randbelow` is
> called with `0x100000000`, because a statistical test for a 1-in-4-billion event is
> either vacuous or flaky. **Ids already written keep their 16-bit risk forever** and
> are never rewritten. Body below is the original published finding, unedited.

**The claim:** two rows created in the same millisecond have a ~1/65,536 chance of
being assigned the same id, and because every merge path dedupes **by id**, the loser
is **silently discarded**. In a ledger whose entire job is not losing measurements,
that is a correctness bug, not a nuisance.

**Measured, not argued** (this machine, 2026-08-02):

```
calls per millisecond bucket:            [38]      ← all 38 landed in ONE ms
duplicate ids in 200 trials of 38:         1
dupes in 200,000 sequential ids:         874       ← ≈ 1 in 229
```

## How it surfaced

`tests/test_study.py::test_import_merges_and_is_idempotent` failed on main
(`build (macos-latest, 3.13)`, run 30740151860) with `assert 37 == 38` — one call short
after merging seven fleet bundles. The fixture seeds 38 calls in a tight loop with **no
explicit `call_id`**, so each got a random one; two collided, and `mergeutil.union_by_id`
correctly kept one.

The test was *right*. The id generator was wrong.

## The mechanism

```python
# cage/ids.py
def new_id(prefix: str) -> str:
    ms = int(time.time() * 1000)
    return f"{prefix}_{ms:011x}{secrets.randbelow(0x10000):04x}"
```

`0x10000` = **16 bits** of randomness, and the millisecond prefix is shared by every row
created in that millisecond. Birthday-bound for *k* rows in one millisecond:
`P ≈ k² / 131072`. At k=38 that is ~1.1%; a burst of 200 in one millisecond is ~26%.

Then dedupe does the rest — every one of these treats an id as an identity:
`ledger.append_new` · `mergeutil.union_by_id` · `ledger.receipts` · `study.import_bundles`.

## Why it matters beyond the test

- **`metering.py`** (the library adapter) mints a random id per call. A high-throughput
  metered app is exactly the burst case.
- **`study.import_bundles`** merges fleet bundles by id — a collision across two
  machines' rows drops one machine's call.
- Receipts (`make_receipt`) and savings rows share the generator.

**Not affected:** the transcript importer, which derives ids deterministically from the
turn (`c_<uuid>` / `transcript._composite_id`) precisely so re-imports dedupe. That
design is right and is the reason the dominant capture path never hit this.

## Fix (proposed, not applied)

Widen the random component from 4 hex to 8 hex (16 → 32 bits): collision probability
per same-millisecond pair falls ~65,000×, to ~1 in 4.3 billion.

```python
return f"{prefix}_{ms:011x}{secrets.randbelow(0x100000000):08x}"
```

Consequences to check before applying — **this is why it was not done in the same
change as the v0.43.0 release**:

- Ids get 4 characters longer. `transcript._composite_id`'s docstring claims "same
  `c_`+15-char shape as the uuid path"; that parity becomes stale. It is cosmetic (ids
  are opaque strings) but the comment must be corrected, not left lying.
- Existing ledger rows are untouched — ids are never rewritten, and the two formats
  coexist safely because neither is parsed.
- Check nothing pins id *length*: `tests/test_study.py` pins `len(machine_id) == 18`,
  which is `machine.py`, a different generator.

A per-process counter was considered instead. It is strictly stronger within one
process but does nothing across processes (two agents metering at once is the normal
case here), so widening the random field is the better single change.

## Note on the release

v0.43.0 shipped with this defect present — it predates the release by many versions and
its per-event probability is ~1/65,536. The release CI (run 30742360863) was green on
all 12 cells; the earlier failure was this flake firing on one cell.
