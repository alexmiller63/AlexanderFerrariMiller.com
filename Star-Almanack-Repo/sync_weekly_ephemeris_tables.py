#!/usr/bin/env python3
"""Synchronize Almanack week sections from weekly-ephemeris-2026.csv.

The familiar 7-body table is retained for compact/mobile readability. Uranus,
Neptune, and Ceres appear immediately below it as an Extended targets table in
the same Weekly Solar-System Ephemeris section.

By default this updates almanack.md, whose historical source contains only the
early ISO weeks. A different Markdown target can be supplied as argv[1], which
allows the same code to synchronize the generated 53-week expanded Almanack.
"""
from __future__ import annotations

import csv
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
EPHEMERIS = ROOT / "weekly-ephemeris-2026.csv"

PRIMARY = [
    ("☉ Sun", "sun"),
    ("☽ Moon", "moon"),
    ("☿ Mercury", "mercury"),
    ("♀ Venus", "venus"),
    ("♂ Mars", "mars"),
    ("♃ Jupiter", "jupiter"),
    ("♄ Saturn", "saturn"),
]
EXTENDED = [
    ("♅ Uranus", "uranus"),
    ("♆ Neptune", "neptune"),
    ("⚳ Ceres", "ceres"),
]


def table(columns, row):
    return (
        "| " + " | ".join(label for label, _ in columns) + " |\n\n"
        "|" + "|".join("---:" for _ in columns) + "|\n\n"
        "| " + " | ".join(row[key] for _, key in columns) + " |"
    )


def replacement(row):
    monday = date.fromisoformat(row["monday_utc"])
    return (
        "### Weekly Solar-System Ephemeris\n\n"
        f"**Snapshot:** Monday, {monday:%b} {monday.day}, {monday.year} · 00:00 UTC\n\n"
        + table(PRIMARY, row)
        + "\n\n**Extended targets:**\n\n"
        + table(EXTENDED, row)
        + "\n\n"
    )


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "almanack.md"
    with EPHEMERIS.open(encoding="utf-8", newline="") as f:
        rows = {row["iso_week"]: row for row in csv.DictReader(f)}
    if len(rows) != 53:
        raise SystemExit(f"Expected 53 ephemeris rows, found {len(rows)}")
    for key, row in rows.items():
        for required in ("uranus", "neptune", "ceres"):
            if not row.get(required):
                raise SystemExit(f"{key} is missing {required}")

    text = target.read_text(encoding="utf-8")
    # Keep the source introduction consistent with the expanded builder's
    # terminology after adding Uranus, Neptune, and Ceres.
    text = text.replace("53 weekly classical-planet snapshots", "53 weekly Solar-System snapshots")

    weeks = [int(x) for x in re.findall(r"(?m)^## ISO 2026-W(\d{2})\s*$", text)]
    if not weeks:
        raise SystemExit(f"No ISO 2026 week sections found in {target}")

    changed = 0
    for week in weeks:
        key = f"2026-W{week:02d}"
        section_re = re.compile(
            rf"(?ms)(^## ISO {re.escape(key)}\s*$.*?)(^### Weekly (?:Classical-Planet|Solar-System) Ephemeris\s*$.*?)(?=^### Sky Note\s*$)"
        )
        match = section_re.search(text)
        if not match:
            raise SystemExit(f"Could not locate ephemeris section for {key} in {target}")
        text = text[:match.start()] + match.group(1) + replacement(rows[key]) + text[match.end():]
        changed += 1

    target.write_text(text, encoding="utf-8")
    print(f"Synchronized {changed} weekly Solar-System ephemeris sections in {target}")


if __name__ == "__main__":
    main()
