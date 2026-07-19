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
- [formulas.md](formulas.md) — the formula catalogue: every computed number's
  shape, method tag, and knobs. **Generated** from the explain registry
  (`python -m tools.docgen --target formulas`; CI `--check` gates drift —
  the CLAUDE.md rule, now mechanical).
- [cli-output-spec.md](cli-output-spec.md) — per-command, per-state output
  contracts (LIVE BEHAVIOR since output-honesty; README-linked). Code blocks
  **generate** from the golden-test fixtures (`tools.docgen --target spec`,
  CI `--check`) — documented and tested output are one artifact.

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
- [sources.md](sources.md) — `[sources]` in policy.toml: configurable import paths
  per agent + custom tools, provenance, the portability guard (plan Phase 4).
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
archive (the lifecycle rule in `CLAUDE.md`).

- [output-and-simplification.plan.md](output-and-simplification.plan.md) — the
  plan of record for the current cycle. Phases 1–4 (output honesty → CLI tiering →
  `[sources]`) shipped in **v0.28.0**; the backlog sweep remains.
- [capture-architecture.plan.md](capture-architecture.plan.md) — design of record for
  the capture rework: capture-on-read replaces hooks as the correctness path, push
  (graphify/fux/proxy) and pull converge on one canonical ledger, and capture becomes
  visible. Built as [capture-architecture.handoff.md](capture-architecture.handoff.md)
  + [capture-architecture.prompt.md](capture-architecture.prompt.md). **Phase 1
  (additive — no hook touched) shipped in v0.31.0**; the pair stays here (not archived)
  until **Phase 2** (deleting the token-capture hooks) ships in a later release.
- [capture-health.handoff.md](capture-health.handoff.md) +
  [capture-health.prompt.md](capture-health.prompt.md) — make silent zero-capture loud
  (an installed agent that matched no files warns on `cage report`). Sequence **after**
  capture-on-read, which makes its `_health` data fresher.

*(Phases 1–4 handoff/prompt pairs archived with the v0.28.0 release, the
`[sources]` visibility + globs follow-on with **v0.29.0**, and capture-health
with **v0.30.0** — see the [archive index](archive/README.md).)*

## Archive

- [archive/README.md](archive/README.md) — every shipped handoff/prompt/build-prompt
  and superseded draft, indexed version · feature · CHANGELOG. History, not spec.
