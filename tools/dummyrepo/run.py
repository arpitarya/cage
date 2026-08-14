"""Dummy sibling-repo scenario runner — the automatable half of
`work/archive/v0.16-dummy-repo-test.plan.md` (handoff §9), build-time only.

Scaffolds a disposable repo *beside* the cage checkout, sandboxes every agent
home (env overrides — nothing touches the real machine), plants the sanitized
fixture corpus (`tests/fixtures/transcripts/`) in each agent's real log
location, and runs the scenario matrix, printing a pass/fail table. The live set is
`SCENARIOS` — ids are never reused, so it is deliberately gappy (S5/S6/S7/S9/S10/S11/
S14/S15 were retired with the subsystems they tested).

Build-time only: **stdlib-only, never imported by cage at runtime, never in the
wheel** (`pyproject` packages only `cage*`). It shells
out to `python -m cage` exactly as a user would — no in-process shortcuts —
so what passes here is the CLI contract, not a test double. Clocks are fine
here (the default sandbox name is timestamped): this is a dev tool, not a
derived view; cage's determinism law applies to what *cage* prints, which S8
asserts byte-for-byte.

A scenario slot not yet backed by a shipped phase renders PENDING with its phase,
and the steps that need a live agent (a real CLI prompt, a real VS Code extension
turn) print as an explicit MANUAL checklist — never skipped silently (handoff §9
acceptance rule).

Usage:
    python -m tools.dummyrepo                 # run everything automatable
    python -m tools.dummyrepo --path DIR      # sandbox parent (default ../cage-dummy-<ts>)
    python -m tools.dummyrepo --keep          # keep the sandbox even on success
    python -m tools.dummyrepo --scenarios S1,S8
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS = REPO_ROOT / "tests" / "fixtures" / "transcripts"

# Sandboxed agent-home env vars (the same overrides the pytest corpus uses) —
# every one points inside the sandbox so no run can read or write real machine data.
HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR", "KIRO_HOME",
             "CAGE_VSCODE_USER")
# Inherited cage knobs that must never leak into the sandbox.
STRIP_ENVS = ("CAGE_BASE", "CAGE_LEDGER", "CAGE_DEBUG", "CAGE_DEBUG_LOG", "CAGE_CAPTURE",
              "CAGE_NOTES_WRITE")

# Content-bearing key/marker strings that must never appear in a ledger row
# (counts-never-content). The fixture logs deliberately carry stripped-content
# placeholders — if one leaks into the ledger, capture copied content.
PII_MARKERS = ("content stripped", '"prompt"', '"message"', '"text"', '"summary"')

AGENTS = ("claude", "copilot", "kiro")


class Fail(Exception):
    """A scenario assertion failed — recorded, never a traceback to the user."""


# ── sandbox ──────────────────────────────────────────────────────────────────

def _rmtree(path: Path) -> None:
    """`shutil.rmtree` that survives Windows: git object files are read-only there and
    plain rmtree dies with WinError 5 — clear the read-only bit and retry the delete.
    (`onexc` is the 3.12+ spelling; `onerror` covers 3.11.)"""
    import stat

    def _force(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=_force)
    else:  # pragma: no cover — 3.11 CI lane
        shutil.rmtree(path, onerror=lambda f, p, e: _force(f, p, e))


def _sh(cmd: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    # encoding pinned: text=True alone decodes with the locale codec (cp1252 on
    # Windows), which chokes on cage's ✔/·/⚠ glyphs — utf-8 + replace keeps the
    # runner OS-independent without masking real output differences.
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True,
                          encoding="utf-8", errors="replace")


def make_sandbox(base: Path, name: str) -> tuple[Path, dict]:
    """A fresh dummy repo + isolated agent homes + env. Returns (repo, env)."""
    repo = base / name
    homes = base / f"{name}-homes"
    repo.mkdir(parents=True)
    homes.mkdir(parents=True)
    (repo / "src").mkdir()
    (repo / "README.md").write_text("# cage dummy testbed\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
    for cmd in (["git", "init", "-q"], ["git", "add", "-A"],
                ["git", "-c", "user.email=dummy@cage.test", "-c", "user.name=cage-dummy",
                 "commit", "-qm", "seed"]):
        r = _sh(cmd, cwd=repo)
        if r.returncode != 0:
            raise Fail(f"sandbox git scaffold failed: {' '.join(cmd)}: {r.stderr.strip()}")
    env = {k: v for k, v in os.environ.items() if k not in STRIP_ENVS}
    env["PYTHONUTF8"] = "1"  # child `python -m cage` pipes stay UTF-8 on Windows (glyph asserts)
    env["CAGE_HOME"] = str(homes / "global-home")
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    for e in HOME_ENVS:
        env[e] = str(homes / f"home-{e.lower()}")
    return repo, env


def cage(repo: Path, env: dict, *args: str) -> subprocess.CompletedProcess:
    return _sh([sys.executable, "-m", "cage", *args], cwd=repo, env=env)


def expect_ok(repo: Path, env: dict, *args: str) -> str:
    r = cage(repo, env, *args)
    if r.returncode != 0:
        raise Fail(f"`cage {' '.join(args)}` exited {r.returncode}: "
                   f"{(r.stderr or r.stdout).strip()[:300]}")
    return r.stdout


# ── fixture planting + ledger reading ────────────────────────────────────────

def fixture_specs(surface: str) -> list[dict]:
    specs = []
    for agent in AGENTS:
        d = CORPUS / agent / surface
        spec = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        spec["agent"], spec["dir"] = agent, d
        specs.append(spec)
    return specs


def plant(specs: list[dict], env: dict) -> None:
    for spec in specs:
        dst = Path(env[spec["env"]]) / spec["plant"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(spec["dir"] / spec["log"], dst)


def _read_jsonl(shard: Path) -> list[dict]:
    rows = []
    for line in shard.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _ledger_rows_at(ledger_dir: Path) -> list[dict]:
    """`calls*.jsonl` rows. **No built-in agent writes these any more** (P5 retired
    claude's and copilot's legs, KIRO-CALLS-LEG kiro's) — what still lands here is a
    `[sources.<name>]` custom tool, which is exactly what S17 reads."""
    rows = []
    for shard in sorted(ledger_dir.glob("calls*.jsonl")):
        rows.extend(_read_jsonl(shard))
    return rows


def ledger_rows(repo: Path) -> list[dict]:
    return _ledger_rows_at(repo / ".cage" / "ledger")


#: The one source per agent whose rows are that agent's token basis — a local mirror of
#: `ledger.SPEND_SOURCES` (the runner shells out and must not import cage, so the table is
#: copied; if the two disagree, `ledger.py` is right). **Filtering is not optional here:**
#: a metric file carries the SAME facts at two grains — claude `transcript` (per chat) and
#: `request` (per request), copilot `cli` (cumulative) and `cli-delta` — so summing the
#: file whole double-counts every token, which is exactly what it did before this table
#: existed. Kiro is the one agent with no spend spine at all (`ABSENT_SPINES`); `ide-log`
#: is capture-only, and is named so the relocation KIRO-CALLS-LEG performed can still be
#: proven lossless rather than skipped.
_BASIS_SOURCE: dict[str, tuple[str, ...]] = {
    "claude": ("request",),
    "copilot": ("chat", "cli-delta"),
    "kiro": ("ide-log",),
}


def _metric_rows_at(ledger_dir: Path, agent: str) -> list[dict]:
    """That agent's basis-grain metric rows (`ledger/<agent>/chats-*.jsonl`, v0.51's
    one-directory-per-producer shape) — where the three built-in agents' captured usage
    lives now that no built-in leg writes `calls`."""
    base = ledger_dir / agent
    if not base.is_dir():
        return []
    allowed = _BASIS_SOURCE[agent]
    rows = []
    for shard in sorted(base.glob("chats*.jsonl")):
        rows.extend(r for r in _read_jsonl(shard) if r.get("source", "") in allowed)
    return rows


# Minted fresh every `cage import` sweep (the manifest-row FK, import-ledger plan §4) —
# volatile on every row regardless of what a fixture's own `volatile` list declares, and
# never itself a fixture field, so it is stripped rather than presence-checked.
_ALWAYS_VOLATILE = ("import_id",)


def assert_captured_facts(repo: Path, specs: list[dict], env: dict) -> None:
    """Every spec's captured **token totals** must land in the ledger that agent
    captures into, and no built-in agent may write a `calls` row.

    **Asserted on the facts, not the row shape — the same split, for the same reason, as
    `tests/test_fixture_corpus.py`.** P5 (claude, copilot) and KIRO-CALLS-LEG (kiro)
    retired the transcript→`calls` legs, so the exact-row comparison this helper used to
    make now runs against a permanently empty `calls` glob: it would pass while pinning
    nothing (the basis-change trap CLAUDE.md names). The row *grain* legitimately moved
    (copilot CLI: 2 call rows → 1 `cli-delta` row), so a row count is not asserted either
    — token totals are the invariant that survived the change, verified identical before
    and after P5. `expected.json` keeps its byte-for-byte assertion in the pytest suite,
    pointed at the parsers directly; blessing whatever the new code emits here would have
    thrown away the evidence the corpus exists to hold.

    Kiro routes to the machine ledger, never the project one (ADR-KIRO)."""
    for spec in specs:
        agent = spec["agent"]
        sink = (Path(env["CAGE_HOME"]) / ".cage" / "ledger") if agent == "kiro" else \
            (repo / ".cage" / "ledger")
        where = "machine (kiro, ADR-KIRO)" if agent == "kiro" else "project"
        want_in = sum(r.get("tokens_in", 0) for r in spec["rows"])
        want_out = sum(r.get("tokens_out", 0) for r in spec["rows"])
        got = _metric_rows_at(sink, agent)
        if not got:
            raise Fail(f"{agent}: capture produced no {agent}/chats-*.jsonl rows in the "
                       f"{where} ledger")
        got_in = sum(r.get("tokens_in", 0) for r in got)
        got_out = sum(r.get("tokens_out", 0) for r in got)
        if (got_in, got_out) != (want_in, want_out):
            raise Fail(f"{agent}: captured token totals != fixture expectation in the "
                       f"{where} ledger (in {got_in} vs {want_in}, out {got_out} vs {want_out})")
    # No built-in leg writes a `calls` row any more. Not vacuous: the totals above already
    # proved the same facts DID land, so an empty `calls` here means relocated, not lost.
    if (stray := ledger_rows(repo)):
        raise Fail(f"a built-in agent wrote {len(stray)} `calls` row(s) — the retired "
                   f"leg is back: {sorted({r.get('agent') for r in stray})}")


def assert_pii_clean(repo: Path) -> None:
    # imports.jsonl (cage/manifest.py) is a DELIBERATE, documented exception (import-ledger
    # ADR-CLI, Arpit 2026-07-25): it always captures a best-available human-authored
    # session_name/title, a conscious PII widening scoped to this one local audit file —
    # never a call/receipt/savings row, never read by a derived view. The generic
    # counts-never-content scan below is for those rows; it must not flag a title.
    for f in sorted((repo / ".cage" / "ledger").glob("*.jsonl")):
        if f.name == "imports.jsonl":
            continue
        text = f.read_text(encoding="utf-8")
        for marker in PII_MARKERS:
            if marker in text:
                raise Fail(f"PII marker {marker!r} found in {f.name} — counts-never-content violated")


def shard_bytes(repo: Path) -> bytes:
    """Every ledger shard, for the idempotency checks — `rglob`, not a `calls*` glob, so
    the per-agent metric trees (`ledger/<agent>/chats-*.jsonl`, where captured usage
    actually lands since v0.51) are covered. A `calls`-only glob would compare two empty
    byte strings and pass no matter what a re-import did."""
    base = repo / ".cage" / "ledger"
    return b"".join(f.read_bytes() for f in sorted(base.rglob("*.jsonl")))


# ── scenarios ────────────────────────────────────────────────────────────────

def s1_cli(base: Path) -> str:
    """S1 — per agent × CLI: wiring reports all three; planted CLI logs import to exact
    rows; doctor exits 0; a simulated teammate clone gets portable wiring (no absolute
    paths, the committed shim resolves). (The hook-fires-live half is manual.)"""
    repo, env = make_sandbox(base, "s1-cli")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    for agent in AGENTS:
        expect_ok(repo, env, "setup", "--wire-only", f"--{agent}")
    status = expect_ok(repo, env, "setup", "--status")
    missing = [a for a in AGENTS if a not in status]
    if missing:
        raise Fail(f"setup --status omits agent(s): {missing}")
    specs = fixture_specs("cli")
    plant(specs, env)
    expect_ok(repo, env, "import")
    assert_captured_facts(repo, specs, env)
    assert_pii_clean(repo)
    expect_ok(repo, env, "doctor")
    clone_note = _clone_simulation(base, repo, env)
    return f"wired 3/3 · CLI fixtures → exact rows · doctor ok · {clone_note}"


def _clone_simulation(base: Path, repo: Path, env: dict) -> str:
    """Portable-wiring acceptance (ADR-GRAPHIFY): copy the wired testbed to a new path the
    way a `git clone` would land it — no `.git`, none of the `.cage/.gitignore`d dirs
    (ledger/out/state) — then assert the clone's wiring is portable end-to-end:
    doctor's portability check is clean and the committed shim actually resolves."""
    clone = base / f"{repo.name}-clone"
    shutil.copytree(repo, clone,
                    ignore=shutil.ignore_patterns(".git", "ledger", "out", "state"))
    r = cage(clone, env, "doctor")
    # NB: the exact problem phrase — the kiro-MCP *advice* line legitimately contains
    # the words "machine-absolute" (the documented exception), and is not a flag.
    if "machine-absolute cage path in committed file(s)" in r.stdout:
        raise Fail("clone doctor flags a machine-absolute path — wiring not portable: "
                   + r.stdout[:300])
    if "committed wiring is portable" not in r.stdout:
        raise Fail("clone doctor missing the portability-clean line: " + r.stdout[:300])
    # run the committed shim directly — must resolve cage on this machine and pass
    # args through (POSIX twin here; the .cmd twin on Windows)
    shim = clone / ".cage" / "bin" / "cage-run"
    argv = [str(shim) + ".cmd"] if os.name == "nt" else ["sh", str(shim)]
    rs = _sh(argv + ["--version"], cwd=clone, env=env)
    if rs.returncode != 0 or "cage" not in rs.stdout:
        raise Fail(f"clone shim did not resolve cage: exit {rs.returncode}, "
                   f"out={rs.stdout.strip()[:120]!r}")
    return "clone-sim portable (shim resolves)"


def s2_vscode(base: Path) -> str:
    """S2 — per agent × VS Code: hooks stay unwired (the extension case), planted
    extension-format logs import to exact rows, re-import is byte-identical (cursor)."""
    repo, env = make_sandbox(base, "s2-vscode")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    specs = fixture_specs("vscode")
    plant(specs, env)
    expect_ok(repo, env, "import")
    assert_captured_facts(repo, specs, env)
    before = shard_bytes(repo)
    expect_ok(repo, env, "import")
    if shard_bytes(repo) != before:
        raise Fail("re-import changed the ledger — cursor/id-dedupe failed")
    assert_pii_clean(repo)
    unverified = [s["agent"] for s in specs if not s["format_verified"]]
    return ("extension fixtures → exact rows · re-import idempotent"
            + (f" · stand-in formats (UNVERIFIED): {', '.join(unverified)}" if unverified else ""))


def _debug_contexts(repo: Path) -> str:
    log = repo / ".cage" / "state" / "debug.log"
    return log.read_text(encoding="utf-8") if log.exists() else ""


def s3_broken_setups(base: Path) -> str:
    """S3 — adversarial states: every capture failure stays fail-open (exit 0, no
    traceback) AND leaves an attributable debug.log line under CAGE_DEBUG=1; a broken
    policy is flagged by doctor (exit 1)."""
    checks = []

    # (a) malformed cage.toml — import degrades to the bundled default + logs it;
    #     doctor flags the policy check as FAIL (exit 1).
    repo, env = make_sandbox(base, "s3-bad-policy")
    env["CAGE_DEBUG"] = "1"
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    (repo / ".cage" / "cage.toml").write_text("[debug]\n[debug]\n", encoding="utf-8")
    plant(fixture_specs("cli")[:1], env)  # one claude log is enough
    expect_ok(repo, env, "import")
    if "import.policy" not in _debug_contexts(repo):
        raise Fail("broken policy: no import.policy line in debug.log")
    if cage(repo, env, "doctor").returncode == 0:
        raise Fail("broken policy: doctor did not flag it (expected exit 1)")
    checks.append("bad-policy")

    # (b) unwritable ledger dir — the append fails open and logs ledger.append.
    repo, env = make_sandbox(base, "s3-unwritable")
    env["CAGE_DEBUG"] = "1"
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    blocker = repo / "blocker"
    blocker.write_text("", encoding="utf-8")
    env["CAGE_LEDGER"] = str(blocker / "ledger")  # parent is a file → every append fails
    plant(fixture_specs("cli")[:1], env)
    expect_ok(repo, env, "import")  # still exit 0 — fail-open
    if "ledger.append" not in _debug_contexts(repo):
        raise Fail("unwritable ledger: no ledger.append line in debug.log")
    del env["CAGE_LEDGER"]
    checks.append("unwritable-ledger")

    # (c) truncated shard tail — reads stay tolerant, the view exits 0. Torn on a *metric*
    # shard: since P5/KIRO-CALLS-LEG no built-in agent writes `calls`, so the old
    # `calls*.jsonl` glob matched nothing and died with StopIteration before it could
    # assert anything.
    repo, env = make_sandbox(base, "s3-truncated")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    plant(fixture_specs("cli"), env)
    expect_ok(repo, env, "import")
    shards = sorted((repo / ".cage" / "ledger").rglob("*.jsonl"))
    if not shards:
        raise Fail("truncated-shard: import wrote no ledger shard to tear")
    with shards[0].open("a", encoding="utf-8") as fh:
        fh.write('{"id": "c_torn", "ts": "2026-06-14T')  # crash mid-append
    expect_ok(repo, env, "insights", "chats")
    checks.append("truncated-shard")

    # (d) empty log — imports 0 rows, no error.
    repo, env = make_sandbox(base, "s3-empty-log")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    spec = fixture_specs("cli")[0]
    dst = Path(env[spec["env"]]) / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("", encoding="utf-8")
    out = expect_ok(repo, env, "import")
    if "imported 0 call(s)" not in out:
        raise Fail(f"empty log: expected 0 imports, got: {out.strip()[:120]}")
    checks.append("empty-log")

    return "fail-open + debug-line on: " + ", ".join(checks)


def s4_bundle(base: Path) -> str:
    """S4 — `cage doctor --bundle` produces one archive; PII grep of every member clean."""
    repo, env = make_sandbox(base, "s4-bundle")
    env["CAGE_DEBUG"] = "1"
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    plant(fixture_specs("cli"), env)
    expect_ok(repo, env, "import")
    expect_ok(repo, env, "doctor", "--bundle", "bundle.zip")
    out = repo / "bundle.zip"
    if not out.exists():
        raise Fail("doctor --bundle exited 0 but wrote no archive")
    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        need = {"manifest.json", "doctor.txt", "footprint.txt", "policy-provenance.txt",
                "state/debug.log"}
        if not need <= names:
            raise Fail(f"bundle missing member(s): {sorted(need - names)}")
        blob = b"".join(zf.read(n) for n in names)
    for marker in PII_MARKERS:
        if marker.encode("utf-8") in blob:
            raise Fail(f"PII marker {marker!r} found inside the bundle")
    return f"{len(names)} members · PII grep clean"


def s8_determinism(base: Path) -> str:
    """S8 — determinism sweep: derived views byte-identical across runs, and
    CAGE_DEBUG=1 does not change any derived output."""
    repo, env = make_sandbox(base, "s8-det")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    specs = fixture_specs("cli")
    plant(specs, env)
    expect_ok(repo, env, "import")
    # The surviving read surface. `report` and `insights attrib/matrix/budget/roi` were
    # deleted (SURFACE-CUT v0.50, ADR 0011's money cull) — the determinism law binds
    # whatever cage actually prints, so the sweep follows the surface rather than
    # asserting over dead verbs.
    views = (("insights", "chats"), ("insights", "graphify"), ("insights", "commits"),
             ("insights", "chats", "--csv"), ("insights", "graphify", "--csv"))
    first = {v: expect_ok(repo, env, *v) for v in views}
    for v in views:
        if expect_ok(repo, env, *v) != first[v]:
            raise Fail(f"`cage {' '.join(v)}` not byte-identical across two runs")
    debug_env = {**env, "CAGE_DEBUG": "1"}
    for v in views:
        r = _sh([sys.executable, "-m", "cage", *v], cwd=repo, env=debug_env)
        if r.returncode != 0 or r.stdout != first[v]:
            raise Fail(f"CAGE_DEBUG=1 changed `cage {' '.join(v)}` output")
    return f"{len(views)} views byte-identical · CAGE_DEBUG=1 no-drift"


def s12_launcher(base: Path) -> str:
    """S12 — python-launcher wiring mode (restricted endpoints): the flag persists to
    policy; nothing exe-shaped in any wired file; a flagless re-run preserves the mode
    byte-identically; the shim resolves via the interpreter; doctor names the mode.
    (Hookless: only the committed shim + the per-machine kiro MCP entry carry the
    launcher form now — the copilot/git-hook files are no longer written.)"""
    repo, env = make_sandbox(base, "s12-launcher")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    expect_ok(repo, env, "setup", "--wire-only", "--all", "--python-launcher")
    pol = (repo / ".cage" / "cage.toml").read_text(encoding="utf-8")
    if "python_launcher = true" not in pol:
        raise Fail("[wiring] python_launcher = true not persisted in cage.toml")
    wired = [repo / ".cage" / "bin" / "cage-run",
             repo / ".cage" / "bin" / "cage-run.cmd",
             repo / ".kiro" / "settings" / "mcp.json"]
    for f in wired:
        text = f.read_text(encoding="utf-8")
        for shape in ("cage.exe", "command -v cage", "where cage", ".local/bin/cage"):
            if shape in text:
                raise Fail(f"exe shape {shape!r} in launcher-mode file {f.name}")
    if "-m cage" not in (repo / ".cage" / "bin" / "cage-run").read_text(encoding="utf-8"):
        raise Fail("launcher shim lost the interpreter form")
    before = b"".join(f.read_bytes() for f in wired)
    expect_ok(repo, env, "setup", "--wire-only", "--all")  # no flag — mode must persist
    if b"".join(f.read_bytes() for f in wired) != before:
        raise Fail("flagless setup re-run changed launcher-mode wiring")
    shim = repo / ".cage" / "bin" / "cage-run"
    argv = [str(shim) + ".cmd"] if os.name == "nt" else ["sh", str(shim)]
    rs = _sh(argv + ["--version"], cwd=repo, env=env)  # env carries PYTHONPATH → repo cage
    if rs.returncode != 0 or "cage" not in rs.stdout:
        raise Fail(f"launcher shim did not resolve via the interpreter: exit "
                   f"{rs.returncode}, out={rs.stdout.strip()[:120]!r}")
    doc = expect_ok(repo, env, "doctor")
    if "mode: python-launcher" not in doc:
        raise Fail("doctor does not name the python-launcher mode")
    return "policy persisted · wired files exe-free · flagless re-run identical · shim → interpreter · doctor names mode"


def s13_pyz(base: Path) -> str:
    """S13 — cage.pyz distribution parity (work/restricted-environments.md): the
    zipapp labels itself, reads bundled data from inside the zip, imports the
    fixture corpus, and derives byte-identically to the repo-module run over the
    SAME ledger. $CAGE_PYZ (CI passes the exact release artifact) beats a local
    build. Parity is checked via `insights chats` — `report` was removed in v0.50
    (SURFACE-CUT)."""
    pyz_env = os.environ.get("CAGE_PYZ")
    if pyz_env:
        pyz_path = Path(pyz_env)
        built = "CI artifact"
    else:
        from tools import buildpyz
        pyz_path = buildpyz.build(base / "cage.pyz")
        built = "local build"
    repo, env = make_sandbox(base, "s13-pyz")
    # The zip's cage must win — the archive is sys.path[0], but strip PYTHONPATH
    # anyway so nothing about the parity claim depends on the checkout.
    penv = {k: v for k, v in env.items() if k != "PYTHONPATH"}

    def pyz(*args: str) -> subprocess.CompletedProcess:
        return _sh([sys.executable, str(pyz_path), *args], cwd=repo, env=penv)

    r = pyz("--version")
    if r.returncode != 0 or not r.stdout.strip().endswith("(zipapp)"):
        raise Fail(f"pyz --version missing the zipapp label: {r.stdout.strip()!r} "
                   f"{r.stderr.strip()[:200]!r}")
    if pyz("setup", "--project-only", "--no-graphify").returncode != 0:
        raise Fail("pyz setup (scaffold) failed")
    if pyz("demo").returncode != 0:
        raise Fail("pyz demo failed (bundled policy unreadable from the zip?)")
    specs = fixture_specs("cli")
    plant(specs, env)
    if pyz("import").returncode != 0:
        raise Fail("pyz import failed")
    rep1, rep2 = pyz("insights", "chats"), pyz("insights", "chats")
    if rep1.returncode != 0 or not rep1.stdout:
        raise Fail(f"pyz insights chats failed: {rep1.stderr.strip()[:200]}")
    if rep1.stdout != rep2.stdout:
        raise Fail("pyz insights chats not byte-identical across two runs")
    module_rep = expect_ok(repo, env, "insights", "chats")  # repo checkout over the SAME ledger
    if module_rep != rep1.stdout:
        raise Fail("pyz insights chats differs from the wheel/module output over the same ledger")
    assert_pii_clean(repo)
    return f"zipapp labelled · demo+import ok · insights chats deterministic · wheel↔pyz parity ({built})"


# Seeder for S16 — priced calls so every derived view has real numbers to hold
# byte-identical across the policy apply.
_S16_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema
root = Path(sys.argv[1])
for i in range(2):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-sonnet-5",
        tokens_in=100000, tokens_out=20000, agent="claude",
        ts=f"2026-07-0{i+1}T10:00:00Z", call_id=f"c_s16_{i}"))
"""

# Rewrite the inited policy to the v0.16-era shape (no [meta], no [cleanup], no
# capture.import_before_export — the only non-pricing keys the bundle has gained
# since, per the git history of data/policy.toml) + one hand edit (daily budget).
_S16_STRIP = """
import sys
from pathlib import Path
p = Path(sys.argv[1]) / ".cage" / "cage.toml"
out, skip = [], False
for ln in p.read_text(encoding="utf-8").splitlines(keepends=True):
    s = ln.strip()
    if s in ("[meta]", "[cleanup]"):
        skip = True
        continue
    if skip and s.startswith("["):
        skip = False
    if skip or s.startswith("import_before_export"):
        continue
    out.append(ln)
# [budgets] is opt-in/commented-out in the bundle now (BUD-V, work/archive/
# v0.36-suite-green.handoff.md) and can't demonstrate a customized hand edit — this
# mirrors tests/test_policysync.py's re-point to `[quality] signal`, a bundle-shipped,
# active, scalar-keyed table that survives the v0.16 strip.
p.write_text("".join(out).replace('signal = "task_ok"', 'signal = "task_custom"'),
             encoding="utf-8")
"""


def s16_policy_sync(base: Path) -> str:
    """S16 — project-policy upgrade (CLAUDE.md): a v0.16-shaped policy shows
    exact add/keep categories; `--apply` writes the adds, keeps the hand edit,
    stamps [meta] policy_version, and changes no derived view by one byte;
    the second apply is a byte-identical no-op; doctor/hook hints flip clean."""
    repo, env = make_sandbox(base, "s16-policy-sync")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    r = _sh([sys.executable, "-c", _S16_SEED, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S16 seeding failed: {r.stderr.strip()[:300]}")
    r = _sh([sys.executable, "-c", _S16_STRIP, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S16 policy strip failed: {r.stderr.strip()[:300]}")

    # 1. dry-run: exact categories, deterministic, recommendation on the surfaces
    diff = expect_ok(repo, env, "policy", "diff")
    for needle in ("add (4)",
                   "+ [capture] import_before_export = true",
                   "+ [cleanup] days = 90",
                   "+ [cleanup] enabled = true",
                   "+ [cleanup] warn = true",
                   "keep (1)",
                   '[quality] signal = "task_custom" (bundled "task_ok")',
                   "bundled policy defaults are newer"):
        if needle not in diff:
            raise Fail(f"policy diff missing {needle!r}")
    if expect_ok(repo, env, "policy", "diff") != diff:
        raise Fail("policy diff not byte-identical across two runs")
    if "bundled policy defaults are newer" not in expect_ok(repo, env, "doctor"):
        raise Fail("doctor missing the policy-version recommendation")

    # 2. behavior-neutrality: --apply changes no derived view by one byte
    views = [("insights", "chats"), ("insights", "graphify"), ("insights", "commits")]
    before = [expect_ok(repo, env, *v) for v in views]
    applied = expect_ok(repo, env, "policy", "sync", "--apply")
    for needle in ("✔ [capture] import_before_export = true added",
                   "✔ [cleanup] added (days = 90, enabled = true, warn = true)",
                   "✔ [meta] policy_version stamped"):
        if needle not in applied:
            raise Fail(f"policy sync --apply missing {needle!r}")
    if [expect_ok(repo, env, *v) for v in views] != before:
        raise Fail("--apply changed a derived view — neutrality invariant broken")

    # 3. idempotent apply: second run is a byte-identical no-op
    pol_file = repo / ".cage" / "cage.toml"
    first = pol_file.read_bytes()
    if "already in sync" not in expect_ok(repo, env, "policy", "sync", "--apply"):
        raise Fail("second apply did not report already-in-sync")
    if pol_file.read_bytes() != first:
        raise Fail("second apply rewrote the file — idempotency broken")
    if 'signal = "task_custom"' not in pol_file.read_text(encoding="utf-8"):
        raise Fail("hand-edited [quality] signal was clobbered — customized must be kept")

    # 4. hints flip clean; the hand edit survives in the merged view
    if "project policy defaults are current" not in expect_ok(repo, env, "doctor"):
        raise Fail("doctor still stale after apply")
    assert_pii_clean(repo)
    return ("v0.16 shape → add(4) exact · hand edit kept · apply neutral to the "
            "byte · second apply no-op · doctor hint flips clean")


# id → (phase that ships it, callable or None-if-pending)
def s17_sources(base: Path) -> str:
    """S17 — configurable import paths (plan Phase 4): a custom tool declared in
    `[sources]` imports a claude-format log from a policy-declared path and stamps
    `agent = <name>` (reports split it out); doctor --paths shows the `policy`
    provenance + the custom section + a rejected glob entry; a machine-absolute
    path in an *uncommitted* project policy raises no portability warn."""
    repo, env = make_sandbox(base, "s17-sources")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")

    # Plant a claude-format log at a non-standard path a custom tool points at.
    logs = repo / "router-logs"
    logs.mkdir()
    shutil.copyfile(CORPUS / "claude" / "cli" / "session-c1a2b3.jsonl",
                    logs / "session-c1a2b3.jsonl")

    # Append a custom tool + a rejected glob entry to the project policy. as_posix()
    # keeps the path a valid TOML basic string on Windows (a raw `\` is a TOML escape).
    # A fresh key (not `claude`) for the rejected entry — `cage setup` now materializes
    # `[[sources.claude]]` as an active array-of-tables by default, and redeclaring the
    # same dotted key in a different shape is a TOML parse error, not an override.
    pol = repo / ".cage" / "cage.toml"
    pol.write_text(pol.read_text(encoding="utf-8")
                   + f'\n[sources.myrouter]\npaths = ["{logs.as_posix()}"]\nformat = "claude"\n'
                   + f'\n[sources.badglob]\npaths = ["{repo.as_posix()}/glob-*.jsonl"]\n'
                   + 'format = "claude"\n',
                   encoding="utf-8")

    expect_ok(repo, env, "import")
    rows = ledger_rows(repo)
    if not rows or any(r["agent"] != "myrouter" for r in rows):
        raise Fail(f"custom-tool rows not stamped agent=myrouter: "
                   f"{sorted({r['agent'] for r in rows})}")
    # `report --by agent` was the read side of this assertion and is gone (SURFACE-CUT).
    # The recorded fact — a custom source's rows carry its own agent name — is asserted
    # against the rows above; `insights chats` is the surviving view that must render it.
    chats = expect_ok(repo, env, "insights", "chats")
    if "myrouter" not in chats:
        raise Fail(f"insights chats does not show the custom tool: {chats[:300]!r}")

    paths_out = expect_ok(repo, env, "doctor", "--paths")
    for needle in ("myrouter  (custom tool, format=claude)", "[policy]",
                   "⚠ ignored:", "glob character"):
        if needle not in paths_out:
            raise Fail(f"doctor --paths missing {needle!r}: {paths_out[:400]!r}")
    if "machine-absolute path in a committed" in paths_out:
        raise Fail("portability warned on an uncommitted policy path")

    expect_ok(repo, env, "query", "sources")   # concept entry renders
    assert_pii_clean(repo)
    return ("custom tool → rows agent=myrouter · insights chats shows it · "
            "doctor --paths shows [policy] + custom section + rejected glob · "
            "no false portability warn (uncommitted)")


def s18_stale_wiring(base: Path) -> str:
    """S18 — stale-wiring liveness (docs/stale-wiring.handoff.md): an installed
    artifact naming a verb the CLI no longer accepts is detected by `cage doctor`
    against the live parser, healed by re-running `cage setup`, and the heal is
    idempotent. Black-box: everything through the shipped CLI, nothing imported."""
    repo, env = make_sandbox(base, "s18-stale-wiring")
    expect_ok(repo, env, "setup", "--project-only", "--no-graphify")
    expect_ok(repo, env, "setup", "--wire-only", "--all")

    # Plant a pre-removal Claude hook + a stale graphify interceptor, exactly as v0.27
    # left them on a real machine. Hookless setup no longer writes `.claude/settings.json`
    # (MCP goes in `.mcp.json`), so create the stale file directly — the heal must strip it.
    settings = repo / ".claude" / "settings.json"
    settings.parent.mkdir(parents=True, exist_ok=True)
    settings.write_text(json.dumps({"hooks": {"SessionStart": [{"hooks": [
        {"type": "command", "command": "/old/bin/cage import-claude --project ."}]}]}},
        indent=2) + "\n", encoding="utf-8")
    bin_dir = repo / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "graphify").write_text(
        "#!/usr/bin/env bash\n"
        'if command -v cage >/dev/null 2>&1 && cage graphify --help >/dev/null 2>&1; then\n'
        '  exec cage graphify -- "$REAL" "$@"\n'
        "fi\n", encoding="utf-8")
    (bin_dir / "graphify").chmod(0o755)

    doc = cage(repo, env, "doctor").stdout   # exits 1 by design here
    if "import-claude" not in doc:
        raise Fail("doctor did not report the dead `import-claude` wiring")
    if "import --agent claude" not in doc:
        raise Fail("doctor reported the fault but not its remediation")
    if "UNMETERED" not in doc:
        raise Fail("doctor did not report the dead graphify interceptor")

    expect_ok(repo, env, "setup", "--wire-only", "--all")
    # Hookless heal: a stale cage hook entry is STRIPPED, not rewritten to the current
    # verb (cage no longer wires hooks) — so the dead verb must be gone entirely.
    #
    # **And here it goes with the whole file.** Cage planted nothing else in this
    # settings file, so stripping its entry empties the object, and `claudewire` then
    # drops the emptied `hooks` table and *unlinks* a file it alone reduced to `{}` —
    # otherwise every off-switch would leave a permanent committed diff. An ABSENT file
    # is therefore the strongest possible form of "the dead verb is gone", not a
    # failure: this scenario used to `read_text()` it unconditionally and die with
    # FileNotFoundError on the correct outcome. Assert the removal rather than tolerate
    # it — it is documented behaviour with no other scenario covering it.
    if settings.exists():
        body = settings.read_text(encoding="utf-8")
        if "import-claude" in body:
            raise Fail("re-running setup did not strip the dead cage hook")
        raise Fail("cage reduced settings.json to nothing of anyone's but left the "
                   f"file behind — an empty settings file is a diff with no meaning:\n{body}")
    # The refreshed shim must probe the verb the CLI actually has. `cage data graphify`
    # (what this line pinned) was deleted by SURFACE-CUT and the interceptor was restored
    # in v0.51 as `cage interceptor graphify` — pinning the dead spelling asserted the
    # opposite of the invariant, since a shim naming it is precisely what "stale" means.
    shim = (bin_dir / "graphify").read_text(encoding="utf-8")
    if "cage interceptor graphify" not in shim:
        raise Fail("re-running setup did not refresh the stale graphify interceptor")

    doc2 = cage(repo, env, "doctor").stdout
    if "is not a command" in doc2 or "UNMETERED" in doc2:
        raise Fail(f"doctor still reports dead wiring after the heal:\n{doc2}")
    # Absent reads as b"" on both sides — the file stays removed across a re-heal, which
    # is itself part of "byte-identical" (a re-setup must not resurrect an empty file).
    def wiring_bytes() -> bytes:
        s = settings.read_bytes() if settings.exists() else b""
        return s + (bin_dir / "graphify").read_bytes()

    before = wiring_bytes()
    expect_ok(repo, env, "setup", "--wire-only", "--all")
    if wiring_bytes() != before:
        raise Fail("healing an already-healed tree was not byte-identical")
    return ("dead verb + dead interceptor detected · healed by re-setup "
            "(emptied settings file removed) · idempotent")


# id → (phase that ships it, callable or None-if-pending)
# **Retired, and never to be re-added under the same id** (the S9/S10 precedent — S10 went
# with the human axis, S9 with the fleet study): S5 `insights compare` · S6 `insights
# estimate`/`calibration` · S7 `insights verdict` · S11/S14/S15 the whole `prices` surface
# and the receipt-pricing ladder. Their subject matter was deleted by SURFACE-CUT (v0.50)
# and ADR 0011's money cull, so there is nothing left for them to assert — they are gone
# rather than rewritten, because a scenario retargeted at a different question is a new
# scenario wearing an old id.
SCENARIOS: dict[str, tuple[str, object]] = {
    "S1": ("P0", s1_cli),
    "S2": ("P0", s2_vscode),
    "S3": ("P1", s3_broken_setups),
    "S4": ("P1", s4_bundle),
    "S8": ("P0", s8_determinism),
    "S12": ("restricted", s12_launcher),
    "S13": ("restricted", s13_pyz),
    "S16": ("policy", s16_policy_sync),
    "S17": ("sources", s17_sources),
    "S18": ("stale-wiring", s18_stale_wiring),
}

MANUAL_CHECKLIST = """\
MANUAL steps (need a live agent — capture is pull-based, so a `cage import` is the trigger):
  [ ] per agent: one real prompt → `cage import` then `cage insights chats` shows the row
  [ ] same prompt, import twice → deduped, no double count (cursor + id-dedupe)
  [ ] per VS Code extension: one real prompt → row appears after `cage import`\
"""


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m tools.dummyrepo",
                                 description="cage dummy sibling-repo scenario runner")
    ap.add_argument("--path", help="sandbox parent dir (default: ../cage-dummy-<timestamp>)")
    ap.add_argument("--keep", action="store_true",
                    help="keep the sandbox even when everything passes")
    ap.add_argument("--scenarios", default="all",
                    help="comma-separated ids (default: all), e.g. S1,S8")
    args = ap.parse_args(argv)

    base = Path(args.path) if args.path else (
        REPO_ROOT.parent / f"cage-dummy-{time.strftime('%Y%m%d-%H%M%S')}")
    if base.exists() and any(base.iterdir()):
        print(f"error: sandbox dir {base} exists and is not empty", file=sys.stderr)
        return 1
    wanted = list(SCENARIOS) if args.scenarios == "all" else [
        s.strip().upper() for s in args.scenarios.split(",") if s.strip()]
    unknown = [s for s in wanted if s not in SCENARIOS]
    if unknown:
        print(f"error: unknown scenario(s) {unknown}; known: {list(SCENARIOS)}", file=sys.stderr)
        return 1

    base.mkdir(parents=True, exist_ok=True)
    print(f"sandbox: {base}\n")
    results: list[tuple[str, str, str]] = []
    failed = False
    for sid in wanted:
        phase, fn = SCENARIOS[sid]
        if fn is None:
            results.append((sid, "PENDING", f"ships with phase {phase}"))
            continue
        try:
            results.append((sid, "PASS", fn(base)))
        except Fail as e:
            results.append((sid, "FAIL", str(e)))
            failed = True
        except Exception as e:  # a runner bug, not a cage finding — still a failure
            results.append((sid, "FAIL", f"runner error: {type(e).__name__}: {e}"))
            failed = True

    width = max(len(s) for s, _, _ in results)
    print("scenario results:")
    for sid, verdict, detail in results:
        print(f"  {sid:<{width}}  [{verdict}]  {detail}")
    print()
    print(MANUAL_CHECKLIST)
    if failed or args.keep:
        print(f"\nsandbox kept for inspection: {base}")
    else:
        _rmtree(base)
        print("\nsandbox removed (use --keep to retain).")
    return 1 if failed else 0
