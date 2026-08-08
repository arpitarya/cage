"""Configurable import paths — the `[sources]` policy table (plan Phase 4).

The two must-never-skip tests are first: **empty-`[sources]` byte-identity** (capture
is byte-for-byte unchanged for everyone who doesn't use it) and the **full precedence
matrix** (env home override > policy > built-in, replace/disabled, dedup). Then
expansion, custom-tool end-to-end (a fixture log at a policy path → rows stamped with
the tool name, reports split by it), cursor incrementality on a policy path, the
portability warn/no-warn guard, and `policy sync` ownership.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from cage import (agents, importcmd, ledger, paths, pathprobe, policy, policysync,
                  report)


def _imp_args(agent="all", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _claude_line(uuid, tin, tout, cwd="/Users/me/my_programs/widget"):
    return json.dumps({"type": "assistant", "uuid": uuid, "cwd": cwd,
                       "timestamp": "2026-06-14T10:00:00Z",
                       "message": {"model": "claude-opus-4-8",
                                   "usage": {"input_tokens": tin, "output_tokens": tout}}})


_HOME_ENVS = ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")


def _isolate_homes(d, monkeypatch):
    """Point every agent home at a throwaway dir so a pathless sweep never reads the
    developer's real logs — hermetic + deterministic (import tests). Note: this sets
    the home env overrides, so built-in candidates resolve with `env` provenance."""
    for env in _HOME_ENVS:
        monkeypatch.setenv(env, str(d / f"home-{env.lower()}"))


def _no_env(monkeypatch):
    """Clear every home env override so built-in candidates carry `built-in`
    provenance — the baseline for the provenance/precedence assertions. The resolver
    never touches disk, so leaving homes at their real defaults is safe here."""
    for env in _HOME_ENVS:
        monkeypatch.delenv(env, raising=False)


def _write_policy(root, body: str):
    base = root / ".cage"
    base.mkdir(parents=True, exist_ok=True)
    (base / "policy.toml").write_text(body, encoding="utf-8")


# ── MUST-NEVER-SKIP 1: [sources] is the ONLY authority (Directive A, §3.6) ──

def test_empty_sources_captures_nothing(monkeypatch):
    # Directive A: the built-in registry is a SEED, not a runtime fallback. With no
    # [sources] table, resolution yields NOTHING (and the import sweep says so loudly).
    _no_env(monkeypatch)
    for pol in ({}, {"sources": {}}):  # no key, and an empty [sources] table
        res = paths.resolve_log_sources(pol)
        assert res.problems == [] and res.sources == []
    assert paths.agent_log_sources("copilot") == []  # nothing resolves without [sources]


def test_no_sources_captures_nothing_loudly(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # Plant a claude log in the isolated home — with no [sources] it is NOT captured.
    cl = tmp_path / "home-claude_config_dir" / "projects" / "p"
    cl.mkdir(parents=True)
    (cl / "session-x.jsonl").write_text(_claude_line("u1", 100, 50) + "\n", encoding="utf-8")

    def _capture(body):
        root = tmp_path / body[:4]
        _write_policy(root, body)
        monkeypatch.chdir(root)
        lines = importcmd.run(root, "all", _imp_args())
        return ledger.calls(root), lines

    no_key_rows, no_key_lines = _capture("# no sources table\n")
    empty_rows, _ = _capture("[sources]\n")
    assert no_key_rows == [] and empty_rows == []               # nothing captured
    assert any("no [sources]" in ln for ln in no_key_lines)     # …and it is loud


# ── MUST-NEVER-SKIP 2: [sources] is the sole authority; env is not consulted ──

def test_sources_are_the_only_authority_env_ignored(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    # An env home override is NO LONGER consulted for path resolution (Directive A):
    # copilot has no [sources.copilot], so it resolves nothing despite COPILOT_HOME being set.
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "copilot-redirected"))
    add = tmp_path / "extra-claude"
    pol = {"sources": {"claude": {"paths": [str(add)]}}}
    res = paths.resolve_log_sources(pol)

    claude = [s for s in res.sources if s.agent == "claude"]
    assert [s.path for s in claude] == [add]  # only the declared path — no built-in prepended
    assert all(s.provenance == "policy" for s in claude) and claude[0].fmt == "claude"
    assert [s for s in res.sources if s.agent == "copilot"] == []  # env ignored, undeclared


def test_undeclared_agent_has_no_sources(monkeypatch, tmp_path):
    # `replace`/`disabled` are gone: an agent is captured iff it has a [sources.<agent>]
    # entry. Declaring copilot leaves kiro (undeclared) with nothing — the new "disable".
    _isolate_homes(tmp_path, monkeypatch)
    only = tmp_path / "only-copilot"
    pol = {"sources": {"copilot": {"paths": [str(only)]}}}
    res = paths.resolve_log_sources(pol)
    copilot = [s for s in res.sources if s.agent == "copilot"]
    assert [s.path for s in copilot] == [only] and copilot[0].provenance == "policy"
    assert [s for s in res.sources if s.agent == "kiro"] == []  # undeclared ⇒ silent


def test_duplicate_policy_paths_dedupe(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    d = tmp_path / "logs"
    pol = {"sources": {"claude": {"paths": [str(d), str(d)]}}}  # same path twice
    claude = [s for s in paths.resolve_log_sources(pol).sources if s.agent == "claude"]
    assert len(claude) == 1 and claude[0].provenance == "policy"  # deduped by (path, glob)


# ── expansion, validation ─────────────────────────────────────────────────────

def test_tilde_and_env_var_expand(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    monkeypatch.setenv("MYLOGS", str(tmp_path / "shared"))
    pol = {"sources": {"claude": {"paths": ["~/alt", "$MYLOGS/claude"]}}}
    added = [s for s in paths.resolve_log_sources(pol).sources
             if s.agent == "claude" and s.provenance == "policy"]
    assert added[0].path == paths.Path.home() / "alt"
    assert added[1].path == tmp_path / "shared" / "claude"
    assert added[0].raw == "~/alt"  # raw kept for the portability check


def test_glob_entry_rejected_as_problem(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    pol = {"sources": {"claude": {"paths": ["/logs/*.jsonl"]}}}
    res = paths.resolve_log_sources(pol)
    assert not [s for s in res.sources if s.provenance == "policy"]
    assert any("glob" in p for p in res.problems)


def test_custom_tool_needs_format_and_reserved_names(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # missing format → rejected, contributes nothing
    res = paths.resolve_log_sources({"sources": {"mytool": {"paths": ["/x"]}}})
    assert any("format" in p for p in res.problems)
    assert not paths.custom_tool_sources({"sources": {"mytool": {"paths": ["/x"]}}})
    # a bad format value is also rejected — the tool contributes no sources
    bad = paths.resolve_log_sources({"sources": {"t": {"paths": ["/x"], "format": "grok"}}})
    assert bad.problems and not [s for s in bad.sources if s.agent == "t"]


# ── custom-tool import end-to-end ─────────────────────────────────────────────

def test_custom_tool_imports_and_stamps_agent_name(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "router-logs"
    logs.mkdir()
    (logs / "session-r1.jsonl").write_text(_claude_line("cu1", 200, 40) + "\n",
                                           encoding="utf-8")
    root = tmp_path / "proj"
    # as_posix() keeps the path a valid TOML basic string on Windows (a raw `\` is a
    # TOML escape); Path() accepts forward slashes on every OS.
    _write_policy(root, f'[sources.myrouter]\npaths = ["{logs.as_posix()}"]\nformat = "claude"\n')
    monkeypatch.chdir(root)

    lines = importcmd.run(root, "all", _imp_args())
    rows = ledger.calls(root)
    assert rows and all(r["agent"] == "myrouter" for r in rows)  # stamped with the tool name
    assert any("myrouter (custom, format=claude)" in ln for ln in lines)

    # reports split by the tool name.
    rep = report.summarize(root, policy.load(paths.Footprint(root).policy), dim="agent")
    assert "myrouter" in rep["groups"]


def test_custom_tool_cursor_incremental(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "rl"
    logs.mkdir()
    (logs / "s.jsonl").write_text(_claude_line("c1", 10, 5) + "\n", encoding="utf-8")
    root = tmp_path / "proj"
    _write_policy(root, f'[sources.myrouter]\npaths = ["{logs.as_posix()}"]\nformat = "claude"\n')
    monkeypatch.chdir(root)

    importcmd.run(root, "all", _imp_args())
    assert len(ledger.calls(root)) == 1
    cur = json.loads(paths.Footprint(root).cursors.read_text())
    assert "myrouter" in cur and str(logs / "s.jsonl") in cur["myrouter"]  # own cursor bucket
    importcmd.run(root, "all", _imp_args())  # unchanged file → skip
    assert len(ledger.calls(root)) == 1


# ── portability guard ─────────────────────────────────────────────────────────

def _probe(root, pol, monkeypatch, *, committed):
    monkeypatch.setattr(pathprobe, "_git_tracked", lambda *a, **k: committed)
    return pathprobe.probe(root, pol)


def test_portability_warns_only_on_committed_machine_absolute_project_path(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    abs_pol = {"sources": {"claude": {"paths": ["/Users/dev/logs"]}}}
    tilde_pol = {"sources": {"claude": {"paths": ["~/logs"]}}}

    warns = _probe(root, abs_pol, monkeypatch, committed=True)["portability"]
    assert warns and "machine-absolute" in warns[0]
    assert not _probe(root, tilde_pol, monkeypatch, committed=True)["portability"]  # ~ exempt
    assert not _probe(root, abs_pol, monkeypatch, committed=False)["portability"]   # uncommitted exempt


def test_portability_never_warns_for_global_policy(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    # No project .cage/ → active sink is global (~/.cage), which is per-machine by nature.
    fresh = tmp_path / "no-project"
    fresh.mkdir()
    monkeypatch.chdir(fresh)
    abs_pol = {"sources": {"claude": {"paths": ["/Users/dev/logs"]}}}
    assert not _probe(fresh, abs_pol, monkeypatch, committed=True)["portability"]


def test_doctor_paths_shows_policy_authority_and_undeclared(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    # Directive A: only [sources] declares paths. claude declared; kiro/copilot undeclared.
    pol = {"sources": {"claude": {"paths": ["~/alt"]}}}
    out = pathprobe.run(root, pol)
    assert "[policy]" in out                       # the declared source's provenance tag
    assert "not declared in [sources]" in out      # kiro/copilot swept nothing — loud
    assert "SOLE path authority" in out            # the legend line reflects the new model


# ── policy sync ownership ─────────────────────────────────────────────────────

def test_bundle_ships_no_sources_table():
    assert "sources" not in policy.bundled_raw()  # asserted invariant


def test_policy_sync_never_touches_sources(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    _write_policy(root, '[meta]\npolicy_version = "0.25"\n\n'
                        '[sources.claude]\npaths = ["~/alt"]\n')
    monkeypatch.chdir(root)
    d = policysync.sync_view(root)
    flat = json.dumps(d)
    assert "sources" not in flat  # never in add/update/customized/orphan/project_own


# ── per-source glob (v0.29) — the dict `glob` key and the array-of-tables form ──

def test_dict_glob_key_overrides_the_format_default(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    add = tmp_path / "logs"
    pol = {"sources": {"claude": {"paths": [str(add)], "glob": "usage-*.ndjson"}}}
    added = [s for s in paths.resolve_log_sources(pol).sources
             if s.agent == "claude" and s.provenance == "policy"]
    assert len(added) == 1 and added[0].glob == "usage-*.ndjson"  # declared, not **/*.jsonl
    assert added[0].fmt == "claude"  # still parsed as claude


def test_absent_glob_falls_back_to_format_default(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    pol = {"sources": {"copilot": {"paths": [str(tmp_path / "c")]}}}
    added = [s for s in paths.resolve_log_sources(pol).sources
             if s.agent == "copilot" and s.provenance == "policy"]
    assert added[0].glob == paths._FORMAT_GLOB["copilot"]  # the imposed default


def test_empty_glob_is_a_problem_not_a_silent_fallback(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    pol = {"sources": {"claude": {"paths": [str(tmp_path / "x")], "glob": ""}}}
    res = paths.resolve_log_sources(pol)
    assert not [s for s in res.sources if s.provenance == "policy"]  # skipped, not defaulted
    assert any("glob" in p and "non-empty" in p for p in res.problems)


def test_glob_in_path_message_names_the_fix(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    res = paths.resolve_log_sources({"sources": {"claude": {"paths": ["/logs/*.jsonl"]}}})
    assert res.problems and any("glob = " in p for p in res.problems)  # points at glob =


def test_array_of_tables_form_with_per_entry_glob(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    a, b = tmp_path / "a", tmp_path / "b"
    pol = {"sources": {"claude": [
        {"path": str(a)},                                  # glob defaults
        {"path": str(b), "glob": "sess-*.jsonl"},          # own glob
    ]}}
    added = [s for s in paths.resolve_log_sources(pol).sources
             if s.agent == "claude" and s.provenance == "policy"]
    assert [(s.path, s.glob) for s in added] == \
        [(a, paths._FORMAT_GLOB["claude"]), (b, "sess-*.jsonl")]


def test_dict_and_array_shapes_coexist_across_agents(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    pol = {"sources": {
        "claude": {"paths": [str(tmp_path / "cl")], "glob": "c-*.jsonl"},     # dict form
        "copilot": [{"path": str(tmp_path / "cp"), "glob": "x-*.jsonl"}],     # array form
    }}
    res = paths.resolve_log_sources(pol)
    assert res.problems == []
    cl = [s for s in res.sources if s.agent == "claude" and s.provenance == "policy"]
    cp = [s for s in res.sources if s.agent == "copilot" and s.provenance == "policy"]
    assert cl[0].glob == "c-*.jsonl" and cp[0].glob == "x-*.jsonl"


def test_array_form_custom_tool_needs_per_entry_format(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    ok = tmp_path / "ok"
    pol = {"sources": {"mytool": [{"path": str(ok), "format": "claude", "glob": "u-*.jsonl"}]}}
    got = paths.custom_tool_sources(pol)
    assert len(got) == 1 and got[0].agent == "mytool" and got[0].glob == "u-*.jsonl"
    # a format-less array entry is rejected (no table level to hold one)
    bad = paths.resolve_log_sources({"sources": {"t": [{"path": str(ok)}]}})
    assert bad.problems and not [s for s in bad.sources if s.agent == "t"]


def test_doctor_paths_shows_the_declared_glob(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    pol = {"sources": {"claude": {"paths": ["~/alt"], "glob": "usage-*.ndjson"}}}
    assert "usage-*.ndjson" in pathprobe.run(root, pol)  # the pattern column


# ── surface key: restamp the client-surface only when declared (both shapes) ──

def test_surface_absent_defaults_empty_and_is_byte_identical(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    # No surface key anywhere ⇒ every LogSource.surface is "" (parser value stands).
    pol = {"sources": {"claude": {"paths": [str(tmp_path / "a")]}}}
    for s in paths.resolve_log_sources(pol).sources:
        assert s.surface == ""


def test_surface_dict_shape_restamps_imported_rows(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "kiro-cli-logs"
    logs.mkdir()
    (logs / "session-k1.jsonl").write_text(_claude_line("cs1", 120, 30) + "\n",
                                           encoding="utf-8")
    root = tmp_path / "proj"
    # A built-in agent (claude here) whose parser leaves surface="" — declaring
    # surface="cli" must restamp the row (the exact fix for a non-IDE store).
    _write_policy(root, f'[sources.claude]\npaths = ["{logs.as_posix()}"]\nsurface = "cli"\n')
    monkeypatch.chdir(root)
    importcmd.run(root, "all", _imp_args())
    rows = ledger.calls(root)
    assert rows and all(r.get("surface") == "cli" for r in rows)


def test_surface_array_shape_restamps_per_entry(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "alt"
    logs.mkdir()
    (logs / "s.jsonl").write_text(_claude_line("ca1", 10, 5) + "\n", encoding="utf-8")
    root = tmp_path / "proj"
    _write_policy(root, f'[[sources.claude]]\npath = "{logs.as_posix()}"\nsurface = "vscode"\n')
    monkeypatch.chdir(root)
    importcmd.run(root, "all", _imp_args())
    rows = ledger.calls(root)
    assert rows and all(r.get("surface") == "vscode" for r in rows)


def test_declared_surface_wins_on_builtin_collision(monkeypatch, tmp_path):
    # capture-precision §3.5: declaring a surface on a path that EQUALS a built-in used
    # to be silently dropped (the built-in, with no surface, won). Now the declared value
    # wins — it upgrades the colliding built-in instead of vanishing.
    _no_env(monkeypatch)
    monkeypatch.setenv("KIRO_DATA_DIR", str(tmp_path / "kd"))
    builtin = paths.kiro_token_log()  # the exact built-in kiro path
    pol = {"sources": {"kiro": {"paths": [str(builtin)], "surface": "cli"}}}
    ksrcs = [s for s in paths.resolve_log_sources(pol).sources if s.agent == "kiro"]
    assert ksrcs, "the kiro source must still resolve (not dropped)"
    assert all(s.surface == "cli" for s in ksrcs)  # declared value applied, not lost


def test_surface_out_of_set_is_a_problem_not_a_raise(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    res = paths.resolve_log_sources(
        {"sources": {"claude": {"paths": [str(tmp_path / "a")], "surface": "phone"}}})
    assert res.problems and any("surface must be one of" in p for p in res.problems)
    # the bad entry is skipped, never crashes the sweep (fail-open)
    assert not [s for s in res.sources
                if s.agent == "claude" and s.provenance == "policy"]


def test_custom_tool_surface_restamps_alongside_agent(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    logs = tmp_path / "router-logs"
    logs.mkdir()
    (logs / "r.jsonl").write_text(_claude_line("cx1", 50, 10) + "\n", encoding="utf-8")
    root = tmp_path / "proj"
    _write_policy(root, f'[sources.myrouter]\npaths = ["{logs.as_posix()}"]\n'
                        f'format = "claude"\nsurface = "cli"\n')
    monkeypatch.chdir(root)
    importcmd.run(root, "all", _imp_args())
    rows = ledger.calls(root)
    assert rows and all(r["agent"] == "myrouter" and r.get("surface") == "cli"
                        for r in rows)


def test_doctor_paths_shows_surface(monkeypatch, tmp_path):
    _isolate_homes(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    pol = {"sources": {"claude": [{"path": "~/alt", "surface": "cli"},
                                   {"path": "~/alt2"}]}}  # one declares surface, one doesn't
    out = pathprobe.run(root, pol)
    assert "surface=cli" in out       # declared surface shown
    assert "surface=parser" in out    # the undeclared-surface source shows the fallback


# ── Directive A: materialization, --sync-sources, and drift ────────────────────

def test_setup_materializes_active_sources_table(monkeypatch, tmp_path):
    # `cage setup` (initcmd.run) freezes the built-in seed into an ACTIVE [sources] table
    # (not the inert comment block the bundle ships).
    from cage import initcmd
    root = tmp_path / "proj"
    initcmd.run(root, pointer=False)
    text = (root / ".cage" / "cage.toml").read_text(encoding="utf-8")
    assert "[[sources.claude]]" in text and paths.SOURCES_START in text
    pol = policy.load(paths.Footprint(root).policy)
    assert [s for s in paths.resolve_log_sources(pol).sources if s.agent == "claude"]


def test_sync_sources_preserves_user_entries(monkeypatch, tmp_path):
    from cage import initcmd
    root = tmp_path / "proj"
    initcmd.run(root, pointer=False)
    fp = paths.Footprint(root)
    # A user pins an extra source OUTSIDE the managed marker block.
    fp.policy.write_text(fp.policy.read_text(encoding="utf-8")
                         + '\n[[sources.myrouter]]\npath = "~/mine"\nformat = "claude"\n',
                         encoding="utf-8")
    initcmd.sync_sources(fp)  # refresh managed block
    text = fp.policy.read_text(encoding="utf-8")
    assert "[[sources.myrouter]]" in text          # user entry survives the refresh
    assert "[[sources.claude]]" in text            # managed block regenerated


def test_sources_drift_reports_missing_and_in_sync(monkeypatch, tmp_path):
    _no_env(monkeypatch)
    # A materialized (seed) table has no drift; a table missing an agent shows it missing.
    full = {"sources": {}}
    for e in paths.sources_seed():
        full["sources"].setdefault(e["name"], []).append(
            {k: v for k, v in e.items() if k != "name"})
    missing, stale = paths.sources_drift(full)
    assert missing == [] and stale == []            # a full seed is in sync
    partial = {"sources": {"claude": full["sources"]["claude"]}}  # only claude declared
    missing, _ = paths.sources_drift(partial)
    assert any(m.startswith("copilot") for m in missing)  # copilot default is missing


def test_no_test_writes_a_raw_path_into_a_toml_basic_string():
    """Grep-gate (v0.47.2): a `[sources]` path written as `"{some_path}"` **must** go
    through `.as_posix()`.

    On Windows `str(Path)` is `C:\\Users\\…`, and TOML treats `\\U` inside a basic string as
    an escape — `tomllib` raises `Invalid hex value` and the source silently never
    resolves. Six tests here already followed the rule; `test_graphify_kiro` did not, and
    it cost a release (v0.47.1 → v0.47.2) after the same class had *already* cost one
    (v0.47.0 → v0.47.1, a path substituted into raw JSON).

    The rule generalises: **a filesystem path crossing into any escape-processing syntax
    — JSON, TOML basic strings, shell — needs an explicit conversion, never `str()`.**
    """
    import re
    from pathlib import Path as _P
    bad = []
    # non-greedy `.+?`, NOT `[^}"]+`: the form that actually shipped the bug was
    # `paths = ["{proj / "data.sqlite3"}"]` — it contains inner quotes, so a
    # quote-excluding class silently skips the one case this gate exists for.
    pat = re.compile(r'(?:paths?\s*=\s*\[?)"\{(.+?)\}"')
    for f in sorted((_P(__file__).parent).glob("test_*.py")):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue          # prose about the rule is not a violation of it
            for m in pat.finditer(line):
                expr = m.group(1)
                if ".as_posix()" not in expr:
                    bad.append(f"{f.name}:{i}: {expr}")
    assert not bad, (
        "TOML path(s) written without `.as_posix()` — these break on Windows:\n  "
        + "\n  ".join(bad))
