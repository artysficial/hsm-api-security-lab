"""Tiny static-dashboard toolkit: one self-contained HTML file, no JavaScript libraries.

Charts are inline SVG generated here, the page follows the system light/dark setting, and the
look is shared by every project in the Arunika Bank case study. Copy this file into a repo and
build pages with `page(...)` and the helpers below.
"""

from __future__ import annotations

import html
import math
from datetime import datetime, timezone

PORTFOLIO = "https://artysficial.github.io/"

# the case study: every project is one lens on the same (fictional) programme
CASE_STUDY = [
    ("Consultant", "IT maturity assessment", "it-maturity-assessment"),
    ("Business Analyst", "Requirements traceability", "requirements-traceability"),
    ("Project Manager", "Project health", "project-health-dashboard"),
    ("SDET", "HSM API security", "hsm-api-security-lab"),
    ("SAP", "Procure-to-pay analytics", "sap-p2p-analytics"),
    ("IT Auditor", "ITGC audit analytics", "itgc-audit-analytics"),
]

STATUS = {  # label -> css class
    "pass": "ok", "passed": "ok", "met": "ok", "on track": "ok", "low": "ok", "effective": "ok", "covered": "ok", "go": "ok",
    "warn": "warn", "at risk": "warn", "medium": "warn", "partially effective": "warn", "partial": "warn", "skipped": "warn", "blocked": "warn",
    "known defect": "bad", "fixed defect": "warn", "done": "ok", "verified": "ok", "complete": "ok", "in progress": "warn", "at risk": "warn", "on track": "ok", "strong": "ok", "moderate": "warn", "weak": "bad", "failing": "bad", "untested": "warn", "not covered": "bad", "not started": "neutral", "amber": "warn", "green": "ok", "red": "bad", "open": "bad", "closed": "ok", "mitigated": "ok",
    "fail": "bad", "failed": "bad", "not met": "bad", "off track": "bad", "high": "bad", "critical": "bad", "ineffective": "bad", "gap": "bad", "no-go": "bad", "error": "bad",
}

PALETTE = ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--pink)", "var(--teal)", "var(--yellow)", "var(--red)"]

esc = lambda value: html.escape(str(value))


def pill(label: str) -> str:
    return f'<span class="pill {STATUS.get(str(label).lower(), "neutral")}">{esc(label)}</span>'


def kpis(items: list[tuple]) -> str:
    """items: (label, value, note) or (label, value, note, tone) with tone ok|warn|bad"""
    cards = []
    for item in items:
        label, value, note, *tone = item
        cards.append(
            f'<div class="kpi {tone[0] if tone else ""}"><div class="kpi-label">{esc(label)}</div>'
            f'<div class="kpi-value">{esc(value)}</div><div class="kpi-note">{esc(note)}</div></div>'
        )
    return f'<div class="kpis">{"".join(cards)}</div>'


def table(headers: list[str], rows: list[list], raw_columns: set[int] = frozenset()) -> str:
    """Cells in raw_columns are inserted as HTML (for pills/links); everything else is escaped."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell if i in raw_columns else esc(cell)}</td>" for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def bars(data: list[tuple[str, float]], unit: str = "", max_value: float | None = None, colors: list[str] | None = None) -> str:
    """Horizontal bar chart."""
    top = max_value or max((v for _, v in data), default=1) or 1
    rows = []
    for i, (label, value) in enumerate(data):
        width = max(0.5, 100 * value / top)
        color = (colors or PALETTE)[i % len(colors or PALETTE)]
        shown = f"{value:,.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"
        rows.append(
            f'<div class="bar-row"><div class="bar-label">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar" style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-value">{shown}{esc(unit)}</div></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'


def donut(parts: list[tuple[str, float, str]], center: str = "", caption: str = "") -> str:
    """parts: (label, value, css color). Inline SVG ring with a legend."""
    total = sum(v for _, v, _ in parts) or 1
    radius, circumference = 42, 2 * math.pi * 42
    offset, rings, legend = 0.0, [], []
    for label, value, color in parts:
        length = circumference * value / total
        rings.append(
            f'<circle r="{radius}" cx="60" cy="60" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" stroke-dashoffset="{-offset:.2f}" />'
        )
        offset += length
        legend.append(f'<li><i style="background:{color}"></i>{esc(label)} <b>{value:g}</b></li>')
    return (
        f'<div class="donut"><svg viewBox="0 0 120 120" role="img" aria-label="{esc(caption or center)}">'
        f'<circle r="{radius}" cx="60" cy="60" fill="none" stroke="var(--track)" stroke-width="14" />'
        f'<g transform="rotate(-90 60 60)">{"".join(rings)}</g>'
        f'<text x="60" y="64" text-anchor="middle" class="donut-center">{esc(center)}</text></svg>'
        f'<ul class="legend">{"".join(legend)}</ul></div>'
    )


def lines(series: list[tuple[str, list[float], str]], labels: list[str], height: int = 220, unit: str = "") -> str:
    """Line chart: series of (name, values, color) over shared x labels."""
    width, pad = 640, 36
    values = [v for _, vals, _ in series for v in vals if v is not None]
    top = max(values or [1]) * 1.1 or 1
    x = lambda i: pad + i * (width - 2 * pad) / max(1, len(labels) - 1)
    y = lambda v: height - pad - (v / top) * (height - 2 * pad)
    grid = "".join(
        f'<line x1="{pad}" x2="{width - pad}" y1="{y(top * f):.1f}" y2="{y(top * f):.1f}" class="grid" />'
        f'<text x="{pad - 6}" y="{y(top * f) + 4:.1f}" text-anchor="end" class="axis">{top * f:,.0f}{esc(unit)}</text>'
        for f in (0, 0.25, 0.5, 0.75)
    )
    step = max(1, len(labels) // 8)
    xlabels = "".join(
        f'<text x="{x(i):.1f}" y="{height - 10}" text-anchor="middle" class="axis">{esc(label)}</text>'
        for i, label in enumerate(labels) if i % step == 0 or i == len(labels) - 1
    )
    paths, legend = [], []
    for name, vals, color in series:
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        paths.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />')
        legend.append(f'<li><i style="background:{color}"></i>{esc(name)}</li>')
    return (
        f'<div class="chart"><svg viewBox="0 0 {width} {height}" role="img">{grid}{"".join(paths)}{xlabels}</svg>'
        f'<ul class="legend inline">{"".join(legend)}</ul></div>'
    )


def radar(axes: list[str], series: list[tuple[str, list[float], str]], max_value: float = 5) -> str:
    """Spider chart for maturity-style scores."""
    size, center, radius = 320, 160, 118
    n = len(axes)
    point = lambda i, v: (
        center + radius * (v / max_value) * math.sin(2 * math.pi * i / n),
        center - radius * (v / max_value) * math.cos(2 * math.pi * i / n),
    )
    rings = "".join(
        f'<polygon points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in (point(i, level) for i in range(n)))}" class="grid" fill="none" />'
        for level in range(1, int(max_value) + 1)
    )
    spokes = "".join(f'<line x1="{center}" y1="{center}" x2="{point(i, max_value)[0]:.1f}" y2="{point(i, max_value)[1]:.1f}" class="grid" />' for i in range(n))
    labels = "".join(
        f'<text x="{point(i, max_value * 1.2)[0]:.1f}" y="{point(i, max_value * 1.2)[1] + 4:.1f}" text-anchor="middle" class="axis">{esc(a)}</text>'
        for i, a in enumerate(axes)
    )
    shapes, legend = [], []
    for name, vals, color in series:
        pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in (point(i, v) for i, v in enumerate(vals)))
        shapes.append(f'<polygon points="{pts}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="2" />')
        legend.append(f'<li><i style="background:{color}"></i>{esc(name)}</li>')
    return (
        f'<div class="chart radar"><svg viewBox="-40 -10 {size + 80} {size + 20}" role="img">{rings}{spokes}{"".join(shapes)}{labels}</svg>'
        f'<ul class="legend inline">{"".join(legend)}</ul></div>'
    )


def section(title: str, body: str, intro: str = "") -> str:
    return f'<section class="card"><h2>{esc(title)}</h2>{f"<p class=intro>{esc(intro)}</p>" if intro else ""}{body}</section>'


def grid(*cards: str) -> str:
    return f'<div class="grid2">{"".join(cards)}</div>'


def page(*, title: str, eyebrow: str, summary: str, body: str, repo: str, verdict: tuple[str, str] | None = None) -> str:
    """verdict: (label, tone) shown as the headline status, e.g. ("Go", "ok")."""
    built = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    siblings = "".join(
        f'<a href="{PORTFOLIO}{slug}/" class="{"current" if slug == repo else ""}"><span>{esc(role)}</span>{esc(name)}</a>'
        for role, name, slug in CASE_STUDY
    )
    in_case_study = any(slug == repo for _, _, slug in CASE_STUDY)
    verdict_html = f'<div class="verdict {verdict[1]}">{esc(verdict[0])}</div>' if verdict else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)} · Rahmadani Tyas Ningrum</title>
<meta name="description" content="{esc(summary)}">
<style>{CSS}</style>
</head>
<body>
<header class="top"><a href="{PORTFOLIO}" class="brand">Rahmadani Tyas Ningrum</a><a href="https://github.com/artysficial/{repo}" class="src">Source on GitHub →</a></header>
<main>
<div class="hero">
  <p class="eyebrow">{esc(eyebrow)}</p>
  <h1>{esc(title)}</h1>
  <p class="summary">{esc(summary)}</p>
  {verdict_html}
  <p class="built">Generated {built} by the project's CI pipeline.</p>
</div>
{body}
{f'<section class="case"><h2>Arunika Bank case study</h2><p class="intro">One fictional payment-security programme, seen through six roles. Every dashboard uses the same programme, requirement IDs and systems.</p><nav>{siblings}</nav></section>' if in_case_study else ''}
</main>
<footer>Fictional data for portfolio purposes · <a href="{PORTFOLIO}">artysficial.github.io</a></footer>
</body>
</html>"""


CSS = """
:root{--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#6e6e73;--line:#d2d2d7;--track:#e8e8ed;
--blue:#0071e3;--green:#28a745;--orange:#f56300;--purple:#8e44ad;--pink:#e3006d;--teal:#0a9396;--yellow:#c99700;--red:#d70015;
--ok-bg:#e3f7e8;--ok:#1a7f37;--warn-bg:#fff4dc;--warn:#9a6700;--bad-bg:#ffe5e7;--bad:#c4001a;--neutral-bg:#ececf0;}
@media (prefers-color-scheme:dark){:root{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;--muted:#a1a1a6;--line:#38383a;--track:#2c2c2e;
--blue:#2997ff;--green:#30d158;--orange:#ff9f0a;--purple:#bf5af2;--pink:#ff375f;--teal:#40c8e0;--yellow:#ffd60a;--red:#ff453a;
--ok-bg:#0f2e1a;--ok:#30d158;--warn-bg:#33270a;--warn:#ffd60a;--bad-bg:#3a0e12;--bad:#ff6961;--neutral-bg:#2c2c2e;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:17px/1.47 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.top{position:sticky;top:0;z-index:2;display:flex;justify-content:space-between;align-items:center;padding:12px max(20px,calc(50% - 540px));background:color-mix(in srgb,var(--bg) 78%,transparent);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid var(--line);font-size:14px}
.brand{color:var(--text);font-weight:600}
main{max-width:1080px;margin:0 auto;padding:0 20px 64px}
.hero{text-align:center;padding:72px 0 40px}
.eyebrow{color:var(--orange);font-weight:600;font-size:15px;margin:0 0 8px}
h1{font-size:clamp(36px,6vw,64px);line-height:1.05;letter-spacing:-.02em;margin:0 0 16px;font-weight:700}
.summary{color:var(--muted);font-size:clamp(18px,2.2vw,22px);max-width:760px;margin:0 auto}
.built{color:var(--muted);font-size:13px;margin-top:20px}
.verdict{display:inline-block;margin-top:24px;padding:10px 22px;border-radius:980px;font-weight:600;font-size:19px}
.verdict.ok{background:var(--ok-bg);color:var(--ok)}.verdict.warn{background:var(--warn-bg);color:var(--warn)}.verdict.bad{background:var(--bad-bg);color:var(--bad)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:0 0 20px}
.kpi{background:var(--card);border-radius:20px;padding:22px}
.kpi-label{color:var(--muted);font-size:14px}.kpi-value{font-size:clamp(24px,2.4vw,34px);font-weight:700;letter-spacing:-.02em;margin:4px 0;white-space:nowrap}.kpi-note{color:var(--muted);font-size:13px}
.kpi.ok .kpi-value{color:var(--ok)}.kpi.warn .kpi-value{color:var(--warn)}.kpi.bad .kpi-value{color:var(--bad)}
.card{background:var(--card);border-radius:24px;padding:28px;margin:0 0 20px}
.card h2{margin:0 0 6px;font-size:24px;letter-spacing:-.01em}.intro{color:var(--muted);margin:0 0 18px;font-size:15px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px;margin:0 0 20px}.grid2 .card{margin:0}
@media (max-width:520px){.grid2{grid-template-columns:1fr}.card{padding:20px}}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:500;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
td{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
.pill{display:inline-block;padding:2px 10px;border-radius:980px;font-size:12px;font-weight:600;white-space:nowrap;background:var(--neutral-bg)}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.warn{background:var(--warn-bg);color:var(--warn)}.pill.bad{background:var(--bad-bg);color:var(--bad)}
.bars{display:grid;gap:10px}.bar-row{display:grid;grid-template-columns:minmax(110px,30%) 1fr auto;gap:12px;align-items:center;font-size:14px}
.bar-track{height:12px;background:var(--track);border-radius:6px;overflow:hidden}.bar{height:100%;border-radius:6px}.bar-value{font-variant-numeric:tabular-nums;color:var(--muted)}
.donut{display:flex;align-items:center;gap:24px;flex-wrap:wrap}.donut svg{width:170px;height:170px}.donut-center{font-size:20px;font-weight:700;fill:var(--text)}
.legend{list-style:none;padding:0;margin:0;font-size:14px;display:grid;gap:6px}.legend.inline{display:flex;flex-wrap:wrap;gap:16px;margin-top:8px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:middle}
.chart svg{width:100%;height:auto}.grid{stroke:var(--line);stroke-width:1}.axis{fill:var(--muted);font-size:11px}.radar svg{max-width:420px;display:block;margin:0 auto}
code{font:13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--track);padding:2px 6px;border-radius:6px}
.case{margin-top:48px;text-align:center}.case h2{font-size:28px;margin:0 0 6px}
.case nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:20px}
.case a{display:block;background:var(--card);border-radius:18px;padding:16px;color:var(--text);font-weight:600;font-size:15px;text-align:left}
.case a span{display:block;color:var(--muted);font-weight:500;font-size:12px;margin-bottom:4px}.case a.current{outline:2px solid var(--blue)}
footer{text-align:center;color:var(--muted);font-size:12px;padding:24px}
"""


def write(path: str, content: str) -> None:
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
