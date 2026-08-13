---
doc: research — what the copilot-VSCode and kiro stores actually persist about tool runs
date: 2026-08-07
probed: VS Code 1.132.0 chatSessions (157 files · 7,741 tool parts · 1,132 terminal runs) ·
  kiro-cli 2.16.0 conversations_v2 (19 conversations, 2 live probe runs) ·
  Kiro IDE 0.12.333 workspace-sessions (16 session files)
relates: graphify-agent-coverage.handoff.md (P0 gate) · adr/0005 (deferral) ·
  regression/2026-07-29-run-report.md (copilot-CLI route, must not regress)
---

# graphify store evidence — copilot VS Code, kiro CLI, kiro IDE

**Takeaway, in one line each:**

- **copilot VS Code is buildable, and the F2 assumption it was skipped for is FALSE** —
  `run_in_terminal` persists the command, the cwd *and* the output.
- **kiro CLI is buildable** — `execute_bash` args and results both persist — **but it
  truncates stdout at ~2000 tokens**, and most real graphify queries exceed that, so the
  query route there will honestly file nothing most of the time.
- **kiro IDE is structurally unbuildable, now confirmed rather than assumed** — and for a
  *different reason* than the handoff gave.
- **No VS Code truncation marker exists in 1,132 real samples.** Every candidate hit was
  the command's own output (clippy `cast_possible_truncation`). A substring guard would
  have false-positived on rust lint output.

Counts and structural keys only — no prompt or response body was copied out of any store.
Probes were read-only; both SQLite reads used `mode=ro&immutable=1` on a copy.

## 1 · copilot VS Code — `chatSessions` DOES persist terminal commands and results

`~/Library/Application Support/Code/User/workspaceStorage/<hash>/chatSessions/<id>.jsonl`
— 157 files, 43 workspace hashes, VS Code 1.132.0 (copilot-chat bundled).

Record format is the patch stream `parse_copilot_vscode_calls` already walks: `kind:0`
(initial snapshot), `kind:1` (set at key path `k`), `kind:2` (append at `k`). Tool parts
live in `requests[i].response[]` and reach the reader through three carriers —
`kind:0 → v.requests[].response`, `kind:2 k:["requests"] → v[].response`, and
`kind:2 k:["requests",i,"response"] → v[]`. **All three must be walked**; the last is the
common one for a live session.

### Part census (7,741 tool parts)

| `toolId` | count | | `toolInvocationSerialized` key | count |
|---|---|---|---|---|
| `copilot_readFile` | 2,932 | | `toolCallId` / `toolId` / `invocationMessage` | 7,741 |
| **`run_in_terminal`** | **1,132** | | `toolSpecificData` | 1,830 |
| `copilot_createFile` | 1,015 | | `resultDetails` | 633 |
| `copilot_replaceString` | 748 | | `pastTenseMessage` | 5,207 |

### The terminal part — every field the route needs

`toolSpecificData` on `run_in_terminal` is `kind: "terminal"` (1,114/1,132) and carries:

| field | present | shape |
|---|---|---|
| `commandLine` | 1,114 | dict — `{original, toolEdited}` (536) or `+{forDisplay, isSandboxWrapped}` (578) |
| `cwd` | 1,114 | URI dict — always has `path` + `scheme`; `fsPath`/`external` vary |
| `terminalCommandOutput` | 1,011 | `{text: str, lineCount: int}` |
| `terminalCommandState` | 1,079 | `{exitCode?, timestamp, duration}` |
| `resultDetails` | 133 | `{input, output: [{isText, type, value}], isError}` |

`commandLine.original` is the command as issued — this is what `graphify_ops()` parses.

**`cwd` is per-command**, which is *better* than the handoff's plan of resolving the
workspace from the sibling `workspace.json`. That file exists and works as a fallback
(`{"folder": "file:///Users/…/test-repo"}`, confirmed) but `toolSpecificData.cwd.path`
is exact and needs no second file read.

### Which carrier is the `actual`? — a real fork, see OPEN QUESTION A

Two carriers hold the output and they **never agree**: across the 133 parts carrying
both, `resultDetails.output[].value` is consistently *larger* than the ANSI-stripped
`terminalCommandOutput.text` (worst case 46,459 vs 37,941 chars; 0/133 identical, 21/133
within 2%). `resultDetails` is the model-facing result — the analogue of the claude
route's `tool_result` — but it is present on only **133/1,132** parts, so a route that
required it would file on ~12% of terminal runs.

### Truncation: no VS Code marker exists in this corpus

- Output sizes: p50 451 B · p95 4,925 B · max **44,930 B**, with no clustering at any
  round boundary — **no observed cap**.
- Marker sweep over both carriers hit `truncat`/`exceeds` **23 times, and every single
  one was the command's own output** — rust clippy's `cast_possible_truncation` lint and
  a `--max-diagnostics` message. **Zero VS Code-inserted markers.**
- `lineCount > len(text.splitlines())` on 341/1,011 parts looked like elision but is not:
  338 of those 341 contain `\r` and 197 contain `\x1b` — `lineCount` counts *rendered*
  terminal lines including redraws. **`lineCount` is not a truncation detector.**

Consequence: the handoff's marker-based truncation guard **cannot be pinned from
evidence** for VS Code. What *is* evidence-backed: output carrier absent (121/1,132 parts
have neither) and `terminalCommandState.exitCode` missing or non-zero.

### The report-read route needs no result text and is fully buildable

`copilot_readFile.invocationMessage` is a markdown-string dict whose `uris` map carries
the structured path (2,932/2,932):

```
{"value": "Reading [](file:///…/hello_claude.py)", "uris": {"file:///…": {"$mid":1, "path":"/…", "scheme":"file"}}}
```

`_is_report_path()` matches against `uris[].path` directly.

### The gap: zero graphify runs in the corpus

**No `run_in_terminal` command in 1,132 samples contains `graphify`.** The 14 files that
match `graphify` match it in file content and instruction text, not in a command. The
route is buildable on strong *structural* evidence (the store is command-agnostic — it
persists whatever ran, ANSI included), but **no graphify-specific run has been observed**.
See OPEN QUESTION B.

## 2 · kiro CLI — buildable, and truncation is real and pinned

`~/Library/Application Support/kiro-cli/data.sqlite3`, table `conversations_v2`, keyed by
the symlink-resolved cwd (19 rows). kiro-cli 2.16.0.

Two live probe runs were made in `~/my_programs/cage` for this gate (0.09 + 0.12 credits).

### Shapes, verified against a real `execute_bash` run

```
value.history[i].assistant.ToolUse.tool_uses[]
    → {id, name: "execute_bash", orig_name, args: {command, working_dir, summary?}, orig_args}

value.history[j].user.content.ToolUseResults.tool_use_results[]
    → {tool_use_id, status: "Success", content: [{Json: {exit_status: str, stdout: str, stderr: str}}]}
```

- Pairing is by `tool_use_id`, exactly like the claude route's `tool_use_id`.
- **Results land in the NEXT history entry**, not the one carrying the ToolUse. A turn that
  errors before the follow-up persists the command with no result (observed on probe 1).
- cwd: `args.working_dir` (exact) → `user.env_context.env_state.current_working_directory`
  → the row key. All three were present and agreed.
- `fs_read` results use `{Text: str}` instead of `{Json: …}` — the report-read route
  reads `args.operations[].path` and needs no result body.
- Tool registry (`value.tools`) confirms `execute_bash` on all 19 conversations, schema
  `{command (required), working_dir, summary}`.

### Truncation marker — pinned exactly

A `graphify query` producing 6,039 chars of stdout was stored with the literal suffix:

```
\n... (truncated to ~2000 token budget)\n
```

cut **mid-token** (`…NODE test_s`). This is kiro's own marker, appended at the very end.

**This is the load-bearing finding for the kiro route.** A truncated stdout under-counts
`actual`, which *inflates* the modeled saving — the exact fabrication the method law
forbids. The guard is an **anchored end-of-string** check, not a substring search, and it
will fire on most real graphify queries: the smaller `graphify explain ledger` (300 chars)
stored complete, the ordinary `graphify query` did not. Expect the kiro-CLI *query* route
to file honestly-nothing most of the time; the *report-read* route is unaffected.

## 3 · kiro IDE — unbuildable, confirmed, for a different reason than assumed

The handoff said kiro IDE has only the token log. **It has more than that**, and the
extra store still cannot support a receipt:

`~/Library/Application Support/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/<base64url(cwd)>/<sessionId>.json`
— 6 workspaces, 16 session files. Directory names decode cleanly
(`L1VzZXJzL2FycGl0YXJ5YS9teV9wcm9ncmFtcy90ZXN0LXJlcG8_` → `/Users/arpitarya/my_programs/test-repo`),
and each file carries `sessionId`, `workspacePath`, `workspaceDirectory`, `title`, `history`.

But:

| what was checked | result |
|---|---|
| `history[].message.content` block types | `user:text` × 27 — **only user turns** |
| assistant / tool_use / tool_result blocks | **0** |
| `history[].promptLogs[].completion` | **26 of 26 are the empty string** |
| `history[].promptLogs[].prompt` | user turns only; longest 815 chars across a whole session |

**No assistant output, no tool call, no tool result is persisted anywhere in the Kiro IDE
store.** There is nothing to detect and nothing to size a counterfactual with. This is a
structural limit of the client, not a cage gap — it belongs in the P3 loud-gap treatment
(OPEN QUESTION 2 in the handoff answers itself: yes, documented gap).

## 4 · What each route can file

| route | query receipt | report-read receipt | evidence |
|---|---|---|---|
| copilot VS Code | yes — `commandLine.original` + output carrier | yes — `copilot_readFile.uris[].path` | structural, 1,132 samples; **no graphify run observed** |
| kiro CLI | yes, **when stdout is untruncated** | yes — `fs_read args.operations[].path` | 2 live runs, both shapes pinned |
| kiro IDE | **no** | **no** | 16 files, 26 empty completions |

## 5 · Open questions this evidence raises (not in the handoff)

- **A · which VS Code carrier is the `actual`?** `resultDetails` is model-facing but
  covers 12% of runs; `terminalCommandOutput` covers 89% but is the UI buffer (ANSI, redraws).
- **B · is the structural VS Code evidence enough to build on**, or does P1 wait for one
  confirming graphify run in a real Copilot chat?
- **C · the VS Code truncation guard has no marker to key on.** Options: structural-only
  guard (evidence-backed), or an `UNVERIFIED-FORMAT`-labelled marker set.
- **D · kiro's ~2000-token cap makes its query route mostly silent.** Worth shipping, or
  is report-read + a named gap the honest kiro answer?

## 6 · Verdicts (Arpit, 2026-08-07, at the P0 gate)

| # | question | verdict |
|---|---|---|
| OQ1 | probe copilot-chat's own transcripts as a fallback? | **Not needed** — the query route is possible; F2 was wrong |
| OQ2 | is kiro-IDE-as-documented-gap acceptable? | **Yes** — now confirmed by measurement, not assumed |
| A | which VS Code carrier is the `actual`? | **`resultDetails` when present, else ANSI-stripped `terminalCommandOutput.text`** |
| B | build VS Code on structural evidence? | **Build now**; one real graphify run in a Copilot chat confirms post-build (handoff §9 manual item) |
| C | VS Code truncation guard | **Structural signals only** — no output carrier, or `exitCode` missing/non-zero. **No invented marker string** |
| D | kiro's mostly-silent query route | **Ship both routes** (query + `fs_read` report-read) and **name the ~2000-token cap** in doctor + explainer |

## Reproducing

```bash
# VS Code (read-only, no copy needed)
ls ~/Library/Application\ Support/Code/User/workspaceStorage/*/chatSessions/*.jsonl

# kiro CLI — always copy first, then open immutable
cp ~/Library/Application\ Support/kiro-cli/data.sqlite3 /tmp/k.db
python3 -c "import sqlite3;print([r[0] for r in sqlite3.connect('file:/tmp/k.db?mode=ro&immutable=1',uri=True).execute('select key from conversations_v2')])"

# Kiro IDE
ls ~/Library/Application\ Support/Kiro/User/globalStorage/kiro.kiroagent/workspace-sessions/*/
```
