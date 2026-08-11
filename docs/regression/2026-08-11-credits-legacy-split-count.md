# CREDITS-LEGACY-SPLIT — the count that gated the decision (2026-08-11)

**Result: ZERO.** No multi-model copilot shutdown group exists on this ledger, so the
forward-only fix (REV-CREDITS defect 2, `billed_with`) leaves **no legacy rows
mispriced**. Verdict **(a) — leave the ledger alone and state the limit**. No read-side
group detector, no `cage data migrate-*` verb.

## What was counted

Grouping key is the one the queue item named: `(agent, session, surface, ts)`.

| measure | value |
|---|---|
| ledger rows read | 48,069 (`calls-2026-02` … `calls-2026-08`) |
| rows by agent | `claude-code` 47,986 · `copilot` 83 |
| copilot rows by surface | `vscode` 57 · `cli` 26 |
| copilot `(agent,session,surface,ts)` groups | 83 |
| **groups carrying more than one model** | **0** |
| `credits-2026-08.jsonl` rows | 3 — all `kiro`, all `model: auto`, three distinct sessions |

Every copilot group is 1:1 with a row. The double-basis defect needs a group of ≥2 rows
sharing a shutdown; none exists, in either the calls shards or the credits shard.

## The limit this number carries — read it before quoting it

**This is the PROJECT ledger (`.cage/ledger/`), not the machine ledger (`~/.cage/`).**
The machine ledger was not reachable from the environment that ran this count, so a
copilot-CLI shutdown that happened with the cwd outside any project (the
**KIRO-CLI-SCOPE** shape, which applies to copilot too) is **not in this 48,069**.

The count is therefore *0 at project scope*, not *0 absolutely*. It is enough to close
the item — the fix is forward-only either way and rows are append-only — but a future
session that finds multi-model groups on `~/.cage` should reopen at option (b), the
read-side group detector, not at (c).

**Reopen trigger:** any multi-model `(agent, session, surface, ts)` copilot group found
on a real machine ledger. Re-run the count before arguing the design.

## How to re-run it

    python3 - <<'PY'
    import json,glob,collections,os
    g=collections.defaultdict(set)
    root=os.path.expanduser('~/.cage/ledger')   # or '.cage/ledger' for project scope
    for f in glob.glob(root+'/calls-*.jsonl'):
        for l in open(f):
            try: r=json.loads(l)
            except: continue
            if 'copilot' in str(r.get('agent','')):
                g[(r.get('agent'),r.get('session'),r.get('surface'),r.get('ts'))].add(r.get('model'))
    print("groups:",len(g)," MULTI-MODEL:",sum(1 for v in g.values() if len(v)>1))
    PY
