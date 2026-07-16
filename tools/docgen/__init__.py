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
- ``--target policy``   → **two** generated regions of the bundled
  `cage/data/policy.toml`: (1) the `# formula:` comment lines above their
  budget/human headers, from the same registry (carried into project policies
  by `cage policy sync`'s normal add path); and (2) the inert, ~-relative
  `[sources]` documentation block between the ``# cage:sources-start`` /
  ``# cage:sources-end`` sentinels, from `paths.builtin_source_docs()` (a comment
  block — `tomllib` sees no `sources` key; the defaults stay in code). A missing
  sentinel fails loudly with the regenerate command; prose outside survives. Both
  regions are one writer on one file, so `--target policy` owns the whole file and
  `TARGETS` stays 1:1 with files (a separate `sources` target would race this one).

``--check`` regenerates in memory and exits 1 on drift instead of writing.
"""
