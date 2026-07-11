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
    with pytest.raises(CageError, match="cage init"):
        pricestoml.set_price(proj, "x", "m", ROW)


def test_every_mutation_leaves_a_parseable_file(root):
    """The sharpest edge: a bad write would make capture silently fall back to the
    bundled table. Every mutation must leave a tomllib-clean file behind."""
    pricestoml.set_price(root, "a", "m.dotted-1.5", ROW)
    pricestoml.set_alias(root, "", "copilot/auto", "a/m.dotted-1.5")
    pricestoml.update_meta(root, {"prices_version": "2026-07-11"})
    pricestoml.set_price(root, "a", "m.dotted-1.5", {**ROW, "input": 9.0})
    pricestoml.parse(_policy(root))  # raises on corruption
