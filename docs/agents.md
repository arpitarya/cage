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

`cage adopt` is the one-command wrapper for a project: `cage init` + agent wiring
(all four surfaces by default — pass `--claude`/`--codex`/`--copilot`/`--kiro` for a
subset, or `--no-hooks` to skip wiring) + the graphify interceptor. Idempotent.

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
- **`cage.record_human(task=…, minutes=…|usd=…|task_type=…)`** — the Tier-1 human
  alternative. Orff's `LLMGateway` calls it fail-open when it closes a task, so the
  ledger carries *agent vs human* ($ and time saved) alongside tool-vs-tool savings.

## Tool-savings receipts — two integration strategies

A *savings receipt* is what makes `cage attrib` / `cage matrix` / `cage roi` show
real with/without numbers (token contract in
[tool-receipts.graphify-fux.handoff.md](tool-receipts.graphify-fux.handoff.md)).
How a tool files one depends on who owns it:

- **In-tool shim (tools you own) — e.g. fux.** fux carries a ~15-line fail-open
  `cage_receipt.py` and emits its own `tool="fux"` receipt at the hook-recall
  assembly point (it knows the exact injected payload + the rules it selected, so
  this is the most accurate). cage stays an *optional* dependency: the shim
  `try/except`-imports cage and no-ops if it's absent, so fux runs byte-identically
  without cage.

- **External adapter (third-party tools you can't edit) — e.g. graphify.**
  `cage graphify -- graphify query "…"` runs the unmodified `graphify` command,
  passes its **stdout/stderr/exit through unchanged**, and on the side parses the
  answer for the `source_file`s it cites — filing one `tool="graphify"` receipt
  (`actual` = answer tokens; `raw_alternative` = the whole *touched, present-on-disk*
  source files, deduped, never the repo). A metering error never alters graphify's
  result; if no source file resolves it files **nothing** (unmeasurable ≠ zero).
  graphify is never edited. This is the same "meter what you observe" family as
  `cage meter -- <cmd>` and `cage import-codex`. Alias
  `graphify='cage graphify -- graphify'` to make it transparent.

  > Token receipts carry their model price via the task's calls, so `attrib`/`matrix`
  > show real dollars. `roi` prices a receipt only when it links a specific `call`
  > id; both emitters default to `call=""`, so `roi` lists the tools but shows $0
  > saved unless a call is linked — honest, per the receipt contract.
