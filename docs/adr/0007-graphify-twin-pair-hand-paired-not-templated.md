# ADR 0007 — the graphify interceptor is a hand-paired twin, installed on every OS, spec'd outside package data

- **Status:** Accepted (v0.38.0, plan §5)
- **Date:** 2026-08-01
- **Deciders:** Arpit (ratifier), Claude (Opus 5, WIN-GF executor)

## Context

`cage/data/shims/graphify` was a single extensionless bash script. Windows resolves a
bare `graphify` **only** through `PATHEXT` (`.COM;.EXE;.BAT;.CMD;…`), which has no
extensionless entry — so the shim could never be *found* there, and the shim capture
route was structurally absent on Windows (WIN-GF, found by release CI on v0.37.x).

Fixing it raised three questions with real, expensive-to-reverse answers, none of them
obvious from the code:

1. Does the Windows twin install **only** on Windows, or on every OS?
2. Is one twin generated from the other (a shared template), or are they hand-paired?
3. Does the behaviour contract live beside the shims (package data) or in `docs/`?

## Decision

**All three, decided together, because they reinforce one another:**

- **Both twins install on every OS.** `cage setup` writes `bin/graphify` *and*
  `bin/graphify.cmd` regardless of the host OS; `adoptcmd.refresh_shim` completes
  whichever twin is missing when the other is already present.
- **Hand-paired, not templated.** Two separate files, written and reviewed
  independently, kept in sync by a written contract and tests — not generated from one
  source.
- **The contract lives in `docs/shim-contract.md`, not beside the shims.**
  `cage/data/shims/*` is bundled package data (shipped inside the wheel/pyz); the
  contract is project documentation.

## Consequences

- A `bin/` scaffolded on macOS is byte-identical to one scaffolded on Windows — cloning
  a project across OSes never leaves a machine with only the twin it cannot run.
  (`paths.GRAPHIFY_SHIMS` / `graphify_shims()` is the one enumeration every writer and
  reader shares, so this can't be forgotten in a new call site.)
- The Windows-only alternative would have shipped an interceptor that *looks* installed
  everywhere but a Linux/macOS user's `bin/` would carry a dead `.cmd` twin their shell
  never touches — harmless, but a discoverable inconsistency ("why is there a `.cmd`
  file in my Linux project?") is cheaper to explain once, here, than to re-litigate per
  bug report.
- Hand-pairing means every future change to shim behaviour touches **two files plus the
  contract** — real ongoing cost, paid deliberately (see *Alternatives rejected*).
- The contract's marker set (`cage data graphify` / `cage graphify` /
  `graphify metering interceptor`) has **three** copies by necessity — the sh `grep -E`,
  the cmd `findstr /C:`, and `pathshim._INTERCEPTOR` — and drift between them silently
  disables liveness detection *and* re-enables the stacked-shim recursion this project
  already lost nine days to (F1). The contract doc and `tests/test_win_graphify_shim.py`
  exist specifically to make that drift loud.
- `docs/shim-contract.md` is package documentation, not package data — a wheel or
  `cage.pyz` never ships it. Anyone auditing the twins reads it from the repo/GitHub,
  not from an installed copy.

## Alternatives rejected

- **Windows-only install.** Rejected above (an inconsistent, unexplained `bin/` on
  non-Windows clones is a worse failure mode than one extra inert file).
- **A shared template rendering both twins** (the `runshim.py` pattern —
  `cage-run`/`cage-run.cmd` from one Python string pair). Rejected: `runshim.py`'s pair
  is simple enough (PATH-probe-and-exec) that one template genuinely captures both. The
  graphify interceptor is not — it carries a recursion guard, a capability probe, and a
  PATH walk that skips every other interceptor, and **cmd has no `exec`** (the shim's
  single most consequential divergence: the real binary runs as a child process, not a
  replacement). Batch and POSIX sh share essentially no syntax subset once control flow
  gets this involved; a "shared template" would in practice be two templates wearing one
  name, which is worse than two files that admit they're different.
- **Contract as a code-level docstring instead of a `docs/` file.** Rejected: the
  contract is tested from *outside* both shim files (`tests/test_win_graphify_shim.py`
  reads both twins' text and checks them against it), and a spec that has to be imported
  from a specific module to be read is worse UX for the human auditing a shell script
  than a markdown file linked from `cage query graphify-shims`.

## Reference

[docs/shim-contract.md](../shim-contract.md) is the worked artifact — B1–B8 binding
behaviours, D1–D7 documented divergences, the four-mechanism anti-recursion proof.
`docs/proposals/tool-integration-contract.md` is why this matters beyond graphify: the
contract is designed to be the template the *next* tool interceptor copies, with only
the tool name, the cage verb, and the marker strings changing.

## Veto condition (when to revisit)

**Contingent — the templating call, and only the templating call, is revisitable:**
this decision reopens only when **a third tool interceptor exists** *and* at least two
of the three (including graphify) share a syntax family close enough that one template
could render both without becoming "two templates wearing one name" (the failure mode
above). Two shims sharing nothing but a *shape* — as sh and cmd do — does not meet this
bar; the trigger is a **named third interceptor**, not an argument that templating would
be nice.

**Invariant — does not move with tool count:** the *written contract* is the shared
artifact across every tool interceptor cage ever builds, not the code. Whether there are
two interceptors or twenty, each still gets its own written contract and its own
hand-paired implementations, because a generated pair hides exactly the divergence
(`exec` vs `call`, PATHEXT vs extensionless) that a human auditing "does this still do
what it says" needs to see in plain text. This does not revisit on evidence; it reverses
only by ratifying a change to this ADR.

**Deliberately not taken, left open:** a **generator that emits the *test* skeleton**
from the contract (not the shim itself) — i.e., codify B1–B8/D1–D7 as structured data
once, and have `test_win_graphify_shim.py`-shaped suites generate per-tool. This is a
meaningfully different proposal from templating the shims and was not built here; it is
recorded so a future agent building the second tool interceptor doesn't rediscover it
from scratch, but also doesn't mistake its absence for an oversight.
