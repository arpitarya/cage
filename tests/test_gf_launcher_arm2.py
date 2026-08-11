"""GF-LAUNCHER verdict B — B5 **arm 2**: no `cage` COMMAND is not the same as no cage.

The probe used to ask *"is there a `cage` command"* when the question it means is
*"can cage run"*. `cage setup --python-launcher` removes the command by design, so under
it **neither twin** could ever meter — and the same miss covers a `cage.pyz` on
`PYTHONPATH`, an unactivated venv, and any importable-but-not-on-PATH install. Arm 2
falls back to `python3 -m cage` (POSIX) / `py -3` then `python` (Windows, divergence D8).

**These tests EXECUTE the POSIX twin**, because the compare doc's verdict says B is
verifiable end to end on POSIX from a dev machine and only CI-asserted on Windows — so
the POSIX half is proven by running it, and the cmd half by the contract tests in
`test_win_graphify_shim.py`. The honest close is *"fixed on POSIX, CI-asserted on
Windows"*, never *"fixed"*.

The failure mode being guarded is the one that made GF-LAUNCHER an item at all: the shim
is installed, sits on PATH, names live verbs, and still meters nothing — silently, since
a shim's output goes nowhere and it fails open to the real binary.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

from cage import ledger, paths

REPO = Path(__file__).resolve().parents[1]
SH = REPO / "cage" / "data" / "shims" / "graphify"

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX twin — sh hosts")

_ANSWER = "NODE store [src=store.py loc=L1 community=0]\n"


def _real(dirpath: Path) -> Path:
    """A stand-in graphify that prints one citing answer — enough for the meter to
    compute a real counterfactual, with no real graphify installed."""
    dirpath.mkdir(parents=True, exist_ok=True)
    real = dirpath / "graphify"
    # A /bin/sh script, not a python one: the "cage unreachable entirely" case below
    # runs with a PATH that deliberately has no `python3` on it, and a real binary that
    # needed python3 to start would fail for the wrong reason.
    real.write_text(f"#!/bin/sh\nprintf '%s' {_ANSWER.strip()!r}\necho\n", encoding="utf-8")
    real.chmod(0o755)
    return real


def _twin(dirpath: Path) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    twin = dirpath / "graphify"
    twin.write_bytes(SH.read_bytes())
    twin.chmod(0o755)
    return twin


def _run(proj: Path, path_dirs: list[Path], *args: str) -> subprocess.CompletedProcess:
    """Invoke the bare name `graphify` through PATH resolution — how a user's shell
    resolves it. PATH carries **no `cage`**: that is the whole scenario. `python3` is
    made to resolve to this interpreter, which can import cage."""
    env = {k: v for k, v in os.environ.items()
           if k not in ("CAGE_GRAPHIFY_SHIM", "CAGE_BASE", "CAGE_LEDGER")}
    env["PATH"] = os.pathsep.join([*(str(d) for d in path_dirs), "/usr/bin", "/bin"])
    env["PYTHONPATH"] = str(REPO)
    # Deliberately NO `CAGE_BASE`: that variable names the cage root *directly*, so
    # setting it to the project would send the receipt to `<proj>/ledger/…` while
    # `ledger.receipts(proj)` reads `<proj>/.cage/ledger/…` — a green-looking harness
    # asserting the wrong tree. The shim resolves the root the way a user's would, by
    # finding `.cage/` from cwd.
    return subprocess.run(["graphify", *args], capture_output=True, text=True,
                          env=env, cwd=str(proj), timeout=120)


def _python3_dir(tmp_path: Path) -> Path:
    """A PATH directory whose `python3` is *this* interpreter — the venv one that can
    import cage. Without it the arm-2 probe would resolve /usr/bin/python3, which
    generally cannot, and the test would assert the old behaviour by accident."""
    d = tmp_path / "py"
    d.mkdir(parents=True, exist_ok=True)
    link = d / "python3"
    link.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    link.chmod(0o755)
    return d


@pytest.fixture
def proj(tmp_path):
    paths.Footprint(tmp_path).ledger.mkdir(parents=True, exist_ok=True)
    (tmp_path / "store.py").write_text("x = 1\n" * 500, encoding="utf-8")
    return tmp_path


@posix_only
def test_arm2_meters_when_no_cage_command_is_on_path(proj, tmp_path):
    """The defect itself. No `cage` anywhere on PATH — exactly what launcher mode
    produces — and a receipt is still filed, because cage is *importable*."""
    real_dir, bin_dir = tmp_path / "real", tmp_path / "bin"
    _real(real_dir)
    _twin(bin_dir)
    r = _run(proj, [bin_dir, real_dir, _python3_dir(tmp_path)], "query", "how")

    assert r.returncode == 0
    assert r.stdout == _ANSWER, "B6: passthrough is sacred, metered or not"
    receipts = [x for x in ledger.receipts(proj) if x.get("tool") == "graphify"]
    assert receipts, (
        "no receipt filed with cage unreachable-by-command but importable — arm 2 did "
        f"not fire. stderr:\n{r.stderr}")
    assert receipts[0]["saved"] > 0


@posix_only
def test_passthrough_is_unchanged_when_cage_is_unreachable_entirely(proj, tmp_path):
    """The other side: neither a `cage` command nor an importable `python3 -m cage`.
    Arm 2 must fall through to plain, unmetered passthrough — never fail, never hang.
    This is the property that keeps the fix on a fail-open path."""
    real_dir, bin_dir = tmp_path / "real", tmp_path / "bin"
    _real(real_dir)
    _twin(bin_dir)
    env = {k: v for k, v in os.environ.items()
           if k not in ("CAGE_GRAPHIFY_SHIM", "CAGE_BASE", "CAGE_LEDGER", "PYTHONPATH")}
    # A NORMAL system PATH minus any `cage`, and with `PYTHONPATH` dropped so the
    # system `python3` cannot import cage either — both arms miss for the real reason.
    #
    # An earlier version of this test cut PATH down to `/bin` to remove `python3`. It
    # HUNG for 120s, and the cause is worth recording: B3's content check shells out to
    # `grep`, which on macOS lives in `/usr/bin`. With `/usr/bin` gone the check errors,
    # every candidate reads as "not an interceptor", and the twin selects ITSELF as the
    # real binary and re-execs forever — the exact recursion B1–B4 claim is impossible.
    # Filed as SHIM-TOOL-DEPS; do not "fix" this test by shortening the timeout.
    env["PATH"] = os.pathsep.join([*(str(d) for d in (bin_dir, real_dir)),
                                   "/usr/bin", "/bin"])
    r = subprocess.run(["graphify", "query", "how"], capture_output=True, text=True,
                       env=env, cwd=str(proj), timeout=120)

    assert r.returncode == 0 and r.stdout == _ANSWER
    assert [x for x in ledger.receipts(proj) if x.get("tool") == "graphify"] == []


@posix_only
def test_arm1_still_wins_first_so_a_standard_install_is_unchanged(proj, tmp_path):
    """Arm 1 is tried first, so a normal install pays no interpreter start. Asserted by
    giving arm 1 a `cage` that RECORDS being called and would never be reached if the
    order were wrong."""
    real_dir, bin_dir, cage_dir = tmp_path / "real", tmp_path / "bin", tmp_path / "cagebin"
    _real(real_dir)
    _twin(bin_dir)
    cage_dir.mkdir()
    marker = tmp_path / "arm1-was-used"
    fake_cage = cage_dir / "cage"
    fake_cage.write_text(
        "#!/bin/sh\n"
        f'printf x >> "{marker}"\n'
        f'exec "{sys.executable}" -m cage "$@"\n', encoding="utf-8")
    fake_cage.chmod(0o755)

    r = _run(proj, [bin_dir, real_dir, cage_dir, _python3_dir(tmp_path)], "query", "how")
    assert r.returncode == 0
    assert marker.exists(), "arm 2 ran before arm 1 — a standard install must not pay it"


def test_both_twins_carry_arm_two_and_the_cmd_twin_declares_d8():
    """ADR 0007's binding rule: a change to one twin is a change to both, or liveness
    detection and the anti-recursion proof drift apart. Runs on every OS on purpose —
    a macOS dev must not be able to leave the cmd twin behind."""
    sh, cmd = SH.read_text(encoding="utf-8"), \
        (REPO / "cage" / "data" / "shims" / "graphify.cmd").read_text(encoding="utf-8")
    assert "python3 -m cage data graphify --help" in sh
    assert "python3 -m cage data graphify --" in sh
    # D8: the cmd twin CANNOT say python3 — it is frequently absent on Windows.
    assert "py -3 -m cage data graphify --help" in cmd
    assert "python -m cage data graphify --help" in cmd
    # D8 binds the EXECUTABLE lines; the `rem` block above them explains the divergence
    # and necessarily names the POSIX spelling to do so.
    code = [l for l in cmd.splitlines() if not l.strip().lower().startswith("rem")]
    assert not any("python3" in l for l in code), \
        "D8: the cmd twin must not name the POSIX spelling in executable text"


def test_arm_two_needs_no_new_marker_so_the_twins_still_skip_each_other():
    """B3's three-copy marker set is unchanged, and this asserts WHY that is safe rather
    than assuming it: the new invocation still contains `cage data graphify`, so a twin
    carrying arm 2 is still recognised as an interceptor by all three copies."""
    from cage import pathshim
    for line in ("python3 -m cage data graphify -- /x/graphify query q",
                 "py -3 -m cage data graphify -- C:\\x\\graphify.exe query q"):
        assert pathshim._INTERCEPTOR.search(line), line
    assert pathshim.is_interceptor(SH)
    assert pathshim.is_interceptor(REPO / "cage" / "data" / "shims" / "graphify.cmd")
