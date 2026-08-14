"""GC4 + GC5 (graphify-capture plan) — graph freshness and the forward model.

GC4: `cage doctor` reports graph.json staleness vs HEAD.
GC5a: a history band over graphify receipts, refusing below MIN_ESTIMATE_N.
GC5b: a deterministic day-one repo ceiling from graph.json (same graph ⇒ same band).
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cage import doctorcmd, graphifymodel, savings
from cage.constants import MIN_ESTIMATE_N
from cage.policy import load as load_policy
from cage import paths


@pytest.fixture
def proj(tmp_path, monkeypatch):
    monkeypatch.delenv("CAGE_BASE", raising=False)
    (tmp_path / ".cage" / "ledger").mkdir(parents=True)
    return tmp_path


def _graph(proj: Path, files: list[str], communities: list[int] | None = None) -> None:
    """Write a graphify-out with one node per file. ``communities`` (default: each file
    its own community) assigns each file's node to a community id, so the bounded ceiling
    (Phase A) has a structure to group by; omit it to exercise the pre-community fallback
    via ``_graph_no_community``."""
    out = proj / "graphify-out"
    out.mkdir(exist_ok=True)
    comms = communities if communities is not None else list(range(len(files)))
    (out / "graph.json").write_text(json.dumps(
        {"nodes": [{"source_file": f, "community": c} for f, c in zip(files, comms)]}))
    for f in files:
        (proj / f).write_text("x = 1\n" * 300)
    (out / "GRAPH_REPORT.md").write_text("# report\n" * 30)


def _graph_no_community(proj: Path, files: list[str]) -> None:
    """A pre-community graph.json (no `community` field) — exercises the unbounded fallback."""
    out = proj / "graphify-out"
    out.mkdir(exist_ok=True)
    (out / "graph.json").write_text(json.dumps(
        {"nodes": [{"source_file": f} for f in files]}))
    for f in files:
        (proj / f).write_text("x = 1\n" * 300)
    (out / "GRAPH_REPORT.md").write_text("# report\n" * 30)


# ── GC5b: deterministic, community-bounded ceiling ──────────────────────────

def test_repo_ceiling_deterministic(proj):
    # a.py+b.py in one community, c.py alone in another → largest community = {a,b}
    _graph(proj, ["a.py", "b.py", "c.py"], communities=[0, 0, 1])
    d1 = graphifymodel.repo_ceiling(proj, cwd=proj)
    d2 = graphifymodel.repo_ceiling(proj, cwd=proj)
    assert d1["ok"] and d1 == d2                     # same graph ⇒ same band (determinism)
    assert d1["bounded"] is True
    assert d1["files"] == 3 and d1["communities"] == 2
    assert d1["ceiling_files"] == 2                  # largest community spans 2 files
    # bounded ceiling < whole corpus (the whole point of Phase A)
    assert 0 < d1["ceiling_tokens"] < d1["corpus_tokens"]
    assert d1["typical_tokens"] <= d1["ceiling_tokens"]
    assert d1["method"] == "modeled"


def test_repo_ceiling_bounded_below_whole_corpus(proj):
    # 4 files, each its own community → largest community is one file, far below the whole
    _graph(proj, ["a.py", "b.py", "c.py", "d.py"], communities=[0, 1, 2, 3])
    d = graphifymodel.repo_ceiling(proj, cwd=proj)
    assert d["bounded"] and d["communities"] == 4
    assert d["ceiling_tokens"] < d["corpus_tokens"]  # the bound is a fraction of the whole


def test_repo_ceiling_pre_community_graph_is_unbounded_but_loud(proj):
    _graph_no_community(proj, ["a.py", "b.py", "c.py"])
    d = graphifymodel.repo_ceiling(proj, cwd=proj)
    assert d["ok"] and d["bounded"] is False         # fallback, but explicit
    assert d["ceiling_tokens"] == d["corpus_tokens"]  # whole corpus, labelled unbounded
    assert "UNBOUNDED" in graphifymodel.render_repo_ceiling(d)


def test_repo_ceiling_no_graph_refuses(proj):
    d = graphifymodel.repo_ceiling(proj, cwd=proj)
    assert not d["ok"] and "no graphify-out/graph.json" in d["reason"]


# ── GC5a: history band, min-n gated ─────────────────────────────────────────

def test_history_band_refuses_below_min_n(proj):
    for i in range(MIN_ESTIMATE_N - 1):
        savings.record(proj, tool="graphify", unit="tokens", raw_alternative=1000,
                       actual=100, op="query", savings_id=f"s_h{i:03d}")
    d = graphifymodel.history_band(proj, load_policy(paths.Footprint(proj).policy))
    assert not d["ok"] and d["n"] == MIN_ESTIMATE_N - 1
    assert d["method"] == "modeled"


def test_history_band_at_min_n_is_a_band(proj):
    for i in range(MIN_ESTIMATE_N):
        savings.record(proj, tool="graphify", unit="tokens", raw_alternative=1000 + i * 10,
                       actual=100, op="query", savings_id=f"s_h{i:03d}")
    d = graphifymodel.history_band(proj, load_policy(paths.Footprint(proj).policy))
    assert d["ok"] and d["n"] == MIN_ESTIMATE_N
    assert d["tokens"]["q1"] <= d["tokens"]["median"] <= d["tokens"]["q3"]
    assert d["method"] == "modeled"


# ── GC4: doctor graph staleness ─────────────────────────────────────────────

def _git(proj: Path, *args) -> None:
    subprocess.run(["git", "-C", str(proj), *args], check=True,
                   capture_output=True, text=True)


def test_doctor_graph_staleness_fresh_and_stale(proj):
    _git(proj, "init")
    _git(proj, "config", "user.email", "t@t")
    _git(proj, "config", "user.name", "t")
    _graph(proj, ["a.py"])
    (proj / "a.py").write_text("v = 1\n")
    _git(proj, "add", "-A")
    _git(proj, "commit", "-m", "one")
    # graph.json was written before the commit → predates HEAD → stale
    import os
    old = subprocess.run(["git", "-C", str(proj), "log", "-1", "--format=%ct"],
                         capture_output=True, text=True).stdout.strip()
    os.utime(proj / "graphify-out" / "graph.json", (int(old) - 100, int(old) - 100))
    level, detail = doctorcmd._graph_staleness(proj)
    assert level == "warn" and "predates HEAD" in detail
    # touch the graph to now → current
    os.utime(proj / "graphify-out" / "graph.json", None)
    level2, detail2 = doctorcmd._graph_staleness(proj)
    assert level2 == "ok" and "current with HEAD" in detail2


def test_doctor_graph_staleness_no_graph_is_ok(proj):
    level, detail = doctorcmd._graph_staleness(proj)
    assert level == "ok" and "not used" in detail
