# Handoff — `cage query` concept layer + CLI help grouping

**Status:** spec-first. Build prompt in `cage-query-concepts.build-prompt.md`.

**Already shipped (do not redo):** `cage/constants.py` (the three-layer numbers
story) and `cage query` with **calculation** topics — `cage/explain.py` has a
`REGISTRY` of 12 entries (`human-cost`, `cost`, `saved`, `matrix`, `confidence`,
…), live value interpolation via `_live(pol)`, and `match` / `closest_ids` /
`payload` / `render` / `render_list`. The top-level parser already has a
`description`.

**This handoff adds the two remaining pieces:**

1. **the concept layer** — `cage query` should explain *how cage itself works*
   (data flow, fail-open metering, attribution, method tags, receipts, …), not
   only how a value is computed;
2. **CLI help grouping** — group the subcommands into categories in `cage --help`.

---

## 0. Module structure — split data from engine

Adding concept entries pushes `explain.py` well past the module size budget. Split
it: move the `REGISTRY` tuple into a new **`explain_data.py`** (a pure declarative
table; `explain.py` imports `REGISTRY` from it) and keep the `Explanation`
dataclass + the engine (`_live`/`_score`/`match`/`closest_ids`/`render`/`payload`/
`render_list`) in `explain.py`. The ≤100-line rule governs *logic* complexity, so
the engine should land near budget while `explain_data.py` is exempt as a data
table — same status as `policy.toml` / `constants.py`. Unique-`id` invariant
(`_BY_ID`) is unchanged; just sourced from the data module.

## 1. Concept topics — extend the existing registry, don't rebuild it

Add a second *kind* of entry to the **existing** `explain.py` registry so one
`cage query` answers both "how is X calculated" (the entries already there) and
"how does cage work" (new).

**Schema change — add `kind` to `Explanation`** (and a `plan_ref`):

```python
@dataclass(frozen=True)
class Explanation:
    id: str
    kind: str = "calculation"          # "calculation" | "concept"  (default keeps
    keywords: tuple[str, ...] = ()      #   the 12 existing entries valid unchanged)
    summary: str = ""
    body: str = ""                      # formula (calculation) OR mechanism (concept)
    code_refs: tuple[str, ...] = ()
    plan_ref: str = ""                  # docs/cage-plan.md § — for concept entries
    method_note: str = ""
```

Tag the 12 existing entries `kind="calculation"` (one-word touch each) and append
the **concept** entries below.

**Concept entries to seed** (ids · what they explain):

| id | explains |
|----|----------|
| `overview` / `how-cage-works` | the front door: the one-way data-flow diagram + the laws, with "see also" pointers to the sub-topics |
| `data-flow` | `record_call`/`record_receipt` → append-only `ledger/{calls,receipts,tasks}.jsonl` → derive every view ($0) |
| `metering` | the four surfaces (library / proxy / transcript / MCP), **fail-open** — a metering error never breaks a call |
| `attribution` | marginal-by-fixed-order; why marginals sum to the total with no overlap; why not Shapley (deferred audit mode) |
| `matrix-concept` | the 2ⁿ counterfactual; only the configuration actually run is `measured` |
| `method-law` | `measured` vs `modeled` vs `estimated`, and the law that **no projection may read as an invoice** (id is `method-law`, NOT `method-tags` — that id is already the calculation/trust-rank entry and must stay unchanged) |
| `receipts` | the two strategies — in-tool shim (fux) vs external adapter (`cage graphify`) |
| `human-axis` | Tier-1 (agent vs human, whole task) vs Tier-2 (tool vs tool) |
| `determinism` | `$0`, no model / clock / RNG in derived views; same ledger + policy ⇒ same tables |
| `pii-safety` | counts not prompt bodies; point `CAGE_LEDGER` at a private store |
| `numbers-layers` | contract (`schema` enums) vs policy (`policy.toml`) vs constants (`constants.py`) — the §1 story |

**Anti-drift rule (this is what makes it more than relocated docs):** a `concept`
entry must (a) carry `code_refs` to the implementing files **and** a `plan_ref`,
and (b) interpolate any *structural* fact it states from the **live** source, not a
literal. Use the helpers that already exist:

- pipeline order → `policy.tool_order(pol)`
- ledger paths → `paths.Footprint(root)`
- meter surfaces → `agents.SURFACES`
- registered subcommands → the parser

So `cage query data-flow` prints the *actual* ledger filenames, and
`cage query attribution` prints the *actual* tool order — and both stay correct as
cage changes.

**Rendering:** `render` currently formats a calculation (formula/chain/method). Add
a concept branch (or a sibling `render_concept`) that prints `summary`, the
interpolated `body`, a `see also:` line of related ids, and `code:` + `plan:`
refs. `payload` (the `--json` path) gains `kind`, `body`, `plan_ref`.

**Listing + filtering:** `render_list` groups by `kind` (calculation block, then
concept block). Add `cage query --list --kind concept|calculation` and let a bare
`cage query <q>` match across both kinds. Matching, scoring, and `closest_ids`
stay as-is (they already work on `keywords` + id words).

## 2. CLI help grouping

The top-level `description` exists; the subcommands are still an ungrouped wall.
Group them in `cage --help` into: **ledger** (`report`/`budget`/`why`),
**attribution** (`attrib`/`matrix`/`roi`), **human axis** (`human`/`human-record`/
`trend`), **ops** (`regression`/`recommend`/`forecast`/`quality`/`outcome`),
**setup** (`init`/`adopt`/`doctor`/`setup`/`hooks`/`proxy`/`mcp`/`serve`), **meta**
(`query`/`demo`). Use a grouped `epilog` (with `RawDescriptionHelpFormatter`, already
set) or argument groups — whichever is cleaner. Add a one-line pointer:
*"ask how anything works: `cage query \"how does cage work\"`."* Document the global
`--json` once. Help text only — no behaviour change.

## Acceptance criteria

1. `cage query "how does cage work"` returns the `overview` concept entry; the 12
   existing calculation answers are unchanged.
2. A concept answer's structural facts are **live**: reordering `policy [tools].order`
   changes `cage query attribution`'s printed order; the ledger filenames in
   `cage query data-flow` come from `paths`. (Guard test.)
3. Every concept entry has non-empty `code_refs` and `plan_ref` (test asserts it for
   all `kind=="concept"` entries).
4. `cage query --list` groups by kind; `--list --kind concept` filters; an unmatched
   query still suggests closest ids.
5. `cage query` makes **no** network/LLM call (existing guard test still passes;
   extend it to a concept query).
6. `--json` for a concept topic carries `id`, `kind`, `summary`, `body`,
   `code_refs`, `plan_ref`.
7. `cage --help` shows grouped categories + the `cage query` pointer.
8. Doc-sync: `README.md` (note `cage query` now explains *how cage works*, not just
   values), `docs/cage-plan.md`, `CLAUDE.md`.
