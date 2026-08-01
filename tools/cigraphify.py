"""`python -m tools.cigraphify` — the `present` leg of the graphify CI axis (CI-GF).

Both cage CI workflows historically ran with graphify **absent**, so the entire
integration surface — shim interception, receipt push, doctor's liveness checks — was
covered by mocks only, and a WIN-GF-class bug surfaced at *release* rather than at PR.
This runner is the other leg: real graphify, real queries, real ledger.

**It costs nothing.** `graphify update/query` is AST-only — no LLM call, no network — so
running the real binary against a real corpus in CI is $0. The boundary holds: **CI
proves capture and derivation, the lab proves agent adoption.** Anything needing a real
agent turn is paid, and stays cage-lab's job.

**Cross-platform by construction.** The interception check must resolve `graphify` the
way a *shell* does, which is the whole point on Windows (PATHEXT, docs/shim-contract.md)
— so every invocation goes through `shell=True` rather than an argv list. Python's own
`CreateProcess` appends only `.exe` and would never find `graphify.cmd`, i.e. it would
fail the Windows leg for a reason that has nothing to do with cage.

Build-time only: stdlib-only, never imported by cage at runtime, never in the wheel
(`pyproject` packages only `cage*`). It shells out to the installed CLI exactly as a
user would.

**The corpus-sizing rule (learned the hard way — the first draft violated it):** a
graphify query only files a savings receipt when the answer is genuinely cheaper than
the source files it cites (`graphifymeter._meter`: `raw <= 0` or `actual >= raw` ⇒
`outcome="unmeasurable"`, no receipt). The first `tests/fixtures/cicorpus/` draft was
~1.2 KB, and every query against it came back honestly `unmeasurable` — a leg that would
have gone green on the strength of graphify running without any interception ever having
been *proven*, because "0 receipts" and "receipts disabled/broken" render identically
unless something specifically checks for the receipt. **The corpus must stay large
enough that a query is genuinely cheaper than the files it cites, or the leg is vacuous
regardless of how many other checks pass.**

This is enforced, not just written down: `check_bare_graphify_is_intercepted` below
raises `Fail` outright when no savings row lands, or when one lands with a
non-positive saving — an all-`unmeasurable` corpus cannot produce a passing `intercept`
row. `tests/test_cigraphify.py` pins that assertion directly (no real graphify needed —
it monkeypatches the query/ledger-read seams and proves the check refuses to pass on
an empty or zero-saving result), so the vacuous-leg failure mode has a regression test,
not just a comment.

Usage:
    python -m tools.cigraphify              # run every check, print a table
    python -m tools.cigraphify --keep       # keep the sandbox even on success
    python -m tools.cigraphify --path DIR   # sandbox parent
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS = REPO_ROOT / "tests" / "fixtures" / "cicorpus"

# One-word query: identical quoting under sh and cmd, so the two legs really do run the
# same command line rather than two dialects of one.
QUERY = "password"

# cage knobs that must never leak in from the surrounding environment.
STRIP_ENVS = ("CAGE_BASE", "CAGE_LEDGER", "CAGE_DEBUG", "CAGE_DEBUG_LOG",
              "CAGE_CAPTURE", "CAGE_CAPTURE_ON_READ", "CAGE_NOTES_WRITE",
              "CAGE_GRAPHIFY_SHIM", "CAGE_QUIET")


class Fail(Exception):
    """A check failed — recorded and tabulated, never a traceback at the user."""


# ── sandbox ──────────────────────────────────────────────────────────────────────

def _rmtree(path: Path) -> None:
    """`shutil.rmtree` that survives Windows read-only files (same helper shape as
    tools.dummyrepo — a sandbox that cannot be deleted turns a green run red)."""
    import stat

    def _onexc(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_onexc)
    else:
        shutil.rmtree(path, onerror=lambda f, p, e: _onexc(f, p, e))


def _env(sandbox: Path, project: Path, *, on_path: Path | None = None) -> dict:
    """A hermetic environment: HOME inside the sandbox (so `cage setup`'s shell-rc line
    and the global `~/.cage` land there and not on the machine), every inherited cage
    knob stripped, and optionally ``on_path`` prepended so the shim wins resolution."""
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENVS}
    env["HOME"] = str(sandbox / "home")
    env["USERPROFILE"] = str(sandbox / "home")
    env["CAGE_HOME"] = str(sandbox / "home")
    env["PYTHONUTF8"] = "1"
    if on_path:
        env["PATH"] = os.pathsep.join([str(on_path), env.get("PATH", "")])
    del project
    return env


def _sh(cmdline: str, *, cwd: Path, env: dict, check: bool = True) -> subprocess.CompletedProcess:
    """Run ``cmdline`` through the platform shell — the only faithful way to test PATH
    resolution of a bare name (D2/PATHEXT in docs/shim-contract.md)."""
    r = subprocess.run(cmdline, shell=True, cwd=str(cwd), env=env,
                       capture_output=True, text=True, timeout=600)
    if check and r.returncode != 0:
        raise Fail(f"`{cmdline}` exited {r.returncode}\n{r.stdout}\n{r.stderr}")
    return r


def _cage(args: str, *, cwd: Path, env: dict, check: bool = True):
    return _sh(f'"{sys.executable}" -m cage {args}', cwd=cwd, env=env, check=check)


def _savings_rows(project: Path) -> list[dict]:
    out = []
    for p in sorted((project / ".cage" / "ledger" / "savings").rglob("*.jsonl")):
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                out.append(json.loads(line))
    return out


# ── checks ───────────────────────────────────────────────────────────────────────

def check_setup_installs_both_twins(project: Path, env: dict) -> str:
    """`cage setup` must write the twin pair on every OS — the POSIX shim and the
    Windows `.cmd`. A leg that only ever sees its own twin cannot catch the case this
    whole feature exists for."""
    _cage("setup --project-only", cwd=project, env=env)
    missing = [n for n in ("graphify", "graphify.cmd")
               if not (project / "bin" / n).is_file()]
    if missing:
        raise Fail(f"cage setup did not install: {', '.join(missing)}")
    return "bin/graphify + bin/graphify.cmd"


def check_graph_builds(project: Path, env: dict) -> str:
    """Real graphify, real corpus, $0 — AST only."""
    _sh("graphify update .", cwd=project, env=env)
    graph = project / "graphify-out" / "graph.json"
    if not graph.is_file():
        raise Fail("graphify update produced no graphify-out/graph.json")
    nodes = len(json.loads(graph.read_text(encoding="utf-8")).get("nodes", []))
    return f"{nodes} nodes"


def check_bare_graphify_is_intercepted(project: Path, env: dict) -> str:
    """**The F1 path, and WIN-GF's acceptance test.** With `bin/` first on PATH, a bare
    `graphify query` typed at a shell must reach cage and file a savings row.

    Before the `.cmd` twin this could not hold on Windows at all: PATHEXT has no
    extensionless entry, so the interceptor was structurally unreachable there. This
    assertion is the flipped form — it asserts the fix, not the gap."""
    shim_env = _env(Path(env["HOME"]).parent, project, on_path=project / "bin")
    before = len(_savings_rows(project))
    r = _sh(f"graphify query {QUERY}", cwd=project, env=shim_env)
    if not r.stdout.strip():
        raise Fail("intercepted graphify produced no stdout")
    rows = _savings_rows(project)
    new = [x for x in rows[before:] if x.get("tool") == "graphify"]
    if not new:
        raise Fail("bare `graphify query` filed no savings row — the interceptor did "
                   "not reach cage (PATH/PATHEXT resolution, or a dead probe verb)")
    saved = int(new[0].get("raw_alternative", 0)) - int(new[0].get("actual", 0))
    if saved <= 0:
        raise Fail(f"savings row claims no saving: {new[0]}")
    return f"1 savings row, ~{saved:,} tokens (gross)"


def check_passthrough_is_transparent(project: Path, env: dict) -> str:
    """B6 of the shim contract: metering must not alter what graphify prints. Compared
    against a direct invocation with the shim off PATH.

    **Compared as a sorted line multiset, deliberately.** `graphify query` emits the same
    lines in a different order on every run (verified: raw digests differ across three
    runs, sorted digests are identical). A byte-for-byte comparison of two *separate*
    invocations would therefore test graphify's determinism, not cage's passthrough, and
    would flake in CI roughly always. cage's own determinism law is asserted where it
    belongs — over derived views, in `check_derivation_is_deterministic`."""
    shim_env = _env(Path(env["HOME"]).parent, project, on_path=project / "bin")
    through = _sh(f"graphify query {QUERY}", cwd=project, env=shim_env)
    direct = _sh(f"graphify query {QUERY}", cwd=project, env=env)
    if sorted(through.stdout.splitlines()) != sorted(direct.stdout.splitlines()):
        raise Fail("stdout content differs between the metered and direct runs")
    if through.returncode != direct.returncode:
        raise Fail("exit code differs between the metered and direct runs")
    return f"{len(through.stdout.splitlines())} lines identical (as a set) + same exit"


def check_doctor_reports_live(project: Path, env: dict) -> str:
    shim_env = _env(Path(env["HOME"]).parent, project, on_path=project / "bin")
    res = json.loads(_cage("doctor --json", cwd=project, env=shim_env, check=False).stdout)
    checks = {c["name"]: c for c in res.get("checks", [])}
    for name in ("interceptor", "path-interceptor"):
        if name in checks and checks[name]["level"] == "fail":
            raise Fail(f"doctor `{name}` is failing on a healthy install: "
                       f"{checks[name]['detail']}")
    return "interceptor + path-interceptor not failing"


def check_a_killed_shim_reports_dead(project: Path, env: dict) -> str:
    """The F1 regression: a shim whose capability probe names a removed verb runs
    graphify unmetered and silently. Doctor must call that a **failure**, and
    `cage setup` must heal it."""
    shim_env = _env(Path(env["HOME"]).parent, project, on_path=project / "bin")
    shim = project / "bin" / ("graphify.cmd" if os.name == "nt" else "graphify")
    original = shim.read_bytes()
    shim.write_bytes(original.replace(b"cage data graphify --help",
                                      b"cage graphify --help"))
    try:
        res = json.loads(_cage("doctor --json", cwd=project, env=shim_env,
                               check=False).stdout)
        levels = {c["name"]: c["level"] for c in res.get("checks", [])}
        if "fail" not in (levels.get("interceptor"), levels.get("path-interceptor")):
            raise Fail(f"a dead interceptor did not fail doctor: {levels}")
        _cage("setup --project-only", cwd=project, env=shim_env)
        if shim.read_bytes() != original:
            raise Fail("`cage setup` did not heal the dead interceptor")
    finally:
        shim.write_bytes(original)
    return "dead ⇒ doctor fail, then healed by `cage setup`"


def check_derivation_is_deterministic(project: Path, env: dict) -> str:
    """Same ledger + same policy ⇒ same table, twice. And the present leg must add
    **only** savings rows: graphify files receipts, never calls, so the calls table stays
    byte-identical to an absent leg's."""
    a = _cage("report --no-import --csv", cwd=project, env=env, check=False)
    b = _cage("report --no-import --csv", cwd=project, env=env, check=False)
    if a.stdout != b.stdout:
        raise Fail("two `cage report --csv` runs over one ledger disagree")
    calls = project / ".cage" / "ledger"
    stray = [p.name for p in calls.glob("calls*.jsonl")]
    if stray:
        raise Fail(f"the graphify leg produced call rows, not just savings: {stray}")
    return "report reproducible; savings-only, no call rows"


CHECKS = (
    ("setup", check_setup_installs_both_twins),
    ("graph", check_graph_builds),
    ("intercept", check_bare_graphify_is_intercepted),
    ("passthrough", check_passthrough_is_transparent),
    ("doctor-live", check_doctor_reports_live),
    ("doctor-dead", check_a_killed_shim_reports_dead),
    ("determinism", check_derivation_is_deterministic),
)


# ── runner ───────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.cigraphify", description=__doc__)
    ap.add_argument("--path", type=Path, default=None, help="sandbox parent")
    ap.add_argument("--keep", action="store_true", help="keep the sandbox on success")
    args = ap.parse_args(argv)

    if not shutil.which("graphify"):
        print("cigraphify: graphify is not installed — this is the `present` leg and it "
              "has nothing to test. The `absent` leg is the gate that always runs.")
        return 0

    sandbox = (args.path or REPO_ROOT.parent) / f"cage-cigf-{int(time.time())}"
    project = sandbox / "proj"
    project.mkdir(parents=True)
    (sandbox / "home").mkdir(parents=True)
    for src in sorted(CORPUS.glob("*.py")):
        shutil.copy2(src, project / src.name)
    env = _env(sandbox, project)

    print(f"▸ cage CI graphify leg — sandbox {sandbox}")
    print(f"  graphify: {shutil.which('graphify')}")
    rows, failed = [], 0
    for name, fn in CHECKS:
        try:
            rows.append((name, "PASS", fn(project, env)))
        except Exception as exc:  # noqa: BLE001 — every failure is tabulated
            failed += 1
            rows.append((name, "FAIL", str(exc).replace("\n", " ")[:300]))
    width = max(len(n) for n, _, _ in rows)
    for name, status, detail in rows:
        print(f"  {'✔' if status == 'PASS' else '✗'} {name.ljust(width)}  {detail}")
    print(f"\n{len(rows) - failed}/{len(rows)} checks passed")

    if failed == 0 and not args.keep:
        _rmtree(sandbox)
    elif failed:
        print(f"sandbox kept for inspection: {sandbox}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
