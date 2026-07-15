"""`cage prices` — manage the price tables the ledger reprices against (plan §3.3).

Five verbs over two read layers and one write layer:

- ``list``     — every price row visible to this ledger: bundled vs project origin,
  which wins, plus the ``[meta]`` version of each side and the sync recommendation.
- ``unpriced`` — scan the resolved ledger for calls whose model matched ``none``
  (billing $0) and print a ready-to-run fix line per key. cage itself never fetches
  a price — no network on any cage code path; the research step is the user's
  (vendor pricing page, or a web search for "<vendor> <model> API pricing").
- ``set``      — idempotent insert-or-update of a project price row.
- ``alias``    — explicit routing for router pseudo-models (``copilot/auto``);
  renders as an ``alias`` footnote, never ``exact``, and never a silent default.
- ``sync``     — compare project rows against the installed bundle; dry-run by
  default, ``--update`` applies bundled values only to rows the user confirmed
  (cage cannot reconstruct which *old* bundle an unmarked row came from, so it
  lists the diff and asks per row — simple and honest over clever).

Reads resolve like every other read surface (``--ledger``/``CAGE_BASE`` → project
``.cage/`` → global ``~/.cage``); writes go to that root's *project* policy.toml —
the bundled table is read-only at runtime. Expected failures raise
:class:`~cage.errors.CageError` at the CLI boundary.
"""
from __future__ import annotations

import re
from pathlib import Path

from cage import ledger, paths, policy, prices, pricestoml, render
from cage.errors import CageError

_UNKNOWN_META = "unknown (pre-0.19)"


def _fmt(v: float) -> str:
    return f"{v:g}"


def _key(provider: str, model: str) -> str:
    return f"{provider or '—'}/{model}"


def _meta_version(meta: dict) -> str:
    return str(meta.get("prices_version") or "") or _UNKNOWN_META


def _tables(prices: dict) -> dict:
    """Only the per-provider row tables under ``[prices]`` — scalar keys there
    (``stale_days``, or a user typo) are settings, not providers, and iterating
    them as tables is a TypeError waiting to happen."""
    return {k: v for k, v in (prices or {}).items() if isinstance(v, dict)}


def sync_recommendation(project_meta: dict) -> str | None:
    """One line when the installed bundle's prices are newer than the project's —
    never auto-applied; shared by `prices list`, `sync`, and `cage doctor`."""
    bundled = policy.bundled_raw().get("meta", {})
    bv = str(bundled.get("prices_version") or "")
    pv = str(project_meta.get("prices_version") or "")
    if not bv:
        return None
    if not pv or pv < bv:  # ISO dates — lexicographic == chronological
        shown = pv or _UNKNOWN_META
        return (f"bundled prices are newer ({bv} > {shown}) — run 'cage prices sync'")
    return None


def _project_raw(foot: paths.Footprint) -> dict:
    try:
        return policy.load_project_raw(foot.policy)
    except Exception as e:  # noqa: BLE001 — malformed project policy → clean CLI error
        raise CageError(f"{foot.policy}: {e}") from e


def _custom_headers(text: str) -> set[tuple[str, ...]]:
    """Table paths the user owns: marked ``# cage:custom`` or inside the managed
    block (rows written by `prices set`/`alias` are customized by definition)."""
    owned: set[tuple[str, ...]] = set()
    before, body, after = pricestoml.split_block(text)
    for line in (before + after).splitlines():
        if pricestoml.CUSTOM_MARK in line:
            hp = pricestoml._header_path(line.split(pricestoml.CUSTOM_MARK)[0].rstrip())
            if hp:
                owned.add(tuple(hp))
    owned.update(pricestoml._block_tables(body))
    return owned


# ── list ─────────────────────────────────────────────────────────────────────

def list_view(root: Path) -> dict:
    foot = paths.Footprint(root)
    bundled = policy.bundled_raw()
    project = _project_raw(foot)
    rows = []
    b_tables, p_tables = _tables(bundled.get("prices", {})), _tables(project.get("prices", {}))
    providers = sorted(set(b_tables) | set(p_tables))
    for prov in providers:
        b_rows = b_tables.get(prov, {})
        p_rows = p_tables.get(prov, {})
        for model in sorted(set(b_rows) | set(p_rows)):
            in_b, in_p = model in b_rows, model in p_rows
            win = p_rows.get(model) if in_p else b_rows.get(model)
            rows.append({
                "provider": prov, "model": model,
                "input": win.get("input", 0.0), "output": win.get("output", 0.0),
                "cache_read": win.get("cache_read", 0.0),
                "origin": ("project" if in_p and not in_b
                           else "bundled" if in_b and not in_p else "both"),
                "wins": "project" if in_p else "bundled",
            })
    aliases = []
    merged_prices = policy.load(foot.policy).get("prices", {})
    for prov in sorted(project.get("alias", {}) or {}):
        for model, entry in sorted((project["alias"][prov] or {}).items()):
            target = entry.get("to", "") if isinstance(entry, dict) else str(entry)
            tprov, _, tmodel = target.partition("/")
            aliases.append({"provider": prov, "model": model, "to": target,
                            "broken": tmodel not in merged_prices.get(tprov, {})})
    # [tools.<tool>] price_at routes (call-less receipt pricing, plan §4.5) — a
    # dangling route prices nothing (rung 1 refuses, never falls through): warn.
    from cage import receiptprice
    merged_pol = policy.load(foot.policy)
    dangling = receiptprice.dangling_routes(merged_pol)
    tool_routes = [{"tool": tool, "to": target, "broken": tool in dangling}
                   for tool, target in receiptprice.routes(merged_pol).items()]
    b_meta, p_meta = bundled.get("meta", {}), project.get("meta", {})
    return {"rows": rows, "aliases": aliases, "tool_routes": tool_routes,
            "bundled_meta": b_meta, "project_meta": p_meta,
            "project_policy": str(foot.policy) if foot.policy.exists() else None,
            # no project policy at all ⇒ the bundle applies directly — nothing stale
            "recommendation": sync_recommendation(p_meta) if foot.policy.exists() else None}


def render_list(d: dict) -> str:
    b, p = d["bundled_meta"], d["project_meta"]
    head = (f"prices — bundled {_meta_version(b)} (cage {b.get('cage_version', '?')})"
            f" · project {_meta_version(p)}"
            + (f" ({d['project_policy']})" if d["project_policy"] else " (no project policy.toml)"))
    table = render.table(
        ["provider", "model", "in $/M", "out $/M", "cache $/M", "origin", "wins"],
        [[r["provider"] or "—", r["model"], _fmt(r["input"]), _fmt(r["output"]),
          _fmt(r["cache_read"]), r["origin"], r["wins"]] for r in d["rows"]],
        rights={2, 3, 4})
    out = [head, "", table]
    if d["aliases"]:
        out += ["", "aliases (explicit routing — renders as an alias footnote, never exact):"]
        for a in d["aliases"]:
            broken = "   ⚠ broken — target row missing" if a["broken"] else ""
            out.append(f"  {_key(a['provider'], a['model'])} → {a['to']}{broken}")
    if d.get("tool_routes"):
        out += ["", "tool routes ([tools.<tool>] price_at — prices call-less token receipts):"]
        for t in d["tool_routes"]:
            broken = ("   ⚠ dangling — no price row resolves; the tool's receipts stay UNPRICED"
                      if t["broken"] else "")
            out.append(f"  {t['tool']} → {t['to']}{broken}")
    if d["recommendation"]:
        out += ["", f"· {d['recommendation']}"]
    return "\n".join(out)


# ── unpriced ─────────────────────────────────────────────────────────────────

def fix_line(provider: str, model: str) -> str:
    """The ONE runnable fix line for an unpriced (provider, model) — printed by
    `cage prices unpriced` and the report's `--usd` ⚠ block (one wording, one
    home; the fix-hint contract: always copy-paste runnable)."""
    if provider:
        return (f"cage prices set {provider} '{model}' --input <IN> --output <OUT>"
                f"   # per-MTok USD from the vendor's pricing page")
    return (f"cage prices alias - '{model}' --to <provider>/<model>"
            f"   # route the router pseudo-model explicitly")


def unpriced_view(root: Path, pol: dict, since: str | None = None) -> dict:
    groups: dict[tuple[str, str], dict] = {}
    for c in ledger.calls(root, since=since):
        _, match, _ = prices.call_usd_match(pol, c)
        if match != "none":
            continue
        k = (c.get("provider", ""), c.get("model", ""))
        g = groups.setdefault(k, {"calls": 0, "tokens": 0})
        g["calls"] += 1
        g["tokens"] += int(c.get("tokens_in", 0)) + int(c.get("tokens_out", 0))
    items = []
    for (prov, model), g in sorted(groups.items()):
        items.append({"provider": prov, "model": model, **g,
                      "fix": fix_line(prov, model)})
    return {"unpriced": items,
            "total_calls": sum(i["calls"] for i in items),
            "total_tokens": sum(i["tokens"] for i in items)}


def render_unpriced(d: dict) -> str:
    if not d["unpriced"]:
        return "✔ every recorded call prices — nothing is billing $0."
    out = []
    for i in d["unpriced"]:
        out.append(f"  {_key(i['provider'], i['model'])}   {i['calls']} calls   "
                   f"{render.tok(i['tokens'])} tokens")
        out.append(f"    fix: {i['fix']}")
    out.append("")
    out.append(f"⚠ {d['total_calls']} calls ({render.tok(d['total_tokens'])} tokens) "
               "billing $0 — totals understated until priced.")
    out.append("cage never fetches prices (no network) — check the vendor's pricing "
               "page, fill in the line, run it. `cage query unpriced` explains.")
    return "\n".join(out)


# ── set / alias ──────────────────────────────────────────────────────────────

def _fmt_row(row: dict | None) -> str:
    if not row:
        return "(none)"
    return (f"input={_fmt(row.get('input', 0.0))} output={_fmt(row.get('output', 0.0))} "
            f"cache_read={_fmt(row.get('cache_read', 0.0))}")

_REPRICE_NOTE = ("derived views re-price immediately — the ledger is never rewritten. "
                 "(Self-costed rows and receipts keep their stored figures.)")


def _stamp_meta_on_create(root: Path, res: dict) -> None:
    """A freshly-created project policy derives from the installed bundle, so stamp
    the bundled ``[meta]`` on it (exactly what a `cage setup` copy would carry) —
    the sync recommendation then measures real staleness, not a missing stamp."""
    if res.get("mode") == "created":
        meta = policy.bundled_raw().get("meta", {})
        if meta:
            pricestoml.update_meta(root, dict(meta))


def set_price(root: Path, args) -> str:
    if not args.provider or not args.model:
        raise CageError("usage: cage prices set <provider> <model> --input <usd/Mtok> "
                        "--output <usd/Mtok> [--cache-read <usd/Mtok>]")
    if args.input is None or args.output is None:
        raise CageError("cage prices set needs both --input and --output (USD per MTok)")
    if args.input < 0 or args.output < 0 or (args.cache_read or 0) < 0:
        raise CageError("prices are USD per million tokens — negative rates are invalid")
    defaulted = args.cache_read is None
    cache_read = round(args.input * 0.1, 6) if defaulted else args.cache_read
    if cache_read > args.input:
        raise CageError(f"cache_read ({_fmt(cache_read)}) must not exceed input "
                        f"({_fmt(args.input)}) — a cache read is a discounted input")
    row = {"input": float(args.input), "output": float(args.output),
           "cache_read": float(cache_read)}
    res = pricestoml.set_price(root, args.provider, args.model, row)
    _stamp_meta_on_create(root, res)
    hdr = pricestoml.table_header("prices", args.provider, args.model)
    lines = []
    if res["mode"] == "unchanged":
        lines.append(f"· {hdr} already set — no change ({_fmt_row(res['after'])})")
    else:
        where = {"in-place": "updated in place", "block": "written to the cage-managed block",
                 "created": "written to a new project policy"}.get(res["mode"], res["mode"])
        lines.append(f"✔ {hdr} {where} — {res['path']}")
        lines.append(f"  before: {_fmt_row(res['before'])}")
        lines.append(f"  after:  {_fmt_row(res['after'])}")
    if defaulted:
        lines.append(f"  cache_read defaulted to 0.1× input ({_fmt(cache_read)}) — "
                     "override with --cache-read")
    lines.append(f"  {_REPRICE_NOTE}")
    return "\n".join(lines)


def set_alias(root: Path, pol: dict, args) -> str:
    if not args.provider or not args.model:
        raise CageError("usage: cage prices alias <provider|-> <model> --to <provider>/<model>")
    if not args.to or "/" not in args.to:
        raise CageError("--to must name a price row as <provider>/<model> "
                        "(e.g. anthropic/claude-sonnet-4-6)")
    provider = "" if args.provider == "-" else args.provider
    tprov, _, tmodel = args.to.partition("/")
    if tmodel not in pol.get("prices", {}).get(tprov, {}):
        raise CageError(f"alias target {args.to} has no exact price row — aliases route "
                        f"to a real row, never to another guess (`cage prices set "
                        f"{tprov} '{tmodel}' …` first)")
    res = pricestoml.set_alias(root, provider, args.model, args.to)
    _stamp_meta_on_create(root, res)
    hdr = pricestoml.table_header("alias", provider, args.model)
    if res["mode"] == "unchanged":
        return f"· {hdr} already routes to {args.to} — no change"
    return (f"✔ {_key(provider, args.model)} → {args.to} — {res['path']}\n"
            f"  renders as an alias footnote (approximate routing), never exact.\n"
            f"  {_REPRICE_NOTE}")


# Same token rule as task labels (`clicmds._LABEL` — a module import here would be
# circular): one short identifier, never a path or free text.
_TOOL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")


def route_tool(root: Path, pol: dict, args) -> str:
    """`cage prices route-tool <tool> --to <provider>/<model> | --remove` — the
    managed writer for the rung-1 receipt-pricing route (plan §4.5).

    Unlike `alias` (which refuses a target with no exact row), a dangling target
    is **written with a warning**: set-route-then-add-price must work, and doctor/
    `prices list` keep flagging the dangling state until the row exists."""
    tool = args.provider  # the verb's first free positional carries the tool name
    if not tool:
        raise CageError("usage: cage prices route-tool <tool> --to <provider>/<model> "
                        "(or --remove)")
    if not _TOOL.match(tool):
        raise CageError("tool must be one short token (letters/digits/._-, ≤32 chars) "
                        "— the receipt `tool` field, never a path or free text")
    hdr = pricestoml.table_header("tools", tool)
    if getattr(args, "remove", False):
        res = pricestoml.remove_tool_route(root, tool)
        if res["mode"] == "absent":
            return f"· {hdr} has no route — nothing to remove"
        was = (res["before"] or {}).get("price_at", "?")
        return (f"✔ {hdr} removed — {res['path']} (was {was})\n"
                f"  its call-less receipts fall back to the task model, else UNPRICED.\n"
                f"  {_REPRICE_NOTE}")
    if not args.to or "/" not in args.to:
        raise CageError("--to must name a price row as <provider>/<model> "
                        "(e.g. anthropic/claude-sonnet-4-6)")
    tprov, _, tmodel = args.to.partition("/")
    if not tprov or not tmodel:
        raise CageError("--to must name a price row as <provider>/<model> "
                        "(e.g. anthropic/claude-sonnet-4-6)")
    _, match, key = policy.price_match(pol, tprov, tmodel)
    res = pricestoml.set_tool_route(root, tool, args.to)
    _stamp_meta_on_create(root, res)
    lines = []
    if res["mode"] == "unchanged":
        lines.append(f"· {hdr} already routes to {args.to} — no change")
    else:
        where = {"in-place": "updated in place", "block": "written to the cage-managed block",
                 "created": "written to a new project policy"}.get(res["mode"], res["mode"])
        lines.append(f"✔ {hdr} {where} — {res['path']}")
        lines.append(f"  before: {(res['before'] or {}).get('price_at') or '—'}")
        lines.append(f"  after:  price_at = \"{args.to}\"")
        lines.append("  call-less token receipts from this tool now price via rung 1 "
                     "(`cage query receipt-pricing`).")
    if match == "none":
        lines.append(f"  ⚠ {args.to} resolves no price row — the route is dangling and "
                     f"the tool's receipts stay UNPRICED until you run `cage prices set "
                     f"{tprov} '{tmodel}' …` (doctor and `prices list` keep flagging it)")
    elif match != "exact":
        lines.append(f"  ≈ target resolves by {match} via {key} — priced at that row")
    lines.append(f"  {_REPRICE_NOTE}")
    return "\n".join(lines)


# ── sync ─────────────────────────────────────────────────────────────────────

def sync_view(root: Path) -> dict:
    foot = paths.Footprint(root)
    bundled = policy.bundled_raw()
    project = _project_raw(foot)
    text = foot.policy.read_text(encoding="utf-8") if foot.policy.exists() else ""
    owned = _custom_headers(text)
    in_sync, customized, drift, bundled_only, project_only = [], [], [], [], []
    b_tables, p_tables = _tables(bundled.get("prices", {})), _tables(project.get("prices", {}))
    for prov in sorted(b_tables):
        for model in sorted(b_tables[prov]):
            b_row = b_tables[prov][model]
            p_row = p_tables.get(prov, {}).get(model)
            key = _key(prov, model)
            if p_row is None:
                bundled_only.append(key)
            elif p_row == b_row:
                in_sync.append(key)
            elif ("prices", prov, model) in owned:
                customized.append({"key": key, "project": p_row, "bundled": b_row})
            else:
                drift.append({"key": key, "provider": prov, "model": model,
                              "project": p_row, "bundled": b_row})
    for prov in sorted(p_tables):
        for model in sorted(p_tables[prov]):
            if model not in b_tables.get(prov, {}):
                project_only.append(_key(prov, model))
    return {"bundled_meta": bundled.get("meta", {}), "project_meta": project.get("meta", {}),
            "in_sync": in_sync, "customized": customized, "drift": drift,
            "bundled_only": bundled_only, "project_only": project_only,
            # no project policy at all ⇒ the bundle applies directly — nothing stale
            "recommendation": (sync_recommendation(project.get("meta", {}))
                               if foot.policy.exists() else None)}


def sync_apply(root: Path, d: dict, yes: list[str]) -> list[str]:
    """--update: restamp [meta] from the bundle and apply bundled values to the
    drift rows the user confirmed (`--yes provider/model`, `--yes all`)."""
    out = []
    take_all = "all" in yes
    wanted = {y for y in yes if y != "all"}
    applied = set()
    for item in d["drift"]:
        if take_all or item["key"] in wanted or f"{item['provider']}/{item['model']}" in wanted:
            pricestoml.set_price(root, item["provider"], item["model"], dict(item["bundled"]))
            applied.add(item["key"])
            out.append(f"✔ {item['key']} → bundled values applied ({_fmt_row(item['bundled'])})")
    missed = wanted - applied - {i["key"] for i in d["drift"]}
    for m in sorted(missed):
        out.append(f"· --yes {m}: not a drifted row — nothing to apply")
    meta = dict(d["bundled_meta"])
    if meta:
        pricestoml.update_meta(root, meta)
        out.append(f"✔ [meta] restamped to bundled {_meta_version(meta)}")
    skipped = [i["key"] for i in d["drift"] if i["key"] not in applied]
    if skipped:
        out.append("· left untouched (confirm each with --yes <provider>/<model>): "
                   + ", ".join(skipped))
    return out


def render_sync(d: dict, updated: list[str] | None = None) -> str:
    out = [f"prices sync — bundled {_meta_version(d['bundled_meta'])} vs project "
           f"{_meta_version(d['project_meta'])}", ""]
    if d["bundled_only"]:
        out.append(f"· {len(d['bundled_only'])} bundled rows with no project shadow — "
                   "already live via the merge, nothing to copy")
    if d["in_sync"]:
        out.append(f"· {len(d['in_sync'])} project rows equal to the bundle — in sync")
    for c in d["customized"]:
        out.append(f"· {c['key']} customized (cage-managed/marked) — preserved "
                   f"(project {_fmt_row(c['project'])})")
    for i in d["drift"]:
        out.append(f"⚠ {i['key']} differs from the installed bundle (provenance unknown "
                   f"— cage can't tell a deliberate edit from a stale copy):")
        out.append(f"    project: {_fmt_row(i['project'])}")
        out.append(f"    bundled: {_fmt_row(i['bundled'])}")
        out.append(f"    apply:   cage prices sync --update --yes {i['key']}")
    if d["project_only"]:
        out.append("· project-only rows (no bundled counterpart): " + ", ".join(d["project_only"]))
    if updated is not None:
        out += ["", *updated] if updated else ["", "· --update: nothing confirmed — dry-run only"]
    elif d["drift"] or d["recommendation"]:
        rec = d["recommendation"]
        out += ["", "dry-run (house pattern) — `--update` applies bundled values to rows "
                    "you confirm with --yes; customized rows are never clobbered."]
        if rec:
            out.append(f"· {rec}")
    if not any((d["drift"], d["customized"], d["project_only"], d["recommendation"])):
        out += ["", "✔ nothing to do — project prices match the installed bundle."]
    return "\n".join(out)


# ── dispatch ─────────────────────────────────────────────────────────────────

def run(args, root: Path, pol: dict) -> tuple[dict, str]:
    """(payload, text) per verb; the caller emits (envelope for --json)."""
    if args.action == "list":
        d = list_view(root)
        return d, render_list(d)
    if args.action == "unpriced":
        d = unpriced_view(root, pol, since=getattr(args, "since", None))
        return d, render_unpriced(d)
    if args.action == "set":
        text = set_price(root, args)
        return {"result": text.splitlines()}, text
    if args.action == "alias":
        text = set_alias(root, pol, args)
        return {"result": text.splitlines()}, text
    if args.action == "route-tool":
        text = route_tool(root, pol, args)
        return {"result": text.splitlines()}, text
    # sync
    d = sync_view(root)
    updated = sync_apply(root, d, list(args.yes or [])) if args.update else None
    return {**d, "updated": updated}, render_sync(d, updated)
