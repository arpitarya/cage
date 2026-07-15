"""tools/docgen — build-time documentation generators (plan Phase 5.6).

Three generated surfaces, one source each, all drift-gated in CI (the skillgen
pattern — build-time only, stdlib-only, never imported at runtime, never in the
wheel):

- ``--target spec``     → `docs/cli-output-spec.md` code blocks, regenerated
  from the golden fixtures under `tests/fixtures/goldens/` (the same files
  `tests/test_output_spec.py` asserts — documented and tested output are one
  artifact and cannot disagree).
- ``--target formulas`` → `docs/formulas.md` formula blocks, regenerated from
  the `cage/explain_data.py` calculation registry (the same entries `cage
  query` renders live). Hand-written prose between blocks survives — only the
  anchored code fences are rewritten.
- ``--target policy``   → the `# formula:` comment lines in the bundled
  `cage/data/policy.toml`, from the same registry (carried into project
  policies by `cage policy sync`'s normal add path).

``--check`` regenerates in memory and exits 1 on drift instead of writing.
"""
