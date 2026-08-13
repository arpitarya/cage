# Restricted environments — running cage where exes are blocked or pip is unavailable

**Status:** design of record (handoff: `work/archive/v0.22-restricted-env.handoff.md`).
Companion to the committed-shim design of record — `cage query portable-wiring` and
[PLAN.md §5.3](PLAN.md) (the standalone `portable-wiring.md` doc was folded into those
two during the v0.36 hookless doc sweep; this file was dropped in the same sweep and is
restored here because eight source files still cite it by path).

Locked-down endpoints — finance/enterprise Windows fleets with AppLocker or WDAC
policies — commonly block **unknown executables**, including the `Scripts\cage.exe`
launcher that pip generates in a user-writable path. Some of the same machines
also block pip/PyPI entirely. Cage never structurally needs its exe (`py -m cage`
is fully equivalent), and its `dependencies = []` design makes a single-file
distribution nearly free. This page describes the three tiers, what each solves,
and what none of them can promise.

## Tier 1 — python-launcher wiring mode (installed, but the exe is blocked)

```
cage setup --python-launcher --all
```

persists `[wiring] python_launcher = true` in the project `.cage/cage.toml`
and (re)writes **all** wiring so that nothing exe-shaped is ever probed or
executed — everything goes straight through the already-approved Python
interpreter:

| Surface | Standard mode | Launcher mode |
|---|---|---|
| `.cage/bin/cage-run` (committed shim) | PATH → known installs → `python3 -m cage` → exit 0 | `python3 -m cage` → exit 0 (no probe at all) |
| `.cage/bin/cage-run.cmd` (Windows twin) | `where cage` → installs → `py -3 -m cage` → exit 0 | `py -3 -m cage` → exit 0 |
| `~/.copilot/hooks/cage.json` | resolved absolute cage path | `python3 -m cage import …` (bash) / `py -3 -m cage import …` (powershell) |
| `.kiro/settings/mcp.json` | resolved absolute cage path (the documented gitignore-advised exception) | `python3` / `py` + `["-m", "cage", "mcp"]` |
| `.git/hooks/post-commit`, `prepare-commit-msg` | resolved absolute cage path | `python3 -m cage …` / `py -3 -m cage …` |

(Codex support — `~/.codex/config.toml` MCP — was removed completely in v0.33.0; the
row above described it while it existed and is gone with it.)

Committed files are unchanged either way — they reference the shim, and the shim
*is* the mode. The fail-open contract is identical in both modes: cage not
importable ⇒ exit 0 silently, agents keep working, no capture.

- **Persisted + idempotent:** the flag is project policy, so a later plain
  `cage setup` (no flag) preserves the mode; re-runs are byte-identical.
  Revert by setting `[wiring] python_launcher = false` (or deleting the key)
  and re-running `cage setup`.
- **`cage doctor`** names the active mode in its portability check
  (`mode: python-launcher · …`) and warns when policy and the on-disk shim
  disagree (flip + forgot to re-run setup).
- **No-rewire escape hatch:** `CAGE_RUN_PYTHON=1` in a hook's environment makes
  the **standard** shim skip the exe probe at runtime and go straight to
  `python3 -m cage` / `py -3 -m cage` — useful to *test* the interpreter path
  before committing to the mode. It is deliberately a runtime-only override: it
  never changes what `cage setup` writes.

### GF-LAUNCHER — CLOSED 2026-08-12: the interceptor reaches cage through the interpreter

**Fixed on POSIX, CI-asserted on Windows.** Both twins gained a second capability arm
(`docs/shim-contract.md` B5b): when no `cage` command resolves, they probe
`python3 -m cage` (POSIX) / `py -3` then `python` (Windows, divergence D8) and meter
through that. Launcher mode no longer silences the shim route.

The probe used to ask *"is there a `cage` command"* when the question it means is
*"can cage run"*. Launcher mode is one way to make those differ; it is not the only one —
arm 2 also covers a `cage.pyz` on `PYTHONPATH`, an unactivated venv, and any
importable-but-not-on-PATH install.

`cage doctor`'s `launcher-gap` check **inverted with the fix**: it no longer warns that
launcher mode means unmetered. It now asks whether the interpreter that wins on PATH can
import cage — the same silent-start class the `kiro-mcp` check exists for — and warns
only when it cannot.

**What this did NOT fix, stated so the gap is not mistaken for closed.** The shim route
is one of several, and the others are untouched:

| invoker | metered in launcher mode? | why |
|---|---|---|
| claude, any surface | yes | transcript route, PATH-independent |
| copilot **CLI** | yes | transcript route |
| copilot **VS Code** | no | store carries the command but no tool result (F2) |
| kiro | no | no graphify detection on the kiro leg at all |
| human, bare terminal call | **yes, now** | the shim route, via arm 2 |

## Tier 2 — `cage.pyz` (no pip, no PyPI access)

Every GitHub release carries a **`cage.pyz`** asset — a stdlib
[zipapp](https://docs.python.org/3/library/zipapp.html) built by CI (never from a
developer laptop) next to a `SHA256SUMS` file. One file, zero dependencies,
Python ≥ 3.11:

```
py cage.pyz --version          # Windows        → cage X.Y.Z (zipapp)
python3 cage.pyz import        # sweep every agent's logs into the ledger
python3 cage.pyz report        # derived views — byte-identical to a pip install
```

`cage --version` and `cage doctor` label a zipapp run explicitly
(`cage X.Y.Z (zipapp)`) so a bug report always says which distribution produced
it. Bundled data (default policy, price tables) reads from inside the archive via
`paths.bundled_data()`; `report`/`attrib`/every derived view is byte-identical to a
wheel install over the same ledger (CI smoke-checks exactly that on the 3-OS
matrix, and the dummyrepo scenario S13 re-checks it on every push).

**The pyz story is pull-based capture** — `import` / `export` / `report` run by
hand or from your own scheduler line. The decided limitation: **wired shims
never embed a pyz path** (it would be machine-specific, breaking the portable-
wiring law), so hooks and MCP servers require an *importable* install — the pyz
on `PYTHONPATH`, or a real pip/mirror install. If you can also
`pip install cage-flux` (Tier 3), hooks work as normal; if the pyz is all you
have, `py cage.pyz import` is the documented path and `cage doctor` (run from
the pyz) reports hooks honestly as pull-based.

**Verify before running** — the release notes and `SHA256SUMS` carry the digest:

```
shasum -a 256 -c SHA256SUMS            # macOS/Linux
CertUtil -hashfile cage.pyz SHA256     # Windows, compare by eye
```

No signing is claimed: the offer is a checksum plus execution mediated by your
already-approved Python interpreter — materially different from an unknown exe
under AppLocker, but see the honesty section below.

## Tier 3 — internal mirror (documentation only)

Organizations with an Artifactory/Nexus PyPI mirror can ingest `cage-flux`
as-is. The review answers are structural:

- `dependencies = []` — nothing transitive to audit.
- Published exclusively by CI over **OIDC trusted publishing** (no stored PyPI
  token anywhere), triggered only by a GitHub release; a version on PyPI always
  has a matching tag + release to diff against.

## The honest caveat: WDAC script-host policies

Some WDAC deployments constrain *script hosts* as well as executables —
Python itself may be blocked, or restricted to signed/allowlisted scripts. In
that posture neither the launcher mode nor the pyz helps, and **`cage doctor`
cannot detect it** (a blocked interpreter never gets to run the check). Check
your endpoint policy; don't assume. Cage deliberately makes no claim past
"interpreter-mediated execution + checksum".

## First locked-down-endpoint validation checklist

Nobody has field-validated this tier on a real WDAC/AppLocker fleet yet (the
same posture as the Windows manual checklist — CI-tested until a participant
runs it). The first validation run should record:

- [ ] `py -3 -m cage --version` works in the constrained shell (interpreter path clears policy).
- [ ] `py cage.pyz --version` prints `cage X.Y.Z (zipapp)` (zipapp execution clears policy).
- [ ] `SHA256SUMS` digest matches the downloaded asset.
- [ ] `cage setup --python-launcher --all` in a test repo; `cage doctor` shows `mode: python-launcher`, no exe-shaped string in any wired file.
- [ ] One real agent turn → `py -3 -m cage import` → `report` shows the row.
- [ ] If the project also uses graphify: confirm `cage doctor`'s `launcher-gap` check
      fires and that this is expected (GF-LAUNCHER, above) — not read as a bug.
- [ ] Note the exact policy product/mode (AppLocker vs WDAC, audit vs enforce) for the doc.

## What this work never does

- No PyInstaller/frozen binary — an unsigned unknown exe is exactly what these
  endpoints block; it would be the worst artifact for this threat model.
- No code-signing promises, no MSI.
- The standard wiring mode stays the default, byte-for-byte, for everyone else.
