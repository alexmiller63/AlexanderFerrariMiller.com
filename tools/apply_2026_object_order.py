#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "Star-Almanack-Repo" / "almanack-expanded.md",
    *sorted((ROOT / "almanack" / "2026").glob("W??/index.html")),
    *sorted((ROOT / "Star-Almanack-Repo" / "site" / "2026").glob("W??/index.html")),
]

BANDS = "Northern|Tropical|Southern"
SEASONS = "Spring|Summer|Autumn|Winter"
MESSIER_TYPES = (
    "Supernova Remnant|Globular Cluster|Open Cluster|Diffuse Nebula|"
    "Planetary Nebula|Asterism|Double Star|Milky Way|Spiral Galaxy|"
    "Barred Galaxy|Lenticular Galaxy|Elliptical Galaxy|Irregular Galaxy"
)

# Fixed stars: name — visibility — Declination Season
STAR = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS})(?=(?:<br>| \||</td>|$))"
)

# Messier: designation/name — object type — Declination Season — visibility
MESSIER = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<type>{MESSIER_TYPES}) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS}) — (?P<vis>👁|B|🔭)"
)

# Already-modernized but wrong order from the immediately preceding source edit.
STAR_SEASON_FIRST = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})(?=(?:<br>| \||</td>|$))"
)
MESSIER_SEASON_FIRST = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<vis>👁|B|🔭) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})"
)


def rewrite(text: str) -> str:
    text = MESSIER.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)
    text = STAR.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)
    text = MESSIER_SEASON_FIRST.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)
    text = STAR_SEASON_FIRST.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)
    return text


changed = 0
for path in TARGETS:
    if not path.exists():
        continue
    old = path.read_text(encoding="utf-8")
    new = rewrite(old)
    if new != old:
        path.write_text(new, encoding="utf-8")
        changed += 1

print(f"Standardized object order in {changed} files")
