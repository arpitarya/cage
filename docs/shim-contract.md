---
doc: spec — the graphify interceptor behaviour contract
status: current
applies-to: cage/data/shims/graphify (POSIX sh) · cage/data/shims/graphify.cmd (Windows)
---

# The graphify interceptor contract

**What this is:** the one behaviour spec both interceptor twins implement and are
tested against. Two implementations of an unwritten contract drift; this is the
written one.

**Also the first artifact of the [tool-integration-contract](proposals/tool-integration-contract.md)** —
every future tool interceptor implements this same shape, with only the tool name,
the cage verb and the marker strings changing.

Live-interpolated user-facing summary: `cage query graphify-shims`. The decisions this
doc encodes (both twins install on every OS · hand-paired, not templated · contract in
`docs/`, not package data) are recorded in [ADR 0007](adr/0007-graphify-twin-pair-hand-paired-not-templated.md).

- Behaviours **B1–B8** are binding on every twin.
- Divergences **D1–D7** are real and permanent — cmd cannot do what sh does. They are
  recorded, never papered over.
- The anti-recursion proof is at the bottom. It is the reason this doc exists.

---

## B1 — Re-entry guard (both directions)

| side | rule |
|---|---|
| **read** | `CAGE_GRAPHIFY_SHIM=1` in the environment ⇒ **do not meter**; run the real binary directly |
| **write** | the metering branch sets `CAGE_GRAPHIFY_SHIM=1` in the metered child's environment |

**Correction to the WIN-GF handoff:** re-entry skips *metering only*, **not resolution**.
The PATH scan (B2) and the 127 rule (B4) still run. "Straight to the real binary" means
"past the cage branch", not "past the scan" — a re-entrant call with no real binary on
PATH still exits 127 rather than falling back to the bare name.

## B2 — Resolve the real binary by walking PATH, skipping **every** interceptor

- Walk PATH in order. The **first** candidate that exists, is runnable, and is **not** an
  interceptor (B3) wins; stop there.
- Skip **all** interceptors, not just the shim's own directory. Two stacked shims that
  each stripped only their own dir resolved to *each other* and recursed forever.
- Empty PATH entries are skipped. POSIX reads an empty entry as the current directory;
  the twins decline it deliberately (see D3).
- The walk visits each PATH entry at most once and is bounded (B8).

## B3 — An interceptor is identified by **content**, never by filename

Marker strings, matched case-sensitively — any one of them means "this is a cage
interceptor, never select it as the real binary":

```
cage data graphify              # the current capability probe / invocation
cage graphify                   # the pre-rename (adopt-era) form
graphify metering interceptor   # the header self-identification
```

- Every twin must carry at least one marker **in its own text**, so twins skip each other.
- Filename matching is forbidden: on Windows the real binary and the twin can share a
  name, and on any OS a shim can be renamed.
- **Three copies of this predicate exist and move together:** `grep -Eq` in the sh twin ·
  `findstr /C:` in the cmd twin · `pathshim._INTERCEPTOR` in Python. The Python copy is a
  *diagnostic* and sniffs only the first 8 KiB; the two shims scan the whole file, which
  is the safe side (a shim is never mistaken for the real binary).

## B4 — No real binary ⇒ exit **127**

- Print to **stderr**: `graphify: not found - only the metering interceptor shim is on PATH`
- Exit `127`. **Never** fall back to the bare name `graphify` — that re-enters a shim and
  recurses.

## B5 — Meter only when cage can actually do it

Two probes, in order; either failing ⇒ run the real binary unmetered:

1. a `cage` command resolves;
2. `cage data graphify --help` exits 0 (the capability probe — this is what catches a
   renamed verb, the F1 root cause).

The metered form is exactly `cage data graphify -- <REAL> <args…>`.

**Known gap (both twins):** the probe wants a `cage` *command*. Under
`cage setup --python-launcher` (`cage query restricted-env`) there is no `cage` on PATH,
so the interceptor never meters — it degrades to correct, unmetered passthrough.
Deliberately **not** fixed in the cmd twin alone: a one-sided fix is exactly the drift
this contract exists to prevent. Tracked as **GF-LAUNCHER** in
[OPEN-WORK.md](OPEN-WORK.md).

## B6 — Transparent passthrough

stdout, stderr and exit code are identical to invoking the real binary directly, metered
or not. Arguments are forwarded verbatim, including spaces, embedded quotes and `!`.

## B7 — No leaked state, no partial state; delayed expansion is off wherever `%*` is forwarded

- sh: `set -euo pipefail`.
- cmd: `@echo off` + `setlocal`. Delayed expansion (`!var!`) is enabled **only** around
  the PATH-walk (it needs to read a variable set earlier in the same parenthesized `for`
  block, which plain `%var%` cannot do) and is turned back off, via a second `setlocal
  DisableDelayedExpansion`, **before** either line that forwards `%*` to the real binary.
  Delayed expansion active at a forwarding line would eat a literal `!` out of the
  caller's arguments — a real, documented cmd.exe hazard, not a hypothetical one.
- Environment mutations (the B1 stamp, scratch variables) never reach the caller.

## B8 — Resolution is bounded and provably terminating, with no `call`/`goto` back-edge into the walk

The sh twin iterates a fixed word list. The cmd twin walks PATH with a **flat nested
`for`** (directories × PATHEXT entries) — no subroutine call, no `goto` jump back into
the loop. It terminates after at most `len(PATH directories) × len(PATHEXT entries)`
iterations by construction, so no counter is needed.

> **⚠️ Diagnosis corrected 2026-08-02 — an earlier version of this section named the
> wrong cause.** It attributed the real Windows CI failure
> (`Recursion Count=335, Stack Usage=90 percent, ****** BATCH PROCESSING IS ABORTED ******`)
> to a `call :subroutine` + `goto` back-edge leaking cmd.exe stack frames. **That was a
> hypothesis that did not survive.** Rewriting to the flat loop was a real improvement
> but **did not fix the observed failure** — see B8a for the actual cause. The flat `for`
> is retained on its own merits (provable termination, no interpreter bookkeeping to
> trust); it is **not** load-bearing against the recursion abort. Corrected against the
> v0.38.0 CHANGELOG, written by the session that debugged it on real Windows CI.

## B8a — No `<` or `>` anywhere inside a parenthesized block, **including in comments**

**The actual cause of the recursion abort**, and the single most expensive Windows fact
this project has bought. A `rem` comment sitting *inside* the nested `for` block read
`"<candidate>"`. **cmd.exe's parser still tokenizes redirection characters inside a
comment when that comment is nested in a multi-line `(...)` block** — the `<`/`>`
corrupted the block's parsing, which surfaced as the recursion abort on *every*
invocation.

**The rule, binding on this twin and on every future interceptor** (TOOL-SDK's tools
implement this same shape): **comments live outside every parenthesized block.** Never
write `<`, `>`, `|` or `&` inside `(...)`, in code *or* in a `rem`, without escaping —
cmd.exe does not have "comments" in the sense the word implies; `rem` is a command whose
line is still tokenized.

This is invisible on POSIX, invisible in review, and produces an error message that
points at recursion rather than at the character that caused it. **It cost five pushes
and two wrong hypotheses to find** — which is exactly why it is written here rather
than left in a changelog entry. The `where graphify` fail-open fallback is likewise a single small
loop, never a `goto`-driven one.

**Test-harness corollary (also bought on CI):** a Windows test that invokes the twin
must leave enough of `PATH` intact for the shim's own `findstr.exe` / `where.exe`
(`%SystemRoot%\\System32`) to resolve. Wiping `PATH` to the test's tmp dirs makes the
shim fail for a reason that has nothing to do with the shim. Prepend tmp dirs onto the
system dirs — never the whole inherited `PATH` (that risks exposing a real `cage` and
defeating the "cage absent" assumption), and never nothing.

---

## Divergences (cmd vs sh) — real, permanent, documented

| # | divergence | why | consequence |
|---|---|---|---|
| **D1** | `call "%REAL%" %*` then `exit /b %ERRORLEVEL%`, instead of `exec` | cmd has no `exec` | the real binary is a **child process**, not a replacement. Ctrl-C prompts `Terminate batch job (Y/N)?`; one extra process in the tree; a caller signalling by pid signals the batch. Streams and exit code are still identical (B6 holds). |
| **D2** | candidates come from `PATHEXT`; the bare extensionless name is never tried | cmd.exe cannot execute an extensionless file | the POSIX twin is **invisible** to the cmd twin's scan — half the anti-recursion proof |
| **D3** | the current directory is not searched | cmd.exe resolves cwd *before* PATH; the sh twin deliberately declines the POSIX cwd (an empty PATH entry) | a `graphify.cmd` in cwd but not on PATH ⇒ 127 rather than running. Deliberate: twin parity, and no cwd hijack. **Scoped exception:** the pathological-PATH fallback (below) delegates to `where`, which searches cwd first — a fail-open last resort, still content-filtered. |
| **D4** | three `findstr /C:` literals instead of one `grep -E` alternation | findstr has no alternation | identical marker set, OR-ed, case-sensitive in both |
| **D5** | `if exist` only — no execute-bit test | Windows has no execute bit | existence is the whole test |
| **D6** | `%*` instead of `"$@"` | cmd has no argument array | quoting is preserved as *typed*, which is the closest available; this is why delayed expansion must be off (B7) at both lines that forward `%*` |
| **D7** | the B4 message uses an ASCII hyphen where sh uses an em dash | a `.cmd` is read in the console's OEM codepage; an em dash renders as mojibake | one character of the shim's own diagnostic differs. graphify's own output is untouched. |

**Fail-open last resort (cmd only).** If the PATH walk finds nothing — a pathologically
quoted PATH entry the batch tokenizer cannot split, or an empty `PATHEXT` — the twin asks
Windows' own resolver (`where graphify`) before giving up, and filters that list through
the same B3 content check. Better unmetered-but-working than a broken `graphify`.

## Shared warts (kept for parity, not endorsed)

- A **directory** named `graphify`/`graphify.cmd` passes the existence test in both twins;
  the content check then fails, so it is selected and the run fails. Pre-existing in sh;
  the cmd twin keeps parity rather than diverging.
- The Python `pathshim` sniff is capped at 8 KiB while the shims scan whole files, so a
  marker beyond 8 KiB classifies differently. The shims' unbounded scan is the safe side.

## Windows facts that shape the twin

- **graphify is a PyPI distribution (`graphifyy`), not npm.** The WIN-GF handoff assumed
  npm and therefore a real `graphify.cmd`. On Windows, pip/uv writes a console-script
  launcher **`Scripts\graphify.exe`** — so the twin does **not** share a filename with the
  real binary.
- **`.EXE` precedes `.CMD` in the default `PATHEXT`.** Resolution is *directory-major,
  extension-minor*: every extension is tried in one PATH directory before moving to the
  next. So cage's `<root>\bin\graphify.cmd` wins over a `Scripts\graphify.exe` **only**
  because `bin\` comes earlier on PATH. **Never install the twin into the same directory
  as `graphify.exe`** — there `.exe` wins and interception is silently off.
- `.ps1` is absent from the default `PATHEXT`, which is why the twin is not PowerShell.

## Why recursion is impossible

Four independent mechanisms; any one of them suffices:

1. **Content skip (B3)** — no interceptor can ever be selected as the real binary, in
   either twin.
2. **Structural blindness (D2)** — the cmd twin only ever considers PATHEXT candidates and
   the sh twin only ever considers the extensionless name, so a `bash + cmd` pair
   *cannot* select each other even if content matching were removed.
3. **Re-entry guard (B1)** — a metered child runs with `CAGE_GRAPHIFY_SHIM=1` and takes
   the unmetered branch.
4. **Bounded walk (B8)** — the scan terminates by construction.

Tested in both pairings (`bash + cmd`, `cmd + cmd`) — see `tests/test_win_graphify_shim.py`.
