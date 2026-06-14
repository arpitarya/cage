# Cage with your coding agent

Cage meters whatever speaks the OpenAI/Anthropic wire format and reads the ledger
over MCP. One ledger contract, four surfaces — nothing about an agent is hardcoded.

```bash
cage setup            # install a global /cage asset into every agent home (once):
                      #   claude/codex → skill · copilot → prompt · kiro → steering
cd your-project
cage init             # scaffold .cage/ (policy + gitignored ledger)
cage hooks install    # wire claude + codex + copilot + kiro (or pass --claude etc.)
```

`cage setup` is symmetric across all four agents (paths are env-overridable —
`CAGE_VSCODE_USER` for Copilot's prompt dir, `KIRO_HOME` for Kiro). The per-project
MCP/hook wiring is `cage hooks install`.

## Claude Code

- **Meter (proxy-free):** `cage hooks install --claude` adds a **SessionEnd** hook
  that parses the session transcript (which already records per-turn `usage`) and
  appends call rows. Off the request path; works on API and subscription alike.
  A **SessionStart** hook prints a one-line spend banner into context.
- **Read:** the `cage` MCP server is wired in `.mcp.json`; the `/cage` skill answers
  "what did this cost / what saved money" from the ledger.
- **Alt meter (real-time, for budget blocking):** `export ANTHROPIC_BASE_URL=$(cage proxy)`.

## Codex

- **Meter:** `cage meter -- codex exec …` runs Codex under the proxy (sets
  `OPENAI_BASE_URL`); or `cage import-codex ~/.codex/sessions` parses rollout logs
  after the fact (best-effort — Codex's schema shifts between versions).
- **Read:** `cage hooks install --codex` registers `[mcp_servers.cage]` in
  `~/.codex/config.toml`; the `/cage` skill is installed to `~/.codex/skills/`.

## GitHub Copilot

- **Meter:** the proxy — point Copilot's model endpoint at `cage proxy` where your
  setup allows a custom base URL.
- **Read:** `cage hooks install --copilot` adds the `cage` MCP server to
  `.vscode/mcp.json` and a Cage pointer to `.github/copilot-instructions.md`.

## Kiro

- **Meter:** the proxy (`cage proxy` / `cage meter -- <cmd>`), or a Kiro agent hook
  that shells `cage report` on save.
- **Read:** `cage hooks install --kiro` adds the `cage` MCP server to
  `.kiro/settings/mcp.json` and a steering doc at `.kiro/steering/cage.md`.

## The universal fallbacks

- **`cage proxy --port 8788`** — a thin metering reverse-proxy. Point any agent's
  base URL at it; it forwards verbatim and records `usage`. Fail-open: a metering
  error never changes the bytes the client receives.
- **`cage mcp`** — the read surface for any MCP-capable agent.
- **`cage.meter()` / `cage.record_call()`** — the library adapter for code you own
  (this is how Orff meters; see the Anton integration).
