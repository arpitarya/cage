"""`prices.toml` — the vendor-price split out of `cage.toml` (prices-toml plan §3).

The invariant under test is **the money does not move**: prices resolve identically
whether they live inline in a legacy `cage.toml` (fallback) or in their own
`prices.toml`. `prices.toml` wins when both carry prices; the loser is named, never
silently ignored. `[meta]` splits per key so a staleness check can't quietly stop
firing. Mirrors `test_config_rename` (the `policy.toml → cage.toml` precedent).
"""
from __future__ import annotations

from cage import cleanup, initcmd, paths, policy


def _base(root):
    b = root / ".cage"
    b.mkdir(parents=True, exist_ok=True)
    return b


_OPUS = '[prices.anthropic."claude-opus-4-8"]\ninput = {i}\noutput = 25.0\ncache_read = 0.5\n'


# ── resolution + fallback ─────────────────────────────────────────────────────

def test_fresh_project_resolves_to_prices_toml(proj):
    _base(proj)
    (proj / ".cage" / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    foot = paths.Footprint(proj)
    # No prices.toml on disk ⇒ the resolver falls back to the policy file (legacy prices).
    assert foot.prices.name == "cage.toml"
    assert foot.shadowed_prices is None
    # A prices.toml present ⇒ it is the resolved prices source.
    (proj / ".cage" / "prices.toml").write_text("[meta]\nprices_version = \"2026-07-14\"\n",
                                                encoding="utf-8")
    assert paths.Footprint(proj).prices.name == "prices.toml"


def test_legacy_inline_prices_resolve_via_fallback(proj):
    # A project with prices still inline in cage.toml (releases ≤ v0.35) resolves them
    # untouched — never a breaking change.
    base = _base(proj)
    (base / "cage.toml").write_text(_OPUS.format(i="111.0"), encoding="utf-8")
    pol = policy.load(paths.Footprint(proj).policy)
    assert pol["prices"]["anthropic"]["claude-opus-4-8"]["input"] == 111.0


def test_prices_toml_overrides_bundle(proj):
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    (base / "prices.toml").write_text(_OPUS.format(i="222.0"), encoding="utf-8")
    pol = policy.load(paths.Footprint(proj).policy)
    assert pol["prices"]["anthropic"]["claude-opus-4-8"]["input"] == 222.0
    # a non-price section still resolves from cage.toml (one merged dict)
    assert pol["budgets"]["daily_usd"] == 5.0


# ── both present: prices.toml wins, the legacy block is named ──────────────────

def test_both_present_prices_toml_wins_and_names_the_shadowed_block(proj):
    base = _base(proj)
    (base / "cage.toml").write_text(_OPUS.format(i="111.0"), encoding="utf-8")
    (base / "prices.toml").write_text(_OPUS.format(i="222.0"), encoding="utf-8")
    foot = paths.Footprint(proj)
    assert foot.prices.name == "prices.toml"
    assert policy.load(foot.policy)["prices"]["anthropic"]["claude-opus-4-8"]["input"] == 222.0
    assert foot.shadowed_prices is not None
    assert foot.shadowed_prices.name == "cage.toml"


def test_migrated_cage_toml_shadows_nothing(proj):
    # A cage.toml with no price tables (post-migration) beside a prices.toml is not a
    # shadow — shadowed_prices only fires when the policy file still declares prices.
    base = _base(proj)
    (base / "cage.toml").write_text("[budgets]\ndaily_usd = 5.0\n", encoding="utf-8")
    (base / "prices.toml").write_text(_OPUS.format(i="222.0"), encoding="utf-8")
    assert paths.Footprint(proj).shadowed_prices is None


# ── [meta] splits per key ─────────────────────────────────────────────────────

def test_meta_splits_per_key_across_the_two_files(proj):
    initcmd.run(proj)
    foot = paths.Footprint(proj)
    b_meta = policy.bundled_raw()["meta"]
    cage_meta = policy.load_project_raw(foot.policy)["meta"]
    prices_meta = policy.load_project_raw(foot.prices)["meta"]
    assert set(cage_meta) == {"cage_version", "policy_version"}
    assert set(prices_meta) == {"prices_version", "prices_date"}
    # the merged dict reconstructs the full [meta] — same shape consumers always read
    assert policy.load(foot.policy)["meta"] == b_meta


def test_bundled_cage_version_is_derived_never_a_stale_literal():
    # `data/cage.toml` ships no `cage_version` literal at all — `policy._bundled`
    # derives it live from `cage.__version__` (a hand-maintained copy drifted eleven
    # releases before this test existed). This is the drift-impossible guard: it fails
    # the moment the two ever disagree, whatever the release number becomes.
    from cage import __version__
    assert policy.bundled_raw()["meta"]["cage_version"] == __version__


def test_fresh_scaffold_stamps_the_live_cage_version(proj):
    # A newly `cage setup`-scaffolded project's cage.toml historical stamp is the
    # version that created it — also the live version, at the moment of creation.
    from cage import __version__
    initcmd.run(proj)
    foot = paths.Footprint(proj)
    assert policy.load_project_raw(foot.policy)["meta"]["cage_version"] == __version__


# ── migration on setup: money-neutral, idempotent ─────────────────────────────

def test_setup_migrates_legacy_inline_prices_money_neutral(proj):
    base = _base(proj)
    # legacy: a customized opus row (differs from bundle) + a bundle-equal sonnet row,
    # both inline in cage.toml, plus a non-price section that must survive.
    (base / "cage.toml").write_text(
        "[meta]\nprices_version = \"2026-07-14\"\nprices_date = \"2026-07-14\"\n"
        "cage_version = \"0.25.0\"\npolicy_version = \"0.26.0\"\n\n"
        + _OPUS.format(i="99.0")
        + '\n[prices.anthropic."claude-sonnet-5"]\ninput = 3.0\noutput = 15.0\ncache_read = 0.3\n'
        + "\n[budgets]\ndaily_usd = 7.0\n", encoding="utf-8")
    before = policy.load(paths.Footprint(proj).policy)

    info = initcmd.run(proj)
    assert info["migrated_prices"]  # a migration happened
    foot = paths.Footprint(proj)
    assert (base / "prices.toml").exists()
    # money preserved exactly: the custom opus override survives, sonnet still resolves
    after = policy.load(foot.policy)
    assert after["prices"]["anthropic"]["claude-opus-4-8"] == \
        before["prices"]["anthropic"]["claude-opus-4-8"]
    assert after["prices"]["anthropic"]["claude-sonnet-5"] == \
        before["prices"]["anthropic"]["claude-sonnet-5"]
    # cage.toml no longer declares prices; the non-price section and meta split survive
    cage_raw = policy.load_project_raw(foot.policy)
    assert "prices" not in cage_raw
    assert cage_raw["budgets"]["daily_usd"] == 7.0
    assert set(cage_raw["meta"]) == {"cage_version", "policy_version"}
    assert foot.shadowed_prices is None  # a clean migration leaves nothing shadowed


def test_setup_migration_is_idempotent(proj):
    base = _base(proj)
    (base / "cage.toml").write_text(_OPUS.format(i="99.0") + "\n[budgets]\ndaily_usd = 7.0\n",
                                    encoding="utf-8")
    initcmd.run(proj)
    cage_after = (base / "cage.toml").read_text(encoding="utf-8")
    prices_after = (base / "prices.toml").read_text(encoding="utf-8")
    # second run migrates nothing and rewrites nothing
    info2 = initcmd.run(proj)
    assert info2["migrated_prices"] is None
    assert (base / "cage.toml").read_text(encoding="utf-8") == cage_after
    assert (base / "prices.toml").read_text(encoding="utf-8") == prices_after


# ── cleanup never touches it ──────────────────────────────────────────────────

def test_cleanup_never_lists_prices_toml():
    assert "prices.toml" in cleanup.NEVER
