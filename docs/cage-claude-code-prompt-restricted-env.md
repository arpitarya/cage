# Claude Code prompt: restricted environments — python-launcher mode + cage.pyz

You are implementing the restricted-environments work. The full spec is
**`docs/cage-handoff-restricted-env.md`** — read it first; its Definition of
Done and Non-negotiables are binding. Run AFTER the current tree is
reviewed/committed (ask if dirty). **No commits, tags, pushes, publishes.**

## Context to load first

- The handoff, then: `cage/runshim.py`, `cage/paths.py`
  (`bundled_data_dir` + grep every consumer), `cage/setupcmd.py`,
  `cage/agents.py`, `cage/doctorcmd.py`, `docs/portable-wiring.md`,
  `.github/workflows/publish.yml` (reference only — its publish job is
  off-limits), `tools/dummyrepo/run.py`, `CLAUDE.md`.

## Task, in order

1. **importlib.resources migration (pyz prerequisite):** one stdlib helper
   replaces the `Path(__file__).parent / "data"` pattern everywhere bundled
   data is read; `as_file` where a real path is unavoidable (copying skill
   assets, graphify shim source). Wheel-installed behavior stays
   byte-identical (tested).
2. **Python-launcher mode:** `cage setup --python-launcher` persists
   `[wiring] python_launcher = true` (project policy) and writes shim +
   user-level wiring that go straight to `py -m cage` / `python3 -m cage` —
   never probing or executing `cage`/`cage.exe`. Runtime override
   `CAGE_RUN_PYTHON=1` in the standard shim skips exe probing without
   rewiring. Same fail-open exit-0 contract, all four agents, idempotent,
   re-runs preserve the mode; `cage doctor` names the active mode.
3. **`cage.pyz` CI job:** new job in the release workflow (same
   `release: published` trigger, independent of — and never modifying — the
   PyPI publish job): stage package → stdlib `python -m zipapp`
   (`main="cage.cli:main"`) → smoke on the 3-OS matrix (`--version`, `demo`,
   `import` over a fixture, `report`) → attach `cage.pyz` + `SHA256SUMS` to
   the release. Asset-job failure must not fail the publish job.
4. **Distribution awareness:** `cage --version` / `doctor` label a zipapp run
   (`cage X.Y.Z (zipapp)`); anything provably non-functional from a zip is
   doctor-reported and documented, never silent. Decided in the handoff:
   shims never embed a pyz path — the pyz story is pull-based
   (`py cage.pyz import/export/report`), hooks require an importable install.
5. **Docs + query:** `docs/restricted-environments.md` (three tiers:
   launcher mode · pyz · internal mirror; WDAC script-host caveat stated
   honestly; a short checklist for the first locked-down-endpoint
   validation), README install/platform links, `docs/portable-wiring.md`
   extended with the mode, `cage query restricted-env` entry, CHANGELOG
   in-tree, CLAUDE.md proposed-not-applied, skillgen fragments if CLI text
   changed (regen + `--bless`).

## Required workflow

Explore → plan (files you'll touch, pause for my confirmation) → implement
incrementally (task 1 lands green before 3) → verify per phase: `just test`,
local pyz build + smoke (report byte-identical to wheel install over the same
ledger), dummyrepo extension (launcher-mode wiring grep: no `cage.exe`, no
bare-`cage` probe in written files; pyz smoke step), skillgen `--check`,
determinism double-run on one derived view under the pyz.

## Constraints (hard)

- $0/stdlib (`zipapp`, `importlib.resources`); standard wiring mode stays the
  default and byte-identical for existing users; fail-open shim contract in
  both modes; four agents; additive-only.
- **Do not modify the PyPI publish job.** The pyz is CI-built only — never
  build-and-attach from a laptop.
- No PyInstaller/frozen binaries, no signing claims — checksum + approved-
  interpreter execution is the offer.
- No commits; working tree only.

## Acceptance criteria (self-check)

- [ ] Every handoff §2 box satisfied.
- [ ] Bundled-data reads work from wheel AND pyz (tested); wheel behavior
      byte-identical.
- [ ] Launcher-mode files contain nothing exe-shaped (grep-tested);
      `CAGE_RUN_PYTHON=1` honored; mode persisted + doctor-reported.
- [ ] CI: pyz job independent of publish job; smoke matrix green; checksums
      attached.
- [ ] `docs/restricted-environments.md` linked from README; query answers;
      portable-wiring doc updated.
- [ ] `just test` green; zero commits.

## Guardrails

- If any bundled-data consumer can't migrate cleanly (a genuine
  filesystem-only need), STOP and show me the case rather than shipping a
  pyz that half-works.
- The handoff's OPEN QUESTIONS are mine — surface, don't resolve.
