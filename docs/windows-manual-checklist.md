# Windows manual capture checklist — for a Windows fleet participant

Cage on Windows is **CI-tested, not yet field-validated** (macOS is; see the
README platform note). This is the Part-C-style capture matrix from
`docs/full-test-plan-sibling-repo.md`, distilled for one person on one Windows
laptop. Running it upgrades the honest wording — and your `cage doctor --bundle`
is the evidence either way.

Work from a fresh test repo (e.g. `C:\dev\cage-testbed`), PowerShell or cmd.
Prefix verification runs with `set CAGE_DEBUG=1` (cmd) / `$env:CAGE_DEBUG=1`
(PowerShell) so misses leave `debug.log` lines.

```bat
pip install cage-flux
cd C:\dev\cage-testbed
git init . && echo hello > README.md && git add -A && git commit -m init
cage setup
cage setup --all
cage doctor
cage doctor --paths     :: every candidate log location on THIS machine, with why-lines
```

## Where the agent logs should be on Windows

| Agent × surface | Expected log location | Status |
|---|---|---|
| Claude Code (CLI + VS Code ext) | `%USERPROFILE%\.claude\projects\<slug>\*.jsonl` | CI-tested format; location assumed same as POSIX |
| Codex (CLI + VS Code ext) | `%USERPROFILE%\.codex\sessions\YYYY\MM\DD\rollout-*.jsonl` | CI-tested format; location assumed same as POSIX |
| Copilot CLI | `%USERPROFILE%\.copilot\session-state\<id>\events.jsonl` | CI-tested format; location assumed same as POSIX |
| Copilot VS Code ext | `%APPDATA%\Code\User\workspaceStorage\<hash>\chatSessions\<session>.jsonl` | documented VS Code location; CI-tested |
| Kiro IDE | `%APPDATA%\Kiro\User\globalStorage\kiro.kiroagent\dev_data\tokens_generated.jsonl` | **UNVERIFIED-LAYOUT** — inferred from VS Code-family; please confirm |

Env overrides win everywhere: `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `COPILOT_HOME`,
`KIRO_DATA_DIR`, `CAGE_VSCODE_USER` (the VS Code *User* dir), `CAGE_HOME` (the
global ledger's home).

## Per-cell check (same for every agent you have installed)

1. Run one small real session in the test repo ("create a file that prints
   hello <agent>").
2. `cage report --by agent` — did rows land live (CLI hooks)? Note it.
3. `cage import` then `cage report --by agent` — the session's rows must appear
   with the right `agent`, non-zero tokens, and a priced USD (a $0 row usually
   means no `(provider, model)` price row — note the model id).
4. `cage import` again — totals must NOT change (idempotent re-import).
5. PII grep — nothing you typed may appear:
   `findstr /s /i "hello" .cage\ledger\*` → no prompt text, ever.
6. If a cell captured nothing: `cage doctor --paths` says which locations were
   probed and why each missed. If the real log lives somewhere else, that path
   is the finding — send it.

## Windows-specific checks

- [ ] `cage data watch` then Ctrl-C → exits (echo `%ERRORLEVEL%` — expected 130;
      record any deviation rather than forcing it).
- [ ] Hook files: after `cage setup`, open `.claude\settings.json` /
      `.codex\hooks.json` etc. — the cage command must be the **resolved**
      path, quoted if it contains spaces (`"C:\...\Scripts\cage.exe" import …`).
- [ ] Git hooks fire from Git-for-Windows: make a commit, then
      `cage authorship origin <sha>` shows a provenance row (`hook-post-commit` ran under
      git's bundled sh).
- [ ] The doctor scheduler hint prints a `schtasks /create …` example — and
      `schtasks /query | findstr cage` proves cage installed **nothing**.
- [ ] Console: `cage report` in a default cmd window must not crash on the
      ✔/·/⚠ glyphs (they may degrade to `?` on cp1252 — that's the designed
      fallback, not a bug).

## Send back

`cage doctor --bundle` → one redacted archive (counts-never-content; your
username is rendered as `~`). Attach it plus the table above with each cell
marked pass / fail / not-installed. If the Kiro row's real path differs from
the UNVERIFIED-LAYOUT guess, the corrected path is the single most valuable
line in the report.
