"""`policy.toml` → `cage.toml`: the resolved-name fallback, the both-present
precedence + warning, and the `cage setup` migration (Task B of the config pair).

The invariant under test is **never a breaking rename**: releases ≤ v0.35 wrote
`policy.toml` and are on PyPI, so a real user's on-disk `policy.toml` must keep
working untouched. `cage.toml` is canonical and wins when both exist; the loser is
named, never silently ignored.
"""
from __future__ import annotations

from cage import cleanup, cli, initcmd, paths, policy


def _base(root):
    b = root / ".cage"
    b.mkdir(parents=True, exist_ok=True)
    return b


# ── resolution + fallback ─────────────────────────────────────────────────────

def test_fresh_project_resolves_to_cage_toml(proj):
    # Neither file on disk ⇒ the canonical name a scaffold will write.
    assert paths.Footprint(proj).policy.name == "cage.toml"
    assert paths.Footprint(proj).shadowed_config is None


def test_legacy_policy_toml_alone_still_resolves_and_loads(proj):
    base = _base(proj)
    (base / "policy.toml").write_text("[budgets]\ndaily_usd = 7.0\n", encoding="utf-8")
    foot = paths.Footprint(proj)
    assert foot.policy.name == "policy.toml"          # fallback, untouched
    assert foot.shadowed_config is None                # only one file — nothing shadowed
    assert policy.load(foot.policy)["budgets"]["daily_usd"] == 7.0


def test_cage_toml_alone_resolves(proj):
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    assert paths.Footprint(proj).policy.name == "cage.toml"


# ── both present: cage.toml wins, the leftover is named ───────────────────────

def test_both_present_cage_toml_wins_and_names_the_shadowed_file(proj):
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    (base / "policy.toml").write_text("[budgets]\ndaily_usd = 9.0\n", encoding="utf-8")
    foot = paths.Footprint(proj)
    assert foot.policy.name == "cage.toml"                       # winner
    assert policy.load(foot.policy)["budgets"]["daily_usd"] == 5.0  # cage.toml's value
    assert foot.shadowed_config is not None
    assert foot.shadowed_config.name == "policy.toml"           # the ignored leftover


def test_both_present_warns_once_on_stderr_stdout_unchanged(proj, monkeypatch, capsys):
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    (base / "policy.toml").write_text("[budgets]\ndaily_usd = 9.0\n", encoding="utf-8")
    monkeypatch.chdir(proj)
    assert cli.main(["insights", "chats"]) == 0
    cap = capsys.readouterr()
    assert "policy.toml is ignored" in cap.err and "cage.toml takes precedence" in cap.err
    assert "policy.toml" not in cap.out  # the warning is stderr-only — stdout stays clean


# ── cage setup migration ──────────────────────────────────────────────────────

def test_setup_migrates_legacy_policy_toml(proj):
    base = _base(proj)
    (base / "policy.toml").write_text("[budgets]\ndaily_usd = 3.0\n", encoding="utf-8")
    info = initcmd.run(proj, pointer=False)
    assert info["migrated_config"] == str(base / "cage.toml")
    assert (base / "cage.toml").exists() and not (base / "policy.toml").exists()
    # content preserved through the rename (not overwritten by the bundled default)
    assert policy.load(base / "cage.toml")["budgets"]["daily_usd"] == 3.0


def test_setup_migration_is_idempotent_and_non_destructive_when_both_exist(proj):
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    (base / "policy.toml").write_text("[budgets]\ndaily_usd = 9.0\n", encoding="utf-8")
    info = initcmd.run(proj, pointer=False)
    assert info["migrated_config"] is None                # nothing renamed
    assert (base / "cage.toml").exists() and (base / "policy.toml").exists()  # both kept


def test_setup_on_fresh_project_writes_cage_toml_no_migration(proj):
    info = initcmd.run(proj, pointer=False)
    assert info["migrated_config"] is None
    assert (proj / ".cage" / "cage.toml").exists()


# ── cleanup never touches either config name ──────────────────────────────────

def test_cleanup_never_list_protects_both_config_names():
    assert "cage.toml" in cleanup.NEVER and "policy.toml" in cleanup.NEVER
