# Finding — copilot `--path` glob — RESOLVED

> **⬛ RESOLVED (2026-08-01, unreleased)** — superseding the `◻ OPEN` Status line in the
> body below. Fixed by **`[sources] path_globs`**: a second, **root-agnostic** discovery
> key beside the anchored `glob`, seeded in code, materialized into `cage.toml` by
> `cage setup`, and read from there at import (Directive A). All three `--path` branches
> now share `importcmd._override_sources`, so **no glob literal remains in any import
> branch** (AST-gated by `tests/test_path_globs.py`). `--path` over a `chatSessions/`
> tree imports with `surface = "vscode"` from the parser; a foreign `.jsonl` is never
> matched. Absent `path_globs` ⇒ `--path` scans nothing, **loudly**; the zero-match ⚠ now
> names the patterns tried. Built from
> [`work/archive/v0.36-path-globs.handoff.md`](../archive/v0.36-path-globs.handoff.md).
>
> _Banner only: it sits **above** the `HASH-COVERS-BELOW` marker, so the body below is
> byte-identical to what was originally published, and the published sha256 is unchanged.
> The body describes the bug as it stood; cite it as history, never as current behaviour._

**Finding sha256 (body below the marker = the whole file as originally published):**
`c491e214009365770da7d556a22a6ff36cdc7c70068f019b7ee4f4d33ce87ca7`
_Hashed range: from the newline after the marker to EOF; this header is excluded._

<!-- HASH-COVERS-BELOW -->
# Finding — `cage import --agent copilot --path` can never reach the VS Code store

**Severity:** medium (capture is silently off for a scoped copilot import) ·
**Status:** ◻ **OPEN — real code bug** · **Surface:** `cage import --agent copilot --path`
· **From:** [2026-08-01 leg D run report](2026-08-01-leg-d-run-report.md), cell D3.

## What happens

`importcmd.import_copilot`'s `--path` branch hardcodes the **CLI** glob:

```python
sources = ([(Path(args.path), "*/events.jsonl", "")] if getattr(args, "path", None)
           else [(s.path, s.glob, s.surface) for s in paths.agent_log_sources("copilot", pol)])
```

— [`cage/importcmd.py:477`](../../cage/importcmd.py#L477)

So a `--path` scoped import can **never** match the VS Code store's
`chatSessions/*.jsonl`, no matter how the files are staged.

- **The parser is fine.** `_parse_copilot_any` dispatches on `f.parent.name ==
  "chatSessions"` and handles **both** shapes ([`importcmd.py:359`](../../cage/importcmd.py#L359)).
  Only the glob is wrong.
- **Claude's equivalent branch works** — it uses `**/*.jsonl`
  ([`importcmd.py:312`](../../cage/importcmd.py#L312)).
- The non-`--path` route is unaffected: it reads `paths.agent_log_sources`, which carries
  the right per-store globs.

## Symptom

A misleading `matched 0 files — capture is off for this agent` **while the files exist
and are parseable**. Nothing errors; the import simply reports nothing to import.

## Why the scripted legs never saw it

The scripted legs never scope copilot by `--path`. The bug is only reachable when a run
deliberately points copilot at one workspace's store — which is exactly what a
per-workspace lab cell must do.

## Workaround used in leg D (and the correct mechanism)

A `[sources.copilot]` override in the workspace `cage.toml`:

```toml
[sources.copilot]
replace = true
paths = ["~/Library/Application Support/Code/User/workspaceStorage/<workspace-id>"]
glob = "chatSessions/*.jsonl"
surface = "vscode"
```

**Renaming the files to `events.jsonl` would *not* have been a valid workaround** — it
would have satisfied the glob but stamped `surface = cli`, corrupting the very check D3
exists to make.

## Suggested fix (not built)

Give the `--path` branch the same treatment as claude's: a glob that reaches both stores
(the parser already dispatches per file), or resolve `--path` through the same per-store
glob table the registry uses. Whatever the shape, the accompanying test should assert a
`--path` import over a `chatSessions/` tree returns rows with `surface` **unstamped by the
CLI default**.

## Status history

- **2026-08-01** — filed OPEN from leg D cell D3. Confirmed in source, not just observed.
