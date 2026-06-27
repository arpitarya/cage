# Debugging capture — why an agent isn't being metered

Cage's capture path is **fail-open and silent by design**: a hook that errors, or skips
because of a guard, never raises and never prints — so a hook that *never fires* looks
identical to one that fires and quietly records nothing. The debug layer makes that path
observable. It is **metadata-only** (agent, event, paths, counts, skip reasons,
tracebacks — never prompt or response bodies) and **off by default** ($0, stdlib, writes
nothing until you turn it on).

> **First, the universal path.** Capture is pull-based (plan §3.7): `cage import` reads
> every agent's on-disk log into the active ledger, and `cage export` refreshes then emits
> it — **no hooks, no project required**. If `cage report` looks empty, run `cage import`
> (or `cage watch`) first; that alone fixes the most common "nothing is captured" case
> (a Copilot-only user, or any agent under a VS Code extension whose hooks never fire).
> Hooks are an *optional* real-time add-on that fire only under a CLI client; the debug
> layer below is for when you want to know *why* a hook isn't firing.

Use this when: an agent's tokens aren't showing up in `cage report` even after `cage
import`, and you need to know whether its hook fired, was skipped by a guard, or hit a
parser error.

## The model — what has to be true

For a **hook** to capture in real time, two things must hold (the on-disk `cage import`
path needs only the last one):

1. **The hook fires.** The agent actually executes cage's hook. This only happens under a
   CLI client — a **VS Code extension never runs** `.codex/hooks.json` / `.kiro/hooks/*` /
   `~/.copilot/hooks` (only Claude Code's extension honors its hooks). If the hook never
   fires, use `cage import` / `cage watch` / your own cron instead.
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
export. `cage setup`/`cage init` already writes a `[debug]` block to `.cage/policy.toml`
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
| Agent **absent** from `cage debug` / **"never"** in `cage doctor` | The hook isn't firing (e.g. a VS Code extension) | this is expected — capture that agent with `cage import` / `cage watch` / your own cron |

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
cage watch             # a foreground loop you start and Ctrl-C (no daemon)
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
