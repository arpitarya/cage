"""The PATH-winning graphify interceptor — the shim that *actually runs* (B-fix-1/2).

`wiringscan` answers "is this root's wiring live?". That is the wrong question for the
graphify interceptor, because the interceptor is a **PATH** mechanism: the one that runs
is whichever `graphify` the shell resolves first, and it can live in a *different
project's* `bin/` — outside every root cage scans. That gap is not hypothetical. On a
real machine an adopt-era shim in another repo won on PATH, probed the pre-rename
pre-rename bare `graphify` verb (now `cage data graphify`), failed its own capability
guard, fell through to `exec "$REAL"`,
and ran graphify **unmetered and silently** for nine days while `cage doctor`, run
inside cage, reported ✅ (the finding was filed 2026-07-30 as OPEN-WORK §B2; the queue is
now an index and that section is gone — the mechanism is `wiringscan.py` and
`cage query stale-wiring`).

So this module resolves `graphify` **the way the shell does** — walk `PATH`, first
executable wins — and classifies that one file:

  ``absent``    no `graphify` on PATH at all; nothing to intercept, nothing to report
  ``live``      the winner is a cage interceptor naming live verbs
  ``dead``      the winner is a cage interceptor naming a verb the parser rejects —
                capture is silently off. A doctor **failure**, never a warning
  ``shadowed``  this root has an interceptor but a *different* file wins — advisory,
                and the message names **both** paths
  ``foreign``   the winner is not cage-written (typically the real graphify binary):
                reported, **never touched**

`dead` and `foreign` are deliberately distinct. A dead cage shim means *cage's own
wiring is broken*; a foreign winner means metering is off *by absence*. Merging them
would report the same severity for two different problems with two different fixes.

**The detector is the live parser, never `verbmap.REMOVED`** — `cage adopt` was removed
outright rather than renamed, so it is absent from `REMOVED` and a grep against it would
miss the very artifact this module exists for. `REMOVED` supplies the fix-hint only.
The liveness oracle itself is `wiringscan.is_live_verb`; nothing is re-derived here.

**Read-only and side-effect-free by construction.** The resolved file is never executed
— executing it could not distinguish "verb dead" from "cage absent" anyway, which is the
whole bug — and no import is ever triggered. PII: paths and verbs only.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import NamedTuple

from cage import wiringscan

# The shim's own predicate, in Python. `data/shims/graphify` carries the same expression
# as a `grep -Eq` because it must stay zero-dep shell — an intentional duplicate of the
# kind `CHARS_PER_TOKEN` already has in the third-party shims, and the two must be
# changed together. It matches BOTH the current form (`cage data graphify`) and the
# pre-rename adopt-era one (the bare `graphify` verb, or the header comment), so
# a stale shim can never be misclassified as the real binary and quietly excused.
_INTERCEPTOR = re.compile(r"cage (?:data )?graphify|graphify metering interceptor")

# A shim is a small shell script and its marker sits in the first ~2 KiB. Capping the
# read keeps classifying a multi-megabyte real binary to one block, and keeps this a
# *sniff* rather than a scan of somebody else's executable.
_SNIFF_BYTES = 8192


class PathShim(NamedTuple):
    """What the shell would run for `graphify`, and whether cage can meter it."""
    state: str                      # absent | live | dead | shadowed | foreign
    winner: str                     # the resolved path ("" when absent)
    verbs: tuple[str, ...] = ()     # the dead verb path, when state == "dead"
    fix_tail: str = ""              # verbmap replacement tail ("" when removed outright)
    root_shim: str = ""             # this root's bin/graphify, when it exists
    managed_root: str = ""          # the cage-managed root owning the winner ("" = none)
    others: tuple[str, ...] = ()    # further `graphify` files on PATH, in shell order

    @property
    def interceptor(self) -> bool:
        return self.state in ("live", "dead")

    @property
    def healable(self) -> bool:
        """May `cage setup` rewrite this file? Only a **dead cage-written** shim inside
        a **cage-managed root**. Everything else is named, never written — silently
        editing another project's files is exactly the class of action cage refuses."""
        return self.state == "dead" and bool(self.managed_root)


# ── resolution (exactly what the shell does) ────────────────────────────────────

def _candidates(name: str, env: dict[str, str] | None = None) -> list[str]:
    """The file names a bare ``name`` can resolve to, **in this OS's resolution order**.

    On Windows that is the PATHEXT list and *only* the PATHEXT list: cmd.exe cannot
    execute an extensionless file, so including the bare name would let the POSIX twin
    (`bin/graphify`) be reported as the interceptor that runs when in fact nothing
    resolves — the exact false ✅ this module exists to prevent. Cage's Windows
    interceptor is `graphify.cmd` (docs/adr/0004_graphify.md); the real graphify is a PyPI
    console script, so on Windows it is `Scripts\\graphify.exe`.

    Order matters twice over: resolution is **directory-major, extension-minor** (every
    extension is tried in one PATH directory before moving to the next), and `.EXE`
    precedes `.CMD` in the default PATHEXT — so a twin sharing a directory with
    `graphify.exe` would lose to it. `executables()` reproduces both orderings."""
    if os.name != "nt":
        return [name]
    exts = (env or os.environ).get("PATHEXT", ".COM;.EXE;.BAT;.CMD").split(os.pathsep)
    return [name + e.lower() for e in exts if e]


def executables(name: str = "graphify", env: dict[str, str] | None = None) -> list[Path]:
    """Every `name` on PATH **in shell resolution order** — index 0 is the one that runs.

    Deliberately a plain PATH walk rather than `shutil.which`: `which` answers only "the
    first one", and `shadowed` needs to know a second exists. Duplicate directories are
    collapsed the way a shell effectively does (a repeated dir cannot win twice)."""
    raw = (env or os.environ).get("PATH", "")
    out: list[Path] = []
    seen: set[str] = set()
    for d in raw.split(os.pathsep):
        if not d or d in seen:
            continue
        seen.add(d)
        for cand in _candidates(name, env):
            p = Path(d) / cand
            try:
                if p.is_file() and os.access(p, os.X_OK):
                    out.append(p)
                    break
            except OSError:
                continue
    return out


def sniff(path: Path) -> str:
    """The first `_SNIFF_BYTES` of `path` as text; "" on any read error. Never executed,
    never fully read — fail-open, because a diagnostic must not be the thing that breaks."""
    try:
        with path.open("rb") as fh:
            return fh.read(_SNIFF_BYTES).decode("utf-8", errors="ignore")
    except OSError:
        return ""


def is_interceptor(path: Path) -> bool:
    """Is this file a cage-written graphify interceptor (current **or** adopt-era)?"""
    return bool(_INTERCEPTOR.search(sniff(path)))


def managed_root(path: Path) -> str:
    """The cage-managed project root owning `path`, or "" if there isn't one.

    Deliberately narrow: exactly the `<root>/bin/graphify[.cmd]` layout `cage setup`
    (and the removed `cage adopt`) writes, with a `<root>/.cage/` beside it. It does **not** walk
    up looking for any `.cage/`, because `~/.cage` is the *global ledger* — a walk would
    declare the whole home directory a cage-managed root and make an unrelated
    `~/bin/graphify` writable by cage. Narrow-and-sure beats broad-and-sorry when the
    consequence is writing to a file cage does not own."""
    if path.parent.name != "bin":
        return ""
    root = path.parent.parent
    if root == Path.home() or not (root / ".cage").is_dir():
        return ""
    return str(root)


# ── classification ──────────────────────────────────────────────────────────────

def classify(root: Path, env: dict[str, str] | None = None) -> PathShim:
    """Resolve `graphify` on PATH and say whether cage can meter what runs.

    Precedence is severity-first: a **dead** winner outranks `shadowed`, because a
    shadowing note about a shim that is itself broken would bury the actual failure."""
    found = executables("graphify", env)
    # This root's own interceptor is the twin THIS OS can actually resolve. On Windows
    # the POSIX copy sits right beside it and can never run, so counting it would report
    # `shadowed` — "put bin/ earlier on PATH" — for a file no PATH order can rescue.
    # A root carrying only the wrong twin has no live interceptor, and `doctorcmd`
    # names that case directly.
    from cage import paths
    shim = root / "bin" / paths.graphify_shim_name()
    root_shim = str(shim) if shim.exists() else ""
    others = tuple(str(p) for p in found[1:])
    if not found:
        return PathShim("absent", "", root_shim=root_shim)

    win = found[0]
    if not is_interceptor(win):
        # Not cage-written. If this root ships an interceptor, the useful fact is that
        # it loses — name both. Otherwise it is simply the real binary winning.
        state = "shadowed" if root_shim and str(win) != root_shim else "foreign"
        return PathShim(state, str(win), root_shim=root_shim, others=others)

    for verbs in wiringscan.verbs_in_shell(sniff(win)):
        if not wiringscan.is_live_verb(verbs):
            return PathShim("dead", str(win), verbs, wiringscan.remediation(verbs),
                            root_shim, managed_root(win), others)

    state = "shadowed" if root_shim and str(win) != root_shim else "live"
    return PathShim(state, str(win), root_shim=root_shim, others=others)
