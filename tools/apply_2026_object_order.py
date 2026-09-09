#!/usr/bin/env python3
from pathlib import Path
import csv
import json
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FIXED_OBJECTS = ROOT / "Star-Almanack-Repo" / "fixed-objects.yaml"
EDITORIAL_DATA = ROOT / "Star-Almanack-Repo" / "messier-editorial.json"

BANDS = "Northern|Tropical|Southern"
SEASONS = "Spring|Summer|Autumn|Winter"

ROW_RE = re.compile(
    r"(?m)^(\| (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Z][a-z]{2}) (\d{2}), (20\d{2}) \| [^|]+ \| )([^|]*)( \|)$"
)
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
)}

STAR = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS})(?=(?:<br>| \||</td>|$))"
)
STAR_WITH_DASH = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<band>{BANDS}) — (?P<season>{SEASONS})(?=(?:<br>| \||</td>|$))"
)
STAR_SEASON_FIRST = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})(?=(?:<br>| \||</td>|$))"
)
BAND_SEASON_WITH_DASH = re.compile(rf"\b(?P<band>{BANDS}) — (?P<season>{SEASONS})\b")

MESSIER_CALENDAR = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<vis>👁|B|🔭) — "
    rf"(?P<band>{BANDS})(?: —)? (?P<season>{SEASONS})"
)
MESSIER_CALENDAR_OLD = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<type>[^—<|]+?) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS}) — (?P<vis>👁|B|🔭)"
)
MESSIER_SEASON_FIRST = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<vis>👁|B|🔭) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})"
)

KNOWN_PROSE_TYPES = (
    "supernova remnant|globular cluster|open cluster|diffuse nebula|"
    "emission nebula|emission and reflection nebula|reflection nebula|"
    "planetary nebula|asterism|double star|Milky Way star cloud|"
    "spiral galaxy|barred spiral galaxy|lenticular galaxy|elliptical galaxy|"
    "irregular galaxy"
)
MESSIER_PROSE_NAMED = re.compile(
    rf"\b(M(?:110|10\d|[1-9]\d?)), the [^,.;<]+, (?:an? )?(?:{KNOWN_PROSE_TYPES})"
)
MESSIER_PROSE_NGC = re.compile(
    rf"\b(M(?:110|10\d|[1-9]\d?)) \((?:NGC|IC) [^)]+\), (?:an? )?(?:{KNOWN_PROSE_TYPES})"
)


def parse_years() -> list[int]:
    if len(sys.argv) == 1:
        return [2026]
    years: list[int] = []
    for raw in sys.argv[1:]:
        year = int(raw)
        if not 1900 <= year <= 2100:
            raise SystemExit(f"Unsupported year: {year}")
        if year not in years:
            years.append(year)
    return years


def targets(years: list[int]) -> list[Path]:
    paths = [ROOT / "Star-Almanack-Repo" / "almanack-expanded.md"]
    for year in years:
        paths.extend(sorted((ROOT / "almanack" / str(year)).glob("W??/index.html")))
        paths.extend(sorted((ROOT / "Star-Almanack-Repo" / "site" / str(year)).glob("W??/index.html")))
    return paths


def load_editorial_data() -> dict:
    data = json.loads(EDITORIAL_DATA.read_text(encoding="utf-8"))
    required = {"baseline_provenance", "type_labels", "constellation_labels", "objects"}
    missing = required - set(data)
    if missing:
        raise SystemExit(f"Messier editorial data missing keys: {sorted(missing)}")
    return data


EDITORIAL = load_editorial_data()


def load_messier_catalog() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    in_messier = False
    for raw in FIXED_OBJECTS.read_text(encoding="utf-8").splitlines():
        if raw == "messier:":
            in_messier = True
            continue
        if in_messier and raw and not raw.startswith(" "):
            break
        if not in_messier:
            continue
        m = re.match(r"\s*-\s*\[(.*)\]\s*$", raw)
        if not m:
            continue
        row = next(csv.reader([m.group(1)], skipinitialspace=True))
        if len(row) < 5 or not re.fullmatch(r"M\d{1,3}", row[0].strip()):
            continue
        designation = row[0].strip().upper()
        catalog_name = row[2].strip()
        if catalog_name.casefold() == "null":
            catalog_name = None
        catalog_type = row[3].strip()
        con_code = row[4].strip()
        object_editorial = EDITORIAL["objects"].get(designation, {})
        name = object_editorial.get("accepted_name", catalog_name)
        editorial_type = object_editorial.get("editorial_type", EDITORIAL["type_labels"].get(catalog_type))
        if not editorial_type:
            raise SystemExit(f"No editorial type for {designation} catalog type {catalog_type}")
        constellation = EDITORIAL["constellation_labels"].get(con_code)
        if not constellation:
            raise SystemExit(f"No constellation label for {designation}: {con_code}")
        provenance = object_editorial.get("provenance", [EDITORIAL["baseline_provenance"]])
        if not provenance:
            raise SystemExit(f"No provenance for {designation}")
        catalog[designation] = {
            "name": name,
            "catalog_type": catalog_type,
            "type": editorial_type,
            "constellation": constellation,
            "provenance": provenance,
        }
    if len(catalog) != 110:
        raise SystemExit(f"Expected 110 Messier source objects, found {len(catalog)}")
    return catalog


CATALOG = load_messier_catalog()


def canonical_messier(designation: str) -> str:
    designation = designation.upper()
    info = CATALOG[designation]
    number = designation[1:]
    lead = f"{info['name']} ({designation})" if info["name"] else f"Messier {number} ({designation})"
    return f"{lead}, {info['type']} in {info['constellation']}"


def designation_from_head(head: str) -> str:
    m = re.match(r"M\d{1,3}", head.strip(), flags=re.I)
    if not m:
        raise ValueError(head)
    return m.group(0).upper()


def rewrite(text: str) -> str:
    text = STAR.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} {m.group('season')}", text)
    text = STAR_WITH_DASH.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} {m.group('season')}", text)
    text = STAR_SEASON_FIRST.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} {m.group('season')}", text)

    def cal(m: re.Match[str]) -> str:
        designation = designation_from_head(m.group('head'))
        return f"{canonical_messier(designation)} — {m.group('vis')} — {m.group('band')} {m.group('season')}"

    text = MESSIER_CALENDAR_OLD.sub(cal, text)
    text = MESSIER_SEASON_FIRST.sub(cal, text)
    text = MESSIER_CALENDAR.sub(cal, text)
    text = BAND_SEASON_WITH_DASH.sub(lambda m: f"{m.group('band')} {m.group('season')}", text)
    text = MESSIER_PROSE_NAMED.sub(lambda m: canonical_messier(m.group(1)), text)
    text = MESSIER_PROSE_NGC.sub(lambda m: canonical_messier(m.group(1)), text)
    return text


def main() -> None:
    years = parse_years()
    changed = 0
    for path in targets(years):
        if not path.exists():
            continue
        old = path.read_text(encoding="utf-8")
        new = rewrite(old)
        if new != old:
            path.write_text(new, encoding="utf-8")
            changed += 1
    print(f"Standardized object order and Messier labels in {changed} files for years: {' '.join(map(str, years))}")


if __name__ == "__main__":
    main()
