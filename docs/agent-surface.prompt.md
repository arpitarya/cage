# Claude Code prompt — the agent surface, all phases (AGENT-L0…L3)

**Model: per phase — P0 Sonnet · P1 Sonnet · P2 OPUS · P3 Sonnet.** P2 is Opus because
it wires three agents' hook systems into a capture path that must stay fail-open and
must not change a single number; a wrong call there re-creates the silent-unmetering
class this project has already paid for twice.

**Run the phases in order and stop at each gate.** Do not start a phase whose gate has
not passed. **No paid LLM calls. The cage tree stays uncommitted** (commits in
`cage-lab` only).

## Read first

- [agent-surface.handoff.md](agent-surface.handoff.md) — all four phases, per-phase detail
- [proposals/agent-surface-layers.md](proposals/agent-surface-layers.md) — the ladder
- `cage/mcpserver.py` (the six existing tools) · `cage/verdict.py` (**a pure composer**) ·
  `cage/compare.py` (`MIN_COMPARE_N`) · `cage/{claude,copilot,kiro}wire.py` ·
  `cage/wiringscan.py` · `CLAUDE.md` (portable wiring, three-agent invariant, fail-open)

## The rule that outranks every phase

**L0 must work perfectly, alone, forever.** Every layer above is opt-in and degrades to
absent. **If removing a layer changes a number, the phase is wrong** — stop and report
rather than adjusting the number.

---

## P0 — residue + the floor test (Sonnet)

Remove the README's claims of a skill that no longer exists (≈ lines 60, 69, 219),
including **"all four agents"** — no skill exists and it has been **three** since v0.33.
Remove `--no-skill` if the CLI still accepts it.

**Do not touch `claudewire._strip_stale_hooks`** — migration, not residue.

**Then build the floor test**: a project with **no hooks, no MCP, no steering** captures,
derives and reports identically. **This must exist before P1**, because P2 and P3 are
judged against it.

**Gate:** floor test green; no skill claim anywhere.

## P1 — L2: MCP (Sonnet)

Add **`cage_verdict`** and **`cage_compare`**, mirroring the six existing tools exactly.

**The refusals are the point.** `INSUFFICIENT DATA` · `SAVING (GROSS)` · the min-n block
must reach the agent **verbatim**. Test each path. A tool that returns silence where the
CLI would have explained itself is worse than no tool.

Add **one** write tool: **`cage_task_outcome`**. Every starved surface is starved because
nobody closes tasks. Append-only through the existing path, validated single-token label,
never rewrites history, fail-open. **It is the only write tool in the entire ladder** —
say so in its docstring so the next reader doesn't add a second by analogy.

`verdict` stays a pure composer. If the wrapper seems to need a new statistic, stop.

**Gate:** refusals verified as refusals; CLI output byte-identical; floor test still green.

## P2 — L1: hooks + steering (**OPUS**)

**Build for the two things L0 structurally cannot do**, not for real-time capture:

1. **Agent identity at capture** — a hook knows which agent fired it. **Stamp it; never
   infer it.** This is what ADOPT-COV cannot get from a shim subprocess.
2. **Auto task-close on session boundary** — unblocks `compare`/`estimate`/`calibration`/
   NET-1 at once.

Plus: give `budget.check` its first real caller — block *before* a paid call when
`on_exceed = "block"`.

All three agents (`agents.SURFACES`), reusing `<agent>wire.py`. **Committed files
reference `.cage/bin/cage-run`, never an absolute path** — `tests/test_portable_wiring.py`
greps for this. Every wired verb must be visible to `wiringscan`, or a future rename
silently kills capture (F1, twice burned).

**Hard gates:**
- **Opt-in** — `cage setup` stays hookless by default.
- **A test proves the same ledger yields identical derived output with hooks present and
  absent.** This is the phase's real acceptance criterion.
- **No double capture** — hooks and pull must not both record a turn; prove the id
  dedupe holds.
- Fail-open: a hook error never breaks the agent's turn.

**Gate:** hooks change no number; no double capture; portable-wiring test green.

## P3 — L3: skills (Sonnet)

**Governing rule, in every skill: a skill never computes a number — it runs cage and
quotes it.** Method tags verbatim, refusals relayed never smoothed, no arithmetic.

Build order: **task-closer** (needs P1's write tool) → **analyst** → **doctor-triage** →
**honesty-reviewer** → **release** → **lab-runner** → **windows-shim**.

**One source text per skill, three deliveries** (Claude skill · Copilot prompt · Kiro
steering). **Never hand-write three copies** — that is the drift the shim contract exists
to prevent, in prose.

**Gate:** no skill computes a number; all three deliveries render from one source.

---

## Hard constraints (all phases)

- stdlib only; `dependencies = []` unchanged; no network in L0.
- Determinism: same ledger + policy ⇒ same tables, at every layer.
- Fail-open on every write path; typed `CageError` only at the CLI boundary.
- Three agents, always — never drop or silently break one.
- No commits in `cage`; don't touch `docs/regression/**`.

## Stop and report if

- A phase's gate cannot be met without changing a number.
- P2 needs a second write tool, or P3 needs a skill to compute something.
- Hook capture and pull capture both record a turn and dedupe doesn't hold.

## Handback (per phase, not just at the end)

What landed · the gate evidence (the actual test output, not a claim) · anything in the
handoff that proved wrong · re-blessed goldens · what the next phase should do
differently.
