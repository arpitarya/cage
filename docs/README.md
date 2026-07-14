# Cage docs — start here

The living design of record plus operations docs live in this directory's root;
everything that drove already-shipped work lives in [`archive/`](archive/README.md).
A doc here is **current spec**; a doc in the archive is **history** and must never
be cited as current spec.

## Start here

- [cage-plan.md](cage-plan.md) — the design of record: substrate contract,
  attribution engine, every plan-§ referenced from code and CLAUDE.md.
- [maintainers-interview.md](maintainers-interview.md) — the maintainer
  handoff: an outgoing model's exit interview (intent, scar tissue, working
  with the human). Context for every future maintainer, never spec; departing
  maintainers append their own lessons.

## Subsystem design docs

- [human-baseline.design.md](human-baseline.design.md) — the Tier-1 human axis
  (agent vs human, rates, confidence ladder, derived attention).
- [portable-wiring.md](portable-wiring.md) — the committed runtime-resolving shim;
  no absolute paths in committed files.
- [restricted-environments.md](restricted-environments.md) — locked-down endpoints:
  python-launcher mode, `cage.pyz`, internal mirrors.
- [debugging-capture.md](debugging-capture.md) — `CAGE_DEBUG`, heartbeats, the
  fail-open-but-never-silent contract.
- [csv-output.md](csv-output.md) — per-view CSV column contracts (plan §3.9).
- [pricing.md](pricing.md) — how a call prices: family matching, the unpriced
  workflow, policy versioning/sync, fleet repricing, credits vs prices.
- [skillgen.md](skillgen.md) — the rendered skill/prompt/steering assets
  (edit fragments, never the rendered files).
- [agents.md](agents.md) — per-agent wiring and capture surfaces.
- [adr/](adr/) — architecture decision records.

## Operations

- [full-test-plan-sibling-repo.md](full-test-plan-sibling-repo.md) — the evergreen
  manual test plan (last executed: v0.22.1; run record archived).
- [cage-claude-code-prompt-full-test-run.md](cage-claude-code-prompt-full-test-run.md) —
  the reusable Claude Code driver prompt that executes the plan end-to-end
  (version-agnostic; pairs with the plan above).
- [windows-manual-checklist.md](windows-manual-checklist.md) — upgrade Windows from
  CI-tested to field-validated.

## Active work

Unshipped handoff/prompt pairs live here until their release ships them into the
archive (the lifecycle rule in `CLAUDE.md`). **Nothing is active right now** —
the next feature's `docs/<feature>.handoff.md` + `docs/<feature>.prompt.md` pair
gets listed here.

## Archive

- [archive/README.md](archive/README.md) — every shipped handoff/prompt/build-prompt
  and superseded draft, indexed version · feature · CHANGELOG. History, not spec.
