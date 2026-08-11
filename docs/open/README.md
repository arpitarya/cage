# docs/open — one file per open item

[OPEN-WORK.md](../OPEN-WORK.md) is the **index**: one line per item, nothing else. The
detail — gate, protocol, pre-committed reading, traps — lives here, one file per item, so
the queue stays readable at a glance and an item can be handed to someone whole.

**The maintenance law is unchanged** ([CLAUDE.md](../../CLAUDE.md) *Documentation
discipline*): maintained continuously · a completed item's file is **deleted**, not ticked,
and only after its outcome is in [IMPLEMENTATION.md](../IMPLEMENTATION.md) and any evidence
is published to [regression/](../regression/) · **a file's own status line is never
evidence** — reconcile against the code.

**Deleting an item file is a citation migration.** Re-point or past-tense every link to it
in the same change, exactly as for any removed doc.

| file | what it holds |
|---|---|
| `<ITEM>.md` | one open item: why it is open, what closes it, what binds a fix |
| [CONSTRAINTS.md](CONSTRAINTS.md) | rules that outlive their originating item — **not** open work |

Adding an item = a new `<ITEM>.md` **and** one line in the index. A file with no index line
is invisible; an index line with no file is a lie.
