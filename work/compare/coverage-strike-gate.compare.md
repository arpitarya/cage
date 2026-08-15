---
doc: compare — what mechanical gate, if any, follows COVERAGE-STRIKE-2/3
status: proposed verdict D, awaiting Arpit's accept or override
decides: OPEN-WORK **COVERAGE-STRIKE-2**
---

# coverage-strike-gate.compare.md — does two-strikes actually point at a generator?

**Fork:** [ADR-COVERAGE](../../docs/adr/0002_coverage.md) §3 parked a full generated coverage
matrix, reopened on "found stale twice." STRIKE 1 (2026-08-14, interceptor row) and STRIKE 2
(2026-08-14, legend + authorship marks) hit that threshold, and the ADR's own text logs a
"Decision needed": extend `tests/test_formulas_coverage.py`'s pattern to ADR-COVERAGE's two
✅/N-A tables, or accept the record's failure mode is prose and stop counting strikes. Then
STRIKE 3 (2026-08-15, copilot-CLI Chat-title cell) landed, and the ADR itself says the named
remedy would **not** have caught it. Filed to Arpit rather than decided by the sweep that found
it — this doc is that decision.

**Status:** proposed verdict **D**, awaiting Arpit's accept or override.
**Relates:** ADR-COVERAGE §1 (the STRIKE-3 paragraph) · §3 *Deliberately not taken* (STRIKE 1/2) ·
`tests/test_formulas_coverage.py` (the existing, narrower precedent it would extend) · OPEN-WORK
**COVERAGE-STRIKE-2**

---

## 1 · What is actually true today (measured, not inferred)

| # | fact | evidence |
|---|---|---|
| 1 | A generator over one registry already exists and works | `tests/test_formulas_coverage.py` gates `docs/FORMULAS.md` §2.7 from `graphifytx.GRAPHIFY_COVERAGE` only |
| 2 | Five registries are named as the candidate sources for a fuller one | ADR-COVERAGE §2 Context: `ledger.ABSENT_SPINES` · `units.ABSENT` · `authorcapture.COVERAGE_GAPS` · `graphifytx.GRAPHIFY_COVERAGE` · `agents.HOOK_EVENTS`/`HOOK_GAPS` |
| 3 | **Four of the five are agent-level, not agent×surface-level** | `units.ABSENT` has 3 keys total (`claude`, `kiro`×2); `authorcapture.COVERAGE_GAPS` has 2 (`copilot`, `kiro`); `ledger.ABSENT_SPINES` has 1 (`kiro`); `agents.HOOK_GAPS` is per-agent. ADR-COVERAGE's *Usage capture* and *Derived surfaces* tables are 6-column, **agent × CLI/IDE** |
| 4 | Only `GRAPHIFY_COVERAGE` is already surface-grained | `(agent, surface, ok, why)` tuples — the one registry a generator can reuse as-is |
| 5 | Six of *Usage capture*'s eight rows have **no backing registry at all** | cache-read/write tokens, thinking/cache-TTL/server-tool split, sub-agent split, working-dir stamp, per-chat identity — every one sourced from a dated §2 Reference probe, never a code constant |
| 6 | STRIKE 3's own cell (Chat title) has **no backing registry at all** | no title-coverage table exists in `cage/*.py`; `chats._title_map` / `importcmd.session_name_copilot_cli` compute a *value*, not a *capability flag* a generator could read |
| 7 | STRIKE 2 was two prose contradictions, neither table-shaped | the stale ⛔-legend sentence and the ⚠️→✅ authorship-mark error both live in prose no registry touches |

**Net effect.** ADR-COVERAGE's own "small… the obvious next step" framing undersells the cost.
A generator faithful to the tables **as rendered** (6 columns, not 3 agent-level buckets) needs
new surface-grained registries for most of *Usage capture* and for *Chat title* — real, separate
backlog work, not a re-derive of what already exists. Built as literally scoped, it either (a)
requires writing 6+ new registries, or (b) generates a coarser agent-level claim that quietly
loses the CLI/IDE split the table currently makes — a precision regression dressed as a fix.

## 2 · Options

**A — Build the full generator as originally parked**, over all five named registries plus
whatever new ones reach surface-grain. Closes STRIKE 1/2's table-shaped half in full.

**B — Extend `test_formulas_coverage.py`'s pattern to the two ✅/N-A tables, using only
registries that exist today**, accepting agent-level grain where finer isn't available. This is
COVERAGE-STRIKE-2's option (a) as it can actually ship — **without** new registries.

**C — Build the missing registries first** (a `TITLE_COVERAGE`-shaped table, the *Usage
capture* field flags), then revisit A/B. Not decided here — filed as its own OPEN-WORK residual
regardless of this fork's outcome, since it is capability-tracking work, not a gate extension.

**D — Close the two-strikes counter on the generator (the ADR's own option (b)); build no new
coverage-generator gate.** Accept STRIKE 1–3 as review-caught drift a table-diff cannot reach
without disproportionate new registry work.

## 3 · Matrix

| | A full generator | **B narrow generator** | C build registries first | D close the counter |
|---|---|---|---|---|
| Cost | 6+ new registries + generator (large, open-ended) | ~1 test file, existing registries only (small) | scoped registry work, size TBD per field | 0 |
| Catches STRIKE 1 (interceptor row) | ✅ | ✅ — via `GRAPHIFY_COVERAGE`, already possible | ✅ eventually | ❌ |
| Catches STRIKE 2 (prose/legend) | ❌ not table-shaped | ❌ | ❌ | ❌ (unaddressed either way) |
| Catches STRIKE 3 (Chat title) | ❌ without a new registry | ❌ | ✅ once that registry exists | ❌ |
| Precision vs. the rendered table | kept, if registries reach grain | **lost** on 6/8 *Usage capture* rows | kept | n/a — no gate |
| New backlog opened | large, undefined scope | none | one scoped item | none |
| Matches §3's own rejection reasoning ("prose reasons flatten") | contradicts it for newly-built rows | mostly avoids it — gates only existing flags, never a reason | avoids it, if built carefully | agrees with it |

## 4 · Proposed verdict — **D**, close the counter; file C as separate optional backlog

1. **The premise the two-strikes rule assumes doesn't hold for this record.** CLAUDE.md's rule
   targets a repeated failure class *a mechanical gate can close*. STRIKE 1 was table-shaped and
   cheaply closeable (B, today). STRIKE 2 and STRIKE 3 were not: one was prose contradicting
   prose, the other a value with no registry behind it at all. Three strikes span two different
   failure classes, and only one of them a table-diff generator ever addresses — counting them
   together over-indexes the trigger.
2. **B is real and cheap — ship it on its own merits, not as the STRIKE-2/3 fix.** It costs about
   what `test_formulas_coverage.py` already cost, and would have caught STRIKE 1 outright. It
   should not be presented as "the generator the two-strikes clause was pointing at," because it
   provably isn't for the other two strikes.
3. **C is legitimate future work but isn't this fork's call.** A title-capability registry (and
   the missing *Usage capture* field registries) could plausibly prevent a STRIKE-3-shaped repeat
   — but it's new capability-tracking code, sized on its own, not a gate extension riding in under
   this ticket.
4. **What actually catches a STRIKE-3-shaped drift is unchanged: review, on contact, when the
   underlying function changes** — the same class of drift CLAUDE.md's own "deleting a doc is a
   citation migration" rule already accepts is human-caught. No invented gate should claim
   otherwise.

**If Arpit wants the fuller precision instead of accepting the gap:** take C, sized as its own
item, rather than stretching COVERAGE-STRIKE-2 to cover it.

## 5 · Reopen trigger

- **D is reopened** if a fourth stale-cell incident is found **and** it is table-shaped — a
  registry existed and the doc simply didn't match it. That's squarely B's target, so shipping B
  should already prevent a repeat of exactly this shape.
- **C becomes worth doing** if a stale-cell incident hits a *Usage capture* field row or the
  *Chat title* row a second time — the two classes STRIKE 3 showed have no registry today.
- **A stays parked** regardless of this verdict — nothing found here makes the full
  five-or-six-registry generator cheaper than it was when §3 first rejected it.

---

## 6 · One finding worth filing regardless of the verdict

**F-1 · `units.ABSENT` and `authorcapture.COVERAGE_GAPS` are agent-level, but ADR-COVERAGE
renders them as if they were agent×surface-level.** Nothing is wrong today — no cell was found
false because of this — but a future edit to either registry that is only true for one surface
(e.g. a copilot-CLI-only fix) has no code-level way to avoid also reading as true for copilot-IDE
in the ADR's table. This is one level upstream of what STRIKE 3 exploited (there, the registry
didn't even exist); worth naming so a fourth strike doesn't repeat it at this layer instead.
Independent of A/B/C/D above.
