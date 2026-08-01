---
doc: cage-lab verification
audience: whoever is scoring a run
---

# 03 — Verify: what "the numbers are correct" actually means

**The governing principle:** *cage can never be more precise than its source.* Exact
where the log carries counts, loudly `estimated` where it doesn't. So the pass bar
**differs per agent** and must be stated per cell — never averaged into one score.

## 1. The per-agent bar

| agent · surface | token bar | graphify savings bar |
|---|---|---|
| claude (cli + vscode) | **exact** to the token | receipt per query **+** report-reads; routes converge to one receipt |
| copilot cli | **exact** | shim receipts **+** transcript detection |
| copilot vscode | exact if capture works | **usage row without a receipt is the expected honest outcome** — the log carries the command but not the result |
| kiro | **credit-derived `estimated`** — this is **FINAL, not a defect** | shim receipts only; no transcript cross-check exists |

Two of these are **limits, not bugs**. Scoring them as failures would push someone to
"fix" them by fabricating precision the source cannot support — the exact thing cage
exists to prevent in other tools.

## 2. The three-way reconciliation

Every cell, every time:

```
source log  ↔  ledger row  ↔  derived view
```

- **source log** — the agent's own file, as captured verbatim
- **ledger row** — what `cage import` wrote
- **derived view** — what `cage report` / `insights attrib` computes

All three must agree. If they don't, the cell is **UNPROVEN** — never quietly passed.

Keep the eyeball surface usable: for any question, `transcript-map.json` should let
you put the log lines, the ledger row, and the arithmetic side by side.

## 3. The per-cell checklist

1. **Captured at all?** Calls appear after `cage --ledger <lab> import`.
2. **Tokens right?** Ledger vs the log — exact for claude/copilot; `estimated` is the
   *correct answer* for kiro.
3. **Surface right?** Row says `cli` / `vscode` / `ide` correctly — this is the
   surface-collision fix's live test.
4. **Session and model real?** Not a router alias, not a synthetic constant.
5. **Zero UNPRICED rows.**
6. **ON cells: THREE separate answers** (01-setup §4a) — (a) did the **hook** fire
   (graphify intervened; cage cannot see this — capture graphify's own evidence),
   (b) did graphify actually **run a query**, (c) did **cage see it** (receipt + usage
   row). `fired=yes, cage=no` is a finding; collapsing any of the three hides it.
7. **Which route produced the saving?** Shim receipt or transcript detection — and
   does it match what the pre-flight said about the shim? If the shim was dead, a shim
   receipt should be impossible.
8. **Usage rows ≥ receipts?** A receipt with no usage row means a route bypassed the
   breadcrumb.
9. **Re-import idempotent?** Import twice; the second yields **0** new rows.
10. **Dedupe holds?** Same query via shim + transcript ⇒ **one** receipt. Same query in
    two sessions ⇒ **two** (per-session attribution must survive).
11. **`~/.cage` untouched?** Depends on how the run was invoked, and the two cases have
    **opposite** expected answers (ADR 0006):
    - **Under the lab's explicit `--ledger`/`CAGE_BASE`** (the normal run): still
      untouched. An explicit sink wins for kiro too — that is exactly why the override
      exception exists, and it is what keeps the lab isolated.
    - **A default run with no `--ledger`**: `~/.cage` **is** written, by design — kiro's
      IDE rows are a machine fact and route there. Only kiro; claude/copilot are
      unchanged. Seeing kiro rows in `~/.cage` after a default run is a PASS, not
      contamination.

    So assert the *override* case. If a run wrote kiro rows to `~/.cage`, first check
    whether the driver actually exported `CAGE_BASE` before scoring it a FAIL.
12. **No machine-wide contamination?** The ledger's call count matches this run's
    turns — not thousands. Capture-on-read must be **off** (01-setup §4b); a bare
    `cage import` or an on_read sweep pulls the entire machine's agent history in.

## 4. Verdicts — four, and they are not interchangeable

| verdict | meaning |
|---|---|
| **PASS** | reconciled three ways, bar met |
| **HONEST-LIMIT** | the source cannot carry it (kiro tokens, copilot-vscode results). A *result*, not a failure |
| **UNPROVEN** | couldn't verify — missing surface, unverified PATH, no data |
| **FAIL** | the numbers disagree. A real defect |

**Coverage, not completeness.** "6/12 verified, 6 UNPROVEN" is a good report.
"12/12" bought with invented cells is worthless.

## 5. What invalidates a cell before you even score it

- The PATH-winning `graphify` was **dead** or unverified ⇒ ON cells are `UNPROVEN` by
  construction; a receipt was never possible.
- VS Code launch method not recorded ⇒ the PATH is unknown ⇒ `UNPROVEN`.
- Fixture bytes changed ⇒ this is a **new baseline**, not a comparison. Say so.
- The lab wasn't run from its `.venv` with an explicitly-set, proven PATH ⇒ the run
  isn't reproducible.

Next: [04-publish.md](04-publish.md).
