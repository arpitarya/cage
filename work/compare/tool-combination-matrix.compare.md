# tool-combination-matrix.compare.md — MATRIX-REVIVAL: does the tool-combination cost view come back, and how does it hold a tool with no receipts yet

**Fork:** Arpit asked (2026-08-15) for a matrix of token cost/savings across tool
combinations — vanilla agent, agent+graphify, agent+graphify+caveman (a proposed future
Tier-2 compressor, unbuilt). That view — `cage insights matrix` / `cage insights compare`
— was deleted in SURFACE-CUT (v0.50.0, 2026-08-14, `CHANGELOG.md`). The join engine that
computed it, `taskgroup.py`, was not deleted. This doc is the fork: does the view come
back, and if so, how does it represent a tool that has never filed a receipt.

**Status:** **DECIDED — verdict B accepted by Arpit, 2026-08-15, ratified as
[ADR-MATRIX](../../docs/adr/0014_matrix.md).** The code (`cage/matrixview.py` + the CLI
leaf) is **not built** — tracked as a build item under ADR-MATRIX in
[OPEN-WORK.md](../OPEN-WORK.md). **Same-day amendment (still 2026-08-15):** Arpit asked
that the view work "for claude, kiro, copilot independently" — the three named-tool
combinations computed per agent, never pooled. Folded into ADR-MATRIX §1/§2 directly
(agent bucket derived from a task's joined calls, unanimous-only) rather than reopening
this fork — it narrows verdict B's shape, it doesn't change which option won.
**Second same-day correction:** Arpit then asked to double-check claude-vs-credits —
right call: `ledger.SPEND_SOURCES["kiro"] = ()` (`ledger.ABSENT_SPINES`) means Kiro
contributes zero rows to `ledger.spend()`, permanently — it has no token spine to put
in a table at all, unlike copilot (which does spend token rows, plus an unrelated
`credits` field). ADR-MATRIX §1/§2 now render kiro as a fixed no-data notice, not a
token table. Still narrows verdict B's shape; still not a reopened fork.
**Relates:** [ADR-MATRIX](../../docs/adr/0014_matrix.md) (the ratified record) ·
[ADR-CLI](../../docs/adr/0003_cli.md) ·
[ADR-GRAPHIFY](../../docs/adr/0008_graphify.md) · `CLAUDE.md` *Must-Know Rules*
(usage-never-cost) · `CHANGELOG.md` `## v0.50.0` entry. The SURFACE-CUT decision itself is
archived (`work/archive/v0.50-surface-cut.decision.md`) — named here for history, not
cited as backing (CLAUDE.md *Archived documents are named, never cited*); every claim
below is grounded in a live source instead.

---

## 1 · What is actually true today (measured, not inferred)

| # | fact | evidence |
|---|---|---|
| 1 | `cage insights matrix`/`compare` do not exist | no `add_parser` for either in `cage/cli.py`; `cage/compare.py` is absent from the tree |
| 2 | The join engine is intact | `cage/taskgroup.py` — `join`/`join_rows`/`closed_tasks`, still imported by `cage/commitjoin.py` |
| 3 | "Stack" grouping was already designed in, not invented now | `taskgroup.GROUP_KEYS = ("stack", "scope", "label")` and the module docstring's own definition of a stack signature |
| 4 | The stack signature is already the right shape for this ask | "sorted set of `tool` values on the task's joined receipts, `human` excluded... Empty set ⇒ `agent-only`" (`taskgroup.py` docstring) |
| 5 | The deletion was scoped, not absolute | `CHANGELOG.md` `## v0.50.0`: "**Survives in `cage insights`:** `chats` · `graphify` · `commits` · `commit` · `why`" — `insights` as a group was kept |
| 6 | Every input the matrix would join is still measured, not modeled | `ledger.spend` (calls, tokens_in/out) and `ledger.receipts` (savings rows) are both live, unchanged code paths |
| 7 | The tool-savings namespace already anticipates more than one savings tool | `docs/GLOSSARY.md` "per-producer directory": `graphify/ fux/ compress/ responsecache/` all reserved under `ledger/`, refused-at-write-time on collision (`paths.reserve_tool_name`) |
| 8 | A not-yet-built tool has a stated integration point already | `cage/compress.py` docstring: "The learned Tier-2 compressor is a pluggable adapter over this same receipt shape" |
| 9 | The measured/modeled split is enforced in three independent places already | `cage/savings.py` `GROSS_NOTE` · `cage/graphifymodel.py` ("never blended, never summed into a measured total") · `CHANGELOG.md` v0.50.0 ("cage measures usage, never cost") |

**Net effect.** Nothing needs inventing. The join, the grouping key, the namespace and the
measured/modeled discipline all already exist; only the CLI leaf and its renderer are gone.

---

## 2 · Options

**A — Leave it cut.** SURFACE-CUT's own thesis was that the old reporting surface was
disproportionate to a usage meter. Answer Arpit's question ad hoc (a one-off script, or a
`cage query` explainer) rather than adding a permanent command.

**B — Revive `cage insights matrix` as a new, narrow, tokens-only view.** Not a
resurrection of the deleted `compare.py` (which was money-coupled — it priced totals via
`prices.call_usd`, per `CHANGELOG.md`'s own description of the old command). A new
`cage/matrixview.py` built on `taskgroup.join`, rendering measured stack-signature rows
only, tokens-only, with a separately-labelled modeled section for any tool with zero
receipts.

**C — Add it as a flag on an existing view instead of a new command.** E.g.
`cage insights commits --by-stack`. Reuses an existing leaf, avoids a new top-level noun.

**D — Park it.** Do nothing until caveman itself is designed, on the grounds that a matrix
with one real column (`agent-only` vs `agent+graphify`) and one permanently-empty row
(`+caveman`) is not yet worth building.

## 3 · Matrix

| | A leave cut | **B new narrow view** | C flag on `commits` | D park |
|---|---|---|---|---|
| Answers the question asked | ❌ | **✅** | ✅ | ❌ |
| Reuses the surviving join engine | n/a | **✅ `taskgroup.join`, zero new join logic** | ✅ same engine | n/a |
| Repeats SURFACE-CUT's stated mistake (money-coupled, disproportionate) | n/a | **no — tokens-only from line 1, no `prices` import** | no | n/a |
| Cost | ~0 (a `cage query` entry) | **one module + one CLI leaf + tests, mirrors `insights graphify`'s shape** | smaller, but conflates "per-commit" and "per-stack" grains in one view | 0 now, unbounded later |
| Honest about caveman being unbuilt | n/a | **✅ — 0-task row, never faked** | ✅ | n/a |
| Matches the name Arpit already used, and the name SURFACE-CUT's own record used for this view | ❌ | **✅** | ❌ new shape | ❌ |
| Reversible | ✅ trivially | **✅ — one module, no substrate change** | less — bolted onto a stable view | ✅ |

## 4 · Proposed verdict — **B**

1. **The engine is already paid for.** `taskgroup.py` survived the cut specifically
   because `commitjoin` needed it — B spends nothing on new join logic, only a renderer.
2. **It does not repeat SURFACE-CUT's stated reason for cutting the old surface.** The
   old `compare.py` priced totals in USD; B never imports `prices` and never resolves a
   `display` context — the same discipline `commitview.py` already documents for itself
   ("no USD on this surface, by design").
3. **C is real but conflates two grains.** `insights commits` is per-commit; a
   stack-signature rollup is per-closed-task. Bolting one onto the other's flags makes
   both harder to reason about later — worth a note, not the verdict.
4. **D is the only option under which the underlying data keeps accruing with no reader**
   — the same class OPEN-WORK.md's `UNREAD-FACTS` item already names for `route_key`,
   `state/attest.jsonl`, `scope`, and task `label`/`outcome`. Task `label`/`outcome` is on
   that list *because* `compare`/`calibration` died — B is that gap's own remedy, not a
   new one.

## 5 · Reopen trigger

- **A becomes live** if Arpit decides a one-off answer is enough and no second question
  ever needs the same join.
- **B is reopened for narrowing** if, once built, the `agent+graphify+caveman` row stays
  at `0 tasks` for a long stretch after caveman ships receipts — a signal the stack never
  actually forms in practice and the view should collapse to two columns.
- **C becomes live** if a second per-commit-or-per-task cross-cut is requested later and a
  combined "sliceable" view is worth paying the conflation cost once instead of twice.
- **D is not really an option that gets "reopened"** — it is the default until this
  verdict is accepted.

---

## 6 · One finding this review turned up alongside the fork

**`docs/example/cli.md` still lists `cage insights matrix` as a live command** (its
`Read` section: `"cage insights matrix        # tool × tool savings grid"`). It has been
dead since 2026-08-14. This is doc-drift independent of the verdict above — under B the
line becomes true again; under A/C/D it needs to be struck. Filed here rather than fixed
silently, per the doc-drift-is-a-citation-migration rule in `CLAUDE.md`.
