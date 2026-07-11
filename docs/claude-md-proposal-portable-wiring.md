# Proposed CLAUDE.md edits — portable wiring (v0.20.0, plan §5.3)

**Status: applied to CLAUDE.md on 2026-07-11** (edits 1–2 below; edit 3 was a
no-change note). Kept for the record of what changed and why.

## 1. Adapters & agents section — amend the wiring paragraph

In the **Wiring — one `<agent>wire.py` per agent** bullet, after the sentence
about each wire exposing `install`/`status`/…, insert:

```markdown
  **Committed wiring is portable (plan §5.3):** every project-committed wired
  file (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`,
  `.codex/hooks.json`, `.kiro/hooks/*.kiro.hook`) references the committed
  runtime-resolving shim `.cage/bin/cage-run` ([runshim.py](cage/runshim.py) —
  written by `agents.install`, identical bytes on every machine, resolution:
  PATH → ~/.local/bin/pipx/$VIRTUAL_ENV → `python3 -m cage` → exit 0 silently,
  fail-open) — **never** `paths.cage_bin()`'s absolute path. Per-host reference
  mechanism is documented in each wire module's docstring (Claude:
  `$CLAUDE_PROJECT_DIR` / `${CLAUDE_PROJECT_DIR:-.}`; VS Code:
  `${workspaceFolder}`; codex/kiro hooks: the `runshim.selflocating_command`
  git-root one-liner). User-level configs (~/.copilot/hooks, ~/.codex
  config.toml MCP, .git/hooks) stay absolute — per-machine by nature. The ONE
  exception: `.kiro/settings/mcp.json` stays absolute (Kiro spawns MCP servers
  from its install dir, no workspace variable) — gitignore-advised via doctor.
  Re-running setup migrates legacy absolute entries (idempotent, printed).
  `cage doctor` has a `portability` check; `cage query portable-wiring`
  explains the design. A new committed file must never embed a machine path —
  `tests/test_portable_wiring.py` greps for this and must stay green.
```

## 2. Dev section — test count

`just test` comment: `(496 passing)` → `(509 passing)`.

## 3. No other changes

The "Must-Know Rules" section needs no new rule: the invariant is enforced by
the regression grep test, and the fail-open law already covers the shim's
contract (this proposal's edit 1 records where it lives).
