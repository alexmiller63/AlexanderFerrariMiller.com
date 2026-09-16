#!/usr/bin/env python3
"""Build derived constellation membership keyed by permanent fixed_object_id.

This deliberately treats constellation membership as a relationship, never as
part of physical-object identity. For each normalized physical object, the
builder selects one reconciled source position and records the corresponding
constellation value carried by that source. The existing identity audit has
already resolved/reviewed source constellation contradictions, including
boundary-spanning cases. A later geometry validator may independently compare
these relationships against the committed IAU boundary snapshot.
"""
from __future__ import annotations

import json
from pathlib import Path

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
    memberships = []
    no_constellation = []

    for obj in data.get("fixed_objects") or []:
        fixed_id = obj["fixed_object_id"]
        values = []
        evidence = []
        for source_record in obj.get("source_records") or []:
            facts = source_record.get("facts") or {}
            con = constellation_from_facts(facts)
            if con:
                values.append(con)
                evidence.append({
                    "source": source_record["source"],
                    "source_key": source_record["source_key"],
                    "constellation": con,
                })

        distinct = sorted(set(values))
        if len(distinct) > 1:
            raise SystemExit(
                f"fixed_object_id {fixed_id} has conflicting reconciled constellation values: {distinct}"
            )
        if not distinct:
            no_constellation.append(fixed_id)
            continue

        memberships.append({
            "fixed_object_id": fixed_id,
            "constellation": distinct[0],
            "derivation": "reconciled_source_membership",
            "evidence": evidence,
        })

    result = {
        "schema_version": 1,
        "purpose": "Derived constellation membership relationships for permanent physical fixed objects.",
        "identity_registry": "database/fixed-object-registry.json",
        "fixed_objects_source": "database/fixed-objects.json",
        "iau_boundary_snapshot": "reference-data/iau-constellation-boundaries",
        "membership_is_identity_defining": False,
        "membership_count": len(memberships),
        "objects_without_source_constellation_count": len(no_constellation),
        "objects_without_source_constellation": no_constellation,
        "constellation_memberships": memberships,
    }
    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT_PATH.relative_to(ROOT)}: {len(memberships)} memberships; {len(no_constellation)} without source constellation.")


if __name__ == "__main__":
    main()
