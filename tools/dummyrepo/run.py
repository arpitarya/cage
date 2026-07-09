"""Dummy sibling-repo scenario runner — the automatable half of
`docs/dummy-repo-test-plan.md` (handoff §9), build-time only.

Scaffolds a disposable repo *beside* the cage checkout, sandboxes every agent
home (env overrides — nothing touches the real machine), plants the sanitized
fixture corpus (`tests/fixtures/transcripts/`) in each agent's real log
location, and runs the scenario matrix S1–S8, printing a pass/fail table.

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
    rows; doctor exits 0. (The hook-fires-live half is manual — see the checklist.)"""
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
    return "wired 4/4 · CLI fixtures → exact rows · doctor ok"


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


def s9_fleet(base: Path) -> str:
    """S9 — 7 simulated machines (5 complete, 1 mid-week gap, 1 missing phase 2):
    bundles → import-merge → exact coverage + gap flag + paired delta; double-import
    idempotent."""
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
    merged = expect_ok(repo, env, "import", *bundles)
    if merged.count("✔") != 7:
        raise Fail(f"expected 7 bundle merge lines, got: {merged.strip()[:200]}")
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
    return "7 machines · gap flagged · pairs 6 · exact −7,000 tok/day delta · re-import idempotent"


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
    "S9": ("P5", s9_fleet),
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
