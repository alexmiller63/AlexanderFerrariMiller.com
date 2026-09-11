#!/usr/bin/env python3
"""Wire independently calculated eclipse data into Almanack year pages.

The historical filename is retained so existing workflows keep working, but
publication is year-parameterized. Pass one or more eclipse YAML files;
with no arguments the preserved 2026 Star-Almanack-Repo/eclipse.yaml is used.
"""
from __future__ import annotations

import html
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ECLIPSE_SOURCE = ROOT / "Star-Almanack-Repo" / "eclipse.yaml"
ALMANACK_SOURCE = ROOT / "Star-Almanack-Repo" / "almanack-expanded.md"
ECLIPSE_PAGE = ROOT / "star-almanack" / "eclipses.html"

GLYPHS = {
    "solar": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/solar-eclipse.svg" alt="Solar eclipse" aria-label="Solar eclipse">',
    "lunar": '<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/lunar-eclipse.svg" alt="Lunar eclipse" aria-label="Lunar eclipse">',
}


def parse_year(text: str) -> int:
    m = re.search(r"(?m)^year:\s*(\d{4})\s*$", text)
    if not m:
        raise SystemExit("Eclipse source is missing a top-level year: value")
    return int(m.group(1))


def parse_eclipses(text: str, year: int) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    blocks = re.split(r"(?m)^  - id: ", text)[1:]
    for block in blocks:
        def required(key: str) -> str:
            m = re.search(rf"(?m)^    {re.escape(key)}: ?\"?([^\"\n]+)\"?$", block)
            if not m:
                raise SystemExit(f"Eclipse entry is missing {key}")
            return m.group(1).strip()

        def optional(key: str) -> str:
            m = re.search(rf"(?m)^    {re.escape(key)}: ?\"?([^\"\n]+)\"?$", block)
            return m.group(1).strip() if m else ""

        kind = required("kind")
        typ = required("type")
        day = required("date")
        maximum = required("maximum_geometry_utc")
        if date.fromisoformat(day).year != year:
            raise SystemExit(f"Eclipse {day} does not belong to declared year {year}")
        out.append({
            "kind": kind,
            "type": typ,
            "date": day,
            "maximum": maximum,
            "magnitude": optional("magnitude"),
            "visibility": optional("visibility"),
            "observing_note": optional("observing_note"),
        })
    if not out:
        raise SystemExit(f"No eclipses found for {year}")
    return out


def details(e: dict[str, str]) -> list[str]:
    parts = [f"greatest eclipse {e['maximum'][:5]} UTC"]
    if e.get("magnitude"):
        parts.append(f"magnitude {e['magnitude']}")
    if e.get("visibility"):
        parts.append(f"visibility: {e['visibility']}")
    if e.get("observing_note"):
        parts.append(f"observing: {e['observing_note']}")
    return parts


def label(e: dict[str, str], html_output: bool = True) -> str:
    glyph = GLYPHS[e["kind"]] if html_output else ("☀" if e["kind"] == "solar" else "☾")
    body = " · ".join(details(e))
    return f"{glyph} {e['type'].title()} {e['kind']} eclipse · {body}"


def update_markdown(text: str, e: dict[str, str]) -> str:
    d = date.fromisoformat(e["date"])
    day = d.strftime("%a, %b %d, %Y")
    event = label(e, html_output=False)
    pat = re.compile(rf"(?m)^(\| {re.escape(day)} \| [^|]+ \| )([^|]*)( \|)$")
    m = pat.search(text)
    if not m:
        raise SystemExit(f"Calendar row not found for {e['date']}")
    existing = m.group(2).strip()
    parts = [] if existing in ("", "—") else [p for p in existing.split("<br>") if " eclipse " not in p]
    new = "<br>".join([event] + parts)
    return text[:m.start()] + m.group(1) + new + m.group(3) + text[m.end():]


def update_html(text: str, e: dict[str, str]) -> str:
    d = date.fromisoformat(e["date"])
    day = d.strftime("%a, %b %d, %Y")
    event = label(e, html_output=True)
    pat = re.compile(rf"(<tr><td>{re.escape(day)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
    m = pat.search(text)
    if not m:
        raise SystemExit(f"HTML calendar row not found for {e['date']}")
    existing = m.group(2)
    parts = [] if existing.strip() in ("", "—") else [p for p in existing.split("<br>") if " eclipse " not in p]
    new = "<br>".join([event] + parts)
    return text[:m.start()] + m.group(1) + new + m.group(3) + text[m.end():]


def page_table(eclipses: list[dict[str, str]]) -> str:
    rows = []
    for e in eclipses:
        d = date.fromisoformat(e["date"])
        visibility = html.escape(e.get("visibility", "")) or "—"
        magnitude = html.escape(e.get("magnitude", "")) or "—"
        observing = html.escape(e.get("observing_note", "")) or "—"
        rows.append(
            f"<tr><td>{d.strftime('%B')} {d.day}, {d.year}</td><td>{e['type'].title()} {e['kind']}</td>"
            f"<td>{e['maximum'][:5]} UTC</td><td>{magnitude}</td><td>{visibility}</td><td>{observing}</td></tr>"
        )
    return (
        "<table><thead><tr><th>Date</th><th>Eclipse</th><th>Greatest eclipse</th><th>Magnitude</th>"
        "<th>Visibility</th><th>Observing note</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
    )


def update_eclipse_page(text: str, year: int, eclipses: list[dict[str, str]]) -> str:
    table = page_table(eclipses)
    start = f"      <h2>{year} eclipses</h2>"
    block = start + "\n      " + table
    if start in text:
        return re.sub(
            rf"      <h2>{year} eclipses</h2>.*?(?=\n\s*<h2>|\n\s*</section>)",
            block,
            text,
            count=1,
            flags=re.S,
        )

    headings = list(re.finditer(r"      <h2>(\d{4}) eclipses</h2>", text))
    for heading in headings:
        if int(heading.group(1)) > year:
            return text[:heading.start()] + block + "\n\n" + text[heading.start():]

    marker = "      <h2>Publication and research remain separate</h2>"
    if marker not in text:
        raise SystemExit("Expected eclipse-page insertion marker not found")
    return text.replace(marker, block + "\n\n" + marker, 1)


def publish(source_path: Path) -> tuple[int, int]:
    source_text = source_path.read_text(encoding="utf-8")
    year = parse_year(source_text)
    eclipses = parse_eclipses(source_text, year)

    if year == 2026:
        source = ALMANACK_SOURCE.read_text(encoding="utf-8")
        for e in eclipses:
            source = update_markdown(source, e)
        ALMANACK_SOURCE.write_text(source, encoding="utf-8")

    source_site = ROOT / "Star-Almanack-Repo" / "site" / str(year)
    public_site = ROOT / "almanack" / str(year)
    for e in eclipses:
        iso_year, week, _ = date.fromisoformat(e["date"]).isocalendar()
        for root in (source_site if iso_year == year else ROOT / "Star-Almanack-Repo" / "site" / str(iso_year), public_site if iso_year == year else ROOT / "almanack" / str(iso_year)):
            page = root / f"W{week:02d}" / "index.html"
            if not page.exists():
                raise SystemExit(f"Missing Almanack week page: {page}")
            text = page.read_text(encoding="utf-8")
            page.write_text(update_html(text, e), encoding="utf-8")

    page_text = ECLIPSE_PAGE.read_text(encoding="utf-8")
    ECLIPSE_PAGE.write_text(update_eclipse_page(page_text, year, eclipses), encoding="utf-8")
    print(f"{year}: wired {len(eclipses)} eclipses with magnitude, visibility, and observing details; PASS")
    return year, len(eclipses)


def main() -> None:
    paths = [Path(x) for x in sys.argv[1:]] or [DEFAULT_ECLIPSE_SOURCE]
    total = 0
    years = []
    for path in paths:
        year, count = publish(path)
        years.append(str(year))
        total += count
    print(f"Eclipse publication parameterized for {', '.join(years)}; {total} event(s) total")


if __name__ == "__main__":
    main()