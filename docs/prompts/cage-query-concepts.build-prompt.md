# Build prompt — `cage query` concept layer + CLI help grouping (hand to Claude Code)

> Run from the **cage** repo root. Full spec: `docs/cage-query-concepts.handoff.md`
> (source of truth; read it first). Builds on already-shipped work — `constants.py`
> and `cage query`'s calculation topics exist; **extend, don't rebuild.**

---

Extend `cage query` so it explains **how cage itself works**, not only how a value
is calculated, and group the CLI help. Implement `docs/cage-query-concepts.handoff.md`.
Stay inside cage law: **`$0`, stdlib-only, deterministic, no LLM/network on any
read path; `method` sacred; modules ≤100 lines; a code change ships its doc update.**

## Stage 0 — split data from engine (handoff §0)

- Move the `REGISTRY` tuple into a new `cage/explain_data.py` (pure data table);
  `explain.py` imports `REGISTRY` from it and keeps the `Explanation` dataclass +
  the engine. `explain.py` should land near the line budget; `explain_data.py` is
  an exempt data table. Behaviour unchanged — verify the suite is green before
  adding any concept entries.

## Stage 1 — concept topics in the registry

- In `cage/explain.py`, add `kind: str = "calculation"` (and `plan_ref: str = ""`)
  to the `Explanation` dataclass. The default keeps the 12 existing entries valid;
  tag them `kind="calculation"`.
- Append the **concept** entries (in `explain_data.py`) from handoff §1: `overview`,
  `data-flow`, `metering`, `attribution`, `matrix-concept`, **`method-law`**,
  `receipts`, `human-axis`, `determinism`, `pii-safety`, `numbers-layers`.
  ⚠️ The method-discipline concept entry's id is **`method-law`** — `method-tags`
  already exists as a calculation entry and must stay unchanged (unique-id / `_BY_ID`).
- **Anti-drift (the whole point):** every concept entry interpolates structural
  facts **live** — pipeline order from `policy.tool_order(pol)`, ledger paths from
  `paths.Footprint`, surfaces from `agents.SURFACES`, subcommands from the parser —
  never a literal. Every concept entry carries `code_refs` + `plan_ref`.
- Add a concept render branch (`summary`, interpolated `body`, `see also:` ids,
  `code:`/`plan:` refs); extend `payload` (`--json`) with `kind`/`body`/`plan_ref`.
- `render_list` groups by kind; add `cage query --list --kind concept|calculation`.
  Leave `match`/`closest_ids`/scoring as-is; a bare `cage query <q>` matches both
  kinds.

## Stage 2 — CLI help grouping

- Group subcommands in `cage --help` into the handoff §2 categories (ledger /
  attribution / human axis / ops / setup / meta) via a grouped `epilog`
  (`RawDescriptionHelpFormatter` is already set) or argument groups.
- Add the pointer line: *ask how anything works: `cage query "how does cage work"`*.
  Document the global `--json` once. Help text only — no behaviour change.

## Stage 3 — verify + doc-sync

- Full suite green; `cage demo` unchanged.
- New tests: `cage query "how does cage work"` → `overview`; reordering
  `policy [tools].order` changes `cage query attribution`'s printed order (live-fact
  proof); every `kind=="concept"` entry has `code_refs` + `plan_ref`; the no-LLM
  guard extended to a concept query; `--json` concept payload shape.
- Manually run `cage query "how does cage work"`, `cage query data-flow`,
  `cage query --list --kind concept`, and `cage --help`.
- Doc-sync: `README.md`, `docs/cage-plan.md`, `CLAUDE.md`.

## Working rules

- Plan before code: show me the concept entry ids + their `code_refs`/`plan_ref`
  and which live source feeds each one's structural facts, before writing bodies.
- Extend the existing registry/render/list — don't fork a parallel system.
- Concept prose must be anchored: if a fact isn't backed by a `code_ref` or derived
  live, cut it. No LLM, no network, no new dependency.

Acceptance = `cage query` answers "how does cage work" with live, code-anchored
concept entries; calculation topics unchanged; `cage --help` grouped; suite green;
no new dependency.
