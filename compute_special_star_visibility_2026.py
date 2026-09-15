#!/usr/bin/env python3
"""Compute precise 2026 Star Almanack visibility dates for Special Stars.

Coordinates come from special-star-catalog.csv. The calculation reuses the
same observer-first visibility engine as the audited Bayer and bright-star
layers and normalizes annual occurrences into ISO week-year 2026.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

from compute_bayer_visibility_2026 import best_visibility, iso_date
from compute_bright_star_visibility_2026 import normalize_to_iso_2026

EXPECTED_SPECIAL_STARS = 24


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, nargs="?", default=Path("special-star-catalog.csv"))
    parser.add_argument("output", type=Path, nargs="?", default=Path("special-star-visibility-2026.csv"))
    args = parser.parse_args()

    with args.input.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit("Special Star coordinate catalog is empty")

    output = []
    for row in rows:
        ra = float(row["ra_h"])
        instant, date = best_visibility(ra)
        instant, date = normalize_to_iso_2026(ra, instant, date)
        enriched = dict(row)
        enriched["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
        enriched["best_date"] = date.isoformat()
        enriched["iso"] = iso_date(date)
        output.append(enriched)

    fieldnames = list(rows[0].keys()) + ["best_instant_utc", "best_date", "iso"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)

    if len(output) != EXPECTED_SPECIAL_STARS:
        raise SystemExit(f"Expected {EXPECTED_SPECIAL_STARS} Special Stars, got {len(output)}")
    bad = [r for r in output if __import__('datetime').date.fromisoformat(r['best_date']).isocalendar().year != 2026]
    if bad:
        raise SystemExit(f"Special Star dates outside ISO 2026: {[r['name'] for r in bad]}")

    print(f"Special Star coordinate rows: {EXPECTED_SPECIAL_STARS}")
    print("All best dates fall inside ISO 2026")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
