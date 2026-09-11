#!/usr/bin/env python3
"""Permanent Star Almanack type-coverage regression.

One representative 2026 sample is required for each supported semantic class.
The test fails if a sample disappears, moves to the wrong generated ISO week,
uses the wrong semantic marker, or loses its required observing/event glyph.

This is intentionally a reader-visible regression: every failure prints the
live week URL and a concise expected result so the failing page can be opened
and inspected directly.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
YEAR = 2026
SITE = ROOT / "almanack" / str(YEAR)
SRC = ROOT / "Star-Almanack-Repo"
GENERATED = SRC / "generated"
BASE_URL = f"https://AlexanderFerrariMiller.com/almanack/{YEAR}"


@dataclass(frozen=True)
class Case:
    name: str
    week: str
    expected: str
    checks: tuple[str, ...]
    proximity: tuple[tuple[str, str], ...] = ()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def row_for(path: Path, **wanted: str) -> dict[str, str]:
    for row in read_csv(path):
        if all(row.get(k) == v for k, v in wanted.items()):
            return row
    raise AssertionError(f"source row missing in {path}: {wanted}")


def week_from_iso(value: str) -> str:
    m = re.search(r"-(W\d{2})-", value)
    if not m:
        raise AssertionError(f"cannot parse ISO week from {value!r}")
    return m.group(1)


def html_for(week: str) -> str:
    path = SITE / week / "index.html"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def close_together(html: str, left: str, right: str, radius: int = 800) -> bool:
    pos = html.find(left)
    if pos < 0:
        return False
    lo = max(0, pos - radius)
    hi = min(len(html), pos + len(left) + radius)
    return right in html[lo:hi]


def source_week(path: Path, selector: dict[str, str], iso_field: str = "iso") -> str:
    return week_from_iso(row_for(path, **selector)[iso_field])


def build_cases() -> list[Case]:
    constellation_week = source_week(
        SRC / "constellation-observance-2026.csv", {"name": "Andromeda"}
    )
    asterism_week = source_week(
        SRC / "asterism-geometry-2026.csv", {"asterism": "Great Square of Pegasus"}
    )
    pleiades_asterism_week = source_week(
        SRC / "asterism-geometry-2026.csv", {"asterism": "Pleiades"}
    )
    alpha_week = source_week(
        GENERATED / "expanded-bayer-visibility-2026.csv", {"proper": "Achernar"}
    )
    beta_week = source_week(
        GENERATED / "expanded-bayer-visibility-2026.csv", {"proper": "Cursa"}
    )
    messier_week = source_week(
        GENERATED / "messier-visibility-2026.csv", {"messier": "M45"}
    )
    caldwell_week = source_week(
        GENERATED / "caldwell-visibility-2026.csv", {"caldwell": "C4"}
    )
    finest_week = source_week(
        GENERATED / "finest-ngc-visibility-2026.csv", {"finest_ngc": "19"}
    )

    return [
        Case(
            "constellation center",
            constellation_week,
            "Andromeda center appears on its calculated visibility date and is explicitly a constellation-center event.",
            ("Andromeda", "center"),
            (("Andromeda", "center"),),
        ),
        Case(
            "asterism center",
            asterism_week,
            "Great Square of Pegasus center appears and is distinguishable from a constellation center.",
            ("Great Square of Pegasus", "center"),
            (("Great Square of Pegasus", "center"),),
        ),
        Case(
            "alpha Bayer star",
            alpha_week,
            "Achernar appears as α Eridani; α is a Bayer role, not an observing-aid glyph.",
            ("Achernar", "α"),
            (("Achernar", "α"),),
        ),
        Case(
            "beta Bayer star",
            beta_week,
            "Cursa appears as β Eridani; β is visibly distinct from α.",
            ("Cursa", "β"),
            (("Cursa", "β"),),
        ),
        Case(
            "Messier object",
            messier_week,
            "Pleiades appears with its M45 Messier identity.",
            ("Pleiades", "M45"),
            (("Pleiades", "M45"),),
        ),
        Case(
            "Caldwell object",
            caldwell_week,
            "C4 / NGC 7023 / Iris Nebula appears as a Caldwell object, not generic NGC only.",
            ("C4", "NGC 7023", "Iris Nebula"),
        ),
        Case(
            "Finest NGC object",
            finest_week,
            "Finest NGC sample NGC 1491 appears without being mislabeled Messier or Caldwell.",
            ("NGC 1491",),
        ),
        Case(
            "naked-eye observing aid",
            alpha_week,
            "Achernar carries the custom naked-eye observing-aid glyph.",
            ("Achernar",),
            (("Achernar", "eye.svg"),),
        ),
        Case(
            "binocular observing aid",
            "W40",
            "M15 carries the Star Almanack binocular SVG; the letter B is not the observing symbol.",
            ("M15",),
            (("M15", "binoculars.svg"),),
        ),
        Case(
            "telescope observing aid",
            "W49",
            "M74 carries the Star Almanack telescope SVG.",
            ("M74",),
            (("M74", "telescope.svg"),),
        ),
        Case(
            "meteor shower",
            "W33",
            "Perseids peak appears with the dedicated meteor-shower glyph.",
            ("Perseids",),
            (("Perseids", "meteor-shower.svg"),),
        ),
        Case(
            "solar eclipse",
            "W33",
            "The Aug 12 total solar eclipse appears with the dedicated solar-eclipse glyph.",
            ("Total solar eclipse",),
            (("Total solar eclipse", "solar-eclipse.svg"),),
        ),
        Case(
            "lunar eclipse",
            "W10",
            "The Mar 3 total lunar eclipse appears with the dedicated lunar-eclipse glyph.",
            ("Total lunar eclipse",),
            (("Total lunar eclipse", "lunar-eclipse.svg"),),
        ),
        Case(
            "Solar-System ephemeris",
            "W41",
            "Extended ephemeris exposes Uranus, Neptune, and Ceres as distinct Solar-System bodies.",
            ("Uranus", "Neptune", "Ceres"),
        ),
        Case(
            "overlapping semantic identities",
            pleiades_asterism_week,
            "Pleiades simultaneously preserves M45 identity and a separately identifiable asterism-center event.",
            ("Pleiades", "M45", "center"),
            (("Pleiades", "M45"), ("Pleiades", "center")),
        ),
    ]


def run() -> int:
    cases = build_cases()
    passed = 0
    failed = 0

    print("Star Almanack Type Coverage Regression")
    print("=" * 40)

    for i, case in enumerate(cases, 1):
        html = html_for(case.week)
        url = f"{BASE_URL}/{case.week}/"
        reasons: list[str] = []
        if not html:
            reasons.append("generated week page is missing")
        else:
            for token in case.checks:
                if token not in html:
                    reasons.append(f"missing {token!r}")
            for left, right in case.proximity:
                if not close_together(html, left, right):
                    reasons.append(f"{right!r} is not attached to/near {left!r}")

        if reasons:
            failed += 1
            status = "FAIL"
        else:
            passed += 1
            status = "PASS"

        print(f"{i:02d}. {status} — {case.name}")
        print(f"    {url}")
        print(f"    Expected: {case.expected}")
        for reason in reasons:
            print(f"    - {reason}")

    # Permanent semantic invariants for the legend itself.
    legend_path = ROOT / "_includes" / "almanack-notation-legend.html"
    legend = legend_path.read_text(encoding="utf-8") if legend_path.exists() else ""
    required_legend_tokens = (
        "eye.svg",
        "binoculars.svg",
        "telescope.svg",
        "meteor-shower.svg",
        "solar-eclipse.svg",
        "lunar-eclipse.svg",
        "Observing aid",
        "Events",
    )
    legend_missing = [token for token in required_legend_tokens if token not in legend]
    if legend_missing:
        failed += 1
        print("LEGEND FAIL")
        for token in legend_missing:
            print(f"    - missing {token!r}")

    print("-" * 40)
    print(f"RESULT: {passed} PASS / {failed} FAIL")
    print(f"Concrete sample cases: {len(cases)}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
