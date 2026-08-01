"""The Windows graphify interceptor (`graphify.cmd`) and its contract with the POSIX twin.

Two implementations of one behaviour spec — [docs/shim-contract.md](../docs/shim-contract.md),
behaviours B1–B8, divergences D1–D7. These tests are that contract, executable.

Two tiers, deliberately:

  * **contract tests** run everywhere. They pin the invariants a macOS or Linux dev can
    break without noticing — the shared marker set, the twin pairing, the anti-recursion
    structure, the delayed-expansion ban. Windows-only tests that skip on the dev machine
    would let those rot between CI runs.
  * **behaviour tests** run only on Windows (CI-GF's `present` leg). They execute the
    twin: passthrough, exit codes, the 127 path, and stacked-shim recursion.

The failure this guards is F1 on a new OS: an interceptor that exists, sits on PATH and
names live verbs, and still never runs — so every graphify call is unmetered and silent.
"""
from __future__ import annotations

import os
import subprocess
import textwrap
from pathlib import Path

import pytest

from cage import adoptcmd, doctorcmd, pathshim, paths, wiringscan

REPO_SHIMS = Path(__file__).resolve().parents[1] / "cage" / "data" / "shims"
SH = REPO_SHIMS / "graphify"
CMD = REPO_SHIMS / "graphify.cmd"

windows_only = pytest.mark.skipif(os.name != "nt", reason="cmd.exe — Windows hosts")

# B3's marker set. The single source of truth for "is this a cage interceptor", carried
# in three places that must move together: sh `grep -Eq`, cmd `findstr /C:`, and
# `pathshim._INTERCEPTOR`.
MARKERS = ("cage data graphify", "cage graphify", "graphify metering interceptor")


# ── contract: the twins agree (every OS) ────────────────────────────────────────

def test_both_twins_ship_bundled():
    """No `.exe`, nothing compiled — two text files, both package data."""
    assert SH.is_file() and CMD.is_file()
    assert set(paths.GRAPHIFY_SHIMS) == {SH.name, CMD.name}


@pytest.mark.parametrize("shim", [SH, CMD], ids=["sh", "cmd"])
def test_every_twin_self_identifies_as_an_interceptor(shim):
    """B3: a twin must be recognizable *by content* — that is what stops any twin from
    being selected as the real binary by any other twin."""
    assert pathshim.is_interceptor(shim)


@pytest.mark.parametrize("shim", [SH, CMD], ids=["sh", "cmd"])
def test_every_twin_names_only_live_verbs(shim):
    """B5, and the F1 detector applied to both copies. A dead verb here means the
    capability probe fails and graphify runs unmetered and silently."""
    verbs = wiringscan.verbs_in_shell(shim.read_text(encoding="utf-8"))
    assert ("data", "graphify") in verbs
    assert [v for v in verbs if not wiringscan.is_live_verb(v)] == []


def test_the_three_marker_copies_cover_the_same_set():
    """B3's three-copy invariant: the Python predicate, the sh grep and the cmd findstr
    must agree, or liveness detection silently fails and stacked shims recurse."""
    for marker in MARKERS:
        assert pathshim._INTERCEPTOR.search(marker), marker
        assert f'/C:"{marker}"' in CMD.read_text(encoding="utf-8"), marker
    sh_text = SH.read_text(encoding="utf-8")
    assert "cage (data )?graphify|graphify metering interceptor" in sh_text


def test_the_twins_can_never_select_each_other():
    """D2, the structural half of the anti-recursion proof: the sh twin only ever
    considers the extensionless name and the cmd twin only ever considers PATHEXT
    candidates, so a stacked bash+cmd pair cannot resolve to one another even if the
    content check were removed entirely."""
    assert '_cand="$_d/graphify"' in SH.read_text(encoding="utf-8")
    assert "graphify%%e" in CMD.read_text(encoding="utf-8")
    nt_env = {"PATH": "", "PATHEXT": ".COM;.EXE;.BAT;.CMD"}
    if os.name == "nt":
        assert "graphify" not in pathshim._candidates("graphify", nt_env)
        assert "graphify.cmd" in pathshim._candidates("graphify", nt_env)


# ── contract: the cmd twin's own hazards ────────────────────────────────────────

def test_cmd_twin_disables_delayed_expansion_before_forwarding_args():
    """B7. Delayed expansion eats `!` out of `%*`, so `graphify query "why!"` would
    silently lose a character of the user's query — but the PATH-walk earlier in the
    script needs delayed expansion to read a same-block variable, so the invariant is
    narrower than "never enabled anywhere": it must be OFF again before either line
    that forwards `%*` to the real binary."""
    text = CMD.read_text(encoding="utf-8")
    assert "enabledelayedexpansion" in text.lower()          # the walk turns it on...
    assert "disabledelayedexpansion" in text.lower()         # ...and turns it back off
    disable_at = text.lower().index("disabledelayedexpansion")
    for marker in ('call cage data graphify -- "%_cage_gf_real%" %*',
                  'call "%_cage_gf_real%" %*'):
        assert text.lower().index(marker) > disable_at, marker


def test_cmd_twin_reads_the_exit_code_on_its_own_line():
    """D1. `call "%REAL%" %* & exit /b %ERRORLEVEL%` looks right and is wrong: on one
    line `%ERRORLEVEL%` expands at parse time, before `call` has run, so the shim
    reports the *previous* command's status. Passthrough is sacred (B6)."""
    text = CMD.read_text(encoding="utf-8")
    assert "& exit /b" not in text
    assert text.count("exit /b %ERRORLEVEL%") == 2      # metered branch + direct branch


def test_cmd_twin_never_falls_back_to_the_bare_name():
    """B4. Re-invoking `graphify` by bare name re-enters a shim and recurses; the only
    legal outcome with no real binary is 127."""
    text = CMD.read_text(encoding="utf-8")
    assert "exit /b 127" in text
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("rem ") or not stripped:
            continue
        assert not stripped.startswith("graphify"), line
        assert not stripped.startswith("call graphify"), line


def test_cmd_twin_is_crlf():
    """A batch file is read by cmd.exe, not by a POSIX shell. Pinned in .gitattributes
    so no checkout on any platform can rewrite it."""
    raw = CMD.read_bytes()
    assert raw.count(b"\r\n") == raw.count(b"\n") > 0


def test_cmd_twin_walk_is_flat_with_no_call_goto_backedge():
    """B8, re-derived from a real failure. An earlier draft used `call :subroutine`
    from inside a `for` loop plus a `goto` back-edge to re-enter it — reproduced on
    real Windows CI as cmd.exe's own internal safety abort (`Recursion Count=...,
    BATCH PROCESSING IS ABORTED`) hundreds of hops before this script's own logic ever
    hit a bound. The fix is structural: a flat nested `for` (directories x PATHEXT)
    with no subroutine call and no backward jump into itself — provably terminating
    by construction, with nothing left to count."""
    executable = "\n".join(ln for ln in CMD.read_text(encoding="utf-8").splitlines()
                          if not ln.strip().lower().startswith(("rem ", "@echo")))
    assert "call :" not in executable.lower()             # no subroutine invocation
    assert "goto cage_gf_walk" not in executable.lower()  # no back-edge into the walk
    assert "for %%d in" in executable and "for %%e in" in executable  # flat dir x ext walk
    assert "where graphify" in executable                 # the fail-open last resort


# ── the twin pair is installed and healed as a pair ─────────────────────────────

def _fake_graphify_installed(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/graphify")


def test_setup_installs_both_twins_byte_identical(tmp_path, monkeypatch):
    """`bin/` is committed and shared, so a project scaffolded on one OS must keep
    working when it is cloned onto another."""
    _fake_graphify_installed(monkeypatch)
    primary = adoptcmd._install_shim(tmp_path)
    assert primary == str(tmp_path / "bin" / paths.graphify_shim_name())
    for src in (SH, CMD):
        assert (tmp_path / "bin" / src.name).read_bytes() == src.read_bytes()


def test_refresh_completes_a_missing_twin_then_is_idempotent(tmp_path):
    """The migration path: a project scaffolded on POSIX before the `.cmd` existed and
    then opened on Windows. Without this, `cage setup` there reports success while PATH
    interception stays structurally absent."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "graphify").write_bytes(SH.read_bytes())

    assert adoptcmd.refresh_shim(tmp_path) is True
    assert (tmp_path / "bin" / "graphify.cmd").read_bytes() == CMD.read_bytes()
    assert adoptcmd.refresh_shim(tmp_path) is False       # no mtime churn on re-setup


def test_refresh_still_never_creates_an_interceptor_from_nothing(tmp_path):
    """Unchanged boundary: a project that opted out of the interceptor never gets one
    handed to it by a heal."""
    assert adoptcmd.refresh_shim(tmp_path) is False
    assert not (tmp_path / "bin").exists()


def test_a_dead_verb_in_either_twin_is_reported_against_that_file(tmp_path):
    """Both committed copies are scanned on every OS: a dead verb in the twin *this*
    machine cannot run is still dead on a teammate's machine, and the finding has to
    name the file to fix."""
    (tmp_path / ".cage").mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "graphify").write_bytes(SH.read_bytes())
    (tmp_path / "bin" / "graphify.cmd").write_text(
        "@echo off\r\ncall cage graphify --help >nul 2>nul\r\n", encoding="utf-8")

    scan = wiringscan.run(tmp_path)
    assert scan.interceptor_dead
    assert [d.artifact for d in scan.dead] == ["bin/graphify.cmd"]


def test_the_wrong_twin_alone_is_a_doctor_failure(tmp_path, monkeypatch):
    """The Windows half of the F1 lesson. An interceptor that exists, sits on PATH and
    names live verbs, but that this OS can never resolve, must not report ✅."""
    (tmp_path / "bin").mkdir()
    other = "graphify" if os.name == "nt" else "graphify.cmd"
    (tmp_path / "bin" / other).write_bytes((SH if other == "graphify" else CMD).read_bytes())

    level, detail = doctorcmd._interceptor(tmp_path, wiringscan.run(tmp_path))
    assert level == "fail"
    assert "UNMETERED" in detail and "cage setup" in detail


# ── behaviour: the twin actually runs (Windows only) ────────────────────────────

def _real(dirpath: Path, *, code: int = 0) -> Path:
    """A stand-in for the real graphify: echoes its argv, writes to both streams, and
    exits with a chosen code. Carries none of B3's markers, so the twin must select it."""
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / "graphify.cmd"
    p.write_text(textwrap.dedent(f"""\
        @echo off
        echo out:%*
        echo err:%*  1>&2
        exit /b {code}
        """).replace("\n", "\r\n"), encoding="utf-8")
    return p


def _twin(dirpath: Path) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / "graphify.cmd"
    p.write_bytes(CMD.read_bytes())
    return p


def _run(shim: Path, *args: str, path_dirs: list[Path], env: dict | None = None,
         cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke a shim with a controlled PATH. `cage` is deliberately absent from that
    PATH, so B5's first probe fails and the unmetered branch is what gets exercised —
    these tests are about passthrough and recursion, not about metering."""
    e = {k: v for k, v in os.environ.items() if k != "CAGE_GRAPHIFY_SHIM"}
    e.update(env or {})
    e["PATH"] = os.pathsep.join(str(d) for d in path_dirs)
    return subprocess.run([str(shim), *args], capture_output=True, text=True,
                          env=e, cwd=str(cwd) if cwd else None, timeout=60)


@windows_only
def test_passthrough_is_byte_identical_to_the_real_binary(tmp_path):
    """B6, the sacred one: stdout, stderr and exit code identical to a direct call."""
    real = _real(tmp_path / "real", code=3)
    twin = _twin(tmp_path / "bin")
    args = ["query", "auth flow"]

    direct = _run(real, *args, path_dirs=[tmp_path / "real"], cwd=tmp_path)
    through = _run(twin, *args, path_dirs=[tmp_path / "bin", tmp_path / "real"], cwd=tmp_path)

    assert (through.stdout, through.stderr, through.returncode) == \
           (direct.stdout, direct.stderr, direct.returncode)
    assert through.returncode == 3                       # the real binary's code, not 0
    assert "auth flow" in through.stdout and "auth flow" in through.stderr


@windows_only
def test_no_real_binary_exits_127_and_never_recurses(tmp_path):
    """B4. Only interceptors on PATH ⇒ 127 on stderr, promptly — never a bare-name
    fallback, which would re-enter a shim."""
    twin = _twin(tmp_path / "bin")
    r = _run(twin, "query", "x", path_dirs=[tmp_path / "bin"], cwd=tmp_path)
    assert r.returncode == 127
    assert "not found" in r.stderr and "interceptor shim" in r.stderr
    assert r.stdout == ""


@windows_only
def test_stacked_cmd_twins_cannot_recurse(tmp_path):
    """The failure that already cost this project. Two interceptors ahead of the real
    binary: each must skip *both* (B3), not merely its own directory."""
    first = _twin(tmp_path / "a")
    _twin(tmp_path / "b")
    _real(tmp_path / "real")
    r = _run(first, "query", "x",
             path_dirs=[tmp_path / "a", tmp_path / "b", tmp_path / "real"], cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == "out:query x\n"


@windows_only
def test_the_posix_twin_is_never_selected_as_the_real_binary(tmp_path):
    """D2 executed: an extensionless `graphify` beside the twin is not a PATHEXT
    candidate, so a bash+cmd stack cannot loop through the cmd side."""
    bin_dir = tmp_path / "bin"
    twin = _twin(bin_dir)
    (bin_dir / "graphify").write_bytes(SH.read_bytes())
    r = _run(twin, "query", "x", path_dirs=[bin_dir], cwd=tmp_path)
    assert r.returncode == 127          # the sh twin was not mistaken for the real thing


@windows_only
def test_the_reentry_guard_skips_metering(tmp_path):
    """B1. A shim invoked from inside a metered run passes straight through."""
    _real(tmp_path / "real")
    twin = _twin(tmp_path / "bin")
    r = _run(twin, "query", "x", path_dirs=[tmp_path / "bin", tmp_path / "real"],
             env={"CAGE_GRAPHIFY_SHIM": "1"}, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == "out:query x\n"


@windows_only
@pytest.mark.parametrize("arg", ["a b", "why!", "C:\\Program Files\\x", "a&b", ""],
                         ids=["space", "bang", "spaced-path", "amp", "empty"])
def test_arguments_survive_the_forward(tmp_path, arg):
    """B6/B7/D6. `%*` forwards the tail as typed; delayed expansion would eat the `!`."""
    _real(tmp_path / "real")
    twin = _twin(tmp_path / "bin")
    r = _run(twin, "query", arg, path_dirs=[tmp_path / "bin", tmp_path / "real"],
             cwd=tmp_path)
    assert r.returncode == 0
    assert arg in r.stdout or (arg == "" and "query" in r.stdout)
