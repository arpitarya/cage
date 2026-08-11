---
item: OUTPUT-GROWTH
lane: parked · reopen only on a measured number
status: fine as parked — do not revisit from first principles
---

# OUTPUT-GROWTH — .cage/output/ grows without bound

`.cage/output/` has **no cleanup class by design**: cage never deletes an artifact it
wrote, the same standing `ledger/savings/` has. An as-of record is unrecoverable. So an
export-heavy user grows the directory forever.

## The reopen trigger, and it is deliberate

**Reopen only with a named size number from a real machine**, per the trigger in
[compare/view-export-and-run-stamp.compare.md](../compare/view-export-and-run-stamp.compare.md).
**Never re-argued from first principles** — a veto you can only reopen with a
*measurement* pre-empts a future agent re-litigating a settled call.

Realistically this surfaces as a disk complaint or never.
