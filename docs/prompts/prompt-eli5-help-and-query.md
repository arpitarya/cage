# Claude Code prompt: newcomer-friendly `cage --help` and `cage query`

You are making `cage --help` and `cage query` easy for a competent newcomer to start cold
— by fixing the front door and adding a few concrete worked examples — **without** lowering
cage's precision or adding a prose register to every registry entry. The full spec is in
`docs/handoff-eli5-help-and-query.md` — **read it first** and treat its Definition of Done,
Scope (especially the rejected "Out of scope" items), and Non-negotiables as binding.

> Note: an earlier "rewrite all 24 topics to a 5-year-old reading level + jargon-police
> test + live-interpolated examples" plan was **rejected**. Do not implement it. The
> handoff's §3 and §5.4 explain why. Build the narrowed version below.

## Context to load first
- Read: `CLAUDE.md` (the laws), then `cage/cli.py` (`_DESCRIPTION`, `_EPILOG`, the `query`
  parser, every `help=` string), `cage/explain.py` (`render`, `render_list`, `payload`,
  `_live`), `cage/explain_types.py`, `cage/explain_data.py` (note: `summary` is already the
  plain one-liner), `cage/clicmds.py` (`cmd_query`).
- Find the existing explain/query tests in `tests/` — they assert exact render output and
  will need updating.

## Task
1. **Front door (`cli.py`).** Rewrite `_DESCRIPTION` to lead with one plain sentence, then
   keep the precise "flux: deterministic attribution ledger" line (sequence, don't delete),
   and add a "New here? run `cage query "how does cage work"`" pointer. Rewrite `_EPILOG` so
   each category has a short plain gloss and a concrete example with **no `§`**. Translate
   the `(§4.x)`-tagged `help=` strings to one plain line each.
2. **One new field (`explain_types.py`).** Add `example: str = ""` — static, illustrative.
   Do **not** add a `plain` field.
3. **Fill examples (`explain_data.py`).** Add `example` to the money topics only — `cost`,
   `saved`, `human-cost`, `roi`, `matrix` — concrete, everyday words, labelled illustrative
   ("roughly"/"about"). Others optional. Tighten any `summary` that's genuinely unclear to a
   newcomer (light touch). Do **not** fill all 24, do **not** add a jargon/coverage test.
4. **Render (`explain.py`).** Add `plain: bool = False` to `render()`. Default: show
   `example` (when set) right after `summary`, then the existing formula/method/code (or
   body/code/plan for concepts) unchanged. `--plain`: show only id/summary/example. Add
   `example` to `payload()` as a raw string (additive — keep all existing keys). Give
   `render_list()`/no-match a one-line friendly header pointing at
   `cage query "how does cage work"`.
5. **CLI flag.** Add `--plain` to the `query` parser; thread `args.plain` through
   `cmd_query` in `clicmds.py`.

## Required workflow
1. **Explore** `cli.py`, `explain.py`/`explain_data.py`, and the existing tests. Confirm the
   render and `--json` shape — don't assume.
2. **Plan** — list the files you'll change and show me: the rewritten `_DESCRIPTION`, and
   the new render for `cost` (default and `--plain`). Pause for my confirmation before the
   rest.
3. **Implement incrementally** — field + engine first (keep build green), then the 5
   examples, then the `cli.py` text.
4. **Verify** — run `just test`; fix what you break. Then run and paste:
   `cage --help`, `cage query cost`, `cage query cost --plain`,
   `cage query "how does cage work"`, `cage query --list`.

## Constraints (hard)
- **Additive only.** Do NOT delete/rename existing render lines or `--json` keys; the only
  new key is `example`. Auditors keep formula/method/code.
- **`example` is static and illustrative — do NOT run it through `.format(**_live(pol))`.**
  Authoritative numbers stay in `formula` via `_live`. (See handoff §5.4.)
- **Do NOT** rewrite topics to a 5-year-old level, add a `plain` field, or add a
  jargon/coverage test. **Do NOT** change any formula, number, or attribution rule.
- **Do NOT** add/remove/rename/reorder registry entries — the set stays 24.
- **$0 / stdlib-only / deterministic** — no new deps, no clock/RNG/model; same ledger +
  policy ⇒ byte-identical output. Precision is sequenced behind the plain hook, never removed.
- Do not modify: the ledger, read views, MCP server, wiring, or the CLI surface (only
  `help=` *text* changes here).

## Acceptance criteria (self-check before finishing)
- [ ] `cage --help` opens plain, keeps the precise definition after it, points newcomers at
      `cage query "how does cage work"`, and has no `§` in user-facing examples; `help=`
      strings read plainly.
- [ ] `example` field exists; filled for the 5 money topics; rendered after `summary` in
      default mode; `--plain` shows only id/summary/example.
- [ ] `--json` has the new `example` key and every prior key.
- [ ] `just test` green; explain/help tests updated.

## Tests
- Update existing explain/query render + `--list` tests to the new format (keep exact-byte
  determinism assertions).
- Add: a render test (example line present in default; formula/method/code/plan absent under
  `--plain`); a `--json` additive-key test; a narrow assertion that the 5 money topics have
  a non-empty `example`. Do NOT add a broader coverage/jargon test.

## Guardrails
- Ask before: changing public API/contract, altering `--json` keys beyond the one addition,
  or anything irreversible.
- If a requirement is ambiguous or conflicts with the code, STOP and ask — especially the
  two OPEN QUESTIONS in the handoff (is the audience non-engineers? include the `help=`
  rewrite here?). Defaults per the handoff: audience is competent newcomers so `--plain` is
  opt-in and `example` stays light; yes, include the `help=` rewrite.
