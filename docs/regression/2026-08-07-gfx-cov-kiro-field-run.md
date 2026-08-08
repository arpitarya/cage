# 2026-08-07 — GFX-COV field run: the kiro-CLI graphify route, on real data

**Verdict: the kiro-CLI route works end to end on a real store, and its truncation guard
fires on real traffic.** 2 graphify invocations were present; 1 filed a receipt
(**3,545 tokens saved**), 1 was refused as truncated. Re-running filed nothing.

This closes **half** of OPEN-WORK **GFX-COV-FIELD**. The copilot **VS Code** half is
still open and needs a real Copilot chat — see *What this does not cover*.

- Ships with: v0.47.0 (GFX-COV), uncommitted in tree at the time of the run.
- Store probed: `~/Library/Application Support/kiro-cli/data.sqlite3`, kiro-cli 2.16.0.
- Shapes and the truncation marker: [research/2026-08-07-graphify-store-evidence.md](../research/2026-08-07-graphify-store-evidence.md).
- Carve-out: [ADR 0009](../adr/0009-kiro-cli-tool-run-bodies-read-transiently-never-persisted.md).

## Method

Two real `graphify` runs were issued through `kiro-cli chat` during the GFX-COV P0 gate
(0.09 + 0.12 credits) and left in the store. This run reads them back through the shipped
code path.

- The store was **copied first** and every read used `mode=ro&immutable=1`.
- Receipts were written to a **throwaway sandbox ledger**, never `~/.cage`. Verified after
  the run: the real global ledger holds **0** graphify receipts and its
  `savings/graphify/savings-2026-08.jsonl` still carries its 5 pre-existing rows,
  last written 2026-08-03.
- Detection ran with `workspace=""` — the machine-ledger scope. A *project*-scoped sweep
  from the sandbox correctly filed nothing, because the real conversations are keyed to
  `~/my_programs/cage` and not to the sandbox tree ([ADR 0006](../adr/0006-kiro-rows-are-machine-facts-not-project-facts.md)
  scoping, observed working rather than asserted).

## Result

| | |
|---|---|
| conversations carrying tool runs | 10 |
| tool runs total | 10 (8 `fs_read`, 2 `execute_bash`) |
| **graphify invocations detected** | **2** |
| filed a receipt | **1** |
| refused — stdout truncated | **1** |
| refused — non-zero exit | 0 |
| re-run: new receipts | **0** (idempotent) |

The filed receipt:

```
op=explain   saved=3545 tokens   raw_alternative=3620   actual=75
method=modeled   confidence=0.6   source_files=1
```

The two invocations and why they diverged:

| command | stdout | outcome |
|---|---|---|
| `graphify explain ledger` | 300 chars, complete | **filed** — 3,545 tokens saved |
| `graphify query "how does the ledger append rows"` | 6,039 chars, ends in kiro's marker | **refused** — truncated |

## What this establishes

- **The route is real, not just green in tests.** A receipt derived from an actual kiro-cli
  conversation, through `transcript.parse_kiro_cli_tool_runs` →
  `graphifytx.detect_and_file_kiro_cli` → `_file_query`, with the same counterfactual
  every other route uses.
- **The truncation guard fires on real traffic, not only on a fixture.** The refused run is
  an ordinary `graphify query` — not a contrived one — which is the point: this is the
  common shape, and refusing it is correct because a truncated stdout under-counts `actual`
  and would inflate the saving.
- **Idempotency holds on real data**, not just synthetic ids.
- **ADR 0006 scoping is observed**, not assumed: the project-scoped sweep excluded
  conversations belonging to another tree.

## The number that matters, and its limit

**Observed refusal rate: 1 of 2 (50%).**

**n = 2. Do not quote this as a rate.** It is enough to prove both branches execute on real
data and nothing more. The honest statement is *both outcomes occur in ordinary use*; the
proportion is unmeasured. ADR 0009's veto condition sets the threshold that would reopen
the design — **if the query route files on < 10% of observed invocations, report-read-only
may be the honest kiro answer** — and that judgement needs a real usage sample, not this
one.

The direction of the evidence is worth naming even so: the run that filed was
`graphify explain` (300 chars); the one that refused was an ordinary `graphify query`
(6,039 chars). If typical `query` output sits above kiro's ~2000-token cap, the query route
on kiro will be sparse by construction. That is a **hypothesis this run is too small to
test**, and it is exactly what the veto trigger exists to settle.

## What this does not cover

- **copilot VS Code — untested in the field.** No real graphify run has ever been observed
  in a Copilot chat. The route is built on structural evidence from 1,132 real
  `run_in_terminal` parts (every key it reads verified present), and its fixture is
  labelled **SHAPE-VERIFIED / CONTENT-SYNTHETIC** for that reason. One terminal
  `graphify query` inside a VS Code Copilot chat, then `cage import --rescan-graphify`,
  would close it — and would let the fixture be replaced with a sanitized real sample.
- **kiro IDE** — nothing to test. Its store persists no assistant output
  (26/26 empty completions when probed); it is a named gap, not a pending route.
- **`--rescan-graphify` against a real cursor-consumed session** — exercised in the suite,
  not on this machine's real ledger (that would have written to `~/.cage`).

## Reproducing

```bash
cp ~/Library/Application\ Support/kiro-cli/data.sqlite3 /tmp/field.db
python3 - <<'EOF'
from pathlib import Path
from cage import graphifytx, ledger
root = Path("/tmp/gfx-sandbox"); (root/".cage"/"ledger").mkdir(parents=True, exist_ok=True)
ids = {r.get("id") for r in ledger.receipts(root) if r.get("tool") == "graphify"}
print(graphifytx.detect_and_file_kiro_cli(root, Path("/tmp/field.db"), workspace="",
                                          existing_ids=ids))
EOF
```
