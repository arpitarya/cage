"""`cage policy sync` / `cage policy diff` — upgrade the project policy.toml
to the installed bundle (plan §3.10).

Generalizes `cage prices sync` from the pricing tables to the whole file: adds
new sections/keys the bundle gained since the project was inited, refreshes
stale un-customized defaults, and *never* touches a customized value or deletes
anything. Dry-run is the default surface; nothing anywhere auto-applies it.

Four rendered categories (the DoD contract):

- **add** — in the bundle, absent in the project → written with bundled
  defaults as plain text (one provenance comment), never into the managed
  block and never ``# cage:custom``-marked: behavior-neutral by construction,
  because `policy.load` was already merging exactly these defaults in.
- **update** — the project value equals its *old* bundled default (per the
  ``DEFAULT_CHANGES`` record below and the project's ``[meta] policy_version``)
  and the bundle's default changed → refreshed, old→new shown.
- **keep (customized)** — structurally owned (``# cage:custom`` / managed
  block) or the value differs from every default the bundle ever shipped →
  the user's edit, never touched, listed so the skip is visible.
- **orphan** — keys the bundle used to ship and no longer does (per
  ``REMOVED_KEYS``) → warned with version context, never deleted.

Where the old default is *not* reconstructable (a pre-``policy_version``
project and a key whose default actually changed) the row falls to a per-key
confirm bucket (``--yes section.key`` / ``--yes all``) — honest over clever,
exactly the `prices sync` stance. Pricing-family tables (``[prices]``,
``[credits]``, ``[alias]``, ``[tools.<name>]`` routes) are never diffed here:
the one merge brain is `pricescmd.sync_view`, whose summary embeds in this
output (the scalar ``[tools] order`` pipeline key *is* owned here — it is
policy, not pricing). Reads resolve like every read surface; writes are the
`pricestoml` text surgery (comment-preserving, atomic, typed
:class:`~cage.errors.CageError` on refusal).
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from cage import paths, policy, pricescmd, pricestoml
from cage.errors import CageError

_UNKNOWN_META = "unknown (pre-0.25)"

# Sections whose tables belong to the pricing merge brain (`cage prices sync`)
# — never diffed or written here. [tools] is split: its scalar keys (the
# pipeline `order`) are policy and sync here; its subtables ([tools.<name>]
# price_at routes) are pricing and delegate.
_DELEGATED = ("prices", "credits", "alias")

# ── the versioned-defaults record ────────────────────────────────────────────
# Maintenance rule: any release that CHANGES a bundled non-pricing default
# appends (changed_in_policy_version, old_value) here — ascending — and any
# release that REMOVES a bundled key records it in REMOVED_KEYS; both releases
# bump [meta] policy_version in data/policy.toml. Empty today: no non-pricing
# default value has ever changed and no key was ever removed (v0.2 → v0.25,
# verified against the git history of data/policy.toml). Empty is load-bearing:
# it lets a differing un-marked value classify as the user's own edit
# (old default == current default), never as clobber-able drift.
DEFAULT_CHANGES: dict[tuple[str, ...], tuple[tuple[str, object], ...]] = {}
#   (section, ..., key) -> ((changed_in_policy_version, old_value), ...)
REMOVED_KEYS: dict[tuple[str, ...], str] = {}
#   (section, ..., key) -> removed_in_policy_version


def _ver_tuple(v: object) -> tuple[int, ...]:
    """Version-tuple compare — "0.9.0" < "0.10.0" (lexicographic would not be)."""
    parts = str(v or "").lstrip("v").split(".")
    out = []
    for p in parts:
        digits = "".join(ch for ch in p if ch.isdigit())
        out.append(int(digits) if digits else 0)
    return tuple(out) or (0,)


def _meta_version(meta: dict) -> str:
    v = str(meta.get("policy_version") or "")
    return f"v{v}" if v else _UNKNOWN_META


def sync_recommendation(project_meta: dict) -> str | None:
    """One line when the installed bundle's policy defaults are newer than the
    project's — never auto-applied; shared by `policy sync`, `cage doctor`,
    and the freshness surface (one wording, one home)."""
    bundled = policy.bundled_raw().get("meta", {})
    bv = str(bundled.get("policy_version") or "")
    pv = str(project_meta.get("policy_version") or "")
    if not bv:
        return None
    if not pv or _ver_tuple(pv) < _ver_tuple(bv):
        shown = f"v{pv}" if pv else _UNKNOWN_META
        return (f"bundled policy defaults are newer (v{bv} > {shown}) — "
                f"run 'cage policy sync'")
    return None


def _project_raw(foot: paths.Footprint) -> dict:
    try:
        return policy.load_project_raw(foot.policy)
    except Exception as e:  # noqa: BLE001 — malformed project policy → clean CLI error
        raise CageError(f"{foot.policy}: {e}") from e


def _walk(tree: dict, known: tuple[str, ...] | None = None) -> dict[tuple[str, ...], dict]:
    """Flatten the non-pricing policy tree to {leaf-table path: {key: scalar}}.

    Skips the delegated pricing families, ``[meta]`` (version bookkeeping, not a
    tunable), and ``[sources]`` (configurable import paths — entirely user-owned,
    the bundle ships none, so sync never adds/updates/orphans it, plan Phase 4);
    under ``[tools]`` keeps only scalar keys (the subtables are price routes).
    ``known`` limits the walk to those top-level sections — the project walk passes
    the cage-known set so a user's own section is invisible to sync entirely."""
    tables: dict[tuple[str, ...], dict] = {}

    def descend(prefix: tuple[str, ...], node: dict) -> None:
        leaves = {k: v for k, v in node.items() if not isinstance(v, dict)}
        if leaves:
            tables[prefix] = leaves
        if prefix == ("tools",):  # subtables are pricing routes — delegated
            return
        for k, v in node.items():
            if isinstance(v, dict):
                descend(prefix + (k,), v)

    for section, node in (tree or {}).items():
        if section in _DELEGATED or section in ("meta", "sources") or not isinstance(node, dict):
            continue
        if known is not None and section not in known:
            continue
        descend((section,), node)
    return tables


def _default_at(changes: tuple[tuple[str, object], ...], current: object,
                pv: str) -> object:
    """The bundled default a ``policy_version``-era project was inited with:
    the ``old_value`` of the first change *after* that era, else the current."""
    for changed_in, old in changes:
        if _ver_tuple(pv) < _ver_tuple(changed_in):
            return old
    return current


def _git_tracked(root: Path, pol_path: Path) -> bool:
    """Fail-open: is the project policy.toml git-tracked? (Shelled out, never
    imported — the tasks.py rule; any failure ⇒ False, no note printed.)"""
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--error-unmatch",
                            str(pol_path)], capture_output=True, timeout=5)
        return r.returncode == 0
    except Exception:  # noqa: BLE001 — diagnostics only, never in the way
        return False


# ── view ─────────────────────────────────────────────────────────────────────

def sync_view(root: Path) -> dict:
    foot = paths.Footprint(root)
    bundled = policy.bundled_raw()
    b_meta = bundled.get("meta", {})
    if not foot.policy.exists():
        return {"no_project": True, "policy_path": str(foot.policy),
                "bundled_meta": b_meta, "project_meta": {}}
    project = _project_raw(foot)
    p_meta = project.get("meta", {})
    pv = str(p_meta.get("policy_version") or "")
    text = foot.policy.read_text(encoding="utf-8")
    owned = pricescmd._custom_headers(text)
    b_tables = _walk(bundled)
    known = tuple(set(bundled) | set(policy._SECTIONS))
    p_tables = _walk(project, known=known)

    add, update, confirm, customized, orphan, project_own = [], [], [], [], [], []
    in_sync_n = 0
    for path in sorted(set(b_tables) | set(p_tables)):
        dotted = ".".join(path)
        b_vals = b_tables.get(path, {})
        p_vals = p_tables.get(path, {})
        is_owned = tuple(path) in owned
        for key in sorted(set(b_vals) | set(p_vals)):
            path_key = path + (key,)
            if key not in p_vals:
                add.append({"table": dotted, "path": list(path), "key": key,
                            "value": b_vals[key], "owned": is_owned})
                continue
            if key not in b_vals:
                if path_key in REMOVED_KEYS:
                    orphan.append({"table": dotted, "key": key,
                                   "value": p_vals[key],
                                   "removed_in": REMOVED_KEYS[path_key]})
                else:
                    project_own.append({"table": dotted, "key": key})
                continue
            p_val, b_val = p_vals[key], b_vals[key]
            if p_val == b_val:
                in_sync_n += 1
                continue
            item = {"table": dotted, "path": list(path), "key": key,
                    "project": p_val, "bundled": b_val}
            if is_owned:
                customized.append({**item, "reason": "marked"})
                continue
            changes = DEFAULT_CHANGES.get(path_key)
            if not changes:  # default never changed ⇒ the differ is the user's edit
                customized.append({**item, "reason": "edited"})
            elif pv:
                old = _default_at(changes, b_val, pv)
                if p_val == old:
                    update.append({**item, "old": old})
                else:
                    customized.append({**item, "reason": "edited"})
            elif any(p_val == old for _, old in changes):
                confirm.append(item)  # pre-policy_version era — not reconstructable
            else:
                customized.append({**item, "reason": "edited"})

    prices_d = pricescmd.sync_view(root)
    return {"no_project": False, "policy_path": str(foot.policy),
            "bundled_meta": b_meta, "project_meta": p_meta,
            "add": add, "update": update, "confirm": confirm,
            "customized": customized, "orphan": orphan,
            "project_own": project_own, "in_sync_n": in_sync_n,
            "recommendation": sync_recommendation(p_meta),
            "prices": {k: prices_d[k] for k in
                       ("in_sync", "customized", "drift", "bundled_only",
                        "project_only", "recommendation")},
            "prices_text": pricescmd.render_sync(prices_d),
            "git_tracked": _git_tracked(root, foot.policy)}


# ── apply ────────────────────────────────────────────────────────────────────

def _fmt_val(v: object) -> str:
    return pricestoml._fmt_value(v)


def _key_id(item: dict) -> str:
    return f"{item['table']}.{item['key']}"


def sync_apply(root: Path, d: dict, yes: list[str]) -> list[str]:
    """--apply: write adds and updates, apply --yes-confirmed rows, then stamp
    ``[meta] policy_version`` (only that key — ``prices_version`` stays the
    prices brain's business). Never touches a pricing table."""
    out: list[str] = []
    bv = str(d["bundled_meta"].get("policy_version") or "")
    comment = f"# added by cage policy sync (v{bv})" if bv else \
        "# added by cage policy sync"
    take_all = "all" in yes
    wanted = {y for y in yes if y != "all"}
    applied: set[str] = set()

    by_table: dict[tuple[str, ...], list[dict]] = {}
    for a in d["add"]:
        by_table.setdefault(tuple(a["path"]), []).append(a)
    for path in sorted(by_table):
        items = by_table[path]
        dotted = items[0]["table"]
        if items[0]["owned"]:
            out.append(f"· [{dotted}] is customized — not adding "
                       + ", ".join(i["key"] for i in items)
                       + " (bundled defaults stay live via the merge)")
            continue
        values = {i["key"]: i["value"] for i in items}
        res = pricestoml.add_table(root, path, values, comment=comment)
        if res["mode"] == "added":
            out.append(f"✔ [{dotted}] added ("
                       + ", ".join(f"{k} = {_fmt_val(v)}"
                                   for k, v in sorted(values.items())) + ")")
        else:  # table existed — add_table appended the missing keys in place
            out.append(f"✔ [{dotted}] "
                       + ", ".join(f"{k} = {_fmt_val(v)}"
                                   for k, v in sorted(values.items()))
                       + " added")

    for u in d["update"]:
        pricestoml.set_table(root, tuple(u["path"]), {u["key"]: u["bundled"]},
                             mark_custom=False)
        out.append(f"✔ [{u['table']}] {u['key']}: {_fmt_val(u['project'])} → "
                   f"{_fmt_val(u['bundled'])}")

    for c in d["confirm"]:
        kid = _key_id(c)
        if take_all or kid in wanted:
            pricestoml.set_table(root, tuple(c["path"]), {c["key"]: c["bundled"]},
                                 mark_custom=False)
            applied.add(kid)
            out.append(f"✔ [{c['table']}] {c['key']}: {_fmt_val(c['project'])} → "
                       f"{_fmt_val(c['bundled'])} (confirmed)")
    for m in sorted(wanted - applied - {_key_id(c) for c in d["confirm"]}):
        out.append(f"· --yes {m}: not a confirmable row — nothing to apply")
    skipped = [_key_id(c) for c in d["confirm"] if _key_id(c) not in applied]
    if skipped:
        out.append("· left untouched (confirm each with --yes <section.key>): "
                   + ", ".join(skipped))

    pv = str(d["project_meta"].get("policy_version") or "")
    if bv and pv != bv:
        if skipped:
            # Stamping would re-era the file and silently reclassify the pending
            # confirm rows as customized next run — stamp only once they're decided.
            out.append(f"· [meta] policy_version not stamped — {len(skipped)} "
                       "row(s) await --yes confirmation")
        else:
            pricestoml.update_meta(root, {"policy_version": bv})
            out.append(f"✔ [meta] policy_version stamped v{bv}")
    return out


# ── render ───────────────────────────────────────────────────────────────────

def render(d: dict, updated: list[str] | None = None) -> str:
    if d.get("no_project"):
        return (f"policy sync — no project policy.toml at {d['policy_path']}\n"
                f"the bundled defaults apply directly — nothing can be stale.\n"
                f"run `cage setup` to materialize one.")
    out = [f"policy sync — bundled {_meta_version(d['bundled_meta'])} vs project "
           f"{_meta_version(d['project_meta'])}", ""]
    if d["in_sync_n"]:
        out.append(f"· {d['in_sync_n']} project keys equal to the bundle — in sync")
    if d["add"]:
        out.append(f"add ({len(d['add'])}) — in the bundle, missing here; "
                   "--apply writes bundled defaults:")
        for a in d["add"]:
            out.append(f"  + [{a['table']}] {a['key']} = {_fmt_val(a['value'])}"
                       + (" (table customized — stays live via the merge)"
                          if a["owned"] else ""))
    if d["update"]:
        out.append(f"update ({len(d['update'])}) — stale copies of old bundled "
                   "defaults; --apply refreshes:")
        for u in d["update"]:
            out.append(f"  ~ [{u['table']}] {u['key']}: {_fmt_val(u['project'])} → "
                       f"{_fmt_val(u['bundled'])}")
    if d["confirm"]:
        out.append(f"confirm ({len(d['confirm'])}) — differs from the bundle and the "
                   "old default is not reconstructable (pre-policy_version file):")
        for c in d["confirm"]:
            out.append(f"  ? [{c['table']}] {c['key']}: project "
                       f"{_fmt_val(c['project'])}, bundled {_fmt_val(c['bundled'])}")
            out.append(f"    apply:   cage policy sync --apply --yes {_key_id(c)}")
    if d["customized"]:
        out.append(f"keep ({len(d['customized'])}) — customized, never touched:")
        for c in d["customized"]:
            out.append(f"  · [{c['table']}] {c['key']} = {_fmt_val(c['project'])} "
                       f"(bundled {_fmt_val(c['bundled'])})")
    if d["orphan"]:
        out.append(f"orphan ({len(d['orphan'])}) — the bundle no longer ships "
                   "these; never deleted:")
        for o in d["orphan"]:
            out.append(f"  ⚠ [{o['table']}] {o['key']} = {_fmt_val(o['value'])} "
                       f"(dropped in v{o['removed_in']})")
    if d["project_own"]:
        out.append("· your own keys (not in the bundle) — untouched: "
                   + ", ".join(f"{p['table']}.{p['key']}" for p in d["project_own"]))
    out += ["", "pricing tables — delegated to `cage prices sync`:",
            *("  " + line for line in d["prices_text"].splitlines())]
    if updated is not None:
        out += ["", *updated] if updated else \
            ["", "· --apply: nothing to write — already in sync"]
    else:
        pending = d["add"] or d["update"] or d["confirm"] or d["recommendation"]
        if pending:
            out += ["", "dry-run — `--apply` writes adds/updates and stamps [meta] "
                        "policy_version; customized values are never modified, "
                        "orphans never deleted."]
            if d["recommendation"]:
                out.append(f"· {d['recommendation']}")
        else:
            out += ["", "✔ nothing to do — project policy matches the installed bundle."]
    if d["git_tracked"]:
        out.append("· policy.toml is git-tracked — review any applied change with "
                   "git; cage writes no .bak files.")
    return "\n".join(out)


# ── dispatch ─────────────────────────────────────────────────────────────────

def run(args, root: Path, pol: dict) -> tuple[dict, str]:
    """(payload, text) — `diff` is the dry-run view by name; `sync --apply`
    writes. The caller emits (envelope for --json)."""
    apply = bool(getattr(args, "apply", False))
    if args.action == "diff" and apply:
        raise CageError("`cage policy diff` is the dry-run view — "
                        "use `cage policy sync --apply` to write")
    d = sync_view(root)
    updated = None
    if apply and not d.get("no_project"):
        updated = sync_apply(root, d, list(getattr(args, "yes", None) or []))
    return {**d, "updated": updated}, render(d, updated)
