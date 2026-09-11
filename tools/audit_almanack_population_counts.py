#!/usr/bin/env python3
"""Star Almanack population-count audit for generated 2026 pages.

This complements the representative type-coverage regression.  It reports how
many unique members of each authoritative source population actually survive
into generated calendar cells.  Counts are deliberately reported before they
are frozen as hard expectations: the current Almanack is known to have missing
populations, so today's deficient output must not become the accepted baseline.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026
SRC = ROOT / "Star-Almanack-Repo"
SITE = ROOT / "almanack" / str(YEAR)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def calendar_html() -> str:
    chunks: list[str] = []
    for page in sorted(SITE.glob("W??/index.html")):
        text = page.read_text(encoding="utf-8")
        chunks.extend(
            re.findall(
                r'<table class="calendar">.*?</table>',
                text,
                flags=re.DOTALL,
            )
        )
    return "\n".join(chunks)


def present_token(html: str, token: str) -> bool:
    if not token:
        return False
    return token in html


def unique_values(rows: list[dict[str, str]], field: str) -> list[str]:
    return sorted({row.get(field, "").strip() for row in rows if row.get(field, "").strip()})


def count_named_population(html: str, names: list[str], suffix: str = "") -> tuple[int, int]:
    expected = len(names)
    rendered = sum(1 for name in names if present_token(html, f"{name}{suffix}"))
    return rendered, expected


def count_bayer_role(html: str, role: str) -> tuple[int, int]:
    rows = [row for row in read_csv(SRC / "expanded-bayer-visibility-2026.csv") if row.get("bayer_code") == role]
    # Prefer the proper name when one exists; otherwise the compact Bayer designation
    # is the stable rendered identity (for example β Cam).
    identities = [row.get("proper", "").strip() or row.get("bayer", "").strip() for row in rows]
    expected = len(identities)
    rendered = sum(1 for identity in identities if present_token(html, identity))
    return rendered, expected


def count_catalog_ids(html: str, path: Path, field: str) -> tuple[int, int]:
    ids = unique_values(read_csv(path), field)
    expected = len(ids)
    # Word-ish boundaries prevent M1 from being counted merely because M10 appears.
    rendered = 0
    for ident in ids:
        pattern = rf'(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])'
        if re.search(pattern, html):
            rendered += 1
    return rendered, expected


def count_event_phrase(html: str, phrase: str) -> int:
    return len(re.findall(re.escape(phrase), html, flags=re.IGNORECASE))


def show(label: str, rendered: int, expected: int | None = None) -> None:
    if expected is None:
        print(f"{label:<28} {rendered}")
        return
    status = "PASS" if rendered == expected else "INCOMPLETE"
    print(f"{label:<28} {rendered}/{expected}  {status}")


def run() -> int:
    html = calendar_html()
    if not html:
        raise SystemExit(f"No generated calendar pages found under {SITE}")

    constellation_rows = read_csv(SRC / "constellation-observance-2026.csv")
    asterism_rows = read_csv(SRC / "asterism-geometry-2026.csv")

    constellation_names = unique_values(constellation_rows, "name")
    asterism_names = unique_values(asterism_rows, "asterism")

    print("Star Almanack Population Count Audit")
    print("=" * 44)

    rendered, expected = count_named_population(html, constellation_names, " center")
    show("Constellation centers", rendered, expected)

    rendered, expected = count_named_population(html, asterism_names, " center")
    show("Asterism centers", rendered, expected)

    rendered, expected = count_bayer_role(html, "Alp")
    show("Alpha stars", rendered, expected)

    rendered, expected = count_bayer_role(html, "Bet")
    show("Beta stars", rendered, expected)

    rendered, expected = count_catalog_ids(html, SRC / "messier-visibility-2026.csv", "messier")
    show("Messier identities", rendered, expected)

    caldwell_catalog = SRC / "caldwell-catalog.csv"
    if caldwell_catalog.exists():
        rendered, expected = count_catalog_ids(html, caldwell_catalog, "caldwell")
        show("Caldwell identities", rendered, expected)

    finest_catalog = SRC / "finest-ngc-catalog.csv"
    if finest_catalog.exists():
        finest_rows = read_csv(finest_catalog)
        field = "catalog" if finest_rows and "catalog" in finest_rows[0] else "ngc"
        ids = unique_values(finest_rows, field)
        rendered = sum(
            1
            for ident in ids
            if ident and re.search(rf'(?<![A-Za-z0-9]){re.escape(ident)}(?![A-Za-z0-9])', html)
        )
        show("Finest NGC identities", rendered, len(ids))

    print("-")
    # Event counts are occurrence counts rather than unique catalog populations.
    show("Meteor-shower events", count_event_phrase(html, "meteor shower"))
    show("Solar-eclipse events", count_event_phrase(html, "solar eclipse"))
    show("Lunar-eclipse events", count_event_phrase(html, "lunar eclipse"))

    show("Naked-eye aid glyphs", html.count("eye.svg"))
    show("Binocular aid glyphs", html.count("binoculars.svg"))
    show("Telescope aid glyphs", html.count("telescope.svg"))

    print("=" * 44)
    print("NOTE: INCOMPLETE is diagnostic, not yet a CI failure.")
    print("Correct totals will be frozen only after the population generators are repaired.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
