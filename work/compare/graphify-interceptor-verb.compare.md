# graphify-interceptor-verb.compare.md — SHIM-DEAD-VERB: what replaces the probe SURFACE-CUT deleted

**Fork:** `cage data graphify` — the verb both interceptor twins probe — was deleted by
SURFACE-CUT (v0.50.0, `cb4a4a6`). The twins were left untouched, deliberately (Arpit,
2026-08-14). This doc is the fork that leaves open: **restore a verb, retire the route, or
make the dead state honest.**

**Status:** proposed verdict **B**, awaiting Arpit's accept or override.
**Relates:** [ADR-GRAPHIFY](../../docs/adr/0007_graphify.md) §2 B5/B3 ·
[ADR-COVERAGE](../../docs/adr/0008_coverage.md) §1 *Derived surfaces* ·
[ADR-CLI](../../docs/adr/0002_cli.md) · OPEN-WORK **SHIM-DEAD-VERB**

---

## 1 · What is actually true today (measured, not inferred)

| # | fact | evidence |
|---|---|---|
| 1 | Both twins probe `cage data graphify` | `cage/data/shims/graphify` (6 occurrences) · `graphify.cmd` (9) |
| 2 | The verb does not exist | no `add_parser("data"…)` in `cage/cli.py`; the whole group went in `cb4a4a6` |
| 3 | The metering engine is **intact** | `graphifymeter.run(root, argv, task)` untouched — only the CLI leaf that called it was deleted |
| 4 | Restoring it is **8 lines** | deleted leaf = 6 lines of parser (`cli.py` ~646-651) + handler `cmd_graphify` = 2 lines (`clicmds.py` ~449) |
| 5 | `cage setup` **still installs the dead twin** | `clicmds.cmd_setup` → `adoptcmd.run(graphify=True)` → copies both shims verbatim from package data |
| 6 | `cage doctor` **fails loudly** — the F1 lesson held | `doctorcmd._interceptor` → `scan.dead_interceptors` ⇒ `_FAIL`; `_path_interceptor` state `dead` ⇒ `_FAIL` |
| 7 | …but its **fix hint cannot fix it** | hint says re-run `cage setup --wire-only`; `verbmap.REMOVED["graphify"] = ""` (removed outright) and `wiringscan.heal_tail` skips empty fixes |
| 8 | 15 tests red | `test_pathshim` ×8 · `test_win_graphify_shim` ×5 · `test_wiringscan` ×1 · `test_gf_launcher_arm2` ×1 |
| 9 | A **hidden machine-spawned verb** is already a shipped category | `cli.py` ~653-658: `mcp`, `demo`, `debug` — `help=argparse.SUPPRESS`, in-code as *"callable, off the front door… none are daily human verbs"* |

**Net effect.** No user breakage — B6 passthrough holds, so `graphify` still runs correctly
and unmetered. But **the interceptor route captures nothing, on every OS, for every agent**,
and a fresh `cage setup` today scaffolds an artifact that can never meter and that doctor
immediately fails with an unactionable fix.

### The two consequences that are not obvious

- **kiro-IDE now files nothing at all.** ADR-COVERAGE's matrix marks *Tool savings, via the
  interceptor* ✅ on all six surfaces and annotates kiro-IDE **"the only route here"** — that
  surface has no store-side fallback by construction. Its savings column is not degraded, it
  is gone. ADR-COVERAGE's own Consequences section predicted exactly this: *"If the PATH
  interceptor is not live, kiro-IDE's savings row is not degraded — it is gone."*
- **The spelling is load-bearing.** B3's marker set (`cage data graphify` / `cage graphify` /
  `graphify metering interceptor`) is what makes twins skip each other, and it is compiled
  into every shim already written to every machine. Restoring the verb **at the same
  spelling** heals every installed shim with zero user action. Any *new* spelling leaves
  every installed shim permanently dead unless re-scaffolded, and needs a non-empty
  `verbmap` tail before `heal_tail` will rewrite it.

---

## 2 · Options

**A — Retire the interceptor.** Delete both twins, `pathshim`, the `--no-graphify` flag and
adoptcmd's shim half; ADR-GRAPHIFY drops from four routes to three; ADR-COVERAGE's
interceptor row becomes ❌ everywhere. 15 tests go green by deletion.

**B — Restore `cage data graphify` as a hidden verb.** Re-add the deleted leaf at the
identical spelling, with `help=argparse.SUPPRESS`, in the `mcp`/`demo`/`debug` category.
Nothing else moves: no shim edit, no marker change, no re-scaffold.

**C — Keep it dead, make the dead state honest.** Give `verbmap["graphify"]` a removal
sentence, repoint doctor's fix hint to *"delete `bin/graphify` — the route is retired"*,
flip `cage setup` to `graphify=False` by default, keep the twins and §2's contract as the
documented template for the next interceptor. Re-point the 15 tests rather than delete them.

**D — Park it.** Leave as-is until the ledger restructure lands.

## 3 · Matrix

| | A retire | **B hidden verb** | C honest-dead | D park |
|---|---|---|---|---|
| Heals already-installed shims | n/a | **✅ zero user action** | ❌ they stay dead | ❌ |
| kiro-IDE savings | ❌ gone | **✅ restored** | ❌ gone | ❌ gone |
| `cage setup` stops shipping a broken artifact | ✅ | **✅** | ✅ | ❌ **accrues per install** |
| Cost | ~9 modules + both twins + ADR §2 (~150 lines) | **8 lines + ADR-CLI row** | ~30 lines across 4 sites | 0 |
| 15 red tests | green by deletion | **green as written** | need re-pointing | stay red |
| Keeps the interceptor contract as the tool-integration template | ❌ deletes it | **✅** | ✅ (as history) | ✅ |
| Concedes SURFACE-CUT's thesis | no | **no — hidden ≠ front door** | no | no |
| Reversible | ❌ expensive | **✅ trivially** | ✅ | ✅ |

## 4 · Proposed verdict — **B**, at the identical spelling

1. **Cheapest by an order of magnitude** — 8 lines against ~150 (A) or ~30 (C), and the
   engine it re-exposes (`graphifymeter.run`) was never touched.
2. **It is the only option that repairs machines already in the field**, because B3's marker
   set is already burned into every installed shim (fact 9 above).
3. **It concedes nothing to SURFACE-CUT.** That change narrowed the *human* front door; a
   hidden, machine-spawned verb was never on it. `mcp` is the precedent, in the same file,
   with the same justification written in-code.
4. **It keeps ADR-COVERAGE's matrix true** rather than requiring six cells to be
   downgraded — and keeps kiro-IDE's only capture route alive.
5. **It preserves the interceptor contract as a live artifact**, which ADR-GRAPHIFY §2
   explicitly designates *"the first artifact of the tool-integration contract"* for every
   future tool.

**If Arpit prefers the surface to stay cut, take C, not D** — D is the only option under
which damage accrues (every `cage setup` between now and the decision writes a dead shim).

**Not in scope of this verdict:** whether the interceptor is worth keeping at all on its
merits. That is option A's real question and it deserves its own fork if Arpit wants it —
it should not be decided as a side effect of a deleted verb.

## 5 · Reopen trigger

- **B is reopened** if a second consumer of the `data` group never materialises *and* a
  measured count of interceptor-filed receipts stays at zero over a window with ≥5 real
  graphify runs on a machine where the store routes also fired — i.e. the interceptor is
  live but redundant with import-time detection. That measurement does not exist today.
- **A becomes live** if a named third tool interceptor is built and the contract graduates
  to a shared artifact — at which point the graphify twin is no longer the template and can
  be judged on its own capture value.
- **C is reopened** by any decision to re-expose a `data` group for another reason.

---

## 6 · Three findings this review turned up alongside the fork

Filed here because they were found in the same pass; each is independent of the verdict.

**F-1 · Two ADRs assert a route that was dead the same day they were written.**
ADR-GRAPHIFY's frontmatter reads *"four capture routes live"* and ADR-COVERAGE's matrix
marks the interceptor ✅ on all six surfaces — both dated 2026-08-14, the day the verb was
deleted. ADR-DISCIPLINE (`02c3c98`, same day) requires the owning ADR to move in the same
change. Whichever way this fork resolves, **both frontmatter lines and the matrix row need
the true state.** Under B the fix is a dated note; under A/C the row changes.

**F-2 · `docs/FORMULAS.md` §2.7 has been false since v0.47.0 (7 days, two restructures).**
It still says copilot **VS Code** is *"usage-row-only (F2: its `chatSessions` log has the
command but not the result)"* and *"Kiro is HONEST-LIMIT (no tool bodies in the log)"*.
Both routes shipped in v0.47.0 and both are ✅ in `graphifytx.GRAPHIFY_COVERAGE`. §2.10 also
composes into `insights verdict graphify`, deleted by SURFACE-CUT. This is precisely the
drift ADR-COVERAGE's veto says *"is caught by review alone"* — review did not catch it
twice, which under the two-strikes rule makes it a gate candidate.

**F-3 · `graphifymodel` is orphaned — the forward model has no reader.**
`repo_ceiling` (the bounded "worth installing here" number) and `history_band` are reachable
only from `tests/` and the explain registry; their two consumers (`insights verdict graphify`
and `cage report`'s ceiling footer) were both deleted. This is the **UNREAD-FACTS** class:
decide whether it earns a read surface or the module is retired. Note it is the *only*
surface that ever answered *"what would graphify save me here"* without receipts — the
day-one question, now unanswerable.
