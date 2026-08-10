---
doc: prompt — the agent-lane sweep
pair: [agent-lane-sweep.handoff.md](agent-lane-sweep.handoff.md)
---

# Prompt — the agent-lane sweep

**Model:** **Opus** — four of the seven phases are diagnosis or deletion-with-
entanglements (a foreign-file data-loss path, a normalization boundary, a rewrite of
every persisted `sha`, a capture change), and the tracker they come from is wrong in
eight places. Phases P0/P1/P3/P6 are Sonnet-shaped and are marked so inline; a Sonnet
session may take those alone.

**Progress:** 29% — P0·P1 done (2026-08-11), 5 of 7 phases remaining. 7 phases total
(P0 release · P1 CIGF-HERMETIC · P2 REV-HARDEN P3 · P3 REV-HARDEN P4-mechanical ·
P4 REV-HARDEN P4-judgment · P5 HR-COPILOT-JOIN · P6 EXPORT-SCOPE). **P0 required no
work — it was already released when the pair was picked up** (see the handoff's
corrected §P0); P1 landed with the real CI leg green 7/7 on a developer machine for the
first time.

---

Paste from here down.

---

You are picking up the agent-lane work in `cage`. Read, in this order:

1. `CLAUDE.md` (the contract — it overrides your defaults)
2. `docs/INTERVIEW.md` (the outgoing maintainer's handover)
3. `docs/agent-lane-sweep.handoff.md` (**your spec** — seven phases, with the code-verified
   corrections)

Then work the phases in the handoff's order.

## The rules that bind this whole session

- **The handoff was verified against the code on 2026-08-10 and corrects the tracker in
  eight places, marked ⚠️.** `docs/OPEN-WORK.md` and
  `docs/proposals/review-hardening.proposal.md` are older than it and have been wrong
  about their own premises before. Where any of them disagree, **re-verify against the
  code and trust the code** — then fix the stale doc on contact.
- **Line numbers in the proposal are stale**, worst at `tools/cigraphify.py:807,739` for a
  303-line file. Locate by symbol, never by a cited line.
- **One phase, one change, green on its own.** Do not batch P3 with P4 — P4's items change
  numbers already written to disk.
- **P4's sha rewrite lands LAST.** It rewrites the field the other phases' tests will have
  just been written against.
- **Two error regimes, never mixed.** Write paths stay fail-open (return `False`, swallow,
  never raise into a turn). Only the read/CLI boundary raises, as one `CageError`.
- **`method` is sacred** — no projection may ever read as `measured`.
- **Determinism** — no clocks or randomness in a derived view. Same ledger + same policy ⇒
  byte-identical tables. If a change needs a golden re-blessed, re-bless deliberately
  (`CAGE_BLESS_GOLDENS=1 pytest tests/test_output_spec.py`) and say why in the commit; if
  a change needs a *number* to move to pass, the change is wrong.

## Per phase

1. **Verify the defect still exists** before fixing it, and say so in one line. If the
   handoff is wrong about something, that finding is more valuable than the fix — write it
   down and tell me.
2. Make the smallest change that closes it.
3. **Add the test that would have caught it**, in the file the handoff names. A fix with
   no test is not done here; several of these defects are green today precisely because
   the existing test asserts the wrong layer (`tests/test_win_graphify_shim.py:185-197`
   pins `scan.dead` but never the rendered rows — that is how 5c stayed alive).
4. Run `just test` (or `python -m pytest -q`). Green before moving on.
5. **Docs, in the same change** — this repo treats a stale doc as a bug:
   - append to `docs/IMPLEMENTATION.md` (date · milestone · what · files · tests · next);
   - **delete** the closed row from `docs/OPEN-WORK.md` — never tick it — and only after
     IMPLEMENTATION.md records it; carry residuals forward as their own rows;
   - update `docs/CLI.md` if any flag or command changed (it is gated bidirectionally
     against the live parser, so drift turns the suite red);
   - update `docs/FORMULAS.md` if any number, formula or method tag changed, and keep it
     in step with `cage/explain_data.py` (the copy that ships);
   - bump the matching rows in `docs/DOC-REGISTRY.md`;
   - append to `docs/WORKLOG.md` before the session ends.
6. Update the suite count in `README.md` and `CLAUDE.md`'s `just test` comment when it
   changes.

## Gates and stops

- **P0 (release v0.48.0) — STOP.** Do not tag or run `gh release create` without my
  explicit go in this session. The GitHub release *is* the PyPI publish trigger and it is
  irreversible. Never `uv publish`/`twine`/a local publish. Before you ask me, run
  `just test` on this machine — v0.48.0's green run was on a sandbox interpreter, not this
  venv.
- **P1** — both fixes `OPEN-WORK.md` proposes are wrong. Implement the one in the handoff,
  and state in the commit what property it gives up.
- **P2.2** — do **not** twin kiro's hook. It would break a tested byte-identical-committed-
  file invariant. Name the gap.
- **P2.4** — *"nothing left to preserve"* and *"a shape I don't understand"* must become
  different branches. Two currently-green tests pull in opposite directions here; keep
  both green.
- **P2.5** — land 5a before 5b, and strip *any* trailing parenthetical, not the literal
  `" (L1 hooks)"` (kiro's is singular).
- **P5** — a capture change. Fail open to `""` rather than guessing a project; record the
  multi-root and `--path` decisions in the module docstring.
- If a phase turns out to need a **decision** rather than a fix, stop and ask me. Several
  neighbouring items are explicitly out of scope for exactly that reason, and this repo's
  standing rule is that a fork gets a `docs/compare/` doc *before* a plan — never a call
  made silently inside a fix commit.

## When the last phase lands

Archive the pair to `docs/archive/vX.Y-agent-lane-sweep.{handoff,prompt}.md` with the
one-line archive header, link it from that version's `CHANGELOG.md` entry ("Built
from: …"), update `docs/README.md` and `docs/archive/README.md`, and set this prompt's
`Progress:` line to `100%`.

Start with P1 unless I say otherwise — P0 is waiting on my go.
