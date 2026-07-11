# Restricted environments — running cage where exes are blocked or pip is unavailable

**Status:** design of record (handoff: `docs/cage-handoff-restricted-env.md`).
Companion to [portable-wiring.md](portable-wiring.md), which is the design of
record for the `cage-run` shim this document extends.

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

persists `[wiring] python_launcher = true` in the project `.cage/policy.toml`
and (re)writes **all** wiring so that nothing exe-shaped is ever probed or
executed — everything goes straight through the already-approved Python
interpreter:

| Surface | Standard mode | Launcher mode |
|---|---|---|
| `.cage/bin/cage-run` (committed shim) | PATH → known installs → `python3 -m cage` → exit 0 | `python3 -m cage` → exit 0 (no probe at all) |
| `.cage/bin/cage-run.cmd` (Windows twin) | `where cage` → installs → `py -3 -m cage` → exit 0 | `py -3 -m cage` → exit 0 |
| `~/.copilot/hooks/cage.json` | resolved absolute cage path | `python3 -m cage import …` (bash) / `py -3 -m cage import …` (powershell) |
| `~/.codex/config.toml` MCP | resolved absolute cage path | `python3` / `py` + `["-m", "cage", "mcp"]` |
| `.kiro/settings/mcp.json` | resolved absolute cage path (the documented gitignore-advised exception) | `python3` / `py` + `["-m", "cage", "mcp"]` |
| `.git/hooks/post-commit`, `prepare-commit-msg` | resolved absolute cage path | `python3 -m cage …` / `py -3 -m cage …` |

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
it. Bundled data (default policy, skill assets) reads from inside the archive;
`report`/`attrib`/every derived view is byte-identical to a wheel install over
the same ledger (CI smoke-checks exactly that on the 3-OS matrix, and the
dummyrepo scenario S13 re-checks it on every push).

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
- [ ] Note the exact policy product/mode (AppLocker vs WDAC, audit vs enforce) for the doc.

## What this work never does

- No PyInstaller/frozen binary — an unsigned unknown exe is exactly what these
  endpoints block; it would be the worst artifact for this threat model.
- No code-signing promises, no MSI.
- The standard wiring mode stays the default, byte-for-byte, for everyone else.
