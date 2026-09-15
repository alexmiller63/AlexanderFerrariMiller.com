#!/usr/bin/env python3
"""Build the Star Almanack α/β Bayer-star source catalog from HYG plus audited supplements.

The primary source is HYG v4.1. A small repository supplement may add Bayer
systems that are independently confirmed but not exposed consistently by the
HYG Bayer field. Supplement rows are explicit, reviewable, and provenance-backed.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

BAYER_RE = re.compile(r"^(Alp|Bet)(\d*)$")
GREEK = {"Alp": "α", "Bet": "β"}

# Albireo is Beta Cygni. HYG v4.1 itself documents HIP 95951 as β² Cygni,
# while HIP 95947 is the named primary Albireo (β¹ Cygni). Normalize both
# components by stable Hipparcos identifier so catalog-field omissions cannot
# silently remove Beta Cygni from the Almanack.
BAYER_OVERRIDES = {
    "95947": ("Bet", "1", "Cyg", "Albireo"),
    "95951": ("Bet", "2", "Cyg", "Albireo B"),
}

FIELDNAMES = [
    "bayer_code", "bayer", "greek", "suffix", "con", "proper",
    "ra_h", "dec_deg", "mag", "hyg_id", "hip", "hd", "hr",
]


def as_float(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    return format(float(value), ".10g")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="HYG v4.1 CSV")
    parser.add_argument("output", type=Path, nargs="?", default=Path("expanded-bayer-stars.csv"))
    parser.add_argument(
        "--supplement",
        type=Path,
        default=None,
        help="Optional audited Bayer supplement CSV; may include an extra source column",
    )
    args = parser.parse_args()

    rows = []
    with args.input.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "hip", "hd", "hr", "proper", "ra", "dec", "mag", "bayer", "con"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise SystemExit(f"HYG input missing columns: {sorted(missing)}")

        for star in reader:
            hip = (star.get("hip") or "").strip()
            bayer = (star.get("bayer") or "").strip()
            con = (star.get("con") or "").strip()
            proper = (star.get("proper") or "").strip()

            override = BAYER_OVERRIDES.get(hip)
            if override:
                greek_code, suffix, con, canonical_name = override
                bayer = f"{greek_code}{suffix}"
                proper = canonical_name

            match = BAYER_RE.fullmatch(bayer)
            if not match or not con:
                continue

            greek_code, suffix = match.groups()
            rows.append(
                {
                    "bayer_code": bayer,
                    "bayer": f"{GREEK[greek_code]}{suffix} {con}",
                    "greek": GREEK[greek_code],
                    "suffix": suffix,
                    "con": con,
                    "proper": proper,
                    "ra_h": as_float(star.get("ra") or ""),
                    "dec_deg": as_float(star.get("dec") or ""),
                    "mag": as_float(star.get("mag") or ""),
                    "hyg_id": (star.get("id") or "").strip(),
                    "hip": hip,
                    "hd": (star.get("hd") or "").strip(),
                    "hr": (star.get("hr") or "").strip(),
                }
            )

    existing = {(r["bayer_code"], r["con"]) for r in rows}
    supplement_count = 0
    if args.supplement:
        with args.supplement.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = set(FIELDNAMES).difference(reader.fieldnames or [])
            if missing:
                raise SystemExit(f"Supplement missing columns: {sorted(missing)}")
            for row in reader:
                key = ((row.get("bayer_code") or "").strip(), (row.get("con") or "").strip())
                if not key[0] or not key[1]:
                    raise SystemExit(f"Invalid supplement row: {row}")
                if key in existing:
                    raise SystemExit(f"Supplement duplicates existing Bayer designation: {key[0]} {key[1]}")
                normalized = {name: (row.get(name) or "").strip() for name in FIELDNAMES}
                if normalized["greek"] not in {"α", "β"}:
                    raise SystemExit(f"Invalid supplement Greek letter: {normalized['greek']}")
                if not normalized["ra_h"]:
                    raise SystemExit(f"Supplement row missing RA: {key[0]} {key[1]}")
                rows.append(normalized)
                existing.add(key)
                supplement_count += 1

    rows.sort(key=lambda r: (r["con"], 0 if r["greek"] == "α" else 1, r["suffix"], float(r["mag"] or 99), r["hyg_id"]))

    if not rows:
        raise SystemExit("No α/β Bayer stars found")

    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    alpha = sum(r["greek"] == "α" for r in rows)
    beta = sum(r["greek"] == "β" for r in rows)
    systems = {(r["greek"], r["con"]) for r in rows}
    exact_designations = {(r["bayer_code"], r["con"]) for r in rows}
    print(f"Wrote {len(rows)} source rows: {alpha} α, {beta} β")
    print(f"Audited supplement rows merged: {supplement_count}")
    print(f"Constellation-letter systems represented: {len(systems)}")
    print(f"Distinct Bayer designations represented: {len(exact_designations)}")


if __name__ == "__main__":
    main()
