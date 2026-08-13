# graphify detection fixtures — copilot VS Code · kiro CLI · kiro IDE

Store samples pinning the **shapes a graphify savings receipt would be detected from**,
per route. Evidence for the GFX-COV P0 gate; the sourced findings behind them are
[work/research/2026-08-07-graphify-store-evidence.md](../../../../work/research/2026-08-07-graphify-store-evidence.md).

Deliberately **not** part of the agent × surface corpus above: these carry no
`expected.json`, so `tests/test_fixture_corpus.py` (which globs `*/*/expected.json`)
never picks them up. They pin *detection* input, not call rows.

Counts-never-content: every prompt, response, title and auto-approve body is
`[content stripped — counts only]`, and no absolute user path survives (asserted at
sanitization time). Where a fixture is a real capture, the **structure** is verbatim and
the graphify answer is abridged to cite the files the tests plant — so the shape is real
and the payload is small. Constructed fixtures say so in the table below.

## Shape provenance

| Fixture set | Shape status | Pinned against |
|---|---|---|
| `copilot-vscode/` | **VERIFIED** (`chatSession-graphify.jsonl`, `chatSession-report-read.jsonl`) · **SHAPE-VERIFIED** (`chatSession-negative.jsonl`, `chatSession-failed.jsonl`) | A **real** graphify run in a VS Code Copilot chat, captured 2026-08-08 (VS Code 1.132.0) and sanitized — every part key, the `cd … &&` command shape, `isConfirmed: {"type": 4}`, the absent `resultDetails` and the `kind:2 k:["requests"]` carrier are the real record's. The report-read fixture is a **real** `copilot_readFile` part repointed at the graph report. The two negative fixtures are still constructed, from the same verified key set. |
| `kiro-cli/` | **VERIFIED** | kiro-cli 2.16.0 `conversations_v2`, two live probe runs 2026-08-07. `execute_bash` args/result shapes and the truncation marker are copied verbatim from the real store. |
| `kiro-ide/` | **VERIFIED (negative)** | Kiro IDE 0.12.333 `workspace-sessions`, 16 real session files. Reproduces the finding that matters: `promptLogs[].completion` is the empty string and no assistant/tool block is persisted. |

## What each file is for

### `copilot-vscode/`

Real patch-stream shape — `kind:0` snapshot, `kind:2 k:["requests"]` appends, and
`kind:2 k:["requests",i,"response"]` appends. A reader must walk **all three** carriers.

| file | asserts |
|---|---|
| `chatSession-graphify.jsonl` | **the real captured run** — `cd <repo> && graphify query …` through `run_in_terminal`, no `resultDetails` (so the ANSI-stripped UI buffer is the carrier, as in 89% of real parts), arriving via the `kind:2 k:["requests"]` carrier. Output abridged to cite the two files the test plants; everything else is verbatim from the capture |
| `chatSession-report-read.jsonl` | a **real** `copilot_readFile` part, repointed at `GRAPH_REPORT.md` — its own file because the captured session contained no report read, and folding a synthetic part into a real capture would launder invention into a fixture labelled real |
| `chatSession-negative.jsonl` | the GC2 false-positive guards (`grep graphify`, `echo graphify`, piped `grep`) file nothing; a terminal part with **no output carrier at all** (121/1,132 real parts look like this) files nothing |
| `chatSession-failed.jsonl` | `terminalCommandState.exitCode = 1` files nothing — a failed run sizes no counterfactual |

### `kiro-cli/`

The `conversations_v2.value` JSON. Note the store's real ordering law: a `ToolUse` is in
one history entry and its `ToolUseResults` in the **next**.

| file | asserts |
|---|---|
| `conversation-graphify.json` | a complete `execute_bash` graphify query files a query receipt; cwd resolves from `args.working_dir` |
| `conversation-truncated.json` | stdout ending in the verbatim kiro marker `\n... (truncated to ~2000 token budget)\n` files **nothing** — a truncated answer under-counts `actual` and would inflate the saving |
| `conversation-no-result.json` | a `ToolUse` whose turn errored before the result landed files nothing (observed on a real probe run) |
| `conversation-negative.json` | the false-positive guards, kiro-side |
| `conversation-report-read.json` | `fs_read` of `GRAPH_REPORT.md` files a report-read — needs no result body, so truncation cannot affect it |

### `kiro-ide/`

| file | asserts |
|---|---|
| `session-no-assistant-content.json` | the route is **structurally impossible**: user turns persist, `promptLogs[].completion` is `""`, and no tool call or result is recorded anywhere. A test over this file is what keeps the P3 "loud gap" honest instead of asserted. |

## Rule

**Do not invent formats.** `copilot-vscode/`'s two positive fixtures were synthetic until
2026-08-08 and are now real captures — and the swap **earned two tests**: a real agent emits
`cd <repo> && graphify query …`, not the bare command the synthetic fixture had, and the real
part carries no `resultDetails`. Neither was exercised before. Same discipline applies to the
remaining constructed fixtures: when a real truncated or failed graphify run is captured,
replace them and flip their row.
