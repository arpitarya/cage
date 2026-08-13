# Finding — per-surface attribution is agent-dependent (works for one of three)

**Severity:** — (a limit of the agents' log layouts, not a cage defect) ·
**Status:** ⬛ **HONEST-LIMIT** · **Surface:** the `surface` field on call rows ·
**From:** [2026-08-01 leg D run report](2026-08-01-leg-d-run-report.md), cells D1–D4.

## What was measured

| agent | store layout | `surface` on the row | verdict |
|---|---|---|---|
| **copilot** | CLI (`session-state/*/events.jsonl`) and VS Code (`chatSessions/*.jsonl`) are **separate stores** | **`vscode`** ✅ (D3, D4) | works |
| **claude** | CLI and VS Code extension write the **same store** (`~/.claude/projects/**/*.jsonl`), with no marker distinguishing them | **empty** (D1, D2) | unknowable |
| **kiro** | one global store | `ide` ✅ (D5, D6) | works, but see the kiro findings |

**Per-surface attribution works for one of the three agents** in the sense the check was
designed to test — copilot is the only one where cage can *distinguish* CLI from VS Code
traffic, because only there are the sources genuinely separate.

## Why claude's is empty, not wrong

Cage cannot know which surface produced a claude row, because Claude Code does not record
it. An empty `surface` is the honest answer: the alternative — defaulting to `cli` — would
invent a fact. This was already recorded in the archived import-ledger plan ("CLI vs VS
Code — shared store, indistinguishable"); **D1/D2 are the live confirmation.**

Not fixable on cage's side. It would take a marker from Claude Code.

## What survives for claude — and it matters

`project` is correct on **every** claude row (`workspace-off` in D1, `workspace-on` in
D2). So:

> **Per-workspace attribution holds for claude even though per-surface does not.**

That is the axis that carried leg D's A/B: the two arms were separated by `project`, not
by `surface`. A cage user who wants to slice claude traffic has a working discriminator —
it just is not the surface one.

## Consequences for reporting

- A per-surface breakdown that includes claude will show its traffic as unattributed.
  Read that as *"the source does not say"*, never as *"CLI"*.
- Kiro's `ide` is correct but is only one of the fields kiro loses — see
  [kiro rows carry no time/session/project](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md).

## Status history

- **2026-08-01** — filed HONEST-LIMIT from leg D cells D1–D4. First manual confirmation of
  the surface-collision fix on real VS Code traffic: copilot ✅, claude structurally
  unknowable.
