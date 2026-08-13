---
doc: dogfood snapshot — 2026-08-02
snapshot_date: 2026-08-02
snapshot_version: 0.43.0
window: all-time (ledger's first row 2026-02-15 through 2026-08-02, no --since)
ledger: global (~/.cage)
---

# Dogfood snapshot — 2026-08-02

Real numbers from the dev machine's own global `~/.cage` ledger — the ledger built by
using Claude Code, Copilot and Kiro to build cage itself (and everything else run on
this machine over the same window). Pasted verbatim; method tags intact. This is not
the seeded `cage demo` example the README's headline table uses — see
[the honest-numbers paragraph](../../README.md).

**`cage insights attrib` is intentionally absent from this snapshot.** Every row in
the global ledger's `task` field, checked at publish time, comes from the
`cage demo` seed itself (`session: "demo"`, task `fix-handover-bug`, timestamped
2026-07-23) — no real task on this machine has been tagged/closed yet. Publishing that
would be exactly the dummy data this feature exists to never show. It will appear in a
future snapshot once a real task exists to attribute.

## `cage report --usd --why-ledger`

```
· ledger: global (~/.cage) → /Users/arpitarya/.cage (route-key a45283ee3ef4075c)
· captured 1611 new calls (claude) + 1 graphify saving since last read
Ledger by route · usd

route       calls          tok in     tok out                      cost
---------  ------  --------------  ----------  ------------------------
chat       52,178  11,783,546,701  51,187,181               $9,921.4105
code-edit       1           8,600       1,500                   $0.0483
TOTAL      52,179  11,783,555,301  51,188,681  $9,921.4588 (+ unpriced)

≈ priced by family (approximate — no exact price row):
  claude-haiku-4-5-20251001 → claude-haiku-4-5
  claude-haiku-4.5 → claude-haiku-4-5
  claude-opus-5 → claude-opus-4
  copilot/claude-haiku-4.5 → claude-haiku-4-5
  copilot/claude-opus-4.6 → claude-opus-4-6
  copilot/claude-sonnet-4.6 → claude-sonnet-4-6
· cache: 98% of input tokens were cache reads, 71% of cost ($7,012.8514 of $9,921.4588)
· kiro: input-only log — cost understated; its rows also carry no per-turn time, session or project (`cage query kiro-routing`)
⚠ 33 calls (1,276,213 tokens) UNPRICED — totals understated
  fix: cage prices alias - 'copilot/auto' --to <provider>/<model>   # route the router pseudo-model explicitly
· graphify repo ceiling ≈ 482,949 GROSS tokens per architecture question (modeled, largest community; typical ≈ 3,439) — `cage insights verdict graphify` for the derivation
```

The `code-edit` row (1 call, $0.0483) is the `cage demo` seed call itself, sitting in
the same global ledger as everything else — real numbers include it because the ledger
is append-only and this is what capture-on-read actually returns; it is not
independently filtered out of `report` (only `attrib`'s task-level view was, above).

## `cage insights adoption --why-ledger`

```
· ledger: global (~/.cage) → /Users/arpitarya/.cage (route-key a45283ee3ef4075c)
Adoption — which tools your agents actually invoke
  counts only; usage rows are diagnostic and are never priced

A · invocations — graphify usage breadcrumb (exact, agent-blind)

op     runs  receipt  unmeasurable  empty  non measured  error
-----  ----  -------  ------------  -----  ------------  -----
query     2        2             0      0             0      0

route       runs  receipt  unmeasurable  empty  non measured  error
----------  ----  -------  ------------  -----  ------------  -----
transcript     2        2             0      0             0      0

B · per-agent attribution — savings rows joined to a call's agent

agent   tool        rows  joined via
------  ----------  ----  ------------
claude  compressor     1  call
claude  fux            1  call
claude  graphify       5  call+session

· coverage: 7 of 7 savings rows (100%) are agent-attributable
· no evidence of invocation: codex, copilot, kiro
    — calls in this window, zero savings rows, and every savings row that exists
    was attributed. Absence of evidence, not proof of non-use: a run cage never
    saw looks identical to one that never happened.
```

Note: `codex` appears in the "no evidence of invocation" line because 373 calls in the
global ledger still carry `agent: "codex"` from before its v0.33.0 removal as a
supported surface (old ledger rows still read — a product/scope decision, not a capture
gap; see `work/archive/*-codex-removal.handoff.md`). Read literally per
`cage query tool-adoption`, not as evidence codex is a currently-wired agent.
