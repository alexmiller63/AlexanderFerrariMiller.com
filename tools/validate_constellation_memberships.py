#!/usr/bin/env python3
"""Independently validate canonical fixed-object constellation memberships.

Production B1875 conversion and Roman VI/42 lookup live in
constellation_membership.py. This validator deliberately does not import or
reimplement that conversion. It checks the generated result independently
with Astropy's public constellation lookup from the original J2000 position.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import astropy.units as u
from astropy.coordinates import FK5, SkyCoord, get_constellation
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = ROOT / "database" / "fixed-objects.json"
MEMBERSHIPS_PATH = ROOT / "database" / "constellation-memberships.json"
REPORT_PATH = ROOT / "generated" / "constellation-membership-validation.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def reference_position(obj):
    """Independently recover a usable source position for validation."""
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


def independent_constellation(ra_h, dec_deg):
    position = SkyCoord(
        ra=float(ra_h) * u.hourangle,
        dec=float(dec_deg) * u.deg,
        frame=FK5(equinox=Time("J2000")),
    )
    return str(get_constellation(position, short_name=True)).title()


def main():
    objects = {
        obj["fixed_object_id"]: obj
        for obj in load(OBJECTS_PATH).get("fixed_objects") or []
    }
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

        expected = independent_constellation(position["ra_h"], position["dec_deg"])
        result = {
            "fixed_object_id": fixed_id,
            "derived_constellation": membership["constellation"],
            "independent_constellation": expected,
            "reference_position_j2000": position,
        }
        checked.append(result)
        if expected.lower() != str(membership["constellation"]).lower():
            mismatches.append(result)

    report = {
        "schema_version": 3,
        "purpose": "Independent validation of canonical constellation memberships.",
        "fixed_objects_source": "database/fixed-objects.json",
        "memberships_source": "database/constellation-memberships.json",
        "production_method": "tools/constellation_membership.py: J2000 FK5 -> B1875 FK5 -> Roman VI/42",
        "validation_method": "Astropy get_constellation() applied independently to the reference J2000 FK5 position.",
        "validated_count": len(checked),
        "unvalidated_count": len(unvalidated),
        "mismatch_count": len(mismatches),
        "unvalidated_fixed_object_ids": unvalidated,
        "mismatches": mismatches,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Independently validated {len(checked)} memberships; "
        f"{len(unvalidated)} without usable coordinates; {len(mismatches)} mismatches."
    )
    for result in mismatches[:10]:
        pos = result["reference_position_j2000"]
        print(
            "MISMATCH SAMPLE: "
            f"{result['fixed_object_id']} derived={result['derived_constellation']} "
            f"independent={result['independent_constellation']} "
            f"ra_h={pos['ra_h']} dec_deg={pos['dec_deg']}"
        )
    if mismatches:
        raise SystemExit("Independent constellation-membership validation requires review")


if __name__ == "__main__":
    main()
