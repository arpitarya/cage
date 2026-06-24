"""`cage serve` — a minimal local dashboard over the ledger ($0, stdlib http.server)."""
from __future__ import annotations

import html
import http.server
from functools import partial
from pathlib import Path

from cage import budget, humanview, paths, policy, report, roi, trend

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
    """Write a standalone page to ``path`` (used by `--html` on human/matrix/trend)."""
    Path(path).write_text(_page(title, blocks), encoding="utf-8")


def dashboard_html(root: Path) -> str:
    pol = policy.load(paths.Footprint(root).policy)
    blocks = {
        "Spend by route": report.render_report(report.summarize(root, pol, "route")),
        "Spend by model": report.render_report(report.summarize(root, pol, "model")),
        "ROI by tool": roi.render_roi(roi.by_tool(root, pol)),
        "Agent vs human": humanview.render_human(humanview.rollup(root, pol)),
        "Savings trend": trend.render_trend(trend.series(root, pol)),
        "Budget": budget.render_budget(budget.check(root, pol)),
    }
    return _page("LLM cost ledger", blocks)


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
