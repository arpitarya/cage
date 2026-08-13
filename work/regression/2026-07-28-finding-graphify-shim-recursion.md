# Finding — stacked graphify shims recurse → hang

**Severity:** MED · **Status:** ◻ OPEN (cage shim hardened; stale-artifact hazard
remains) · **Surface:** wiring / PATH interceptors

| field | value |
|---|---|
| Observed in | [run-002](2026-07-28-validation-run-002.md) (graphify-ON cells hit the 2-min cap) |
| Cage-side fix | [capture-precision-fixes §MED](2026-07-28-capture-precision-fixes.md) |

## What happens

- Two graphify interceptors on the test machine's PATH: the **fresh** one
  `cage setup` wrote (`workspace/bin/graphify` → `cage data graphify`) and a
  **stale** one from an old `cage adopt` (`~/my_programs/anton/bin/graphify` → the
  **removed** `cage graphify` verb).
- Each shim removes only *its own* dir before resolving the "real" graphify, so
  with both on PATH they resolve to **each other** → infinite mutual recursion →
  the wrapped call hangs (hit the 2-min cap).
- The stale `anton/bin/graphify` is itself a dead-verb wiring-liveness artifact
  (`cage graphify --help` fails now; it falls through to the real binary, but its
  *presence on PATH* is what closes the recursion loop).

## Status

- **Cage shim hardened** (capture-precision-fixes §MED): the shim now skips
  **every** cage interceptor when resolving the real binary, refuses to fall back
  to the bare name (exit 127, no re-entry), and adds a `CAGE_GRAPHIFY_SHIM`
  re-entry guard. Verified: stacked shims + a real binary resolve to REAL, no hang;
  only-interceptors exits 127.
- **Lab safety net:** `drive.py` drops any PATH dir whose `graphify` shim names the
  removed verb (protects the ON cells — a driver mitigation, not a cage fix).
- **Why still OPEN (product-level):** the *root artifact* — a stale, dead-verb
  foreign shim left on a real machine's PATH — is a wiring-hygiene hazard the
  hardened shim mitigates but does not erase. Reopens if a stacked-interceptor hang
  is seen again in the wild.
