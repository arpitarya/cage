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

`cage setup` scaffolds `.cage/`, writes each agent's **MCP config**, and installs the
`bin/graphify` interceptor twin pair. **By default it writes no hooks and no
skills** — capture is pull-based and needs neither. Re-running heals *and* switches
off: legacy absolute paths migrate, and every cage hook/skill artifact is removed.
Foreign (non-cage) artifacts are never touched; every write is idempotent and
byte-identical.

## The optional layers (`cage query agent-layers`)

```bash
cage setup --all --hooks     # + L1: agent identity at capture, auto task-close, budget blocking
cage setup --all --skills    # + L3: seven skills, one source, three agents
cage setup --all             # neither — and removes both if they were there
```

- **Both are two-way.** A plain `cage setup` is the off-switch, not a no-op.
- **Neither can move a number.** `tests/test_floor.py` installs every layer over a
  fixed ledger and asserts every derived view byte-identical, then strips them and
  asserts again.
- **Hooks are CLI-only** — they do not fire under a VS Code extension. `cage setup
  --status` prints that limit, and each agent's gaps, alongside what is wired.

## What gets written (portable by design)

- **Committed wiring** (`.mcp.json` for Claude Code, `.vscode/mcp.json` for Copilot)
  references the committed shim `.cage/bin/cage-run` — identical bytes on every
  machine, resolves cage at runtime, fails open to exit 0. **Never an absolute path.**
- **Kiro** (`.kiro/settings/mcp.json`) is committed too, by a different route: it
  resolves neither the shim nor a variable, so it carries **no path at all** —
  `python3 -m cage mcp`. Byte-identical everywhere.
- **The price of that, checked not assumed**: it depends on *which* `python3` resolves.
  `cage doctor`'s `kiro-mcp` check asks that interpreter to import cage and names the
  fix if it can't. On Windows `python3` is often absent — `cage setup --python-launcher`
  writes the `py -3` form for that machine.

## Capture works with no hooks

Cage installs none. Capture is pull-based and global — the same path under a CLI
session and a VS Code extension (where hooks would not fire at all):

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
