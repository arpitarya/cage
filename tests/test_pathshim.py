"""The PATH-winning graphify interceptor (B-fix-1) and its heal boundary (B-fix-2).

The failure these tests pin is the one that actually happened: an adopt-era shim in a
*different* project won on PATH, probed a removed verb, and ran graphify unmetered and
silently for nine days while `cage doctor`, run in cage, reported ✅. Every root-scoped
check passed the whole time — which is why the load-bearing assertions here are the ones
about a shim **outside** the scanned root: `test_dead_outside_root_is_a_doctor_failure`
and `test_out_of_root_unmanaged_shim_is_never_written`.

The second is the safety half. Cage may rewrite a shim inside a cage-managed root; it may
never touch a file outside one. A regression there would have cage silently editing
another project's files — the one outcome this fix must not become.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cage import adoptcmd, agents, doctorcmd, pathshim, wiringscan

posix_only = pytest.mark.skipif(os.name != "posix", reason="sh shims — POSIX hosts")

pytestmark = posix_only


# ── builders ────────────────────────────────────────────────────────────────────

def _interceptor(path: Path, verb: str = "interceptor graphify") -> Path:
    """A cage interceptor probing ``cage <verb>`` — the current form by default, an
    adopt-era one when handed a dead verb."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/usr/bin/env bash\n"
        "# cage: graphify metering interceptor — routes queries through cage\n"
        f"if command -v cage >/dev/null 2>&1 && cage {verb} --help >/dev/null 2>&1; then\n"
        f'  exec cage {verb} -- "$REAL" "$@"\n'
        "fi\n"
        'exec "$REAL" "$@"\n')
    path.chmod(0o755)
    return path


def _real_binary(path: Path) -> Path:
    """A `graphify` that is not cage's — the real tool, or anything foreign."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho 'the real graphify'\n")
    path.chmod(0o755)
    return path


def _managed(root: Path) -> Path:
    """A cage-managed root: what makes a shim inside it cage's to rewrite."""
    (root / ".cage").mkdir(parents=True, exist_ok=True)
    return root


def _path(monkeypatch, *dirs: Path) -> None:
    monkeypatch.setenv("PATH", os.pathsep.join(str(d) for d in dirs))


# ── the four states ─────────────────────────────────────────────────────────────

def test_absent_when_no_graphify_on_path(tmp_path, monkeypatch):
    """No graphify anywhere is not a fault — there is nothing to intercept."""
    _path(monkeypatch, tmp_path / "empty")
    assert pathshim.classify(tmp_path).state == "absent"


def test_live_when_the_winner_names_current_verbs(tmp_path, monkeypatch):
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    _path(monkeypatch, root / "bin")
    ps = pathshim.classify(root)
    assert ps.state == "live" and ps.winner == str(root / "bin" / "graphify")


def test_dead_when_the_winner_probes_a_renamed_verb(tmp_path, monkeypatch):
    """The exact live failure: an adopt-era shim still probing the bare `cage graphify`,
    two renames behind the live `cage interceptor graphify`."""
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, root / "bin")
    ps = pathshim.classify(root)
    assert ps.state == "dead"
    assert ps.verbs == ("graphify",)
    assert ps.fix_tail == "interceptor graphify"   # verbmap supplies the HINT only


def test_dead_when_the_verb_was_removed_outright(tmp_path, monkeypatch):
    """`cage adopt` is absent from `verbmap.REMOVED` — a grep against REMOVED would miss
    this artifact entirely, which is why the live parser is the detector."""
    from cage import verbmap
    assert "adopt" not in verbmap.REMOVED
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify", verb="adopt")
    _path(monkeypatch, root / "bin")
    ps = pathshim.classify(root)
    assert ps.state == "dead" and ps.verbs == ("adopt",)
    assert ps.fix_tail == ""                    # never guessed at


def test_shadowed_names_both_paths(tmp_path, monkeypatch):
    """This root installed a shim; a different one wins. Advisory — but both paths must
    be recoverable, or the user cannot tell which file to act on."""
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    other = _interceptor(tmp_path / "other" / "bin" / "graphify")
    _path(monkeypatch, other.parent, root / "bin")
    ps = pathshim.classify(root)
    assert ps.state == "shadowed"
    assert ps.winner == str(other)
    assert ps.root_shim == str(root / "bin" / "graphify")


def test_foreign_winner_is_reported_not_judged(tmp_path, monkeypatch):
    """A non-cage `graphify` wins and this root ships no shim: metering is off by
    ABSENCE — a different condition from a dead shim, and never conflated with it."""
    real = _real_binary(tmp_path / "usr" / "graphify")
    _path(monkeypatch, real.parent)
    ps = pathshim.classify(tmp_path / "proj")
    assert ps.state == "foreign" and not ps.interceptor


def test_real_binary_shadowing_a_root_shim_is_not_current(tmp_path, monkeypatch):
    """The root's shim loses to the real binary — shadowed, and NOT an interceptor, so
    the inventory must not call it 'current' just because it wins."""
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    real = _real_binary(tmp_path / "usr" / "graphify")
    _path(monkeypatch, real.parent, root / "bin")
    ps = pathshim.classify(root)
    assert ps.state == "shadowed" and not ps.interceptor


def test_first_executable_wins_like_the_shell(tmp_path, monkeypatch):
    """Resolution order is the shell's, not 'any match' — only the first one runs."""
    first = _interceptor(tmp_path / "a" / "graphify")
    second = _interceptor(tmp_path / "b" / "graphify", verb="graphify")
    _path(monkeypatch, first.parent, second.parent)
    ps = pathshim.classify(tmp_path / "proj")
    assert ps.state == "live" and ps.others == (str(second),)


def test_non_executable_file_is_not_a_candidate(tmp_path, monkeypatch):
    """PATH resolution requires the executable bit — same as the shell."""
    p = _interceptor(tmp_path / "a" / "graphify")
    p.chmod(0o644)
    _path(monkeypatch, p.parent)
    assert pathshim.classify(tmp_path / "proj").state == "absent"


# ── the heal boundary ───────────────────────────────────────────────────────────

def test_managed_root_requires_the_bin_layout_and_a_dot_cage(tmp_path):
    """Narrow on purpose: exactly `<root>/bin/graphify` beside a `<root>/.cage/`. A walk
    up looking for any `.cage/` would find the GLOBAL ledger at ~/.cage and declare the
    whole home directory writable."""
    unmanaged = _interceptor(tmp_path / "plain" / "bin" / "graphify")
    assert pathshim.managed_root(unmanaged) == ""
    managed = _interceptor(_managed(tmp_path / "proj") / "bin" / "graphify")
    assert pathshim.managed_root(managed) == str(tmp_path / "proj")
    loose = _interceptor(_managed(tmp_path / "proj2") / "graphify")
    assert pathshim.managed_root(loose) == ""       # not a bin/ layout


def test_healable_is_dead_and_managed_only(tmp_path, monkeypatch):
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    _path(monkeypatch, root / "bin")
    assert not pathshim.classify(root).healable          # live → nothing to heal
    _interceptor(root / "bin" / "graphify", verb="graphify")
    assert pathshim.classify(root).healable
    plain = _interceptor(tmp_path / "plain" / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, plain.parent)
    assert not pathshim.classify(root).healable          # dead but not cage-managed


def test_setup_heals_a_dead_path_winner_in_another_cage_managed_root(tmp_path, monkeypatch):
    """B-fix-2: `cage setup` here refreshes the shim that actually RUNS, even when it
    belongs to another cage-managed project — and is idempotent on a second run."""
    here = _managed(tmp_path / "here")
    other = _managed(tmp_path / "other")
    shim = _interceptor(other / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, shim.parent)

    res = agents.install(here, ("claude",))
    assert res["graphify"]["path_shim"].startswith(f"refreshed {shim}")
    assert "cage interceptor graphify" in shim.read_text()
    assert pathshim.classify(here).state in ("live", "shadowed")

    before = shim.read_bytes()
    assert "path_shim" not in agents.install(here, ("claude",)).get("graphify", {})
    assert shim.read_bytes() == before                   # idempotent


def test_out_of_root_unmanaged_shim_is_never_written(tmp_path, monkeypatch):
    """The safety assertion. A dead shim outside every cage-managed root is NAMED, never
    edited — cage does not silently rewrite another project's files."""
    here = _managed(tmp_path / "here")
    shim = _interceptor(tmp_path / "stranger" / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, shim.parent)
    before = shim.read_bytes()

    agents.install(here, ("claude",))
    assert shim.read_bytes() == before

    level, detail = doctorcmd._path_interceptor(here)
    assert level == "fail" and str(shim) in detail


# ── doctor severity + fix lines ─────────────────────────────────────────────────

def test_dead_outside_root_is_a_doctor_failure_with_a_runnable_fix(tmp_path, monkeypatch):
    """A dead cage shim means capture is silently OFF — a failure, never a warning; and
    the message must name the exact file plus something the user can actually run."""
    here = _managed(tmp_path / "here")
    other = _managed(tmp_path / "other")
    shim = _interceptor(other / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, shim.parent)
    level, detail = doctorcmd._path_interceptor(here)
    assert level == "fail"
    assert str(shim) in detail and "UNMETERED" in detail
    assert "cage setup" in detail


def test_shadowed_is_advisory_and_foreign_is_quiet(tmp_path, monkeypatch):
    """`foreign` stays ok-level: doctor's `interceptor` check already warns about the
    same absence, and two warns for one condition is the noise that trains people to
    ignore the check."""
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    other = _interceptor(tmp_path / "other" / "bin" / "graphify")
    _path(monkeypatch, other.parent, root / "bin")
    level, detail = doctorcmd._path_interceptor(root)
    assert level == "warn" and str(other) in detail and str(root / "bin") in detail

    real = _real_binary(tmp_path / "usr" / "graphify")
    _path(monkeypatch, real.parent)
    assert doctorcmd._path_interceptor(tmp_path / "bare")[0] == "ok"


def test_clean_machine_is_quiet(tmp_path, monkeypatch):
    """No graphify at all must produce no noise — the default state of most machines."""
    _path(monkeypatch, tmp_path / "nothing")
    level, detail = doctorcmd._path_interceptor(tmp_path)
    assert level == "ok" and "nothing to intercept" in detail


# ── read-only by construction ───────────────────────────────────────────────────

def test_scan_executes_nothing_and_imports_nothing(tmp_path, monkeypatch):
    """Executing the resolved binary could not distinguish 'verb dead' from 'cage
    absent' anyway — that ambiguity IS the bug. Any subprocess or capture here is a
    regression, so both are made to explode."""
    def _boom(*a, **k):  # noqa: ANN002, ANN003
        raise AssertionError("the scan must never execute or capture")

    for target in ("subprocess.run", "subprocess.Popen", "subprocess.call",
                   "subprocess.check_output", "os.system", "os.execv", "os.execvp",
                   "os.posix_spawn", "cage.importcmd.run", "cage.importcmd.ensure_captured"):
        monkeypatch.setattr(target, _boom, raising=False)

    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, root / "bin")

    assert pathshim.classify(root).state == "dead"
    assert doctorcmd._path_interceptor(root)[0] == "fail"
    wiringscan.inventory(root)


def test_a_multi_megabyte_winner_is_only_sniffed(tmp_path, monkeypatch):
    """The winner may be a real compiled binary — classify reads one small block, never
    the whole file."""
    big = tmp_path / "usr" / "graphify"
    big.parent.mkdir(parents=True)
    big.write_bytes(b"\x7fELF" + b"\0" * (4 * 1024 * 1024))
    big.chmod(0o755)
    _path(monkeypatch, big.parent)
    assert len(pathshim.sniff(big)) <= pathshim._SNIFF_BYTES
    assert pathshim.classify(tmp_path / "proj").state == "foreign"


# ── inventory ───────────────────────────────────────────────────────────────────

def test_inventory_lists_the_path_winner_outside_the_root(tmp_path, monkeypatch):
    """`cage doctor --wiring` must show the one file that decides whether graphify is
    metered — omitting it is how the dead shim stayed invisible."""
    root = _managed(tmp_path / "proj")
    shim = _interceptor(tmp_path / "other" / "bin" / "graphify", verb="graphify")
    _path(monkeypatch, shim.parent)
    rows = [a for a in wiringscan.inventory(root).items if a.kind == "shim"]
    assert [r.status for r in rows] == ["dead"]
    assert rows[0].scope == "global"


def test_inventory_does_not_double_list_the_root_shim(tmp_path, monkeypatch):
    root = _managed(tmp_path / "proj")
    _interceptor(root / "bin" / "graphify")
    _path(monkeypatch, root / "bin")
    rows = [a for a in wiringscan.inventory(root).items if a.kind == "shim"]
    assert [r.display for r in rows] == ["bin/graphify"]


def test_the_bundled_shim_is_recognized_as_an_interceptor(tmp_path):
    """The shipped shim and this module's predicate must agree — the shell copy in
    `data/shims/graphify` is an intentional duplicate and the two move together."""
    dst = tmp_path / "bin" / "graphify"
    dst.parent.mkdir()
    dst.write_text("placeholder")
    adoptcmd.refresh_shim(tmp_path)
    assert pathshim.is_interceptor(dst)
    assert all(wiringscan.is_live_verb(v)
               for v in wiringscan.verbs_in_shell(dst.read_text()))
