"""Phase 3 — CLI tiering contract: the curated front door, the removed-verb
directions, hidden-but-callable plumbing, no argparse abbreviation, and the
grep gates (no stale `cage <old-verb>` anywhere; committed wiring names only
non-moving verbs). See docs/archive/*cli-tiering* + docs/output-and-simplification.plan.md."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from cage import cli, verbmap

REPO = Path(__file__).resolve().parent.parent
FIXT = Path(__file__).parent / "fixtures" / "cli-help.txt"


def _run(argv, cwd=None):
    """Invoke `cage` as a subprocess (isolates argparse SystemExit / exit codes)."""
    return subprocess.run([sys.executable, "-m", "cage", *argv], cwd=cwd or REPO,
                          capture_output=True, text=True)


# ── the front door ────────────────────────────────────────────────────────────

def test_help_matches_the_plan_mock_verbatim():
    """`cage --help` renders the curated front door byte-for-byte (plan Phase 3 mock)."""
    got = _run(["--help"]).stdout
    assert got == FIXT.read_text(encoding="utf-8")
    # structural anchors: five daily verbs, six group names, no usage/options noise.
    assert got.startswith("cage — measure what your AI agents spend")
    assert "usage:" not in got and "positional arguments" not in got
    for line in ("  report ", "  import ", "  setup ", "  doctor ", "  query "):
        assert line in got
    for grp in ("insights", "human", "authorship", "prices", "study", "policy", "data"):
        assert f"  {grp} " in got or f"  {grp}  " in got


def test_help_hides_plumbing_and_moved_verbs():
    got = _run(["--help"]).stdout
    for hidden in ("mcp", "demo", "debug", "hook-", "graphify"):
        # none advertised on the front door (graphify stays a hidden `data` subcommand)
        assert f"\n  {hidden}" not in got


# ── removed verbs → error with directions (never runs the moved command) ────────

@pytest.mark.parametrize("old", sorted(verbmap.REMOVED))
def test_removed_verb_errors_with_direction(old):
    r = _run([old])
    assert r.returncode == 1, (old, r.stdout, r.stderr)
    assert r.stderr.strip() == f"error: '{old}' is now 'cage {verbmap.REMOVED[old]}'"
    assert r.stdout == ""  # the moved command never ran


def test_removed_verb_with_trailing_args_still_directs():
    # a leading option (old `import-claude --project .`) and a positional (old `why <id>`)
    assert _run(["import-claude", "--project", "."]).returncode == 1
    r = _run(["why", "c_abc123"])
    assert r.returncode == 1 and "cage insights why" in r.stderr


def test_removed_map_never_shadows_a_live_top_level_verb():
    """`human` is a group, `mcp`/`debug`/`demo` stay callable — none may sit in REMOVED,
    or the pre-scan would hijack a real command."""
    parser = cli.build_parser()
    live = set(parser._subparsers._group_actions[0].choices)  # every registered subparser
    for old in verbmap.REMOVED:
        assert old not in {"human", "insights", "authorship", "data", "mcp", "debug", "demo"}
    for group in ("insights", "human", "authorship", "data"):
        assert group in live


# ── hidden but callable plumbing ────────────────────────────────────────────────

def test_hidden_verbs_still_callable(tmp_path):
    assert _run(["demo"], cwd=tmp_path).returncode == 0
    assert _run(["debug"], cwd=tmp_path).returncode == 0
    # hook entrypoints resolve (they run fail-open; exit 0)
    assert _run(["hook-session-start"], cwd=tmp_path).returncode == 0


# ── no argparse abbreviation (an old prefix must not accidentally resolve) ───────

@pytest.mark.parametrize("prefix", ["rep", "insi", "hum", "dat"])
def test_subcommand_abbreviation_is_disabled(prefix):
    r = _run([prefix])
    assert r.returncode == 2 and "invalid choice" in r.stderr


# ── grep gates ──────────────────────────────────────────────────────────────────

_MOVED = "|".join(re.escape(v) for v in sorted(verbmap.REMOVED))
# an old verb immediately after `cage `, not already grouped
_STALE = re.compile(rf"cage ({_MOVED})(?![\w-])")
_GROUPED = re.compile(r"cage (insights|human|authorship|data) ")


def _scan(paths, exts):
    hits = []
    for base in paths:
        for f in (REPO / base).rglob("*"):
            if f.suffix not in exts or not f.is_file():
                continue
            if f.name in ("verbmap.py",) or "/data/shims/" in str(f):
                continue
            for i, line in enumerate(f.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                for m in _STALE.finditer(line):
                    # allow the grouped spelling (`cage data export`) and bare group calls
                    seg = line[m.start():]
                    if _GROUPED.match("cage " + seg[5:]):
                        continue
                    hits.append(f"{f.relative_to(REPO)}:{i}: {m.group(0)}")
    return hits


def test_no_stale_old_verb_hints_in_source_or_assets():
    hits = _scan(["cage"], {".py", ".md", ".toml"})
    assert not hits, "stale `cage <old-verb>` strings:\n" + "\n".join(hits)


def test_no_stale_old_verb_hints_in_rendered_skill_assets():
    hits = _scan(["cage/data/skills", "cage/data/prompts", "cage/data/steering"], {".md"})
    assert not hits, "stale verbs in rendered agent assets:\n" + "\n".join(hits)


def test_committed_wiring_names_only_non_moving_verbs():
    """The wire modules emit hook-*/import/mcp into committed files — never a moved
    verb (else a cloned settings.json would break after this release). The claude
    backfill in particular must have migrated off the removed `import-claude`."""
    from cage import claudewire, kirowire, runshim
    blob = " ".join([
        claudewire.BACKFILL(), claudewire.BANNER(),
        *claudewire._simple().values(),
        kirowire._import_cmd(),
        runshim.selflocating_command("import --agent codex --since 7d"),
    ])
    # every command word after the shim reference must be a surviving verb
    for old in verbmap.REMOVED:
        assert f" {old} " not in f"{blob} ", f"wired command still names removed verb {old!r}"
    assert "import --agent claude" in claudewire.BACKFILL()  # migrated, not left as import-claude
