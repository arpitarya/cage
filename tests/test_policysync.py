"""`cage policy sync`/`diff` — categories, the two safety invariants, delegation."""
from __future__ import annotations

import json
import os

import pytest

from cage import cli, initcmd, policy, policysync, pricescmd, pricestoml
from cage.errors import CageError
from cage.paths import Footprint


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage").mkdir()
    monkeypatch.chdir(proj)
    return proj


def _policy_path(root):
    return root / ".cage" / "policy.toml"


def _strip_to_v016(root):
    """Rewrite the inited policy to the v0.16-era byte-shape: no ``[meta]``,
    no ``[cleanup]``, no ``capture.import_before_export`` (the only non-pricing
    keys the bundle has gained since — verified against git history)."""
    p = _policy_path(root)
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
    p.write_text("".join(out), encoding="utf-8")


@pytest.fixture
def v016(root):
    initcmd.run(root)
    _strip_to_v016(root)
    return root


# ── the two safety invariants (never skipped — the safety story) ─────────────

def test_neutrality_apply_keeps_every_derived_view_byte_identical(v016, seeded, capsys):
    """Zero-customization project: --apply must not change one byte of any
    derived view — adds only pin defaults `policy.load` was already using."""
    views = [["report"], ["report", "--by", "model"], ["insights", "attrib"],
             ["insights", "budget"], ["human", "show"], ["insights", "trend"],
             ["insights", "matrix"]]

    def snap():
        outs = []
        for v in views:
            assert cli.main(v) == 0
            outs.append(capsys.readouterr().out)
        return outs

    before = snap()
    assert cli.main(["policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    assert snap() == before


def test_apply_is_idempotent_second_run_byte_identical_noop(v016, capsys):
    assert cli.main(["policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    first = _policy_path(v016).read_bytes()
    assert cli.main(["policy", "sync", "--apply"]) == 0
    out = capsys.readouterr().out
    assert _policy_path(v016).read_bytes() == first
    assert "nothing to write — already in sync" in out


# ── categories ───────────────────────────────────────────────────────────────

def test_v016_shape_lists_exact_adds_then_applies_them(v016, capsys):
    assert cli.main(["policy", "diff"]) == 0
    out = capsys.readouterr().out
    assert "add (3)" in out
    assert "+ [capture] import_before_export = true" in out
    assert "+ [cleanup] days = 30" in out and "+ [cleanup] enabled = true" in out
    assert "bundled policy defaults are newer" in out
    assert cli.main(["policy", "sync", "--apply"]) == 0
    applied = capsys.readouterr().out
    assert "✔ [cleanup] added" in applied
    assert "✔ [meta] policy_version stamped" in applied
    proj_raw = policy.load_project_raw(_policy_path(v016))
    assert proj_raw["cleanup"] == {"enabled": True, "days": 30}
    assert proj_raw["capture"]["import_before_export"] is True
    assert proj_raw["meta"]["policy_version"] == \
        policy.bundled_raw()["meta"]["policy_version"]
    assert "# added by cage policy sync" in _policy_path(v016).read_text()


def test_hand_edited_value_is_kept_customized_never_clobbered(v016, capsys):
    """The pre-mortem killer: an un-marked hand edit (the documented way to set
    budgets) must classify as customized — `--apply` and even `--yes all` must
    never flip it back to the bundled default."""
    p = _policy_path(v016)
    p.write_text(p.read_text().replace("daily_usd = 25.00", "daily_usd = 50.00"))
    assert cli.main(["policy", "sync", "--apply", "--yes", "all"]) == 0
    out = capsys.readouterr().out
    assert "keep (1)" in out and "[budgets] daily_usd = 50.0 (bundled 25.0)" in out
    assert policy.load_project_raw(p)["budgets"]["daily_usd"] == 50.0


def test_marked_and_block_owned_tables_stay_customized(v016, capsys):
    p = _policy_path(v016)
    p.write_text(p.read_text().replace(
        "[human]", f"[human]   {pricestoml.CUSTOM_MARK}").replace(
        "rate_usd_per_hr = 80", "rate_usd_per_hr = 80"))
    p.write_text(p.read_text().replace("rate_usd_per_hr = 80", "rate_usd_per_hr = 120"))
    d = policysync.sync_view(v016)
    marked = [c for c in d["customized"] if c["reason"] == "marked"]
    assert [(c["table"], c["key"]) for c in marked] == [("human", "rate_usd_per_hr")]
    assert cli.main(["policy", "sync", "--apply", "--yes", "all"]) == 0
    assert policy.load_project_raw(p)["human"]["rate_usd_per_hr"] == 120


def test_update_category_refreshes_stale_old_default(v016, monkeypatch, capsys):
    """A project stamped with an era whose recorded old default it still carries
    → update, old→new, applied without confirmation."""
    monkeypatch.setattr(policysync, "DEFAULT_CHANGES",
                        {("human", "rate_usd_per_hr"): (("0.25.0", 60),)})
    p = _policy_path(v016)
    p.write_text(p.read_text().replace("rate_usd_per_hr = 80", "rate_usd_per_hr = 60"))
    pricestoml.update_meta(v016, {"policy_version": "0.20.0"})
    assert cli.main(["policy", "diff"]) == 0
    out = capsys.readouterr().out
    assert "update (1)" in out and "~ [human] rate_usd_per_hr: 60 → 80" in out
    assert cli.main(["policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    assert policy.load_project_raw(p)["human"]["rate_usd_per_hr"] == 80
    # the refresh must NOT mark the table user-owned — it stays sync-updatable
    assert pricestoml.CUSTOM_MARK not in p.read_text().split("[human]")[1].split("[")[0]


def test_update_known_version_differing_from_old_default_is_customized(v016, monkeypatch):
    monkeypatch.setattr(policysync, "DEFAULT_CHANGES",
                        {("human", "rate_usd_per_hr"): (("0.25.0", 60),)})
    p = _policy_path(v016)
    p.write_text(p.read_text().replace("rate_usd_per_hr = 80", "rate_usd_per_hr = 95"))
    pricestoml.update_meta(v016, {"policy_version": "0.20.0"})
    d = policysync.sync_view(v016)
    assert not d["update"] and not d["confirm"]
    assert any(c["key"] == "rate_usd_per_hr" and c["reason"] == "edited"
               for c in d["customized"])


def test_confirm_bucket_pre_version_needs_yes(v016, monkeypatch, capsys):
    """Pre-policy_version file + a key whose default actually changed: not
    reconstructable → listed, applied only per --yes (matching prices sync)."""
    monkeypatch.setattr(policysync, "DEFAULT_CHANGES",
                        {("human", "rate_usd_per_hr"): (("0.25.0", 60),)})
    p = _policy_path(v016)
    p.write_text(p.read_text().replace("rate_usd_per_hr = 80", "rate_usd_per_hr = 60"))
    assert cli.main(["policy", "sync"]) == 0
    out = capsys.readouterr().out
    assert "confirm (1)" in out
    assert "cage policy sync --apply --yes human.rate_usd_per_hr" in out
    assert cli.main(["policy", "sync", "--apply"]) == 0  # no --yes → untouched
    out = capsys.readouterr().out
    assert "left untouched (confirm each with --yes" in out
    # the stamp must wait for the confirm bucket — else next run reclassifies
    # the pending rows as customized (undecided ≠ decided)
    assert "policy_version not stamped" in out
    assert policy.load_project_raw(p)["human"]["rate_usd_per_hr"] == 60
    assert cli.main(["policy", "sync", "--apply", "--yes",
                     "human.rate_usd_per_hr"]) == 0
    capsys.readouterr()
    assert policy.load_project_raw(p)["human"]["rate_usd_per_hr"] == 80


def test_orphan_warned_with_version_context_never_deleted(v016, monkeypatch, capsys):
    monkeypatch.setattr(policysync, "REMOVED_KEYS",
                        {("quality", "old_signal"): "0.25.0"})
    p = _policy_path(v016)
    p.write_text(p.read_text().replace('signal = "task_ok"',
                                       'signal = "task_ok"\nold_signal = "x"'))
    assert cli.main(["policy", "sync", "--apply", "--yes", "all"]) == 0
    out = capsys.readouterr().out
    assert "orphan (1)" in out
    assert '⚠ [quality] old_signal = "x" (dropped in v0.25.0)' in out
    assert policy.load_project_raw(p)["quality"]["old_signal"] == "x"


def test_users_own_sections_invisible_own_keys_listed_untouched(v016, capsys):
    p = _policy_path(v016)
    p.write_text(p.read_text() + '\n[my-own-section]\nfoo = 1\n')
    p.write_text(p.read_text().replace('signal = "task_ok"',
                                       'signal = "task_ok"\nmy_note = "hi"'))
    assert cli.main(["policy", "sync", "--apply"]) == 0
    out = capsys.readouterr().out
    assert "my-own-section" not in out  # unknown section: invisible to sync
    assert "your own keys (not in the bundle) — untouched: quality.my_note" in out
    raw = policy.load_project_raw(p)
    assert raw["my-own-section"]["foo"] == 1 and raw["quality"]["my_note"] == "hi"


def test_tools_order_add_roundtrips_and_routes_stay_delegated(v016, capsys):
    p = _policy_path(v016)
    lines = p.read_text().splitlines(keepends=True)
    out, skip = [], False
    for ln in lines:  # drop the [tools] table entirely (next header ends it)
        if ln.strip() == "[tools]":
            skip = True
            continue
        if skip and ln.strip().startswith("["):
            skip = False
        if not skip:
            out.append(ln)
    p.write_text("".join(out))
    assert cli.main(["policy", "diff"]) == 0
    assert "+ [tools] order = [" in capsys.readouterr().out
    assert cli.main(["policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    assert policy.load_project_raw(p)["tools"]["order"] == \
        policy.bundled_raw()["tools"]["order"]


# ── surface behavior ─────────────────────────────────────────────────────────

def test_diff_is_dry_run_and_refuses_apply(v016, capsys):
    before = _policy_path(v016).read_bytes()
    assert cli.main(["policy", "diff"]) == 0
    capsys.readouterr()
    assert _policy_path(v016).read_bytes() == before
    assert cli.main(["policy", "diff", "--apply"]) == 1
    assert "dry-run view" in capsys.readouterr().err


def test_already_in_sync_message_on_current_file(root, capsys):
    initcmd.run(root)
    assert cli.main(["policy", "sync"]) == 0
    out = capsys.readouterr().out
    assert "✔ nothing to do — project policy matches the installed bundle." in out


def test_no_project_policy_points_at_init(root, capsys):
    assert cli.main(["policy", "sync", "--apply"]) == 0
    out = capsys.readouterr().out
    assert "no project policy.toml" in out and "cage setup" in out


def test_corrupt_project_policy_is_a_typed_error(root, capsys):
    _policy_path(root).write_text("not = valid = toml [", encoding="utf-8")
    assert cli.main(["policy", "diff"]) == 1
    err = capsys.readouterr().err
    assert "error:" in err and "policy.toml" in err


@pytest.mark.skipif(os.name == "nt",
                    reason="chmod cannot make a directory unwritable on Windows")
def test_readonly_target_errors_cleanly_no_partial_write(v016, capsys):
    """--apply on an unwritable .cage/ → `error: …` + exit 1, file untouched
    (temp-write + atomic replace: there is no half-written state to leave)."""
    base = _policy_path(v016).parent
    before = _policy_path(v016).read_bytes()
    os.chmod(base, 0o555)
    try:
        assert cli.main(["policy", "sync", "--apply"]) == 1
        assert "error:" in capsys.readouterr().err
        assert _policy_path(v016).read_bytes() == before
    finally:
        os.chmod(base, 0o755)


def test_git_tracked_policy_prints_the_review_with_git_note(v016, capsys):
    """No .bak files — git is the backup, and the output says so."""
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=v016, check=True)
    subprocess.run(["git", "add", ".cage/policy.toml"], cwd=v016, check=True)
    assert cli.main(["policy", "diff"]) == 0
    out = capsys.readouterr().out
    assert "policy.toml is git-tracked — review any applied change with git" in out
    assert ".bak" in out  # "cage writes no .bak files"


def test_delegated_prices_summary_matches_a_direct_prices_sync(v016):
    d = policysync.sync_view(v016)
    assert d["prices_text"] == pricescmd.render_sync(pricescmd.sync_view(v016))


def test_json_envelope(v016, capsys):
    assert cli.main(["policy", "diff", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["schemaVersion"] == "cage.v1" and d["command"] == "policy"
    assert len(d["data"]["add"]) == 3 and d["data"]["updated"] is None


def test_ver_tuple_orders_versions_not_strings():
    assert policysync._ver_tuple("0.9.0") < policysync._ver_tuple("0.10.0")
    assert policysync._ver_tuple("v0.25.0") == (0, 25, 0)
    assert policysync._ver_tuple("") == (0,)


def test_recommendation_fires_only_when_bundle_newer(v016):
    assert policysync.sync_recommendation({}) is not None          # pre-feature
    assert policysync.sync_recommendation({"policy_version": "0.9.0"}) is not None
    bv = policy.bundled_raw()["meta"]["policy_version"]
    assert policysync.sync_recommendation({"policy_version": bv}) is None


# ── wiring: doctor · freshness · init · query ────────────────────────────────

def test_doctor_policy_version_check(v016, capsys):
    assert cli.main(["doctor"]) in (0, 1)
    out = capsys.readouterr().out
    assert "policy-version" in out
    assert "bundled policy defaults are newer" in out
    assert cli.main(["policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    assert cli.main(["doctor"]) in (0, 1)
    out = capsys.readouterr().out
    assert "project policy defaults are current with the bundle" in out


def test_freshness_policy_line_is_opt_in_report_footer_stays_clean(v016, seeded, capsys):
    """Policy drift changes no derived number — the hint lives on doctor and the
    post-commit hook (include_policy=True), never in the report footer."""
    from cage import freshness, policy as _pol
    line = freshness.policy_line(v016)
    assert line and "cage policy sync" in line
    pol = _pol.load(Footprint(v016).policy)
    composed = freshness.freshness(v016, pol, include_policy=True)
    assert line in composed
    assert line not in freshness.freshness(v016, pol)  # default: excluded
    assert cli.main(["report"]) == 0
    assert "cage policy sync" not in capsys.readouterr().out


def test_init_stamps_policy_version_and_prints_pointer(root, capsys):
    # init merged into setup (Phase 3): the scaffold half stamps the bundled policy_version.
    assert cli.main(["setup", "--project-only", "--no-graphify"]) == 0
    assert policy.load_project_raw(_policy_path(root))["meta"]["policy_version"] == \
        policy.bundled_raw()["meta"]["policy_version"]


def test_query_policy_sync_interpolates_live_versions(v016, capsys):
    assert cli.main(["query", "policy-sync"]) == 0
    out = capsys.readouterr().out
    bv = policy.bundled_raw()["meta"]["policy_version"]
    assert bv in out and "unknown (pre-0.25)" in out
    assert "never touched" in out and "§3.10" in out


def test_writes_resolve_to_active_ledger_root(v016, tmp_path, monkeypatch, capsys):
    """--ledger re-bases the whole footprint — the global policy syncs the same."""
    gbase = tmp_path / "elsewhere" / ".cage"
    gbase.mkdir(parents=True)
    (gbase / "policy.toml").write_text("[budgets]\ndaily_usd = 9.0\n", encoding="utf-8")
    assert cli.main(["--ledger", str(gbase), "policy", "sync", "--apply"]) == 0
    capsys.readouterr()
    raw = policy.load_project_raw(gbase / "policy.toml")
    assert raw["budgets"]["daily_usd"] == 9.0          # customized — kept
    assert raw["cleanup"] == {"enabled": True, "days": 30}  # added
    assert raw["meta"]["policy_version"]
    # the *project* policy in cwd was never touched by the --ledger run
    assert "policy_version" not in policy.load_project_raw(
        _policy_path(v016)).get("meta", {})
