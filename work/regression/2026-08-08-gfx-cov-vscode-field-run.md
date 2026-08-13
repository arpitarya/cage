# 2026-08-08 — GFX-COV field run: the copilot VS Code graphify route, on a real chat

**Verdict: the route works on a real Copilot chat, and the capture exposed two shapes the
synthetic fixture never had.** One real `graphify query` issued by Copilot Agent in VS Code
filed a receipt — **146,261 tokens saved** across 72 cited files — and re-running filed
nothing.

This closes the remaining half of OPEN-WORK **GFX-COV-FIELD**. Both new v0.47.0 routes are
now verified on real data ([kiro half, 2026-08-07](2026-08-07-gfx-cov-kiro-field-run.md)).

- Store: `~/Library/Application Support/Code/User/workspaceStorage/<hash>/chatSessions/`,
  VS Code 1.132.0, Copilot Chat in **Agent** mode.
- Shapes and the P0 evidence this verifies: [research/2026-08-07-graphify-store-evidence.md](../research/2026-08-07-graphify-store-evidence.md).

## Method

Arpit ran one terminal `graphify query` inside a Copilot Agent chat on `~/my_programs/cage`
(4,954-node graph). The resulting chat-session file was then read back through the shipped
`graphifytx.detect_and_file_copilot_vscode`.

- Receipts went to a **throwaway sandbox ledger**, never `~/.cage`.
- **The PATH shim was deliberately not in play**: `graphify` resolves to
  `~/.local/bin/graphify`, not this repo's `bin/graphify`. Had the interceptor fired, the
  store route would have *deferred* to it (ADR 0005) and the run would have proven nothing
  about the VS Code route. The absence of the shim is what makes this a clean test.

## Result

```
op=query   saved=146,261 tokens   raw_alternative=147,789   actual=1,528
method=modeled   confidence=0.6   source_files=72
session=843cda70-f714-4bd3-ae0d-a49be3a630a5   (taken from the store, not the filename)
```

Re-run: **0 new receipts** — idempotent on real data.

## The two findings the capture bought

Both are cases the synthetic fixture could not have produced, and both are now pinned by
tests (`tests/test_graphify_vscode.py`).

**1 · A real agent emits `cd <repo> && graphify query …`, not a bare command.**
`run_in_terminal` reuses one shell across calls, so Copilot prefixes a `cd`. The synthetic
fixture had a bare `graphify query`, so **nothing exercised the `&&` segment split** until
this capture. `graphify_ops` anchors on command position *per segment*, so it handles it —
but it was working by design rather than by test. Now tested, including that a `cd … &&
grep graphify` second segment still files nothing.

**2 · The real part carried no `resultDetails`** — so the carrier that actually ran in the
field is the ANSI-stripped `terminalCommandOutput` fallback, not the preferred one. This
matches the corpus (`resultDetails` on 133/1,132 parts) but had never been the path a
fixture drove end to end. Pinned, so a future change cannot quietly make `resultDetails`
mandatory and silently drop ~89% of real runs.

Three smaller shape corrections also landed in the fixture: `isConfirmed` is a dict
(`{"type": 4}`), not a bool; `cwd` carries `fsPath`/`external` alongside `path`; and the
part arrived via the `kind:2 k:["requests"]` carrier rather than the response-append one.

## Fixture provenance upgraded

`chatSession-graphify.jsonl` is now the **sanitized real capture** — every part key, the
command shape, and the record envelope verbatim; only the graphify answer is abridged, to
cite the two files the tests plant instead of requiring a 72-file corpus.

`chatSession-report-read.jsonl` is a **new, separate** fixture built from a real
`copilot_readFile` part. The captured session contained no report read, and folding a
synthetic part into a real capture would have laundered invention into a fixture labelled
real.

Sanitization is asserted, not assumed: no absolute user path and no username survives in
any graphify fixture (`grep -rilE "arpitarya|/Users/[a-z]"` → clean).

## What this does not establish

- **The 146,261-token figure is a `modeled` counterfactual, not a measurement.** It says
  *the 72 files this answer cited would have cost ~147.8k tokens to read whole*. It is
  **gross** — it excludes the cost of the turn that invoked graphify (`netsaved.GROSS_NOTE`),
  and n=1.
- **No truncation behaviour was observed**, because VS Code did not truncate — consistent
  with the P0 finding that no VS Code-inserted marker exists in 1,132 parts. The negative
  fixtures (`chatSession-negative`, `chatSession-failed`) remain **constructed**.
- **`--rescan-graphify` was not exercised against a real cursor-consumed session** here
  (that would have written to `~/.cage`); it is covered in the suite.
