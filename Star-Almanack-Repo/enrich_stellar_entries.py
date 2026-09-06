#!/usr/bin/env python3
"""Enrich catalog-backed calendar entries with observer-facing metadata.

Stars display observing aid immediately before whole-number V magnitude, followed by
Declination-band Season. Messier objects display designation + common name when
available, object type, Declination-band Season, and observing aid. Authoritative
source values retain full precision; Almanack presentation is rounded/formatted.

Current urban-observer baseline:
  V <= 3.5       -> 👁
  3.5 < V <= 7.5 -> B
  V > 7.5        -> 🔭

The aid is a practical recommendation for a city observer: what should the observer
take outside to enjoy the target? It is not an absolute physiological detection limit.
Extended-object surface brightness and observing conditions can make some targets
harder than their integrated magnitude suggests, so this baseline may be refined by
object-specific observing guidance later.
"""
from __future__ import annotations

import csv
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).parent
TARGET = ROOT / "almanack-expanded.md"
BAYER = ROOT / "expanded-bayer-visibility-2026.csv"
BRIGHT = ROOT / "bright-star-visibility-2026.csv"
MESSIER = ROOT / "messier-visibility-2026.csv"
FIXED_OBJECTS = ROOT / "fixed-objects.yaml"

GREEK = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε",
    "Zet": "ζ", "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ",
    "Lam": "λ", "Mu": "μ", "Nu": "ν", "Xi": "ξ", "Omi": "ο",
    "Pi": "π", "Rho": "ρ", "Sig": "σ", "Tau": "τ", "Ups": "υ",
    "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
}

MESSIER_TYPES = {
    "SN": "Supernova Remnant", "GC": "Globular Cluster", "OC": "Open Cluster",
    "DN": "Diffuse Nebula", "PN": "Planetary Nebula", "AS": "Asterism",
    "DS": "Double Star", "MW": "Milky Way", "SG": "Spiral Galaxy",
    "BG": "Barred Galaxy", "LG": "Lenticular Galaxy", "EG": "Elliptical Galaxy",
    "IG": "Irregular Galaxy",
}

ROW_RE = re.compile(
    r"(?m)^(\| (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun), ([A-Z][a-z]{2}) (\d{2}), (2025|2026|2027) \| [^|]+ \| )([^|]*)( \|)$"
)
MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
)}


def declination_band(dec_deg: str) -> str:
    dec = float(dec_deg)
    if dec > 23.44:
        return "Northern"
    if dec < -23.44:
        return "Southern"
    return "Tropical"


def season_for(d: date) -> str:
    md = (d.month, d.day)
    if (3, 20) <= md < (6, 21):
        return "Spring"
    if (6, 21) <= md < (9, 22):
        return "Summer"
    if (9, 22) <= md < (12, 21):
        return "Autumn"
    return "Winter"


def equipment_for(magnitude: str) -> str:
    try:
        mag = float((magnitude or "").strip())
    except ValueError:
        return ""
    if mag <= 3.5:
        return "👁"
    if mag <= 7.5:
        return "B"
    return "🔭"


def whole_mag(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        rounded = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return value
    return str(int(rounded))


def bayer_display(code: str, con: str) -> str:
    m = re.fullmatch(r"([A-Z][a-z]{2})(?:-?(\d+))?", (code or "").strip())
    if not m:
        return f"{code} {con}".strip()
    return f"{GREEK.get(m.group(1), m.group(1))}{m.group(2) or ''} {con}".strip()


def latin_key(code: str, con: str) -> str:
    m = re.fullmatch(r"([A-Z][a-z]{2})(?:-?(\d+))?", (code or "").strip())
    if not m:
        return f"{code} {con}".strip().casefold()
    suffix = f" {m.group(2)}" if m.group(2) else ""
    return f"{m.group(1).casefold()}{suffix} {con}".strip().casefold()


def canonical_star(row: dict[str, str]) -> str:
    proper = (row.get("proper") or "").strip()
    code = (row.get("bayer_code") or row.get("bayer") or "").strip()
    con = (row.get("con") or "").strip()
    designation = (row.get("bayer") or "").strip()
    if not designation or not designation.startswith(tuple(GREEK.values())):
        designation = bayer_display(code, con)
    name = f"{proper} ({designation})" if proper else designation
    source_mag = row.get("mag") or row.get("representative_vmax") or row.get("catalog_v") or ""
    mag = whole_mag(source_mag)
    d = date.fromisoformat(row["best_date"])
    parts = [name]
    equipment = equipment_for(source_mag)
    visibility_magnitude = " ".join(v for v in (equipment, f"V {mag}" if mag else "") if v)
    if visibility_magnitude:
        parts.append(visibility_magnitude)
    parts.append(f"{declination_band(row['dec_deg'])} {season_for(d)}")
    return " — ".join(parts)


def aliases(row: dict[str, str]) -> list[str]:
    proper = (row.get("proper") or "").strip()
    designation = (row.get("bayer") or "").strip()
    code = (row.get("bayer_code") or row.get("bayer") or "").strip()
    con = (row.get("con") or "").strip()
    short = bayer_display(code, con)
    return [v for v in (proper, designation if designation.startswith(tuple(GREEK.values())) else "", short) if v]


def load_stars() -> dict[str, list[tuple[list[str], str]]]:
    by_date: dict[str, list[tuple[list[str], str]]] = defaultdict(list)
    seen = set()
    with BRIGHT.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row = dict(row)
            row["bayer_code"] = row.get("bayer", "")
            key = (row["best_date"], (row.get("proper") or "").casefold(), latin_key(row.get("bayer", ""), row.get("con", "")))
            seen.add(key)
            by_date[row["best_date"]].append((aliases(row), canonical_star(row)))
    with BAYER.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = (row["best_date"], (row.get("proper") or "").casefold(), latin_key(row.get("bayer_code", ""), row.get("con", "")))
            if key not in seen:
                by_date[row["best_date"]].append((aliases(row), canonical_star(row)))
    return by_date


def load_messier_source() -> dict[str, dict[str, str]]:
    """Read Messier name, type, declination, and magnitude from source-of-truth inventory."""
    out: dict[str, dict[str, str]] = {}
    for raw in FIXED_OBJECTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not re.match(r"^- \[M\d{1,3},", line):
            continue
        payload = line[3:-1] if line.endswith("]") else line[3:]
        fields = next(csv.reader([payload], skipinitialspace=True))
        if len(fields) >= 8:
            name = fields[2].strip()
            if name.casefold() == "null":
                name = ""
            out[fields[0].strip().upper()] = {
                "name": name,
                "type": fields[3].strip(),
                "dec": fields[6].strip(),
                "mag": fields[7].strip(),
            }
    return out


def load_messier() -> dict[str, dict[str, str]]:
    source = load_messier_source()
    out: dict[str, dict[str, str]] = {}
    with MESSIER.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 110:
        raise SystemExit(f"Expected 110 Messier visibility rows, found {len(rows)}")
    for row in rows:
        designation = row["messier"].upper()
        src = source.get(designation)
        if src is None:
            raise SystemExit(f"Missing source metadata for {designation}")
        object_type = MESSIER_TYPES.get(src["type"], src["type"])
        if not object_type:
            raise SystemExit(f"Missing object type for {designation}")
        heading = f"{designation} {src['name']}" if src["name"] else designation
        d = date.fromisoformat(row["best_date"])
        equipment = equipment_for(src["mag"])
        parts = [heading, object_type, f"{declination_band(src['dec'])} {season_for(d)}"]
        if equipment:
            parts.append(equipment)
        out[designation] = {"best_date": row["best_date"], "label": " — ".join(parts)}
    return out


def alias_matches(part: str, alias: str) -> bool:
    p = part.strip().casefold()
    a = alias.strip().casefold()
    return p == a or p.startswith(a + " (") or p.startswith(a + " —")


def enrich_cell(date_iso: str, cell: str, stars, messier) -> str:
    if not cell.strip() or cell.strip() == "—":
        return cell
    parts = cell.split("<br>")
    candidates = stars.get(date_iso, [])
    out = []
    for part in parts:
        replacement = None
        for star_aliases, label in candidates:
            if any(alias_matches(part, alias) for alias in star_aliases if alias):
                replacement = label
                break
        if replacement is None:
            m = re.fullmatch(r"\s*(M\d{1,3})(?:\s+—.*)?\s*", part, flags=re.IGNORECASE)
            if m:
                designation = m.group(1).upper()
                info = messier.get(designation)
                if info and info["best_date"] == date_iso:
                    replacement = info["label"]
        out.append(replacement or part)
    deduped = []
    seen = set()
    for part in out:
        if part not in seen:
            seen.add(part)
            deduped.append(part)
    return "<br>".join(deduped)


def main() -> None:
    text = TARGET.read_text(encoding="utf-8")
    stars = load_stars()
    messier = load_messier()

    def repl(m: re.Match[str]) -> str:
        d = date(int(m.group(4)), MONTHS[m.group(2)], int(m.group(3))).isoformat()
        return m.group(1) + enrich_cell(d, m.group(5), stars, messier) + m.group(6)

    updated = ROW_RE.sub(repl, text)

    for name, info in messier.items():
        if info["label"] not in updated:
            raise SystemExit(f"Expected enriched Messier entry not found: {info['label']}")

    expected = "Enif (ε Peg) — 👁 V 2 — Tropical Autumn"
    if expected not in updated:
        raise SystemExit(f"Expected enriched Enif entry not found: {expected}")
    diadem = "Diadem (α Com) — B V 4 — Tropical Spring"
    if diadem not in updated:
        raise SystemExit(f"Expected enriched Diadem entry not found: {diadem}")
    m53 = "M53 — Globular Cluster — Tropical Spring — 🔭"
    if m53 not in updated:
        raise SystemExit(f"Expected enriched M53 entry not found: {m53}")
    if re.search(r"\bV\s+[+-]?\d+\.\d+", updated):
        raise SystemExit("Decimal stellar magnitude survived Almanack rendering")
    if " — variable — " in updated:
        raise SystemExit("Obsolete variable word survived")

    TARGET.write_text(updated, encoding="utf-8")
    print("Enriched stars and all 110 Messier entries with names, object types, and urban observing-aid recommendations; PASS")


if __name__ == "__main__":
    main()
