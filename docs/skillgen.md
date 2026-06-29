# skillgen — the build-time renderer for cage's skill assets

**Design of record.** `tools/skillgen/` renders the flagship `cage` skill's
per-host assets from one fragment set, so the same pitch can ship to four agents
(plus a generic target) without drifting across hand-authored copies. It is
build-time only, `$0`, stdlib-only, deterministic — the same constitution as the
metering/attribution engine (see [cage-plan.md](cage-plan.md) §5.1).

## Why it exists

cage ships the `cage` skill four ways, one per first-class agent:

| Host    | Kind     | Committed path                          |
| ------- | -------- | --------------------------------------- |
| claude  | skill    | `cage/data/skills/cage/SKILL.md`        |
| codex   | skill    | `cage/data/skills/cage/SKILL.md` *(shared with claude)* |
| copilot | prompt   | `cage/data/prompts/cage.prompt.md`      |
| kiro    | steering | `cage/data/steering/cage.md`            |
| agents  | skill    | `cage/data/skills/agents/cage/SKILL.md` *(new, generic Agent Skills)* |

The *content* — the cage pitch, the command set (`report`/`attrib`/`roi`/`matrix`/
`budget`/`why`), the counts-never-content / PII-safe claim — is identical. Only the
**host wrapper** differs: the frontmatter shape (skill = `name`+`description`,
prompt = `description` only, steering = `inclusion: always`), the H1 header, the
intro framing, and the metering note. Maintaining four files by hand let those
diverge. skillgen makes the shared body the single source of truth and treats the
per-host wrapper as a small set of slots.

> **claude and codex share one physical file.** `cage setup` copies
> `data/skills/cage/` to both `~/.claude/skills/cage/` and `~/.codex/skills/cage/`,
> so both hosts render to the same path and **must** be byte-identical. The
> renderer asserts this (`render_all` raises if two hosts target one path with
> different content) — the collision is the guard, not a bug.

## How it works

```
platforms.toml ──┐
                 ├─► load_platforms() ─► Platform(key, kind, skill_dst, header,
fragments/core/  │                                  intro, meter, name, description)
  core.md        │
fragments/intro/ ├─► _render_core(p): fill @@FRONTMATTER@@ @@HEADER@@ @@INTRO@@
fragments/meter/ │                    @@METER@@  (raise on any leftover @@SLOT@@)
                 │
                 └─► render_all(platforms) ─► dedupe by output path (assert
                       byte-identity on collision) ─► [RenderedArtifact]
```

- **`platforms.toml`** — one `[platform.<key>]` table per host. Declares `kind`
  (`skill`/`prompt`/`steering`), `skill_dst`, the `header` line, the `intro`/`meter`
  fragment basenames, and the `name`/`description`. **`description` is preserved
  verbatim** — it is the host's firing trigger and is never invented.
- **`fragments/core/core.md`** — the shared body with four slots:
  `@@FRONTMATTER@@`, `@@HEADER@@`, `@@INTRO@@`, `@@METER@@`. Everything else
  (command block, PII clause) is literal and therefore single-sourced.
- **`fragments/intro/<variant>.md`, `fragments/meter/<variant>.md`** — the per-host
  framing and metering note. claude/codex use the `skill` variants; copilot, kiro,
  and agents use their own.
- **`expected/`** — a flat, fully tracked snapshot of every rendered artifact (path
  flattened `/`→`__`). `check()` byte-diffs the render against *both* the committed
  file and this snapshot, so a hand-edit of a generated file **or** a stale snapshot
  is caught.

## CLI

Run from the repo root:

```bash
python -m tools.skillgen                 # render every host's asset to its path
python -m tools.skillgen --platform kiro # render/check just one host
python -m tools.skillgen --check         # byte-diff vs committed + expected/, exit 1 on drift
python -m tools.skillgen --bless         # rewrite expected/ from the current render
```

`--check` is wired into the `Python package` CI job and a local `pre-commit` hook
(`.pre-commit-config.yaml`). It is the anti-drift gate: CI fails if the committed
assets don't match the fragments.

## The workflow (for contributors)

**Never hand-edit the rendered files** (`cage/data/skills/cage/`,
`cage/data/prompts/cage.prompt.md`, `cage/data/steering/cage.md`,
`cage/data/skills/agents/cage/`). To change the skill:

1. Edit the fragment(s) under `tools/skillgen/fragments/` (shared body → `core.md`;
   a host's wrapper → its `intro/`/`meter/` fragment or its `platforms.toml` fields).
2. `python -m tools.skillgen` — re-render the committed files.
3. Review the diff (`git diff cage/data/`). For a first-time or large change, this
   is the **bless gate**: confirm the render is what you intend before snapshotting.
4. `python -m tools.skillgen --bless` — refresh `expected/`.
5. Commit the fragments, the rendered files, and `expected/` together.

A single edit to `core.md` updates every host in one `--bless` — that is the whole
point.

## Invariants (guarded by `tests/test_skillgen.py`)

- **Four agents always.** claude/codex/copilot/kiro all render; none is dropped.
  `agents` is additive. Test-asserted.
- **Determinism.** Same fragments ⇒ byte-identical render. LF newlines, one
  trailing newline, fixed slot order, no clock/version/random in any output.
- **No unfilled slot.** A leftover `@@SLOT@@` raises with the slot name.
- **Anchors per host.** Every render retains the command references and the
  counts-never-content / PII-safe claim; skill/prompt hosts keep their
  `description` verbatim.
- **Shared-path byte-identity.** claude and codex render identical bytes to the
  shared `SKILL.md`, or `render_all` raises.
- **Never shipped, never imported.** Nothing under `tools/skillgen/` is imported by
  the `cage` package at runtime; the wheel's `include=["cage*"]` filter excludes it.

## Scope (this foundation) and what's deferred

**In:** the renderer, the five hosts for the **`cage` skill only**, `--check` in
CI + pre-commit, the `expected/` guard, the tests, this doc.

**Deferred to follow-on packets:** rendering the `cage-doctor` skill; always-on
`CLAUDE.md`/`AGENTS.md` block generation; budget/regression hook nudges, `--json`
parity, version stamping; wiring the `agents` host into `cage setup` / `agents.py`
(this packet renders the asset only); any host beyond the five. skillgen also
deliberately adds **no** "use cage before grep" nudge — cage is a passive ledger.
