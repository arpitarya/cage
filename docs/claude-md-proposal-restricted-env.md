# Proposed CLAUDE.md edits — restricted environments (python-launcher mode + cage.pyz)

**Status: applied to CLAUDE.md on 2026-07-11** (edits 1–3 below). Kept for the
record of what changed and why, matching the portable-wiring proposal's pattern.

## 1. Adapters & agents section — extend the portable-wiring paragraph

At the end of the **Committed wiring is portable (plan §5.3)** passage (after
"…`tests/test_portable_wiring.py` greps for this and must stay green."), append:

```markdown
  **Restricted endpoints (docs/restricted-environments.md):** opt-in
  python-launcher mode — `cage setup --python-launcher` persists `[wiring]
  python_launcher = true` (project policy, `policy.python_launcher`, written via
  `pricestoml.set_wiring`); `agents.install` re-reads it every run and fans it
  out to `runshim.write(python_launcher=)` (interpreter-only `_SH_PY`/`_CMD_PY`
  shim pair — nothing exe-shaped, grep-tested in
  `tests/test_launcher_mode.py` + dummyrepo S12) and to every wire module's
  `install(root, python_launcher=)` (copilot hook bash/powershell, codex + kiro
  MCP `command = "python3"|"py"`, git commit hooks — user-level files carry
  interpreter commands instead of `paths.cage_bin()`; claudewire accepts and
  ignores the kwarg, its files reference the shim). `CAGE_RUN_PYTHON=1` is the
  runtime-only override on the standard shim (never read by cage Python code —
  it lives in the shim text). `paths.cage_command_tail` also recognizes
  `python3 -m cage …` / `py -3 -m cage …` so mode switches collapse stale
  entries. Doctor's `portability` check names the mode + warns on policy↔shim
  drift; `cage query restricted-env` explains the tiers.
```

## 2. Must-Know Rules — extend the release-flow bullet

After the sentence about `publish.yml` being fired by the GitHub release,
append:

```markdown
  The same trigger runs the independent `build-pyz` → `smoke-pyz` (3-OS) →
  `release-pyz` chain that attaches `cage.pyz` + `SHA256SUMS` to the release —
  it must never gain a `needs` link to (or from) `publish-pypi`, and the pyz is
  CI-built only (local `python -m tools.buildpyz` / `just pyz` is a smoke
  check, never an upload). `cage --version`/doctor label a zipapp run
  (`(zipapp)`); bundled data reads via `paths.bundled_data()`
  (importlib.resources Traversable — never `Path(__file__)`), so it works from
  inside the archive; `paths.distribution()` is the detector.
```

## 3. Dev section — refresh the test count

`just test          # python -m pytest -q   (543 passing)` →
`just test          # python -m pytest -q   (569 passing)`

(README's `$0` section count is already updated in-tree — CLAUDE.md is the one
deliberately left for this proposal.)
