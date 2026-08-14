"""`cage interceptor graphify` — the machine door both twins call, and the gate that
would have caught SURFACE-CUT.

The failure this file exists for: on 2026-08-12 SURFACE-CUT deleted `cage data graphify`
with the whole `data` group and left both interceptor twins probing it. Nothing failed.
`cage setup` went on installing a shim whose B5 capability probe could never succeed, on
every OS, for every agent — so every graphify call fell through to the unmetered binary,
silently, and kiro-IDE (whose only savings route is the interceptor) filed nothing at all.
`cage doctor` correctly FAILed, but its fix hint pointed at `cage setup --wire-only`,
which rewrote the shim to the same dead verb.

Two gates, both about the *scaffold* rather than the shim text:

  * :func:`test_a_freshly_scaffolded_shim_names_a_verb_the_parser_accepts` — the direct
    inverse of the bug. It binds the artifact cage WRITES to the parser cage RUNS, so a
    future verb rename that misses the twins reddens here instead of shipping.
  * :func:`test_dead_shim_fails_doctor_then_setup_heals_it` — the fix hint must be
    curative, end to end. A FAIL whose remedy does not remedy is worse than no check.

`tests/test_win_graphify_shim.py` owns the twins' own contract (B1–B8, the marker set);
this file owns the verb and the heal path.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from cage import adoptcmd, cli, doctorcmd, paths, pathshim, verbmap, wiringscan

posix_only = pytest.mark.skipif(os.name == "nt", reason="POSIX shim/PATH semantics")

# The verb path the twins probe and invoke. Stated once here so a rename updates the
# contract in one place — and asserted against the live parser below, never trusted.
VERB = ("interceptor", "graphify")


def _managed(root: Path) -> Path:
    """A cage-managed project root with an installed interceptor pair."""
    (root / ".cage").mkdir(parents=True, exist_ok=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    for name in paths.GRAPHIFY_SHIMS:
        adoptcmd._copy_shim(name, root / "bin" / name)
    return root


# ── the verb itself ─────────────────────────────────────────────────────────────

def test_the_verb_the_twins_probe_is_a_live_command():
    """B5's probe is `cage interceptor graphify --help`. If that verb is not live, the
    probe exits non-zero and both twins degrade to correct-but-unmetered passthrough —
    the exact silent failure, and it is invisible from the shim's side."""
    assert wiringscan.is_live_verb(VERB)


def test_the_help_probe_exits_zero(capsys):
    """The twins branch on the *exit code* of `--help`, so that is what is asserted —
    not that a parser node exists, which is what a `build_parser()` walk would prove."""
    with pytest.raises(SystemExit) as exc:
        cli.main([*VERB, "--help"])
    assert exc.value.code == 0
    assert "graphify" in capsys.readouterr().out


def test_the_leaf_carries_the_deleted_leafs_exact_shape():
    """Restored under a NEW spelling but the SAME shape (`--task` + a REMAINDER
    positional), so the twins' `-- "$REAL" "$@"` invocation is unchanged from the form
    that was already proven against the real binary."""
    args = cli.build_parser().parse_args(
        [*VERB, "--task", "t_1", "--", "/usr/local/bin/graphify", "query", "auth flow"])
    assert args.task == "t_1"
    assert args.argv == ["--", "/usr/local/bin/graphify", "query", "auth flow"]


def test_the_group_is_visible_on_the_front_door():
    """D3. `cage data graphify` was reachable but unadvertised, and that is part of why
    deleting the group read as removing a human verb rather than breaking a contract."""
    assert "interceptor" in cli._ROOT_HELP


def test_the_old_top_level_spelling_names_the_new_tail():
    """`verbmap.REMOVED["graphify"]` was `""` — "removed, no replacement" — which became
    a lie the moment this verb existed, and which made `wiringscan.heal_tail` decline to
    rewrite an adopt-era artifact it could now actually fix."""
    assert verbmap.REMOVED["graphify"] == "interceptor graphify"
    assert "no replacement" not in verbmap.direction("graphify")
    assert wiringscan.heal_tail("graphify -- /x/graphify query q") == \
        "interceptor graphify -- /x/graphify query q"


# ── the two gates ───────────────────────────────────────────────────────────────

@posix_only
def test_a_freshly_scaffolded_shim_names_a_verb_the_parser_accepts(tmp_path):
    """**The gate that would have caught SURFACE-CUT.**

    Deleting a verb is allowed; deleting a verb that a *written artifact* depends on and
    leaving the artifact behind is not. This binds the two together at the only point
    where a rename can silently diverge — what `cage setup` copies onto disk — and it is
    written even though the immediate bug is fixed, because the class recurs.

    Both twins are asserted, on every POSIX host: a macOS dev must not be able to leave
    the Windows twin naming a dead verb, where nothing here would ever run it."""
    root = _managed(tmp_path / "proj")
    for shim in paths.graphify_shims(root):
        assert shim.exists(), shim
        verbs = wiringscan.verbs_in_shell(shim.read_text(encoding="utf-8"))
        assert verbs, f"{shim.name} names no cage verb at all"
        dead = [v for v in verbs if not wiringscan.is_live_verb(v)]
        assert dead == [], f"{shim.name} probes dead verbs: {dead}"
        assert VERB in verbs, f"{shim.name} does not probe {VERB}"


@posix_only
def test_dead_shim_fails_doctor_then_setup_heals_it(tmp_path, monkeypatch):
    """Dead shim → doctor FAIL → `cage setup --wire-only` → doctor OK, end to end.

    The half that was broken was the LAST arrow. `verbmap.REMOVED["graphify"]` was empty,
    so the hint named a refresh that produced the same dead verb; a user following the
    fix would have re-run it forever. Asserting the FAIL alone would have passed
    throughout the outage."""
    root = _managed(tmp_path / "proj")
    shim = root / "bin" / paths.graphify_shim_name()
    # A pre-tiering adopt-era interceptor: self-identifies (B3) but probes a dead verb.
    shim.write_text(
        "#!/usr/bin/env bash\n"
        "# cage: graphify metering interceptor\n"
        "if command -v cage >/dev/null 2>&1 && cage graphify --help >/dev/null 2>&1; then\n"
        '  exec cage graphify -- "$REAL" "$@"\n'
        "fi\n", encoding="utf-8")
    shim.chmod(0o755)
    monkeypatch.setenv("PATH", str(shim.parent) + os.pathsep + os.environ["PATH"])

    scan = wiringscan.run(root, assets=False)
    assert scan.dead_interceptors, "a dead twin must be detected before anything is healed"
    level, detail = doctorcmd._interceptor(root, scan)
    assert level == doctorcmd._FAIL
    assert "cage setup --wire-only" in detail          # the hint under test

    # …and the hint is CURATIVE. `refresh_shim` is what `cage setup` runs; it rewrites the
    # whole file from package data rather than going through `heal_tail`.
    assert adoptcmd.refresh_shim(root) is True
    healed = wiringscan.run(root, assets=False)
    assert not healed.dead_interceptors
    assert doctorcmd._interceptor(root, healed)[0] == doctorcmd._OK
    assert adoptcmd.refresh_shim(root) is False        # idempotent


@posix_only
def test_a_healed_shim_is_still_recognised_as_an_interceptor(tmp_path):
    """B3 across the heal: the rewritten file must still self-identify, or two stacked
    shims stop skipping each other and the recursion guard is holed."""
    root = _managed(tmp_path / "proj")
    for shim in paths.graphify_shims(root):
        assert pathshim.is_interceptor(shim)
