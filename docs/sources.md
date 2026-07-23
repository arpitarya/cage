# Configurable import paths — `[sources]` in `policy.toml`

Cage imports each agent's usage log from a **built-in registry** of per-OS
locations (`~/.claude/projects/**/*.jsonl`, Copilot's CLI + VS Code stores,
Kiro's token log). The `[sources]` table lets you
**add or replace** those locations — for a nonstandard install, a network home, a
side-by-side log copy, or a **custom tool** that writes an already-supported format.

Additive by construction: **an empty or absent `[sources]` is byte-identical to the
built-in registry** — capture is unchanged for everyone who doesn't use it. Sources
affect *capture only*; no derived view (report/attrib/matrix/…) changes, and cage's
determinism law is untouched.

## Schema

```toml
# Extend one of the three agents (claude · copilot · kiro):
[sources.claude]
paths = ["~/work/claude-logs", "$TEAM_SHARE/claude"]   # dirs (agent glob) or files

# A directory whose layout isn't the format's canonical glob → declare your own,
# and replace the agent's built-ins entirely (the rare clean override):
[sources.copilot]
paths   = ["/mnt/net/copilot/session-state"]
glob    = "usage-*.ndjson"     # optional; absent ⇒ the format's default glob
replace = true                 # built-in ~/.copilot/session-state is ignored

# Silence a never-installed agent's probe (replace + empty = disabled by policy):
[sources.kiro]
paths   = []
replace = true

# Per-path globs → the array-of-tables form (one [[…]] block per location):
[[sources.claude]]
path = "~/work/claude-logs"    # glob defaults to **/*.jsonl
[[sources.claude]]
path = "~/.myproxy/claude"
glob = "session-*.jsonl"       # this location only

# A custom tool — reuse a declared parser format; rows stamp agent = <name>:
[sources.myrouter]
paths  = ["~/.myrouter/usage"]
format = "claude"              # required: which parser to reuse
```

- **`paths`** — a list of directories (scanned with the format's canonical glob) or
  concrete files. `~` and `$VAR` expand. A **glob-shaped entry** (`*`, `?`, `[`) in a
  `path` is rejected — **put the pattern in `glob = `** and list only concrete files
  or directories.
- **`glob`** — *optional* filename pattern for the directories in this table. Absent
  ⇒ the format's canonical glob (`**/*.jsonl` for claude, `*/events.jsonl` for
  copilot, …). An **empty `glob = ""` is an error** (drop the key to use the default —
  never a silent fallback). Ignored for a file source (Kiro's token log). This is the
  one capability the built-in registry can't express: a tool that writes
  `usage-*.ndjson` instead of the canonical shape.
- **`[[sources.<x>]]`** — the **array-of-tables** form: each `{path, glob?}` block is
  one location with its own optional glob (vs. the table form's one `glob` for every
  `path`). Additive only (no `replace`). TOML makes `[sources.x]` and `[[sources.x]]`
  mutually exclusive per key, so pick one shape per agent — but **different agents may
  use different shapes in the same file**. A custom tool in array form carries
  `format` on each entry (there is no table level to hold one).
- **`replace`** — drop that agent's built-in candidates first (agent tables only).
  With empty `paths`, the agent is **disabled by policy** (a legitimate way to quiet
  a never-installed agent's probe noise). This same stanza is the **opt-out for the
  capture-health warning**: an agent you don't use, declared
  `[sources.<agent>] replace = true, paths = []`, has no sources at all, so cage's
  "installed but capturing nothing" ⚠ (docs/debugging-capture.md) stays silent for it.
- **`format`** — required for a **custom tool** (any table name that is *not* one of
  the three agents). Must be `claude|copilot|kiro` — the parser to reuse. New
  log *formats* are out of scope: a custom source declares which existing parser
  reads it. Rows import with `agent = <table name>`, so `cage report`/`cage insights
  attrib` split the tool out naturally. The three agent names are **reserved** — 
  `[sources.claude]` is the claude agent table, not a custom tool.

## Precedence

**env home override > policy `[sources]` > built-in registry** — resolved in one
place (`paths.resolve_log_sources`). An env override (`CLAUDE_CONFIG_DIR`,
`COPILOT_HOME`, `KIRO_HOME`, …) redirects a built-in home and tags its
candidate `env`; policy paths add `policy` candidates; a policy path equal to a
built-in path is deduped to the built-in tag.

## Verify it

`cage doctor --paths` shows every candidate with its **glob** and a **provenance
column** (`built-in | env | policy`), custom-tool sections, a `disabled by policy` label,
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

## `policy sync` never touches it — and the visible commented block

`[sources]` is entirely user-owned — the bundled `policy.toml` ships **no active
`[sources]` table** — so `cage policy sync` never adds, updates, or orphan-warns it.

The bundle *does* ship the built-in defaults as a **generated comment block**
(between `# cage:sources-start` / `# cage:sources-end` in `policy.toml`), so you can
see the paths, globs, redirect env vars, and per-OS locations in the file you
configure — without reading Python. Because every line is a comment, the claim above
still holds: `tomllib` sees no `sources` key, capture resolves the built-ins
byte-for-byte, and `policy sync` has nothing to touch. **The defaults live in code
(`cage/paths.py`) and upgrade with the package** (`pip install -U`) — the block is
documentation, regenerated by `tools/docgen` and drift-gated in CI, never a config
you edit. Uncommenting a block into a real `[sources.<agent>]` table is an **explicit
pin**: it shadows the built-in for that project and is then, correctly, never synced.

## Scope

**Out of scope:** new log formats or parser changes; per-source prices/rates;
remote/network *fetch* (paths are local filesystem); auto-discovery beyond the
declared paths.

See also: [debugging-capture.md](debugging-capture.md), [agents.md](agents.md),
`cage query capture`.
