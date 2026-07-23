# Debugging capture — why an agent isn't being metered

Cage's capture path is **fail-open and silent by design**: a hook that errors, or skips
because of a guard, never raises and never prints — so a hook that *never fires* looks
identical to one that fires and quietly records nothing. The debug layer makes that path
observable. It is **metadata-only** (agent, event, paths, counts, skip reasons,
tracebacks — never prompt or response bodies) and **off by default** ($0, stdlib, writes
nothing until you turn it on).

> **First, the universal path.** Capture is pull-based (plan §3.7): `cage import` reads
> every agent's on-disk log into the active ledger, and `cage data export` refreshes then emits
> it — **no hooks, no project required**. If `cage report` looks empty, run `cage import`
> (or `cage data watch`) first; that alone fixes the most common "nothing is captured" case
> (a Copilot-only user, or any agent under a VS Code extension whose hooks never fire).
> Hooks are an *optional* real-time add-on that fire only under a CLI client; the debug
> layer below is for when you want to know *why* a hook isn't firing.

Use this when: an agent's tokens aren't showing up in `cage report` even after `cage
import`, and you need to know whether its hook fired, was skipped by a guard, or hit a
parser error.

## Capture-on-read (the primary path, v0.31+)

You rarely need `cage import` by hand any more: **every read runs the incremental sweep
first**. `cage report`, `cage insights *`, and the MCP read tools all capture-on-read —
they sweep your agent logs into the ledger, then render — so a number is never staler than
the instant it's shown. No hook, no scheduler, no project required. The sweep is throttled
(~60s, policy `[capture] read_throttle_secs`) so back-to-back reads don't re-sweep, and it
is fail-open: a capture error is traced under `CAGE_DEBUG` and never blocks the read.

When a read captures new rows it prints one line to **stderr** (never stdout, so a
`--json`/`--csv` stream stays pure), and **stays silent when nothing is new**:

```
· captured 240 new calls (claude, codex) + 3 graphify savings since last read
```

A `graphify`/`fux` saving prints its own stderr proof the moment it's filed:

```
✔ cage: graphify saving captured — ~900 tokens (→ /repo/.cage)
```

Controls (all counts-only, never content):

- **`--why-ledger`** on any read prints which ledger resolved and why, plus its routing
  key: `· ledger: project (.cage/) → /repo/.cage (route-key c89f4cc8…)`. This is the
  one-grep answer to "my graphify saving vanished" — push and read must resolve the same
  ledger, and this shows both.
- **`--quiet`** / **`CAGE_QUIET=1`** silences the confirmations (numbers are unchanged).
- **`--no-import`** skips the pre-read sweep for one invocation; **`CAGE_CAPTURE_ON_READ=0`**
  disables it standing (the switch the determinism/golden suites use); **`CAGE_CAPTURE=0`**
  pauses *all* capture.
- **`cage doctor`** shows a per-source, per-**mode** (pull/push) capture timeline —
  what cage has captured, how, and when, for every agent and the graphify/fux push side.
  Doctor deliberately does **not** sweep first, so it never masks the breakage it
  diagnoses. Its **`wiring`** check is the one below.

## Capture is silently off: a dead verb in an installed artifact

The failure with no symptom. A hook or shim installed before a verb was renamed still
names the **old** verb, so it exits 1 — and because hook output goes nowhere and both
shims fail open to `exit 0`, **a dead verb looks exactly like cage not being installed**.
No error, no log line, no missing file. On one machine this silently disabled graphify
metering for 9 days while `cage doctor` reported ✅, because the interceptor check tested
existence + PATH rather than liveness.

`cage doctor` now checks every installed artifact's verb against the **live parser**:

```
✗ wiring       ~/.claude/settings.json: `cage import-claude` is not a command
               → `cage import --agent claude`; re-run `cage setup --wire-only --<agent>`
✗ interceptor  bin/graphify probes a verb that no longer exists — every graphify call
               falls through UNMETERED and silently; re-run `cage setup …` to refresh it
· receipts     receipts: 0 — the graphify interceptor is dead (see wiring above); fix it
               before concluding the tools are unused
```

The fix is to re-run setup — it rewrites a dead verb to its current form in the same pass
as the absolute-path→shim migration, and refreshes a stale `bin/graphify`:

```bash
cage setup --wire-only --<agent>     # heals wiring; idempotent
cage setup --<agent>                 # also refreshes the agent's skill/prompt/steering assets
```

Notes on what is and isn't checked:

- The detector is the parser, **not** the rename table: a verb deleted outright rather
  than renamed is dead and absent from that table, so only the parser sees it.
- **User-level** artifacts are scanned (`~/.copilot/hooks`, `~/.codex/config.toml`,
  `.git/hooks`, the global skill copies) — the real-world failures were user-level.
- **Foreign (non-cage) hooks are never flagged and never modified**, including ones that
  mention the word "cage".
- A dead verb with **no known replacement** is reported but never rewritten — healing
  does not guess.
- Stale **agent assets** (skills/prompts/steering that differ from the bundled originals)
  are advisory `·`, not a failure: the agent sees a wrong verb, errors, and adapts —
  strictly less severe than capture being silently off.
- Detection is read-only: nothing is executed, and no import runs. Executing a probe
  could not tell "verb dead" from "cage absent" anyway — that ambiguity *is* the bug.

`cage query stale-wiring` explains the design.
- **`CAGE_DEBUG=1`** logs the **ledger-resolution decision** on every push and read
  (`event=ledger-resolve`), every capture-on-read sweep (`event=capture-on-read`), and
  every routing-key reclaim (`event=reclaim`) — see the trace section below.

**One canonical ledger.** Push (graphify/fux/proxy) and pull now resolve the *same* ledger
(`paths.canonical_ledger`). A pushed saving carries a non-PII routing key — a hash of the
resolved ledger-root path — so a repo-root read can **reclaim** a graphify saving pushed
from a subdirectory or a project saving that landed in the global `~/.cage`, matched by
**exact key only** (never a blind union). If a saving still seems missing, `--why-ledger`
on both the graphify run and the report shows whether they agreed on the ledger.

## The capture-health warning (cage tells you first)

You usually won't have to go looking. When an agent is **installed but capturing
nothing**, `cage report` and `cage doctor` say so in the footer:

```
⚠ codex: ~/.codex exists but ~/.codex/sessions matched 0 files — capture is off for this agent.
  cage doctor --paths      (if you don't use codex: [sources.codex] replace=true, paths=[] )
```

This is **triple-gated** so it can never nag wrongly — it fires for an agent only when
(1) its home marker exists, (2) its log matched **0 files** at the last import, and
(3) it has **never contributed a row** to the ledger. Clause 3 makes it self-silencing:
one captured row and it never warns again, so it only ever names an agent that is
genuinely capturing zero. Follow `cage doctor --paths` (the next section) to see exactly
which location cage probed and why it missed — usually a vendor moved its log store, a
nonstandard install, or the `UNVERIFIED-LAYOUT` Windows Kiro path. If you simply don't
use that agent, silence it with the documented `[sources.<agent>] replace=true, paths=[]`
stanza (see [Configurable import paths](sources.md)). The verdict is recorded at import
into `cursors.json["_health"]` and rendered from that cache — no live filesystem probe on
the read path, so `cage report` stays deterministic in its tables.

## The always-on capture breadcrumb (`state/capture.log`)

Unlike everything else on this page, `state/capture.log` needs **no debug flag** —
it's the standing proof-of-capture the 2026-07-22 regression report needed before F1
(zero real savings receipts) could even be diagnosed. Every real import sweep — a
manual `cage import`, a hook firing, or a non-throttled capture-on-read sweep — appends
one line per agent it actually swept, counts-only:

```
{"ts": "2026-07-23T10:15:02+00:00", "agent": "codex", "files_seen": 14,
 "rows_new": 3, "rows_total": 212, "src": "~/.codex/sessions"}
```

- **`files_seen`** — files the glob matched this sweep (pre-cursor).
- **`rows_new`** — rows this run actually appended (0 is a normal, healthy line —
  it means the sweep ran and found nothing new, not that it didn't run).
- **`rows_total`** — that agent's lifetime row count in the ledger, including this run.
- **`src`** — the tilde-relative source location probed, never contents.

**A no-op read appends nothing.** A throttled capture-on-read (within
`[capture] read_throttle_secs`), or a read while `[capture] enabled=false` /
`CAGE_CAPTURE=0`, never calls the sweep at all — so it never reaches this breadcrumb.
Only a *real* sweep writes a line, which is what makes the log's mere presence useful:
if `capture.log` never grows, capture genuinely never ran (not "ran and found nothing").

It's local state, never read by any derived view (`report`/`attrib`/`matrix` are
byte-identical whether this writes or not), and size-managed by the same allowlisted
cleanup as `debug.log` (the `capture-log` class, `policy.toml [cleanup] days`). It's
also in `cage doctor --bundle` (`state/capture.log`) alongside `debug.log`.

## Receipt produce/skip logging — the F1 instrument

The other half of the F6 instrument, this one **is** `CAGE_DEBUG`-gated (verbose, so
off by default): every receipt push/skip site logs `event=receipt` with `tool`,
`produced` (bool), and — when nothing was produced — `skip_reason`:

| Site | `skip_reason` | Meaning |
|---|---|---|
| `graphifymeter._meter` | `non-measured-op` | the graphify subcommand wasn't `query`/`path`/`explain` |
| `graphifymeter._meter` | `no-source-file-parsed` | the answer cited no file that resolved on disk — unmeasurable, not zero |
| `graphifymeter._meter` | `no-saving-to-claim` | the answer wasn't smaller than its cited sources |
| `graphifymeter.run` | `linked-receipt-skipped` | graphify self-metered natively — the wrapper defers, no double-count |
| `metering.record_receipt` | `push-sink-unresolved` | the ledger append itself failed (unwritable sink) |
| `responsecache.lookup` | `cache-miss` | no cached response for this prompt hash |
| `compress.receipt` | `no-saving-to-claim` | the compressed form wasn't smaller than the original |

`produced=True` (no `skip_reason`) means the site actually built/pushed a receipt.
Before F6 a skipped receipt was completely silent — this is what makes "why did cage
report zero savings for tool X" answerable from `CAGE_DEBUG=1 cage debug --tail` instead
of a guess.

## The model — what has to be true

For a **hook** to capture in real time, two things must hold (the on-disk `cage import`
path needs only the last one):

1. **The hook fires.** The agent actually executes cage's hook. This only happens under a
   CLI client — a **VS Code extension never runs** `.codex/hooks.json` / `.kiro/hooks/*` /
   `~/.copilot/hooks` (only Claude Code's extension honors its hooks). If the hook never
   fires, use `cage import` / `cage data watch` / your own cron instead.
2. **Capture is enabled.** `cage import` no-ops only when capture is switched off
   (`[capture] enabled=false` / `CAGE_CAPTURE=0`). There is **no** cwd-`.cage` guard
   anymore: with no project, capture resolves to the global ledger `~/.cage`
   (`--ledger`/`CAGE_BASE` → project `.cage/` → global), never a no-op or a stray local
   footprint.
3. **The log parses.** The agent's on-disk usage log exists where cage looks and parses
   into call rows.

## Step by step

### 1. Install a build with debug support
```bash
cd /path/to/cage
pip install -e .        # or your usual build/install step
cage --version          # confirm the debug-enabled version
```

> **Install the *global* binary, not just a project venv.** Agent hooks call cage by
> absolute path (`paths.cage_bin()`, e.g. `~/.local/bin/cage`) — they do **not** use a
> project's `.venv`. So `uv add /path/to/cage` (which installs into a venv) won't update
> the cage the hooks run. Update the global tool instead — `uv tool install --force
> /path/to/cage` / `pipx install --force …` / `pip install -e …` into the env behind
> `~/.local/bin` — then confirm `~/.local/bin/cage --version` shows the new build and
> `~/.local/bin/cage debug --help` exists.

### 2. (Re)wire the consumer's hooks
```bash
cd /path/to/your-project
cage setup              # regenerates .claude / .codex / .copilot / .kiro hooks
```

### 3. Turn debug on
Two ways. **Prefer the policy file** — it's read by every hook no matter how the agent was
launched, which matters for GUI agents (Kiro, VS Code Copilot) that don't inherit a shell
export. `cage setup`/`cage setup` already writes a `[debug]` block to `.cage/policy.toml`
(default `enabled = false`) — **edit that existing line to `true`; do not append a second
`[debug]` block** (duplicate tables make TOML refuse to load and crash `cage import`):
```toml
# .cage/policy.toml  (flip the block cage already wrote)
[debug]
enabled = true
```
Shell-export alternative (only reaches agents launched *from that shell* — Claude/Codex
CLI):
```bash
export CAGE_DEBUG=1            # or one-off:  CAGE_DEBUG=1 cage import --agent all
```
Optional: pin the log to a fixed path with `CAGE_DEBUG_LOG=/tmp/cage-debug.log` (otherwise
it lives at `.cage/state/debug.log`).

### 4. Exercise each agent
In the project, run each of the four agents once with a trivial task, then end the turn the
way you normally do: **Claude Code, Codex, Copilot, Kiro.** Doing all four lets you compare
— Claude is effectively the known-good control.

### 5. Read the output
```bash
cage debug --tail 50    # recent per-hook events (add --json for raw lines)
cage doctor             # per-agent heartbeat: last-fired time or "never"
cat .cage/state/debug.log
```

### 6. Share it (bug reports)
```bash
cage doctor --bundle    # one redacted archive: doctor output, debug.log, capture.log,
                        # versions, footprint row counts, policy provenance
```
Counts-never-content — safe to attach as-is; never attach raw ledger shards or
agent transcripts instead. `skip=parsed-zero-rows` in the debug log is the
format-drift signature (a non-empty log the parser recovered nothing from) —
exactly what the bundle exists to report.

## Reading the results

`cage debug` prints one line per event, e.g.:

```
2026-06-27 11:40:02  codex/import  src=~/.codex/sessions files=14 parsed=212 appended=212 deduped=0
2026-06-27 11:41:10  claude/import  skip=cursor-unchanged src=~/.claude/projects candidates=37
2026-06-27 11:42:55  kiro/import  error=ValueError
    Traceback (most recent call last):
    ...
```

`cage doctor` shows the heartbeat per agent (`claude Stop: 1m ago · codex Stop: never · …`)
plus the last error/skip.

Interpretation, per agent:

| What you see | Meaning | Fix |
|---|---|---|
| `appended=N` (N>0) | Capturing correctly | nothing |
| `skip=capture-disabled` | Fired but capture is switched off | re-enable (`[capture] enabled=true` / `CAGE_CAPTURE=1`) |
| `skip=since-filtered` / `skip=cursor-unchanged` | Fired but `--since` dropped every file / the cursor saw no new data | widen `--since`; `cursor-unchanged` is normal (nothing new to import) |
| `error=…` + traceback | Fired but the parser choked on that agent's log format | file the traceback — it's a parser bug for that agent/version |
| `skip=parsed-zero-rows` | Log has bytes but the parser recovered no rows — the format-drift signature (agent update changed its log shape) | file it with a `cage doctor --bundle` |
| `ledger.append` `result=write-failed` | The row was parsed but could not be written (unwritable ledger dir / disk) | fix permissions on the shard path in the event |
| Agent **absent** from `cage debug` / **"never"** in `cage doctor` | The hook isn't firing (e.g. a VS Code extension) | this is expected — capture that agent with `cage import` / `cage data watch` / your own cron |

## What it never logs

Counts-never-content holds here too: the debug log records only metadata — agent, event,
cwd, resolved root, `.cage` present?, capture-enabled?, `transcript_path` *presence*, file
paths/counts, parsed/appended/deduped counts, skip reasons, and exception type +
traceback. It never contains prompt bodies, response text, or token text. It's local state
under `.cage/state/` and has no effect on the ledger — derived tables are byte-identical
with debug on or off.

## Turn it off

Remove the `[debug]` block from `.cage/policy.toml` (or `unset CAGE_DEBUG`). The log files
under `.cage/state/` can be deleted at any time; they're regenerated only while debug is on.

## When the hook simply won't fire

If debug proves an agent never executes cage's hook (the norm for VS Code extensions),
don't fight it — that's exactly what the universal pull-based path is for. `cage import`
reads every agent's on-disk log regardless of hooks or cwd, into the resolved ledger
(global `~/.cage` when you're not in a project):

```bash
cage import            # one-shot: capture everything now
cage data watch             # a foreground loop you start and Ctrl-C (no daemon)
```

**cage installs no background job** — no launchd/systemd/cron/schtasks, and no `cage
scheduler` command. If you want hands-off capture, add **your own** cron line; cage will
never create or manage one:
```cron
# your crontab — sweep all agents every 30 min into the global ledger
*/30 * * * * cage import >/dev/null 2>&1
```
The import is idempotent (dedupes by call id) and incremental (a per-agent cursor skips
unchanged files), so it stacks safely with any hooks that *do* fire and stays cheap as the
ledger grows.
