"""Dummy sibling-repo scenario runner — the automatable half of
`docs/dummy-repo-test-plan.md` (handoff §9), build-time only.

Scaffolds a disposable repo *beside* the cage checkout, sandboxes every agent
home (env overrides — nothing touches the real machine), plants the sanitized
fixture corpus (`tests/fixtures/transcripts/`) in each agent's real log
location, and runs the scenario matrix S1–S10, printing a pass/fail table.

Same rules as `tools/skillgen`: **stdlib-only, never imported by cage at
runtime, never in the wheel** (`pyproject` packages only `cage*`). It shells
out to `python -m cage` exactly as a user would — no in-process shortcuts —
so what passes here is the CLI contract, not a test double. Clocks are fine
here (the default sandbox name is timestamped): this is a dev tool, not a
derived view; cage's determinism law applies to what *cage* prints, which S8
asserts byte-for-byte.

Scenario slots not yet backed by a shipped phase (S3–S7) render PENDING with
their phase, and the steps that need a live agent (a real CLI prompt, a real
VS Code extension turn) print as an explicit MANUAL checklist — never skipped
silently (handoff §9 acceptance rule).

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
HOME_ENVS = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR", "KIRO_HOME",
             "CAGE_VSCODE_USER")
# Inherited cage knobs that must never leak into the sandbox.
STRIP_ENVS = ("CAGE_BASE", "CAGE_LEDGER", "CAGE_DEBUG", "CAGE_DEBUG_LOG", "CAGE_CAPTURE",
              "CAGE_HUMAN_RATE", "CAGE_NOTES_WRITE")

# Content-bearing key/marker strings that must never appear in a ledger row
# (counts-never-content). The fixture logs deliberately carry stripped-content
# placeholders — if one leaks into the ledger, capture copied content.
PII_MARKERS = ("content stripped", '"prompt"', '"message"', '"text"', '"summary"')

AGENTS = ("claude", "codex", "copilot", "kiro")


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


def ledger_rows(repo: Path) -> list[dict]:
    rows = []
    for shard in sorted((repo / ".cage" / "ledger").glob("calls*.jsonl")):
        for line in shard.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def assert_exact_rows(repo: Path, specs: list[dict]) -> None:
    expected, volatile = [], {}
    for spec in specs:
        expected.extend(spec["rows"])
        for r in spec["rows"]:
            volatile[r["id"]] = spec["volatile"]
    actual = []
    for row in ledger_rows(repo):
        row = dict(row)
        for v in volatile.get(row["id"], ()):
            if not row.pop(v, None):
                raise Fail(f"row {row['id']} missing volatile field {v!r}")
        actual.append(row)
    a = sorted(actual, key=lambda r: r["id"])
    e = sorted(expected, key=lambda r: r["id"])
    if a != e:
        raise Fail(f"imported rows != fixture expectation ({len(a)} vs {len(e)} rows; "
                   "first diff: " + next((f"{x} != {y}" for x, y in zip(a, e) if x != y),
                                         "row-count mismatch")[:400])


def assert_pii_clean(repo: Path) -> None:
    for f in sorted((repo / ".cage" / "ledger").glob("*.jsonl")):
        text = f.read_text(encoding="utf-8")
        for marker in PII_MARKERS:
            if marker in text:
                raise Fail(f"PII marker {marker!r} found in {f.name} — counts-never-content violated")


def shard_bytes(repo: Path) -> bytes:
    return b"".join(f.read_bytes() for f in sorted((repo / ".cage" / "ledger").glob("calls*.jsonl")))


# ── scenarios ────────────────────────────────────────────────────────────────

def s1_cli(base: Path) -> str:
    """S1 — per agent × CLI: wiring reports all four; planted CLI logs import to exact
    rows; doctor exits 0; a simulated teammate clone gets portable wiring (no absolute
    paths, the committed shim resolves). (The hook-fires-live half is manual.)"""
    repo, env = make_sandbox(base, "s1-cli")
    expect_ok(repo, env, "init")
    for agent in AGENTS:
        expect_ok(repo, env, "setup", "--wire-only", f"--{agent}")
    status = expect_ok(repo, env, "setup", "--status")
    missing = [a for a in AGENTS if a not in status]
    if missing:
        raise Fail(f"setup --status omits agent(s): {missing}")
    specs = fixture_specs("cli")
    plant(specs, env)
    expect_ok(repo, env, "import")
    assert_exact_rows(repo, specs)
    assert_pii_clean(repo)
    expect_ok(repo, env, "doctor")
    clone_note = _clone_simulation(base, repo, env)
    return f"wired 4/4 · CLI fixtures → exact rows · doctor ok · {clone_note}"


def _clone_simulation(base: Path, repo: Path, env: dict) -> str:
    """Portable-wiring acceptance (plan §5): copy the wired testbed to a new path the
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
    expect_ok(repo, env, "init")
    specs = fixture_specs("vscode")
    plant(specs, env)
    expect_ok(repo, env, "import")
    assert_exact_rows(repo, specs)
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

    # (a) malformed policy.toml — import degrades to the bundled default + logs it;
    #     doctor flags the policy check as FAIL (exit 1).
    repo, env = make_sandbox(base, "s3-bad-policy")
    env["CAGE_DEBUG"] = "1"
    expect_ok(repo, env, "init")
    (repo / ".cage" / "policy.toml").write_text("[debug]\n[debug]\n", encoding="utf-8")
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
    expect_ok(repo, env, "init")
    blocker = repo / "blocker"
    blocker.write_text("", encoding="utf-8")
    env["CAGE_LEDGER"] = str(blocker / "ledger")  # parent is a file → every append fails
    plant(fixture_specs("cli")[:1], env)
    expect_ok(repo, env, "import")  # still exit 0 — fail-open
    if "ledger.append" not in _debug_contexts(repo):
        raise Fail("unwritable ledger: no ledger.append line in debug.log")
    del env["CAGE_LEDGER"]
    checks.append("unwritable-ledger")

    # (c) truncated shard tail — reads stay tolerant, report exits 0.
    repo, env = make_sandbox(base, "s3-truncated")
    expect_ok(repo, env, "init")
    plant(fixture_specs("cli"), env)
    expect_ok(repo, env, "import")
    shard = next(iter(sorted((repo / ".cage" / "ledger").glob("calls*.jsonl"))))
    with shard.open("a", encoding="utf-8") as fh:
        fh.write('{"id": "c_torn", "ts": "2026-06-14T')  # crash mid-append
    expect_ok(repo, env, "report")
    checks.append("truncated-shard")

    # (d) empty log — imports 0 rows, no error.
    repo, env = make_sandbox(base, "s3-empty-log")
    expect_ok(repo, env, "init")
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
    expect_ok(repo, env, "init")
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


# Seeder for S5 — run *inside* the sandbox with cage's own row factories (schema/
# ledger/tasks), so the scenario exercises the real substrate, not a hand-rolled
# imitation. 5 agent-only tasks (totals 10.5k–14.5k tok), 5 graphify (4.5k–6.5k,
# one spanning June+July shards), plus a 2-task group the min-n gate must refuse.
# (The handoff's S5 sketch said 3+3, which predates MIN_COMPARE_N=5 — a 3-task
# group would itself be refused, so the runner seeds 5+5.)
_S5_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema, tasks
root = Path(sys.argv[1])
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")
def call(tid, tin, tout, ts):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=tin, tokens_out=tout, task=tid, session=f"s-{tid}", ts=ts, **M))
def receipt(tid, tool, ts):
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=1000, actual=100, task=tid, ts=ts))
def close(tid, ts):
    tasks.record(root, tid, outcome="ok", ts=ts, snapshot=False)
for i, tin in enumerate((10000, 11000, 12000, 13000, 14000)):
    call(f"plain-{i}", tin, 500, f"2026-06-1{i}T10:00:00Z"); close(f"plain-{i}", f"2026-06-1{i}T18:00:00Z")
for i, tin in enumerate((4000, 4500, 6000, 6500)):
    tid = f"graph-{(0, 1, 3, 4)[i]}"
    call(tid, tin, 500, f"2026-06-2{i}T10:00:00Z"); receipt(tid, "graphify", f"2026-06-2{i}T10:00:00Z")
    close(tid, f"2026-06-2{i}T18:00:00Z")
call("graph-2", 3000, 250, "2026-06-28T10:00:00Z")
call("graph-2", 2000, 250, "2026-07-02T10:00:00Z")   # cross-month pair
receipt("graph-2", "graphify", "2026-06-28T10:00:00Z"); close("graph-2", "2026-07-02T18:00:00Z")
for i, tin in enumerate((3000, 3200)):
    tid = f"both-{i}"
    call(tid, tin, 500, f"2026-06-0{i + 1}T10:00:00Z")
    receipt(tid, "graphify", f"2026-06-0{i + 1}T10:00:00Z"); receipt(tid, "fux", f"2026-06-0{i + 1}T10:00:00Z")
    close(tid, f"2026-06-0{i + 1}T18:00:00Z")
"""


def s5_compare(base: Path) -> str:
    """S5 — seeded task groups: `cage compare` exact medians, delta tagged estimated
    with the observational caveat, n=2 group refused, byte-identical re-run."""
    repo, env = make_sandbox(base, "s5-compare")
    expect_ok(repo, env, "init")
    r = _sh([sys.executable, "-c", _S5_SEED, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S5 seeding failed: {r.stderr.strip()[:300]}")
    out = expect_ok(repo, env, "compare")
    for needle in ("12,500", "5,500", "insufficient data (n=2 < 5)",
                   "-7,000 tok · -$0.0350 per task (median, estimated)",
                   "not a controlled experiment"):
        if needle not in out:
            raise Fail(f"compare output missing {needle!r}")
    if expect_ok(repo, env, "compare") != out:
        raise Fail("cage compare not byte-identical across two runs")
    return "exact medians · delta estimated + caveat · n=2 refused · byte-identical"


# Seeder for S6 — history first, then the estimate→record→run→close loop happens
# through the real CLI (`cage estimate --record`, `cage outcome`), so the scenario
# proves the shipped verbs, not library internals.
_S6_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema, tasks
root, phase = Path(sys.argv[1]), sys.argv[2]
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")
def call(tid, tin, ts):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=tin, tokens_out=500, task=tid, session=f"s-{tid}", ts=ts, **M))
if phase == "history":
    for i, tin in enumerate((10000, 11000, 12000, 13000, 14000)):
        call(f"hist-{i}", tin, f"2026-06-1{i}T10:00:00Z")
        tasks.record(root, f"hist-{i}", outcome="ok", ts=f"2026-06-1{i}T18:00:00Z",
                     snapshot=False, label="bugfix")
else:  # the estimated tasks actually run
    call("new-in-band", 12100, "2026-07-01T10:00:00Z")
    call("new-over", 19500, "2026-07-02T10:00:00Z")
"""


def s6_estimate(base: Path) -> str:
    """S6 — estimate → --record → run → close → calibration exact hit-rate."""
    repo, env = make_sandbox(base, "s6-estimate")
    expect_ok(repo, env, "init")
    r = _sh([sys.executable, "-c", _S6_SEED, str(repo), "history"], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S6 seeding failed: {r.stderr.strip()[:300]}")
    out = expect_ok(repo, env, "estimate", "--label", "bugfix")
    for needle in ("n = 5 matching closed tasks", "median 12,500 · IQR 11,500–13,500",
                   "modeled"):
        if needle not in out:
            raise Fail(f"estimate output missing {needle!r}")
    if cage(repo, env, "estimate", "--label", "nope").stdout.find("insufficient history") < 0:
        raise Fail("estimate did not refuse thin history")
    for tid in ("new-in-band", "new-over"):
        expect_ok(repo, env, "estimate", "--label", "bugfix", "--record", tid)
    r = _sh([sys.executable, "-c", _S6_SEED, str(repo), "run"], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S6 run-phase seeding failed: {r.stderr.strip()[:300]}")
    for tid in ("new-in-band", "new-over"):
        expect_ok(repo, env, "outcome", tid, "--label", "bugfix")
    cal = expect_ok(repo, env, "calibration")
    for needle in ("n = 2 closed tasks with estimates",
                   "in-band hit-rate: 50% (1/2", "measured"):
        if needle not in cal:
            raise Fail(f"calibration output missing {needle!r}")
    if expect_ok(repo, env, "calibration") != cal:
        raise Fail("cage calibration not byte-identical across two runs")
    return "band exact · refusal · --record→close loop · 50% hit-rate exact"


# Seeder for S7 — a clearly net-positive tool (graphify: 10k tokens saved per
# receipt, $0 own cost) and a clearly net-negative one (pricey-ml: $0.005 saved
# per receipt vs $0.50 own cost), receipts linked to priced calls.
_S7_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema
root = Path(sys.argv[1])
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")
def seed(tool, tid, saved, ts, cost=0.0):
    call = schema.make_call(tokens_in=1000, tokens_out=100, task=tid,
                            session=f"s-{tid}", ts=ts, **M)
    ledger.append_row(root, "calls", call)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool=tool, raw_alternative=saved + 100, actual=100, task=tid, call=call["id"],
        ts=ts, meta={"tool_cost_usd": cost} if cost else {}))
for i in range(8):
    seed("graphify", f"t-{i}", 10000, f"2026-06-1{i}T10:00:00Z")
    seed("pricey-ml", f"c-{i}", 1000, f"2026-06-1{i}T10:00:00Z", cost=0.5)
"""


def s7_verdict(base: Path) -> str:
    """S7 — verdict on seeded net-positive / net-negative tools + the honest
    insufficient-data path; inputs render with method tags; byte-identical."""
    repo, env = make_sandbox(base, "s7-verdict")
    expect_ok(repo, env, "init")
    r = _sh([sys.executable, "-c", _S7_SEED, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S7 seeding failed: {r.stderr.strip()[:300]}")
    pos = expect_ok(repo, env, "verdict", "graphify")
    for needle in ("graphify is SAVING", "/mo net (modeled)", "(modeled)",
                   "computes no new statistics"):
        if needle not in pos:
            raise Fail(f"SAVING verdict missing {needle!r}")
    neg = expect_ok(repo, env, "verdict", "pricey-ml")
    if "pricey-ml is COSTING" not in neg or "break-even" not in neg:
        raise Fail("COSTING verdict wrong for the net-negative tool")
    ghost = expect_ok(repo, env, "verdict", "ghost-tool")
    if "INSUFFICIENT DATA" not in ghost:
        raise Fail("missing insufficient-data path for a receipt-less tool")
    if expect_ok(repo, env, "verdict", "graphify") != pos:
        raise Fail("cage verdict not byte-identical across two runs")
    return "SAVING + COSTING + INSUFFICIENT DATA · tags rendered · byte-identical"


# Seeder for S9 — one simulated machine ledger per argv name. Markers carry
# historical timestamps (the CLI stamps "now", which would leave June rows
# unphased), so seeding goes through the library; export/import/report run
# through the real CLI. 7 machines per the min-n gate: the handoff's "3
# simulated machines" sketch predates MIN_COMPARE_N=5 (the S5 precedent).
_S9_SEED = """
import sys
from pathlib import Path
from cage import ledger, machine, schema, study
root, kind = Path(sys.argv[1]), sys.argv[2]
(root / ".cage").mkdir(parents=True, exist_ok=True)
machine.ensure(root)
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")
def call(tin, ts):
    ledger.append_row(root, "calls", schema.make_call(
        tokens_in=tin, tokens_out=500, session="s", ts=ts, **M))
study.start(root, "baseline", ts="2026-06-01T00:00:00Z")
for d in ("01", "02", "03"):
    call(12000, f"2026-06-{d}T10:00:00Z")
study.stop(root, ts="2026-06-03T23:59:59Z")
if kind != "missing":
    study.start(root, "plugin", ts="2026-06-08T00:00:00Z")
    days = ("08", "10") if kind == "gap" else ("08", "09", "10")
    for d in days:
        call(5000, f"2026-06-{d}T10:00:00Z")
    study.stop(root, ts="2026-06-10T23:59:59Z")
"""


# Machine 8's markers only — its *calls* are never pre-imported: they exist solely
# as an on-disk Claude transcript, so the bundle's completeness rests entirely on
# export's own sweep (the capture-only / VS-Code-extension fleet participant).
_S9_SWEEP_SEED = """
import sys
from pathlib import Path
from cage import machine, study
root = Path(sys.argv[1])
(root / ".cage").mkdir(parents=True, exist_ok=True)
machine.ensure(root)
study.start(root, "baseline", ts="2026-06-01T00:00:00Z")
study.stop(root, ts="2026-06-20T23:59:59Z")
"""


def s9_fleet(base: Path) -> str:
    """S9 — 8 simulated machines (5 complete, 1 mid-week gap, 1 missing phase 2,
    1 import-never machine that relies solely on export's all-agent sweep):
    bundles → import-merge → exact coverage + gap flag + paired delta;
    double-import idempotent."""
    repo, env = make_sandbox(base, "s9-fleet")
    expect_ok(repo, env, "init")
    bundles = []
    for i in range(1, 8):
        kind = "gap" if i == 6 else ("missing" if i == 7 else "full")
        mroot = base / f"s9-machine-{i}"
        r = _sh([sys.executable, "-c", _S9_SEED, str(mroot), kind], cwd=base, env=env)
        if r.returncode != 0:
            raise Fail(f"S9 machine seed failed: {r.stderr.strip()[:300]}")
        out = str(base / f"s9-bundle-{i}.zip")
        menv = {**env, "CAGE_BASE": str(mroot / ".cage")}
        expect_ok(mroot, menv, "export", "--study", out, "--no-import")
        bundles.append(out)
    # machine 8: no prior `cage import` ever ran — its two calls live only in a
    # planted Claude transcript, and `export --study` (no --no-import) must sweep
    # them into the bundle itself, recording the sweep in the manifest.
    mroot8 = base / "s9-machine-8"
    r = _sh([sys.executable, "-c", _S9_SWEEP_SEED, str(mroot8)], cwd=base, env=env)
    if r.returncode != 0:
        raise Fail(f"S9 machine-8 seed failed: {r.stderr.strip()[:300]}")
    claude8 = base / "s9-machine-8-claude-home"
    spec = next(s for s in fixture_specs("cli") if s["agent"] == "claude")
    dst = claude8 / spec["plant"]
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(spec["dir"] / spec["log"], dst)
    out8 = str(base / "s9-bundle-8.zip")
    menv8 = {**env, "CAGE_BASE": str(mroot8 / ".cage"),
             "CLAUDE_CONFIG_DIR": str(claude8)}
    swept = expect_ok(mroot8, menv8, "export", "--study", out8)
    if "self-refreshed: +2 call(s)" not in swept:
        raise Fail(f"machine-8 export did not self-refresh: {swept.strip()[:200]}")
    bundles.append(out8)
    merged = expect_ok(repo, env, "import", *bundles)
    if merged.count("✔") != 8:
        raise Fail(f"expected 8 bundle merge lines, got: {merged.strip()[:200]}")
    if "merged 2 calls" not in merged or "swept +2 at export" not in merged:
        raise Fail("machine-8 bundle did not carry its sweep record into the "
                   f"analyst's import: {merged.strip()[:300]}")
    report = expect_ok(repo, env, "study", "report")
    for needle in ("⚠ gap days: 2026-06-09", "MISSING — no rows in this phase",
                   "n=6 machines",
                   "-7,000 tok/day · -$0.0350/day per machine (estimated)",
                   "not a randomized experiment"):
        if needle not in report:
            raise Fail(f"study report missing {needle!r}")
    before = shard_bytes(repo)
    again = expect_ok(repo, env, "import", *bundles)
    if "merged 0 calls" not in again or shard_bytes(repo) != before:
        raise Fail("double bundle import was not idempotent")
    if expect_ok(repo, env, "study", "report") != report:
        raise Fail("study report not byte-identical across two runs")
    assert_pii_clean(repo)
    return ("8 machines · gap flagged · pairs 6 · exact −7,000 tok/day delta · "
            "import-never machine self-refreshed via export sweep · re-import idempotent")


# Seeder for S10 — 5 closed tasks whose calls carry known gap_ms (2 derived
# minutes each at the default 10-min cap) + a graphify receipt per task so
# verdict has a tool to judge. Library-seeded like S5 (historic timestamps);
# the transcript-capture half goes through the real `cage import`.
_S10_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema, tasks
root = Path(sys.argv[1])
M = dict(route="chat", provider="anthropic", model="claude-opus-4-8", agent="claude-code")
for i in range(5):
    tid = f"attn-{i}"
    call = schema.make_call(
        tokens_in=1000, tokens_out=100, task=tid, session=f"s-{tid}",
        ts=f"2026-06-1{i}T10:00:00Z", gap_ms=120000, **M)
    ledger.append_row(root, "calls", call)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=1000, actual=100, task=tid,
        call=call["id"], ts=f"2026-06-1{i}T10:00:00Z"))
    tasks.record(root, tid, outcome="ok", ts=f"2026-06-1{i}T18:00:00Z", snapshot=False)
"""

# A synthetic Claude transcript with one known 90 s turn gap (user replies 90 s
# after the previous assistant turn ends) — 1.5 derived minutes once imported.
_S10_TRANSCRIPT = "\n".join((
    '{"type":"user","cwd":"/tmp/cage-testbed","timestamp":"2026-06-20T10:00:00Z","message":{"role":"user","content":"[content stripped — counts only]"}}',
    '{"type":"assistant","uuid":"f1a2b3c4-d5e6-0001-0000-000000000001","timestamp":"2026-06-20T10:00:05Z","cwd":"/tmp/cage-testbed","message":{"role":"assistant","model":"claude-opus-4-8","content":[{"type":"text","text":"[content stripped — counts only]"}],"usage":{"input_tokens":100,"output_tokens":10}}}',
    '{"type":"user","cwd":"/tmp/cage-testbed","timestamp":"2026-06-20T10:01:35Z","message":{"role":"user","content":"[content stripped — counts only]"}}',
    '{"type":"assistant","uuid":"e9d8c7b6-a5f4-0002-0000-000000000002","timestamp":"2026-06-20T10:01:40Z","cwd":"/tmp/cage-testbed","message":{"role":"assistant","model":"claude-opus-4-8","content":[{"type":"text","text":"[content stripped — counts only]"}],"usage":{"input_tokens":200,"output_tokens":20}}}',
)) + "\n"


def s10_attention(base: Path) -> str:
    """S10 — derived human attention (plan §4.10): a seeded transcript with a known
    turn gap imports to exact derived minutes; seeded gap_ms tasks show exact minutes
    in human/compare/verdict (with --agent-only suppression); attesting a task proves
    the attested-beats-derived precedence; calibration --human scores the heuristic
    exactly; the derived view is byte-identical across runs."""
    repo, env = make_sandbox(base, "s10-attention")
    expect_ok(repo, env, "init")
    # transcript capture through the real import path (90 s gap → 1.5 min)
    tdir = Path(env["CLAUDE_CONFIG_DIR"]) / "projects" / "-tmp-cage-testbed"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "session-s10gap.jsonl").write_text(_S10_TRANSCRIPT, encoding="utf-8")
    expect_ok(repo, env, "import")
    r = _sh([sys.executable, "-c", _S10_SEED, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S10 seeding failed: {r.stderr.strip()[:300]}")

    # derived minutes exact in cage human: 5 tasks × 2 min + 1.5 min transcript
    hum = expect_ok(repo, env, "human")
    for needle in ("derived attention", "derived (turn-gaps, capped)", "cap 10 min",
                   "11.5", "never summed"):
        if needle not in hum:
            raise Fail(f"cage human missing {needle!r}")
    if expect_ok(repo, env, "human") != hum:
        raise Fail("cage human not byte-identical across two runs")

    # compare: total-cost line over the 5 closed tasks (10 derived min @ $80/hr)
    cmp_out = expect_ok(repo, env, "compare")
    for needle in ("total cost: agent", "human 10 min × $80/hr",
                   "derived (turn-gaps, capped) 10 min"):
        if needle not in cmp_out:
            raise Fail(f"cage compare missing {needle!r}")
    if "total cost" in expect_ok(repo, env, "compare", "--agent-only"):
        raise Fail("--agent-only did not suppress the compare total-cost line")

    # verdict: composes the same axis ledger-wide (10 + 1.5 loose transcript minutes)
    vd = expect_ok(repo, env, "verdict", "graphify")
    for needle in ("graphify is SAVING", "human 11.5 min × $80/hr"):
        if needle not in vd:
            raise Fail(f"cage verdict missing {needle!r}")
    if "total cost" in expect_ok(repo, env, "verdict", "graphify", "--agent-only"):
        raise Fail("--agent-only did not suppress the verdict total-cost line")

    # attest one task → attested (4 min) beats derived (2 min), reference kept
    expect_ok(repo, env, "outcome", "attn-0", "--minutes", "4")
    cmp2 = expect_ok(repo, env, "compare")
    for needle in ("human 12 min × $80/hr",       # 4 attested + 4×2 derived
                   "attested 4 min", "never summed",
                   "derived ref on attested tasks: 2 min (not summed)"):
        if needle not in cmp2:
            raise Fail(f"post-attest compare missing {needle!r}")

    # attest the rest → calibration --human scores derived/attested = 2/4 exactly
    for i in range(1, 5):
        expect_ok(repo, env, "outcome", f"attn-{i}", "--minutes", "4")
    cal = expect_ok(repo, env, "calibration", "--human")
    for needle in ("n = 5 tasks with both", "derived/attested ratio: median 0.5",
                   "IQR 0.5–0.5", "measured"):
        if needle not in cal:
            raise Fail(f"calibration --human missing {needle!r}")
    below = expect_ok(repo, env, "calibration", "--human")
    if below != cal:
        raise Fail("calibration --human not byte-identical across two runs")
    assert_pii_clean(repo)
    return ("transcript gap → 1.5 min · tasks exact 10 min · attested beats derived · "
            "ratio 0.5 exact · --agent-only clean")


# Seeder for S11 — the field-report shape: an empty-provider router key
# (`copilot/auto`, what the VS Code Copilot store stamps) and an unknown-vendor
# model, both genuinely UNPRICED (no est_cost_usd — transcript calls carry none).
_S11_SEED = """
import sys
from pathlib import Path
from cage import ledger, schema
root = Path(sys.argv[1])
for i in range(3):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="", model="copilot/auto", tokens_in=15000,
        tokens_out=2000, agent="copilot", ts=f"2026-07-0{i+1}T10:00:00Z",
        call_id=f"c_auto{i}"))
ledger.append_row(root, "calls", schema.make_call(
    route="chat", provider="mistral", model="mistral-large-3", tokens_in=1000000,
    tokens_out=200000, agent="codex", ts="2026-07-02T10:00:00Z", call_id="c_m1"))
"""

_S11_BACKDATE = """
import sys
from pathlib import Path
from cage import pricestoml
pricestoml.update_meta(Path(sys.argv[1]), {"prices_version": "2020-01-01"})
"""


def s11_prices(base: Path) -> str:
    """S11 — pricing management (plan §3.3): seeded unpriced calls surface with
    exact counts + fix lines; `prices set`/`alias` reprice the report to exact
    expected USD (idempotent, ledger untouched); a backdated [meta] triggers the
    sync recommendation in list/doctor; `sync --update` restamps; byte-identical."""
    repo, env = make_sandbox(base, "s11-prices")
    expect_ok(repo, env, "init")
    r = _sh([sys.executable, "-c", _S11_SEED, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S11 seeding failed: {r.stderr.strip()[:300]}")

    # 1. unpriced: exact grouping, exact fix lines, deterministic
    unp = expect_ok(repo, env, "prices", "unpriced")
    for needle in ("—/copilot/auto   3 calls   51,000 tokens",
                   "mistral/mistral-large-3   1 calls   1,200,000 tokens",
                   "cage prices alias - 'copilot/auto' --to <provider>/<model>",
                   "cage prices set mistral 'mistral-large-3' --input <IN> --output <OUT>",
                   "4 calls (1,251,000 tokens) billing $0",
                   "cage never fetches prices"):
        if needle not in unp:
            raise Fail(f"prices unpriced missing {needle!r}")
    if expect_ok(repo, env, "prices", "unpriced") != unp:
        raise Fail("prices unpriced not byte-identical across two runs")

    # 2. set (validated, idempotent) + alias (target must be an exact row)
    shards = shard_bytes(repo)
    set_out = expect_ok(repo, env, "prices", "set", "mistral", "mistral-large-3",
                        "--input", "2", "--output", "6", "--cache-read", "0.2")
    if "before: (none)" not in set_out or "re-price immediately" not in set_out:
        raise Fail(f"prices set output unexpected: {set_out[:200]}")
    again = expect_ok(repo, env, "prices", "set", "mistral", "mistral-large-3",
                      "--input", "2", "--output", "6", "--cache-read", "0.2")
    if "no change" not in again:
        raise Fail("prices set is not idempotent")
    expect_ok(repo, env, "prices", "alias", "-", "copilot/auto",
              "--to", "anthropic/claude-sonnet-4-6")

    # 3. report re-prices to exact expected USD; the ledger was never rewritten
    rep = expect_ok(repo, env, "report", "--by", "model")
    for needle in ("$3.2000",     # mistral: 1M×$2 + 200k×$6 per MTok
                   "$0.2250",     # auto→sonnet-4-6: 45k×$3 + 6k×$15 per MTok
                   "$3.4250",     # total
                   "priced by alias (explicit routing — policy [alias]): "
                   "copilot/auto → anthropic/claude-sonnet-4-6"):
        if needle not in rep:
            raise Fail(f"repriced report missing {needle!r}")
    if "UNPRICED" in rep:
        raise Fail("report still shows UNPRICED after set+alias")
    if shard_bytes(repo) != shards:
        raise Fail("repricing rewrote the ledger — it must be derive-time only")
    if "every recorded call prices" not in expect_ok(repo, env, "prices", "unpriced"):
        raise Fail("prices unpriced did not come up clean after set+alias")

    # 4. backdated [meta] → the sync recommendation in list and doctor; --update restamps
    r = _sh([sys.executable, "-c", _S11_BACKDATE, str(repo)], cwd=repo, env=env)
    if r.returncode != 0:
        raise Fail(f"S11 meta backdate failed: {r.stderr.strip()[:300]}")
    lst = expect_ok(repo, env, "prices", "list")
    if "bundled prices are newer (" not in lst or "cage prices sync" not in lst:
        raise Fail("prices list did not recommend sync for a stale [meta]")
    if "bundled prices are newer (" not in expect_ok(repo, env, "doctor"):
        raise Fail("doctor did not recommend sync for a stale [meta]")
    if "bundled prices are newer (" not in expect_ok(repo, env, "prices", "sync"):
        raise Fail("prices sync dry-run did not carry the recommendation")
    if "[meta] restamped" not in expect_ok(repo, env, "prices", "sync", "--update"):
        raise Fail("prices sync --update did not restamp [meta]")
    lst2 = expect_ok(repo, env, "prices", "list")
    if "bundled prices are newer (" in lst2:
        raise Fail("recommendation survived the restamp")
    if expect_ok(repo, env, "prices", "list") != lst2:
        raise Fail("prices list not byte-identical across two runs")
    if expect_ok(repo, env, "report", "--by", "model") != rep:
        raise Fail("report not byte-identical across two runs")
    assert_pii_clean(repo)
    return ("unpriced exact + fix lines · set/alias reprice to $3.4250 exact · "
            "ledger untouched · stale meta → sync rec · restamp clears it")


def s8_determinism(base: Path) -> str:
    """S8 — determinism sweep: derived views byte-identical across runs, and
    CAGE_DEBUG=1 does not change any derived output."""
    repo, env = make_sandbox(base, "s8-det")
    expect_ok(repo, env, "init")
    specs = fixture_specs("cli")
    plant(specs, env)
    expect_ok(repo, env, "import")
    views = (("report",), ("report", "--by", "model"), ("attrib",), ("matrix",),
             ("budget",), ("roi",))
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


# id → (phase that ships it, callable or None-if-pending)
SCENARIOS: dict[str, tuple[str, object]] = {
    "S1": ("P0", s1_cli),
    "S2": ("P0", s2_vscode),
    "S3": ("P1", s3_broken_setups),
    "S4": ("P1", s4_bundle),
    "S5": ("P2", s5_compare),
    "S6": ("P3", s6_estimate),
    "S7": ("P4", s7_verdict),
    "S8": ("P0", s8_determinism),
    "S11": ("pricing", s11_prices),
    "S9": ("P5", s9_fleet),
    "S10": ("attention", s10_attention),
}

MANUAL_CHECKLIST = """\
MANUAL steps (need a live agent — run per docs/dummy-repo-test-plan.md §3/§4/§7):
  [ ] §3 per CLI agent: one real prompt → `cage report` shows the row live (hook fired)
  [ ] §3 same prompt twice → deduped, no double count
  [ ] §4 per VS Code extension: one real prompt → NO row before `cage import`
      (hooks silent under the extension), row appears after `cage import`
  [ ] §7 agent edit + commit → post-commit resolves a `hooked` provenance row;
      `cage origin <sha>` names the agent\
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
