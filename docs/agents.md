# Cage with your coding agent

Cage meters whatever speaks the OpenAI/Anthropic wire format and reads the ledger
over MCP. One ledger contract, four surfaces — nothing about an agent is hardcoded.

```bash
cd your-project
cage setup            # guided wizard: pick ONE agent, then y/n each step
                      #   (global skill · scaffold .cage/ · wire hooks+MCP · graphify)
# non-interactive equivalent:
cage setup --claude   # all steps for claude; --no-skill/--no-project/--no-graphify to trim
```

`cage setup` is the front door — interactive in a terminal, flag-driven otherwise.
It wires only the agent you name; nothing is installed for an agent by default.
Global-asset paths are env-overridable (`CAGE_VSCODE_USER` for Copilot's prompt dir,
`KIRO_HOME` for Kiro).

The granular commands underneath, if you want them directly:

```bash
cage setup                     # scaffold .cage/ only (no agent touched)
cage adopt [--claude]         # init + graphify shim; agent wiring opt-in via --<agent>
cage hooks install --claude   # wire just one agent's metering hooks + MCP (errors if no agent)
```

Agent wiring is **opt-in everywhere**: `cage adopt`/`cage hooks install` with no
`--<agent>` flag wire nothing and tell you to pick one. All steps are idempotent.

## Claude Code

- **Meter (proxy-free, reliable default):** `cage hooks install --claude` wires a
  **SessionStart** hook that first **backfills the previous session** —
  `cage import --agent claude --project .` parses the transcript Claude Code always writes to
  disk — and then prints the one-line spend banner (`cage hook-session-start`), so the
  banner reflects the just-backfilled spend. This is the reliable trigger: the
  transcript is on disk no matter how the session ended.
- A **SessionEnd** hook (`cage hook-session-end`) is also wired, but it is
  *best-effort* — Claude Code only fires it on certain clean terminations (`/exit`,
  logout, clear), never on a killed terminal, crash, or idle session. It is additive,
  not the primary path; running both is safe because `cage import` dedupes by call id.
- **Read:** the `cage` MCP server is wired in `.mcp.json`; the `/cage` skill answers
  "what did this cost / what saved money" from the ledger.
- **Alt meter (real-time, for budget blocking):** `export ANTHROPIC_BASE_URL=$(cage data proxy)`.
- **Alt meter (no hooks):** `cage import --agent claude` parses the transcripts Claude Code
  already writes to `~/.claude/projects/` — same rows the SessionEnd hook would
  produce, off the request path. `--project <dir>` scopes it to one repo, `--since 7d`
  to recent sessions. Idempotent (deduped on the per-turn id), so it's safe on a cron.

## Codex

- **Meter (reliable default):** Codex CLI reads a project `.codex/hooks.json` using the
  same hook schema as Claude Code, so `cage hooks install --codex` wires a
  **SessionStart** backfill — `cage import --agent codex --since 7d` parses the rollouts
  Codex always writes to `~/.codex/sessions`, on the next start. The window only bounds
  the scan (import dedupes by id). Symmetric with Claude's SessionStart-backfill.
- **Meter (alt):** `cage data meter -- codex exec …` runs Codex under the proxy (sets
  `OPENAI_BASE_URL`) for real-time/budget-blocking capture.
- **Read:** `cage hooks install --codex` registers `[mcp_servers.cage]` in
  `~/.codex/config.toml`; the `/cage` skill is installed to `~/.codex/skills/`.

## GitHub Copilot

- **Meter (proxy, reliable path):** Copilot writes no usage transcript, so the proxy
  is its reliable capture path — point Copilot's model endpoint at `cage data proxy` where
  your
  setup allows a custom base URL.
- **Read:** `cage hooks install --copilot` adds the `cage` MCP server to
  `.vscode/mcp.json` and a Cage pointer to `.github/copilot-instructions.md`.

## Kiro

- **Meter (proxy, reliable path):** Kiro writes no usage transcript, so the proxy is
  its reliable capture path (`cage data proxy` / `cage data meter -- <cmd>`), or a Kiro agent
  hook that shells `cage report` on save.
- **Read:** `cage hooks install --kiro` adds the `cage` MCP server to
  `.kiro/settings/mcp.json` and a steering doc at `.kiro/steering/cage.md`.

## Restricted orgs (no hooks / no MCP)

Some orgs block Claude Code hooks and/or MCP servers by policy. Cage still works —
the two questions decouple:

- **Hooks blocked (can't capture):** meter off the request path instead. Either
  `cage import --agent claude` (pull the on-disk transcripts after the fact — cron/CI/login
  script friendly, idempotent) or `cage data proxy` (wire-level: point
  `ANTHROPIC_BASE_URL` at it and record `usage` live). Either path fills the same
  ledger the SessionEnd hook would.
- **MCP blocked (can't read in-agent):** this costs only the *agent-facing* read
  surface (the `/cage` skill / MCP tools). The `cage` CLI reads the ledger directly,
  so `cage report` / `attrib` / `matrix` / `budget` are unaffected.

## The universal fallbacks

- **`cage data proxy --port 8788`** — a thin metering reverse-proxy. Point any agent's
  base URL at it; it forwards verbatim and records `usage`. Fail-open: a metering
  error never changes the bytes the client receives.
- **`cage mcp`** — the read surface for any MCP-capable agent.
- **`cage.meter()` / `cage.record_call()`** — the library adapter for code you own
  (this is how Orff meters; see the Anton integration).
- **`cage.record_human(task=…, minutes=…|usd=…|task_type=…)`** — the Tier-1 human
  alternative. Orff's `LLMGateway` calls it fail-open when it closes a task, so the
  ledger carries *agent vs human* ($ and time saved) alongside tool-vs-tool savings.

## Debugging capture (`CAGE_DEBUG`)

Capture is fail-open by design: a hook that doesn't fire, a `.cage` cwd-guard skip, or
a parser that raises all fail *silently*. When spend isn't landing and you can't tell
why, turn on the observability layer — strictly observational ($0, metadata-only), it
**never changes capture** (the ledger is byte-identical with it on or off):

```bash
export CAGE_DEBUG=1          # or set [debug] enabled = true in .cage/policy.toml
# …run your agent / commit…
cage debug --tail 50         # recent capture events (entries, results, skips, errors)
cage doctor                  # the `trace` row: per-agent last hook fired + last error
```

Full walkthrough — the three failure modes (hook fires? guards pass? log parses?), how
to read the events, and what it never logs — in
[debugging-capture.md](debugging-capture.md).

## Tool-savings receipts — two integration strategies

A *savings receipt* is what makes `cage insights attrib` / `cage insights matrix` / `cage insights roi` show
real with/without numbers (token contract in
[archive/v0.3-tool-receipts-graphify-fux.handoff.md](archive/v0.3-tool-receipts-graphify-fux.handoff.md)).
How a tool files one depends on who owns it:

- **In-tool shim (tools you own) — e.g. fux.** fux carries a ~15-line fail-open
  `cage_receipt.py` and emits its own `tool="fux"` receipt at the hook-recall
  assembly point (it knows the exact injected payload + the rules it selected, so
  this is the most accurate). cage stays an *optional* dependency: the shim
  `try/except`-imports cage and no-ops if it's absent, so fux runs byte-identically
  without cage.

- **External adapter (third-party tools you can't edit) — e.g. graphify.**
  `cage data graphify -- graphify query "…"` runs the unmodified `graphify` command,
  passes its **stdout/stderr/exit through unchanged**, and on the side parses the
  answer for the `source_file`s it cites — filing one `tool="graphify"` receipt
  (`actual` = answer tokens; `raw_alternative` = the whole *touched, present-on-disk*
  source files, deduped, never the repo). A metering error never alters graphify's
  result; if no source file resolves it files **nothing** (unmeasurable ≠ zero).
  graphify is never edited. This is the same "meter what you observe" family as
  `cage data meter -- <cmd>` and `cage import --agent codex`. Alias
  `graphify='cage data graphify -- graphify'` to make it transparent.

  > Token receipts carry their model price via the task's calls, so `attrib`/`matrix`
  > show real dollars. `roi` prices a receipt only when it links a specific `call`
  > id; both emitters default to `call=""`, so `roi` lists the tools but shows $0
  > saved unless a call is linked — honest, per the receipt contract.
