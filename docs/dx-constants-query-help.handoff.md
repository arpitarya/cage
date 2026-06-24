# Handoff — three DX/auditability upgrades for cage

**Status:** spec-first. One build prompt in the sibling
`dx-constants-query-help.build-prompt.md`. Three changes, all in service of cage's
core promise — *every number is reviewable and traceable*:

1. a **central constants file** so code heuristics live in one auditable place;
2. **`cage query "how is X calculated"`** — a deterministic explainer that prints
   the real formula with *live* values and code refs;
3. **better CLI help** — grouped, exampled, discoverable.

---

## 1. `cage/constants.py` — one reviewable home for code heuristics

Today the magic numbers are scattered: `len/4` (token heuristic) in `compress.py`
**and** `graphifymeter.py`; `_MAX_TOOLS = 12` in `matrix.py`; `_TRUST` ranks in
`attribution.py`; `_DEFAULT_CONF` ladder in `human.py`; `1_000_000` in `prices.py`
and `matrix.py`; the `{h,d,w}` since-window in `ledger.py`; graphify receipt
`confidence=0.6` in `graphifymeter.py`. None are reviewable together.

**Three layers, kept distinct (this is the audit story — state it in the file's
docstring):**

| Layer | Holds | Lives in |
|-------|-------|----------|
| **Contract** | closed enums `UNITS`, `METHODS` | `schema.py` (unchanged — it's the substrate contract) |
| **Policy** | user-tunable economics: prices, human rate, default minutes, budgets, tool order, confidence overrides | `policy.toml` (unchanged — "the only place economic numbers live") |
| **Constants** | code heuristics & invariants not meant as user config but that must be reviewable | **`constants.py` (new)** |

`constants.py` centralizes (named, with a one-line rationale each):

```python
CHARS_PER_TOKEN = 4              # deterministic token heuristic (≈ OpenAI/Anthropic avg)
TOKENS_PER_MILLION = 1_000_000   # price tables are per-million
MAX_MATRIX_TOOLS = 12            # 2^12 = 4096-row ceiling on one task's permutations
METHOD_TRUST = {"measured": 2, "modeled": 1, "estimated": 0}   # provenance ranking
DEFAULT_CONFIDENCE = {"measured": 0.9, "estimated": 0.7, "type_table": 0.5, "default": 0.3}
GRAPHIFY_RECEIPT_CONFIDENCE = 0.6
SINCE_WINDOW_DAYS = {"h": 1/24, "d": 1, "w": 7}
```

- `compress.py`, `prices.py`, `matrix.py`, `attribution.py`, `human.py`,
  `ledger.py`, `graphifymeter.py` import from `constants.py` instead of inlining.
  Behaviour is byte-identical (snapshot/`cage demo` unchanged) — it's a move, not a
  retune.
- **`DEFAULT_CONFIDENCE` stays a *fallback*** — `human.py` still prefers
  `policy [human.confidence]` and falls back to the constant (don't break the
  policy override).
- **The third-party shims keep their own copy.** `fux/cage_receipt.py` and the
  graphify shim are zero-dep and can't import cage; their `len/4` stays local, with
  a comment: *"must match cage.constants.CHARS_PER_TOKEN."* Note this divergence in
  the docstring so a reviewer knows the two are intentionally duplicated.

## 2. `cage query` — deterministic, self-verifying explanations of the math

Goal: a CLI that answers *"how is this value calculated?"* — but **deterministic,
`$0`, no LLM** (cage law). Not a model Q&A; a curated explainer registry whose
numbers are read **live** from `policy` + `constants`, so an explanation can never
drift from the code. Mirrors `fux explain` / `graphify query` for family UX.

**`cage/explain.py`** — a registry of `Explanation` entries:

```python
@dataclass(frozen=True)
class Explanation:
    id: str                 # "human-cost", "marginal-attribution", "matrix", …
    keywords: tuple[str,...]# match terms: ("human","person","salary","time saved"…)
    summary: str            # one line
    formula: str            # template with {placeholders} filled from live values
    code_refs: tuple[str,...]
    method_note: str        # which method tag this produces & why
```

Seed topics (each pulls live values so the printed numbers are *current*):
`cost` (input/cache/output, the cache discount), `saved` + `marginal-attribution`
(sum of marginals = total, fixed order), `matrix` (2ⁿ counterfactual, measured vs
modeled), `human-cost` (minutes→usd precedence chain + the live rate + confidence
ladder), `time-saved` (`human_minutes − agent_active_minutes`, can go negative),
`roi`, `token-heuristic` (`CHARS_PER_TOKEN`), `confidence`, `method-tags`,
`trend`, `budget`.

**Command surface:**

```
cage query "how is the value getting calculated"   # best-match explainer
cage query "how do you cost a human"               # natural-language → human-cost
cage query human-cost                              # exact id
cage query --list                                  # all topics (one line each)
cage query <q> --json                              # structured, for the agent-as-user
```

**Matching (stdlib, deterministic):** normalize the query (lowercase, split), score
each entry by keyword/term overlap (a tiny token-overlap or substring score — no
embeddings, no network), return the top entry (or top-N with `--all`). Ties broken
by a fixed registry order. No match → list the closest topic ids, never guess.

**Example output (numbers are live, not hard-coded):**

```
$ cage query "how is human cost calculated"

human-cost · how a human alternative is priced
  formula:  usd = minutes / 60 × rate     (rate = $80/hr, source: policy)
  chain:    explicit usd  >  per-receipt minutes  >  task-type table  >  global default
  confidence: measured 0.9 · estimated 0.7 · type-table 0.5 · default 0.3
  method:   estimated  (a labor guess — never 'measured' unless a real timesheet)
  code:     cage/human.py · cage/convert.py · policy.toml [human]
```

This is the Fux "capture intent + verify" principle turned on cage's own math: the
explanation lives next to the code, and its numbers are the code's actual numbers.

## 3. CLI help — grouped, exampled, discoverable

- **Top-level**: a real `description` (what cage is) + an `epilog` with 4–5 copy-
  paste examples and a one-line pointer to `cage query` for "how is X computed?".
- **Categories**: group subcommands in help output — *ledger* (`report`/`budget`/
  `why`), *attribution* (`attrib`/`matrix`/`roi`), *human axis* (`human`/
  `human-record`/`trend`), *ops* (`regression`/`recommend`/`forecast`/`quality`/
  `outcome`), *setup* (`init`/`adopt`/`doctor`/`setup`/`hooks`/`proxy`/`mcp`/
  `serve`), *meta* (`query`/`demo`). Use argparse argument groups or a grouped
  epilog.
- **Per-command**: each `help=`/`description=` gets a one-line "what + when," and a
  short `epilog` example for the non-obvious ones (`matrix --human`, `graphify`,
  `human-record`, `query`). Document the global `--json` once, prominently.

## Acceptance criteria

1. `constants.py` exists; the seven modules import from it; `cage demo` output and
   the full test suite are **unchanged** (pure move — snapshot test).
2. `DEFAULT_CONFIDENCE` still loses to `policy [human.confidence]` when set (test).
3. `cage query "how is human cost calculated"` prints the formula with the **live**
   policy rate (set `CAGE_HUMAN_RATE` → the printed rate changes, proving it's not
   hard-coded). `--json` emits the same content structured. No LLM/network call on
   the path (assert, mirroring fux's no-LLM guard test).
4. `cage query --list` lists every seeded topic; an unmatched query suggests
   closest ids rather than guessing.
5. `cage --help` shows grouped categories + examples; every subcommand's help reads
   cleanly; `--json` is documented.
6. Doc-sync: `README.md` (add `cage query` + the three-layer numbers story),
   `docs/cage-plan.md`, `CLAUDE.md` (architecture map: `constants.py`, `explain.py`).

## Note — fold the cost-fix helper in here

The `call_usd` helper from `fix-cost-rendering.build-prompt.md` should live beside
or use `constants.py` (it leans on `TOKENS_PER_MILLION` via `prices`), and a
`cage query cost` entry should explain the recompute-with-est_cost-fallback rule so
the very behaviour that was silently wrong becomes self-documenting.
