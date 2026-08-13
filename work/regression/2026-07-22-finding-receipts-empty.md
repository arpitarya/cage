# Finding — Tool-savings receipts are effectively absent (`receipts-empty`)

**Severity:** HIGH · **Status:** ⚠ PARTIALLY RESOLVED — the capture-path cause is
**fixed (v0.32.0)**; the residual is a **product/behavior open item**, not a cage
defect (see below) · **Surface:** receipt/attribution engine

| field | value |
|---|---|
| Observed in | [lab-run-001](2026-07-22-lab-run-001.md) (0 real receipts of 36,451 calls) |
| Corrected by | [2026-07-24 F1 root-cause](2026-07-24-f1-root-cause.md) (on disk, cited) |
| Later evidence | [graphify A/B didn't fire](2026-07-28-finding-graphify-ab-no-fire.md) (golden set) |
| Fix shipped | **v0.32.0** — stale-wiring class fix + `receipts: 0` doctor check |

## Status now (read this first)

The number the run observed — **0 real receipts against 36,451 calls** — was real,
but its *cause* took two corrections to pin down, and the first diagnosis was
wrong. As it stands today:

- **The capture-path defect is RESOLVED (v0.32.0).** The real proximate cause was
  a **dead interceptor verb**, not a missing interceptor: the graphify shim was
  installed and first on `PATH`, but its `cage graphify --help` probe had exited 1
  since the v0.28.0 verb rename, so it silently fell through to the unmetered
  binary. v0.32.0 shipped wiring-liveness detection (`wiringscan.py`), heal-on-
  `cage setup`, an `interceptor` check upgraded from existence+PATH to liveness,
  and the deferred **`receipts: 0 — attribution has no data`** doctor check — so
  the two now report the true cause together. (README "Follow-ups shipped".)
- **The residual is a product/behavior open item, not a cage bug.** Even with a
  live interceptor, real receipt volume on this machine is inherently low because
  agents don't invoke the savings tools unprompted. The golden-set A/B later
  confirmed this directly (`claude -p` / `copilot -p` answered without shelling
  out to graphify) — see [graphify-ab-no-fire](2026-07-28-finding-graphify-ab-no-fire.md).
  That is tracked as its own product-level open finding, not here.

## Superseded first diagnosis (2026-07-22) — kept, visibly wrong

> **Likely cause:** the receipt-emitting paths aren't firing in the real workflow —
> graphify is being run directly rather than through `cage data graphify -- …`, and
> the fux `cage_receipt.py` / compressor / response-cache shims aren't wired or
> aren't pushing.
>
> **Cage fix:** (a) make the graphify interceptor the default path `cage setup`
> wires (verify it's on PATH ahead of the real one) …

**This is superseded.** The interceptor was *already* wired and *already* ahead of
the real binary on PATH — see the correction below. "graphify is being run
directly" and "the interceptor isn't wired" were both false on this machine.

## Evidence (as observed 2026-07-22)

- `total_receipts = 3`, all with `task = fix-handover-bug` (the `cage demo` seed);
  `real_receipts = 0` against 36,451 calls.
- Consequence: attribution (`insights attrib` / `matrix` / `roi` / `verdict`) had
  nothing to divide — every view showed the agent as pure cost (net **−$7,046**).

## History

**2026-07-22 (observed, lab-run-001):** 0 real receipts of 36,451 calls. First
diagnosis (above): interceptor not wired / graphify run directly / shims not
pushing. Proposed fix: wire the interceptor as `cage setup`'s default + a loud
`receipts: 0` doctor check.

**2026-07-24 (corrected — [2026-07-24-f1-root-cause.md](2026-07-24-f1-root-cause.md)):**
the first diagnosis was wrong; four corrections, all evidence-backed:

1. **"No real savings ever captured" is false machine-wide.** True *for `~/.cage`*
   (that global ledger held no `receipts*.jsonl`), but `anton/.cage/ledger/
   receipts.jsonl` holds 8 rows, **5 real** (graphify `probe-grid` 67,080 tok;
   fux hook-recall 228/37/162/236 tok; the other 3 are the demo seed). Receipts
   are written to the *resolved* ledger root, so a project keeps its own; the 36k
   calls live in the *global* ledger. A global-only sweep is structurally blind to
   project-local receipts — numerator and denominator came from different sinks.
   (`compressor`/`responsecache` have still never produced a real receipt — that
   part of the finding stands.)
2. **Real root cause: a dead interceptor, not a missing one.** `which -a graphify`
   showed the cage shim first; but its capability probe (`cage graphify --help`)
   exits 1 since v0.28.0 removed the `graphify` verb, so it `exec`s the raw binary
   unmetered and silent. Reproduced with the F6 instrument: `cage data graphify --
   graphify query …` filed a real 74,563-tok receipt; the bare `graphify query …`
   (how it's actually invoked) produced no receipt and **no debug line at all** —
   the interceptor-never-invoked signature. A silently-failing push (H1) was ruled
   out.
3. **This is a class failure, not a graphify one.** The same v0.28.0 rename
   orphaned the global Claude `SessionStart` hook (`import-claude` → exit 1) and
   every pre-2026-07-15 wiring artifact naming any of the 31 verbs in
   `verbmap.REMOVED`.
4. **The proposed fix wouldn't have worked.** `doctorcmd._interceptor` tested
   existence + PATH — exactly the two things that were already true — so it would
   have reported ✅ OK the whole time the shim was dead. Existence + PATH is not
   liveness. And H3 holds independently: real receipt volume would be low even with
   a perfect interceptor, so the `receipts: 0` check had to ship *with* stale-wiring
   detection or it would read as H3 and mislead. (An instrument caveat — `debuglog`
   silent under `CAGE_BASE`/`--ledger` — was fixed in v0.31.4.)

**v0.32.0 (shipped — README "Follow-ups shipped"):** the stale-wiring class fix.
Detection of any installed artifact naming a verb the live CLI parser rejects
(`wiringscan.py`, user-level files included), healing on `cage setup`,
`interceptor` upgraded to a liveness probe, and the deferred `receipts: 0`
attribution-has-no-data check shipped alongside so the two report the true cause
together.

**2026-07-28 (golden set — [graphify-ab-no-fire](2026-07-28-finding-graphify-ab-no-fire.md)):**
with the wiring healed, the savings path was validated live (a real
`saved=11,692` modeled receipt), but the driven A/B still produced 0 rows because
the agents didn't invoke graphify unprompted. Confirms the residual is
product-level (agent behavior), not a capture defect.

## Bottom line

The capture-path bug F1 pointed at is fixed. The "0 real receipts" number is
*not* evidence of a broken meter — it's a global-only view of a machine whose
project ledgers held a handful of real receipts, on which the savings tools were
barely exercised, behind an interceptor that was dead for an unrelated wiring
reason. The one thing still open — agents not invoking savings tools on their
own — is a product question, tracked in its own finding.
