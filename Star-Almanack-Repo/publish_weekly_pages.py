#!/usr/bin/env python3
"""Publish the expanded 2026 Star Almanack as 53 static weekly HTML pages.

Input:  almanack-expanded.md
Output: site/2026/index.html and site/2026/W01..W53/index.html

The publisher deliberately uses only the Python standard library so GitHub
Actions can regenerate the site reproducibly without an extra Markdown stack.
It supports the Markdown constructs used by the weekly Almanack: headings,
paragraphs, bold/emphasis, inline code, and pipe tables.
"""

from __future__ import annotations

import html
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).parent
SOURCE = ROOT / "almanack-expanded.md"
OUT = ROOT / "site" / "2026"
WEEK_RE = re.compile(r"(?m)^## (ISO 2026-W(\d{2}))\s*$")
H2_RE = re.compile(r"(?m)^##\s+.+$")

ZODIAC_NAMES = {
    "♈": "Aries",
    "♉": "Taurus",
    "♊": "Gemini",
    "♋": "Cancer",
    "♌": "Leo",
    "♍": "Virgo",
    "♎": "Libra",
    "♏": "Scorpio",
    "♐": "Sagittarius",
    "♑": "Capricorn",
    "♒": "Aquarius",
    "♓": "Pisces",
}

CSS = """
:root { color-scheme: light dark; --ink:#202833; --muted:#66717d; --navy:#102a43; --link:#245c86; --paper:#fffdf8; --page:#eee9df; --rule:#d8d2c8; --soft-blue:#edf4f8; }
* { box-sizing: border-box; }
html { font-size:17px; }
body { margin:0; font-family:Georgia,'Times New Roman',serif; line-height:1.65; background:var(--page); color:var(--ink); -webkit-font-smoothing:antialiased; }
a,a:visited { color:var(--link); text-underline-offset:.15em; }
header,footer { background:var(--navy); color:#fff; }
header { border-bottom:4px solid #c5a45c; }
header a,header a:visited,footer a,footer a:visited { color:#eef7ff; }
.wrap { max-width:1080px; margin:0 auto; padding:1.15rem 1.5rem; }
main.wrap { background:var(--paper); min-height:76vh; padding:2rem 2.4rem 3.25rem; box-shadow:0 0 28px rgba(25,35,45,.08); }
.brand { font-size:1.35rem; font-weight:700; }
.subtitle { margin-top:.1rem; opacity:.86; font-size:.94rem; }
nav.weeknav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:.8rem; margin:.4rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.9rem; }
nav.weeknav > :last-child { justify-self:end; }
nav.weeknav a,nav.weeknav a:visited,nav.weeknav span { display:inline-block; min-width:5.5rem; padding:.58rem .8rem; border:1px solid #c8d3dc; border-radius:.45rem; text-decoration:none; text-align:center; color:var(--link); background:#fff; }
h1,h2,h3 { line-height:1.2; color:#17344d; }
h1 { margin:.3rem 0 1rem; font-size:clamp(2rem,5vw,2.75rem); }
h2 { margin:2.25rem 0 .8rem; padding-bottom:.35rem; border-bottom:1px solid var(--rule); font-size:1.42rem; }
p { max-width:72ch; margin:.7rem 0 1rem; }
strong { color:#162d42; }
table { width:100%; border-collapse:separate; border-spacing:0; margin:1rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.93rem; line-height:1.45; border:1px solid #cbd3da; border-radius:.5rem; overflow:hidden; }
th,td { padding:.7rem .8rem; vertical-align:top; border-right:1px solid #d6dde3; border-bottom:1px solid #d6dde3; }
th:last-child,td:last-child { border-right:0; }
tbody tr:last-child td { border-bottom:0; }
th { background:#e8f0f5; text-align:left; color:#17344d; font-weight:700; }
tbody tr:nth-child(even) td { background:#fbfaf7; }
table.calendar { display:table; table-layout:fixed; }
table.calendar th:first-child,table.calendar td:first-child { width:16%; }
table.calendar th:nth-child(2),table.calendar td:nth-child(2) { width:8%; }
table.calendar th:nth-child(3),table.calendar td:nth-child(3) { width:76%; }
table.calendar td:first-child { white-space:nowrap; font-weight:600; }
table.calendar td:nth-child(2) { white-space:nowrap; text-align:center; }
table.calendar td:nth-child(3) { line-height:1.6; }
table.ephemeris { font-size:.9rem; }
table.ephemeris th,table.ephemeris td { text-align:center; }
table.ephemeris td { white-space:nowrap; padding-top:.8rem; padding-bottom:.8rem; }
.zodiac-glyph { font-family:'Apple Symbols','Arial Unicode MS','Segoe UI Symbol','Noto Sans Symbols 2',serif; font-variant-emoji:text; color:currentColor; -webkit-text-fill-color:currentColor; }
code { background:#eef1f3; padding:.1rem .3rem; border-radius:.25rem; font-size:.9em; }
.weekgrid { display:grid; grid-template-columns:repeat(auto-fit,minmax(145px,1fr)); gap:.7rem; padding:0; margin:1.5rem 0 0; list-style:none; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; }
.weekgrid a,.weekgrid a:visited { display:block; padding:.85rem .9rem; border:1px solid #cbd3da; border-radius:.5rem; text-decoration:none; text-align:center; background:#fff; color:var(--link); font-weight:650; }
footer { font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.88rem; }
footer .wrap { padding-top:1.3rem; padding-bottom:1.3rem; opacity:.9; }
@media (max-width:760px) { html{font-size:16px}.wrap{padding-left:1rem;padding-right:1rem}main.wrap{padding:1.35rem 1rem 2.5rem;box-shadow:none}nav.weeknav{gap:.4rem;margin-bottom:1.5rem}nav.weeknav a,nav.weeknav a:visited,nav.weeknav span{min-width:0;padding:.6rem .45rem}table{font-size:.9rem}table.calendar{display:table;width:100%;table-layout:fixed;overflow:hidden}table.calendar th,table.calendar td{padding:.6rem .55rem}table.calendar th:first-child,table.calendar td:first-child{width:20%;min-width:0}table.calendar th:nth-child(2),table.calendar td:nth-child(2){width:11%;min-width:0}table.calendar th:nth-child(3),table.calendar td:nth-child(3){width:69%;min-width:0}table.calendar td:first-child{white-space:normal}table.calendar td:nth-child(2){white-space:nowrap}table.calendar td:nth-child(3){overflow-wrap:anywhere}table.ephemeris{display:block;overflow-x:auto;-webkit-overflow-scrolling:touch;font-size:.86rem}.weekgrid{grid-template-columns:repeat(2,minmax(0,1fr))} }
@media (prefers-color-scheme:dark) { :root{--ink:#dce6ef;--muted:#a7b4c0;--link:#9fd0ff;--paper:#17212b;--page:#10171f;--rule:#394957;--soft-blue:#203549}body{background:var(--page);color:var(--ink)}main.wrap{background:var(--paper);box-shadow:none}h1,h2,h3,strong{color:#f1f7fb}th{background:#223444;color:#eef7ff}th,td{border-color:#40505e}table{border-color:#40505e}tbody tr:nth-child(even) td{background:#1b2732}code{background:#263643}.weekgrid a,.weekgrid a:visited,nav.weeknav a,nav.weeknav a:visited{background:#1c2a36;border-color:#405567;color:#b6dcff}nav.weeknav span{background:#1a242d;border-color:#384956;color:#7f909f} }
""".strip()


def zodiac_glyph(glyph: str) -> str:
    return f'<span class="zodiac-glyph">{html.escape(glyph)}&#xfe0e;</span>'


def inline_markup(text: str) -> str:
    sentinel = "@@BR@@"
    text = text.replace("<br>", sentinel)
    text = html.escape(text)
    for glyph in ZODIAC_NAMES:
        text = text.replace(glyph + "\ufe0f", glyph).replace(glyph + "\ufe0e", glyph)
        text = text.replace(glyph, zodiac_glyph(glyph))
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    return text.replace(sentinel, "<br>")


def is_separator_row(line: str) -> bool:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def format_zodiac_cell(text: str) -> str:
    stripped = text.strip()
    if stripped and stripped[0] in ZODIAC_NAMES:
        glyph = stripped[0]
        remainder = re.sub(rf"^\({re.escape(ZODIAC_NAMES[glyph])}\)\s*", "", stripped[1:].strip())
        spacer = " " if remainder else ""
        return f"{zodiac_glyph(glyph)}{spacer}{inline_markup(remainder)}"
    return inline_markup(text)


def parse_table(lines: list[str], start: int) -> tuple[str, int]:
    rows: list[list[str]] = []
    i = start
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            j = i + 1
            while j < len(lines) and not lines[j].strip(): j += 1
            if j < len(lines) and lines[j].lstrip().startswith("|"):
                i = j
                continue
            break
        if not line.lstrip().startswith("|"): break
        if not is_separator_row(line): rows.append([c.strip() for c in line.strip().strip("|").split("|")])
        i += 1
    if not rows: return "", i
    head, body = rows[0], rows[1:]
    is_ephemeris = len(head) == 7 and head[0].startswith("☉ Sun") and head[-1].startswith("♄ Saturn")
    is_calendar = len(head) == 3 and head == ["Date", "Zodiac day", "Events"]
    table_class = ' class="ephemeris"' if is_ephemeris else (' class="calendar"' if is_calendar else "")
    out = [f"<table{table_class}><thead><tr>"]
    if is_ephemeris:
        out.extend(f"<th>{inline_markup(c.split()[0])}</th>" for c in head)
    else:
        out.extend(f"<th>{inline_markup(c)}</th>" for c in head)
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        for index, c in enumerate(row):
            cell = format_zodiac_cell(c) if (is_ephemeris or (is_calendar and index == 1)) else inline_markup(c)
            out.append(f"<td>{cell}</td>")
        out.append("</tr>")
    out.append("</tbody></table>")
    return "".join(out), i


def markdown_fragment(md: str) -> str:
    lines = md.splitlines(); out=[]; para=[]
    def flush_para():
        if para:
            text=" ".join(x.strip() for x in para).strip()
            if text: out.append(f"<p>{inline_markup(text)}</p>")
            para.clear()
    i=0
    while i < len(lines):
        line=lines[i]
        if not line.strip(): flush_para(); i+=1; continue
        if line.lstrip().startswith("|"):
            flush_para(); table,i=parse_table(lines,i); out.append(table); continue
        m=re.match(r"^(#{1,6})\s+(.+)$",line)
        if m:
            flush_para(); level=len(m.group(1)); out.append(f"<h{level}>{inline_markup(m.group(2))}</h{level}>"); i+=1; continue
        para.append(line); i+=1
    flush_para(); return "\n".join(out)


def page_shell(title: str, body: str, nav: str = "") -> str:
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Star Almanack</title><style>{CSS}</style></head><body><header><div class="wrap"><div class="brand"><a href="/almanack/2026/">Star Almanack</a></div><div class="subtitle">Alexander Ferrari Miller</div></div></header><main class="wrap">{nav}{body}{nav}</main><footer><div class="wrap">© 2026 Alexander Ferrari Miller. All rights reserved.</div></footer></body></html>'''


def week_nav(week: int) -> str:
    prev = f'<a href="../W{week-1:02d}/">← W{week-1:02d}</a>' if week > 1 else '<span>← Previous</span>'
    nxt = f'<a href="../W{week+1:02d}/">W{week+1:02d} →</a>' if week < 53 else '<span>Next →</span>'
    return f'<nav class="weeknav">{prev}<a href="../">All weeks</a>{nxt}</nav>'


def main() -> None:
    text = SOURCE.read_text(encoding="utf-8")
    matches = list(WEEK_RE.finditer(text))
    if len(matches) != 53: raise SystemExit(f"Expected 53 ISO week sections, found {len(matches)}")
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    week_links=[]
    for idx,match in enumerate(matches):
        week=int(match.group(2)); start=match.start()
        if idx+1 < len(matches):
            end=matches[idx+1].start()
        else:
            next_h2=H2_RE.search(text, match.end())
            end=next_h2.start() if next_h2 else len(text)
        section=text[start:end].strip(); fragment=markdown_fragment(section)
        target=OUT/f"W{week:02d}"; target.mkdir(parents=True)
        (target/"index.html").write_text(page_shell(f"ISO 2026-W{week:02d}",fragment,week_nav(week)),encoding="utf-8")
        week_links.append(f'<li><a href="W{week:02d}/">ISO 2026-W{week:02d}</a></li>')
    index_body='<h1>2026 Weekly Almanack</h1><p>Select an ISO week.</p><ul class="weekgrid">'+"".join(week_links)+"</ul>"
    (OUT/"index.html").write_text(page_shell("2026 Weekly Almanack",index_body),encoding="utf-8")
    print("Published 53 weekly pages to",OUT)


if __name__ == "__main__": main()