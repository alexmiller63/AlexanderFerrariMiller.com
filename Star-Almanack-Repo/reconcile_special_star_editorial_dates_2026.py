#!/usr/bin/env python3
"""Reconcile Special Star editorial heading dates to the precise 2026 visibility catalog.

This is deliberately narrow: it changes only the month/day in each `###` Special Star
heading. Long-form prose, season labels, coordinates printed for readers, and observing
text are left untouched for separate editorial review.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
from pathlib import Path

HEADING_RE = re.compile(
    r"(?m)^### (?P<title>.+?) · (?P<season>.+?) · "
    r"(?P<month>January|February|March|April|May|June|July|August|September|October|November|December) "
    r"(?P<day>\d{1,2})\s*$"
)


def heading_name(title: str) -> str:
    # Editorial headings append designations/explanatory subtitles with ` --- `.
    return title.split(" --- ", 1)[0].strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("editorial", type=Path, nargs="?", default=Path("special-stars.md"))
    parser.add_argument("visibility", type=Path, nargs="?", default=Path("special-star-visibility-2026.csv"))
    args = parser.parse_args()

    text = args.editorial.read_text(encoding="utf-8")
    with args.visibility.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    dates = {row["name"]: dt.date.fromisoformat(row["best_date"]) for row in rows}
    if len(dates) != 22:
        raise SystemExit(f"Expected 22 precise Special Star rows, got {len(dates)}")

    seen: set[str] = set()
    changed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        name = heading_name(match.group("title"))
        if name not in dates:
            raise SystemExit(f"No precise visibility row for Special Star heading: {match.group('title')}")
        if name in seen:
            raise SystemExit(f"Duplicate Special Star editorial heading: {name}")
        seen.add(name)

        date = dates[name]
        new_heading = f"### {match.group('title')} · {match.group('season')} · {date.strftime('%B')} {date.day}"
        if new_heading != match.group(0):
            changed += 1
        return new_heading

    reconciled = HEADING_RE.sub(replace, text)

    missing = set(dates) - seen
    if missing:
        raise SystemExit(f"Precise Special Stars missing from editorial source: {sorted(missing)}")
    if len(seen) != 22:
        raise SystemExit(f"Expected 22 Special Star headings, matched {len(seen)}")

    args.editorial.write_text(reconciled, encoding="utf-8")
    print(f"Special Star headings reconciled: {len(seen)}")
    print(f"Editorial dates changed: {changed}")


if __name__ == "__main__":
    main()
