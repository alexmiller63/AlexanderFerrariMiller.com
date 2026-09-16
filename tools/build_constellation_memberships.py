#!/usr/bin/env python3
"""Build canonical constellation membership keyed by permanent fixed_object_id.

Membership is derived geometrically from each object's reference J2000 position:
J2000 FK5 -> B1875 FK5 -> Roman VI/42. Source constellation labels are retained
only as audit evidence and never determine membership.
"""
from __future__ import annotations

import json
from pathlib import Path

from constellation_membership import constellation_for_j2000, load_roman_lookup, reference_position

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = ROOT / "database" / "fixed-objects.json"
OUT_PATH = ROOT / "database" / "constellation-memberships.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def constellation_from_facts(facts):
    value = facts.get("constellation")
    if value is None:
        value = facts.get("con")
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def main():
    data = load(OBJECTS_PATH)
    roman_rows = load_roman_lookup()
    memberships = []
    no_position = []

    for obj in data.get("fixed_objects") or []:
        fixed_id = obj["fixed_object_id"]
        position = reference_position(obj)
        if position is None:
            no_position.append(fixed_id)
            continue

        constellation, ra1875, dec1875 = constellation_for_j2000(
            position["ra_h"], position["dec_deg"], roman_rows
        )

        evidence = []
        for source_record in obj.get("source_records") or []:
            con = constellation_from_facts(source_record.get("facts") or {})
            if con:
                evidence.append({
                    "source": source_record["source"],
                    "source_key": source_record["source_key"],
                    "constellation": con,
                })

        memberships.append({
            "fixed_object_id": fixed_id,
            "constellation": constellation,
            "derivation": "j2000_to_b1875_roman_vi42",
            "reference_position_j2000": position,
            "lookup_position_b1875": {"ra_h": ra1875, "dec_deg": dec1875},
            "evidence": evidence,
        })

    result = {
        "schema_version": 2,
        "purpose": "Canonical constellation membership relationships for permanent physical fixed objects.",
        "fixed_objects_source": "database/fixed-objects.json",
        "membership_authority": "reference-data/roman-vi42/data.dat (CDS VI/42, Roman 1987)",
        "coordinate_method": "Reference J2000 FK5 position precessed to B1875 FK5, then first matching VI/42 ordered range.",
        "membership_is_identity_defining": False,
        "membership_count": len(memberships),
        "objects_without_usable_position_count": len(no_position),
        "objects_without_usable_position": no_position,
        "constellation_memberships": memberships,
    }
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        f"Wrote {OUT_PATH.relative_to(ROOT)}: {len(memberships)} geometrically derived memberships; "
        f"{len(no_position)} without usable positions."
    )


if __name__ == "__main__":
    main()
