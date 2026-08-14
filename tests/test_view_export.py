"""`--export` / `--stamp` — the artifact surface (`cage/viewexport.py`, `cage/runstamp.py`).

The load-bearing assertion in this file is the FIRST one: **stdout is byte-identical
with and without `--export`**. That is what lets a wall clock exist on a read surface
without touching the determinism law — the stamp is metadata about a run, never an
input to a cell, and the default surface the goldens pin has no clock in it at all.
Every other test here is a corollary of that split:

- an artifact ALWAYS carries the block (mandatory in a file: a number with no as-of
  outlives its terminal and becomes unreadable),
- stdout NEVER does unless `--stamp` (optional on a terminal),
- and a format a view cannot produce is a typed refusal, never an empty file — an
  empty CSV reads as *no rows*, which is the one thing it must not be able to say.

The fan-out gate (`test_every_report_and_insight_is_exportable`) is this file's
`_WIRING_ARTIFACTS`: a new insight that forgets `_export_flags` fails here rather than
shipping a view nobody can export. Wire the new command in — never relax the set.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pytest

from cage import cli, runstamp, viewexport

STAMP = "2026-08-10T08:42:40+05:30"
SLUG = "20260810-084240"

# Every view that must be exportable: every `insights` leaf plus the two report-shaped
# views outside that group. Bare `cage` is deliberately absent — a root-level
# `--export` with an optional value would swallow the following subcommand
# (`cage --export chats`), and bare `cage` is a help surface, not a view.
#
# **SURFACE-CUT (2026-08-14) removed six entries** — `report`, `insights attrib`,
# `insights adoption`, `insights compare`, `insights estimate`, `insights calibration` —
# because the commands themselves are gone. The GATE below is unchanged and still
# bidirectional: every name here must own `--export`, and every `--export`-bearing leaf
# the live parser knows must appear here. Adding a view still means adding a row, never
# relaxing the set.
EXPECTED_VIEWS = {
    "insights chats", "insights graphify", "insights commits", "insights commit",
    "insights why",
    # EXPORT-SCOPE (2026-08-11): report-shaped views v0.48.0's scope line missed.
    # Keyed by PARSER LEAF PATH, which is what `_leaves()` walks. `study report` was here
    # too until v0.51 (STUDY-CUT) removed the whole fleet study.
    "authorship summary",
}

# Every exportable view's `view=` label is its parser leaf path — `study` was the last
# exception and lost it with the subparser conversion, before the group was removed.
VIEW_LABELS: dict[str, str] = {}


@pytest.fixture(autouse=True)
def _pinned_clock(monkeypatch):
    """Pin the ONE clock call. Everything downstream — the block, the run-folder name —
    derives from it, so pinning here is enough to make every artifact byte-stable."""
    monkeypatch.setenv("CAGE_RUN_STAMP", STAMP)


@pytest.fixture
def go(seeded, monkeypatch, capsys):
    """Run `cage <argv>` in the §4.4-seeded project; returns (stdout, stderr)."""
    root, _ = seeded
    monkeypatch.chdir(root)

    def _run(argv, expect_exit=0):
        assert cli.main(argv) == expect_exit
        cap = capsys.readouterr()
        return cap.out, cap.err
    _run.root = root
    return _run


def _outdir(root: Path, view: str) -> Path:
    return root / ".cage" / "output" / f"{runstamp.view_slug(view)}-{SLUG}"


# ── 1. the determinism split ──────────────────────────────────────────────────

@pytest.mark.parametrize("argv", [
    ["insights", "chats"],
    ["insights", "graphify"],
    ["insights", "commits"],
])
def test_export_never_changes_stdout(go, argv):
    """The whole design rests here. `--export` writes files; it does not touch the
    stream. If this ever fails, the goldens and `tests/test_floor.py` are asserting a
    surface the flag can perturb, and the clock has leaked into a derived view."""
    plain, _ = go(argv)
    exported, err = go([*argv, "--export"])
    assert exported == plain
    assert "✔ wrote" in err          # the confirmation exists — on stderr, not stdout
    assert "✔ wrote" not in plain


def test_stdout_carries_no_clock_by_default(go):
    out, _ = go(["insights", "chats"])
    assert STAMP not in out and "generated_at" not in out


def test_stamp_is_the_opt_in_half(go):
    out, _ = go(["insights", "chats", "--stamp"])
    assert out.startswith(f"# cage: view=insights chats\n# cage: generated_at={STAMP}\n")
    assert "# cage: cage_version=" in out


def test_stamp_on_csv_is_a_comment_preamble_and_leaves_the_columns_alone(go):
    plain, _ = go(["insights", "chats", "--csv"])
    stamped, _ = go(["insights", "chats", "--csv", "--stamp"])
    body = "".join(ln for ln in stamped.splitlines(keepends=True)
                   if not ln.startswith("# cage: "))
    assert body == plain                      # the pinned column contract is untouched
    assert f"# cage: generated_at={STAMP}\n" in stamped


def test_stamp_on_json_wraps_rather_than_merges(go):
    out, _ = go(["insights", "chats", "--json", "--stamp"])
    doc = json.loads(out)
    assert doc["cage"]["generated_at"] == STAMP
    assert doc["data"] == json.loads(go(["insights", "chats", "--json"])[0])


# ── 2. what an artifact is ────────────────────────────────────────────────────

def test_bare_export_writes_every_format_this_view_has(go):
    _, err = go(["insights", "chats", "--export"])
    d = _outdir(go.root, "insights chats")
    assert sorted(p.name for p in d.iterdir()) == ["insights-chats.csv", "insights-chats.json",
                                                   "insights-chats.txt"]
    assert str(d) in err

def test_a_view_with_no_csv_renderer_exports_the_formats_it_has(go):
    """`insights estimate` was the csv-less example until SURFACE-CUT; `insights why`
    is now the view that owns no `render_csv`, and the rule is unchanged — a bare
    `--export` writes every format the view HAS, and never an empty one it doesn't."""
    go(["insights", "why", "c_1", "--export"])
    d = _outdir(go.root, "insights why")
    assert sorted(p.name for p in d.iterdir()) == ["insights-why.json",
                                                   "insights-why.txt"]


@pytest.mark.parametrize("name", ["insights-chats.txt", "insights-chats.csv",
                                  "insights-chats.json"])
def test_every_artifact_carries_the_block(go, name):
    """Mandatory in a file, with no flag to suppress it — an exported table whose
    as-of is gone is a number no one can safely re-read."""
    go(["insights", "chats", "--export"])
    text = (_outdir(go.root, "insights chats") / name).read_text(encoding="utf-8")
    if name.endswith(".json"):
        block = json.loads(text)["cage"]
        assert block["view"] == "insights chats" and block["generated_at"] == STAMP
    else:
        assert text.startswith(f"# cage: view=insights chats\n"
                               f"# cage: generated_at={STAMP}\n")


def test_the_artifact_body_is_the_same_bytes_the_terminal_showed(go):
    """One data structure, one renderer — an artifact is the stdout view plus a header,
    never a second rendering that could disagree with it."""
    plain, _ = go(["insights", "chats"])
    go(["insights", "chats", "--export"])
    art = (_outdir(go.root, "insights chats") / "insights-chats.txt").read_text()
    assert art.split("\n\n", 1)[1] == plain[:-1]   # stdout's trailing print newline


def test_the_block_names_the_filters_and_not_the_presentation_switches(go):
    """The block names the DATA filters only. `--usd` was the presentation switch this
    guarded against; it went in USAGE-ONLY (ADR 0011), and `--all-columns` went with
    `report` in SURFACE-CUT. `--all` — the truncation switch on `insights chats` — takes
    its place. The rule is unchanged: a switch that cannot change what a number MEANS
    must never appear in the as-of block (`runstamp.FILTER_ARGS`)."""
    go(["insights", "chats", "--since", "30d", "--agent", "claude", "--all", "--export"])
    txt = (_outdir(go.root, "insights chats")
           / "insights-chats.txt").read_text(encoding="utf-8")
    line = next(ln for ln in txt.splitlines() if ln.startswith("# cage: filters="))
    assert "since=30d" in line and "agent=claude" in line
    assert "all" not in line.replace("claude", "")   # the presentation switch stays out


def test_the_block_names_the_ledger_it_read(go):
    go(["insights", "chats", "--export"])
    txt = (_outdir(go.root, "insights chats") / "insights-chats.txt").read_text()
    assert f"# cage: ledger={go.root / '.cage'}\n" in txt


# ── 3. destinations ───────────────────────────────────────────────────────────

def test_a_named_file_writes_exactly_that_file_in_exactly_that_format(go, tmp_path):
    dest = tmp_path / "sub" / "spend.csv"
    _, err = go(["insights", "chats", "--export", str(dest)])
    assert dest.exists() and not (tmp_path / "sub").joinpath("spend.txt").exists()
    assert dest.read_text(encoding="utf-8").startswith("# cage: view=insights chats\n")
    assert f"✔ wrote {dest}" in err


def test_md_and_txt_are_the_same_renderer(go, tmp_path):
    go(["insights", "chats", "--export", str(tmp_path / "a.md")])
    go(["insights", "chats", "--export", str(tmp_path / "b.txt")])
    assert (tmp_path / "a.md").read_text() == (tmp_path / "b.txt").read_text()


def test_a_named_directory_still_gets_a_per_run_folder(go, tmp_path):
    """Two runs of one view must never silently clobber each other — an artifact whose
    job is to be the as-of record is worthless once the previous as-of is gone."""
    go(["insights", "chats", "--export", str(tmp_path / "reports")])
    assert (tmp_path / "reports" / f"insights-chats-{SLUG}" / "insights-chats.csv").exists()


def test_two_runs_at_different_times_do_not_clobber(go, monkeypatch, tmp_path):
    go(["insights", "chats", "--export", str(tmp_path / "r")])
    monkeypatch.setenv("CAGE_RUN_STAMP", "2026-08-11T09:00:00+05:30")
    go(["insights", "chats", "--export", str(tmp_path / "r")])
    assert len(list((tmp_path / "r").iterdir())) == 2


def test_the_default_home_is_the_active_ledgers_output_dir(go):
    go(["insights", "chats", "--export"])
    assert _outdir(go.root, "insights chats").is_dir()


def test_the_artifact_dir_is_not_the_dashboard_docroot(go):
    """`.cage/out/` WAS `cage data serve`'s docroot — a stdlib http.server was pointed
    straight at it, so an artifact landing there would have been published on the
    loopback port. `serve` went in SURFACE-CUT, but the separation is kept deliberately:
    the reason a future server could be added safely is that artifacts never went there.
    Re-pointing `--export` at `.cage/out/` would silently re-create the hazard."""
    go(["insights", "chats", "--export"])
    assert not (go.root / ".cage" / "out").exists()


# ── 4. refusals ───────────────────────────────────────────────────────────────

def test_an_unknown_suffix_is_a_typed_refusal_naming_what_cage_writes(go, tmp_path):
    """A `CageError` at the read boundary — `error: <msg>` + exit 1, never a traceback
    and never a silently-skipped write."""
    _, err = go(["insights", "chats", "--export", str(tmp_path / "x.pdf")], expect_exit=1)
    assert ".pdf" in err and ".csv" in err and ".json" in err


def test_a_format_the_view_cannot_produce_refuses_instead_of_writing_an_empty_file(
        go, tmp_path):
    dest = tmp_path / "why.csv"
    _, err = go(["insights", "why", "c_1", "--export", str(dest)], expect_exit=1)
    assert "no csv renderer" in err
    assert not dest.exists()   # an empty CSV would read as "this view has no rows"


# ── 5. the fan-out gate ───────────────────────────────────────────────────────

def _leaves():
    """(path, flags) for every leaf command the live parser knows."""
    out = {}

    def walk(par, path):
        flags = {o for a in par._actions for o in a.option_strings}
        sub = next((a for a in par._actions
                    if isinstance(a, argparse._SubParsersAction)), None)
        if sub:
            for name, sp in sub.choices.items():
                walk(sp, path + [name])
            return
        out[" ".join(path)] = flags
    walk(cli.build_parser(), [])
    return out


def test_every_report_and_insight_is_exportable():
    """The `_WIRING_ARTIFACTS` rule in export form: a new insight lands here, it does
    not get an exemption. Add `_export_flags(<parser>, "<verb path>")` — never relax
    this set."""
    leaves = _leaves()
    missing = sorted(v for v in EXPECTED_VIEWS
                     if "--export" not in leaves.get(v, set()))
    assert not missing, f"these views cannot be exported: {missing}"
    extra = sorted(p for p, f in leaves.items()
                   if "--export" in f and p not in EXPECTED_VIEWS)
    assert not extra, f"these grew --export without landing in EXPECTED_VIEWS: {extra}"


def test_every_exportable_view_names_itself():
    """`view=` is set on the parser, not at the handler, so an artifact's name and its
    `view=` field cannot disagree with the command that produced it."""
    p = cli.build_parser()
    for path in sorted(EXPECTED_VIEWS):
        args = p.parse_args([*path.split(), *(["x"] if path == "insights commit" else []),
                             *(["c_1"] if path == "insights why" else [])])
        assert getattr(args, "view", None) == VIEW_LABELS.get(path, path)


# ── 6. the stamp itself ───────────────────────────────────────────────────────

def test_the_run_stamp_is_local_time_with_an_offset(monkeypatch):
    monkeypatch.delenv("CAGE_RUN_STAMP", raising=False)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}([+-]\d{2}:\d{2}|Z)",
                        runstamp.now())


def test_an_unparseable_pinned_stamp_degrades_rather_than_raising():
    """Metadata must never be able to fail a read."""
    assert runstamp.slug("not a timestamp") == "not-a-timestamp"
    assert runstamp.slug("") == "run"


def test_view_slug_folds_the_verb_path():
    assert runstamp.view_slug("insights chats") == "insights-chats"


def test_available_reports_only_what_the_view_actually_has():
    assert viewexport.available(text="x", payload={}) == ("text", "json")
    assert viewexport.available(text="x", csv_text="c", payload={}) == ("text", "csv",
                                                                        "json")


# ── 7. EXPORT-SCOPE: the three report-shaped views v0.48.0's scope line missed ──

def test_authorship_summary_exports_all_three_formats(go):
    """It owns a `render_authorship_csv`, so its artifact must carry the CSV. It had no
    `--export` at all because its handler kept a hand-rolled `csv_dest` branch instead
    of routing through `emit` — the duplication the chokepoint exists to remove."""
    _, err = go(["authorship", "summary", "--export"])
    d = _outdir(go.root, "authorship summary")
    assert sorted(p.name for p in d.iterdir()) == ["authorship-summary.csv",
                                                   "authorship-summary.json",
                                                   "authorship-summary.txt"]
    assert str(d) in err


def test_a_csv_less_leaf_exports_only_the_formats_it_has(go):
    """A view that owns no CSV renderer writes text + JSON and
    refuses CSV rather than writing an empty one (an empty CSV reads as *no rows*)."""
    go(["insights", "why", "c_1", "--export"])
    d = _outdir(go.root, "insights why")
    assert sorted(p.name for p in d.iterdir()) == ["insights-why.json",
                                                   "insights-why.txt"]


@pytest.mark.parametrize("argv", [
    ["authorship", "summary"],
])
def test_export_never_changes_these_views_stdout(go, argv):
    """The binding gate, extended to the EXPORT-SCOPE views: stdout is byte-identical
    with and without `--export`. If a future export feature needs stdout to move, the
    feature is wrong."""
    plain, _ = go(argv)
    exported, _ = go([*argv, "--export"])
    assert plain == exported
