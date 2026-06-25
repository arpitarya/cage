# Build prompt — constants file + `cage query` + CLI help (hand to Claude Code)

> Run from the **cage** repo root. Full spec:
> `cage/docs/dx-constants-query-help.handoff.md` (source of truth; §-refs point
> into it). Three changes, all to make cage's math reviewable and traceable.

---

Implement three DX/auditability upgrades for cage per
`docs/dx-constants-query-help.handoff.md` — read it first. Stay inside cage law:
**`$0`, stdlib-only, deterministic, no LLM or network on any read/maintenance
path; `method` stays sacred; modules ≤100 lines (≤50 for utils); a code change
ships its doc update.**

## Stage 1 — `cage/constants.py` (pure move, byte-identical behaviour)

- Create `constants.py` holding the code heuristics named in handoff §1
  (`CHARS_PER_TOKEN`, `TOKENS_PER_MILLION`, `MAX_MATRIX_TOOLS`, `METHOD_TRUST`,
  `DEFAULT_CONFIDENCE`, `GRAPHIFY_RECEIPT_CONFIDENCE`, `SINCE_WINDOW_DAYS`), each
  with a one-line rationale, and a docstring stating the **three-layer split**
  (contract = `schema.py` enums · policy = `policy.toml` economics · constants =
  these heuristics). Do NOT move the `UNITS`/`METHODS` enums (contract) or any
  economic number (policy).
- Repoint `compress.py`, `prices.py`, `matrix.py`, `attribution.py`, `human.py`,
  `ledger.py`, `graphifymeter.py` to import from `constants.py`.
- `DEFAULT_CONFIDENCE` stays a **fallback** — `human.py` still prefers
  `policy [human.confidence]`. Don't break the override.
- Leave the third-party shims (`fux/cage_receipt.py`, graphify shim) alone; add a
  comment in cage's docstring that their `len/4` is an intentional zero-dep copy of
  `CHARS_PER_TOKEN`.
- Verify: `cage demo` output and the full suite are **unchanged** (snapshot). This
  stage must be a no-op on behaviour — if a number changes, you retuned by mistake.

## Stage 2 — `cage query` (deterministic explainer, no LLM)

- Add `cage/explain.py`: a registry of frozen `Explanation` entries (handoff §2
  shape) for the seeded topics. Each `formula`/fields interpolate **live** values
  from `policy` + `constants` at render time — never hard-code the rate, divisor,
  or ladder.
- Matching is stdlib + deterministic: normalize the query, score entries by
  keyword/term overlap, return the top match (`--all` for top-N). No match ⇒
  print closest topic ids; never fabricate an answer.
- Wire `cage query`:
  `cage query "<question>"` · `cage query <id>` · `cage query --list` ·
  `--json` · `--all`.
- **Guard test (mirror fux):** assert `cage query` makes no network/LLM call; assert
  the printed rate tracks `CAGE_HUMAN_RATE` (proves live interpolation, not a
  literal). `--json` carries the same fields as the text render.
- Seed a `cost` entry that explains the **recompute-with-est_cost-fallback** rule
  (the cost bug from `fix-cost-rendering`), so that behaviour is self-documenting.

## Stage 3 — CLI help (grouped, exampled)

- Top-level `description` + `epilog` with 4–5 copy-paste examples and a pointer to
  `cage query` for "how is X computed?".
- Group subcommands into the handoff §3 categories (argument groups or a grouped
  epilog), give each a clean one-line help + an example for the non-obvious ones
  (`matrix --human`, `graphify`, `human-record`, `query`), and document the global
  `--json` once, prominently.
- No behaviour change — help text only.

## Stage 4 — verify + doc-sync

- Full suite green; `cage demo` unchanged; the new tests (Stage 1 snapshot,
  Stage 2 guard + live-rate + json) pass.
- Manually run `cage query "how is the value getting calculated"`,
  `cage query "how do you cost a human"`, `cage query --list`, and `cage --help`;
  confirm they read well and the numbers are live.
- Doc-sync: `README.md` (add `cage query` + the three-layer numbers story),
  `docs/cage-plan.md`, `CLAUDE.md` (architecture map: `constants.py`, `explain.py`).

## Working rules

- Plan before code: show me the `constants.py` contents + the list of import sites,
  and the `Explanation` registry topics with their keywords, before wiring.
- Stage 1 is a **pure refactor** — prove behaviour is identical before moving on.
- Touch only what's named. No retuning constants, no LLM anywhere, no new dependency.
- If a value you're centralizing is actually user-economic (belongs in policy) or
  contract (an enum), stop and ask rather than putting it in `constants.py`.

Acceptance = all 6 handoff criteria green; `cage query` answers "how is X
calculated" deterministically with live numbers; `cage --help` is grouped and
exampled; behaviour and `cage demo` unchanged; no new dependency.
