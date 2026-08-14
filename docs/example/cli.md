# Example — CLI

cage's command-line surface. `cage --help` groups every subcommand; `cage query`
explains any calculation or concept live. Exit codes: `0` ok · `1` error · `2`
argparse usage · `130` interrupt.

## Read — everything derives from the ledger ($0)

```bash
cage report                 # spend so far (tokens by default; --usd for dollars)
cage insights attrib        # per-tool savings (marginal-by-fixed-order)
cage insights matrix        # tool × tool savings grid
cage insights budget        # spend against policy budgets
cage insights roi           # savings ÷ spend
cage task quality           # cost per successful task
cage report --project       # slice by working-dir (exact for Claude)
cage report --scope api     # monorepo top-level-dir slice
cage report --team          # merged refs/notes/cage-ledger (falls back to local)
cage report --csv           # same view as RFC-4180 CSV (one-way reporting)
```

## Capture — pull-based and global (no hook required)

```bash
cage import                 # sweep all agent logs into the resolved ledger
cage import --agent claude  # one agent only
cage import --since 7d      # only logs touched in the window
```

## Explain — no LLM, no network

```bash
cage query "how is roi calculated"     # a calculation (formulas interpolate live values)
cage query "how does cage work"        # a concept (data-flow / attribution / method-law …)
cage query --list                      # every topic
cage query --json                      # agent-as-user
```

## Manage

```bash
cage prices list            # project price table
cage prices unpriced        # models with no price row (⚠ understated totals)
cage prices set <provider>/<model> <in> <out>
cage prices alias <from> <to>
cage doctor                 # diagnose capture (never sweeps; --paths, --wiring, --bundle)
cage setup                  # wire the current project (idempotent)
```

**UNPRICED is loud, not silent:** a call whose model has no price row bills `$0`
and prints `⚠ N calls UNPRICED — totals understated` with a runnable fix line.
Repricing is derive-time — fixing the table re-prices history retroactively.
