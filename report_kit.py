"""Tiny static-dashboard toolkit: one self-contained HTML file, no JavaScript libraries.

Charts are inline SVG generated here and the look is shared by every project in the Arunika Bank
case study. Each page has a light/dark switch (shared with the portfolio site), chart tooltips,
searchable/sortable/filterable tables with CSV download, a plain-language executive summary and
glossary, and an Export PDF button backed by a print stylesheet. Copy this file into a repo and
build pages with `page(...)` and the helpers below.
"""

from __future__ import annotations

import html
import math
import re
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
    "known defect": "bad", "fixed defect": "warn", "done": "ok", "verified": "ok", "complete": "ok", "in progress": "warn", "strong": "ok", "moderate": "warn", "weak": "bad", "failing": "bad", "untested": "warn", "not covered": "bad", "not started": "neutral", "amber": "warn", "green": "ok", "red": "bad", "open": "bad", "closed": "ok", "mitigated": "ok",
    "fail": "bad", "failed": "bad", "not met": "bad", "off track": "bad", "high": "bad", "critical": "bad", "ineffective": "bad", "gap": "bad", "no-go": "bad", "error": "bad",
}
TONE_WORDS = {"ok": "good", "warn": "needs attention", "bad": "action needed"}

# plain-language definitions for board members and other non-specialist readers; a term is
# explained in the page's glossary (and on its KPI card) only when the page uses it
GLOSSARY = {
    "CPI": "Cost Performance Index: value of work completed per rupiah spent. Above 1.00 means under budget.",
    "SPI": "Schedule Performance Index: work completed versus work planned by now. Above 1.00 means ahead of schedule.",
    "Estimate at completion": "The forecast total cost of the programme when it finishes, at the current cost performance.",
    "VAC": "Variance at completion: budget minus forecast final cost. Negative means a forecast overspend.",
    "Planned value": "The budgeted cost of the work that should have been done by now.",
    "Earned value": "The budgeted cost of the work actually done so far.",
    "Actual cost": "What has actually been spent so far.",
    "RAG": "Red / Amber / Green status: green is on track, amber needs attention, red needs action.",
    "RAID": "The log of Risks, Assumptions, Issues and Decisions that the project manager maintains.",
    "Velocity": "Story points a delivery team completes per sprint; a measure of steady delivery pace.",
    "Story points": "A team's relative estimate of the effort in a user story.",
    "Quality gate": "A pass/fail checkpoint that must be met before work moves to the next stage.",
    "HSM": "Hardware Security Module: a tamper-resistant device that protects a bank's cryptographic keys and card PINs.",
    "OWASP": "Open Worldwide Application Security Project; its API Security Top 10 lists the most critical risks to APIs.",
    "Known defects": "Confirmed weaknesses already logged with a fix plan. Their tests reproduce the problem and are expected to fail until the fix lands.",
    "BRD": "Business Requirement Document: the agreed statement of what the business needs.",
    "Gherkin": "Given / When / Then wording for acceptance criteria that business and test teams can both read.",
    "Traceability": "The documented link from a business objective to the requirement, the user story and the test that proves it.",
    "ITGC": "IT general controls: the basic controls over who can access systems, how changes are made and how IT is run.",
    "Segregation of duties": "No single person can both make and approve the same sensitive action.",
    "COBIT 2019": "ISACA's framework for governing and managing enterprise IT.",
    "ISO 27001": "The international standard for running an information security management system.",
    "Full population": "Every record in the period was tested, rather than a sample, so no exception can be missed.",
    "SAP S/4HANA": "SAP's enterprise resource planning (ERP) system, used here for purchasing and accounts payable.",
    "Three-way match": "An invoice is paid only when the purchase order, the goods receipt and the invoice agree.",
    "First-time match": "Share of invoices that pass the three-way match on the first attempt, with no manual rework.",
    "Maverick buying": "Purchases made before or without an approved purchase order.",
    "Committed spend": "Money already promised to suppliers through approved purchase orders.",
    "Maturity": "How established a capability is, on a 0-5 scale from non-existent (0) to optimising (5).",
    "Consensus": "How closely the interviewed stakeholders agree on a score; weak consensus needs a workshop.",
    "Blocked": "The website showed a bot check to the automated browser: an environment limit, not a product fault.",
    "Not configured": "The check needs an API key or quota that was not available, so it was not run.",
    "Discovery document": "Google's public, machine-readable description of an API's methods, limits and data.",
    "Playwright": "A tool that drives a real web browser to test pages the way a user would.",
    "HSTS": "A security header that tells browsers to always use an encrypted (HTTPS) connection to a site.",
    "DNSSEC": "Digital signatures that prove internet address (DNS) answers have not been tampered with.",
    "Pass rate": "Share of the checks that ran which passed. Checks that were blocked or not configured are excluded.",
}

PALETTE = ["var(--blue)", "var(--green)", "var(--orange)", "var(--purple)", "var(--pink)", "var(--teal)", "var(--yellow)", "var(--red)"]

esc = lambda value: html.escape(str(value))


def _term_pattern(term: str) -> re.Pattern:
    # acronyms match exactly; phrases ignore case
    return re.compile(r"(?<![\w-])" + re.escape(term) + r"(?![\w-])", 0 if term.isupper() else re.I)


def _define(text: str) -> str:
    return next((f"{term}: {meaning}" if not meaning.startswith(term) else meaning
                 for term, meaning in GLOSSARY.items() if _term_pattern(term).search(text)), "")


def _num(value: float) -> str:
    return f"{value:,.1f}".rstrip("0").rstrip(".") if isinstance(value, float) else f"{value:,}"


def pill(label: str) -> str:
    return f'<span class="pill {STATUS.get(str(label).lower(), "neutral")}">{esc(label)}</span>'


def kpis(items: list[tuple]) -> str:
    """items: (label, value, note) or (label, value, note, tone) with tone ok|warn|bad"""
    cards = []
    for item in items:
        label, value, note, *tone = item
        tone = tone[0] if tone else ""
        meaning = _define(label)
        info = f'<span class="info" tabindex="0" data-tip="{esc(meaning)}" aria-label="{esc(meaning)}">i</span>' if meaning else ""
        status = f'<span class="sr">({TONE_WORDS[tone]})</span>' if tone in TONE_WORDS else ""
        cards.append(
            f'<div class="kpi {tone}"><div class="kpi-label">{esc(label)}{info}</div>'
            f'<div class="kpi-value">{esc(value)}{status}</div><div class="kpi-note">{esc(note)}</div></div>'
        )
    return f'<div class="kpis">{"".join(cards)}</div>'


def table(headers: list[str], rows: list[list], raw_columns: set[int] = frozenset()) -> str:
    """Cells in raw_columns are inserted as HTML (for pills/links); everything else is escaped.
    In the browser the table gains search, status filters, sorting, CSV download and a row limit."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{cell if i in raw_columns else esc(cell)}</td>" for i, cell in enumerate(row)) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def bars(data: list[tuple[str, float]], unit: str = "", max_value: float | None = None, colors: list[str] | None = None) -> str:
    """Horizontal bar chart; hovering a bar shows its share of the total."""
    top = max_value or max((v for _, v in data), default=1) or 1
    total = sum(v for _, v in data) or 1
    rows = []
    for i, (label, value) in enumerate(data):
        width = max(0.5, 100 * value / top)
        color = (colors or PALETTE)[i % len(colors or PALETTE)]
        shown = _num(value)
        tip = f"{label}: {shown}{unit} · {100 * value / total:.0f}% of total"
        rows.append(
            f'<div class="bar-row" tabindex="0" data-tip="{esc(tip)}"><div class="bar-label">{esc(label)}</div>'
            f'<div class="bar-track"><div class="bar" style="width:{width:.1f}%;background:{color}"></div></div>'
            f'<div class="bar-value">{shown}{esc(unit)}</div></div>'
        )
    return f'<div class="bars">{"".join(rows)}</div>'


def donut(parts: list[tuple[str, float, str]], center: str = "", caption: str = "") -> str:
    """parts: (label, value, css color). Inline SVG ring with a legend; hover a legend item to highlight it."""
    total = sum(v for _, v, _ in parts) or 1
    radius, circumference = 42, 2 * math.pi * 42
    offset, rings, legend = 0.0, [], []
    for i, (label, value, color) in enumerate(parts):
        length = circumference * value / total
        share = f"{100 * value / total:.0f}%"
        rings.append(
            f'<circle class="seg" data-i="{i}" data-tip="{esc(f"{label}: {value:g} ({share})")}" r="{radius}" cx="60" cy="60" fill="none" stroke="{color}" stroke-width="14" '
            f'stroke-dasharray="{length:.2f} {circumference - length:.2f}" stroke-dashoffset="{-offset:.2f}" />'
        )
        offset += length
        legend.append(f'<li data-i="{i}" tabindex="0"><i style="background:{color}"></i>{esc(label)} <b>{value:g}</b> <span class="share">{share}</span></li>')
    return (
        f'<div class="donut" data-series><svg viewBox="0 0 120 120" role="img" aria-label="{esc(caption or center)}">'
        f'<circle r="{radius}" cx="60" cy="60" fill="none" stroke="var(--track)" stroke-width="14" />'
        f'<g transform="rotate(-90 60 60)">{"".join(rings)}</g>'
        f'<text x="60" y="62" text-anchor="middle" class="donut-center">{esc(center)}</text>'
        f'<text x="60" y="76" text-anchor="middle" class="donut-caption">{esc(caption)}</text></svg>'
        f'<ul class="legend">{"".join(legend)}</ul></div>'
    )


def lines(series: list[tuple[str, list[float], str]], labels: list[str], height: int = 220, unit: str = "") -> str:
    """Line chart: series of (name, values, color) over shared x labels; points show their value on hover."""
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
    paths, dots, legend = [], [], []
    for n, (name, vals, color) in enumerate(series):
        points = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals) if v is not None)
        paths.append(f'<polyline class="seg" data-i="{n}" points="{points}" fill="none" stroke="{color}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />')
        dots.extend(
            f'<circle class="dot seg" data-i="{n}" cx="{x(i):.1f}" cy="{y(v):.1f}" r="4" fill="{color}" data-tip="{esc(f"{name} · {labels[i]}: {_num(v)}{unit}")}" />'
            for i, v in enumerate(vals) if v is not None
        )
        legend.append(f'<li data-i="{n}" tabindex="0"><i style="background:{color}"></i>{esc(name)}</li>')
    return (
        f'<div class="chart" data-series><svg viewBox="0 0 {width} {height}" role="img">{grid}{"".join(paths)}{"".join(dots)}{xlabels}</svg>'
        f'<ul class="legend inline">{"".join(legend)}</ul></div>'
    )


def radar(axes: list[str], series: list[tuple[str, list[float], str]], max_value: float = 5) -> str:
    """Spider chart for maturity-style scores; each point shows its score on hover."""
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
    shapes, dots, legend = [], [], []
    for s, (name, vals, color) in enumerate(series):
        pts = " ".join(f"{a:.1f},{b:.1f}" for a, b in (point(i, v) for i, v in enumerate(vals)))
        shapes.append(f'<polygon class="seg" data-i="{s}" points="{pts}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="2" />')
        dots.extend(
            f'<circle class="dot seg" data-i="{s}" cx="{point(i, v)[0]:.1f}" cy="{point(i, v)[1]:.1f}" r="4" fill="{color}" data-tip="{esc(f"{name} · {axes[i]}: {v:.1f} / {max_value:g}")}" />'
            for i, v in enumerate(vals)
        )
        legend.append(f'<li data-i="{s}" tabindex="0"><i style="background:{color}"></i>{esc(name)}</li>')
    return (
        f'<div class="chart radar" data-series><svg viewBox="-40 -10 {size + 80} {size + 20}" role="img">{rings}{spokes}{"".join(shapes)}{"".join(dots)}{labels}</svg>'
        f'<ul class="legend inline">{"".join(legend)}</ul></div>'
    )


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "section"


def section(title: str, body: str, intro: str = "") -> str:
    return f'<section class="card" id="s-{_slug(title)}"><h2>{esc(title)}</h2>{f"<p class=intro>{esc(intro)}</p>" if intro else ""}{body}</section>'


def grid(*cards: str) -> str:
    return f'<div class="grid2">{"".join(cards)}</div>'


def _short(title: str) -> str:
    """Contents label: the part of a section title before any colon, bracket or middle dot."""
    return re.split(r"\s*[:(·]\s*", html.unescape(title))[0]


_last_page: dict = {}


def page(*, title: str, eyebrow: str, summary: str, body: str, repo: str, verdict: tuple[str, str] | None = None,
         takeaways: list[str] | None = None) -> str:
    """verdict: (label, tone) shown as the headline status, e.g. ("Go", "ok").
    takeaways: plain-language sentences for the executive summary at the top of the report."""
    _last_page.update(title=title, eyebrow=eyebrow, repo=repo, verdict=verdict[0] if verdict else "", tone=verdict[1] if verdict else "neutral")
    built = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    siblings = "".join(
        f'<a href="{PORTFOLIO}{slug}/" class="{"current" if slug == repo else ""}"><span>{esc(role)}</span>{esc(name)}</a>'
        for role, name, slug in CASE_STUDY
    )
    in_case_study = any(slug == repo for _, _, slug in CASE_STUDY)
    verdict_html = (f'<div class="verdict {verdict[1]}"><span class="sr">Overall status ({TONE_WORDS.get(verdict[1], "")}): </span>{esc(verdict[0])}</div>'
                    if verdict else "")

    if takeaways:
        legend = "".join(f'<span class="pill {tone}">{label}</span>' for tone, label in (("ok", "Good"), ("warn", "Needs attention"), ("bad", "Action needed")))
        body = (f'<section class="card exec" id="s-summary"><h2>Executive summary</h2><ul>{"".join(f"<li>{esc(t)}</li>" for t in takeaways)}</ul>'
                f'<p class="key">Colour key: {legend}</p></section>') + body

    text = re.sub(r"<[^>]+>", " ", html.unescape(body + summary))
    used = [(term, meaning) for term, meaning in GLOSSARY.items() if _term_pattern(term).search(text)]
    if used:
        body += section("Glossary", "<dl class=glossary>" + "".join(f"<dt>{esc(t)}</dt><dd>{esc(m)}</dd>" for t, m in used) + "</dl>",
                        "Terms used in this report, in plain language.")

    seen: dict[str, int] = {}

    def unique(match: re.Match) -> str:
        sid = match.group(1)
        seen[sid] = seen.get(sid, 0) + 1
        return f'id="{sid}{"" if seen[sid] == 1 else f"-{seen[sid]}"}"'

    body = re.sub(r'id="(s-[^"]+)"', unique, body)
    found = re.findall(r'<section class="card[^"]*" id="(s-[^"]+)"><h2>(.*?)</h2>', body)
    shorts = [_short(t) for _, t in found]
    # sections that would share a short label ("RAID: risks", "RAID: issues") keep their full title
    contents = "".join(f'<a href="#{sid}">{esc(s if shorts.count(s) == 1 else html.unescape(t))}</a>' for (sid, t), s in zip(found, shorts))

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>{esc(title)} · Rahmadani Tyas Ningrum</title>
<meta name="description" content="{esc(summary)}">
<script>(function(){{var t;try{{t=localStorage.getItem("theme")}}catch(e){{}}if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.setAttribute("data-theme",t)}})();</script>
<style>{CSS}</style>
</head>
<body data-report="{esc(title)}">
<header class="top">
  <div class="actions"><a href="{PORTFOLIO}#projects" class="btn back" data-back aria-label="Back to the portfolio"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg><span>Portfolio</span></a></div>
  <div class="actions">
    <a href="https://github.com/artysficial/{repo}" class="src">Source on GitHub</a>
    <button type="button" class="btn" data-theme-toggle aria-label="Switch to dark mode"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="5"/><path d="M12 1v3M12 20v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M1 12h3M20 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1" class="rays"/><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" class="moon"/></svg><span>Dark</span></button>
    <button type="button" class="btn primary" data-export data-goatcounter-click="pdf-export/{esc(repo)}" data-goatcounter-title="PDF export: {esc(title)}" title="Opens the print dialog: choose “Save as PDF”"><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3v12m0 0-5-5m5 5 5-5M4 17v3h16v-3"/></svg><span>Export PDF</span></button>
  </div>
</header>
<main>
<div class="print-meta">Rahmadani Tyas Ningrum · {esc(eyebrow)} · {PORTFOLIO}{esc(repo)}/</div>
<div class="hero">
  <p class="eyebrow">{esc(eyebrow)}</p>
  <h1>{esc(title)}</h1>
  <p class="summary">{esc(summary)}</p>
  {verdict_html}
  <p class="built">Generated {built} by the project's CI pipeline.</p>
</div>
<nav class="toc" aria-label="Contents">{contents}</nav>
{body}
{f'<section class="case"><h2>Arunika Bank case study</h2><p class="intro">One fictional payment-security programme, seen through six roles. Every dashboard uses the same programme, requirement IDs and systems.</p><nav>{siblings}</nav></section>' if in_case_study else ''}
</main>
<footer>Fictional data for portfolio purposes · <a href="{PORTFOLIO}">artysficial.github.io</a> · Generated {built}</footer>
<script>{JS}</script>
<script data-goatcounter="https://artysficial.goatcounter.com/count" async src="https://gc.zgo.at/count.js"></script>
</body>
</html>"""


LIGHT = """--bg:#f5f5f7;--card:#fff;--text:#1d1d1f;--muted:#6e6e73;--line:#d2d2d7;--track:#e8e8ed;--hover:#f0f0f3;
--blue:#0071e3;--green:#28a745;--orange:#f56300;--purple:#8e44ad;--pink:#e3006d;--teal:#0a9396;--yellow:#c99700;--red:#d70015;
--ok-bg:#e3f7e8;--ok:#1a7f37;--warn-bg:#fff4dc;--warn:#9a6700;--bad-bg:#ffe5e7;--bad:#c4001a;--neutral-bg:#ececf0;color-scheme:light;"""
DARK = """--bg:#000;--card:#1c1c1e;--text:#f5f5f7;--muted:#a1a1a6;--line:#38383a;--track:#2c2c2e;--hover:#2a2a2d;
--blue:#2997ff;--green:#30d158;--orange:#ff9f0a;--purple:#bf5af2;--pink:#ff375f;--teal:#40c8e0;--yellow:#ffd60a;--red:#ff453a;
--ok-bg:#0f2e1a;--ok:#30d158;--warn-bg:#33270a;--warn:#ffd60a;--bad-bg:#3a0e12;--bad:#ff6961;--neutral-bg:#2c2c2e;color-scheme:dark;"""

CSS = (":root{" + LIGHT + "}:root[data-theme=dark]{" + DARK + "}"
       "@media (prefers-color-scheme:dark){:root:not([data-theme=light]){" + DARK + "}}") + """
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--text);font:17px/1.47 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",Inter,Roboto,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--blue);text-decoration:none}a:hover{text-decoration:underline}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.top{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px max(20px,calc(50% - 540px));background:color-mix(in srgb,var(--bg) 78%,transparent);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid var(--line);font-size:14px}
.actions{display:flex;align-items:center;gap:8px}
.btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--card);color:var(--text);border-radius:980px;padding:6px 14px;font:inherit;font-size:13px;font-weight:500;cursor:pointer}
.btn:hover{background:var(--hover)}.btn.primary{background:var(--blue);border-color:var(--blue);color:#fff}.btn.primary:hover{filter:brightness(1.08)}
.btn svg{width:16px;height:16px;fill:none;stroke:currentColor;stroke-width:2;stroke-linecap:round;stroke-linejoin:round}
.btn .moon{display:none}:root[data-theme=dark] .btn .moon{display:block}:root[data-theme=dark] .btn circle,:root[data-theme=dark] .btn .rays{display:none}
.btn.back{padding-left:8px;text-decoration:none}.btn.back:hover{text-decoration:none}
@media (max-width:640px){.src{display:none}.btn span{display:none}.btn{padding:8px}.btn.back{padding:6px 12px 6px 6px}.btn.back span{display:inline}}::view-transition-old(root),::view-transition-new(root){animation:none;mix-blend-mode:normal}
main{max-width:1080px;margin:0 auto;padding:0 20px 64px}
.hero{text-align:center;padding:64px 0 28px}
.eyebrow{color:var(--orange);font-weight:600;font-size:15px;margin:0 0 8px}
h1{font-size:clamp(36px,6vw,64px);line-height:1.05;letter-spacing:-.02em;margin:0 0 16px;font-weight:700}
.summary{color:var(--muted);font-size:clamp(18px,2.2vw,22px);max-width:760px;margin:0 auto}
.built{color:var(--muted);font-size:13px;margin-top:20px}
.verdict{display:inline-flex;align-items:center;gap:10px;margin-top:24px;padding:10px 22px;border-radius:980px;font-weight:600;font-size:19px}
.verdict::before,.kpi.ok .kpi-label::before,.kpi.warn .kpi-label::before,.kpi.bad .kpi-label::before{display:inline-grid;place-items:center;width:1.25em;height:1.25em;border-radius:50%;font-size:.8em;font-weight:700;color:var(--card);flex:none}
.verdict.ok,.kpi.ok{--tone:var(--ok)}.verdict.warn,.kpi.warn{--tone:var(--warn)}.verdict.bad,.kpi.bad{--tone:var(--bad)}
.verdict.ok::before,.kpi.ok .kpi-label::before{content:"✓";background:var(--ok)}.verdict.warn::before,.kpi.warn .kpi-label::before{content:"!";background:var(--warn)}.verdict.bad::before,.kpi.bad .kpi-label::before{content:"✕";background:var(--bad)}
.verdict.ok{background:var(--ok-bg);color:var(--ok)}.verdict.warn{background:var(--warn-bg);color:var(--warn)}.verdict.bad{background:var(--bad-bg);color:var(--bad)}
.toc{display:flex;gap:8px;overflow-x:auto;padding:4px 2px 18px;scrollbar-width:none;justify-content:safe center}.toc::-webkit-scrollbar{display:none}
.toc a{flex:none;font-size:13px;color:var(--text);background:var(--card);border:1px solid var(--line);border-radius:980px;padding:5px 12px}.toc a:hover{text-decoration:none;border-color:var(--blue);color:var(--blue)}
.exec{border-left:4px solid var(--blue)}.exec ul{margin:8px 0 0;padding-left:20px;font-size:17px}.exec li{margin:0 0 8px}
.exec .key{color:var(--muted);font-size:13px;margin:14px 0 0;display:flex;flex-wrap:wrap;gap:6px;align-items:center}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin:0 0 20px}
.kpi{background:var(--card);border-radius:20px;padding:22px;border-top:3px solid var(--tone,transparent)}
.kpi-label{color:var(--muted);font-size:14px;display:flex;align-items:center;gap:6px}.kpi-label::before{margin-right:2px}
.kpi-value{font-size:clamp(24px,2.4vw,34px);font-weight:700;letter-spacing:-.02em;margin:4px 0;white-space:nowrap}.kpi-note{color:var(--muted);font-size:13px}
.kpi.ok .kpi-value{color:var(--ok)}.kpi.warn .kpi-value{color:var(--warn)}.kpi.bad .kpi-value{color:var(--bad)}
.info{display:inline-grid;place-items:center;width:16px;height:16px;border-radius:50%;border:1px solid var(--muted);font:600 10px/1 Georgia,serif;font-style:italic;cursor:help;margin-left:auto;flex:none}
.card{background:var(--card);border-radius:24px;padding:28px;margin:0 0 20px}
.card h2{margin:0 0 6px;font-size:24px;letter-spacing:-.01em}.intro{color:var(--muted);margin:0 0 18px;font-size:15px}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:20px;margin:0 0 20px}.grid2 .card{margin:0}
@media (max-width:520px){.grid2{grid-template-columns:1fr}.card{padding:20px}.hero{padding-top:40px}}
.tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 12px}
.tools input{flex:1 1 200px;max-width:320px;font:inherit;font-size:14px;color:var(--text);background:var(--bg);border:1px solid var(--line);border-radius:10px;padding:7px 12px}
.chips{display:flex;flex-wrap:wrap;gap:6px}.chips button{border:1px solid transparent;cursor:pointer;font:inherit;font-size:12px}
.chips button[aria-pressed=true]{border-color:currentColor;box-shadow:0 0 0 1px currentColor}.chips .all{background:var(--neutral-bg);color:var(--text);border-radius:980px;padding:2px 10px;font-weight:600}
.count{color:var(--muted);font-size:13px;margin-left:auto}.tools .btn{padding:4px 12px;font-size:12px}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;font-size:14px}
th{text-align:left;color:var(--muted);font-weight:500;padding:8px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th.sortable{cursor:pointer;user-select:none}th.sortable:hover{color:var(--text)}th.sortable::after{content:" ↕";opacity:.35;font-size:11px}
th[aria-sort=ascending]::after{content:" ↑";opacity:1}th[aria-sort=descending]::after{content:" ↓";opacity:1}
td{padding:10px;border-bottom:1px solid var(--line);vertical-align:top}tr:last-child td{border-bottom:0}
.table-wrap tbody tr:hover td{background:var(--hover)}tr.cut{display:none}.empty td{color:var(--muted);text-align:center}
.more{display:block;margin:12px auto 0}
.pill{display:inline-block;padding:2px 10px;border-radius:980px;font-size:12px;font-weight:600;white-space:nowrap;background:var(--neutral-bg)}
.pill.ok{background:var(--ok-bg);color:var(--ok)}.pill.warn{background:var(--warn-bg);color:var(--warn)}.pill.bad{background:var(--bad-bg);color:var(--bad)}
.bars{display:grid;gap:6px}.bar-row{display:grid;grid-template-columns:minmax(110px,30%) 1fr auto;gap:12px;align-items:center;font-size:14px;padding:3px 6px;margin:0 -6px;border-radius:8px;cursor:default}
.bar-row:hover,.bar-row:focus-visible{background:var(--hover)}
.bar-track{height:12px;background:var(--track);border-radius:6px;overflow:hidden}.bar{height:100%;border-radius:6px;transform-origin:left;animation:grow .8s cubic-bezier(.2,.7,.2,1) both}.bar-value{font-variant-numeric:tabular-nums;color:var(--muted)}
@keyframes grow{from{transform:scaleX(0)}}
.donut{display:flex;align-items:center;gap:24px;flex-wrap:wrap}.donut svg{width:170px;height:170px}.donut-center{font-size:20px;font-weight:700;fill:var(--text)}.donut-caption{font-size:8px;fill:var(--muted)}
.seg{transition:opacity .2s,stroke-width .2s}.donut .seg:hover{stroke-width:17}[data-series].focus .seg:not(.hi){opacity:.15}
.dot{opacity:0;cursor:pointer}.chart:hover .dot,.dot:hover{opacity:1}.dot:hover{r:6}
.legend{list-style:none;padding:0;margin:0;font-size:14px;display:grid;gap:6px}.legend.inline{display:flex;flex-wrap:wrap;gap:16px;margin-top:8px}
.legend li{cursor:default;border-radius:6px;padding:1px 4px;margin:0 -4px}.legend li:hover{background:var(--hover)}.legend .share{color:var(--muted);font-size:12px}
.legend i{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:8px;vertical-align:middle}
.chart svg{width:100%;height:auto}.grid{stroke:var(--line);stroke-width:1}.axis{fill:var(--muted);font-size:11px}.radar svg{max-width:420px;display:block;margin:0 auto}
.tip{position:fixed;z-index:10;pointer-events:none;max-width:300px;background:var(--text);color:var(--bg);font-size:13px;line-height:1.4;padding:7px 11px;border-radius:10px;box-shadow:0 6px 24px rgba(0,0,0,.18);opacity:0;transition:opacity .12s}.tip.on{opacity:1}
.glossary{display:grid;grid-template-columns:minmax(140px,auto) 1fr;gap:8px 20px;margin:0;font-size:15px}.glossary dt{font-weight:600}.glossary dd{margin:0;color:var(--muted)}
@media (max-width:520px){.glossary{grid-template-columns:1fr}.glossary dd{margin-bottom:8px}}
code{font:13px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--track);padding:2px 6px;border-radius:6px}
.case{margin-top:48px;text-align:center}.case h2{font-size:28px;margin:0 0 6px}
.case nav{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:20px}
.case a{display:block;background:var(--card);border-radius:18px;padding:16px;color:var(--text);font-weight:600;font-size:15px;text-align:left}
.case a span{display:block;color:var(--muted);font-weight:500;font-size:12px;margin-bottom:4px}.case a.current{outline:2px solid var(--blue)}
footer{text-align:center;color:var(--muted);font-size:12px;padding:24px}
.print-meta{display:none}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
@media print{
@page{size:A4;margin:14mm 12mm}
body{""" + LIGHT + """--bg:#fff;--card:#fff;font-size:10.5pt;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.top,.toc,.tools,.more,.case,.tip,.info{display:none!important}
main{max-width:none;padding:0}.print-meta{display:block;color:var(--muted);font-size:8.5pt;border-bottom:1px solid var(--line);padding-bottom:6px;margin-bottom:10px}
.hero{text-align:left;padding:0 0 12px}h1{font-size:24pt;margin-bottom:6px}.summary{margin:0;font-size:11pt;max-width:none}.verdict{margin-top:10px;font-size:12pt;padding:6px 14px}.built{margin-top:8px}
.card{border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:0 0 10px}.card h2{font-size:14pt;break-after:avoid}.intro{font-size:9.5pt;margin-bottom:8px}
.exec,.kpi,.grid2 .card,.chart,.donut,.bars,.glossary{break-inside:avoid}
.kpis{grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:10px}.kpi{border:1px solid var(--line);border-top:3px solid var(--tone,var(--line));border-radius:10px;padding:10px 12px}.kpi-value{font-size:16pt}
.grid2{grid-template-columns:1fr 1fr;gap:10px;margin-bottom:10px}.donut svg{width:120px;height:120px}
table{font-size:8.5pt}th,td{padding:4px 6px}thead{display:table-header-group}tr{break-inside:avoid}tr.cut{display:table-row}th.sortable::after{content:none}
.table-wrap{overflow:visible}.bar{animation:none}.dot{display:none}a{color:inherit}
footer{padding:10px 0 0;text-align:left}
}
"""

JS = r"""
(function () {
  var root = document.documentElement;

  // theme: same storage key as the portfolio site, with its circular reveal from the button
  var toggle = document.querySelector("[data-theme-toggle]");
  function label() {
    var dark = root.getAttribute("data-theme") === "dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    toggle.querySelector("span").textContent = dark ? "Light" : "Dark";
  }
  toggle.addEventListener("click", function () {
    var theme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
    var apply = function () { root.setAttribute("data-theme", theme); try { localStorage.setItem("theme", theme); } catch (e) {} label(); };
    if (!document.startViewTransition || matchMedia("(prefers-reduced-motion: reduce)").matches) return apply();
    var box = toggle.getBoundingClientRect(), x = box.left + box.width / 2, y = box.top + box.height / 2;
    var r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    document.startViewTransition(apply).ready.then(function () {
      root.animate({ clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + r + "px at " + x + "px " + y + "px)"] },
        { duration: 650, easing: "cubic-bezier(0.4, 0, 0.2, 1)", pseudoElement: "::view-transition-new(root)" });
    });
  });
  label();

  // back: when the visitor came from the portfolio's home page, return to their place on it
  document.querySelector("[data-back]").addEventListener("click", function (e) {
    var from = document.referrer && new URL(document.referrer);
    if (from && from.origin === location.origin && /^\/(index\.html)?$/.test(from.pathname) && history.length > 1) {
      e.preventDefault();
      history.back();
    }
  });

  // export: the print stylesheet lays the report out on A4; the title becomes the PDF's file name
  var title = document.title;
  document.querySelector("[data-export]").addEventListener("click", function () { window.print(); });
  addEventListener("beforeprint", function () {
    document.title = document.body.getAttribute("data-report") + " - report " + new Date().toISOString().slice(0, 10);
  });
  addEventListener("afterprint", function () { document.title = title; });

  // tooltips for anything with data-tip: charts, bars and KPI definitions
  var tip = document.createElement("div");
  tip.className = "tip"; tip.setAttribute("role", "tooltip");
  document.body.appendChild(tip);
  function place(x, y) {
    var w = tip.offsetWidth, h = tip.offsetHeight;
    tip.style.left = Math.min(innerWidth - w - 8, Math.max(8, x - w / 2)) + "px";
    tip.style.top = (y - h - 12 < 8 ? y + 20 : y - h - 12) + "px";
  }
  function show(el, x, y) { tip.textContent = el.getAttribute("data-tip"); tip.classList.add("on"); place(x, y); }
  function hide() { tip.classList.remove("on"); }
  document.addEventListener("pointerover", function (e) {
    var el = e.target.closest && e.target.closest("[data-tip]");
    el ? show(el, e.clientX, e.clientY) : hide();
  });
  document.addEventListener("pointermove", function (e) { if (tip.classList.contains("on")) place(e.clientX, e.clientY); });
  document.addEventListener("focusin", function (e) {
    var el = e.target.closest("[data-tip]");
    if (el) { var b = el.getBoundingClientRect(); show(el, b.left + b.width / 2, b.top); }
  });
  document.addEventListener("focusout", hide);
  addEventListener("scroll", hide, { passive: true });

  // legends: pointing at a series highlights it in the chart
  document.querySelectorAll("[data-series]").forEach(function (chart) {
    chart.querySelectorAll(".legend li").forEach(function (item) {
      function on() {
        chart.classList.add("focus");
        chart.querySelectorAll(".seg").forEach(function (s) { s.classList.toggle("hi", s.getAttribute("data-i") === item.getAttribute("data-i")); });
      }
      function off() { chart.classList.remove("focus"); }
      item.addEventListener("pointerenter", on); item.addEventListener("focus", on);
      item.addEventListener("pointerleave", off); item.addEventListener("blur", off);
    });
  });

  // tables: search, status filter, sort, CSV download and a row limit
  var RANK = { bad: 0, warn: 1, neutral: 2, ok: 3 };
  var LIMIT = 10;
  function tone(el) { var p = el.querySelector(".pill"); return p ? p.className.replace("pill", "").trim() || "neutral" : null; }
  // amounts, percentages, durations and ratios ("Rp 1.2 bn", "86%", "+3 d", "34/38"); IDs and dates sort as text
  function number(text) {
    var m = text.replace(/,/g, "").replace("−", "-").match(/^(?:Rp\s*)?([+-]?\d+(?:\.\d+)?)\s*(?:%|\/\s*\d+|[a-z]{0,5})$/i);
    return m ? parseFloat(m[1]) * (/\bbn$/.test(text) ? 1000 : 1) : null;
  }
  document.querySelectorAll(".table-wrap").forEach(function (wrap) {
    var table = wrap.querySelector("table"), tbody = table.tBodies[0];
    var rows = Array.prototype.slice.call(tbody.rows);
    if (rows.length < 2) return;
    var heading = wrap.closest(".card") && wrap.closest(".card").querySelector("h2");
    var name = heading ? heading.textContent : "table";
    var query = "", status = "", expanded = rows.length <= LIMIT + 2;
    var tools = document.createElement("div");
    tools.className = "tools";

    if (rows.length > 5) {
      var input = document.createElement("input");
      input.type = "search"; input.placeholder = "Search " + rows.length + " rows";
      input.setAttribute("aria-label", "Search " + name);
      input.addEventListener("input", function () { query = input.value.trim().toLowerCase(); update(); });
      tools.appendChild(input);
    }
    var labels = {};
    rows.forEach(function (r) { r.querySelectorAll(".pill").forEach(function (p) { labels[p.textContent] = p.className; }); });
    var keys = Object.keys(labels).sort(function (a, b) { return RANK[labels[a].replace("pill ", "")] - RANK[labels[b].replace("pill ", "")]; });
    if (keys.length > 1 && keys.length <= 8) {
      var chips = document.createElement("div");
      chips.className = "chips"; chips.setAttribute("role", "group"); chips.setAttribute("aria-label", "Filter by status");
      [""].concat(keys).forEach(function (key) {
        var b = document.createElement("button");
        b.type = "button"; b.textContent = key || "All";
        b.className = key ? labels[key] : "all";
        b.setAttribute("aria-pressed", String(key === status));
        b.addEventListener("click", function () {
          status = key;
          chips.querySelectorAll("button").forEach(function (c) { c.setAttribute("aria-pressed", String(c === b)); });
          update();
        });
        chips.appendChild(b);
      });
      tools.appendChild(chips);
    }
    var count = document.createElement("span");
    count.className = "count";
    tools.appendChild(count);
    var csv = document.createElement("button");
    csv.type = "button"; csv.className = "btn"; csv.textContent = "CSV";
    csv.title = "Download the rows shown (all of them, ignoring the row limit) as a spreadsheet";
    csv.addEventListener("click", function () {
      var quote = function (cell) { return '"' + cell.innerText.trim().replace(/"/g, '""') + '"'; };
      var lines = [Array.prototype.map.call(table.tHead.rows[0].cells, quote).join(",")];
      rows.forEach(function (r) { if (!r.hidden) lines.push(Array.prototype.map.call(r.cells, quote).join(",")); });
      var link = document.createElement("a");
      link.href = URL.createObjectURL(new Blob(["﻿" + lines.join("\r\n")], { type: "text/csv" }));
      link.download = (document.body.getAttribute("data-report") + " " + name).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") + ".csv";
      link.click();
      setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
    });
    tools.appendChild(csv);
    wrap.parentNode.insertBefore(tools, wrap);

    var more = document.createElement("button");
    more.type = "button"; more.className = "btn more";
    more.addEventListener("click", function () { expanded = !expanded; update(); });
    wrap.parentNode.insertBefore(more, wrap.nextSibling);
    var empty = document.createElement("tr");
    empty.className = "empty"; empty.innerHTML = '<td colspan="' + table.tHead.rows[0].cells.length + '">No rows match.</td>';

    function update() {
      var matched = 0, shown = 0, filtering = query || status;
      rows.forEach(function (r) {
        var ok = (!query || r.textContent.toLowerCase().indexOf(query) > -1) &&
          (!status || Array.prototype.some.call(r.querySelectorAll(".pill"), function (p) { return p.textContent === status; }));
        r.hidden = !ok;
        if (ok) matched++;
        var cut = ok && !expanded && !filtering && matched > LIMIT;
        r.classList.toggle("cut", cut);
        if (ok && !cut) shown++;
      });
      if (!matched) tbody.appendChild(empty); else if (empty.parentNode) empty.remove();
      count.textContent = shown === rows.length ? rows.length + " rows" : "Showing " + shown + " of " + rows.length;
      more.hidden = filtering || rows.length <= LIMIT + 2;
      more.textContent = expanded ? "Show fewer" : "Show all " + rows.length + " rows";
    }

    Array.prototype.forEach.call(table.tHead.rows[0].cells, function (th, col) {
      th.classList.add("sortable"); th.tabIndex = 0;
      th.title = "Sort by " + th.textContent + (tone(rows[0].cells[col] || th) !== null ? " (most serious first)" : "");
      function sort() {
        var dir = th.getAttribute("aria-sort") === "ascending" ? -1 : 1;
        Array.prototype.forEach.call(table.tHead.rows[0].cells, function (h) { h.removeAttribute("aria-sort"); });
        th.setAttribute("aria-sort", dir === 1 ? "ascending" : "descending");
        var cells = rows.map(function (r) { return r.cells[col]; });
        var numeric = cells.every(function (c) { var t = c ? c.textContent.trim() : ""; return !t || t === "—" || number(t) !== null; });
        var keyOf = function (c) {
          if (!c) return "";
          var t = tone(c);
          if (t !== null) return RANK[t] + c.textContent;
          var text = c.textContent.trim();
          return numeric ? (number(text) === null ? -Infinity : number(text)) : text;
        };
        var collator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
        rows.sort(function (a, b) {
          var x = keyOf(a.cells[col]), y = keyOf(b.cells[col]);
          return dir * (typeof x === "number" ? x - y : collator.compare(x, y));
        });
        rows.forEach(function (r) { tbody.appendChild(r); });
        update();
      }
      th.addEventListener("click", sort);
      th.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sort(); } });
    });
    update();
  });
})();
"""


def write(path: str, content: str) -> None:
    """Writes a page. Next to a dashboard's index.html it also writes summary.json (verdict and
    test counts), which the portfolio site reads to show each project's live status."""
    import json
    import os

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    if os.path.basename(path) == "index.html" and _last_page:
        counts = {}
        results = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(path))), "reports", "results.json")
        if os.path.exists(results):
            with open(results, encoding="utf-8") as handle:
                counts = json.load(handle).get("counts", {})
        summary = {**_last_page, "counts": counts, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        with open(os.path.join(os.path.dirname(path), "summary.json"), "w", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2)
