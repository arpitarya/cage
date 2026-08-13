# cage-lab — how to build it from scratch

**This directory is the rebuild manual.** `cage-lab` is a **disposable sibling repo**
(`../cage-lab`) that can be deleted and rebuilt at any time; everything needed to
recreate it lives here, in cage, where it is versioned with the tool it tests.

If `../cage-lab` does not exist, start at [01-setup.md](01-setup.md).

## What the lab is for

- **Prove cage's numbers are right** against real agents writing real logs — never
  against fixtures cage itself produced.
- **Black-box**: the lab installs `cage` and runs it as a user would. It never
  imports cage. The in-tree test suite can't see packaging, entry points, or bundled
  data; the lab can.
- **Measure graphify's savings** with the tool toggled ON and OFF as the only variable.

## The documents

| doc | what it covers |
|---|---|
| [01-setup.md](01-setup.md) | zero → a runnable lab: `.venv`, structure, the two workspaces, installers, verification |
| [02-run.md](02-run.md) | driving the questions, capture, the run manifest, cost control |
| [03-verify.md](03-verify.md) | what "the numbers are correct" means, per agent — and how to check it |
| [04-publish.md](04-publish.md) | the three artifact types and how they get published into cage |
| [05-manual-cells.md](05-manual-cells.md) | the VS Code / IDE cells a script cannot reach — Arpit's leg |

## The six laws (they override convenience, every time)

0. **All three agents are always in scope — Claude Code · Copilot · Kiro.** Never a
   per-run choice. Every workspace is wired with **`cage setup --all`**, every
   graphify-ON workspace runs **all three** graphify installers, and every run reports
   all three — a surface that can't be driven is `NOT AVAILABLE`/`UNPROVEN`, never
   dropped. This mirrors cage's own product invariant (`agents.SURFACES`): dropping an
   agent silently is how a capture gap survives a green report.

1. **ZERO dummy data.** Real files, used as they are. A cell that can't run is
   `NOT AVAILABLE` or `UNPROVEN` — never a synthesized row.
2. **Every lab runs in its own `.venv`**, with PATH set explicitly by the driver.
   The run proves its own PATH; it never assumes one. (CLAUDE.md standing rule)
3. **Isolated ledger, always.** `--ledger <lab>`; `~/.cage` is never written.
4. **A workspace is evidence only if reproducible.** `SETUP.md` + `rebuild.sh`, exact
   commands in order, tool-owned installers only.
5. **Rebuild the configuration, never the corpus — and the corpus is FROZEN.**
   Fixture bytes are the control; if they change, you have a new baseline and must
   say so. **Decided 2026-08-01: `tinyshop` is never mutated.** A new question gets a
   **new named corpus alongside** it, and every result is labelled by which corpus
   produced it — so published evidence stays valid permanently instead of being
   invalidated by an edit. Whether tinyshop is too *small* to show graphify's value
   is a separate open question: [proposal](../archive/v0.49-larger-lab-corpus.proposal.md).

## What is safe to delete

| thing | verdict |
|---|---|
| the whole `../cage-lab` tree | **disposable** — this manual rebuilds it |
| `cage/work/regression/**` | **NEVER** — published, hashed, append-only. The lab's *results* live in cage, not in the lab |

That asymmetry is the point: the lab is scaffolding, the evidence is permanent.

## Related

- [../../work/OPEN-WORK.md](../../work/OPEN-WORK.md) — the pending-work plan
- [../regression/](../regression/) — where published lab results live
- [../../CLAUDE.md](../../CLAUDE.md) — *Regression & capture reports* section
