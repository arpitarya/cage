"""Load `.cage/cage.toml` (legacy `policy.toml` read as a fallback) — prices,
pipeline order, budgets, quality (plan §3.3). The resolved filename lives in one
place, `paths.Footprint.policy`; this module never hard-codes it for the project."""
from __future__ import annotations

import os
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover  (Python <3.11)
    tomllib = None

from cage import paths
from cage.constants import (MODEL_EFFORT_SUFFIXES, MODEL_FAMILY_MIN_SEGMENTS,
                            MODEL_ROUTE_PREFIXES)

DEFAULT_ORDER = ["graphify", "fux", "router", "compressor", "cache", "response-cache"]
_ZERO_PRICE = {"input": 0.0, "output": 0.0, "cache_read": 0.0}


# The bundled-seed filenames (the ONLY place these literals live — parallel to
# `Footprint.policy`/`Footprint.prices`, the project-side resolvers). Prices are split
# into `data/prices.toml`; everything else stays in `data/cage.toml` (prices-toml plan §3).
_BUNDLED_POLICY = "cage.toml"
_BUNDLED_PRICES = "prices.toml"


def _parse_bundled(name: str) -> dict:
    # is_file(), not exists(): bundled_data() is a Traversable (no .exists() in the
    # ABC) so the bundled data keeps loading when cage runs from cage.pyz.
    src = paths.bundled_data() / name
    if tomllib is None or not src.is_file():
        return {}
    with src.open("rb") as fh:
        return tomllib.load(fh)


def _bundled() -> dict:
    """The bundled default, reassembled from its two files: `data/cage.toml` (policy)
    + `data/prices.toml` (vendor facts). The merged shape is byte-identical to the
    pre-split single-file bundle — this is a *file* split, not a contract change, so
    every consumer of `policy.load` reads exactly the dict it read before.

    ``[meta] cage_version`` is derived here, never read from a file: the bundle ships
    no such key (a hand-maintained literal drifted eleven releases before this), so
    every caller of `bundled_raw()`/`load()` always sees the *running* package version
    — `cage prices list`'s header and a freshly scaffolded project's stamp both derive
    from this one point. A project's own stamp (once scaffolded) is history and is
    never rewritten (`initcmd.run`)."""
    base = _parse_bundled(_BUNDLED_POLICY)
    prices = _parse_bundled(_BUNDLED_PRICES)
    for section in _SECTIONS:
        if section in prices:
            _merge_section(base, prices, section)
    from cage import __version__  # deferred: avoid any import-order coupling
    base.setdefault("meta", {})["cage_version"] = __version__
    return base


# Sections whose values are per-provider tables of rows: merge one level deeper so
# a project `[prices.anthropic."x"]` row shadows that one key without wiping the
# provider's bundled siblings. (Shallow provider-level replace was the pre-0.19
# behavior — a partial project table silently dropped every bundled row for that
# provider. Nothing legitimate relied on it: removing a row only ever meant falling
# back to family/none, and `cage setup` copies carry the full table anyway.)
_TWO_LEVEL = ("prices", "credits", "alias", "billing")
_SECTIONS = ("prices", "tools", "budgets", "quality", "ledger",
             "capture", "debug", "credits", "alias", "meta", "cleanup", "wiring",
             "display", "sources", "authorship", "billing")

# The vendor-fact sections that live in `prices.toml` (prices-toml plan §2): the rate
# rows and the credit table. Everything else in `_SECTIONS` (routing decisions +
# tunables, incl. `[alias]`) stays in `cage.toml`. `[meta]` is neither — it splits
# per key: `prices_version`/`prices_date` follow the price file, the rest the policy
# file, so a mis-split can't silently stop the staleness nag firing (prices-toml
# plan §2.1 — archived; PLAN.md has no §2.1).
_PRICE_SECTIONS = ("prices", "credits")
_PRICE_META_KEYS = ("prices_version", "prices_date")

# `[billing]` is deliberately NOT a price section, and the distinction is the whole
# reason it is not spelled `[credits.<agent>]` (COPILOT-CREDITS §10):
#
#   · `[credits]` is a VENDOR rate card — per-provider/per-model `per_mtok` multipliers,
#     replaced wholesale by `cage prices sync`, so it lives in `prices.toml`.
#   · `[billing.<agent>] usd_per_credit` is YOUR plan's overage rate — a routing decision
#     about your own economics, hand-set and hand-preserved, so it lives in `cage.toml`.
#
# Filing the rate under `[credits.copilot]` would have put it in a section this loader
# reads from the *prices* file only, so a rate written into `cage.toml` (where the
# proposal put it, and where it belongs by the vendor-facts-move rule) would have been
# read back as absent in every project that has a prices.toml — a silent half-merge, and
# a silently-unpriced ledger. Vendor facts move, routing decisions stay.


def _merge_section(pol: dict, data: dict, section: str) -> None:
    """Merge one section of ``data`` onto ``pol`` in place — two-level deep for the
    per-provider row tables, a flat overlay otherwise. No-op when ``data`` lacks it."""
    if section not in data:
        return
    if section in _TWO_LEVEL:
        merged = dict(pol.get(section, {}))
        for prov, table in data[section].items():
            base = merged.get(prov)
            if isinstance(table, dict) and isinstance(base, dict):
                merged[prov] = {**base, **table}
            else:
                merged[prov] = table
        pol[section] = merged
    else:
        pol[section] = {**pol.get(section, {}), **data[section]}


def load(policy_path: Path | None = None) -> dict:
    """Project policy merged over the bundled default, returned as ONE merged dict —
    the same shape (and, for equal inputs, the same values) every consumer read before
    the price split. Non-price sections come from the policy file (``cage.toml``); the
    price sections (``[prices]``/``[credits]``/the price ``[meta]`` keys) come from the
    resolved *prices* file beside it (``prices.toml`` if present, else the policy file
    itself for a legacy in-``cage.toml`` project — `paths.resolve_prices_file`). Tolerant
    of missing files; a no-project load returns the bundled default unchanged."""
    pol = _bundled()
    if tomllib is None or policy_path is None:
        return pol
    pdata = load_project_raw(policy_path)                       # cage.toml (policy)
    prices_path = paths.resolve_prices_file(policy_path.parent, policy_path)
    xdata = load_project_raw(prices_path) if prices_path != policy_path else pdata
    for section in _SECTIONS:
        if section == "meta":
            continue  # split per key below, never wholesale
        _merge_section(pol, xdata if section in _PRICE_SECTIONS else pdata, section)
    # [meta] splits per key: the non-price counters (cage_version/policy_version) from
    # the policy file, the price counters (prices_version/prices_date) from the price
    # file. In a legacy project xdata is pdata, so all four come from cage.toml — same
    # as today. When prices.toml wins, its price keys override any stale ones in a
    # still-present legacy [meta] (price file merged last).
    meta = dict(pol.get("meta", {}))
    meta.update({k: v for k, v in pdata.get("meta", {}).items() if k not in _PRICE_META_KEYS})
    meta.update({k: v for k, v in xdata.get("meta", {}).items() if k in _PRICE_META_KEYS})
    if meta:
        pol["meta"] = meta
    return pol


def bundled_raw() -> dict:
    """The bundled policy alone (no project merge) — origin attribution for
    `cage prices list`/`sync`/`doctor`, which need to know which side a row
    came from; :func:`load` deliberately erases that."""
    return _bundled()


def load_project_raw(policy_path: Path | None) -> dict:
    """The project policy.toml alone, un-merged; ``{}`` when absent. Parse errors
    propagate — the caller chooses fail-open (capture path) vs CageError (CLI)."""
    if not policy_path or not policy_path.exists() or tomllib is None:
        return {}
    with policy_path.open("rb") as fh:
        return tomllib.load(fh)


def tool_order(pol: dict) -> list[str]:
    return list(pol.get("tools", {}).get("order") or DEFAULT_ORDER)


def _common_prefix_segments(a: list[str], b: list[str]) -> int:
    """Count of equal leading hyphen-segments shared by two split model ids."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def normalize_model(model: str) -> str:
    """Canonical form for family matching: strip a known router prefix
    (`copilot/claude-opus-4.6` → `claude-opus-4.6`), fold `.` to `-` (Copilot's
    dotted ids vs Anthropic's dashed rows), drop trailing effort-tier segments
    (`…-codex-high` → `…-codex` — vendors bill every tier at the same rate).
    The route-prefix list is closed: an unknown `<x>/` prefix stays as-is so an
    unrecognized router surfaces UNPRICED, never silently priced."""
    m = model
    for pre in MODEL_ROUTE_PREFIXES:
        if m.startswith(pre):
            m = m[len(pre):]
            break
    segs = m.replace(".", "-").split("-")
    while len(segs) > 1 and segs[-1] in MODEL_EFFORT_SUFFIXES:
        segs.pop()
    return "-".join(segs)


def _alias_target(pol: dict, provider: str, model: str) -> str | None:
    """The `[alias.<provider>."<model>"] to = "prov/model"` route, if configured."""
    entry = pol.get("alias", {}).get(provider, {}).get(model)
    if isinstance(entry, dict):
        entry = entry.get("to")
    return entry if isinstance(entry, str) and entry else None


def price_match(pol: dict, provider: str, model: str) -> tuple[dict, str, str | None]:
    """Resolve a price row *and how it matched*:
    ``("exact" | "alias" | "family" | "none")``.

    A raw exact key wins. Next an explicit ``[alias]`` route (router pseudo-models
    like ``copilot/auto``) — explicit routing beats every heuristic; a dangling
    alias (target row missing) is ``none``, an explicit-but-broken route must
    surface UNPRICED rather than fall through to a guess. Then the family
    fallback over :func:`normalize_model`-canonical ids: the same-provider row
    sharing the most leading segments (≥ ``MODEL_FAMILY_MIN_SEGMENTS``, so brand +
    tier must agree — an ``opus`` id never borrows a ``sonnet`` price). The longest
    shared prefix wins; ties break on the lexicographically smallest key, so the
    result is independent of dict-insertion order — deterministic and stable.
    Method law: a match through normalization renders ``family`` even when the
    canonical forms are identical — only a byte-equal key is ``exact``.

    Returns ``(row, match, matched_key)`` — ``matched_key`` is the winning price-row
    key (for ``alias``, the ``prov/model`` target string). Never raises; a totally
    unknown model is ``(zeros, "none", None)`` so the caller can flag it UNPRICED
    rather than bill $0.
    """
    rows = pol.get("prices", {}).get(provider, {})
    if model in rows:
        return rows[model], "exact", model
    target = _alias_target(pol, provider, model)
    if target is not None:
        tprov, _, tmodel = target.partition("/")
        trow = pol.get("prices", {}).get(tprov, {}).get(tmodel)
        if trow is not None:
            return trow, "alias", target
        return dict(_ZERO_PRICE), "none", None
    want = normalize_model(model).split("-")
    best_key, best_n = None, 0
    for key in rows:
        n = _common_prefix_segments(want, normalize_model(key).split("-"))
        if n < MODEL_FAMILY_MIN_SEGMENTS:
            continue
        if n > best_n or (n == best_n and (best_key is None or key < best_key)):
            best_key, best_n = key, n
    if best_key is not None:
        return rows[best_key], "family", best_key
    return dict(_ZERO_PRICE), "none", None


def price(pol: dict, provider: str, model: str) -> dict:
    """Per-million-token price row for a model, or zeros if unpriced.

    Thin wrapper over :func:`price_match` for callers that only need the row
    (matrix, ``input_cost_usd``). Exact-or-family; see ``price_match`` for the
    match-kind / matched-key signal that ``report`` and ``doctor`` surface."""
    return price_match(pol, provider, model)[0]


def budgets(pol: dict) -> dict:
    b = pol.get("budgets", {})
    return {"session_usd": b.get("session_usd"), "daily_usd": b.get("daily_usd"),
            "on_exceed": b.get("on_exceed", "warn")}


def _flag(env_name: str, pol: dict, section: str, key: str, default: bool) -> bool:
    """A boolean switch: env override (`0/false/no/off` vs `1/true/yes/on`) beats the
    ``[section] key`` policy value, which beats ``default``. Env is explicit config, not
    entropy, so `(ledger, policy, env) ⇒ tables` still holds."""
    env = os.environ.get(env_name)
    if env is not None:
        v = env.strip().lower()
        if v in ("0", "false", "no", "off"):
            return False
        if v in ("1", "true", "yes", "on"):
            return True
    return bool(pol.get(section, {}).get(key, default))


def python_launcher(pol: dict) -> bool:
    """Persisted wiring mode (docs/restricted-environments.md): shims + user-level
    wiring resolve cage through the interpreter only (`python3 -m cage` /
    `py -3 -m cage`), never probing or executing a `cage`/`cage.exe` binary — for
    endpoints where unknown exes are blocked. Policy ``[wiring] python_launcher``;
    default off (standard mode). Deliberately NOT env-overridable: `CAGE_RUN_PYTHON`
    is the *shim-runtime* no-rewire escape hatch, never a write-time mode switch —
    `cage setup`'s output must not depend on the caller's environment."""
    return bool(pol.get("wiring", {}).get("python_launcher", False))


def credit_rate(pol: dict, agent: str) -> float | None:
    """The configured `[billing.<agent>] usd_per_credit` — rung 1 of the credit pricing
    ladder (`cage/creditprice.py`), or ``None`` when unset.

    ``None`` is the shipped default and is **not** a zero: unset means the rung is
    skipped entirely and recorded credits render as a *count*, never as a dollar. A rate
    of exactly ``0.0`` is a different, legitimate statement (a plan whose credits cost
    nothing marginally) and does price, at $0.0000 — the same absent-vs-recorded-zero
    discipline the `credits` field itself carries.

    Never env-overridable: a billing rate is durable configuration, and a report whose
    dollars depend on the caller's environment would break the determinism law's
    `(ledger, policy) ⇒ tables` reading for the one number people quote."""
    v = pol.get("billing", {}).get(agent, {})
    if not isinstance(v, dict):
        return None
    rate = v.get("usd_per_credit")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)):
        return None
    return float(rate)


def capture_enabled(pol: dict) -> bool:
    """Whether hook-driven `cage import` actually runs — the consumer's on/off switch
    for auto-metering, without unwiring any hooks. Env `CAGE_CAPTURE` overrides policy
    `[capture] enabled`; default on."""
    return _flag("CAGE_CAPTURE", pol, "capture", "enabled", True)


def capture_on_read_enabled(pol: dict) -> bool:
    """Whether a read (report / insights / MCP read tools) lazily sweeps the log registry
    before answering — the capture-on-read primary path (capture-architecture Phase 1).
    Env `CAGE_CAPTURE_ON_READ` (0/1) overrides policy `[capture] on_read`; default **on**.
    A *separate* switch from `capture_enabled`: `CAGE_CAPTURE=0` pauses ALL capture
    (explicit `cage import` included), while this pauses only the read-triggered sweep —
    the knob the determinism/golden suite pins off so a read never mutates the ledger
    under a fixed-ledger test. `--no-import` is the per-invocation equivalent."""
    return _flag("CAGE_CAPTURE_ON_READ", pol, "capture", "on_read", True)


def read_throttle_secs(pol: dict) -> int:
    """Seconds within which a second read won't re-sweep (capture-on-read throttle,
    keyed on the `_last_import` cursor — no new state file). Policy `[capture]
    read_throttle_secs` wins; `constants.CAPTURE_ON_READ_THROTTLE_SECS` covers an unset
    key (the DEFAULT_CONFIDENCE policy-preferred pattern); `0` disables the throttle."""
    from cage.constants import CAPTURE_ON_READ_THROTTLE_SECS
    try:
        return int(pol.get("capture", {}).get("read_throttle_secs",
                                              CAPTURE_ON_READ_THROTTLE_SECS))
    except (TypeError, ValueError):
        return CAPTURE_ON_READ_THROTTLE_SECS


def debug_enabled(pol: dict) -> bool:
    """Whether the capture path writes its metadata-only debug log + hook heartbeat
    (`cage/debuglog.py`). Env `CAGE_DEBUG` overrides policy `[debug] enabled`; default
    **off** — observability is opt-in, never on by default ($0, no file written)."""
    return _flag("CAGE_DEBUG", pol, "debug", "enabled", False)


def task_correlation_enabled(pol: dict) -> bool:
    """Whether the best-effort `task` backfill (plan §4 / Phase 4) runs — correlating an
    import against `tasks.jsonl` by session/time window. Default **off**: it ships
    disabled until validated against real correlated data (handoff §3), and its output is
    always its own `method`/confidence-tagged, never ground truth. Env
    `CAGE_TASK_CORRELATION` overrides policy `[capture] task_correlation`."""
    return _flag("CAGE_TASK_CORRELATION", pol, "capture", "task_correlation", False)


def cleanup_enabled(pol: dict) -> bool:
    """Whether the **automatic** state-dir sweep (`cleanup.maybe_run`, piggybacked on
    import) may run at all. Env `CAGE_CLEANUP` overrides policy `[cleanup] enabled`;
    default on. `enabled=false` means the auto path does nothing — no reminder — but
    is deliberately NOT consulted by a manually-typed `cage data cleanup` /
    `--apply`: an explicit command is always honored (the safer of the two readings —
    see `cleanup.py`'s module docstring). Cleanup only ever touches the closed
    state/ allowlist — never the ledger or policy — and since v0.37 the auto path
    never deletes anything either way; see `cleanup_warn`."""
    return _flag("CAGE_CLEANUP", pol, "cleanup", "enabled", True)


def cleanup_warn(pol: dict) -> bool:
    """Whether the auto sweep prints its stderr reminder when `cleanup_enabled` is
    true (it never deletes — `cage data cleanup --apply` is the only path that does).
    Env `CAGE_CLEANUP_WARN` overrides policy `[cleanup] warn`; default on."""
    return _flag("CAGE_CLEANUP_WARN", pol, "cleanup", "warn", True)


def cleanup_days(pol: dict) -> int:
    """Retention window for the cleanable state/ classes. Policy `[cleanup] days`
    wins; `constants.CLEANUP_DEFAULT_DAYS` covers an unset key (the
    DEFAULT_CONFIDENCE policy-preferred pattern)."""
    from cage.constants import CLEANUP_DEFAULT_DAYS
    try:
        return int(pol.get("cleanup", {}).get("days", CLEANUP_DEFAULT_DAYS))
    except (TypeError, ValueError):
        return CLEANUP_DEFAULT_DAYS


def prices_stale_days(pol: dict) -> int:
    """Age threshold (days) past which the bundled prices count as stale
    (`cage/freshness.py`). Policy `[prices] stale_days` wins;
    `constants.PRICES_STALE_DAYS` covers an unset key (the DEFAULT_CONFIDENCE
    policy-preferred pattern). `0` disables the age signal — documented opt-out."""
    from cage.constants import PRICES_STALE_DAYS
    v = pol.get("prices", {}).get("stale_days", PRICES_STALE_DAYS)
    try:
        return int(v)
    except (TypeError, ValueError):
        return PRICES_STALE_DAYS


def display_usd(pol: dict) -> bool:
    """Whether `report`/`matrix`/the bare overview render dollar columns by default
    (plan Phase 2.5): tokens are the measurement, dollars an interpretation you ask
    for. Precedence: the per-invocation `--usd` flag (handled at the CLI) > env
    `CAGE_USD` > policy `[display] usd` > off. Display-only — pricing always
    computes underneath (budget guards, UNPRICED detection), and money-native
    views (budget/roi/verdict/compare/estimate) never consult this."""
    return _flag("CAGE_USD", pol, "display", "usd", False)


def import_stale_hours(pol: dict) -> int:
    """Age threshold (hours) past which the report footer's `last import: N ago`
    advice line renders (plan Phase 1.6) — it's advice, not a banner. Policy
    `[capture] import_stale_hours` wins; `constants.IMPORT_STALE_HOURS` covers an
    unset key (the DEFAULT_CONFIDENCE policy-preferred pattern). `0` restores the
    always-on line (documented opt-out of the gate)."""
    from cage.constants import IMPORT_STALE_HOURS
    try:
        return int(pol.get("capture", {}).get("import_stale_hours", IMPORT_STALE_HOURS))
    except (TypeError, ValueError):
        return IMPORT_STALE_HOURS


def authorship_capture(pol: dict) -> bool:
    """Whether the import sweep runs the **authorship pass** at all — reading each
    Claude transcript for the text of its proposed edits and matching it, transiently,
    against the added lines of the commits those edits fall inside (v2 P1).

    This is the one capture path that reads a repository's *diffs*, which is the widest
    PII surface cage has (plan §3.5 justifies repo-relative file paths; the line bodies
    themselves never persist). So it gets its own switch, separate from
    `capture_enabled`: someone can meter their spend and still decline to have cage
    look at their code. Off ⇒ no provenance row is ever written, every commit reads
    `unknown` by absence, and not one token or cost number moves.

    Env `CAGE_AUTHORSHIP` overrides policy `[authorship] capture`; default on."""
    return _flag("CAGE_AUTHORSHIP", pol, "authorship", "capture", True)


def authorship_estimate_hours(pol: dict) -> bool:
    """Whether the commit views may render an **estimated** human-hours figure
    (agent-vs-human v2 §4). The estimator is `wall-clock − agent turn-span`, floored
    at 0 — an inference, always shown with `~` and with its method named in the view's
    own footnote, never a measurement and never multiplied by a rate.

    This is the kill-switch the v1 removal bought: `false` and the column renders
    `— not recorded` unless a human attested it with `cage task time`. Env
    `CAGE_AUTHORSHIP_ESTIMATE` overrides policy `[authorship] estimate_hours`;
    default on (`constants.AUTHORSHIP_ESTIMATE_HOURS`)."""
    from cage.constants import AUTHORSHIP_ESTIMATE_HOURS
    return _flag("CAGE_AUTHORSHIP_ESTIMATE", pol, "authorship", "estimate_hours",
                 AUTHORSHIP_ESTIMATE_HOURS)


def authorship_max_est_gap(pol: dict) -> str:
    """The commit gap past which the hours estimate is **refused** rather than printed
    (`—`, with the reason named). Beyond it the wall clock has stopped describing the
    work — an overnight or weekend gap would read as hours at the keyboard — and fog is
    not rendered. A `--since`-shaped window string (`4h` / `2d`); policy
    `[authorship] max_est_gap` wins, `constants.AUTHORSHIP_MAX_EST_GAP` covers an
    unset key (the DEFAULT_CONFIDENCE policy-preferred pattern). An unparseable value
    falls back to the constant rather than disabling the guard — a malformed cap must
    never widen it."""
    from cage import ledger
    from cage.constants import AUTHORSHIP_MAX_EST_GAP
    v = pol.get("authorship", {}).get("max_est_gap", AUTHORSHIP_MAX_EST_GAP)
    v = str(v).strip() if v is not None else ""
    return v if ledger.valid_since(v) and v else AUTHORSHIP_MAX_EST_GAP


def import_before_export(pol: dict) -> bool:
    """Whether `cage data export` runs the all-agent import sweep before bundling, so a
    capture-only machine (hooks never fire under a VS Code extension) still ships a
    complete bundle. Policy `[capture] import_before_export`; the `--no-import`
    flag wins per invocation, and `CAGE_CAPTURE=0` / `[capture] enabled=false`
    already skip the sweep inside `importcmd.run` (precedence: flag > env > policy)."""
    return bool(pol.get("capture", {}).get("import_before_export", True))


def default_toml() -> str:
    """The `cage.toml` `cage setup` writes — a copy of the bundled default (policy only;
    vendor prices live in `prices.toml`, see :func:`default_prices_toml`)."""
    src = paths.bundled_data() / _BUNDLED_POLICY
    return src.read_text(encoding="utf-8")


def default_prices_toml() -> str:
    """The `prices.toml` `cage setup` writes — a copy of the bundled price table
    (the model rate rows, `[credits]`, and the price `[meta]` counters)."""
    src = paths.bundled_data() / _BUNDLED_PRICES
    return src.read_text(encoding="utf-8")
