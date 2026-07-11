"""`cage study` — the fleet study: N laptops, two phases, one analyst (roadmap P5).

The workflow: laptops capture a week agent-only ("baseline"), then a week with a
plugin; each exports one bundle; the analyst imports them into a fresh ledger and
reads one report. This module holds all of it:

- **Recorded phases, not remembered dates.** `start <phase>` / `stop` append
  marker rows to `study.jsonl` (phase = one validated token, the `label` PII
  guard). Derive assigns each row to a phase by its own ``ts`` against the
  markers — deterministic, no clocks at derive time. Phases are resolved
  **per-machine against that machine's own markers** (both the row ``ts`` and
  the markers come from the same clock), so cross-machine clock skew cannot
  cross-assign a row. "Last marker wins forward in time": a repeated `start`
  simply switches phase; a `start` without `stop` extends to the end; rows
  before any marker are *unphased* — excluded from deltas, counted in coverage.
- **Phase intent vs observed stack.** A phase records what the week was *meant*
  to be (a plugin can be installed but unused); `cage compare`'s stack signature
  (§4.7) stays the within-phase truth of what actually ran.
- **The unit is the machine-day.** Capture-only fleets never close tasks, so
  per-task medians would be empty by construction; a study's question is "what
  does a week cost", and its natural sample is one machine's one day. Group
  totals per machine×phase are **measured** (recorded tokens, `prices.call_usd`
  repricing); the paired delta — each machine's own phase-B median daily minus
  its phase-A median daily, then the **median of those paired deltas** (controls
  between-machine variance) — is **`estimated`**: different weeks, different
  work mix, nothing randomized. Below `MIN_COMPARE_N` machines with both phases
  the delta refuses; coverage always renders (a laptop that went silent mid-week
  is the #1 study-killer, so gaps print *before* any number).
"""
from __future__ import annotations

import datetime as _dt
import json
import re
import statistics
import zipfile
from pathlib import Path

from cage import ids, ledger, machine, paths, prices, render, schema
from cage.constants import MIN_COMPARE_N
from cage.errors import CageError

PHASE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,31}\Z")  # the label PII guard
UNPHASED = ""  # rows outside any marker window — counted, never in a delta

CAVEAT = ("observed across different weeks with different work mixes — recorded "
          "phase intent, not a randomized experiment")


# ── markers ──────────────────────────────────────────────────────────────────

def start(root: Path, phase: str, ts: str | None = None) -> str:
    """Append a start marker (and enroll: the opaque machine id is created here).
    Returns the machine id. Raises `CageError` on a bad phase token (CLI boundary)."""
    if not PHASE_RE.match(phase or ""):
        raise CageError("phase must be one short token (letters/digits/._-, ≤32 chars)")
    mid = machine.ensure(root)
    ledger.append(paths.Footprint(root).study,
                  {"id": ids.new_id("s"), "ts": ts or schema._now(), "event": "start",
                   "phase": phase, "machine": mid})
    return mid


def stop(root: Path, ts: str | None = None) -> str:
    mid = machine.ensure(root)
    ledger.append(paths.Footprint(root).study,
                  {"id": ids.new_id("s"), "ts": ts or schema._now(), "event": "stop",
                   "phase": "", "machine": mid})
    return mid


def markers(root: Path) -> list[dict]:
    return ledger.read(paths.Footprint(root).study)


def _timelines(rows: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """Per machine: the marker timeline as sorted ``(ts, phase-or-"")`` switches."""
    per: dict[str, list[tuple[str, str]]] = {}
    for m in rows:
        phase = m.get("phase", "") if m.get("event") == "start" else UNPHASED
        per.setdefault(m.get("machine", ""), []).append((m.get("ts", ""), phase))
    return {mid: sorted(tl) for mid, tl in per.items()}


def phase_of(ts: str, timeline: list[tuple[str, str]]) -> str:
    """The phase in force at ``ts``: the last marker at-or-before it (start ⇒ its
    phase, stop ⇒ unphased); no marker yet ⇒ unphased."""
    current = UNPHASED
    for mts, phase in timeline:
        if mts <= ts:
            current = phase
        else:
            break
    return current


def phase_order(rows: list[dict]) -> list[str]:
    """Distinct phases in first-marker-time order across the whole study — the
    first two are the compared pair (deterministic; more phases render a note)."""
    seen: list[str] = []
    for m in sorted(rows, key=lambda r: r.get("ts", "")):
        p = m.get("phase", "")
        if m.get("event") == "start" and p and p not in seen:
            seen.append(p)
    return seen


# ── bundles (one-file collection) ────────────────────────────────────────────

def export_bundle(root: Path, out: str | None = None) -> Path:
    """One zip per machine: raw calls/receipts/tasks rows + study markers + a
    counts-only manifest. Counts-never-content holds by construction — ledger rows
    carry token counts, never bodies. Unwritable target ⇒ `CageError` (CLI boundary)."""
    mid = machine.machine_id(root)
    kinds = {k: ledger.read_kind(root, k) for k in ("calls", "receipts", "tasks")}
    marks = markers(root)
    ts_all = sorted(c.get("ts", "") for c in kinds["calls"] if c.get("ts"))
    manifest = {"bundle": "cage-study", "machine": mid,
                "cage": __import__("cage").__version__,
                "span": {"first": ts_all[0] if ts_all else "", "last": ts_all[-1] if ts_all else ""},
                "rows": {**{k: len(v) for k, v in kinds.items()}, "study": len(marks)}}
    out_path = Path(out) if out else Path(f"cage-study-{mid or 'unenrolled'}.zip")
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            epoch = (1980, 1, 1, 0, 0, 0)  # fixed stamp — same rows ⇒ same bytes
            zf.writestr(zipfile.ZipInfo("manifest.json", date_time=epoch),
                        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            for name, rows in ({**kinds, "study": marks}).items():
                zf.writestr(zipfile.ZipInfo(f"{name}.jsonl", date_time=epoch),
                            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    except OSError as e:
        raise CageError(f"cannot write study bundle to {out_path}: {e}") from e
    return out_path


def _row_key(kind: str, row: dict) -> str:
    """Merge identity. calls/receipts: the globally-unique ``id``. tasks + study
    markers: the whole row (tasks are append-only *updates* sharing one id — merging
    by id alone would drop a close; content identity keeps every update once)."""
    if kind in ("calls", "receipts"):
        return row.get("id", "")
    return json.dumps(row, sort_keys=True, ensure_ascii=False)


def import_bundles(root: Path, bundles: list[str]) -> list[str]:
    """Merge bundles into the ledger at ``root`` — idempotent (a bundle imported
    twice, or overlapping spans from one machine, dedupe on row identity). Returns
    one summary line per bundle. A missing/corrupt bundle raises `CageError`."""
    existing = {k: {_row_key(k, r) for r in ledger.read_kind(root, k)}
                for k in ("calls", "receipts", "tasks")}
    existing["study"] = {_row_key("study", r) for r in markers(root)}
    lines = []
    for b in bundles:
        p = Path(b)
        try:
            with zipfile.ZipFile(p) as zf:
                manifest = json.loads(zf.read("manifest.json"))
                added = {}
                for kind in ("calls", "receipts", "tasks", "study"):
                    rows = [json.loads(ln) for ln in
                            zf.read(f"{kind}.jsonl").decode("utf-8").splitlines() if ln]
                    n = 0
                    for row in rows:
                        key = _row_key(kind, row)
                        if not key or key in existing[kind]:
                            continue
                        ok = (ledger.append(paths.Footprint(root).study, row)
                              if kind == "study" else ledger.append_row(root, kind, row))
                        if ok:
                            existing[kind].add(key)
                            n += 1
                    added[kind] = n
        except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
            raise CageError(f"cannot import study bundle {p}: {e}") from e
        lines.append(f"✔ {p.name} (machine {manifest.get('machine') or '?'}): merged "
                     + " · ".join(f"{n} {k}" for k, n in added.items()))
    return lines


# ── the report: coverage first, then the paired number ───────────────────────

def _day(ts: str) -> str:
    return ts[:10]


def _days_between(first: str, last: str) -> list[str]:
    try:
        d0 = _dt.date.fromisoformat(first)
        d1 = _dt.date.fromisoformat(last)
    except ValueError:
        return []
    return [(d0 + _dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]


def _dist(vals: list[float]) -> dict:
    if len(vals) < 2:
        return {"median": vals[0], "q1": vals[0], "q3": vals[0]}
    q1, med, q3 = statistics.quantiles(vals, n=4, method="inclusive")
    return {"median": med, "q1": q1, "q3": q3}


def summarize(root: Path, pol: dict, agent_only: bool = False) -> dict:
    """Coverage + paired-by-machine phase deltas over the merged ledger.

    Unless ``agent_only``, a ``total_cost`` block (plan §4.10) totals the merged
    ledger as agent $ + human attention minutes × rate (attested beats derived per
    task, never summed; gap_ms rows survive the bundle round-trip verbatim)."""
    marks = markers(root)
    timelines = _timelines(marks)
    order = phase_order(marks)
    calls = ledger.calls(root)

    # assign each call to (machine, phase) per that machine's own markers
    per: dict[str, dict[str, dict[str, dict]]] = {}   # machine → phase → day → totals
    unphased = 0
    for c in calls:
        mid = c.get("machine", "")
        phase = phase_of(c.get("ts", ""), timelines.get(mid, []))
        if not mid or not phase:  # unenrolled machine, or a row outside every window
            unphased += 1
            continue
        day = _day(c.get("ts", ""))
        slot = per.setdefault(mid, {}).setdefault(phase, {}).setdefault(
            day, {"tokens": 0, "usd": 0.0, "calls": 0, "agents": set()})
        slot["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
        slot["usd"] += prices.call_usd(pol, c)
        slot["calls"] += 1
        slot["agents"].add(c.get("agent", ""))

    machines = []
    for mid in sorted(per):
        entry = {"machine": mid, "phases": {}}
        for phase in order:
            days = per[mid].get(phase, {})
            span = [m for m in timelines.get(mid, []) if m[1] == phase]
            stop_after = [m for m in timelines.get(mid, []) if m[0] > span[0][0]] if span else []
            expected = _days_between(_day(span[0][0]),
                                     _day(stop_after[0][0]) if stop_after else
                                     max(days) if days else _day(span[0][0])) if span else []
            gaps = [d for d in expected if d not in days]
            daily_tok = [float(days[d]["tokens"]) for d in sorted(days)]
            daily_usd = [round(days[d]["usd"], 6) for d in sorted(days)]
            entry["phases"][phase] = {
                "days": len(days), "gaps": gaps,
                "agents": sorted({a for d in days.values() for a in d["agents"]}),
                "tokens": _dist(daily_tok) if daily_tok else None,
                "usd": _dist(daily_usd) if daily_usd else None,
            }
        machines.append(entry)

    d = {"phases": order, "machines": machines, "unphased_calls": unphased,
         "min_n": MIN_COMPARE_N, "caveat": CAVEAT}
    if len(order) >= 2:
        a, b = order[0], order[1]
        d["pair"] = [a, b]
        paired = [m for m in machines
                  if m["phases"].get(a, {}).get("days") and m["phases"].get(b, {}).get("days")]
        d["paired_machines"] = len(paired)
        if len(paired) < MIN_COMPARE_N:
            d["delta"] = {"ok": False,
                          "reason": (f"insufficient machines with both phases "
                                     f"(n={len(paired)} < {MIN_COMPARE_N})")}
        else:
            dt = [m["phases"][b]["tokens"]["median"] - m["phases"][a]["tokens"]["median"]
                  for m in paired]
            du = [round(m["phases"][b]["usd"]["median"] - m["phases"][a]["usd"]["median"], 6)
                  for m in paired]
            d["delta"] = {"ok": True, "method": "estimated",
                          "d_tokens_per_day": statistics.median(dt),
                          "d_usd_per_day": round(statistics.median(du), 6),
                          "per_machine": {m["machine"]: round(x, 6)
                                          for m, x in zip(paired, du)}}
        # pooled per phase: every machine-day is one sample
        pooled = {}
        for phase in (a, b):
            days = [float(day["tokens"]) for mid in per.values()
                    for day in mid.get(phase, {}).values()]
            usd = [round(day["usd"], 6) for mid in per.values()
                   for day in mid.get(phase, {}).values()]
            pooled[phase] = ({"n_days": len(days), "tokens": _dist(sorted(days)),
                              "usd": _dist(sorted(usd))} if days else {"n_days": 0})
        d["pooled"] = pooled
    if not agent_only:
        from cage import attention  # local: keeps the module import graph light
        agent_usd = sum(prices.call_usd(pol, c) for c in calls)
        d["total_cost"] = attention.total_cost(agent_usd, attention.resolve(root, pol), pol)
    return d


def render_study(d: dict) -> str:
    if not d["phases"]:
        return ("Fleet study · no phase markers recorded yet\n\n"
                "enroll each machine with `cage study join <phase>` (or `cage study "
                "start <phase>`), capture, then `cage export --study` and import the "
                "bundles here.")
    out = ["Fleet study · phases: " + " → ".join(d["phases"])
           + (f" (comparing the first two)" if len(d["phases"]) > 2 else ""), "",
           "coverage (days with rows — gaps kill studies, so they print first):"]
    for m in d["machines"]:
        out.append(f"  machine {m['machine']}")
        for phase, p in m["phases"].items():
            if not p["days"]:
                out.append(f"    {phase:<12} MISSING — no rows in this phase")
                continue
            gap = f" · ⚠ gap days: {', '.join(p['gaps'])}" if p["gaps"] else ""
            out.append(f"    {phase:<12} {p['days']} day(s) · agents: "
                       f"{', '.join(p['agents']) or '—'}{gap}")
    if d["unphased_calls"]:
        out.append(f"  (+ {d['unphased_calls']} unphased call(s) — before enrollment "
                   "or unenrolled machines; excluded from deltas)")
    if "pair" not in d:
        out += ["", "only one phase recorded — nothing to pair yet."]
        if "total_cost" in d:  # plan §4.10 — suppressed by --agent-only
            from cage import attention
            out += ["", attention.render_total_cost(d["total_cost"])]
        return "\n".join(out)
    a, b = d["pair"]
    out.append("")
    delta = d["delta"]
    if not delta["ok"]:
        out.append(f"paired delta: {delta['reason']} — the command explains, it never numbers.")
    else:
        out.append(f"paired-by-machine delta ({b} − {a}, median of per-machine deltas, "
                   f"n={d['paired_machines']} machines):")
        out.append(f"  {delta['d_tokens_per_day']:+,.0f} tok/day · "
                   f"{render.signed_usd(delta['d_usd_per_day'])}/day per machine "
                   f"({delta['method']})")
        out.append(f"  ⚠ {d['caveat']}")
    out.append("")
    out.append("pooled machine-days per phase (measured):")
    for phase in (a, b):
        p = d["pooled"][phase]
        if not p["n_days"]:
            out.append(f"  {phase:<12} no machine-days")
            continue
        out.append(f"  {phase:<12} n={p['n_days']} days · median "
                   f"{p['tokens']['median']:,.0f} tok · {render.usd(p['usd']['median'])} "
                   f"(IQR {render.usd(p['usd']['q1'])}–{render.usd(p['usd']['q3'])})")
    if "total_cost" in d:  # plan §4.10 — suppressed by --agent-only
        from cage import attention
        out += ["", attention.render_total_cost(d["total_cost"])]
    return "\n".join(out)
