# Portable wiring — the `cage-run` shim

**Status:** design of record, implemented in v0.20.0 — this document describes
live behavior (`cage/runshim.py` + the four wire modules; each per-host
mechanism below was verified against the host's docs during implementation and
is also recorded in that wire module's docstring).

*Not to be confused with the `bin/graphify` interceptor shim — that one
intercepts a tool to emit savings receipts. This document is about how cage's
own hook/MCP wiring stays machine-independent.*

## The problem

`cage setup` must give every hook and MCP entry a way to find the `cage`
executable. Two facts collide:

1. **A bare `cage` is unreliable.** GUI-launched agents (any VS Code
   extension, the Kiro IDE) don't inherit your shell `PATH`, so `cage` alone
   often fails there. That's why setup historically wrote the **absolute
   resolved path** (`/Users/you/.local/bin/cage`).
2. **Several wired files are committed to git.** `.mcp.json`,
   `.vscode/mcp.json`, `.kiro/hooks/*.hook`, and project hook configs travel
   with the repo. An absolute path that's correct on the machine that ran
   setup is wrong on every teammate's clone — hooks break silently for the
   whole team.

Absolute paths are right for one machine and wrong for a team; bare names are
right for a shell and wrong for an extension. The fix is to stop resolving at
*setup time* and resolve at *run time* instead.

## The design: a committed runtime-resolving launcher

`cage setup` writes a tiny launcher into the repo:

```
.cage/bin/cage-run        # POSIX sh — identical bytes on every machine
.cage/bin/cage-run.cmd    # Windows twin (where cage / Scripts\ / py -m cage)
```

Every **committed** wired entry references the shim instead of a binary path.
The shim resolves cage fresh on each invocation, on whatever machine it runs:

1. `command -v cage` — the PATH, when there is one
2. Well-known install locations — `~/.local/bin/cage`, pipx, an active
   `$VIRTUAL_ENV/bin/cage` (Windows: `where cage`, `Scripts\cage.exe`)
3. `python3 -m cage` (Windows: `py -m cage`) if the package is importable
4. **Nothing found → exit 0, silently.**

Before step 1, the shim honors one runtime override: `CAGE_RUN_PYTHON=1` in the
invoking environment skips the exe probe entirely and goes straight to step 3
(then exit 0) — the no-rewire escape hatch for endpoints that block unknown
executables (see [restricted-environments.md](restricted-environments.md)).

Step 4 is the contract that makes the shim safe to commit: a teammate who has
never installed cage clones the repo and gets fully working agents — no error
noise in their hooks, no broken MCP server, simply no capture on their
machine. This is cage's fail-open law extended to wiring. All arguments pass
through unchanged (`cage-run import` ⇒ `cage import`).

## What references the shim vs what stays absolute

| Wired file | Committed? | References |
|---|---|---|
| `.vscode/mcp.json` | yes | `${workspaceFolder}/.cage/bin/cage-run` — documented VS Code variable substitution (stdio-server cwd also documented as the workspace folder) |
| Claude project hooks (`.claude/settings.json`) | yes | `"$CLAUDE_PROJECT_DIR/.cage/bin/cage-run"` — documented hook path placeholder; hook cwd is only "Claude Code's working directory", so the placeholder is the reliable form |
| `.mcp.json` | yes | `${CLAUDE_PROJECT_DIR:-.}/.cage/bin/cage-run` — documented env expansion; the `:-.` default is a documented requirement (the var is set in the server's env, not the config parser's) |
| `.codex/hooks.json` | yes | self-locating one-liner: `git rev-parse --show-toplevel` → exec the shim → exit 0 if either is missing. Codex documents hook cwd as the *session* cwd (possibly a subdirectory) and its docs recommend git-root resolution |
| `.kiro/hooks/*.kiro.hook` | yes | the same self-locating one-liner — Kiro documents neither the runCommand cwd nor any variable, and has a tracked record of resolving relative paths against the wrong base |
| `.kiro/settings/mcp.json` | yes — **the ONE exception** | absolute path, by necessity: Kiro spawns MCP servers from its *install directory* (kirodotdev/Kiro #6525) and supports no variable substitution in `command` (open FR #5659). A relative/variable form provably breaks, so it stays absolute — **add it to your `.gitignore`** (`cage doctor` prints this advice) |
| `~/.copilot/hooks/cage.json` | no (user-level) | absolute path — per-machine by nature, absolute is the robust choice |
| `~/.codex/config.toml` MCP | no (user-level) | absolute path |
| `.git/hooks/*` | no (never cloned) | absolute path — every machine runs its own setup |

The rule: **anything git carries contains no machine-specific path** —
regression-tested by grepping setup's written files
(`tests/test_portable_wiring.py`) — with the one documented Kiro-MCP exception
above, which is gitignore-advised rather than silently shipped broken.
Anything that never leaves the machine may — and should — use the most robust
local reference.

## Python-launcher mode (opt-in, restricted endpoints)

`cage setup --python-launcher` persists `[wiring] python_launcher = true` in the
project policy and switches the *whole* wiring story to interpreter-only
resolution: the shim pair is rewritten to a variant that runs
`python3 -m cage` / `py -3 -m cage` directly (no PATH probe, no install-dir
probe, nothing exe-shaped in the file), and every user-level file in the table
above that would carry a resolved absolute cage path carries an interpreter
command instead (`python3 -m cage import …`, MCP `command = "python3"`,
`args = ["-m", "cage", "mcp"]`). Committed files are untouched — they reference
the shim either way; **the shim is the mode**.

The mode is project policy, so plain re-runs of `cage setup` preserve it
(byte-identical), and setting the key to `false` + re-running setup reverts
cleanly. The fail-open contract is identical in both modes. `cage doctor`'s
portability check names the active mode (`mode: standard` /
`mode: python-launcher`) and warns when the policy and the on-disk shim
disagree. Full rationale and the other restricted-environment tiers:
[restricted-environments.md](restricted-environments.md);
`cage query restricted-env`.

## Migration and diagnostics

- **Migration:** re-running `cage setup` detects legacy absolute (or bare)
  cage entries in committed files and rewrites them to the shim reference,
  printing a count of what it migrated. A cage command's own flags survive
  the rewrite (only the executable reference changes); foreign, non-cage
  hooks are never touched. Setup remains idempotent: a second run is
  byte-identical.
- **`cage doctor`** checks portability: it flags a committed wired file
  containing a machine-specific absolute path ("teammates' clones will have
  broken wiring — re-run `cage setup`"), a missing shim or lost execute bit,
  and verifies the shim actually resolves on this machine.
- **Cleanup safety:** `.cage/bin/` is outside the state-cleanup allowlist by
  construction — auto-cleanup can never remove the shim.

## FAQ

**Why not tell every teammate to re-run `cage setup` after cloning?**
It works, but it fails silently until someone notices missing rows. The shim
makes a fresh clone work (or degrade cleanly) with zero action. Re-running
setup is still recommended — it wires the *user-level* files and git hooks the
clone can't carry.

**Why not an env var like `$CAGE_BIN`?**
GUI-launched agents don't inherit your shell environment any more than they
inherit PATH — the indirection has to live in a file the host can execute.

**Why exit 0 when cage is missing, instead of warning?**
A hook's stdout/stderr goes nowhere useful, and a non-zero exit can degrade
the agent session itself. Silence is the only safe behavior on the hook path;
`cage doctor` is where absence gets diagnosed loudly.

**Does this change capture behavior?**
No. Hooks remain an optional real-time add-on (CLI clients only); `cage
import`/`cage export` stay the universal path. The shim only changes *how
wired commands find cage*, not what they do.

**What about the ledger numbers?**
Untouched. The shim is wiring, not data — determinism, method tags, and the
substrate contract are unaffected.
