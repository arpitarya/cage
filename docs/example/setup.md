# Example — setup & wiring

cage targets the wire protocol, so the meter and read surface are universal and
each agent needs only thin wiring. Supported agents, always: **Claude Code ·
Copilot · Kiro**.

## One command

```bash
cage setup                  # wire the current project for every agent (idempotent)
cage setup --global         # create/point at the global ~/.cage ledger
cage setup --python-launcher # restricted endpoints: interpreter-only shim
```

`cage setup` writes hooks + MCP config + skill/steering pointers, plus the local
git commit hooks. Re-running migrates legacy absolute paths. Foreign (non-cage)
artifacts are never touched.

## What gets written (portable by design)

- **Committed wiring** (`.claude/settings.json`, `.mcp.json`, `.vscode/mcp.json`,
  `.kiro/hooks/*.kiro.hook`) references the committed shim `.cage/bin/cage-run` —
  identical bytes on every machine, resolves cage at runtime, fails open to exit 0.
  **Never an absolute path.**
- **User-level configs** (`~/.copilot/hooks`, `.git/hooks`) stay absolute — per
  machine by nature.

## Capture works with no hooks

Hooks are an optional real-time add-on that mostly don't fire under VS Code
extensions. The universal path needs none:

```bash
cage import                 # captures the whole stack, any agent, no project required
```

Hands-off automation is **your own** cron/schtasks line calling `cage import` — cage
installs no OS scheduler (ADR 0002). `cage data watch` is an optional foreground
loop you Ctrl-C.

## Check it

```bash
cage doctor --wiring        # per-agent verdict: fully / partially / not wired / needs-healing
cage query portable-wiring  # why the shim, not an absolute path
```
