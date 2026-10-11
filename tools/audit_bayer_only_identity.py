#!/usr/bin/env python3
"""Reproducible audit of active fixed objects whose sole external ID is Bayer.

Writes a durable JSON report; does not change catalog identities.
Run: python tools/audit_bayer_only_identity.py
"""
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "database/fixed-object-registry.json"
destination = ROOT / "generated/bayer-only-identity-audit.json"
registry = json.loads(source.read_text(encoding="utf-8"))
active = [o for o in registry["fixed_objects"] if o.get("status") == "active"]
external = {"hip", "hd", "hr", "gaia_dr3", "wds", "bayer", "ngc", "ic", "sh2", "variable_star", "messier", "caldwell"}
matches = []
for obj in active:
    ids = obj.get("identifiers") or []
    recognized = [i for i in ids if i.get("namespace") in external]
    if recognized and {i.get("namespace") for i in recognized} == {"bayer"}:
        matches.append({
            "fixed_object_id": obj["fixed_object_id"],
            "canonical_identity": obj.get("canonical_identity"),
            "identifiers": ids,
            "source_refs": obj.get("source_refs", []),
            "status": obj.get("status")
        })
# Attach durable review classifications without changing permanent identities.
review_path = ROOT / "database/bayer-only-identity-review-2026-10-11.json"
if review_path.exists():
    review = json.loads(review_path.read_text(encoding="utf-8"))
    by_id = {row["fixed_object_id"]: row for row in review.get("records", [])}
    for row in matches:
        decision = by_id.get(row["fixed_object_id"])
        if decision is None:
            row["review_status"] = "unreviewed"
        elif decision.get("bayer") != row["canonical_identity"].get("value"):
            raise SystemExit(f"Review identity mismatch for fixed_object_id {row['fixed_object_id']}")
        else:
            row["review_status"] = decision.get("status", "unreviewed")
            if decision.get("evidence"):
                row["review_evidence"] = decision["evidence"]
# Report identifier collisions across active objects; a Bayer-only count alone
# cannot establish catalog identity integrity.
alias_owners = {}
for obj in active:
    for ident in obj.get("identifiers") or []:
        namespace = ident.get("namespace")
        value = ident.get("value")
        if namespace in {"hip", "hd", "gaia_dr3", "bayer"} and value:
            alias_owners.setdefault((namespace, value), set()).add(obj["fixed_object_id"])
duplicate_identifiers = [
    {"namespace": ns, "value": value, "fixed_object_ids": sorted(owners)}
    for (ns, value), owners in sorted(alias_owners.items())
    if len(owners) > 1
]
matches.sort(key=lambda o: o["fixed_object_id"])
result = {
    "schema_version": 1,
    "audit": "active Bayer-only external identifier records",
    "source": "database/fixed-object-registry.json",
    "source_registry_count": registry.get("physical_object_count"),
    "active_count": len(active),
    "bayer_only_count": len(matches),
    "records": matches,
    "review_status_counts": dict(Counter(row.get("review_status", "unreviewed") for row in matches)),
    "unreviewed_count": sum(row.get("review_status") == "unreviewed" for row in matches),
    "duplicate_identifier_count": len(duplicate_identifiers),
    "duplicate_identifiers": duplicate_identifiers,
    "note": "A Bayer-only record is not proof of an unidentified star. Review coordinates, multiple systems and catalog crossmatches before changing identities."
}
destination.parent.mkdir(parents=True, exist_ok=True)
destination.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Active: {len(active)}; Bayer-only: {len(matches)}; duplicate identifiers: {len(duplicate_identifiers)}")
for row in matches:
    print(row["fixed_object_id"], ", ".join(i["value"] for i in row["identifiers"] if i.get("namespace") == "bayer"))
print("Saved:", destination.relative_to(ROOT))
