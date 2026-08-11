# OPEN-WORK — the index of pending work

One line per open item. **Detail lives in [open/](open/), one file per item** — this file
is an index and must stay one screen. Rules that outlive an item:
[open/CONSTRAINTS.md](open/CONSTRAINTS.md). Procedures: [FIELD-RUNBOOK.md](FIELD-RUNBOOK.md).

**⚠ Before trusting anything here, reconcile with git — this header had gone stale six
times in a week.** As of 2026-08-12: `__version__` and latest tag are `0.48.0`; local
`HEAD` is **8 commits ahead of `origin/main`** with **65 staged-uncommitted files** —
the whole agent-lane sweep is real, verified in code, and **unpushed**. Suite **1639
passed / 0 failed / 11 skipped**, measured 2026-08-12 (the previously-claimed figure was
the same number, but it was an assertion until then). Ground truth is `git status` ·
`git log origin/main..HEAD` · `git tag --sort=-v:refname` · `cage/__init__.py` — never
this prose. **Since 2026-08-12 the checkable half of that is test-gated**
(`tests/test_queue_honesty.py`): a version, tag, or clean-and-pushed claim here that
contradicts git fails the suite. Counts are deliberately *not* gated — they are
true-at-writing and would redden on the next commit.

**Next:** commit and push the 65 files. Then [NET-1](open/NET-1.md).

## Your hands

| item | one line | state |
|---|---|---|
| [NET-1](open/NET-1.md) | prove graphify pays — n=5 per arm, outcomes pre-committed | open, ungated · **do this one** |
| [L1-FIELD](open/L1-FIELD.md) | do the copilot and kiro hooks actually fire? `--status` already claims they do | 1 of 3 legs verified · **Q3 answered + fixed 2026-08-12**, residual parked |
| [KIRO-MCP-FIELD](open/KIRO-MCP-FIELD.md) | does `python3 -m cage mcp` start on a real Kiro? | open · five minutes, binary |
| [HR-FIELD](open/HR-FIELD.md) | is the four-bucket split honest off cage's own doc-heavy repo? | standing note — waits on you working elsewhere |
| [GFX-KIRO-RATE](open/GFX-KIRO-RATE.md) | how often does kiro's stdout cap refuse a real query? n=2 is not a rate | trigger — cannot be forced |

## Your decision

| item | one line | state |
|---|---|---|
| [GF-LAUNCHER](open/GF-LAUNCHER.md) | under `--python-launcher` neither graphify twin meters | compare written, **verdict B awaiting your accept** |

## Parked — do not pick up before the trigger fires

| item | one line | trigger |
|---|---|---|
| [TOOL-SDK](open/TOOL-SDK.md) | the paved road so the next tool isn't 34 modules | fux existing as a second real consumer |
| [COPILOT-SIDECAR](open/COPILOT-SIDECAR.md) | per-call cache tokens + the real model behind `copilot/auto` | trigger R3 of the pricing-basis compare |
| [POLICYSYNC-FIXTURE](open/POLICYSYNC-FIXTURE.md) | sync tests should own a synthetic bundle | a **third** table removal reddening them |
| [KIRO-CLI-SCOPE](open/KIRO-CLI-SCOPE.md) | project-less kiro credits reach only a machine-ledger sweep | it proving common |
| [OUTPUT-GROWTH](open/OUTPUT-GROWTH.md) | `.cage/output/` grows unbounded by design | **a named size number** from a real machine |

## How this file is maintained

Continuously · completed items **deleted, not ticked** (outcome to
[IMPLEMENTATION.md](IMPLEMENTATION.md), evidence to [regression/](regression/) first) ·
**its own markers are never evidence.** Adding an item = a file in [open/](open/) **and**
one line above. Full law: [`../CLAUDE.md`](../CLAUDE.md) *Documentation discipline*.
