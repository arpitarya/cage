"""`cage limits` — Codex quota snapshot (latest-only state file) + estimated AI-credits.

Quota is a machine-local snapshot, NOT a ledger substrate (plan §3.8). Credits are
estimated from tokens × a policy multiplier, token-based providers only — a model with
no multiplier (Kiro) shows no fabricated number. A renamed/missing `rate_limits` block
yields no snapshot and no error.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import clicmds, credits, importcmd, ledger, limits, paths, render, schema, transcript


# real-shaped Codex `token_count` event: rate_limits is a SIBLING of payload.info
def _codex_rl_line(ts, used_pct, window, resets=1780428020):
    return json.dumps({"timestamp": ts, "type": "event_msg", "payload": {
        "type": "token_count",
        "info": {"last_token_usage": {"input_tokens": 100, "output_tokens": 20}},
        "rate_limits": {"limit_id": "codex", "limit_name": None,
                        "primary": {"used_percent": used_pct, "window_minutes": window,
                                    "resets_at": resets},
                        "secondary": None, "credits": None, "plan_type": "go",
                        "rate_limit_reached_type": None}}})


# ── transcript._codex_rate_limits (parse) ───────────────────────────────────

def test_codex_rate_limits_parses_real_shape():
    rec = json.loads(_codex_rl_line("2026-05-26T19:20:28.595Z", 3.0, 10080))
    snaps = transcript._codex_rate_limits(rec)
    assert snaps == [{"window_minutes": 10080, "used_percent": 3.0,
                      "resets_at": 1780428020, "observed_ts": "2026-05-26T19:20:28.595Z"}]


def test_codex_rate_limits_malformed_yields_nothing():
    # missing block, renamed block, non-numeric fields ⇒ [] (no wrong number)
    assert transcript._codex_rate_limits({"payload": {"info": {}}}) == []
    assert transcript._codex_rate_limits({"payload": {"rate_limits": "nope"}}) == []
    assert transcript._codex_rate_limits({}) == []
    bad = {"payload": {"rate_limits": {"primary": {"used_percent": "high", "window_minutes": 10080}}}}
    assert transcript._codex_rate_limits(bad) == []


# ── snapshot_codex (latest-only state file) ─────────────────────────────────

def test_snapshot_codex_keeps_latest_per_window(tmp_path):
    (tmp_path / ".cage").mkdir()
    f = tmp_path / "rollout-x.jsonl"
    # two snapshots for the SAME window — the newer observed_ts must win (overwrite)
    f.write_text(_codex_rl_line("2026-05-26T10:00:00Z", 3.0, 10080) + "\n"
                 + _codex_rl_line("2026-05-26T20:00:00Z", 12.0, 10080) + "\n"
                 + _codex_rl_line("2026-05-26T20:00:00Z", 39.0, 43200) + "\n", encoding="utf-8")
    assert limits.snapshot_codex(tmp_path, [f]) == 2          # two distinct windows
    state = json.loads(paths.Footprint(tmp_path).limits.read_text())
    assert state["codex"]["10080"]["used_percent"] == 12.0    # latest, not 3.0
    assert state["codex"]["43200"]["used_percent"] == 39.0


def test_snapshot_codex_missing_block_is_noop(tmp_path):
    (tmp_path / ".cage").mkdir()
    f = tmp_path / "rollout-y.jsonl"
    f.write_text(json.dumps({"timestamp": "t", "payload": {"type": "token_count",
                 "info": {"last_token_usage": {"input_tokens": 5}}}}) + "\n", encoding="utf-8")
    assert limits.snapshot_codex(tmp_path, [f]) == 0
    assert not paths.Footprint(tmp_path).limits.exists()      # nothing written, no error


# ── credits dispatch (token-based only) ─────────────────────────────────────

def test_credits_unknown_multiplier_is_none():
    assert credits.tokens_to_credits({}, "kiro", "agent", 1_000_000) is None
    assert credits.tokens_to_credits({"credits": {}}, "anthropic", "claude-opus-4-8", 5) is None


def test_credits_configured_multiplier_estimates():
    pol = {"credits": {"anthropic": {"claude-opus-4-8": {"per_mtok": 30}}}}
    assert credits.tokens_to_credits(pol, "anthropic", "claude-opus-4-8", 2_000_000) == 60.0
    # exact-match only — a dated/family id is deliberately not borrowed
    assert credits.tokens_to_credits(pol, "anthropic", "claude-opus-4-8-20260101", 1) is None


# ── the view (human + cage.v1 JSON) ─────────────────────────────────────────

def _seed_ledger(root):
    (root / ".cage").mkdir(exist_ok=True)
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="anthropic", model="claude-opus-4-8",
        tokens_in=600_000, tokens_out=400_000, agent="claude-code", call_id="c_a"))
    ledger.append_row(root, "calls", schema.make_call(
        route="chat", provider="kiro", model="agent",
        tokens_in=1000, tokens_out=0, agent="kiro", call_id="c_k"))


def test_rollup_credits_token_based_only(tmp_path):
    _seed_ledger(tmp_path)
    pol = {"credits": {"anthropic": {"claude-opus-4-8": {"per_mtok": 30}}}}
    data = limits.rollup(tmp_path, pol)
    by_agent = {r["agent"]: r for r in data["credits"]}
    assert by_agent["claude-code"]["credits"] == 30.0        # 1M tokens × 30/Mtok
    assert by_agent["claude-code"]["method"] == "estimated"
    assert by_agent["kiro"]["credits"] is None               # no fabricated Kiro number
    assert by_agent["kiro"]["method"] is None


def test_render_limits_human_labels_and_reconcile(tmp_path):
    (tmp_path / ".cage").mkdir()
    # seed a quota snapshot + a ledger credit row
    paths.Footprint(tmp_path).state.mkdir(parents=True, exist_ok=True)
    paths.Footprint(tmp_path).limits.write_text(json.dumps({"codex": {
        "10080": {"used_percent": 3.0, "resets_at": 1780428020,
                  "observed_ts": "2026-05-26T19:20:28Z"}}}), encoding="utf-8")
    _seed_ledger(tmp_path)
    text = limits.render_limits(limits.rollup(tmp_path, {}))
    assert "weekly" in text and "97%" in text                # 100 - 3.0
    assert "estimated" in text and "reconcile against your provider dashboard" in text
    assert "—" in text                                       # kiro credit not fabricated


def test_cage_limits_json_is_cage_v1_envelope(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    _seed_ledger(tmp_path)
    monkeypatch.chdir(tmp_path)
    import io
    import contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        clicmds.cmd_limits(SimpleNamespace(json=True))
    payload = json.loads(buf.getvalue())
    assert payload["schemaVersion"] == "cage.v1"
    assert payload["command"] == "limits"
    assert "data" in payload and "quota" in payload["data"] and "credits" in payload["data"]


def test_import_codex_writes_quota_snapshot(tmp_path, monkeypatch):
    (tmp_path / ".cage").mkdir()
    for env in ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_DATA_DIR"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    monkeypatch.chdir(tmp_path)
    roll = tmp_path / "home-codex_home" / "sessions" / "rollout-z.jsonl"
    roll.parent.mkdir(parents=True)
    roll.write_text(_codex_rl_line("2026-05-26T19:20:28Z", 39.0, 43200) + "\n", encoding="utf-8")
    importcmd.import_codex(tmp_path, SimpleNamespace(path=None, since=None))
    state = json.loads(paths.Footprint(tmp_path).limits.read_text())
    assert state["codex"]["43200"]["used_percent"] == 39.0
