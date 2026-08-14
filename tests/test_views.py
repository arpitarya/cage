"""Read views: provenance and the CLI dispatch.

The `budget` and `roi` halves went with the money subsystem (USAGE-ONLY, ADR 0011).
The `report` half went with SURFACE-CUT — `report.summarize`/`render_report` and the
`--by` dimension no longer exist, so the three rollup cases here died with them. What
they pinned (group/total arithmetic over the ledger) is now pinned by `insights chats`
in `tests/test_chats.py` and by the goldens.
"""
from __future__ import annotations

from cage import cli, metering as meter, policy, provenance


def test_provenance_links_call_to_receipts(seeded):
    root, call_id = seeded
    data = provenance.explain(root, call_id)
    assert data["call"]["id"] == call_id
    assert {r["tool"] for r in data["receipts"]} == {"graphify", "fux", "compressor"}


def test_cli_demo_then_views_exit_zero(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    meter._policy_for.cache_clear()
    assert cli.main(["demo"]) == 0
    assert cli.main(["insights", "graphify"]) == 0
    assert cli.main(["insights", "chats"]) == 0
    assert cli.main(["insights", "chats", "--json"]) == 0
    out = capsys.readouterr().out
    assert "graphify" in out


def test_cli_why_unknown_call(proj, monkeypatch, capsys):
    monkeypatch.chdir(proj)
    assert cli.main(["insights", "why", "c_nope"]) == 0
    assert "no call" in capsys.readouterr().out
