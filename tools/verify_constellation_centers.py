#!/usr/bin/env python3
"""Verify generated constellation-center events survived the full Almanack pipeline."""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
GENERATED = SRC / "generated"
ROOTS = (SRC / "site", ROOT / "almanack")


def parse_years() -> list[int]:
    parser = argparse.ArgumentParser(description="Verify Star Almanack constellation centers")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="Years to verify")
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years


def read_rows(year: int) -> list[dict[str, str]]:
    path = GENERATED / f"constellation-observance-{year}.csv"
    if not path.exists():
        raise SystemExit(f"Missing generated constellation table: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 89:
        raise SystemExit(f"{path}: expected 89 constellation-center rows, found {len(rows)}")
    return rows


def page_for_date(root: Path, day: dt.date) -> Path:
    iso = day.isocalendar()
    return root / str(iso.year) / f"W{iso.week:02d}" / "index.html"


def row_pattern(day: dt.date) -> re.Pattern[str]:
    label = day.strftime("%a, %b %d, %Y")
    return re.compile(
        rf"<tr><td>{re.escape(label)}</td><td>.*?</td><td>(.*?)</td></tr>"
    )


def verify_root(root: Path, rows: list[dict[str, str]], year: int) -> None:
    for row in rows:
        name = row["name"].strip()
        day = dt.date.fromisoformat(row["center_best_date"])
        page = page_for_date(root, day)
        if not page.exists():
            raise SystemExit(f"{year}: missing weekly page for {name}: {page}")
        text = page.read_text(encoding="utf-8")
        match = row_pattern(day).search(text)
        if not match:
            raise SystemExit(f"{year}: missing calendar row for {name} on {day} in {page}")
        items = match.group(1).split("<br>") if match.group(1) not in ("", "—") else []
        prefix = f"{name} center — Constellation — "
        count = sum(item.startswith(prefix) for item in items)
        if count != 1:
            raise SystemExit(
                f"{year}: expected {name} center exactly once on {day} in {page}, found {count}"
            )


def main() -> None:
    years = parse_years()
    for year in years:
        rows = read_rows(year)
        for root in ROOTS:
            verify_root(root, rows, year)
        print(f"{year}: constellation-center survival PASS — 89/89 source + 89/89 public")
    print(f"Constellation-center final-output regression PASS for: {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
