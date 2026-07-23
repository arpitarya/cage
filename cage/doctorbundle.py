"""`cage doctor --bundle` — one redacted diagnostics archive (roadmap P1).

Everything a capture bug-report needs, in one zip, under the same PII
discipline as the ledger: **counts-never-content**. The bundle carries doctor
output, the metadata-only debug log + the always-on capture breadcrumb
(`state/capture.log`, `cage/capturelog.py`) + hook heartbeats (if present), version +
platform, resolved footprint paths with per-shard *row counts*, policy
**provenance** (which file won and which cage env overrides are set — never a
prompt, never a diff, never a ledger row body), and the import cursor state.

Two error regimes, split the way the contract means them: a member that can't
be read is **fail-open** — listed under ``skipped`` in the manifest with the
reason, never aborting the bundle — while an unwritable *target* path is an
expected user-facing failure and raises ``CageError`` (the read/CLI boundary).

Deterministic where it can be: zip entries are stamped with a fixed epoch and
written in a fixed order, so the same inputs produce the same archive bytes
(doctor output itself may embed "N ago" ages — doctor is a health check, not a
derived-from-ledger view).
"""
from __future__ import annotations

import json
import os
import platform
import sys
import zipfile
from pathlib import Path

from cage import doctorcmd, ledger, pathprobe, paths, policy
from cage.errors import CageError

DEFAULT_NAME = "cage-doctor-bundle.zip"

# Every env override cage honors — recorded name=value when set (none carry
# secrets; values are paths/flags/rates the user themselves configured).
_CAGE_ENVS = ("CAGE_BASE", "CAGE_LEDGER", "CAGE_HOME", "CAGE_DEBUG", "CAGE_DEBUG_LOG",
              "CAGE_CAPTURE", "CAGE_HUMAN_RATE", "CAGE_NOTES_WRITE", "CAGE_PYTHON",
              "CLAUDE_CONFIG_DIR", "CODEX_HOME", "COPILOT_HOME", "KIRO_HOME",
              "KIRO_DATA_DIR", "CAGE_VSCODE_USER")

_EPOCH = (1980, 1, 1, 0, 0, 0)  # fixed zip timestamp — same inputs ⇒ same bytes


def _doctor_text(res: dict) -> str:
    """The same rendering `cage doctor` prints (clicmds.cmd_doctor), frozen to text."""
    glyph = {"ok": "✔", "warn": "·", "fail": "✗"}
    lines = [f"  {glyph[c['level']]} {c['name']:<12} {c['detail']}" for c in res["checks"]]
    return "\n".join(lines + ["", f"status: {res['status']}"]) + "\n"


def _version_text() -> str:
    from cage import __version__
    return (f"cage {__version__}\n"
            f"python {sys.version.split()[0]}\n"
            f"platform {platform.platform()}\n")


def _footprint_text(root: Path, active: Path, source: str) -> str:
    """Resolved paths + per-shard sizes and row *counts* — never a row body."""
    foot = paths.Footprint(active)
    lines = [f"cwd root: {root}", f"active sink: {source}", f"base: {foot.base}",
             f"ledger dir: {foot.ledger}", f"state dir: {foot.state}", "", "shards:"]
    for kind in ("calls", "receipts", "tasks"):
        for sh in foot.shards(kind):
            try:
                lines.append(f"  {sh.name}  {sh.stat().st_size} B  {len(ledger.read(sh))} row(s)")
            except OSError as e:
                lines.append(f"  {sh.name}  unreadable ({type(e).__name__})")
    if foot.provenance.exists():
        lines.append(f"  {foot.provenance.name}  {foot.provenance.stat().st_size} B  "
                     f"{len(ledger.read(foot.provenance))} row(s)")
    return "\n".join(lines) + "\n"


def _policy_provenance_text(active: Path) -> str:
    """Which policy file won + which env overrides are set — provenance, not contents."""
    foot = paths.Footprint(active)
    project = foot.policy
    lines = ["policy resolution (project merged over bundled default):",
             f"  bundled default: {paths.bundled_data() / 'policy.toml'}",
             f"  project policy:  {project} ({'present' if project.exists() else 'absent'})"]
    try:
        pol = policy.load(project)
        lines.append(f"  loads ok: {len(pol.get('prices', {}))} provider price table(s)")
    except Exception as e:  # noqa: BLE001 — a broken policy is a finding, not a crash
        lines.append(f"  loads FAILED: {type(e).__name__}: {e}")
    lines.append("")
    lines.append("cage env overrides set:")
    set_envs = [f"  {k}={os.environ[k]}" for k in _CAGE_ENVS if k in os.environ]
    lines.extend(set_envs or ["  (none)"])
    return "\n".join(lines) + "\n"


def _member_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _redact_home(data: bytes) -> bytes:
    """Replace the user's home prefix with ``~`` in every text member. Machine-local
    absolute paths are diagnostic signal, but the account *username* inside them is
    identity the bundle doesn't need — same spirit as the study bundle's
    no-hostname/no-username rule, without losing which file a path points at.
    Also covers the slug-escaped form Claude Code uses for project dir names
    (``/Users/me`` → ``-Users-me``), which embeds the same username."""
    home = str(Path.home())
    if not home or home == "/":
        return data
    data = data.replace(home.encode("utf-8"), b"~")
    slug = home.replace("/", "-").replace("\\", "-")
    return data.replace(slug.encode("utf-8"), b"~")


def run(root: Path, out: str | None = None) -> Path:
    """Write the bundle for the *active* sink resolved from ``root``; return its path.

    Raises ``CageError`` only for the unwritable-target case; every member is
    fail-open (skipped + reasoned in the manifest).
    """
    active = paths.resolve_root(root)
    source = paths.active_ledger_source(root)
    foot = paths.Footprint(active)
    out_path = Path(out) if out else Path(DEFAULT_NAME)

    members: list[tuple[str, bytes]] = []
    skipped: dict[str, str] = {}

    def add(name: str, build) -> None:
        try:
            data = build()
            data = data if isinstance(data, bytes) else data.encode("utf-8")
            members.append((name, _redact_home(data)))
        except Exception as e:  # noqa: BLE001 — fail-open per member, reasoned in manifest
            skipped[name] = f"{type(e).__name__}: {e}"

    res = None

    def doctor_res() -> dict:
        nonlocal res
        if res is None:
            res = doctorcmd.run(root)
        return res

    add("doctor.txt", lambda: _doctor_text(doctor_res()))
    add("doctor.json", lambda: json.dumps(doctor_res(), ensure_ascii=False, indent=2) + "\n")
    add("version.txt", _version_text)
    # The path probe: which log locations were checked, which missed, and why — the
    # exportable half of `cage doctor --paths` (read-only; home-redacted like all members).
    add("paths.txt", lambda: pathprobe.run(root))
    add("footprint.txt", lambda: _footprint_text(root, active, source))
    add("policy-provenance.txt", lambda: _policy_provenance_text(active))
    for name, path in (("state/debug.log", foot.debug_log),
                       ("state/capture.log", foot.capture_log),
                       ("state/hooks-seen.jsonl", foot.hooks_seen),
                       ("state/cursors.json", foot.cursors)):
        if path.exists():
            add(name, lambda p=path: _member_bytes(p))
        else:
            skipped[name] = "absent (nothing recorded — e.g. CAGE_DEBUG never on)"

    manifest = {"bundle": "cage-doctor-bundle", "included": [n for n, _ in members],
                "skipped": skipped}
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for name, data in [("manifest.json",
                                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n"),
                               *members]:
                zf.writestr(zipfile.ZipInfo(name, date_time=_EPOCH), data)
    except OSError as e:
        raise CageError(f"cannot write bundle to {out_path}: {e}") from e
    return out_path
