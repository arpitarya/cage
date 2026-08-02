"""`cage data export --otel` (docs/otel-export.handoff.md) — GenAI-conformant JSON,
one-way REPORTING like --csv. Determinism, the pre-stable semconv stamp, honest
omission (never a fabricated zero/dollar), and cage-namespaced savings."""
from __future__ import annotations

import json

import pytest

from cage import cli, constants, ledger, otelout, policy, schema


@pytest.fixture
def root(proj, monkeypatch):
    (proj / ".cage").mkdir()
    monkeypatch.chdir(proj)
    return proj


def _seed(root, *, latency_ms=0):
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=100, tokens_out=50, latency_ms=latency_ms, task="t1",
        ts="2026-07-01T00:00:00Z", call_id="c_1"))


def test_otel_document_maps_call_to_genai_attributes(root):
    _seed(root, latency_ms=1200)
    assert cli.main(["data", "export", "--otel", "--no-import"]) == 0


def test_otel_call_fields_and_duration(root, capsys):
    _seed(root, latency_ms=1200)
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    span = doc["calls"][0]
    assert span["gen_ai.system"] == "anthropic"
    assert span["gen_ai.request.model"] == "claude-opus-4-8"
    assert span["gen_ai.usage.input_tokens"] == 100
    assert span["gen_ai.usage.output_tokens"] == 50
    assert span["gen_ai.client.operation.duration"] == 1.2


def test_zero_latency_omits_duration_never_fabricates_zero(root, capsys):
    _seed(root, latency_ms=0)
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    assert "gen_ai.client.operation.duration" not in doc["calls"][0]


def test_semconv_version_pinned_and_stamped(root, capsys):
    _seed(root)
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["cage.meta"]["semconv"] == constants.OTEL_SEMCONV_VERSION
    assert doc["cage.meta"]["semconv_status"] == "pre-stable"


def test_receipt_carries_cage_namespaced_savings_never_gen_ai(root, capsys):
    _seed(root)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=500, actual=100, call="c_1", task="t1",
        unit="tokens", method="modeled", confidence=0.6))
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    row = doc["cage.savings"][0]
    assert row["cage.tool"] == "graphify"
    assert row["cage.saved"] == 400.0
    assert row["cage.method"] == "modeled"
    assert row["cage.confidence"] == 0.6
    assert row["cage.saved_usd"] > 0
    # No invented gen_ai.* key anywhere in a savings row.
    assert not any(k.startswith("gen_ai.") for k in row)


def test_unpriced_receipt_omits_saved_usd_never_zero(root, monkeypatch, capsys):
    # A call-less token receipt with no call, no task-model history, no price_at
    # route resolves nowhere on the ladder — UNPRICED, must be omitted, not $0.
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="fux", raw_alternative=200, actual=50, unit="tokens",
        method="modeled", confidence=0.6))
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    row = doc["cage.savings"][0]
    assert "cage.saved_usd" not in row
    assert row["cage.saved"] == 150.0


def test_ms_unit_receipt_omits_saved_usd_not_money(root):
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="compress", raw_alternative=500, actual=100, call="c_1", task="t1",
        unit="ms", method="modeled", confidence=0.6))
    row = otelout._savings_row(
        ledger.receipts(root)[0], {"c_1": {"provider": "anthropic",
                                           "model": "claude-opus-4-8"}}, {}, {})
    assert "cage.saved_usd" not in row
    assert row["cage.unit"] == "ms"


def test_legacy_human_rows_excluded_and_counted(root, capsys):
    _seed(root)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="human", raw_alternative=100, actual=0, unit="tokens",
        method="measured", confidence=1.0))
    cli.main(["data", "export", "--otel", "--no-import"])
    doc = json.loads(capsys.readouterr().out)
    assert doc["cage.savings"] == []
    assert doc["cage.meta"]["legacy_human_excluded"] == 1


def test_deterministic_byte_identical(root):
    _seed(root)
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=500, actual=100, call="c_1", task="t1",
        unit="tokens", method="modeled", confidence=0.6))
    from cage.paths import Footprint
    pol = policy.load(Footprint(root).policy)
    calls = ledger.calls(root)
    rcpts = ledger.receipts(root)
    a = otelout.render(calls, rcpts, calls, pol)
    b = otelout.render(calls, rcpts, calls, pol)
    assert a == b
    assert a.endswith("\n") and "\r" not in a


def test_otel_writes_to_file(root, tmp_path, capsys):
    _seed(root)
    out = root / "export.otel.json"
    assert cli.main(["data", "export", "--otel", "--no-import", "-o", str(out)]) == 0
    doc = json.loads(out.read_text())
    assert doc["calls"][0]["gen_ai.system"] == "anthropic"
    assert "otel" in capsys.readouterr().err


def test_otel_rejects_combination_with_csv_and_format(root, capsys):
    _seed(root)
    assert cli.main(["data", "export", "--otel", "--csv", "calls", "--no-import"]) == 1
    assert "--otel" in capsys.readouterr().err
    assert cli.main(["data", "export", "--otel", "--format", "json", "--no-import"]) == 1
    assert "--otel" in capsys.readouterr().err


def test_otel_rejects_combination_with_study(root, capsys):
    _seed(root)
    assert cli.main(["data", "export", "--otel", "--study", "--no-import"]) == 1
    assert "--otel" in capsys.readouterr().err


def test_agent_project_filters_apply_to_calls_only(root, capsys):
    _seed(root)
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="openai", model="gpt-5", tokens_in=10,
        agent="copilot", ts="2026-07-02T00:00:00Z", call_id="c_2"))
    ledger.append_row(root, "receipts", schema.make_receipt(
        tool="graphify", raw_alternative=500, actual=100, call="c_1", task="t1",
        unit="tokens", method="modeled", confidence=0.6))
    cli.main(["data", "export", "--otel", "--no-import", "--agent", "copilot"])
    doc = json.loads(capsys.readouterr().out)
    assert [c["gen_ai.system"] for c in doc["calls"]] == ["openai"]
    # the receipt (linked to the excluded claude call) still exports — receipts
    # have no agent field to filter on, and pricing needs the full call set.
    assert len(doc["cage.savings"]) == 1


# ── "omitted, never zero" must survive an UNPRICED model (REV-HARDEN P2) ──────

def test_an_unpriced_linked_receipt_omits_saved_usd_rather_than_exporting_zero(tmp_path):
    """`policy.price` returns a zero row for a model it cannot price, so
    `prices.input_cost_usd` yields a hard `0.0` that is indistinguishable from a real
    zero. Exported, that is a fabricated dollar figure — the one thing this document
    format promises never to emit.

    The review filed this against `otelout`, which is wrong: its omit-on-None logic is
    already correct. The `0.0` is produced one level down in `convert`, which is where
    the fix belongs — putting it in `otelout` would mean a second copy of the pricing
    ladder there, and the credits rung already drifted between two copies once."""
    from cage import convert, otelout, policy, schema
    pol = policy.load(None)
    call = schema.make_call(route="chat", provider="nobody", model="no-such-model",
                            tokens_in=100, tokens_out=10, call_id="c_u")
    rec = schema.make_receipt(tool="graphify", raw_alternative=5000, actual=1000,
                              call="c_u")
    assert convert.saved_usd(rec, call, pol) == 0.0          # the legacy shape stands
    assert convert.saved_usd_opt(rec, call, pol) is None      # ...but it is UNPRICED

    doc = json.loads(otelout.render([call], [rec], [call], pol))
    row = doc["cage.savings"][0]
    assert "cage.saved_usd" not in row, row
    assert row["cage.saved"] == 4000.0 and row["cage.method"]   # counts still exported


def test_a_genuinely_zero_saving_still_exports_its_zero(tmp_path):
    """The distinction the Optional exists for: absent because unpriceable is not the
    same fact as priced and worth nothing."""
    from cage import convert, policy, schema
    pol = policy.load(None)
    call = schema.make_call(route="chat", provider="anthropic",
                            model="claude-opus-4-8", tokens_in=100, tokens_out=10,
                            call_id="c_z")
    rec = schema.make_receipt(tool="graphify", raw_alternative=1000, actual=1000,
                              call="c_z")
    assert convert.saved_usd_opt(rec, call, pol) == 0.0
