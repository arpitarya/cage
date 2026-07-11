"""Family-prefix price fallback + the explicit-UNPRICED signal (no silent $0)."""
from __future__ import annotations

import pytest

from cage import policy, prices, report
from cage import metering as meter

# A minimal, explicit price table — independent of the bundled policy so the
# numbers below never drift if data/policy.toml is retuned.
POL = {"prices": {"anthropic": {
    "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3},
    "claude-sonnet-4-5": {"input": 3.3, "output": 16.5, "cache_read": 0.33},
    "claude-opus-4-8": {"input": 15.0, "output": 75.0, "cache_read": 1.5},
}}}


def test_exact_match_still_wins():
    row, match, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-6")
    assert match == "exact" and key == "claude-sonnet-4-6"
    assert row["input"] == 3.0


def test_bundled_policy_prices_fable_and_mythos():
    # claude-fable-5 shares only `claude` with opus/sonnet/haiku (< 2 segments), so
    # without its own row it would price at $0. The bundled policy must carry it.
    pol = policy.load(None)  # bundled data/policy.toml
    for model in ("claude-fable-5", "claude-mythos-5"):
        row, match, key = policy.price_match(pol, "anthropic", model)
        assert match == "exact" and key == model, f"{model} not priced exactly"
        assert (row["input"], row["output"]) == (10.0, 50.0)


def test_dated_id_resolves_to_family_row():
    # A full dated Claude Code id with no exact row → its family row's numbers.
    row, match, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-5-20250929")
    assert match == "family" and key == "claude-sonnet-4-5"
    assert (row["input"], row["output"]) == (3.3, 16.5)
    # And the cost path uses those per-million numbers: 1M in = $3.30.
    assert prices.call_cost_usd(POL, "anthropic", "claude-sonnet-4-5-20250929",
                                1_000_000, 0) == pytest.approx(3.30, abs=1e-6)


def test_cross_family_never_borrows():
    # A dated opus id must NOT price off any sonnet row — brand+tier must agree.
    pol = {"prices": {"anthropic": {
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0, "cache_read": 0.3}}}}
    row, match, key = policy.price_match(pol, "anthropic", "claude-opus-4-1-20250805")
    assert match == "none" and key is None
    assert row == {"input": 0.0, "output": 0.0, "cache_read": 0.0}


def test_unknown_model_reports_unpriced_not_zero_dollars(proj):
    # A genuinely unknown model (no exact, no family, no self-cost) must surface as
    # UNPRICED in the report rather than disappear as a $0 line in the totals.
    meter.record_call(route="chat", provider="anthropic", model="claude-mystery-9",
                      tokens_in=1_000_000, tokens_out=0, est_cost_usd=0.0, root=proj)
    rep = report.summarize(proj, POL, dim="model")
    assert rep["total"]["usd"] == 0.0
    assert "anthropic/claude-mystery-9" in rep["unpriced"]
    assert "UNPRICED" in report.render_report(rep)


def test_family_priced_call_is_flagged_approximate(proj):
    meter.record_call(route="chat", provider="anthropic",
                      model="claude-sonnet-4-5-20250929",
                      tokens_in=1_000_000, tokens_out=0, est_cost_usd=0.0, root=proj)
    rep = report.summarize(proj, POL, dim="model")
    assert rep["total"]["usd"] == pytest.approx(3.30, abs=1e-6)  # priced by family
    assert rep["family"].get("claude-sonnet-4-5-20250929") == "claude-sonnet-4-5"
    assert "priced by family" in report.render_report(rep)
    assert not rep["unpriced"]


def test_effort_suffix_normalizes_to_family():
    # Effort tiers bill at the same per-token rate (verified 2026-07-11) — a tier
    # variant prices at the base row, footnoted family, never exact.
    row, match, key = policy.price_match(POL, "anthropic", "claude-opus-4-8-high")
    assert match == "family" and key == "claude-opus-4-8"
    assert row["input"] == 15.0


def test_dot_dash_punctuation_normalizes_to_family():
    # Copilot stamps dotted ids (claude-sonnet-4.6); rows are dashed. Method law:
    # even a full normalized equality renders family, never exact.
    row, match, key = policy.price_match(POL, "anthropic", "claude-sonnet-4.6")
    assert match == "family" and key == "claude-sonnet-4-6"
    assert row["input"] == 3.0


def test_copilot_route_prefix_strips_before_matching():
    # Real field key: VS Code Copilot stamps modelId `copilot/<model>` with
    # provider inferred → anthropic (transcript._copilot_provider).
    row, match, key = policy.price_match(POL, "anthropic", "copilot/claude-sonnet-4.6")
    assert match == "family" and key == "claude-sonnet-4-6"


def test_copilot_auto_stays_unpriced():
    # The bare router id strips to `auto` and must match nothing — a router priced
    # silently is a wrong number; `cage prices alias` is the explicit way out.
    row, match, key = policy.price_match(policy.load(None), "", "copilot/auto")
    assert match == "none" and key is None


def test_unknown_route_prefix_is_not_stripped():
    # The prefix list is closed — an unrecognized router must surface UNPRICED.
    _, match, _ = policy.price_match(POL, "anthropic", "vendor/claude-sonnet-4-6")
    assert match == "none"


def test_alias_beats_family_and_dangling_alias_is_none():
    pol = {"prices": {"anthropic": POL["prices"]["anthropic"]},
           "alias": {"anthropic": {"claude-sonnet-4.6":
                                   {"to": "anthropic/claude-opus-4-8"}}}}
    row, match, key = policy.price_match(pol, "anthropic", "claude-sonnet-4.6")
    assert match == "alias" and key == "anthropic/claude-opus-4-8"
    assert row["input"] == 15.0  # explicit routing beats the family heuristic
    pol["alias"]["anthropic"]["claude-sonnet-4.6"] = {"to": "anthropic/nope"}
    row, match, key = policy.price_match(pol, "anthropic", "claude-sonnet-4.6")
    assert match == "none" and key is None  # broken route surfaces, never guesses


def test_alias_with_empty_provider_prices_at_target():
    pol = {"prices": POL["prices"],
           "alias": {"": {"copilot/auto": {"to": "anthropic/claude-sonnet-4-6"}}}}
    row, match, key = policy.price_match(pol, "", "copilot/auto")
    assert match == "alias" and key == "anthropic/claude-sonnet-4-6"
    assert row["input"] == 3.0


def test_dotted_minor_now_family_matches_base():
    # Behavior change vs pre-0.19 (documented in the changelog): `.`→`-` folding
    # means a dotted minor with no exact row family-prices at the base row —
    # footnoted approximate, and current minors ship exact bundled rows.
    pol = {"prices": {"openai": {"gpt-5": {"input": 1.25, "output": 10.0,
                                           "cache_read": 0.125}}}}
    _, match, key = policy.price_match(pol, "openai", "gpt-5.7")
    assert match == "family" and key == "gpt-5"


def test_bundled_rows_carry_researched_2026_07_rates():
    # Spot-check the researched bundle (sources cited in data/policy.toml).
    pol = policy.load(None)
    expect = {
        ("anthropic", "claude-opus-4-6"): (5.0, 25.0, 0.50),
        ("anthropic", "claude-sonnet-5"): (3.0, 15.0, 0.30),   # standard, not intro
        ("anthropic", "claude-haiku-3-5"): (0.80, 4.0, 0.08),
        ("openai", "gpt-5.5"): (5.0, 30.0, 0.50),              # cache_read fixed
        ("openai", "gpt-5.4"): (2.50, 15.0, 0.25),             # cache_read fixed
        ("openai", "gpt-5.3-codex"): (1.75, 14.0, 0.175),
        ("openai", "gpt-5.6-terra"): (2.50, 15.0, 0.25),
    }
    for (prov, model), (i, o, cr) in expect.items():
        row, match, _ = policy.price_match(pol, prov, model)
        assert match == "exact", f"{model} must have its own row"
        assert (row["input"], row["output"], row["cache_read"]) == (i, o, cr), model


def test_opus_4_5_never_prices_at_retired_opus_4():
    # Without an explicit claude-opus-4-5 row the 3-segment tie would break
    # lexicographically onto claude-opus-4 — the retired 15/75 rate. The bundled
    # row is load-bearing; this pins it.
    pol = policy.load(None)
    row, match, key = policy.price_match(pol, "anthropic", "claude-opus-4-5")
    assert match == "exact" and row["input"] == 5.0
    row, match, key = policy.price_match(pol, "anthropic", "claude-opus-4-5-20251101")
    assert match == "family" and key == "claude-opus-4-5" and row["input"] == 5.0
    # And the dated ids of the genuinely retired models keep their real 15/75.
    row, match, key = policy.price_match(pol, "anthropic", "claude-opus-4-1-20250805")
    assert match == "family" and key == "claude-opus-4-1" and row["input"] == 15.0


def test_real_field_dated_haiku_id_family_matches():
    pol = policy.load(None)
    row, match, key = policy.price_match(pol, "anthropic", "claude-haiku-4-5-20251001")
    assert match == "family" and key == "claude-haiku-4-5"


def test_longest_prefix_tiebreak_is_deterministic():
    # claude-sonnet-4-5-x shares 4 segs with -4-5 but only 3 with -4-6 → longest wins.
    _, _, key = policy.price_match(POL, "anthropic", "claude-sonnet-4-5-20250101")
    assert key == "claude-sonnet-4-5"
    # Equal-length tie → lexicographically smallest key, regardless of dict order.
    tie = {"prices": {"anthropic": {
        "claude-sonnet-4-6": {"input": 9.0, "output": 9.0, "cache_read": 0.0},
        "claude-sonnet-4-5": {"input": 1.0, "output": 1.0, "cache_read": 0.0}}}}
    rev = {"prices": {"anthropic": dict(reversed(list(tie["prices"]["anthropic"].items())))}}
    # "claude-sonnet-4" has 3 common segments with both → tie → "…-4-5" (lex-min).
    for p in (tie, rev):
        _, match, key = policy.price_match(p, "anthropic", "claude-sonnet-4")
        assert match == "family" and key == "claude-sonnet-4-5"


# ── policy.load merge granularity + raw readers (plan §3.3) ──────────────────

def test_project_price_row_no_longer_wipes_bundled_provider(tmp_path):
    # Pre-0.19 the merge was provider-level: one project row under
    # [prices.anthropic] silently dropped every bundled anthropic sibling.
    p = tmp_path / "policy.toml"
    p.write_text('[prices.anthropic."my-model"]\ninput = 1.0\noutput = 2.0\n'
                 'cache_read = 0.1\n', encoding="utf-8")
    pol = policy.load(p)
    assert "my-model" in pol["prices"]["anthropic"]
    assert "claude-fable-5" in pol["prices"]["anthropic"]  # bundled sibling survives


def test_project_row_shadows_same_bundled_key(tmp_path):
    p = tmp_path / "policy.toml"
    p.write_text('[prices.anthropic."claude-opus-4-8"]\ninput = 9.0\noutput = 9.0\n'
                 'cache_read = 0.9\n', encoding="utf-8")
    pol = policy.load(p)
    assert pol["prices"]["anthropic"]["claude-opus-4-8"]["input"] == 9.0


def test_meta_alias_cleanup_sections_survive_load(tmp_path):
    p = tmp_path / "policy.toml"
    p.write_text('[meta]\nprices_version = "2099-01-01"\n'
                 '[alias.""."copilot/auto"]\nto = "anthropic/claude-sonnet-4-6"\n'
                 '[cleanup]\ndays = 7\n', encoding="utf-8")
    pol = policy.load(p)
    assert pol["meta"]["prices_version"] == "2099-01-01"
    assert pol["alias"][""]["copilot/auto"]["to"] == "anthropic/claude-sonnet-4-6"
    assert policy.cleanup_days(pol) == 7


def test_raw_readers_keep_sides_separate(tmp_path):
    p = tmp_path / "policy.toml"
    p.write_text('[prices.x."m"]\ninput = 1.0\noutput = 1.0\ncache_read = 0.1\n',
                 encoding="utf-8")
    bundled = policy.bundled_raw()
    project = policy.load_project_raw(p)
    assert "x" not in bundled.get("prices", {})
    assert list(project["prices"]) == ["x"]
    assert policy.load_project_raw(tmp_path / "absent.toml") == {}
    assert bundled["meta"]["prices_version"]  # the bundle is stamped
