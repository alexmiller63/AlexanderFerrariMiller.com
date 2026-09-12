#!/usr/bin/env python3
"""Verify generated constellation-center occurrences survive final generation.

Constellation centers recur once per astronomical Aries-to-Aries cycle. ISO
week-numbering years are not astronomical cycles: a given identity can appear
zero, one, or twice in an ISO year near the year boundary. The audit therefore
compares rendered output with the generated occurrence snapshot instead of
forcing 89 events into every ISO year.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
ROOTS = (SRC / "site", ROOT / "almanack")
EVENT_RE = re.compile(r"(?:^|<br>)([^<]*? center) — Constellation —")


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return (2026,)
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers") from exc


def expected_counts(year: int) -> Counter[str]:
    path = SRC / "generated" / f"constellation-observance-{year}.csv"
    if not path.exists():
        raise SystemExit(f"Missing generated constellation snapshot: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise SystemExit(f"{year}: generated constellation snapshot is empty")
    counts = Counter(row["name"].strip() for row in rows)
    if any(count not in (1, 2) for count in counts.values()):
        raise SystemExit(f"{year}: unexpected per-identity occurrence count: {counts}")
    return counts


def audit_root(root: Path, year: int, expected: Counter[str]) -> list[str]:
    failures: list[str] = []
    text = "\n".join(
        page.read_text(encoding="utf-8")
        for page in sorted((root / str(year)).glob("W??/index.html"))
    )
    found = Counter(EVENT_RE.findall(text))
    normalized_found = Counter()
    for token, count in found.items():
        name = token[:-7] if token.endswith(" center") else token
        normalized_found[name] += count

    if sum(normalized_found.values()) != sum(expected.values()):
        failures.append(
            f"{root}/{year}: expected {sum(expected.values())} constellation-center occurrences, "
            f"found {sum(normalized_found.values())}"
        )
    for name in sorted(set(expected) | set(normalized_found)):
        if normalized_found[name] != expected[name]:
            failures.append(
                f"{root}/{year}: {name} center occurs {normalized_found[name]} times; "
                f"expected {expected[name]}"
            )
    return failures


def main() -> None:
    failures: list[str] = []
    for year in requested_years():
        expected = expected_counts(year)
        year_failures: list[str] = []
        for root in ROOTS:
            year_failures.extend(audit_root(root, year, expected))
        failures.extend(year_failures)
        if not year_failures:
            print(
                f"{year}: PASS — {sum(expected.values())} generated constellation-center "
                f"occurrence(s) across {len(expected)} represented identities survive in "
                "source and public output"
            )
    if failures:
        print("CONSTELLATION-CENTER SURVIVAL REGRESSION FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
