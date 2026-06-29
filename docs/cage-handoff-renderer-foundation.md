# Handoff: cage skillgen renderer foundation

**One-liner:** Add a build-time, stdlib-only `tools/skillgen/` renderer to cage that emits the per-agent skill/prompt/steering artifacts for the flagship `cage` skill from one fragment set — eliminating drift across claude/codex/copilot/kiro — guarded by `--check` in CI, and prove breadth by adding a generic `agents` (AGENTS.md) target.
**Owner / executor:** Claude Code
**Status:** Ready to build
**Stress-tested:** Challenged as over-engineering for 2 skills. Survives because cage already maintains 4 *different* per-agent wrappers (claude skill / codex skill / copilot prompt / kiro steering) for the same content — that's exactly the drift the renderer kills, making cage the cleanest skillgen fit of either repo. Must include the `agents` target in slice 1 to prove breadth (pre-mortem: abandonment cause = "nobody added hosts"). `expected/` rot → manual-diff-before-first-bless + anchor test. Residual risk: cage's four wrappers differ structurally (skill vs prompt vs steering), so the per-host delta fragments carry more weight than in fux — accepted; that difference is precisely what gets single-sourced.

## 1. Context & background
cage ships the same flagship content four ways: `cage/data/skills/cage/SKILL.md` (claude), the codex skill, `cage/data/prompts/cage.prompt.md` (copilot), and `cage/data/steering/cage.md` (kiro). These are hand-authored and drift independently — change the `cage` pitch once and you must edit four files. graphify's build-time renderer (one `core.md` + per-host delta fragments → N drift-guarded artifacts) fixes this. This packet ports the renderer to cage, scoped to the **flagship `cage` skill only**. The `cage-doctor` skill, always-on CLAUDE.md/AGENTS.md blocks, the budget/regression hook nudges, `--json`, version stamping, and more hosts are **follow-on packets** riding this foundation.

## 2. Definition of done
- [ ] `tools/skillgen/{gen.py, platforms.toml}` + `fragments/` + `expected/` exist; `python -m tools.skillgen` renders, `--check` exits 0 clean / 1 on drift, `--bless` rewrites `expected/`.
- [ ] `gen.py` is **stdlib-only** (`tomllib`, `re`, `pathlib`, `argparse`); `dependencies = []` stays true; nothing under `tools/skillgen/` is imported by the `cage` package at runtime.
- [ ] The flagship `cage` content renders to all of: `claude` (skill), `codex` (skill), `copilot` (prompt), `kiro` (steering), **`agents`** (generic AGENTS.md skill). Each lands at its existing source path (`data/skills/cage/`, `data/prompts/cage.prompt.md`, `data/steering/cage.md`) so `cage setup` / `<agent>wire.py` keep working unchanged; `agents` is new (`data/skills/agents/cage/` mirroring the convention).
- [ ] Editing one shared line in `core.md` updates every host in one `--bless`.
- [ ] `python -m tools.skillgen --check` wired into pre-commit + CI (cage already has a CI gate — add it there).
- [ ] `tools/skillgen/` excluded from the wheel/sdist; a test asserts its absence.
- [ ] Anchor test: each rendered host body retains cage's non-negotiable lines (frontmatter `name`/`description` verbatim for skill hosts; the `cage report`/`cage attrib`/`cage budget` command references; the "counts never prompt text / PII-safe" claim).
- [ ] Determinism test (render twice = identical bytes); no-unfilled-slot test.
- [ ] Docs updated to match (see §9.5), including the CHANGELOG (cage's constitution requires a changelog entry per release).

## 3. Scope
**In scope:** renderer skeleton; `platforms.toml` for `claude/codex/copilot/kiro/agents`; `core.md` + per-host delta fragments for the **`cage` skill only** (the skill-vs-prompt-vs-steering wrapper is the per-host delta); `expected/`; `--check` in pre-commit + CI; wheel exclusion; anchor + determinism tests; `docs/skillgen.md` design-of-record + CHANGELOG entry.

**Out of scope (explicit) — do NOT build:**
- The `cage-doctor` skill — stays hand-authored until a follow-on packet.
- Always-on CLAUDE.md/AGENTS.md block generation/injection (spec §5) — follow-on.
- The budget-threshold + regression hook nudges, `hookio.emit`, `--json` parity, version stamping, `cage doctor` extensions (spec §12–§13) — follow-on.
- Any host beyond the five listed.
- Do **not** alter the metering/ledger/attribution engine, the `<agent>wire.py` hook wiring, `agents.py` `_WIRE`, or `cage setup`'s copy logic beyond confirming it reads the (unchanged-location) rendered assets.
- Do **not** add a "use cage before grep" nudge anywhere (deliberate divergence from graphify — cage is a passive ledger).

## 4. Current state
- Repo: `/Users/arpitarya/my_programs/cage`
- Read first: `cage/data/skills/cage/SKILL.md`, `cage/data/prompts/cage.prompt.md`, `cage/data/steering/cage.md`, `CLAUDE.md`, `docs/cage-plan.md`, `README.md`, `CHANGELOG.md`, `pyproject.toml`, `cage/setupcmd.py`, `cage/agents.py` (SURFACES + `_WIRE`).
- Reference (READ-ONLY, different repo): `/Users/arpitarya/my_programs/graphify/tools/skillgen/{gen.py,platforms.toml,fragments/}` — copy structure, strip migration validators, keep `load_platforms/Platform/_render_core/render/render_all/write_artifacts/check/bless/anchor-helper/main`.
- Architecture today: cage is `$0`, stdlib-only, deterministic; supports **four agents first-class always** (`agents.SURFACES = ("claude","codex","copilot","kiro")`); `cage setup` copies assets per agent (global + project scope); `<agent>wire.py` wires hooks + MCP. The four wrappers differ by host: claude/codex = SKILL.md, copilot = `.prompt.md`, kiro = steering `.md`.

## 5. Technical approach (decided)
- **cage gets its own copy of `gen.py`** — no shared module with fux/graphify (cage's `dependencies = []` independence is constitutional).
- **The per-host wrapper IS the delta.** `core.md` holds the shared `cage` content (the pitch, the command table, the PII-safety claim); per-host fragments supply: frontmatter vs prompt-header vs steering-header, the trigger idiom (`/cage` skill vs Copilot prompt invocation vs always-on steering), and any host-specific framing. The renderer fills `@@HEADER@@`/`@@FRONTMATTER@@`/`@@TRIGGER@@`/`@@HOST_NOTE@@` slots; raise on any unfilled slot.
- **Four-agents invariant preserved:** all of claude/codex/copilot/kiro must render; `agents` is additive. Never drop one — it's a cage product invariant.
- **`description` verbatim per `[platform]`** (firing trigger).
- **`expected/`** flat + fully tracked; `check()` byte-diffs render vs committed AND vs `expected/`.

## 6. Non-negotiables / constraints
- **Style/patterns:** cage house style — small single-purpose modules, the three-audit-layers discipline (don't mix contract/policy/constants), follow `CLAUDE.md`.
- **Use:** stdlib only. **Avoid:** any runtime dep (`dependencies = []` is sacred); any LLM/network on any path; any cross-repo import.
- **Determinism:** same fragments ⇒ byte-identical render (cage tests assert exact numbers/bytes elsewhere — match that bar). LF-normalize, sort references.
- **Four agents always:** the render must keep claude/codex/copilot/kiro first-class; do not silently break one.
- **Compliance/safety:** cage's ledger is counts-never-content/PII-safe — the rendered `cage` skill must keep that claim intact (anchor test guards it). No secrets in fragments.
- **Do not touch:** metering/ledger/attribution/provenance engine, `<agent>wire.py`, `agents.py`, the policy/constants/contract layers, or `cage setup` copy logic (beyond path confirmation). No "query before grep" nudge.

## 7. Dependencies & prerequisites
- Python ≥3.11 (`tomllib`). No env vars/services/secrets.
- Read access to the graphify repo (mounted).

## 8. Edge cases & risks
- **Unfilled slot** → raise with the leftover `@@SLOT@@` name.
- **Dropping a host** → the render MUST produce all five; a test asserts each of the four sacred agents is present.
- **CRLF** → `_normalise()` to LF before diff.
- **First bless blesses wrong output** → mandatory manual diff of each of the four current wrappers vs their render before the first `--bless`.
- **Wheel ships skillgen** → packaging exclude + wheel-content test in the same change.
- **`cage setup` reads a moved asset** → keep rendered outputs at existing paths; verify `setupcmd.py` still finds them.

## 9. Testing & validation
- **Must test:** byte-determinism (render twice); `--check` 0 clean / 1 on un-blessed edit; each of the five hosts renders and the four sacred agents are all present; anchor lines per host (frontmatter/header, command references, PII-safety claim); no surviving `@@`; wheel/sdist excludes `tools/skillgen/`.
- **Verify locally:** `just test` (currently 262 passing — update the count in README + CLAUDE.md `just test` comment if you add tests) · `python -m tools.skillgen --check` · `just demo` (sanity that engine untouched) · wheel build + contents inspection.
- **Manual check:** diff each rendered wrapper (claude skill / codex skill / copilot prompt / kiro steering) vs its current committed file; confirm equivalence before first bless.

## 9.5 Documentation impact
- [x] **CHANGELOG.md** — required (cage constitution: every change that touches shippable behavior/tooling gets an entry; newest first). Add the skillgen entry. Bump `__version__` only if you cut a release (coordinate — cage publishes only via GitHub release, never locally).
- [x] **README** — required: 1–2 line "What's new" pointer + a contributor note that skill assets are rendered (edit `fragments/`, `--bless`). Update the "N tests passing" count if tests were added.
- [x] **docs/cage-plan.md** — required: skillgen is a new build-time component; add a section. Add a new `docs/skillgen.md` design-of-record.
- [x] **AI agent files (CLAUDE.md)** — required, ⚠️ PROPOSE for review (do not auto-write): add a "skill/prompt/steering assets are rendered by `tools/skillgen`; never hand-edit `data/skills/cage/`, `data/prompts/cage.prompt.md`, `data/steering/cage.md`" rule. Surface the diff.
- [ ] **API / MCP contract** — N/A: no schema/contract change.
- [ ] **ADR** — optional: "per-repo gen.py copy, no shared module" one-paragraph note.

## 10. Open questions
- OPEN QUESTION: do codex/copilot/kiro hook events drop plain-stdout (needing the JSON envelope)? Drives the *follow-on* hook-nudge packet, not this one — verify before that packet.
- OPEN QUESTION: confirm the `agents` generic source path (`data/skills/agents/cage/`) and install targets (`~/.agents/skills/cage/`, `./.agents/skills/cage/`) match cage's existing `setupcmd.py` path conventions before wiring.
- OPEN QUESTION: should `cage setup` learn to install the `agents` host in this packet, or is rendering the artifact enough (wiring deferred)? Default: render now, wire `agents` into `cage setup`/`agents.py` in a follow-on (keeps this packet to rendering, not the four-agents invariant surface).
