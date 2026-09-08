#!/usr/bin/env python3
from pathlib import Path
import csv
import re

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "Star-Almanack-Repo" / "almanack-expanded.md",
    *sorted((ROOT / "almanack" / "2026").glob("W??/index.html")),
    *sorted((ROOT / "Star-Almanack-Repo" / "site" / "2026").glob("W??/index.html")),
]
FIXED_OBJECTS = ROOT / "Star-Almanack-Repo" / "fixed-objects.yaml"

BANDS = "Northern|Tropical|Southern"
SEASONS = "Spring|Summer|Autumn|Winter"
TYPE_NAMES = {
    "SN": "supernova remnant",
    "GC": "globular cluster",
    "OC": "open cluster",
    "DN": "diffuse nebula",
    "PN": "planetary nebula",
    "AS": "asterism",
    "DS": "double star",
    "MW": "Milky Way star cloud",
    "SG": "spiral galaxy",
    "BG": "barred galaxy",
    "LG": "lenticular galaxy",
    "EG": "elliptical galaxy",
    "IG": "irregular galaxy",
}
CONSTELLATIONS = {
    "And": "Andromeda", "Aqr": "Aquarius", "Aur": "Auriga", "CMa": "Canis Major",
    "Cnc": "Cancer", "CVn": "Canes Venatici", "Cap": "Capricornus", "Cas": "Cassiopeia",
    "Cet": "Cetus", "Com": "Coma Berenices", "Cyg": "Cygnus", "Dra": "Draco",
    "Gem": "Gemini", "Her": "Hercules", "Hya": "Hydra", "Leo": "Leo", "Lep": "Lepus",
    "Lyr": "Lyra", "Mon": "Monoceros", "Oph": "Ophiuchus", "Ori": "Orion",
    "Peg": "Pegasus", "Per": "Perseus", "Psc": "Pisces", "Pup": "Puppis",
    "Sge": "Sagitta", "Sgr": "Sagittarius", "Sco": "Scorpius", "Sct": "Scutum",
    "Ser": "Serpens", "Tau": "Taurus", "Tri": "Triangulum", "UMa": "Ursa Major",
    "Vir": "Virgo", "Vul": "Vulpecula",
}
# Reader-facing common-name corrections. None means the object is treated as unnamed.
NAME_OVERRIDES = {
    "M15": None,
    "M42": "Orion Nebula",
}

ROW_RE = re.compile(
    r"(?m)^(\| (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Z][a-z]{2}) (\d{2}), (2025|2026|2027) \| [^|]+ \| )([^|]*)( \|)$"
)
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
)}

# Fixed stars: name — visibility — Declination — Season
STAR = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS})(?=(?:<br>| \||</td>|$))"
)
STAR_SEASON_FIRST = re.compile(
    rf"(?P<head>(?:(?!<br>|\|).)+?) — (?P<vis>(?:👁|B|🔭) V \d+) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})(?=(?:<br>| \||</td>|$))"
)

# Existing calendar forms, including old designation/name labels.
MESSIER_CALENDAR = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<vis>👁|B|🔭) — "
    rf"(?P<band>{BANDS}) — (?P<season>{SEASONS})"
)
MESSIER_CALENDAR_OLD = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<type>[^—<|]+?) — "
    rf"(?P<band>{BANDS}) (?P<season>{SEASONS}) — (?P<vis>👁|B|🔭)"
)
MESSIER_SEASON_FIRST = re.compile(
    rf"(?P<head>M\d{{1,3}}(?: [^—<|]+?)?) — (?P<vis>👁|B|🔭) — "
    rf"(?P<season>{SEASONS}) — (?P<band>{BANDS})"
)

# Sky-note forms emitted by the previous expander.
MESSIER_PROSE_NAMED = re.compile(
    r"\b(M(?:110|10\d|[1-9]\d?)), the [^,.;<]+, (?:an? )?[^,.;<]+"
)
MESSIER_PROSE_NGC = re.compile(
    r"\b(M(?:110|10\d|[1-9]\d?)) \((?:NGC|IC) [^)]+\), (?:an? )?[^,.;<]+"
)


def load_messier_catalog() -> dict[str, dict[str, str | None]]:
    catalog: dict[str, dict[str, str | None]] = {}
    in_messier = False
    for raw in FIXED_OBJECTS.read_text(encoding="utf-8").splitlines():
        if raw.strip() == "messier:":
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
        name = row[2].strip()
        if name.casefold() == "null":
            name = None
        if designation in NAME_OVERRIDES:
            name = NAME_OVERRIDES[designation]
        type_name = TYPE_NAMES.get(row[3].strip(), row[3].strip().lower())
        con = CONSTELLATIONS.get(row[4].strip(), row[4].strip())
        catalog[designation] = {"name": name, "type": type_name, "constellation": con}
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
    # Preserve the established star ordering.
    text = STAR.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)
    text = STAR_SEASON_FIRST.sub(lambda m: f"{m.group('head')} — {m.group('vis')} — {m.group('band')} — {m.group('season')}", text)

    def cal(m: re.Match[str]) -> str:
        designation = designation_from_head(m.group('head'))
        return f"{canonical_messier(designation)} — {m.group('vis')} — {m.group('band')} — {m.group('season')}"

    text = MESSIER_CALENDAR_OLD.sub(cal, text)
    text = MESSIER_SEASON_FIRST.sub(cal, text)
    text = MESSIER_CALENDAR.sub(cal, text)

    # Canonicalize the common expanded prose forms used in Sky Notes.
    text = MESSIER_PROSE_NAMED.sub(lambda m: canonical_messier(m.group(1)), text)
    text = MESSIER_PROSE_NGC.sub(lambda m: canonical_messier(m.group(1)), text)
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

print(f"Standardized object order and Messier labels in {changed} files")
