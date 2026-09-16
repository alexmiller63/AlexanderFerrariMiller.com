#!/usr/bin/env python3
"""Canonical constellation-membership geometry.

Production rule: reference J2000 FK5 RA/Dec -> B1875 FK5 -> Roman VI/42.
Catalog constellation labels are evidence only and never determine membership.
"""
from __future__ import annotations

import math
from pathlib import Path

import astropy.units as u
from astropy.coordinates import FK5, SkyCoord
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
ROMAN_PATH = ROOT / "reference-data" / "roman-vi42" / "data.dat"


def load_roman_lookup(path: Path = ROMAN_PATH):
    if not path.exists():
        raise SystemExit(
            "Roman VI/42 snapshot is missing; run tools/acquire_roman_constellation_lookup.py"
        )
    rows = []
    for number, line in enumerate(path.read_text(encoding="ascii").splitlines(), 1):
        if not line.strip():
            continue
        try:
            ra_low = float(line[1:8])
            ra_up = float(line[9:16])
            dec_low = float(line[17:25])
            constellation = line[26:29].strip()
        except (ValueError, IndexError) as exc:
            raise SystemExit(f"invalid Roman VI/42 row {number}: {line!r}") from exc
        rows.append((ra_low, ra_up, dec_low, constellation))
    if len(rows) != 357:
        raise SystemExit(f"expected 357 Roman VI/42 rows, found {len(rows)}")
    return rows


def reference_position(obj):
    """Return the first usable source J2000 position, preserving its provenance."""
    for record in obj.get("source_records") or []:
        facts = record.get("facts") or {}
        ra = facts.get("ra_h", facts.get("ra"))
        dec = facts.get("dec_deg", facts.get("dec"))
        try:
            ra = float(ra)
            dec = float(dec)
        except (TypeError, ValueError):
            continue
        if (
            math.isfinite(ra)
            and math.isfinite(dec)
            and 0.0 <= ra <= 24.0
            and -90.0 <= dec <= 90.0
        ):
            return {
                "source": record.get("source", ""),
                "source_key": record.get("source_key", ""),
                "ra_h": ra,
                "dec_deg": dec,
            }
    return None


def j2000_to_b1875(ra_h, dec_deg):
    position = SkyCoord(
        ra=float(ra_h) * u.hourangle,
        dec=float(dec_deg) * u.deg,
        frame=FK5(equinox=Time("J2000")),
    )
    b1875 = position.transform_to(FK5(equinox=Time("B1875")))
    return b1875.ra.hour % 24.0, b1875.dec.deg


def constellation_for_j2000(ra_h, dec_deg, rows):
    """Return canonical IAU constellation abbreviation and B1875 lookup position."""
    ra1875, dec1875 = j2000_to_b1875(ra_h, dec_deg)
    for ra_low, ra_up, dec_low, constellation in rows:
        if dec1875 >= dec_low and ra_low <= ra1875 < ra_up:
            return constellation.title(), ra1875, dec1875
    raise RuntimeError(
        f"Roman VI/42 produced no constellation for B1875 RA={ra1875}h Dec={dec1875}deg"
    )
