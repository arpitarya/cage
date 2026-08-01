# Example — cage.toml + prices.toml

Cage's **policy** layer is now two files with opposite lifecycles (prices-toml
plan §3): `cage.toml` holds *your decisions* (budgets, pipeline order,
capture switches, routing) and is preserved on upgrade; `prices.toml` holds the
*vendor rate card* (`[prices]`, `[credits]`) and is replaced wholesale by
`cage prices sync`. The rule: **vendor facts move, routing decisions stay.** Both
are part of cage's three never-mixed number layers — contract (enums in code),
policy (these files), constants (reviewable code heuristics).

> **Filenames:** the config was `policy.toml` through v0.35 → `cage.toml`; prices
> then split into `prices.toml`. A legacy project with prices still inline in
> `cage.toml` is **still read** (fallback) and **migrated** on the next
> `cage setup` (money-neutral, idempotent). If both carry prices, `prices.toml`
> wins and `cage doctor` names the ignored in-`cage.toml` block. The resolved names
> live in one place each (`paths.Footprint.policy` / `paths.Footprint.prices`).
> `cage query prices-file` explains it.

The bundled `data/cage.toml` + `data/prices.toml` are read-only at runtime; a
project's live in `.cage/`. Writes are text surgery (managed blocks / `# cage:custom`
markers), never a whole-file rewrite: `cage prices set`/`sync` write `prices.toml`;
`alias`/`route-tool` write `cage.toml`. cage **never fetches a price** — pricing
research is build-time/user work.

### `.cage/prices.toml` — the vendor rate card

```toml
# Price-research provenance (drives the staleness nag + `cage prices sync`).
[meta]
prices_version = "2026-07-14"
prices_date    = "2026-07-14"

# Prices — a call prices only if (provider, model) is in the table.
# The transcript meter stamps provider="anthropic", so that key must carry Claude rows.
[prices.anthropic]
"claude-opus-5"   = { input = 15.0, output = 75.0 }   # $/million tokens
"claude-sonnet-5" = { input = 3.0,  output = 15.0 }
```

### `.cage/cage.toml` — your decisions

```toml
# Non-pricing provenance (drives `cage policy sync`).
[meta]
cage_version   = "0.36.0"
policy_version = "0.26.0"

# Alias — a ROUTING decision (describes your setup), so it stays here, not in
# prices.toml: it must survive a wholesale price sync. Family match absorbs
# prefixes/effort tiers.
[alias]
"claude-opus-5-20260101" = "anthropic/claude-opus-5"

# Pipeline order — attribution is marginal-by-fixed-order; this is the order.
[tools]
order = ["compress", "responsecache", "graphify", "fux"]

# Budgets — warn or block on exceed.
[budgets]
monthly_usd = 200
on_exceed = "warn"          # warn | block


# Capture switches — a consumer can pause metering without unwiring hooks.
[capture]
enabled = true
on_read = true
import_before_export = true

# State-dir maintenance — .cage/state/ only, a closed allowlist (never ledger/,
# so tool savings can't be touched). Deletion only ever happens via an explicit
# `cage data cleanup --apply`. The auto sweep (piggybacked on `cage import`) only
# ever warns on stderr, silent when nothing is eligible, never deletes:
# `enabled` gates that reminder outright (env CAGE_CLEANUP), `warn` silences the
# reminder text without disabling the gate (env CAGE_CLEANUP_WARN). Either way,
# a manually-typed `cage data cleanup` / `--apply` always runs. days: 30 → 90 in
# v0.37 (30 proved tighter than a real usage gap).
[cleanup]
enabled = true
warn = true
days = 90

# Import sources — add/replace log locations beyond the built-in registry.
# Additive: an absent [sources] = the built-in registry, byte-identical.
[sources.kiro]
paths   = ["~/.kiro/sessions"]   # a non-IDE Kiro store
surface = "cli"                  # cli|vscode|ide — restamps imported rows so the
                                 # non-IDE store isn't mislabelled `ide` (absent ⇒
                                 # the parser's own value stands, byte-identical)
path_globs = ["**/*.jsonl"]      # root-agnostic; `cage import --path` only (below)
```

### `glob` vs `path_globs` — two keys, two jobs

| key | anchoring | read by | absent ⇒ |
|---|---|---|---|
| `glob` | **anchored** to this entry's `path` | every normal import | the format's default pattern |
| `path_globs` | **root-agnostic** (`**/…`) | `cage import --path` / `--project` only | that agent's `--path` scans **nothing**, loudly |

- `--path` replaces the location with a directory *you* name, so an anchored pattern
  cannot work there — `*/chatSessions/*.jsonl` matches nothing when you point `--path`
  **at** a `chatSessions` directory. That is why this is a second key, not a reuse.
- Patterns live in `cage.toml`, never in Python. `cage setup` materializes the seed;
  refresh after an upgrade with `cage setup --sync-sources`.
- **No code fallback.** An unmaterialized project gets `⚠ <agent>: no path_globs
  declared … Run cage setup --sync-sources`, never a silent guess.
- `replace = true` replaces an agent's `path_globs` along with its `paths`/`glob` —
  same table, same entries, same semantics. Without it, extra entries are additive and
  their `path_globs` union in declaration order.
- Overlapping patterns never hand the same file over twice.
- Copilot's seed names **both** store shapes explicitly (`**/events.jsonl`,
  `**/chatSessions/*.jsonl`) rather than a blanket `**/*.jsonl`, so a foreign `.jsonl`
  under your `--path` is never matched — safe by construction, not by the accident of
  it parsing to zero rows.
- A custom tool (`[sources.<tool>]`) has no `path_globs`: `--path` never reaches one.

Edit prices in `prices.toml`, budgets/order/routing in `cage.toml`; repricing
is derive-time and retroactive, so fixing a price re-prices every historical row.
Full field list: `cage query prices-cli` / `cage query prices-file` and the bundled
policy's generated `[sources]` comment block.
