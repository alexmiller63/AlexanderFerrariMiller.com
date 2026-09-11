#!/usr/bin/env python3
"""Verify that all Almanack constellation-center events survive final generation.

There are 88 IAU constellations, but the Almanack emits 89 center events because
Serpens is represented by separate Caput and Cauda centers.
"""
from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
ROOTS = (SRC / "site", ROOT / "almanack")
EXPECTED_EVENTS = 89
EXPECTED_CONSTELLATIONS = 88
EVENT_RE = re.compile(r"(?:^|<br>)([^<]*? center) — Constellation —")


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return (2026,)
    try:
        return tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers") from exc


def expected_names(year: int) -> list[str]:
    path = SRC / "generated" / f"constellation-observance-{year}.csv"
    if not path.exists():
        raise SystemExit(f"Missing generated constellation snapshot: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    names = [row["name"].strip() for row in rows]
    if len(names) != EXPECTED_EVENTS or len(set(names)) != EXPECTED_EVENTS:
        raise SystemExit(
            f"{year}: expected {EXPECTED_EVENTS} distinct center rows, got "
            f"{len(names)} rows / {len(set(names))} distinct names"
        )
    if "Serpens Caput" not in names or "Serpens Cauda" not in names:
        raise SystemExit(f"{year}: Serpens Caput/Cauda split is missing")
    return names


def audit_root(root: Path, year: int, names: list[str]) -> list[str]:
    failures: list[str] = []
    text = "\n".join(
        page.read_text(encoding="utf-8")
        for page in sorted((root / str(year)).glob("W??/index.html"))
    )
    found = EVENT_RE.findall(text)
    if len(found) != EXPECTED_EVENTS:
        failures.append(
            f"{root}/{year}: expected {EXPECTED_EVENTS} constellation-center events, found {len(found)}"
        )
    for name in names:
        token = f"{name} center — Constellation —"
        count = text.count(token)
        if count != 1:
            failures.append(f"{root}/{year}: {token!r} occurs {count} times; expected 1")
    return failures


def main() -> None:
    failures: list[str] = []
    for year in requested_years():
        names = expected_names(year)
        # 88 IAU constellations are represented by these 89 Almanack center events:
        # Serpens contributes two named component centers instead of one.
        represented = EXPECTED_EVENTS - 1
        if represented != EXPECTED_CONSTELLATIONS:
            failures.append(f"internal invariant failure: {represented} != {EXPECTED_CONSTELLATIONS}")
        for root in ROOTS:
            failures.extend(audit_root(root, year, names))
        if not failures:
            print(
                f"{year}: PASS — {EXPECTED_CONSTELLATIONS} constellations represented by "
                f"{EXPECTED_EVENTS} center events (Serpens Caput + Cauda), surviving in source and public output"
            )
    if failures:
        print("CONSTELLATION-CENTER SURVIVAL REGRESSION FAILED")
        for failure in failures:
            print(f"FAIL: {failure}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
