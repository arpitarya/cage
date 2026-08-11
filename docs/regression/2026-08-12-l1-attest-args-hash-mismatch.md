# L1-FIELD Q3 — why the attested table reads ZERO (2026-08-12)

**Cause named: three producers write `args_hash`, and they do not agree on what they
hash.** `graphifymeter.run` — the shim/native interceptor route — hashed the **full
argv including `argv[0]`**, while `attest.record_tool` and the transcript route both
hash the **tail** (`argv[1:]`). On the shim path `argv[0]` is `$REAL`, the *absolute
resolved path* of the real binary, so the key was machine-specific and could never match
an attestation. The exact join was structurally unable to fire.

**Fixed for cause 1, forward-only.** [graphifymeter.py](../../cage/graphifymeter.py)
now hashes `cmd[1:]`. Two further causes remain and are **not** fixed — see §4.

Read with: [L1-FIELD](../open/L1-FIELD.md) Q3 · the read that raised it,
[adopt-cov](2026-08-11-adopt-cov-dev-ledger-read.md) §3 · FORMULAS §2.12.

---

## 1. What the tool printed (verbatim, `cage insights adoption --no-import`)

Identical before and after the fix — the fix is forward-only and rewrites nothing.

```
A · invocations — graphify usage breadcrumb (exact, agent-blind)

op       runs  receipt  unmeasurable  empty  non measured  error
-------  ----  -------  ------------  -----  ------------  -----
query       5        5             0      0             0      0
explain     2        2             0      0             0      0
—           1        0             0      0             1      0

route       runs  receipt  unmeasurable  empty  non measured  error
----------  ----  -------  ------------  -----  ------------  -----
transcript     6        6             0      0             0      0
shim           2        1             0      0             1      0

  by agent — attested by an L1 hook (stamped, not inferred)
agent  runs
-----  ----

B · per-agent attribution — savings rows joined to a call's agent

agent    tool      rows  joined via
-------  --------  ----  ----------
claude   graphify     6  session
copilot  graphify     1  session

· agent breakdown: attested for CLI sessions only — hooks do not fire under a VS Code extension, so a VS Code session leaves no attestation
· coverage: 7 of 9 savings rows (78%) are agent-attributable
· 8 run(s) have no attestation — either made before hooks were wired, from a VS Code session, or attested by more than one agent.
    Not evidence that no agent ran them.
```

The store is not empty: `.cage/state/attest.jsonl` holds **34 rows — 31 `session`, 3
`tool`** (all `claude`, all `graphify`). `state/graphify-usage.jsonl` holds **8** rows.
Zero of the 3 tool attestations join to any of the 8 usage rows.

## 2. How the cause was established

Every `kind:tool` attestation was **reproduced from the real command** by re-hashing
Claude transcripts — not inferred from reading the code:

| attested `args_hash` | reconstructed command | hashed as |
|---|---|---|
| `904cd809af922956` | `./bin/graphify --help 2>&1 \| head -5` | tail |
| `0a90e7e3d734134a` | `./bin/graphify query "does this fire the hook" 2>&1 \| head -3` | tail |
| `77f55281ae1bd214` | `graphify update . 2>&1 \| tail -5` | tail |

The first two pair with shim usage rows **two seconds later** — `e11af2dfe1f408e9` and
`bd53136fd29c9798`, the same runs, different keys.

| producer | hashes | file |
|---|---|---|
| `attest.record_tool` | `argv[1:]` | [attest.py](../../cage/attest.py) |
| `graphifytx._file_query` (transcript) | `argv[1:]` via `content_signature` | [graphifytx.py](../../cage/graphifytx.py) |
| **`graphifymeter.run` (shim/native)** | **full `cmd`** | [graphifymeter.py](../../cage/graphifymeter.py) |

## 3. Why no test caught it

Every existing test built its usage row **by hand** with
`usagelog.args_hash(<tail>)` — the attestation's own convention — so the two sides were
asserted to agree using one side's code twice. The disagreeing producer was never
exercised. The new test runs the **real interceptor**
(`tests/test_hooks_layer.py::test_the_real_interceptor_writes_a_row_the_attestation_can_join`)
and fails without the fix with exactly the field symptom: `agents: []`,
`unattested: 1`.

## 4. What is still broken — stated, not fixed

- **Cause 2 — the hook attests a *shell command line*, the usage row an *argv*.**
  `attest.record_tool` `shlex.split`s what the host reports, so `2>&1 | head -3` enters
  the hash: `['query','does this fire the hook','2>&1','|','head','-3']` ≠
  `['query','does this fire the hook']`. **A piped or redirected invocation still will
  not join**, and every one of the three real attestations is piped. Normalizing shell
  syntax is a *decision*, not a defect — filed as
  [attest-join-command-normalization](../proposals/attest-join-command-normalization.proposal.md).
- **Cause 3 — an attested run can have no usage row at all.** `graphify update .` was
  attested and produced none: the transcript route breadcrumbs **only when a receipt is
  filed** ([graphifytx.py](../../cage/graphifytx.py) `_file_query`), and a binary that
  bypasses the interceptor is never seen. Reported, not fixed — half A counts *runs the
  breadcrumb saw*, and inventing a row for a run cage did not observe would be the
  fabrication this whole view exists to prevent.
- **The fix is forward-only.** The 8 usage rows already written keep their old keys.
  The ledger is append-only and rows are never rewritten, so **this table stays empty
  until new runs land**, and its emptiness today is history, not a live defect.

## 5. Verdict on §10's open question — fix, or capture change?

**A fix.** It captures no new field, changes no schema, and adds no row: one producer was
violating the convention the other two already implement and that `content_signature`
already documents in prose. `args_hash` lives in `state/`, is diagnostic-only, and is
never read by a money view — so the correction cannot move a reported number.

**But necessary, not sufficient:** it makes a plain `graphify query "x"` join, and
leaves every piped invocation to cause 2. Q3 is answered; it is not closed.
