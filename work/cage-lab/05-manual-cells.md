---
doc: cage-lab manual cells (VS Code / IDE)
audience: Arpit — this leg is his hands
---

# 05 — Manual cells: the surfaces a script cannot reach

**Runs LAST**, after every scripted leg is green. Arpit's time is the scarcest input;
it goes only to cells a script can't reach, and only once the automated legs have
shaken out protocol bugs that would otherwise cost him the pass twice.

**Use the SAME questions the scripted legs used** (`questions.txt`, verbatim). A
different set makes these cells incomparable and wastes the run.

## 1. Pre-flight — once per machine, before any cell

Without these three answers a VS Code cell is **UNPROVEN even if it looks like it
passed** — the shim can be present, on PATH, and still silently not metering.

```bash
command -v graphify              # which one wins?
cat "$(command -v graphify)"     # cage interceptor? foreign? the real binary?
```

**Then judge:**

| the shim routes through | meaning |
|---|---|
| `cage data graphify` | **live** — metering is possible |
| `cage graphify` | **DEAD** — that verb exits 1, the shim falls through and runs graphify unmetered and **silent** |
| neither (foreign / real binary) | no metering by absence — a different result, don't merge it with "dead" |

**Record how VS Code was launched** — `code .` from a terminal (inherits the rc PATH)
or Dock / Finder / Spotlight (no rc sourced ⇒ the interceptor dir is probably absent).
The same machine gives different answers by launch method.

**Then, inside the agent**, as its first turn:

> Run `command -v graphify` and show me the output, then show me the contents of that file.

That subprocess PATH is the one that matters — not your terminal's. If it differs from
what you saw in the terminal, **that difference is the finding.**

⚠️ **The lab `.venv` does not remove this step.** It makes the *scripted* legs
deterministic; a VS Code extension's subprocess inherits VS Code's launch environment,
not the venv. To get `.venv/bin` onto that PATH you'd launch from an activated shell
(`source .venv/bin/activate && code .`) — and that becomes part of the cell's
provenance, so record it.

## 1a. How to actually type them in a VS Code extension

Per cell, in this order:

1. **Open the right folder as the workspace root** — `cage-lab/workspace-off` for an
   OFF cell, `cage-lab/workspace-on` for an ON cell. Not the lab root: the agent must
   see that workspace's `CLAUDE.md`, `.cage/`, and `.mcp.json`.
   - To give the extension the lab's PATH, launch from an activated shell:
     `cd cage-lab && source .venv/bin/activate && code workspace-on` — and **record
     that you did**, it's part of the cell's provenance.
2. **Open the agent's chat panel** — Claude Code / Copilot Chat / Kiro's agent pane.
3. **Turn 1 is always the pre-flight probe** (§1): *"Run `command -v graphify` and show
   me the output, then show me the contents of that file."*
4. **Then paste Q1…Q6 — one per turn.** Wait for each answer to finish before sending
   the next. Do not batch them into one message: the run needs one turn per question so
   the ledger rows map back to questions.
5. **Same session per cell.** Don't start a new chat between questions — session
   identity is one of the things being verified.
6. **Note the wall-clock start and end** of each cell, so the captured log window can
   be matched to the cell if anything looks ambiguous later.
7. Then run the import + report commands in §2 from a terminal.

**Repeats:** Q1–Q3 three times each (they're the graphify-sensitive ones); Q4–Q6 once.
Run the repeats as **separate sessions**, not three times in one chat — a second ask
in the same session sees the first answer in context and isn't an independent sample.

**The questions** are in [01-setup.md §4](01-setup.md) — use them verbatim, same order,
every cell, both arms.

## 2. The cells

**All three agents appear here** (law 0). Claude and Copilot also have scripted CLI
cells; Kiro has *only* these — it is not scriptable, which changes the route, not its
place in the matrix.

| cell | agent · surface | what it must answer |
|---|---|---|
| **D1** | claude · VS Code · **OFF** | do calls capture at all from the extension (tokens exact, session/model right)? |
| **D2** | claude · VS Code · **ON** | does a saving appear — and by which route (shim vs transcript)? |
| **D3** | copilot · VS Code · **OFF** | do calls capture? |
| **D4** | copilot · VS Code · **ON** | **usage row without a receipt is the expected honest outcome** — record it as HONEST-LIMIT, not a failure |
| **D5** | kiro · IDE · **OFF** | credit-derived `estimated` tokens — **FINAL, not a defect** |
| **D6** | kiro · IDE · **ON** | shim receipts only; no transcript cross-check exists |

Per cell: paste the questions one per turn, then:

```bash
cage --ledger <lab>/labledger import
cage --ledger <lab>/labledger report
cage --ledger <lab>/labledger insights attrib
```

## 3. Score each cell

Use the eleven checks in [03-verify.md](03-verify.md) §3, and one of the four verdicts
in §4 — **PASS · HONEST-LIMIT · UNPROVEN · FAIL**.

Record the pre-flight answers **alongside** the cells. They are what make the ON
verdicts interpretable: a dead shim means an ON cell could never have produced a
receipt, and without that context a reader will misread the zero as a cage defect.

## 4. Zero dummy data

A cell you can't run is **`NOT AVAILABLE`** and the leg continues. Never a plausible
row, never an inferred number. Coverage, not completeness.
