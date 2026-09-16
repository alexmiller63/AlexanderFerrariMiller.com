#!/usr/bin/env python3
"""Validate derived fixed-object constellation memberships with Roman VI/42.

Nancy Roman's CDS VI/42 lookup is authoritative for deciding which
constellation contains a position.  The IAU/Davenhall polygon snapshot is
retained separately for chart geometry and is deliberately not used here.
Reference positions are treated as J2000 and precessed to B1875 before the
VI/42 lookup, following the catalog's prescribed method.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from astropy.coordinates import FK5, SkyCoord
from astropy.time import Time
import astropy.units as u

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = ROOT / "database" / "fixed-objects.json"
MEMBERSHIPS_PATH = ROOT / "database" / "constellation-memberships.json"
ROMAN_PATH = ROOT / "reference-data" / "roman-vi42" / "data.dat"
REPORT_PATH = ROOT / "generated" / "constellation-membership-validation.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_roman_lookup():
    if not ROMAN_PATH.exists():
        raise SystemExit(
            "Roman VI/42 snapshot is missing; run tools/acquire_roman_constellation_lookup.py"
        )
    rows = []
    for number, line in enumerate(ROMAN_PATH.read_text(encoding="ascii").splitlines(), 1):
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


def j2000_to_b1875(ra_h, dec_deg):
    position = SkyCoord(
        ra=float(ra_h) * u.hourangle,
        dec=float(dec_deg) * u.deg,
        frame=FK5(equinox=Time("J2000")),
    )
    b1875 = position.transform_to(FK5(equinox=Time("B1875")))
    return b1875.ra.hour % 24.0, b1875.dec.deg


def roman_constellation(ra_h, dec_deg, rows):
    """Apply Roman VI/42 in its published order after conversion to B1875."""
    ra1875, dec1875 = j2000_to_b1875(ra_h, dec_deg)
    for ra_low, ra_up, dec_low, constellation in rows:
        if dec1875 >= dec_low and ra_low <= ra1875 < ra_up:
            return constellation.title(), ra1875, dec1875
    raise RuntimeError(
        f"Roman VI/42 produced no constellation for B1875 RA={ra1875}h Dec={dec1875}deg"
    )


def reference_position(obj):
    candidates = []
    for record in obj.get("source_records") or []:
        facts = record.get("facts") or {}
        ra = facts.get("ra_h")
        if ra is None:
            ra = facts.get("ra")
        dec = facts.get("dec_deg")
        if dec is None:
            dec = facts.get("dec")
        try:
            ra = float(ra)
            dec = float(dec)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(ra) or not math.isfinite(dec) or not (0.0 <= ra <= 24.0) or not (-90.0 <= dec <= 90.0):
            continue
        candidates.append((record.get("source", ""), record.get("source_key", ""), ra, dec))
    if not candidates:
        return None
    source, source_key, ra, dec = candidates[0]
    return {"source": source, "source_key": source_key, "ra_h": ra, "dec_deg": dec}


def main():
    roman_rows = load_roman_lookup()
    objects = {obj["fixed_object_id"]: obj for obj in load(OBJECTS_PATH).get("fixed_objects") or []}
    memberships = load(MEMBERSHIPS_PATH).get("constellation_memberships") or []

    checked = []
    mismatches = []
    unvalidated = []

    for membership in memberships:
        fixed_id = membership["fixed_object_id"]
        obj = objects.get(fixed_id)
        if obj is None:
            raise SystemExit(f"membership references missing fixed_object_id {fixed_id}")
        position = reference_position(obj)
        if position is None:
            unvalidated.append(fixed_id)
            continue
        constellation, ra1875, dec1875 = roman_constellation(
            position["ra_h"], position["dec_deg"], roman_rows
        )
        result = {
            "fixed_object_id": fixed_id,
            "derived_constellation": membership["constellation"],
            "roman_vi42_constellation": constellation,
            "reference_position_j2000": position,
            "lookup_position_b1875": {"ra_h": ra1875, "dec_deg": dec1875},
        }
        checked.append(result)
        if constellation.lower() != str(membership["constellation"]).lower():
            mismatches.append(result)

    report = {
        "schema_version": 2,
        "purpose": "Validation of derived constellation memberships against Nancy Roman CDS VI/42.",
        "fixed_objects_source": "database/fixed-objects.json",
        "memberships_source": "database/constellation-memberships.json",
        "membership_authority": "reference-data/roman-vi42/data.dat (CDS VI/42, Roman 1987)",
        "coordinate_method": "Reference J2000 FK5 position precessed to B1875 FK5, then first matching VI/42 ordered range.",
        "graphics_boundary_snapshot": "reference-data/iau-constellation-boundaries (not used for membership assignment)",
        "validated_count": len(checked),
        "unvalidated_count": len(unvalidated),
        "mismatch_count": len(mismatches),
        "unvalidated_fixed_object_ids": unvalidated,
        "mismatches": mismatches,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Validated {len(checked)} memberships with Roman VI/42; "
        f"{len(unvalidated)} without usable coordinates; {len(mismatches)} mismatches."
    )
    for result in mismatches[:10]:
        pos = result["reference_position_j2000"]
        print(
            "MISMATCH SAMPLE: "
            f"{result['fixed_object_id']} derived={result['derived_constellation']} "
            f"roman={result['roman_vi42_constellation']} "
            f"ra_h={pos['ra_h']} dec_deg={pos['dec_deg']}"
        )
    if mismatches:
        raise SystemExit("Roman VI/42 constellation-membership validation requires review")


if __name__ == "__main__":
    main()
