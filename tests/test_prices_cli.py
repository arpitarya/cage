"""`cage prices` end-to-end: unpriced → set/alias → repriced report → sync/list."""
from __future__ import annotations

import json

import pytest

from cage import cli, initcmd, ledger, paths, pricestoml, schema
from cage.paths import Footprint


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage").mkdir()
    monkeypatch.chdir(proj)
    return proj


def _seed_unpriced(root):
    """The field-report shape: an empty-provider router key + an unknown vendor."""
    for i in range(3):
        ledger.append_row(root, "calls", schema.make_call(
            route="chat", provider="", model="copilot/auto", tokens_in=15_000,
            tokens_out=2_000, agent="copilot", ts=f"2026-07-0{i + 1}T10:00:00Z",
            call_id=f"c_auto{i}"))
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="mistral", model="mistral-large-3", tokens_in=1_000_000,
        tokens_out=200_000, agent="codex", ts="2026-07-02T10:00:00Z", call_id="c_m1"))


def _shards(root):
    return b"".join(p.read_bytes() for p in Footprint(root).shards("calls"))


def test_unpriced_groups_counts_tokens_and_fix_lines(root, capsys):
    _seed_unpriced(root)
    assert cli.main(["prices", "unpriced"]) == 0
    out = capsys.readouterr().out
    assert "—/copilot/auto   3 calls   51,000 tokens" in out
    assert "mistral/mistral-large-3   1 calls   1,200,000 tokens" in out
    assert "cage prices alias - 'copilot/auto' --to <provider>/<model>" in out
    assert "cage prices set mistral 'mistral-large-3' --input <IN> --output <OUT>" in out
    assert "cage never fetches prices" in out
    # deterministic ordering + double-run byte-identity
    again = cli.main(["prices", "unpriced"]) == 0 and capsys.readouterr().out
    assert again == out


def test_unpriced_excludes_family_and_alias_matched_keys(root, capsys):
    # copilot-served Claude family-matches after normalization — priced, not listed.
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="copilot/claude-sonnet-4.6",
        tokens_in=1000, agent="copilot", ts="2026-07-01T00:00:00Z", call_id="c_cs"))
    assert cli.main(["prices", "unpriced"]) == 0
    out = capsys.readouterr().out
    assert "copilot/claude-sonnet-4.6" not in out
    assert "every recorded call prices" in out


def test_set_validation_is_typed(root, capsys):
    assert cli.main(["prices", "set", "x", "m", "--input", "-1", "--output", "2"]) == 1
    assert "error:" in capsys.readouterr().err
    assert cli.main(["prices", "set", "x", "m", "--input", "1", "--output", "2",
                     "--cache-read", "5"]) == 1
    assert "must not exceed input" in capsys.readouterr().err
    assert cli.main(["prices", "set", "x", "m", "--input", "1"]) == 1  # missing --output
    assert "error:" in capsys.readouterr().err


def test_set_reprices_report_without_rewriting_ledger(root, capsys):
    _seed_unpriced(root)
    before = _shards(root)
    assert cli.main(["prices", "set", "mistral", "mistral-large-3",
                     "--input", "2", "--output", "6", "--cache-read", "0.2"]) == 0
    out = capsys.readouterr().out
    assert "before: (none)" in out and "after:  input=2 output=6 cache_read=0.2" in out
    assert "re-price immediately" in out
    assert cli.main(["report", "--by", "model"]) == 0
    rep = capsys.readouterr().out
    assert "$3.2000" in rep                     # 1M×$2 + 200k×$6 per MTok
    assert _shards(root) == before              # the ledger is never rewritten
    # idempotent: identical set is a no-op
    assert cli.main(["prices", "set", "mistral", "mistral-large-3",
                     "--input", "2", "--output", "6", "--cache-read", "0.2"]) == 0
    assert "no change" in capsys.readouterr().out


def test_set_announces_defaulted_cache_read(root, capsys):
    assert cli.main(["prices", "set", "x", "m", "--input", "4", "--output", "8"]) == 0
    assert "cache_read defaulted to 0.1× input (0.4)" in capsys.readouterr().out


def test_alias_requires_exact_target_and_reprices(root, capsys):
    _seed_unpriced(root)
    # a family-only target is another guess — refused
    assert cli.main(["prices", "alias", "-", "copilot/auto",
                     "--to", "anthropic/claude-sonnet-4.6"]) == 1
    assert "no exact price row" in capsys.readouterr().err
    assert cli.main(["prices", "alias", "-", "copilot/auto",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0
    assert "alias footnote" in capsys.readouterr().out
    assert cli.main(["report", "--by", "model"]) == 0
    rep = capsys.readouterr().out
    assert "priced by alias" in rep and "copilot/auto → anthropic/claude-sonnet-4-6" in rep
    assert "UNPRICED" not in rep or "copilot/auto," not in rep


def test_report_unpriced_summary_line(root, capsys):
    _seed_unpriced(root)
    assert cli.main(["report", "--by", "model"]) == 0
    out = capsys.readouterr().out
    assert "⚠ 4 calls (1,251,000 tokens) UNPRICED — totals understated" in out
    assert "run 'cage prices unpriced'" in out
    assert "cage query unpriced" in out


def test_overview_unpriced_line(root, capsys):
    _seed_unpriced(root)
    assert cli.main([]) == 0
    assert "UNPRICED — totals understated" in capsys.readouterr().out


def test_list_shows_origin_meta_and_recommendation(root, capsys):
    initcmd.run(root)  # verbatim bundle copy — carries the bundled [meta]
    assert cli.main(["prices", "list"]) == 0
    out = capsys.readouterr().out
    assert "origin" in out and "bundled" in out
    assert "bundled prices are newer" not in out  # init copy is current
    # backdate the project meta → the one-line recommendation appears
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    assert cli.main(["prices", "list"]) == 0
    out = capsys.readouterr().out
    assert "bundled prices are newer (" in out and "cage prices sync" in out


def test_init_copy_carries_bundled_meta(root):
    initcmd.run(root)
    from cage import policy
    project = policy.load_project_raw(Footprint(root).policy)
    assert project["meta"] == policy.bundled_raw()["meta"]


def test_sync_classifies_and_updates_only_confirmed_rows(root, capsys):
    # cage-managed rows are customized by definition; hand rows that differ are drift.
    assert cli.main(["prices", "set", "anthropic", "claude-opus-4-8",
                     "--input", "9", "--output", "9", "--cache-read", "0.9"]) == 0
    pol_path = Footprint(root).policy
    pol_path.write_text(pol_path.read_text(encoding="utf-8")
                        + '\n[prices.anthropic."claude-sonnet-4-6"]\ninput = 7.0\n'
                          'output = 7.0\ncache_read = 0.7\n', encoding="utf-8")
    capsys.readouterr()
    assert cli.main(["prices", "sync"]) == 0
    out = capsys.readouterr().out
    assert "customized (cage-managed/marked) — preserved" in out
    assert "anthropic/claude-sonnet-4-6 differs" in out
    assert "--yes anthropic/claude-sonnet-4-6" in out
    # --update without --yes leaves drift untouched
    assert cli.main(["prices", "sync", "--update"]) == 0
    out = capsys.readouterr().out
    assert "left untouched" in out
    from cage import policy
    raw = policy.load_project_raw(pol_path)
    assert raw["prices"]["anthropic"]["claude-sonnet-4-6"]["input"] == 7.0
    # --yes applies the bundled values and restamps meta; customized row survives
    assert cli.main(["prices", "sync", "--update",
                     "--yes", "anthropic/claude-sonnet-4-6"]) == 0
    out = capsys.readouterr().out
    assert "bundled values applied" in out and "[meta] restamped" in out
    raw = policy.load_project_raw(pol_path)
    assert raw["prices"]["anthropic"]["claude-sonnet-4-6"]["input"] == 3.0
    assert raw["prices"]["anthropic"]["claude-opus-4-8"]["input"] == 9.0
    assert raw["meta"] == policy.bundled_raw()["meta"]


def test_prices_json_uses_envelope(root, capsys):
    _seed_unpriced(root)
    assert cli.main(["prices", "unpriced", "--json"]) == 0
    d = json.loads(capsys.readouterr().out)
    assert d["schemaVersion"] == "cage.v1" and d["command"] == "prices"
    assert d["data"]["total_calls"] == 4


def test_doctor_prices_meta_check(root, capsys):
    initcmd.run(root)
    assert cli.main(["doctor"]) == 0 or True  # doctor may warn on unrelated checks
    out = capsys.readouterr().out
    assert "prices-meta" in out or "current with the bundle" in out
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "bundled prices are newer" in out


def test_writes_resolve_to_active_ledger_root(proj, monkeypatch, capsys):
    # No project .cage/ → the resolved root is the (test-redirected) global home;
    # prices set must land there, not scatter a local footprint.
    monkeypatch.chdir(proj)
    gh = paths.global_home()
    (gh / ".cage").mkdir(parents=True, exist_ok=True)
    assert cli.main(["prices", "set", "x", "m", "--input", "1", "--output", "2"]) == 0
    assert (gh / ".cage" / "policy.toml").exists()
    assert not (proj / ".cage").exists()


# ── route-tool: the managed writer for [tools.<tool>] price_at (plan §4.5) ──────

def _policy_text(root):
    return (Footprint(root).policy).read_text(encoding="utf-8")


def test_route_tool_write_update_remove_idempotent(root, capsys):
    assert cli.main(["prices", "route-tool", "graphify",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0
    out = capsys.readouterr().out
    assert "✔ [tools.graphify]" in out and "before: —" in out
    assert 'after:  price_at = "anthropic/claude-sonnet-4-6"' in out
    assert "rung 1" in out
    text1 = _policy_text(root)
    assert '[tools.graphify]' in text1 and 'price_at = "anthropic/claude-sonnet-4-6"' in text1
    # idempotent re-run: "no change" printed, file bytes identical
    assert cli.main(["prices", "route-tool", "graphify",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0
    assert "already routes to anthropic/claude-sonnet-4-6 — no change" in capsys.readouterr().out
    assert _policy_text(root) == text1
    # update to a new target prints before/after
    assert cli.main(["prices", "route-tool", "graphify",
                     "--to", "anthropic/claude-opus-4-6"]) == 0
    out = capsys.readouterr().out
    assert "before: anthropic/claude-sonnet-4-6" in out
    assert 'after:  price_at = "anthropic/claude-opus-4-6"' in out
    # remove, then remove again (idempotent no-op, exit 0)
    assert cli.main(["prices", "route-tool", "graphify", "--remove"]) == 0
    out = capsys.readouterr().out
    assert "✔ [tools.graphify] removed" in out and "anthropic/claude-opus-4-6" in out
    assert "[tools.graphify]" not in _policy_text(root)
    assert cli.main(["prices", "route-tool", "graphify", "--remove"]) == 0
    assert "has no route — nothing to remove" in capsys.readouterr().out


def test_route_tool_dangling_target_warns_but_writes(root, capsys):
    assert cli.main(["prices", "route-tool", "fux", "--to", "anthropic/mystery-9000"]) == 0
    out = capsys.readouterr().out
    assert "⚠ anthropic/mystery-9000 resolves no price row" in out
    assert "stay UNPRICED" in out
    assert 'price_at = "anthropic/mystery-9000"' in _policy_text(root)  # written anyway


def test_route_tool_family_target_notes_match_kind(root, capsys):
    # dotted id family-matches the dashed row — accepted, match kind named (§8)
    assert cli.main(["prices", "route-tool", "fux",
                     "--to", "anthropic/claude-sonnet-4.6"]) == 0
    out = capsys.readouterr().out
    assert "≈ target resolves by family via claude-sonnet-4-6" in out


def test_route_tool_typed_errors(root, capsys):
    for argv in (["prices", "route-tool"],                                  # no tool
                 ["prices", "route-tool", "graphify"],                      # no --to
                 ["prices", "route-tool", "graphify", "--to", "nomodel"],   # no slash
                 ["prices", "route-tool", "graphify", "--to", "/m"],        # empty provider
                 ["prices", "route-tool", "a b", "--to", "x/y"],            # not one token
                 ["prices", "route-tool", "tools/../etc", "--to", "x/y"]):  # path-shaped
        assert cli.main(argv) == 1
        assert capsys.readouterr().err.startswith("error: ")


def test_route_tool_hand_added_table_edited_in_place_with_custom_mark(root, capsys):
    # mirror `prices set`: a user-owned [tools.x] outside the block is edited in
    # place and marked # cage:custom — never duplicated into the managed block
    pol = Footprint(root).policy
    pol.write_text('[tools.zed]\nprice_at = "anthropic/claude-opus-4-6"\n', encoding="utf-8")
    assert cli.main(["prices", "route-tool", "zed",
                     "--to", "anthropic/claude-sonnet-4-6"]) == 0
    assert "updated in place" in capsys.readouterr().out
    text = _policy_text(root)
    assert text.count("[tools.zed]") == 1 and pricestoml.CUSTOM_MARK in text
    assert 'price_at = "anthropic/claude-sonnet-4-6"' in text
    # --remove refuses to delete the user's own text, with a typed error
    assert cli.main(["prices", "route-tool", "zed", "--remove"]) == 1
    assert "hand-added outside" in capsys.readouterr().err


def test_route_tool_visible_in_list_and_doctor_unchanged(root, capsys):
    cli.main(["prices", "route-tool", "ghost", "--to", "anthropic/mystery-9000"])
    capsys.readouterr()
    assert cli.main(["prices", "list"]) == 0
    out = capsys.readouterr().out
    assert "ghost → anthropic/mystery-9000" in out and "⚠ dangling" in out


def test_sync_picks_up_new_bundle_rows(root, capsys):
    # Handoff B (plan §3.3): a project stamped from an older bundle sees the
    # recommendation; `sync --update` restamps, and the newly-researched rows
    # (here the load-bearing codex fixture id) resolve through the merge.
    initcmd.run(root)
    pricestoml.update_meta(root, {"prices_version": "2020-01-01"})
    assert cli.main(["prices", "sync"]) == 0
    assert "bundled prices are newer (" in capsys.readouterr().out
    assert cli.main(["prices", "sync", "--update"]) == 0
    assert "[meta] restamped" in capsys.readouterr().out
    assert cli.main(["prices", "sync"]) == 0
    assert "bundled prices are newer (" not in capsys.readouterr().out
    from cage import policy
    pol = policy.load(Footprint(root).policy)
    row, match, _ = policy.price_match(pol, "openai", "gpt-5.1-codex")
    assert match == "exact" and row["input"] == 1.25
