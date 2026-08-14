"""The Windows graphify interceptor (`graphify.cmd`) and its contract with the POSIX twin.

Two implementations of one behaviour spec — [docs/adr/0007_graphify.md](../docs/adr/0007_graphify.md),
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
    reports the *previous* command's status. Passthrough is sacred (B6).

    Asserted as the CONTRACT, not as a branch count. This used to read
    `count(...) == 2`, which was a proxy for "the metered branch and the direct branch";
    GF-LAUNCHER's arm 2 legitimately makes it four, and bumping the literal would have
    been the kind of assertion-relaxation that lets the third branch ship unchecked. So:
    **every `call` that forwards the user's arguments must be followed immediately by
    `exit /b %ERRORLEVEL%` on its own line** — which binds any number of branches,
    including ones not written yet.
    """
    text = CMD.read_text(encoding="utf-8")
    assert "& exit /b" not in text
    lines = [l.strip() for l in text.splitlines()]
    forwards = [i for i, l in enumerate(lines)
                if l.lower().startswith("call ") and "%*" in l]
    assert len(forwards) >= 2, f"expected the metered and direct branches, got {forwards}"
    for i in forwards:
        assert lines[i + 1] == "exit /b %ERRORLEVEL%", (
            f"{lines[i]!r} does not read its exit code on the next line: {lines[i+1]!r}")
    # …and no forward may read it any other way.
    assert text.count("exit /b %ERRORLEVEL%") == len(forwards)


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


def _check_attr(*paths_: Path) -> dict[str, dict[str, str]]:
    """`git check-attr -a` — the *resolved* attributes, which is the only thing that
    decides what a checkout writes. Parsing `.gitattributes` by hand would re-test the
    pattern syntax rather than its effect."""
    repo = Path(__file__).resolve().parents[1]
    r = subprocess.run(["git", "check-attr", "-a", "--", *(str(p) for p in paths_)],
                       cwd=repo, capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"git check-attr unavailable: {r.stderr.strip()}")
    out: dict[str, dict[str, str]] = {}
    for line in r.stdout.splitlines():
        path, attr, value = line.split(": ", 2)
        out.setdefault(path, {})[attr] = value
    return out


def test_posix_twin_is_pinned_to_lf_in_the_working_tree():
    """The twin of `test_cmd_twin_is_crlf`, and it asserts **the pin**, not the bytes.

    A bytes assertion here would be blind in exactly the way this defect needs: the
    file is LF today, so it would pass on a repo with no rule at all — which is what
    `.gitattributes` had. And the blob is not where the risk lives. `core.autocrlf=true`
    normalizes CRLF→LF *at commit*, so the committed bytes stay clean either way; what
    it changes is the **working tree**, which `pyproject.toml`'s `data/shims/*` packages
    verbatim into the wheel. A CRLF checkout ships `#!/usr/bin/env bash\\r` to every
    user of that build — *bad interpreter*, and every graphify call silently unmetered.
    `eol=lf` is the setting that binds the working tree, which is why it is the fix.
    """
    attrs = _check_attr(SH, CMD)
    # `-a` prints nothing at all for a file with no attributes — which is precisely the
    # unpinned state — so this must read as "no pin", never as a KeyError.
    sh, cmd = attrs.get(str(SH), {}), attrs.get(str(CMD), {})

    assert sh.get("text") == "set", f"the POSIX twin is unpinned: {sh}"
    assert sh.get("eol") == "lf", f"the POSIX twin has no LF pin: {sh}"
    # And the opposite pin on the .cmd is untouched — the two rules must not collapse
    # into one blanket `* text=auto`, which would rewrite the batch file to LF.
    assert cmd.get("text") == "unset", f"the Windows twin lost its -text pin: {cmd}"


def test_the_committed_posix_twin_is_actually_lf():
    """The pin's observable effect, kept beside it: a rule that is present but wrong
    (mis-typed path, wrong attribute) would still leave CRLF in the tree."""
    raw = SH.read_bytes()
    assert b"\r\n" not in raw and raw.count(b"\n") > 0


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


def test_one_dead_twin_never_marks_the_healthy_one_dead(tmp_path):
    """P2.5c. `interceptor_dead` is one global bool and was consumed as if it described
    *this* file, so a single stale twin stamped BOTH inventory rows `dead` — a healthy
    copy reported broken, with nothing to say which file to fix.

    **This is the assertion that was missing.** The test above pins `scan.dead` and has
    always passed; the defect lived one layer up, in the rendered rows. Asserting the
    scan and not the render is exactly how it stayed green."""
    (tmp_path / ".cage").mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "graphify").write_bytes(SH.read_bytes())          # healthy
    (tmp_path / "bin" / "graphify.cmd").write_text(                       # dead verb
        "@echo off\r\ncall cage graphify --help >nul 2>nul\r\n", encoding="utf-8")

    scan = wiringscan.run(tmp_path)
    assert scan.dead_interceptors == frozenset({"graphify.cmd"})
    assert scan.interceptor_dead is True      # the bool still answers "anything dead?"

    rows = {a.display: a for a in wiringscan.inventory(tmp_path).items
            if a.kind == "shim"}
    assert rows["bin/graphify.cmd"].status == "dead"
    assert rows["bin/graphify"].status == "current", \
        "a healthy twin was reported dead because the other one is"
    assert "removed verb" not in rows["bin/graphify"].detail


def test_doctor_names_the_twin_that_actually_carries_the_dead_verb(tmp_path, monkeypatch):
    """P2.5c, the second consumer. Doctor's message interpolated the twin THIS OS
    resolves, whichever one was stale — so a POSIX dev with a dead `graphify.cmd` was
    pointed at a file with nothing wrong in it."""
    (tmp_path / ".cage").mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    primary = paths.graphify_shim_name()
    other = "graphify.cmd" if primary == "graphify" else "graphify"
    (tmp_path / "bin" / primary).write_bytes(
        (SH if primary == "graphify" else CMD).read_bytes())
    (tmp_path / "bin" / other).write_text(
        "@echo off\r\ncall cage graphify --help >nul 2>nul\r\n"
        if other.endswith(".cmd") else
        "#!/usr/bin/env bash\ncage graphify --help >/dev/null 2>&1\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tmp_path / "bin"))

    level, detail = doctorcmd._interceptor(tmp_path, wiringscan.run(tmp_path))
    assert level == "fail"
    # Compared as whole tokens: `bin/graphify` is a PREFIX of `bin/graphify.cmd`, so a
    # substring check here silently passes (or fails) for the wrong reason.
    named = {w for w in detail.replace(",", " ").split() if w.startswith("bin/")}
    assert named == {f"bin/{other}"}, \
        f"doctor named {named}, not the twin carrying the dead verb"


def test_the_receipts_check_still_asks_the_global_question(tmp_path):
    """The bool is KEPT, not replaced: `_receipts` genuinely wants *is anything dead* —
    a stale twin on either OS explains an empty receipts table — and is correct as-is."""
    (tmp_path / ".cage").mkdir(parents=True)
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "graphify").write_bytes(SH.read_bytes())
    (tmp_path / "bin" / "graphify.cmd").write_text(
        "@echo off\r\ncall cage graphify --help >nul 2>nul\r\n", encoding="utf-8")

    scan = wiringscan.run(tmp_path)
    level, detail = doctorcmd._receipts(tmp_path, scan)
    assert level == "warn" and "interceptor is dead" in detail


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
    """Invoke the bare name `graphify` through PATH resolution — exactly how a real
    user's shell resolves it, and exactly what `tools/cigraphify.py`'s `present` CI
    leg does (which passes on real Windows CI, on this identical committed file).
    `shim` names which file `path_dirs` is expected to resolve to; it is not invoked
    directly by path.

    PATH is `path_dirs` plus **just enough of the real system directories**
    (`%SystemRoot%\\System32`, `%SystemRoot%`) for `findstr.exe`/`where.exe`/`cmd.exe`
    itself to resolve — never the *whole* inherited PATH (that could put a real
    `cage` on it, defeating B5's "cage absent" assumption below) and never *nothing*
    (every earlier attempt at this test wiped PATH down to just the tmp test
    directories, and reproducibly hit cmd.exe's own "BATCH RECURSION exceeds STACK
    limits" abort, byte-identically, no matter how the shim's own logic or the
    invocation style changed — because the shim's own calls to `findstr`/`where` had
    no way to find their executables). `tools/cigraphify.py`'s `present` leg, which
    passes on real Windows CI against this identical committed file, never wipes PATH
    either."""
    del shim
    e = {k: v for k, v in os.environ.items() if k != "CAGE_GRAPHIFY_SHIM"}
    e.update(env or {})
    system_root = e.get("SystemRoot", r"C:\Windows")
    system_dirs = [f"{system_root}\\System32", system_root] if os.name == "nt" else []
    e["PATH"] = os.pathsep.join([*(str(d) for d in path_dirs), *system_dirs])
    # Quote only where cmd.exe's own line parser would otherwise misread the arg (a
    # space, an empty string, or a character with special meaning outside quotes) —
    # a bare simple word stays bare, matching what the older argv-list invocation used
    # to forward and keeping the existing exact-match assertions valid.
    def _q(a: str) -> str:
        return f'"{a}"' if a == "" or any(c in a for c in ' &|<>^"') else a
    cmdline = " ".join(["graphify"] + [_q(a) for a in args])
    return subprocess.run(cmdline, shell=True, capture_output=True, text=True,
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
