# Claude Code prompt: cage skillgen renderer foundation

You are adding a build-time, stdlib-only skill renderer to the **cage** repo. The full spec is in the handoff doc `cage-handoff-renderer-foundation.md` — read it first and treat its Definition of Done, Scope, and Non-negotiables as binding.

## Context to load first
- Read: `cage/data/skills/cage/SKILL.md`, `cage/data/prompts/cage.prompt.md`, `cage/data/steering/cage.md` (the four flagship wrappers you'll unify), `CLAUDE.md`, `docs/cage-plan.md`, `README.md`, `CHANGELOG.md`, `pyproject.toml`, `cage/setupcmd.py`, `cage/agents.py`.
- Reference implementation to copy structure from (READ-ONLY, different repo, do not modify): `/Users/arpitarya/my_programs/graphify/tools/skillgen/gen.py`, `.../platforms.toml`, `.../fragments/`.
- Respect `CLAUDE.md`, the `$0`/stdlib-only/`dependencies = []`/deterministic laws, and the "four agents always" product invariant.

## Task
Create `tools/skillgen/` in cage: `gen.py` (a stripped ~250-line port of graphify's renderer — keep `load_platforms`, `Platform`, `_render_core`, `render`, `render_all`, `write_artifacts`, `check`, `bless`, an anchor/`headings` helper, and `main` with `--check`/`--bless`/`--platform`; drop all graphify-migration validators), `platforms.toml`, `fragments/`, and `expected/`. Templatize the **flagship `cage` content only** into `fragments/core/core.md` with `@@SLOT@@`s where the per-host wrapper differs (claude skill / codex skill / copilot prompt / kiro steering / new generic `agents` skill). Render all five to their existing source paths (`data/skills/cage/`, `data/prompts/cage.prompt.md`, `data/steering/cage.md`; `data/skills/agents/cage/` is new). Wire `python -m tools.skillgen --check` into pre-commit + CI. Exclude `tools/skillgen/` from the wheel.

## Required workflow
1. **Explore** graphify's `tools/skillgen/` and cage's four flagship wrappers; identify exactly what differs per host (header/frontmatter, trigger idiom, framing) vs the shared body. That difference becomes the slots + per-host fragments.
2. **Plan** — list files to create, the `platforms.toml` table per host, the slot set, the rendered output paths (keep existing paths so `cage setup`/`<agent>wire.py` keep working), and the test list. **Pause for my confirmation before implementing.**
3. **Implement incrementally** — renderer skeleton (prove stdlib-only render), then `core.md` + per-host fragments, then all five hosts, then `--bless`, then CI wiring, then wheel exclusion, then tests. Keep the build green.
4. **Manual bless gate** — before the FIRST `--bless`, print the diff of each rendered wrapper (claude skill, codex skill, copilot prompt, kiro steering) vs its current committed file and STOP for my confirmation. Do not bless an unreviewed render.
5. **Update docs to match** — CHANGELOG (required; newest first), README ("What's new" line + contributor note + test-count if changed), `docs/cage-plan.md` + new `docs/skillgen.md`. For `CLAUDE.md`: PROPOSE the "never hand-edit rendered cage assets; edit fragments + `--bless`" rule as a diff for my review — do NOT auto-write it. MCP/contract = N/A; say so.
6. **Verify** after changes: `just test` (update the "N passing" count in README + the CLAUDE.md `just test` comment if you added tests), `python -m tools.skillgen --check`, `just demo` (engine untouched), and a wheel build + contents inspection. Fix what you break. Don't report done until these pass.

## Constraints (hard)
- Use: stdlib only (`tomllib`, `re`, `pathlib`, `argparse`). Do NOT use: any runtime dependency (`dependencies = []` is sacred); any LLM/network on any path; any cross-repo import (cage's `gen.py` is its own copy).
- The render MUST keep claude/codex/copilot/kiro first-class (four-agents invariant) plus add `agents`. Never drop one.
- Preserve each host's `description` (firing trigger) VERBATIM from `platforms.toml`.
- Determinism: same fragments ⇒ byte-identical render; LF-normalize; sort references; no clocks/random.
- Do not modify: the metering/ledger/attribution/provenance engine, `<agent>wire.py`, `agents.py`, the policy/constants/contract layers, or `cage setup` copy logic. Do NOT add any "use cage before grep" nudge.
- `tools/skillgen/` must never be imported at runtime and must not ship in the wheel.
- Do NOT publish or bump a release. If `__version__` needs bumping, ask — cage publishes only via GitHub release, never locally.

## Acceptance criteria (self-check before finishing)
- [ ] `--check` exits 0 clean / 1 on un-blessed edit; `--bless` rewrites `expected/`.
- [ ] All five hosts render; the four sacred agents are all present (test-asserted); editing one `core.md` line updates all in one `--bless`.
- [ ] `gen.py` stdlib-only; `dependencies = []` unchanged; nothing under `tools/skillgen/` imported at runtime.
- [ ] Anchor test (frontmatter/header + `cage report`/`attrib`/`budget` references + PII-safety claim per host), determinism test, no-unfilled-slot test, wheel-excludes-skillgen test — passing.
- [ ] `--check` in pre-commit + CI.
- [ ] CHANGELOG + README + docs/cage-plan.md + docs/skillgen.md updated; CLAUDE.md rule proposed for review.

## Tests
Add tests covering: byte-determinism; `--check` pass/fail; all five hosts render + four sacred agents present; per-host anchor lines; no surviving `@@`; wheel excludes `tools/skillgen/`. Run via `just test`.

## Guardrails
- Ask before: deleting/moving any existing skill/prompt/steering asset, changing `pyproject.toml` beyond the skillgen exclude, bumping `__version__`, or touching the four-agents wiring.
- Do not auto-edit `CLAUDE.md` — propose the diff.
- If a requirement is ambiguous or conflicts with the code (the `agents` path convention, whether to wire `agents` into `cage setup` now), STOP and ask.
- This packet is the renderer foundation ONLY. Do not build the budget/regression nudges, `hookio`, `--json`, version stamping, `cage-doctor` rendering, always-on blocks, or more hosts — those are explicit follow-on packets.
