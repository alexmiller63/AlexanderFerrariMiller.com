#!/usr/bin/env python3
"""Wire calculated 2026 eclipse data into Almanack calendar pages and eclipse page."""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ECLIPSE_SOURCE = ROOT / "Star-Almanack-Repo" / "eclipse.yaml"
ALMANACK_SOURCE = ROOT / "Star-Almanack-Repo" / "almanack-expanded.md"
SOURCE_SITE = ROOT / "Star-Almanack-Repo" / "site" / "2026"
PUBLIC_SITE = ROOT / "almanack" / "2026"
ECLIPSE_PAGE = ROOT / "star-almanack" / "eclipses.html"


def parse_eclipses(text: str) -> list[dict[str, str]]:
    out = []
    blocks = re.split(r"(?m)^  - id: ", text)[1:]
    for block in blocks:
        get = lambda key: re.search(rf"(?m)^    {re.escape(key)}: ?\"?([^\"\n]+)\"?$", block)
        kind = get("kind").group(1).strip()
        typ = get("type").group(1).strip()
        day = get("date").group(1).strip()
        maximum = get("maximum_geometry_utc").group(1).strip()
        out.append({"kind": kind, "type": typ, "date": day, "maximum": maximum})
    if len(out) != 4:
        raise SystemExit(f"Expected 4 eclipses in eclipse.yaml, found {len(out)}")
    return out


def label(e: dict[str, str]) -> str:
    symbol = "☀" if e["kind"] == "solar" else "☾"
    return f"{symbol} {e['type'].title()} {e['kind']} eclipse — greatest {e['maximum'][:5]} UTC"


def update_markdown(text: str, e: dict[str, str]) -> str:
    d = date.fromisoformat(e["date"])
    day = d.strftime("%a, %b %d, %Y")
    event = label(e)
    pat = re.compile(rf"(?m)^(\| {re.escape(day)} \| [^|]+ \| )([^|]*)( \|)$")
    m = pat.search(text)
    if not m:
        raise SystemExit(f"Calendar row not found for {e['date']}")
    existing = m.group(2).strip()
    if event in existing:
        return text
    new = event if existing in ("", "—") else event + "<br>" + existing
    return text[:m.start()] + m.group(1) + new + m.group(3) + text[m.end():]


def update_html(text: str, e: dict[str, str]) -> str:
    d = date.fromisoformat(e["date"])
    day = d.strftime("%a, %b %d, %Y")
    event = label(e)
    pat = re.compile(rf"(<tr><td>{re.escape(day)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
    m = pat.search(text)
    if not m:
        raise SystemExit(f"HTML calendar row not found for {e['date']}")
    existing = m.group(2)
    if event in existing:
        return text
    new = event if existing.strip() in ("", "—") else event + "<br>" + existing
    return text[:m.start()] + m.group(1) + new + m.group(3) + text[m.end():]


def page_table(eclipses: list[dict[str, str]]) -> str:
    rows = []
    for e in eclipses:
        d = date.fromisoformat(e["date"])
        rows.append(
            f"<tr><td>{d.strftime('%B %-d, %Y')}</td><td>{e['type'].title()} {e['kind']}</td>"
            f"<td>{e['maximum'][:5]} UTC</td></tr>"
        )
    return "<table><thead><tr><th>Date</th><th>Eclipse</th><th>Greatest eclipse</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def update_eclipse_page(text: str, eclipses: list[dict[str, str]]) -> str:
    table = page_table(eclipses)
    start = "      <h2>2026 eclipses</h2>"
    block = start + "\n      " + table
    if start in text:
        text = re.sub(r"      <h2>2026 eclipses</h2>.*?(?=\n\s*<h2>|\n\s*</section>)", block, text, count=1, flags=re.S)
    else:
        marker = "      <h2>Publication and research remain separate</h2>"
        if marker not in text:
            raise SystemExit("Expected eclipse-page insertion marker not found")
        text = text.replace(marker, block + "\n\n" + marker, 1)
    text = text.replace(
        "The next implementation step is to connect this page to generated eclipse data from the Star Almanack calculation repository.",
        "The 2026 eclipse list above is generated from the Star Almanack calculation data; validation and precision work continue separately."
    )
    return text


def main() -> None:
    eclipses = parse_eclipses(ECLIPSE_SOURCE.read_text(encoding="utf-8"))

    source = ALMANACK_SOURCE.read_text(encoding="utf-8")
    for e in eclipses:
        source = update_markdown(source, e)
    ALMANACK_SOURCE.write_text(source, encoding="utf-8")

    for e in eclipses:
        week = date.fromisoformat(e["date"]).isocalendar().week
        for root in (SOURCE_SITE, PUBLIC_SITE):
            page = root / f"W{week:02d}" / "index.html"
            text = page.read_text(encoding="utf-8")
            page.write_text(update_html(text, e), encoding="utf-8")

    page_text = ECLIPSE_PAGE.read_text(encoding="utf-8")
    ECLIPSE_PAGE.write_text(update_eclipse_page(page_text, eclipses), encoding="utf-8")

    for e in eclipses:
        token = label(e)
        assert token in ALMANACK_SOURCE.read_text(encoding="utf-8")
    print("Wired 4 calculated 2026 eclipses into calendar source, weekly pages, and eclipse page; PASS")


if __name__ == "__main__":
    main()
