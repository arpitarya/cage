---
doc: cage-lab setup
audience: an agent or Arpit rebuilding ../cage-lab from nothing
---

# 01 — Setup: zero to a runnable lab

**Goal:** a lab that installs cage the way a user does, drives real agents, and can
prove what its own PATH and versions were.

**Everything here goes into `cage-lab/SETUP.md` and `cage-lab/rebuild.sh` as you do
it.** A lab whose setup wasn't recorded is not evidence — its captures are downgraded
to `UNPROVEN`.

## 0. Before you start

- `../cage-lab` may be deleted freely. This manual is the source.
- **`cage/work/regression/**` is never touched.** Past results already live there.
- The cage tree stays **uncommitted**; commits happen in `cage-lab` only.

## 1. Structure

```
../cage-lab/
  .venv/                    # gitignored — the lab's own toolchain
  SETUP.md                  # every command, in order, with output — written as you go
  rebuild.sh                # the same, re-runnable, exits non-zero on any check failure
  bin/                      # cage-written interceptor shim(s) live here
  _src/                     # the CANONICAL fixture — the control variable
  workspace-off/            # fixture + cage, NO graphify anything
  workspace-on/             # fixture + cage + graphify graph + per-agent installers
  questions.txt             # the question set (§4)
  drive.sh                  # the driver — sets PATH explicitly, proves it
  labledger/                # isolated ledger; ~/.cage is never written
  runs/                     # per-run scratch — disposable
  reports/                  # run report · finding docs · benchmark (published into cage)
```

## 2. The `.venv` — standing rule, not a preference

**Why:** a lab whose `cage`/`graphify` come from whatever is globally installed is not
reproducible, and PATH order gets decided by the machine's shell rc instead of the
experiment. This is not hypothetical — a stale interceptor in an unrelated project
once won on PATH *from inside cage-lab* and silently unmetered every graphify run.

```bash
cd ../cage-lab
python3 -m venv .venv                 # needs python3.11+ (cage) / 3.10+ (graphifyy) —
                                       # if the machine's default python3 is older, use a
                                       # newer interpreter explicitly, e.g. a pyenv version
.venv/bin/pip install -e ../cage      # see the deviation note below
.venv/bin/pip install graphifyy       # pin the version; record it
.venv/bin/cage --version
.venv/bin/python -c "import importlib.metadata as m; print(m.version('graphifyy'))"
```

**Python version note:** cage requires `>=3.11`, graphifyy requires `>=3.10`.
A machine whose default `python3` predates either (e.g. macOS's bundled
3.9.x) will fail both installs — `pip install -e ../cage` errors outright,
and a `pip index versions graphifyy` run under that same old interpreter can
misreport "no matching distribution" (pip filters by `requires-python`) even
though the package is published. Create the venv with a `>=3.11` interpreter
(pyenv, uv python, etc.) and re-check under *that* venv's own pip before
concluding a package isn't published.

**⚠️ Declared deviation:** cage-lab is black-box by rule — it installs the *shipped*
cage and never imports it. `-e ../cage` installs local source, which is the only
option while v0.36 is unreleased. **Record it in `SETUP.md` as a deviation**, and
switch to the published wheel once v0.36 ships.

### PATH: set it explicitly, never rely on activation

Activation only affects shells that activate. Put this at the top of `drive.sh` and in
`rebuild.sh`:

```bash
export PATH="$LAB/bin:$LAB/.venv/bin:$PATH"   # lab interceptor › lab tools › machine
```

Then **prove it** — the run writes the result into its manifest, nobody checks by hand:

```bash
command -v graphify   # must resolve inside $LAB, not to a machine-global shim
command -v cage
```

**This proves the POSIX twin only.** `command -v` is a POSIX shell builtin; it
resolves the extensionless `bin/graphify`, never `bin/graphify.cmd` (Windows'
twin — `docs/adr/0005_graphify.md`, ADR 0007). cage-lab has never run on Windows, so it
has never proven — and cannot, as written, prove — that the `.cmd` twin resolves
the way `graphify.exe %*` at a cmd prompt would. That coverage is CI-GF's job
(`tools/cigraphify.py`, the `graphify (windows-latest)` CI job), not the lab's.

**Which `bin/` — a correction.** `cage setup` writes the metering interceptor
into **the workspace's own** `<workspace>/bin/graphify`, not a shared
lab-level `bin/` — and `cage doctor`'s interceptor-liveness check requires
that *specific* `bin/` to be literally on `PATH` (it compares the shim's
parent dir against `PATH` element-for-element). So the operative PATH line,
whenever you're actually inside a workspace, is:

```bash
export PATH="$WORKSPACE/bin:$LAB/.venv/bin:$PATH"   # $WORKSPACE = workspace-off or workspace-on
```

`$LAB/bin` (top-level) is kept as a symlink to whichever workspace has the
live shim, for discoverability matching the tree diagram — but it is not
what `cage doctor` or a driven session actually needs on `PATH`.

## 3. The fixture (`_src/`) — the control variable

**As built** (`_src/tinyshop/`, ~43 KB total — author once, never edit; its bytes are
what make two runs comparable):

```
_src/
  .fixture-sha256          # the hashes, asserted on every rebuild
  tinyshop/__init__.py
  tinyshop/models.py       # the large module — the reason a graph answer can win
  tinyshop/pricing.py      # discount stacking (PercentageDiscount, FixedAmountDiscount, coupons)
  tinyshop/inventory.py    # reserve/release stock
  tinyshop/orders.py       # places orders — calls pricing + inventory
  tinyshop/cli.py          # entry point — the far end of the Q2 call path
```

- The large module must genuinely be large. Without it, reading the file is as cheap
  as querying the graph and the A/B has nothing to measure.
- The small modules carry **real cross-module calls** so "how does X relate to Y" is a
  genuine question, not a lookup.
- **Hash every fixture file** into `.fixture-sha256` + `SETUP.md`. Re-hash after every
  rebuild and assert identical — a changed fixture is a **new baseline**, declared, not
  discovered.

## 4. The questions (`questions.txt`) — the pinned six

Authored against the §3 fixture. **Use verbatim, in this order, in every cell and both
arms.** Changing them mid-cycle makes cells incomparable.

**Graphify-sensitive (Q1–Q3)** — where the ON/OFF delta is measured; **repeats = 3**:

```
Q1  In the tinyshop package, which module owns discount-stacking logic
    (PercentageDiscount, FixedAmountDiscount, coupon stacking), and which module
    calls into it to price an order line?
Q2  Trace the call path from tinyshop/cli.py to tinyshop/models.py — which modules
    sit between them and what do they each contribute?
Q3  Which module in tinyshop is responsible for mutating inventory stock levels
    (reserving and releasing stock), and which function calls into it when an order
    is placed?
```

**Capture-correctness (Q4–Q6)** — deterministic, near-zero output; **repeats = 1**:

```
Q4  Reply with exactly this text and nothing else: cage-lab-capture-check-one
Q5  Compute 17 * 23 and reply with only the resulting number, no words.
Q6  Say the single word HELLO, then on a new line say the single word CAGE-LAB.
```

Why this split: Q1–Q3 force cross-module reasoning a grep-and-read agent answers by
opening the large module — the expensive path the graph is supposed to replace.
Q4–Q6 are deliberately trivial and **deterministic**: their answers are fixed, so any
token variance between arms is the agent's overhead, not the question's — they exist
to generate turns to meter, not to favour either arm.

**Content-free by construction** — we authored them, so captures are stored byte-exact
with no sanitizing.

## 4a. graphify 0.9.30 — what the claude integration actually is (verified 2026-07-30)

**Re-verified against the installed wheel. Every 0.5.0-era claim in cage's docs about
this hook is now false — do not carry them forward.**

| claim from the 0.5.0 probe | reality at 0.9.30 |
|---|---|
| the PreToolUse hook "spawns no process — a static bash conditional" | it runs **`graphify hook-guard search` / `hook-guard read`** as a real subprocess |
| "no `--strict` flag exists anywhere" | `hook-guard read --strict` exists, plus a `GRAPHIFY_HOOK_STRICT` env override |
| matcher was a passive nudge on `Glob|Grep` | matchers are **`Bash|Grep`** and **`Read|Glob`** — it intervenes on the agent's primary search *and* read paths |

### ⚠️ The hook bypasses cage's interceptor — by design, not by accident

`install.py::_claude_pretooluse_hooks` resolves `_resolve_graphify_exe()` and writes an
**absolute** path into the hook:

```
/Users/.../cage-lab/.venv/bin/graphify hook-guard search
```

That never traverses `PATH`, so `workspace-on/bin/graphify` — cage's metering shim —
**cannot see it**. Neither can the transcript route: a hook is not a Bash tool call, so
nothing appears in the transcript for `graphifytx` to detect. **Both cage routes are
blind to hook-guard.**

**Keep the claim proportionate.** hook-guard mostly *nudges*: it prints a suggestion and
exits, and if the agent then runs `graphify query` through Bash, **that** call does hit
the shim and is metered normally. The bypass costs cage *visibility of the nudge*, not
automatically a receipt.

The exception that matters: **in `--strict` mode the read hook DENIES the first raw
read** of an indexed file per session and redirects to `graphify query`. There the
avoided read is a real saving that may never produce a metered query — a saving cage
cannot see by any route.

### Decision: `--strict` is OFF for this run (2026-07-30)

- Strict changes agent behaviour *and* introduces an unmeterable saving path. Turning
  it on at the same time as the ON/OFF pairing would change two variables at once and
  make the delta uninterpretable.
- So: **install without `--strict`**, record `GRAPHIFY_HOOK_STRICT` as unset in
  `SETUP.md` and the run manifest, and treat strict as a **separate later arm** once
  the baseline pairing is understood.
- Because the hook fires under a matcher the agent hits constantly, **record the
  installed hook block verbatim in `SETUP.md`** — if graphify is upgraded, this section
  is the first thing that goes stale.

### The measurement this forces on every ON cell

An ON cell must record **three** things, not two:

1. **Did the hook fire?** (graphify intervened) — cage cannot tell you this; capture
   graphify's own evidence.
2. **Did graphify actually run a query?** (`graphify query|path|explain`)
3. **Did cage see it?** (a receipt + a usage row)

Without #1 the run will observe behaviour changes it cannot explain, and will be
tempted to attribute them to the wrong cause.

## 4b. ⚠️ Turn capture-on-read OFF in every lab workspace (2026-08-01)

**Found the hard way:** a single `cage report` in `workspace-on` swept **33,003
machine-wide calls** (back to February, 7.6 B tokens) into the lab ledger. Capture is
**global by design** — a read triggers `importcmd.ensure_captured`, which sweeps every
agent's real log directory, not just work done in this workspace. Correct for a normal
project; **fatal for a lab**, where the ledger must contain this run and nothing else.

**This is not fixed by choosing a different ledger.** Pointing at `labledger/` would
have absorbed exactly the same 33k rows. The isolation comes from two things:

1. **`on_read = false`** in *both* workspaces' `.cage/cage.toml`:

   ```toml
   [capture]
   enabled = true
   on_read = false     # a read must never sweep the machine's agent logs
   ```

   Set it in the **config, not the environment** — `CAGE_CAPTURE_ON_READ=0` works in a
   shell but does not reach a VS Code extension's subprocess, the same propagation gap
   that already bit PATH.

2. **Import only with an explicit `--path`** pointing at the run's own copied logs
   (what `drive.sh` does). A bare `cage import` is a machine-wide sweep by definition.

**Verify after setting it:** `cage report --no-import` shows only this lab's rows.

**If a ledger is already contaminated:** delete `ledger/calls-*.jsonl`,
`ledger/credits-*.jsonl` and `ledger/imports.jsonl` — but **keep `ledger/savings/`**,
whose receipts are real lab data filed by the shim.

## 5. The two workspaces

Build both from the **same `_src` bytes**. Graphify is the only difference.

### `workspace-off/`

```bash
cp -a _src/. workspace-off/ && cd workspace-off && git init
cage setup --all --no-graphify    # all three agents — see the note below
cage doctor
```

- **`--no-graphify` is required here, not optional.** The lab's `.venv` puts a
  real `graphify` binary on PATH for *both* workspaces (it's one shared venv).
  Plain `cage setup --all` installs a `bin/graphify` interceptor shim
  whenever `graphify` resolves on PATH at all — it doesn't check whether the
  project has any graphify steering. Without `--no-graphify`, workspace-off
  would get a shim of its own, which is itself a graphify artifact and fails
  the very check below.
- **OFF must be genuinely off:** no `graphify-out/`, no steering block in any agent
  file, no `bin/graphify` shim. A leftover graph (or shim) makes "off" a weaker "on".
- **One documented exemption:** `.cage/cage.toml` legitimately contains `graphify` in
  `[tools] order` — that is cage's **bundled default pipeline order**, not a graphify
  artifact, and with no graphify installed it can produce nothing. A naive
  "no mention of graphify anywhere" grep fails on this benign line; the check must
  exempt `[tools] order` explicitly rather than be waived by hand each time.

### `workspace-on/`

```bash
cp -a _src/. workspace-on/ && cd workspace-on && git init
graphify update .            # builds graphify-out/ — record the exact verb + flags
graphify claude install      # CLAUDE.md steering + a PreToolUse hook
graphify copilot install     # ~/.copilot/skills — a passive /graphify skill
graphify kiro install        # .kiro/skills + steering — ALWAYS (kiro is never optional)
cage setup --all             # all three agents — .cage/, bin/graphify shim, MCP wiring, cage's block
cage doctor
```

- **Use the tools' own installers. Never hand-write a steering block** — otherwise you
  are measuring your guess at what graphify installs, not what a user gets.
- **Skip `graphify hook install`.** It rebuilds the graph on commit — freshness, not
  usage — and a mid-run rebuild adds noise to the one thing the ON arm measures.
- **⚠️ All three agents, always (law 0).** `cage setup --claude` wires claude *only*;
  a copilot or kiro session in that workspace then has no MCP wiring. Use
  **`cage setup --all`** in **both** workspaces and verify with `cage setup --status`
  — it must list **claude, copilot and kiro** as wired.
- **All three graphify installers run in `workspace-on`** — claude, copilot **and**
  kiro. Omitting one silently turns that agent's ON cell into a second OFF cell, and
  the run reports a zero that looks like an adoption finding but is a setup bug.
- **Record what each installer did to `CLAUDE.md`.** Both graphify and cage write it;
  snapshot after each and diff. Who clobbers whom is an observation, not a detail.

## 6. Verify before you spend anything

All of these must pass, and `rebuild.sh` must exit non-zero if any fails:

- [ ] `cage setup --status` lists **claude, copilot AND kiro** as wired, in
      **both** workspaces (law 0 — never a per-run choice).
- [ ] `workspace-on` carries all three graphify integrations: the claude
      CLAUDE.md block + PreToolUse hook, the copilot skill file, and the
      kiro skill + steering file.
- [ ] `command -v graphify` resolves **inside `$LAB`**, and the file routes through
      **`cage data graphify`** (live) — not `cage graphify` (**dead**: exits 1, falls
      through, runs unmetered and silent).
- [ ] `cage doctor` reports the interceptor **live**, not merely present.
- [ ] `workspace-on/CLAUDE.md` carries **both** a cage block and an
      installer-written graphify block.
- [ ] `workspace-off/` has **no** graphify artifacts of any kind, for **any** agent.
- [ ] Fixture hashes match `SETUP.md` (keep the machine-checkable form too —
      a `shasum -a 256` listing in `_src/.fixture-sha256`, so `rebuild.sh` can
      `shasum -a 256 -c` it directly instead of parsing prose).
- [ ] A one-prompt smoke run captures into `labledger/` and **leaves `~/.cage`
      untouched** (check its mtime before and after) — **also watch `~/.zshrc`**:
      `cage setup` (without `--no-graphify`) appends a `PATH=` line to the real
      shell rc on a machine with no prior cage install (`adoptcmd._wire_path`);
      hash it before/after too.

**`rebuild.sh` must not spend money on every re-run.** It's meant to be safe
to run repeatedly (after a partial run, after a cage/graphify upgrade, just to
re-prove wiring). Gate the smoke-prompt check behind an explicit flag (e.g.
`--smoke`); the plain invocation re-verifies structure for $0.

## 7. Record it

`SETUP.md` must contain: every command in order · their real output summaries · cage
and graphify versions **and which cage build** (local source vs wheel) · the
`CLAUDE.md` ownership observation (which installer wrote first, and whether
either clobbered the other) · the fixture hashes · the proven PATH (and which
`bin/` it actually needs, per the correction in §2) · any deviation the real
CLI forced versus this manual's literal commands, each with its own exit
condition.

Next: [02-run.md](02-run.md).
