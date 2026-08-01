# Phase benchmark — cage capture, per agent × surface × graphify-state (2026-08-01)

**Artifact type:** phase benchmark — derived from run reports, **introduces no new
numbers.** Every figure below traces to
[2026-07-29 run report](2026-07-29-run-report.md) (scripted CLI legs) or
[2026-08-01 leg D run report](2026-08-01-leg-d-run-report.md) (manual VS Code / IDE
cells), each of which cites its own ledger.

**Supersedes** [2026-07-29-phase-benchmark.md](2026-07-29-phase-benchmark.md), which is
bannered and retained unedited as the record of what was true before leg D ran.

**Phase I is now complete: scripted legs + manual leg D.** This is the current statement
of what cage captures, and of what it still does not know.

> **⚠ Read the savings numbers below as GROSS.** `saved` is a per-query counterfactual; it
> excludes the cost of *using* the tool. In leg D's own paired arms the graphify-**ON**
> session cost **+31%** more than the OFF session while cage printed a saving — **n = 1,
> UNPROVEN, a signal not a measurement**, but the *label* problem is structural and does
> not depend on n. Every receipt figure in this benchmark inherits it, and so does the
> `repoceiling` bound. See
> [finding — `saved` is GROSS](2026-08-01-finding-saved-is-gross.md). This
> benchmark is not publishable without that counterweight, and it is not stated as a
> footnote for that reason.

## Legend

✅ **verified** — real traffic, reconciled, cited ·
⬛ **HONEST-LIMIT** — the *source* cannot carry it; cage's behaviour is correct ·
⬜ **UNTESTED** — the path was never exercised; explicitly **not** a pass and **not** a
confirmed limit ·
▨ **NOT AVAILABLE** — the surface does not exist to test ·
**FINAL** vs **PENDING** are tracked separately from the verdict.

---

## The matrix

| agent · surface | token capture | graphify OFF | graphify ON — capture | verified by |
|---|---|---|---|---|
| **claude · CLI** | ✅ exact (386 rows = 181 + 205 turns) | ✅ 0 receipts | ✅ **1 receipt** (weak auto-adoption via hook + CLAUDE.md) | 07-29 — 3-way reconcile, isolated ledger |
| **claude · VS Code** | ✅ **exact** — 30 rows, 1,288,664 in / 8,000 out, log = ledger | ✅ 0 receipts (D1) | ✅ **2 receipts, 18,456 tokens saved, `route: transcript`** — agent invoked graphify **unprompted, twice** (D2) | 08-01 leg D, D1 + D2 |
| **copilot · CLI** | ✅ exact (idempotent) | ✅ 0 receipts | ✅ **23 receipts via F1** when invoked; **0** when not (adoption) | 07-29 — 3-way reconcile; F1 on real traffic |
| **copilot · VS Code** | ✅ **exact** — 5 rows (OFF) / 4 rows (ON); `surface = vscode` ✅ | ✅ 0 receipts (D3) | ⬜ **UNTESTED — copilot never invoked graphify.** 0 usage rows, 0 receipts. **F2's usage-row-without-receipt limit was never exercised and is NOT confirmed** | 08-01 leg D, D3 + D4 |
| **kiro · CLI** | ▨ **NOT AVAILABLE** — no headless `-p` (Electron IDE) | ▨ | ▨ | 07-29 — premise-checked |
| **kiro · IDE** | ⬛ **HONEST-LIMIT** — credit-derived `estimated`, `tokens_out = 0`, **and no `ts` / `session` / `project`**; re-import idempotent ✅, `surface = ide` ✅ | ⬛ rows captured but **not separable by arm** (D5) | ⬜ **UNTESTED — kiro never invoked graphify.** 0 usage rows, 0 receipts (D6) | 08-01 leg D, D5 + D6 |

### Two cells deserve their exact wording

- **copilot · VS Code · graphify ON is UNTESTED, not confirmed.** The predicted limit (F2:
  the chat store carries the tool command but not its result, so no counterfactual can be
  sized ⇒ a usage row with no receipt) **never got a chance to fire**, because copilot did
  not invoke graphify at all. Reporting F2 as "confirmed" would be the single easiest
  over-claim in this benchmark. It is not confirmed.
- **kiro · IDE has no reportable A/B.** D5 and D6 rows are literally indistinguishable in
  the ledger. **No kiro ON/OFF delta may be reported** — see
  [the finding](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md).

---

## What this phase proves that the scripted legs did not

- **The VS Code surface captures.** Both extension-driven agents produce exact token rows
  in an isolated per-workspace ledger — the first time this was shown on real traffic
  rather than assumed.
- **The transcript route is what makes VS Code graphify savings visible.** In D2 the
  interceptor shim was *not* on the extension subprocess PATH, so the shim route produced
  nothing; the transcript route (GC2) caught both queries. With only the PATH shim, the
  savings would have been invisible. This is the live resolution of §B's shim
  contingency for claude · VS Code.
- **Adoption is agent-specific, and cage measured it.** Same workspace, same six
  questions, same graphify install: claude invoked graphify unprompted, copilot and kiro
  did not. The usage log is what makes *"never ran"* distinguishable from *"ran but cage
  missed it"* — without it, all three would look identical and the conclusion would have
  been a capture bug.
- **Per-surface attribution is agent-dependent** — copilot's stores are separate
  (`surface = vscode` ✅), claude's are shared (`surface` empty, unknowable). For claude,
  `project` is the discriminator that does work.

---

## The correctness bar, per agent (unchanged, now met on both surfaces)

Cage can never be more precise than its source, so the bar differs by agent and is stated
per cell, never averaged:

| agent | token bar | met? | graphify savings bar | met? |
|---|---|---|---|---|
| **claude** | **exact** to the token | ✅ CLI + VS Code | receipt per query; routes converge to one receipt | ✅ CLI (1) + VS Code (2, transcript) |
| **copilot** | **exact**, but the model is a **router alias** (`copilot/auto`) ⇒ rows are **UNPRICED** — a *source* limit, and correct refusal-to-guess behaviour | ✅ exact; ⬛ UNPRICED | shim + F1 transcript receipts on CLI | ✅ CLI (23 when invoked); ⬜ VS Code untested |
| **kiro** | **credit-derived `estimated`** — **FINAL, not a defect** | ⬛ | shim receipts only; no transcript cross-check | ⬜ untested (never invoked) |

`copilot/auto` UNPRICED is a **live user-action item**
([F4](2026-07-22-finding-unpriced-copilot-auto.md)), not a cage bug: route the alias and
the rows price.

---

## Coverage, honestly (not completeness)

**Token capture, 6 cells:** ✅ **4 verified** (claude CLI + VS Code, copilot CLI +
VS Code) · ⬛ **1 HONEST-LIMIT** (kiro IDE — captured, but estimated and unattributable) ·
▨ **1 NOT AVAILABLE** (kiro CLI). **0 UNPROVEN.**

**graphify-ON capture, 6 cells:** ✅ **3 verified** (claude CLI, claude VS Code, copilot
CLI) · ⬜ **2 UNTESTED** (copilot VS Code, kiro IDE — the agent never invoked graphify;
adoption, not capture) · ▨ **1 NOT AVAILABLE** (kiro CLI).

**What this benchmark does NOT certify — the savings *number*, only its *capture*.** Every
✅ above answers *"when a saving happened, did cage see it?"* — and the answer is yes, on
three cells. **None of them certifies that the saved figure is the net economic win.** It
is gross by construction ([finding](2026-08-01-finding-saved-is-gross.md)), and the
one paired arm in this phase points the other way (+31%, n = 1, UNPROVEN). A capture
benchmark cannot settle a metric-definition question, and this one does not pretend to.

**Standing HONEST-LIMITs — 4, all FINAL unless the source changes:**

| limit | agent | status |
|---|---|---|
| `surface` unknowable (CLI + VS Code share one store) | claude | **FINAL** — needs a marker from Claude Code |
| `copilot/auto` router alias ⇒ UNPRICED | copilot | **PENDING** user action (route the alias) |
| credit-derived `estimated`, `tokens_out = 0`, no `ts`/`session`/`project` | kiro | **FINAL** — [proxy route closed negative](2026-07-28-kiro-proxy-probe.md) |
| one global log × many ledgers ⇒ cross-ledger double-count | kiro | **OPEN** — document or warn ([finding](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md)) |

**Still PENDING after this phase (each a specific next action, not a vague gap):**

1. **F2's copilot-VS-Code receipt limit** — untested. Exercising it needs a run in which
   copilot **actually invokes graphify** (forced, as the scripted leg did on CLI).
2. **D3/D4 prompt counts** — UNVERIFIED. 5 and 4 ledger rows against a 7-turn script, with
   the prompt count unrecorded at run time. Neither "copilot logs per request" nor "turns
   went missing" is asserted.
3. **The `--path` copilot glob bug**
   ([finding](2026-08-01-finding-copilot-path-glob.md)) — OPEN, real code bug.
4. **Gross vs net `saved`** ([finding](2026-08-01-finding-saved-is-gross.md)) — the
   label fix is available immediately ("avoided read cost (gross)"); the netting is real
   work; the supporting delta needs the **repeats = 3** ON/OFF pair before it is more than
   a signal.

---

## Cost

Leg D added no new spend line of its own beyond the six manual cells' own traffic, which
is recorded per cell in the [leg D run report](2026-08-01-leg-d-run-report.md). The
scripted legs' cost — **$5.29 for 70 prompts / 429 metered turns**, 82% cache — stands as
published in the [2026-07-29 run report](2026-07-29-run-report.md).

## Related artifacts

- Run reports: [2026-07-29](2026-07-29-run-report.md) ·
  [2026-08-01 leg D](2026-08-01-leg-d-run-report.md)
- Findings from this phase: [adoption, not capture](2026-07-29-finding-adoption-not-capture.md)
  · [copilot `--path` glob](2026-08-01-finding-copilot-path-glob.md)
  · [kiro cross-ledger double-count](2026-08-01-finding-kiro-rows-double-count-across-ledgers.md)
  · [kiro no time/session/project](2026-08-01-finding-kiro-rows-carry-no-time-session-project.md)
  · [surface attribution is agent-dependent](2026-08-01-finding-surface-attribution-is-agent-dependent.md)
  · [`saved` is GROSS](2026-08-01-finding-saved-is-gross.md)
