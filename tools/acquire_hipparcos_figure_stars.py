#!/usr/bin/env python3
"""Acquire Hipparcos positions needed by accepted finder geometry.

The full CDS I/239 Hipparcos main catalogue is downloaded only when the local
subset is missing one or more HIP identifiers used by Martz/MacRobert geometry.
The repository-owned subset is then reused by subsequent builds.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "finder-geometry" / "martz-macrobert.json"
DEST = ROOT / "reference-data" / "hipparcos" / "figure-stars.csv"
URL = "https://cdsarc.cds.unistra.fr/ftp/cats/I/239/hip_main.dat"
FIELDS = ("hip", "ra_h", "dec_deg")

# Documented astrometric fallbacks for valid HIP identities lacking usable
# positions in the original Hipparcos I/239 main catalogue. Keep this table
# deliberately small and source-specific; ordinary stars must still come from
# I/239. HIP 55203 = Xi Ursae Majoris (Alula Australis).
ASTROMETRIC_FALLBACKS: dict[int, tuple[str, str]] = {
    55203: ("11.3031000000", "31.5308000000"),
}


def required_hips() -> set[int]:
    data = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    hips: set[int] = set()
    for section in ("constellations", "asterisms"):
        for figure in (data.get(section) or {}).values():
            for path in figure.get("paths") or []:
                for point in path or []:
                    if (
                        isinstance(point, dict)
                        and str(point.get("catalog") or "").upper() == "HIP"
                        and point.get("id") is not None
                    ):
                        hips.add(int(point["id"]))
                    elif isinstance(point, str) and point.upper().startswith("HIP "):
                        hips.add(int(point.split()[1]))
    return hips


def read_cached() -> dict[int, tuple[str, str]]:
    if not DEST.exists():
        return {}
    rows: dict[int, tuple[str, str]] = {}
    with DEST.open(newline="", encoding="ascii") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != FIELDS:
            raise SystemExit(f"invalid Hipparcos subset header: {reader.fieldnames!r}")
        for row in reader:
            hip = int(row["hip"])
            ra_h = row["ra_h"].strip()
            dec_deg = row["dec_deg"].strip()
            float(ra_h)
            float(dec_deg)
            if hip in rows:
                raise SystemExit(f"duplicate HIP {hip} in {DEST.relative_to(ROOT)}")
            rows[hip] = (ra_h, dec_deg)
    return rows


def download_positions(wanted: set[int]) -> dict[int, tuple[str, str]]:
    request = Request(URL, headers={"User-Agent": "Star-Almanack-reference-data/1.0"})
    with urlopen(request, timeout=120) as response:
        text = response.read().decode("ascii")
    found: dict[int, tuple[str, str]] = {}
    for line in text.splitlines():
        if len(line) < 76:
            continue
        hip_text = line[8:14].strip()
        if not hip_text:
            continue
        hip = int(hip_text)
        if hip not in wanted:
            continue
        ra_deg = line[51:63].strip()
        dec_deg = line[64:76].strip()
        if not ra_deg or not dec_deg:
            continue
        found[hip] = (f"{float(ra_deg) / 15.0:.10f}", f"{float(dec_deg):.10f}")
    return found


def write_subset(rows: dict[int, tuple[str, str]]) -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    with DEST.open("w", newline="", encoding="ascii") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(FIELDS)
        for hip in sorted(rows):
            writer.writerow((hip, *rows[hip]))


def main() -> None:
    wanted = required_hips()
    cached = read_cached()
    missing = wanted.difference(cached)
    if missing:
        acquired = download_positions(missing)
        unresolved = missing.difference(acquired)
        fallback = {hip: ASTROMETRIC_FALLBACKS[hip] for hip in unresolved if hip in ASTROMETRIC_FALLBACKS}
        acquired.update(fallback)
        unresolved.difference_update(fallback)
        if unresolved:
            sample = ", ".join(str(hip) for hip in sorted(unresolved)[:20])
            raise SystemExit(
                f"Hipparcos I/239 lacks usable positions for {len(unresolved)} "
                f"required HIP objects: {sample}"
            )
        cached.update(acquired)
        write_subset({hip: cached[hip] for hip in wanted})
        print(
            f"Acquired {len(acquired)} Hipparcos positions; "
            f"cached {len(wanted)} figure-star rows in {DEST.relative_to(ROOT)}"
        )
    else:
        extra = set(cached).difference(wanted)
        if extra:
            write_subset({hip: cached[hip] for hip in wanted})
        print(
            f"Reusing cached Hipparcos figure-star subset: "
            f"{DEST.relative_to(ROOT)} ({len(wanted)} HIP objects)"
        )


if __name__ == "__main__":
    main()
