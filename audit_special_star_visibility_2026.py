#!/usr/bin/env python3
"""Audit Special Star editorial dates against precise catalog coordinates.

The long-form editorial source remains special-stars.md. Coordinates are taken
from special-star-catalog.csv rather than the rounded RA/Dec printed in prose.
The current Star Almanack observer-first visibility engine then computes the
natural ISO-2026 placement and reports, but does not silently rewrite, stale
editorial dates.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path

from compute_bayer_visibility_2026 import best_visibility, iso_date
from compute_bright_star_visibility_2026 import normalize_to_iso_2026

MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ],
        1,
    )
}

HEADING_RE = re.compile(
    r"(?m)^### (?P<title>.+?) · (?P<season>.+?) · "
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December) "
    r"(?P<day>\d{1,2})\s*$"
)
COORD_RE = re.compile(
    r"\*\*RA (?P<h>\d+)h (?P<m>\d+)m · Dec (?P<dec>[+−\-]?\d+(?:\.\d+)?)° · mag (?P<mag>.+?)\*\*"
)
OBS_RE = re.compile(r"\*\*Observing:\s*(?P<obs>.*?)\*\*", re.S)


def compact(text: str) -> str:
    return " ".join(text.split())


def heading_name(title: str) -> str:
    """Return the observer-facing object name before designation/story qualifiers."""
    return title.split(" ---", 1)[0].strip()


def load_catalog(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 22:
        raise SystemExit(f"Expected 22 precise Special Star coordinate rows, got {len(rows)}")
    by_name = {row["name"]: row for row in rows}
    if len(by_name) != len(rows):
        raise SystemExit("Duplicate Special Star names in coordinate catalog")
    return by_name


def parse_special_stars(text: str, catalog: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    matches = list(HEADING_RE.finditer(text))
    rows: list[dict[str, str]] = []

    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        block = text[match.end():end]
        coord = COORD_RE.search(block)
        if coord is None:
            raise SystemExit(f"Missing printed RA/Dec line for Special Star heading: {match.group('title')}")
        obs = OBS_RE.search(block)
        if obs is None:
            raise SystemExit(f"Missing observing line for Special Star heading: {match.group('title')}")

        name = heading_name(match.group("title"))
        source = catalog.get(name)
        if source is None:
            raise SystemExit(f"No precise coordinate row for Special Star: {name}")

        stated_date = dt.date(2026, MONTHS[match.group("month")], int(match.group("day")))
        ra_h = float(source["ra_h"])
        instant, computed_date = best_visibility(ra_h)
        instant, computed_date = normalize_to_iso_2026(ra_h, instant, computed_date)

        rows.append(
            {
                "name": name,
                "title": match.group("title").strip(),
                "season": match.group("season").strip(),
                "stated_date": stated_date.isoformat(),
                "ra_h": source["ra_h"],
                "dec_deg": source["dec_deg"],
                "coordinate_source": source["coordinate_source"],
                "observing_aid": source["observing_aid"],
                "printed_magnitude": compact(coord.group("mag")),
                "printed_observing_text": compact(obs.group("obs")),
                "best_instant_utc": instant.strftime("%Y-%m-%d %H:%M"),
                "computed_date": computed_date.isoformat(),
                "iso": iso_date(computed_date),
                "status": "PASS" if computed_date == stated_date else "STALE_DATE",
            }
        )

    if len(rows) != 22:
        raise SystemExit(f"Expected 22 Special Star headings, got {len(rows)}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("editorial", type=Path, nargs="?", default=Path("special-stars.md"))
    parser.add_argument("catalog", type=Path, nargs="?", default=Path("special-star-catalog.csv"))
    parser.add_argument("output", type=Path, nargs="?", default=Path("special-star-visibility-audit-2026.csv"))
    args = parser.parse_args()

    catalog = load_catalog(args.catalog)
    rows = parse_special_stars(args.editorial.read_text(encoding="utf-8"), catalog)
    fieldnames = [
        "name", "title", "season", "stated_date", "ra_h", "dec_deg",
        "coordinate_source", "observing_aid", "printed_magnitude",
        "printed_observing_text", "best_instant_utc", "computed_date", "iso", "status",
    ]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    stale = [r for r in rows if r["status"] != "PASS"]
    print(f"Special Stars audited from precise coordinates: {len(rows)}")
    print(f"Dates matching current visibility rule: {len(rows) - len(stale)}")
    print(f"Dates requiring reconciliation: {len(stale)}")
    for row in stale:
        print(f"STALE {row['name']}: stated {row['stated_date']} -> computed {row['computed_date']}")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
