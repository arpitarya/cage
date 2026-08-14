"""`cage data serve` — a minimal local dashboard over the ledger ($0, stdlib http.server).

The ROI and Budget panels went with the money subsystem (USAGE-ONLY, ADR 0011); what
remains is usage, which is what cage now measures.
"""
from __future__ import annotations

import html
import http.server
from functools import partial
from pathlib import Path

from cage import paths, policy, report

_CSS = ("body{font:14px ui-monospace,SFMono-Regular,monospace;background:#0e1116;"
        "color:#e6edf3;max-width:900px;margin:2rem auto;padding:0 1rem}"
        "h1{font-size:18px}h2{font-size:13px;color:#8b949e;text-transform:uppercase}"
        "pre{background:#161b22;border:1px solid #30363d;border-radius:8px;"
        "padding:1rem;white-space:pre-wrap;overflow-x:auto}")


def _page(title: str, blocks: dict[str, str]) -> str:
    """A standalone, dependency-free HTML page (inline CSS, no CDN) — design §4.3."""
    body = "".join(f"<h2>{html.escape(t)}</h2><pre>{html.escape(b)}</pre>"
                   for t, b in blocks.items())
    return (f"<!doctype html><meta charset=utf-8><title>{html.escape(title)}</title>"
            f"<style>{_CSS}</style><h1>🦅 Cage — {html.escape(title)}</h1>{body}")


def write_html(path: str, title: str, blocks: dict[str, str]) -> None:
    """Write a standalone page to ``path``."""
    Path(path).write_text(_page(title, blocks), encoding="utf-8")


def dashboard_html(root: Path) -> str:
    pol = policy.load(paths.Footprint(root).policy)
    blocks = {
        "Usage by route": report.render_report(report.summarize(root, pol, "route")),
        "Usage by model": report.render_report(report.summarize(root, pol, "model")),
        "Usage by agent": report.render_report(report.summarize(root, pol, "agent")),
    }
    return _page("LLM usage ledger", blocks)


def serve(root: Path, port: int = 8788) -> int:
    out = paths.Footprint(root).out
    out.mkdir(parents=True, exist_ok=True)
    (out / "index.html").write_text(dashboard_html(root), encoding="utf-8")
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(out))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"cage: serving {out} at http://127.0.0.1:{port}/  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\ncage: stopped.")
    finally:
        httpd.server_close()
    return 0
