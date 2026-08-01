"""`[sources] path_globs` — the root-agnostic discovery patterns `cage import --path` uses.

Two keys, two jobs (path-globs handoff §5). ``glob`` is **anchored** to its declared
``path`` and drives every normal import; ``path_globs`` is **root-agnostic** and is read
only when ``--path``/``--project`` replaces the location with a user-provided root.

Why the second key exists at all: copilot's ``--path`` branch used to hardcode
``*/events.jsonl`` — the CLI shape only — so pointing it at a VS Code
``chatSessions`` tree matched nothing while the files sat there and parsed fine. Reusing
the anchored ``glob`` would have relocated that bug rather than fixed it, because
``*/chatSessions/*.jsonl`` under a ``chatSessions`` directory matches nothing either.

The patterns live in ``cage.toml``, never in Python (Directive A): code holds the *seed*,
`cage setup` *materializes* it, and import reads the *project file*. The consequence is
deliberate and asserted here — an unmaterialized project scans nothing under ``--path``,
loudly.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cage import clicmds, importcmd, initcmd, ledger, paths, policy
from srcseed import mkcage

FIXTURES = Path(__file__).parent / "fixtures" / "transcripts" / "copilot"


def _args(agent="copilot", path=None, project=None, since=None):
    return SimpleNamespace(agent=agent, path=path, project=project, since=since)


def _cli_events() -> str:
    """One Copilot **CLI** session's `events.jsonl` (usage at `session.shutdown`)."""
    return json.dumps({"type": "session.shutdown", "timestamp": "2026-06-14T10:00:00Z",
                       "data": {"totalPremiumRequests": 1, "currentModel": "gpt-5-mini",
                                "modelMetrics": {"gpt-5-mini": {"usage": {
                                    "inputTokens": 1200, "outputTokens": 80,
                                    "cacheReadTokens": 0}}}}}) + "\n"


def _vscode_session() -> str:
    """A real VS Code `chatSessions/<id>.jsonl` — the store the old glob couldn't reach."""
    return (FIXTURES / "vscode" / "20236884-4f14-453d-a016-aa37c72f819d.jsonl").read_text(
        encoding="utf-8")


def _staged(tmp_path, *, cli=False, vscode=False, foreign=False) -> Path:
    """A directory a user would point `--path` at, holding the requested store shapes."""
    stage = tmp_path / "stage"
    stage.mkdir(exist_ok=True)
    if cli:
        ev = stage / "sess-1" / "events.jsonl"
        ev.parent.mkdir(parents=True, exist_ok=True)
        ev.write_text(_cli_events(), encoding="utf-8")
    if vscode:
        cs = stage / "ws-abc" / "chatSessions" / "20236884-4f14-453d-a016-aa37c72f819d.jsonl"
        cs.parent.mkdir(parents=True, exist_ok=True)
        cs.write_text(_vscode_session(), encoding="utf-8")
    if foreign:
        # A non-copilot .jsonl sitting in the same tree. It must not MATCH — "matched but
        # parsed to zero rows" is only incidentally safe, and would silently start
        # recording the day some other tool's jsonl happened to parse.
        (stage / "notes.jsonl").write_text(
            json.dumps({"hello": "world", "tokens": 999}) + "\n", encoding="utf-8")
    return stage


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    """A materialized project (`cage.toml` carries the seeded `[sources]` + `path_globs`)
    with every agent home redirected somewhere empty, so a sweep reads only what a test
    stages."""
    root = mkcage(tmp_path / "proj")
    for env in ("CLAUDE_CONFIG_DIR", "COPILOT_HOME", "KIRO_DATA_DIR", "CAGE_VSCODE_USER"):
        monkeypatch.setenv(env, str(tmp_path / f"home-{env.lower()}"))
    monkeypatch.chdir(root)
    return root


# ── 1–3: the shapes `--path` must reach ───────────────────────────────────────

def test_path_reaches_the_copilot_cli_shape(proj, tmp_path):
    """`--path <dir>` over `<sid>/events.jsonl` — the shape that always worked."""
    stage = _staged(tmp_path, cli=True)
    importcmd.run(proj, "copilot", _args(path=str(stage)))
    calls = ledger.calls(proj)
    assert len(calls) == 1
    assert calls[0]["tokens_in"] == 1200 and calls[0]["model"] == "gpt-5-mini"


def test_path_reaches_the_vscode_chatsessions_shape_with_the_parsers_surface(proj, tmp_path):
    """THE regression this change exists for: `--path` over a `chatSessions` tree.

    The rows must also carry ``surface = "vscode"`` **from the parser** — under an
    override nothing is declared, so the parser's own value has to be right. That was
    untested: the lab run only ever saw ``vscode`` because a `[sources]` entry declared
    it, which would have masked a wrong parser value.
    """
    stage = _staged(tmp_path, vscode=True)
    importcmd.run(proj, "copilot", _args(path=str(stage)))
    calls = ledger.calls(proj)
    assert calls, "the chatSessions store must be reachable under --path"
    assert {c["surface"] for c in calls} == {"vscode"}
    assert {c["agent"] for c in calls} == {"copilot"}


def test_both_shapes_under_one_path_import_without_double_counting(proj, tmp_path):
    """Overlapping patterns must dedupe the *file set*, not merely the rows."""
    stage = _staged(tmp_path, cli=True, vscode=True)
    importcmd.run(proj, "copilot", _args(path=str(stage)))
    calls = ledger.calls(proj)
    surfaces = sorted(c["surface"] for c in calls)
    assert "vscode" in surfaces and len(calls) == len(set(c["id"] for c in calls))
    cli_rows = [c for c in calls if c["model"] == "gpt-5-mini"]
    assert len(cli_rows) == 1  # the CLI session recorded exactly once


# ── 4: foreign files are not MATCHED (not merely "parse to zero") ─────────────

def test_a_foreign_jsonl_under_path_is_never_matched(proj, tmp_path):
    """Safe by construction: copilot names both known shapes, so a stray `.jsonl` is
    never even opened. Asserted at the scan layer — a row-count assertion would pass
    just as well for a file that *was* read and happened to yield nothing."""
    stage = _staged(tmp_path, cli=True, foreign=True)
    pats = paths.path_globs_for("copilot", policy.load(paths.Footprint(proj).policy))
    matched = importcmd._scan(proj, "copilot", stage, pats, None)
    assert [f.name for f in matched] == ["events.jsonl"]
    assert not any(f.name == "notes.jsonl" for f in matched)


def test_overlapping_patterns_hand_each_file_over_once(proj, tmp_path):
    """Two patterns that both match one file must still scan it once — `_ingest` parsing
    a transcript twice is wasted work at best and a double-count risk at worst."""
    stage = _staged(tmp_path, cli=True)
    both = ["**/events.jsonl", "**/*.jsonl"]  # deliberately overlapping
    matched = importcmd._scan(proj, "copilot", stage, both, None)
    assert len(matched) == len(set(matched)) == 1


# ── 5: a normal (pathless) import is untouched ────────────────────────────────

def test_path_globs_never_affect_a_normal_import(proj, tmp_path, monkeypatch):
    """`path_globs` is `--path`-only. A pathless sweep must produce byte-identical rows
    whether or not the key is declared — it is the anchored `glob` that drives it."""
    home = tmp_path / "home-copilot_home" / "session-state" / "sess-1"
    home.mkdir(parents=True)
    (home / "events.jsonl").write_text(_cli_events(), encoding="utf-8")
    monkeypatch.setenv("COPILOT_HOME", str(tmp_path / "home-copilot_home"))
    importcmd.run(proj, "copilot", _args(path=None))
    with_key = [dict(c) for c in ledger.calls(proj)]
    assert with_key, "sanity: the pathless registry sweep captured the staged session"

    # Same fixture, same table, `path_globs` stripped from every entry.
    other = mkcage(tmp_path / "proj2")
    text = paths.Footprint(other).policy.read_text(encoding="utf-8")
    stripped = "\n".join(ln for ln in text.splitlines()
                         if not ln.startswith("path_globs = "))
    paths.Footprint(other).policy.write_text(stripped + "\n", encoding="utf-8")
    importcmd.run(other, "copilot", _args(path=None))
    without_key = [dict(c) for c in ledger.calls(other)]

    def _shape(rows):
        return sorted((r["model"], r["tokens_in"], r["tokens_out"], r["surface"])
                      for r in rows)

    assert _shape(with_key) == _shape(without_key)


# ── 6: absent path_globs ⇒ nothing scanned, said out loud ─────────────────────

def test_absent_path_globs_scans_nothing_and_says_so(tmp_path, monkeypatch):
    """The deliberate behaviour change. A project that never materialized its table gets
    a loud no-op, never a silent code fallback — a fallback here would put the patterns
    back in two places, which is the whole problem this key closes."""
    root = tmp_path / "bare"
    (root / ".cage").mkdir(parents=True)
    monkeypatch.chdir(root)
    stage = _staged(tmp_path, cli=True, vscode=True)

    lines = importcmd.run(root, "copilot", _args(path=str(stage)))

    assert ledger.calls(root) == []
    loud = [ln for ln in lines if "path_globs" in ln]
    assert len(loud) == 1
    assert loud[0].startswith("⚠ copilot:")
    assert "cage setup --sync-sources" in loud[0]  # the fix is named, and it is runnable


def test_the_zero_match_warning_names_the_patterns_it_tried(proj, tmp_path, monkeypatch):
    """The other half of the fix. "matched 0 files" with the glob hidden is unanswerable —
    that omission is why the copilot bug cost twenty minutes to find."""
    from cage import report
    # A home marker must exist for the triple gate to fire (installed but capturing nothing).
    (tmp_path / "home-copilot_home").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(importcmd, "_home_markers",
                        lambda a: [tmp_path / "home-copilot_home"])
    empty = tmp_path / "empty"
    empty.mkdir()
    importcmd.run(proj, "copilot", _args(path=str(empty)))

    warns = report.capture_warnings(importcmd.capture_health(proj))
    assert warns, "an installed agent that matched nothing must warn"
    assert "matched 0 files (tried: " in warns[0]
    assert "**/events.jsonl" in warns[0] and "**/chatSessions/*.jsonl" in warns[0]


# ── 7: the grep-gate — no glob literal survives in an import branch ───────────

def test_no_glob_literal_remains_in_the_import_path_branches():
    """The guard that stops this fix silently regressing.

    A future edit that reintroduces a hardcoded pattern in an import adapter puts the
    discovery rules back in two places — code *and* `cage.toml` — which is exactly the
    condition that let copilot's `--path` glob drift out of sync with its parser.
    Docstrings are exempt: prose that mentions a path shape is documentation, not a glob
    cage will scan with.
    """
    tree = ast.parse(Path(importcmd.__file__).read_text(encoding="utf-8"))
    targets = {"import_claude", "import_copilot", "import_kiro", "_override_sources"}
    offenders, seen = [], set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in targets:
            continue
        seen.add(node.name)
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]  # skip the docstring
        for sub in body:
            for n in ast.walk(sub):
                if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                        and any(ch in n.value for ch in "*?[")):
                    offenders.append(f"{node.name}: {n.value!r}")
    # A gate that inspects nothing passes forever. If a branch is renamed, this fails
    # here rather than quietly going blind.
    assert seen == targets, f"gate went blind — not found in importcmd.py: {targets - seen}"
    assert not offenders, ("glob literal(s) back in an import branch — patterns belong in "
                           f"cage.toml `[sources] path_globs`: {offenders}")


# ── 8: materializer round-trip ────────────────────────────────────────────────

def test_setup_materializes_path_globs_and_resync_is_idempotent(tmp_path):
    """`cage setup` writes the seed; `--sync-sources` re-runs to identical bytes."""
    root = tmp_path / "fresh"
    initcmd.run(root, pointer=False)
    fp = paths.Footprint(root)
    text = fp.policy.read_text(encoding="utf-8")
    assert 'path_globs = ["**/events.jsonl"]' in text
    assert 'path_globs = ["**/chatSessions/*.jsonl"]' in text
    assert 'path_globs = ["**/*.jsonl"]' in text

    assert initcmd.sync_sources(fp) is False  # nothing to change
    assert fp.policy.read_text(encoding="utf-8") == text

    resolved = paths.path_globs_for("copilot", policy.load(fp.policy))
    assert resolved == ["**/events.jsonl", "**/chatSessions/*.jsonl"]


def test_a_hand_written_path_globs_is_honoured_verbatim(tmp_path):
    """A user's declared patterns are used exactly as written — never quietly unioned
    with the seed behind their back. `replace = true` drops the managed entries first,
    same table and same semantics as it already has for `paths`/`glob`."""
    pol = {"sources": {"copilot": {"replace": True, "paths": ["/logs/mine"],
                                   "glob": "usage-*.ndjson",
                                   "path_globs": ["**/mine-*.ndjson"]}}}
    assert paths.path_globs_for("copilot", pol) == ["**/mine-*.ndjson"]


def test_a_user_entry_adds_to_the_managed_ones_without_replace(tmp_path):
    """Without `replace`, an extra `[[sources.copilot]]` is additive — the same rule the
    table already applies to paths, so `path_globs` needs no special case."""
    pol = {"sources": {"copilot": [{"path": "/logs/a", "glob": "*.jsonl",
                                    "path_globs": ["**/events.jsonl"]},
                                   {"path": "/logs/b", "glob": "*.ndjson",
                                    "path_globs": ["**/extra.ndjson"]}]}}
    assert paths.path_globs_for("copilot", pol) == ["**/events.jsonl", "**/extra.ndjson"]


def test_a_malformed_path_globs_is_a_problem_never_a_silent_glob_fallback(tmp_path):
    """Fail-open at the sweep (the entry is skipped, nothing raises) but never silent —
    falling back to the anchored `glob` here would recreate the original bug exactly."""
    res = paths.resolve_log_sources(
        {"sources": {"copilot": {"paths": ["/logs/a"], "path_globs": "**/events.jsonl"}}})
    assert res.sources == []
    assert any("path_globs must be a non-empty list" in p for p in res.problems)


def test_doctor_flags_a_table_materialized_before_path_globs_existed(tmp_path):
    """Stale materialization is advisory, not a failure: imports still work, only the
    `--path` escape hatch is missing — which would otherwise surface as a mystery at the
    exact moment someone reaches for it."""
    pol = {"sources": {"copilot": {"paths": ["/logs/a"], "glob": "*.jsonl"}}}
    assert paths.path_globs_missing(pol) == ["copilot"]
    pol["sources"]["copilot"]["path_globs"] = ["**/a.jsonl"]
    assert paths.path_globs_missing(pol) == []


def test_project_override_uses_the_same_declared_patterns(proj, tmp_path, monkeypatch):
    """`--project` resolves a claude project dir rather than a user dir, but it is the
    same "the root is replaced" case, so it draws on the same key — no literal is left
    behind next to the one this change removed."""
    home = tmp_path / "home-claude_config_dir"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home))
    target = tmp_path / "widget"
    target.mkdir()
    sess = home / "projects" / paths.claude_project_slug(target)
    sess.mkdir(parents=True)
    (sess / "s.jsonl").write_text(json.dumps({
        "type": "assistant", "uuid": "u1", "timestamp": "2026-06-14T10:00:00Z",
        "message": {"model": "claude-opus-4-8",
                    "usage": {"input_tokens": 100, "output_tokens": 50}}}) + "\n",
        encoding="utf-8")
    importcmd.run(proj, "claude", _args(agent="claude", project=str(target)))
    assert len(ledger.calls(proj)) == 1
