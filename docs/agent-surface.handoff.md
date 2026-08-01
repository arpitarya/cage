---
doc: handoff — the agent surface, all phases (AGENT-L0…L3)
status: decided 2026-08-02, unbuilt
design of record: proposals/agent-surface-layers.md
---

# Handoff — the agent surface, all four phases

**The ladder:** **L0 hookless** (the floor, never optional) → **L1 hooks+steering** →
**L2 MCP** → **L3 skills**. Each opt-in, each strictly additive.

**Binding rule, every phase:** *L0 must work perfectly, alone, forever.* Every layer
above degrades cleanly to absent. **No layer may become a dependency of a lower one** —
if removing L1 changes a number, the phase is wrong.

**Build order: P0 → P1 (L2) → P2 (L1) → P3 (L3).** L2 before L1 because it is cheap and
answers the product question; L1 before L3 because hooks unblock the evidence that makes
L3's advice worth taking.

| phase | layer | model | gate before the next |
|---|---|---|---|
| **P0** | L0 residue + floor proof | Sonnet | hookless proven perfect, alone |
| **P1** | L2 MCP read + task-close | Sonnet | refusals cross the boundary verbatim |
| **P2** | L1 hooks + steering | **Opus** | removing hooks changes no number |
| **P3** | L3 skills | Sonnet | a skill never computes a number |

---

## P0 — clear the residue, prove the floor

**A. Remove claims of a skill that no longer exists.** `README.md` promises one **three
times** (≈ lines 60, 69, 219), and one says **"all four agents"** — wrong twice: no skill
exists, and cage has supported **three** since v0.33. Live on PyPI. If `--no-skill` is
still an accepted flag, remove it.

**Keep `claudewire._strip_stale_hooks`** — it strips *old* cage hook entries from user
configs. Migration, not residue; deleting it abandons pre-rebuild machines to dead verbs.

**B. Prove the floor.** A test asserting a project with **no hooks, no MCP, no steering**
still captures, derives and reports identically. This is the invariant every later phase
must not break — it must exist *before* they are built.

## P1 — L2: MCP

**Read tools.** Six ship (`report` · `attrib` · `matrix` · `budget` · `roi` · `why`).
Add the two that answer the product question and are missing: **`cage_verdict`** and
**`cage_compare`**. Mirror the existing shape exactly — args, `format: csv`,
capture-on-read, `structuredContent.capture`.

**The point is the refusals.** They must cross the boundary **verbatim**: `verdict` →
`INSUFFICIENT DATA` (no receipts) and `SAVING (GROSS)` (no cost-of-use figure);
`compare` → the `MIN_COMPARE_N` block. **An agent must receive the refusal, not an empty
result that reads like zero.** A tool that silently returns nothing where the CLI would
have explained itself is worse than no tool.

**One write tool: `cage_task_outcome`.** The single most valuable mutation an agent can
perform — every starved surface (`compare`, `estimate`, `calibration`, NET-1) is starved
because nobody closes tasks. Constraints: append-only via the existing `task outcome`
path, validated single-token label, **never** rewrites history, fail-open. It is the
*only* write tool in the whole ladder; say so in its docstring.

**`verdict` stays a pure composer** — it computes no new statistics. If a wrapper seems
to need one, stop.

## P2 — L1: hooks + steering (**Opus** — this is the risky one)

**The prize is not real-time capture.** It is two things L0 structurally cannot do:

1. **A hook knows which agent fired it** → agent identity at capture time, which is
   exactly what [ADOPT-COV](OPEN-WORK.md) cannot get from a shim subprocess. Stamp it on
   the row; do not infer it.
2. **Session boundaries auto-close tasks** → unblocks `compare` / `estimate` /
   `calibration` / NET-1 in one stroke.

Also: `budget.check` finally gets a real caller — it can **block before a paid call**
(`on_exceed = "block"`), which today is advisory-only with no enforcement site.

**Scope per agent — all three, always** (`agents.SURFACES`): Claude Code hooks ·
`~/.copilot/hooks` · Kiro's one-hook-per-file `agentStop`. Reuse the existing
`<agent>wire.py` modules; the wiring convention and portability rules are unchanged —
**committed files reference `.cage/bin/cage-run`, never an absolute path**
(`tests/test_portable_wiring.py` greps for this).

**Steering** = passive text the agent reads: cage exists, the tools exist, here is what
to ask. Three deliveries, one source.

**Hard gates:**
- **Opt-in.** `cage setup` does *not* wire hooks unless asked. Default stays hookless.
- **Removing hooks changes no number** — a test proves the same ledger yields identical
  derived output with hooks present and absent.
- **Fail-open, always.** A hook error never breaks the agent's turn.
- **No double capture.** Hooks and pull capture must not both record a turn — dedupe by
  id as the substrate already does, and prove it.
- Every wired verb goes through the liveness scan (`wiringscan`), or a renamed verb
  silently kills capture again — the F1 class, twice burned.

## P3 — L3: skills

**The only layer that can carry the honesty discipline.** MCP hands an agent a JSON
number; nothing makes it say *"that's `modeled`, not measured"*.

**The governing rule, in every skill:** *a skill never computes a number — it runs cage
and quotes it.* Method tags verbatim; refusals relayed, never smoothed; no arithmetic
of its own.

Candidates, in build order:

| skill | what it does | needs |
|---|---|---|
| **task-closer** | closes a task at session end with a validated label | P1's write tool |
| **analyst** | "what did this week cost, which tool earned its keep" — quotes, never computes | P1 read tools |
| **doctor-triage** | capture failure → doctor → paths → wiring → the runnable fix; knows dead-shim ≠ not-installed | L0 |
| **honesty-reviewer** | reviews a *diff* for method-law violations: modeled rendered as measured, fabricated zeros, dropped caveats | L0 |
| **release** | the release checklist; refuses local publish | L0 |
| **lab-runner** | drives a lab cell: PATH proof, per-cell prompt count (the D3/D4 lesson) | L0 |
| **windows-shim** | B1–B8 + B8a's `<`/`>`-in-`rem` trap for anyone touching a twin | L0 |

**Delivery:** three per skill — Claude skill · Copilot prompt · Kiro steering — from
**one source text**, same fan-out discipline as every other surface. Never write three
copies by hand.

---

## Definition of done (whole program)

- [ ] **P0:** no skill claim, no "four agents", `--no-skill` gone; **floor test exists**
- [ ] **P1:** `cage_verdict` + `cage_compare` + `cage_task_outcome`; every refusal tested
      as a refusal; the write tool is the only one
- [ ] **P2:** hooks opt-in on all three agents; **agent identity stamped at capture**;
      auto task-close; budget can block; **a test proves hooks change no number**; no
      double capture; portable wiring intact
- [ ] **P3:** skills from one source × three agents; **no skill computes a number**;
      refusals relayed verbatim
- [ ] Every phase: L0 unaffected, determinism intact, `just test` green, goldens named
- [ ] Proposal archived only when **all four** phases land; partial ⇒ it stays parked
      with the remainder carried forward

## Out of scope

Making any layer mandatory · a fourth agent · a network or dependency anywhere in L0 ·
reviving the deleted machinery as-is (rebuild from this design, or not at all).
