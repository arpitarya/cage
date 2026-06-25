# Claude Code kickoff — finish hookless + build gateway metering

Paste the block below into Claude Code from the cage repo root.

---

Implement the remaining work in `docs/prompts/handoff-hookless-and-gateway-metering.md`.
That file is the source of truth — read it in full first (note §2: pricing
family-fallback, `cage import-claude`, and `import-codex` are **already done** — do
not redo them; verify and build on them). Then read: `docs/cage-plan.md` (§5, §9.5,
§3, §10), `CLAUDE.md`, `cage/clicmds.py`, `cage/cli.py`, `cage/doctorcmd.py`,
`cage/agents.py`, `cage/transcript.py`, `cage/hooks.py`, `cage/paths.py`,
`cage/policy.py`, `cage/proxy.py`, `cage/usageparse.py`, `cage/pointers.py`,
`cage/schema.py`. Don't change the substrate contract or hook entrypoints without
re-reading the plan section they touch.

Working agreement:
- **Plan before code.** Produce a short written plan (files you'll touch, the umbrella
  `cage import` dispatch + per-agent adapter mapping, the Copilot/Kiro fallback line,
  the `cage doctor` four-agent matrix, the test list) and stop for my review before
  implementing. Do not write code until I approve.
- **Phase 1 only this pass.** Deliver the umbrella `cage import [--agent ...]` (default
  `all`), the explicit Copilot/Kiro proxy-fallback output, and the four-agent
  `cage doctor` matrix — keeping `import-claude`/`import-codex` working as the
  Claude/Codex adapters. Leave the Phase-2 gateway for a separate pass, but don't
  paint it into a corner (the proxy/adapter seams should generalize).
- **Honor cage law every step:** all four agents first-class; additive (never remove
  or alter hooks/MCP or the existing import commands); $0/stdlib only;
  counts-never-content; fail-open + idempotent; deterministic. Re-read §5 of the
  handoff if unsure.
- **Empirically verify, don't assume.** Before claiming Copilot/Kiro have no usage log,
  actually check their on-disk locations and report what you found; if either does
  log usage, write a real adapter instead of the proxy-fallback line.
- **Test as specified.** Meet the Phase 1 acceptance list, including: each of the four
  agents reachable via `cage import --agent <x>`; idempotent re-import (incl. no-op
  when a hook already recorded the same turns); no-log agents emit the asserted proxy
  line; `--all` runs every adapter; existing import tests still pass; doctor renders
  the matrix. Use `policy.price_match`-priced model strings so a $0 doesn't mask a
  broken import. `just test` must stay green (112+ passing) with no changes to
  existing plan-number assertions.

Deliverable this pass: the approved plan, then the Phase 1 implementation + tests, then
the output of `just test` and a `cage import --all` / `cage doctor` run on a fixture or
the test repo. End by summarizing what each of the four agents resolves to
(import vs proxy).

When Phase 1 is merged and green, ask me before starting Phase 2 (the org gateway);
that one begins with the design doc and the per-agent reachability matrix, not code.
