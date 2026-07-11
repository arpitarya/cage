# CSV output — column contracts (plan §3.9)

CSV is cage's one-way **reporting** format: flat, for spreadsheets/BI, never an
import source. The re-importable fleet bundle (`cage export --study`) stays
jsonl — the two are never blurred. `cage query csv-output` explains the design;
this file pins the per-view column contracts.

**Laws** (tested in `tests/test_csv.py`):

- One shared data structure per view feeds the text table AND the CSV
  (`render_csv` lives beside each `render_*` and consumes the same
  `summarize()`/`attribute()`/`rollup()` payload) — same numbers by
  construction, no view computes twice.
- stdlib `csv` module; RFC-4180 quoting; **LF line endings pinned on every OS**
  (stdout renderers use `lineterminator="\n"`, file writes pass `newline=""`).
  Same ledger + same policy ⇒ byte-identical CSV.
- **method/match tags are columns, never dropped** — a spreadsheet must be able
  to tell `measured` from `estimated`. Refusals (min-n), observational caveats,
  and UNPRICED counts survive as rows/columns.
- Cell canon (`csvout.cell`): bool → `true`/`false` · float → trimmed 6-decimal
  fixed point · list → `;`-joined · dict → sorted compact JSON · `None` → empty.
- Numbers are raw (no `$`, no thousands separators) — the text view formats,
  the CSV carries values.

Usage: bare `--csv` streams to stdout (pipe-friendly; confirmations go to
stderr); `--csv <path>` writes the file.

## Read views (`--csv`)

### `cage report --csv [--by DIM]`

One row per group (spend-descending, like the text table) + a `TOTAL` row.

```
<dim>, calls, tokens_in, tokens_out, cached_in, cost_usd,
[saved_usd, net_usd,]            # only on savings dims (task / agent)
unpriced_calls, unpriced_tokens, method
```

`method` is `measured` (recorded tokens repriced at derive time — see
`cage query repricing`). The `unpriced_*` pair is the per-group share of the
text view's ⚠ UNPRICED warning — an understated total stays visible.

### `cage attrib --csv`

```
tool, saved_tokens, saved_usd, method, confidence     (+ TOTAL row)
```

### `cage roi --csv`

```
tool, receipts, saved_usd, own_cost_usd, net_usd, added_latency_ms, method
```

`method` = the least-trusted receipt behind the row (worst-case provenance,
same rule as attrib).

### `cage compare --csv`

One flat table typed by a leading `kind` column:

```
kind, <the --by keys: stack[, scope][, label]>, baseline, n,
median_tokens, iqr_lo_tokens, iqr_hi_tokens, median_usd, iqr_lo_usd, iqr_hi_usd,
d_median_tokens, d_median_usd, method, note
```

- `group` — measured group totals; a below-min-n group keeps its refusal in
  `note` and **no numbers**.
- `delta` — `estimated`, the observational caveat verbatim in `note`.
- `unpriced` — mirrors the text ⚠ line in `note`, when it renders.

### `cage study report --csv`

```
kind, machine, phase, days, gap_days, agents, n,
median_tokens, q1_tokens, q3_tokens, median_usd, q1_usd, q3_usd,
d_tokens_per_day, d_usd_per_day, method, note
```

- `coverage` — one row per machine × phase (gap days / agents `;`-joined);
  a phase with no rows carries the MISSING note.
- `unphased` — the excluded-call count.
- `delta` — paired-by-machine, `estimated`, caveat in `note`; refused ⇒ reason
  in `note`, no numbers.
- `pooled` — per compared phase (n = machine-days, measured dists).
- `unpriced` — the ⚠ line, when it renders.

### `cage calibration --csv`

```
kind, task, est_tokens, actual_tokens, ratio, in_band, n,
median_ratio, q1_ratio, q3_ratio, hit_rate, hits,
skipped_open, skipped_zero_actual, skipped_no_band, method
```

`task` rows per scored task; one `summary` row (the skip counts stay visible).
Both `measured`.

### `cage calibration --human --csv`

```
kind, task, attested_minutes, derived_minutes, ratio, n,
median_ratio, q1_ratio, q3_ratio, cap_minutes, method, note
```

Refused (below min-n) ⇒ the `summary` row carries the reason in `note` and no
distribution.

### `cage human --csv`

```
kind, agent, tasks, human_usd, agent_usd, saved_usd, saved_minutes, confidence,
sessions, calls, attention_minutes, method, note
```

`attested` rows (the receipt-priced table + TOTAL) vs `derived` rows (the
turn-gap block, `attention_minutes`) — separate kinds, never blended, exactly
like the text view's two sections; derived rows carry the
`derived (turn-gaps, capped)` label in `note`. Both `estimated`.

### `cage trend --csv`

```
kind, bucket, tasks, agent_usd, human_usd, saved_usd, saved_minutes,
attention_minutes, method, note
```

`attested` vs `derived` rows per bucket, same separation law as `cage human`.

## Raw rows (`cage export --csv KIND`)

`cage export --csv calls|receipts|tasks [--since …] [-o FILE]` — flattened
ledger rows for pivot tables, exactly as stored (tasks stay raw append-only
updates, not the last-write-wins merge). Same PII surface as the ledger:
counts and ids, never content. Honors import-before-export (`--no-import` to
snapshot). `--format csv` is the legacy spelling of `--csv calls`.
`--agent`/`--project` filter call rows only (typed error on other kinds).

Column contracts (`exportcmd.RAW_CSV_FIELDS`): `calls` and `receipts` are the
schema tuples (`CALL_FIELDS`/`RECEIPT_FIELDS`) plus the additive fleet
`machine` stamp; `tasks` pins identity + outcome + label + the recorded
estimate fields + the PII-guarded git snapshot:

```
calls:    id, ts, session, task, agent, route, provider, model, tokens_in,
          tokens_out, cached_in, est_cost_usd, latency_ms, ok, retries, scope,
          project, gap_ms, machine
receipts: id, ts, call, task, tool, unit, raw_alternative, actual, saved,
          method, confidence, meta, scope, machine
tasks:    id, ts, type, outcome, label, agents, est_tokens, est_usd, est_n,
          est_tokens_q1, est_tokens_q3, commit, branch, files_changed,
          insertions, deletions, dirs, machine
```

## MCP parity

The read server (`cage mcp`) exposes `format: "csv"` on `cage_report`,
`cage_attrib`, and `cage_roi` — the same `render_csv` output the CLI emits, so
an extension-hosted agent with no shell can still produce the CSV content.

The one-paragraph architecture summary lives in the repo `CLAUDE.md`
("CSV output (plan §3.9)" bullet); this file is the column-contract detail
behind it.
