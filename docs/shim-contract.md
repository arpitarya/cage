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

## B7 — No leaked state, no partial state

- sh: `set -euo pipefail`.
- cmd: `@echo off` + `setlocal`, and **delayed expansion stays off** — it eats `!` out of
  `%*` when the arguments are forwarded.
- Environment mutations (the B1 stamp, scratch variables) never reach the caller.

## B8 — Resolution is bounded and provably terminating

The sh twin iterates a fixed word list. The cmd twin consumes PATH head-first and
additionally caps the walk at 512 directories. A shim that hangs is worse than a shim
that does not meter.

---

## Divergences (cmd vs sh) — real, permanent, documented

| # | divergence | why | consequence |
|---|---|---|---|
| **D1** | `call "%REAL%" %*` then `exit /b %ERRORLEVEL%`, instead of `exec` | cmd has no `exec` | the real binary is a **child process**, not a replacement. Ctrl-C prompts `Terminate batch job (Y/N)?`; one extra process in the tree; a caller signalling by pid signals the batch. Streams and exit code are still identical (B6 holds). |
| **D2** | candidates come from `PATHEXT`; the bare extensionless name is never tried | cmd.exe cannot execute an extensionless file | the POSIX twin is **invisible** to the cmd twin's scan — half the anti-recursion proof |
| **D3** | the current directory is not searched | cmd.exe resolves cwd *before* PATH; the sh twin deliberately declines the POSIX cwd (an empty PATH entry) | a `graphify.cmd` in cwd but not on PATH ⇒ 127 rather than running. Deliberate: twin parity, and no cwd hijack. **Scoped exception:** the pathological-PATH fallback (below) delegates to `where`, which searches cwd first — a fail-open last resort, still content-filtered. |
| **D4** | three `findstr /C:` literals instead of one `grep -E` alternation | findstr has no alternation | identical marker set, OR-ed, case-sensitive in both |
| **D5** | `if exist` only — no execute-bit test | Windows has no execute bit | existence is the whole test |
| **D6** | `%*` instead of `"$@"` | cmd has no argument array | quoting is preserved as *typed*, which is the closest available; this is why B7 forbids delayed expansion |
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
