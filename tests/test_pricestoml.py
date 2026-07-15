"""The project-policy write layer — text surgery, never a whole-file rewrite."""
from __future__ import annotations

import pytest

from cage import pricestoml
from cage.errors import CageError

ROW = {"input": 2.0, "output": 6.0, "cache_read": 0.2}


@pytest.fixture
def root(proj):
    (proj / ".cage").mkdir()
    return proj


def _policy(root):
    return root / ".cage" / "policy.toml"


def test_set_price_creates_file_with_managed_block(root):
    res = pricestoml.set_price(root, "mistral", "mistral-large-3", ROW)
    assert res["mode"] == "created" and res["before"] is None
    text = _policy(root).read_text()
    assert pricestoml.BLOCK_START in text and pricestoml.BLOCK_END in text
    _, data = pricestoml.parse(_policy(root))  # must re-parse as TOML
    assert data["prices"]["mistral"]["mistral-large-3"] == ROW


def test_set_price_idempotent_no_write(root):
    pricestoml.set_price(root, "mistral", "mistral-large-3", ROW)
    before = _policy(root).read_bytes()
    res = pricestoml.set_price(root, "mistral", "mistral-large-3", ROW)
    assert res["mode"] == "unchanged"
    assert _policy(root).read_bytes() == before


def test_block_regeneration_is_order_independent(root):
    a = {"input": 1.0, "output": 2.0, "cache_read": 0.1}
    b = {"input": 3.0, "output": 4.0, "cache_read": 0.3}
    pricestoml.set_price(root, "x", "m1", a)
    pricestoml.set_price(root, "y", "m2", b)
    one = _policy(root).read_bytes()
    _policy(root).unlink()
    pricestoml.set_price(root, "y", "m2", b)
    pricestoml.set_price(root, "x", "m1", a)
    assert _policy(root).read_bytes() == one  # sorted block ⇒ same bytes either order


def test_inplace_edit_preserves_comments_and_marks_custom(root):
    _policy(root).write_text(
        "# hand-written\n[prices.openai.\"gpt-x\"]\n# above input\ninput = 1.0\n"
        "output = 2.0\ncache_read = 0.1\n", encoding="utf-8")
    res = pricestoml.set_price(root, "openai", "gpt-x",
                               {"input": 5.0, "output": 2.0, "cache_read": 0.1})
    assert res["mode"] == "in-place"
    assert res["before"] == {"input": 1.0, "output": 2.0, "cache_read": 0.1}
    text = _policy(root).read_text()
    assert "# hand-written" in text and "# above input" in text
    assert pricestoml.CUSTOM_MARK in text
    assert "input = 5.0" in text


def test_duplicate_header_refused_and_file_untouched(root):
    # TOML forbids declaring one table twice — a duplicate (e.g. hand-copied into
    # the managed block AND outside it) makes the file unparseable, so the write
    # layer refuses with a clean CageError instead of compounding the damage.
    pricestoml.set_price(root, "x", "m", ROW)  # in the block
    text = _policy(root).read_text()
    corrupted = '[prices.x."m"]\ninput = 9.0\n\n' + text
    _policy(root).write_text(corrupted, encoding="utf-8")
    with pytest.raises(CageError, match="does not parse"):
        pricestoml.set_price(root, "x", "m", {"input": 1.0, "output": 1.0, "cache_read": 0.1})
    assert _policy(root).read_text() == corrupted  # never half-written


def test_alias_with_empty_provider_roundtrips(root):
    res = pricestoml.set_alias(root, "", "copilot/auto", "anthropic/claude-sonnet-4-6")
    assert res["mode"] in ("created", "block")
    _, data = pricestoml.parse(_policy(root))
    assert data["alias"][""]["copilot/auto"]["to"] == "anthropic/claude-sonnet-4-6"


def test_update_meta_inplace_outside_block(root):
    _policy(root).write_text("[meta]\nprices_version = \"2020-01-01\"\n", encoding="utf-8")
    pricestoml.update_meta(root, {"prices_version": "2026-07-11"})
    _, data = pricestoml.parse(_policy(root))
    assert data["meta"]["prices_version"] == "2026-07-11"


def test_parse_failure_raises_cageerror(root):
    _policy(root).write_text("not = valid = toml [", encoding="utf-8")
    with pytest.raises(CageError, match="does not parse"):
        pricestoml.set_price(root, "x", "m", ROW)


def test_missing_footprint_raises_with_init_hint(proj):
    with pytest.raises(CageError, match="cage setup"):
        pricestoml.set_price(proj, "x", "m", ROW)


def test_every_mutation_leaves_a_parseable_file(root):
    """The sharpest edge: a bad write would make capture silently fall back to the
    bundled table. Every mutation must leave a tomllib-clean file behind."""
    pricestoml.set_price(root, "a", "m.dotted-1.5", ROW)
    pricestoml.set_alias(root, "", "copilot/auto", "a/m.dotted-1.5")
    pricestoml.update_meta(root, {"prices_version": "2026-07-11"})
    pricestoml.set_price(root, "a", "m.dotted-1.5", {**ROW, "input": 9.0})
    pricestoml.parse(_policy(root))  # raises on corruption


# ── policy-sync writer extensions (add_table / set_table / list values) ──────

def test_add_table_lands_before_block_with_comment_and_no_mark(root):
    pricestoml.set_price(root, "x", "m", ROW)  # creates the managed block
    res = pricestoml.add_table(root, ("cleanup",), {"enabled": True, "days": 30},
                               comment="# added by cage policy sync (v0.25.0)")
    assert res["mode"] == "added" and res["before"] is None
    text = _policy(root).read_text()
    assert text.index("# added by cage policy sync") < text.index(pricestoml.BLOCK_START)
    assert pricestoml.CUSTOM_MARK not in text.split(pricestoml.BLOCK_START)[0]
    _, data = pricestoml.parse(_policy(root))
    assert data["cleanup"] == {"enabled": True, "days": 30}


def test_add_table_at_eof_without_block(root):
    _policy(root).write_text("# mine\n[budgets]\ndaily_usd = 50.0", encoding="utf-8")
    pricestoml.add_table(root, ("cleanup",), {"enabled": True, "days": 30})
    text = _policy(root).read_text()
    assert "\n\n[cleanup]\n" in text  # blank-line separated, plain append
    _, data = pricestoml.parse(_policy(root))
    assert data["budgets"]["daily_usd"] == 50.0 and data["cleanup"]["days"] == 30


def test_add_table_idempotent_no_write(root):
    pricestoml.add_table(root, ("cleanup",), {"enabled": True, "days": 30})
    before = _policy(root).read_bytes()
    res = pricestoml.add_table(root, ("cleanup",), {"enabled": True, "days": 30})
    assert res["mode"] == "unchanged"
    assert _policy(root).read_bytes() == before


def test_add_table_existing_edits_in_place_without_mark(root):
    _policy(root).write_text("# note\n[cleanup]\nenabled = true\ndays = 14\n",
                             encoding="utf-8")
    res = pricestoml.add_table(root, ("cleanup",), {"enabled": True, "days": 30})
    assert res["mode"] == "in-place" and res["before"] == {"enabled": True, "days": 14}
    text = _policy(root).read_text()
    assert "# note" in text and pricestoml.CUSTOM_MARK not in text
    assert "days = 30" in text


def test_add_table_refuses_block_owned_table(root):
    pricestoml.set_tool_route(root, "graphify", "anthropic/claude-x")  # in the block
    with pytest.raises(CageError, match="cage-managed block"):
        pricestoml.add_table(root, ("tools", "graphify"), {"price_at": "y/z"})


def test_fmt_value_list_roundtrips(root):
    order = ["graphify", "fux", "router"]
    pricestoml.add_table(root, ("tools",), {"order": order})
    _, data = pricestoml.parse(_policy(root))
    assert data["tools"]["order"] == order


def test_set_table_mark_custom_false_leaves_header_unmarked(root):
    _policy(root).write_text("[human]\nrate_usd_per_hr = 80\n", encoding="utf-8")
    pricestoml.set_table(root, ("human",), {"rate_usd_per_hr": 95},
                         mark_custom=False)
    text = _policy(root).read_text()
    assert pricestoml.CUSTOM_MARK not in text and "rate_usd_per_hr = 95" in text
    pricestoml.set_table(root, ("human",), {"rate_usd_per_hr": 99})  # default marks
    assert pricestoml.CUSTOM_MARK in _policy(root).read_text()


def test_update_meta_subset_leaves_sibling_keys(root):
    """Regression pin: policy sync restamps policy_version only — prices_version
    must survive an update_meta carrying a subset of keys."""
    _policy(root).write_text('[meta]\nprices_version = "2026-07-14"\n', encoding="utf-8")
    pricestoml.update_meta(root, {"policy_version": "0.25.0"})
    _, data = pricestoml.parse(_policy(root))
    assert data["meta"] == {"prices_version": "2026-07-14", "policy_version": "0.25.0"}
