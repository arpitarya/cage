# Handoff: make `cage --help` and `cage query` easy for a newcomer

**One-liner:** Fix the front door (`--help`) and add a handful of concrete worked examples
to `cage query`, so a competent newcomer can start cold — **without** lowering cage's
precision or taxing the registry's growth path.
**Owner / executor:** Claude Code
**Status:** Ready to build

> **This doc was pressure-tested and narrowed.** The original version ("rewrite all 24
> `query` topics to a 5-year-old reading level, mandatory `plain` field, jargon-police
> test, live-interpolated examples") was **rejected** — it taxes the core extensibility
> path, fights cage's precision positioning, and the "live-interpolated example" rule was
> internally contradictory (see §5.4 and §10). What survives is a smaller, sharper change.
> The goal is **understandable to a newcomer**, not baby-talk for everyone.

---

## 1. Context & background

`cage query` is cage's deterministic, $0 self-explainer: 24 `Explanation` entries
(12 `calculation`, 12 `concept`) whose numbers interpolate **live** from policy + constants
at render time (set `CAGE_HUMAN_RATE`, the printed rate changes — the self-verification
point). `cage --help` is the front door.

The real barrier for a newcomer isn't reading level — it's that both surfaces assume you
already hold cage's mental model, and the front door opens with undecoded jargon:
`_DESCRIPTION` literally starts *"Cage — a flux: a deterministic attribution ledger…"* and
epilog examples are tagged `§4.4`. The fix is a **plain hook + a start-here path + a few
real worked examples** — sequenced *in front of* the precise definitions, not replacing
them. The `summary` line each topic already has is the plain one-liner; we don't need a
second prose register on every entry.

This is a **text/UX change only**. It must not touch any number, formula, or the
live-interpolation mechanism. Determinism and $0 are unaffected and stay intact.

---

## 2. Definition of done

Build is done when ALL are true:

- [ ] `cage --help` opens with **one plain sentence**, *then* the precise "flux" definition
      (plain hook first, precision kept — not deleted), plus a "New here? run `cage query
      "how does cage work"`" pointer.
- [ ] `_EPILOG`: each command category has a short plain gloss and a concrete example;
      **no `§` references** in any user-facing example line.
- [ ] Per-subcommand `help=` strings drop the `(§4.x)` tags and read as one plain line each
      (e.g. `attrib` → "how much each tool saved you on a task").
- [ ] `Explanation` gains **one** optional field: `example: str = ""` (static, illustrative).
- [ ] `example` is filled for the money topics only — `cost`, `saved`, `human-cost`, `roi`,
      `matrix` — and may be added to others opportunistically. It is **not** mandatory on
      all 24, and there is **no** coverage/jargon test forcing it.
- [ ] `cage query <topic>` renders the `example` (when present) right after `summary`, then
      the existing `formula`/`method`/`code` unchanged.
- [ ] `cage query <topic> --plain` shows the gist only — id, summary, example — hiding
      formula/method/code/plan. (Opt-in; never the default.)
- [ ] `cage query --json` includes a new `example` key; every previously-present key
      remains (purely additive).
- [ ] Any `summary` that reads too terse/jargony for a newcomer is tightened in place
      (light touch — most already read plainly).
- [ ] `just test` green; explain/help tests updated for the new lines.

---

## 3. Scope

**In scope:**
- `cage/cli.py` — rewrite `_DESCRIPTION` (plain-hook-then-precise) + `_EPILOG`; translate
  the `(§4.x)` `help=` strings; add `--plain` to the `query` parser.
- `cage/explain_types.py` — add the single `example: str = ""` field.
- `cage/explain_data.py` — fill `example` for the 5 money topics (others optional); tighten
  any genuinely-unclear `summary` lines.
- `cage/explain.py` — render `example` after `summary`; `--plain` gist mode; friendly
  one-line header on `--list`/no-match.
- `cage/clicmds.py` — thread `--plain` through `cmd_query`.
- `tests/` — update for new render; light additions (see §9).

**Out of scope (do NOT do — these were considered and rejected):**
- A mandatory `plain` field on entries, or rewriting all 24 to a "5-year-old" reading
  level. The `summary` is the plain register; don't add a parallel one.
- A jargon-police / coverage test forcing baby-talk. Don't add it.
- **Live-interpolating the `example`** (running it through `.format(**_live(pol))`).
  Examples are static and illustrative — see §5.4 for why mixing live + static is unsafe.
- Any change to a formula, number, attribution rule, or live-interpolation of `formula`.
- Adding/removing/renaming/reordering registry entries — the set stays 24.
- Removing/shortening existing `formula`/`method`/`code` lines (auditors need them).
- The ledger, read views, MCP server, wiring, or the CLI surface (only `help=` *text*).

---

## 4. Current state

- Repo: this one (`cage`). Read `CLAUDE.md` first (the laws).
- Key files to read before writing:
  - `cage/cli.py` — `_DESCRIPTION`, `_EPILOG`, the `query` parser, every `help=` string.
  - `cage/explain.py` — `render()` (branches on `e.kind`), `render_list()`, `payload()`
    (the `--json` shape), `match()`/`closest_ids()`, `_live()`.
  - `cage/explain_types.py` — the `Explanation` dataclass.
  - `cage/explain_data.py` — the 24 entries; note `summary` is already a plain one-liner.
  - `cage/clicmds.py` — `cmd_query`.
  - `tests/` — existing explain/query tests assert exact render output; update them.
- Wiring today: `cmd_query` → `explain.match()` → `explain.render(e, pol)` (text) or
  `explain.payload(e, pol)` (`--json`). Formula placeholders fill from `_live(pol)`.

---

## 5. Technical approach (decided)

**5.1 New field (`explain_types.py`):**
```python
example: str = ""    # one concrete, static, illustrative line ("Say you… → about …")
```
One field, optional, defaulted — no parser churn, no second mental model.

**5.2 `--help` rewrite (`cli.py`):**
- `_DESCRIPTION`: lead with a plain sentence, then keep the precise line. e.g.
  > "Cage keeps a private tally of what your AI tools cost you and what they save you.
  > Under the hood it's a *flux*: a deterministic, $0 attribution ledger — every number is
  > derived from an append-only log, the same way every time.
  > New here? Run:  cage query \"how does cage work\""
  The precision stays; it's just no longer the *first* thing a newcomer hits.
- `_EPILOG`: keep the category grouping; add a one-line plain gloss + a real example per
  category; strip `§` from the examples.
- `help=` strings: translate the `(§4.x)`-tagged ones to one plain line each. Keep short.

**5.3 `example` content rules (`explain_data.py`):**
- Concrete and small; everyday words. Label it as illustrative ("roughly", "about").
- Fill for `cost`, `saved`, `human-cost`, `roi`, `matrix` first. Others optional.
- Illustrative `cost` target:
  `"Say a message reads ~1,000 words and writes ~200 back — that's roughly a few cents."`

**5.4 Why `example` is static, not live-interpolated (the rejected trap):**
A worked example needs a *self-consistent* scenario (inputs **and** result agree). If we
interpolate only the live rate but hard-code "1,000 words" and "a few cents," the sentence
silently goes arithmetically wrong when the rate moves. The only consistent options are
(a) fully compute the example through `prices.call_usd` — real engine + test surface for a
cosmetic line — or (b) keep it static and illustrative. We choose (b): the **`formula` +
`_live` values remain the authoritative, drift-proof numbers**; `example` is explicitly a
rough picture, never an authority. Do not run `example` through `.format(**_live(pol))`.

**5.5 Render (`explain.py`):**
- Add `plain: bool = False` to `render()`.
  - Default (calculation): `id · summary` → `for example:` (if set) → `formula:` →
    `method:` → `code:` (existing lines unchanged).
  - Default (concept): `id · summary` → `for example:` (if set) → body → `code:` → `plan:`.
  - `--plain`: `id · summary` → `for example:` (if set). Nothing else.
- `payload()` adds `example` (raw string, no interpolation) — additive only.
- `render_list()`/`closest_ids` suggestions: prepend one friendly line, e.g.
  `Not sure what to ask? Try:  cage query "how does cage work"`.

**5.6 `clicmds.cmd_query`:** thread `args.plain` → `explain.render(..., plain=args.plain)`.

---

## 6. Non-negotiables / constraints

- **Additive only.** Don't delete/rename existing render lines or `--json` keys. Auditors
  keep `formula`/`method`/`code`. The only new key is `example`.
- **Precision is sequenced, not removed.** The plain hook goes *in front of* the exact
  definition; the `§`/formula detail still exists for those who want it.
- **$0 / stdlib-only / deterministic.** No new deps, no clock/RNG/model. Same ledger +
  policy ⇒ byte-identical output (now with the static `example` lines).
- **`example` is illustrative, never authoritative or live.** Authoritative numbers stay
  in `formula` via `_live`. No interpolation of `example`.
- **24 entries, unchanged set.** Enrich only.
- **Method stays sacred.** No example may imply a modeled/estimated figure is measured.
- **No mandatory plain register, no jargon linter.** Don't reintroduce the rejected plan.

---

## 7. Dependencies & prerequisites

None. Stdlib + existing modules. No env vars, no services.

---

## 8. Edge cases & risks

- **Entry with empty `example`** → render skips the `for example:` line cleanly (no blank
  label). `--plain` on such an entry shows just `id · summary`.
- **`--plain` on a concept entry** → id/summary/example only; skip body/code/plan.
- **Long `example`/`summary`** → wrap, continuation indented under the value column.
- **Existing snapshot tests** fail on the new line — update to the new expected bytes; keep
  exact-byte determinism assertions (don't weaken them).
- **Risk — scope creep back to ELI5-everything.** If you find yourself filling `example`
  on all 24 or softening every `summary`, stop: the spec says money topics + a light touch.
- **Risk — someone "helpfully" interpolates `example`.** Explicitly forbidden (§5.4).

---

## 9. Testing & validation

- **Update** existing explain/query render + `--list` tests to the new format.
- **Add** a small render test: an entry with an `example` shows the `for example:` line in
  default mode; `--plain` shows id/summary/example and **omits** formula/method/code/plan.
- **Add** a `--json` test: `example` key present; all prior keys still present.
- **Do NOT** add a coverage/jargon test (rejected). A test may assert the 5 money topics
  have a non-empty `example` (narrow, intentional) — nothing broader.
- **Verify locally:**
  ```
  just test
  cage --help
  cage query cost
  cage query cost --plain
  cage query "how does cage work"
  cage query --list
  ```
  Eyeball: a newcomer can start from `--help` and understand `cost` without a glossary —
  while the formula/method/code are still right there for an expert.

---

## 10. Open questions

- OPEN QUESTION (the real fork): if you genuinely intend to put cage in front of
  **non-engineers** (not just smooth the newcomer path), say so — that would justify
  making `--plain` more prominent and filling `example` more widely. Default assumption:
  the audience is competent newcomers + auditors + agents, so `--plain` stays opt-in and
  `example` stays light. **Confirm or override.**
- OPEN QUESTION: include the per-subcommand `help=` rewrite in this PR, or split it?
  Recommendation: include — same "plain front door" job, small.
