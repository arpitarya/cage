# Configurable import paths — `[sources]` in `policy.toml`

Cage imports each agent's usage log from a **built-in registry** of per-OS
locations (`~/.claude/projects/**/*.jsonl`, `~/.codex/sessions/**/rollout-*.jsonl`,
Copilot's CLI + VS Code stores, Kiro's token log). The `[sources]` table lets you
**add or replace** those locations — for a nonstandard install, a network home, a
side-by-side log copy, or a **custom tool** that writes an already-supported format.

Additive by construction: **an empty or absent `[sources]` is byte-identical to the
built-in registry** — capture is unchanged for everyone who doesn't use it. Sources
affect *capture only*; no derived view (report/attrib/matrix/…) changes, and cage's
determinism law is untouched.

## Schema

```toml
# Extend one of the four agents (claude · codex · copilot · kiro):
[sources.claude]
paths = ["~/work/claude-logs", "$TEAM_SHARE/claude"]   # dirs (agent glob) or files

# Replace an agent's built-ins entirely (the rare clean override):
[sources.codex]
paths   = ["/mnt/net/codex/sessions"]
replace = true                 # built-in ~/.codex/sessions is ignored

# Silence a never-installed agent's probe (replace + empty = disabled by policy):
[sources.kiro]
paths   = []
replace = true

# A custom tool — reuse a declared parser format; rows stamp agent = <name>:
[sources.myrouter]
paths  = ["~/.myrouter/usage"]
format = "claude"              # required: which parser to reuse
```

- **`paths`** — a list of directories (scanned with the format's canonical glob) or
  concrete files. `~` and `$VAR` expand. A **glob-shaped entry** (`*`, `?`, `[`) is
  rejected — list concrete paths.
- **`replace`** — drop that agent's built-in candidates first (agent tables only).
  With empty `paths`, the agent is **disabled by policy** (a legitimate way to quiet
  a never-installed agent's probe noise).
- **`format`** — required for a **custom tool** (any table name that is *not* one of
  the four agents). Must be `claude|codex|copilot|kiro` — the parser to reuse. New
  log *formats* are out of scope: a custom source declares which existing parser
  reads it. Rows import with `agent = <table name>`, so `cage report`/`cage insights
  attrib` split the tool out naturally. The four agent names are **reserved** — 
  `[sources.claude]` is the claude agent table, not a custom tool.

## Precedence

**env home override > policy `[sources]` > built-in registry** — resolved in one
place (`paths.resolve_log_sources`). An env override (`CLAUDE_CONFIG_DIR`,
`CODEX_HOME`, `COPILOT_HOME`, `KIRO_HOME`, …) redirects a built-in home and tags its
candidate `env`; policy paths add `policy` candidates; a policy path equal to a
built-in path is deduped to the built-in tag.

## Verify it

`cage doctor --paths` shows every candidate with a **provenance column**
(`built-in | env | policy`), custom-tool sections, a `disabled by policy` label,
overlap warnings (one path serving two agents), and — for a **committed project
policy** — a portability warning on any machine-absolute path. `cage query sources`
prints the schema plus your live resolved sources.

## Cursors, dedupe, fail-open

Policy paths sweep exactly like built-ins: the same incremental cursors (keyed on
each resolved file path), the same id-dedupe (`hooks.append_new`), the same
per-file fail-open (a missing/unreadable path is a debug-logged skip, never an
error). `cage data export`'s import-first sweep includes them; `CAGE_CAPTURE=0`
disables them with everything else.

## Portability & where to put it

A path in a **committed** project `policy.toml` is machine-specific — a teammate's
clone probes a directory that doesn't exist. `cage doctor --paths` warns on a
committed machine-absolute source path. Prefer:

- the **global** `~/.cage/policy.toml` (per-machine by nature — never warned), or
- a `~/…` / `$VAR/…` path (resolves per-machine — never warned).

## `policy sync` never touches it

`[sources]` is entirely user-owned — the bundled `policy.toml` ships none — so
`cage policy sync` never adds, updates, or orphan-warns it.

## Scope

**Out of scope:** new log formats or parser changes; per-source prices/rates;
remote/network *fetch* (paths are local filesystem); auto-discovery beyond the
declared paths.

See also: [debugging-capture.md](debugging-capture.md), [agents.md](agents.md),
`cage query capture`.
