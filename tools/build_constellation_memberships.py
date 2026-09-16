#!/usr/bin/env python3
"""Build derived constellation membership keyed by permanent fixed_object_id.

Constellation membership is a relationship, never part of physical-object
identity. Source constellation labels are preserved as evidence. When source
labels disagree, an explicit machine-readable review may resolve the derived
membership (for example, an extended object spanning an IAU boundary).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OBJECTS_PATH = ROOT / "database" / "fixed-objects.json"
REGISTRY_PATH = ROOT / "database" / "fixed-object-registry.json"
REVIEWS_PATH = ROOT / "database" / "object-constellation-reviews.json"
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


def identifier_key(identifier):
    return (str(identifier.get("namespace", "")).strip().lower(), str(identifier.get("value", "")).strip())


def reviewed_resolutions():
    """Index explicit reviewed boundary resolutions by object identifier."""
    if not REVIEWS_PATH.exists():
        return {}
    reviews = load(REVIEWS_PATH).get("reviews") or []
    return {
        identifier_key(review["object_identifier"]): review
        for review in reviews
        if review.get("audit_resolution") == "suppress_constellation_identity_contradiction"
        and review.get("object_identifier")
    }


def registry_identifiers_by_fixed_id():
    """Return permanent object identifiers keyed by immutable fixed_object_id."""
    registry = load(REGISTRY_PATH)
    return {
        obj["fixed_object_id"]: obj.get("identifiers") or []
        for obj in registry.get("fixed_objects") or []
    }


def review_for_identifiers(identifiers, resolutions):
    for identifier in identifiers:
        review = resolutions.get(identifier_key(identifier))
        if review:
            return review
    return None


def main():
    data = load(OBJECTS_PATH)
    resolutions = reviewed_resolutions()
    registry_identifiers = registry_identifiers_by_fixed_id()
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
        review = None
        if len(distinct) > 1:
            review = review_for_identifiers(registry_identifiers.get(fixed_id, []), resolutions)
            if not review:
                raise SystemExit(
                    f"fixed_object_id {fixed_id} has conflicting reconciled constellation values: {distinct}"
                )
            resolved = (review.get("iau_boundary_snapshot") or {}).get("primary_constellation_by_reference_point")
            if not resolved:
                raise SystemExit(
                    f"fixed_object_id {fixed_id} has reviewed constellation conflict but no primary boundary membership"
                )
            distinct = [resolved]

        if not distinct:
            no_constellation.append(fixed_id)
            continue

        membership = {
            "fixed_object_id": fixed_id,
            "constellation": distinct[0],
            "derivation": "reviewed_iau_boundary_membership" if review else "reconciled_source_membership",
            "evidence": evidence,
        }
        if review:
            membership["review"] = {
                "source": "database/object-constellation-reviews.json",
                "status": review.get("status"),
                "audit_resolution": review.get("audit_resolution"),
            }
        memberships.append(membership)

    result = {
        "schema_version": 1,
        "purpose": "Derived constellation membership relationships for permanent physical fixed objects.",
        "identity_registry": "database/fixed-object-registry.json",
        "fixed_objects_source": "database/fixed-objects.json",
        "constellation_reviews": "database/object-constellation-reviews.json",
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
