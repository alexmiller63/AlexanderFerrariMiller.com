#!/usr/bin/env python3
"""Migrate physical catalog targets from spelling/catalog identifiers to permanent fixed_object_id values."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "database" / "fixed-object-registry.json"
TARGETS_PATH = ROOT / "database" / "catalog-entry-targets.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    registry = load(REGISTRY_PATH)
    data = load(TARGETS_PATH)

    alias_to_id = {}
    source_to_id = {}
    for obj in registry["fixed_objects"]:
        fixed_id = obj["fixed_object_id"]
        if obj.get("status") != "active":
            continue
        for ident in obj.get("identifiers") or []:
            key = (str(ident["namespace"]), str(ident["value"]))
            prior = alias_to_id.get(key)
            if prior is not None and prior != fixed_id:
                raise SystemExit(f"Ambiguous registry identifier {key}: {prior}, {fixed_id}")
            alias_to_id[key] = fixed_id
        for ref in obj.get("source_refs") or []:
            key = (str(ref["source"]), str(ref["source_key"]))
            prior = source_to_id.get(key)
            if prior is not None and prior != fixed_id:
                raise SystemExit(f"Ambiguous registry source reference {key}: {prior}, {fixed_id}")
            source_to_id[key] = fixed_id

    migrated = 0
    unresolved = []
    for entry in data.get("catalog_entries") or []:
        for target in entry.get("targets") or []:
            kind = target.get("target_kind")
            fixed_id = None
            if kind == "physical_object_identifier":
                ident = target.get("identifier") or {}
                key = (str(ident.get("namespace", "")), str(ident.get("value", "")))
                fixed_id = alias_to_id.get(key)
                if fixed_id is None:
                    unresolved.append(f"{entry['catalog_entry_key']}: identifier {key}")
            elif kind == "physical_object_candidate":
                ref = str(target.get("candidate_ref") or "")
                if "/" not in ref:
                    unresolved.append(f"{entry['catalog_entry_key']}: candidate_ref {ref!r}")
                    continue
                source, source_key = ref.rsplit("/", 1)
                fixed_id = source_to_id.get((source, source_key))
                if fixed_id is None:
                    unresolved.append(f"{entry['catalog_entry_key']}: candidate_ref {ref!r}")
            else:
                continue

            if fixed_id is not None:
                target["fixed_object_id"] = fixed_id
                target["target_kind"] = "fixed_object"
                # Preserve the former identifier/reference as reconciliation evidence,
                # but identity is now exclusively the permanent numeric ID.
                migrated += 1

    if unresolved:
        raise SystemExit("Unresolved physical targets; migration aborted:\n" + "\n".join(unresolved))

    data["schema_version"] = max(int(data.get("schema_version", 0)), 3)
    data["purpose"] = "Machine-readable relationship layer separating catalog entries and observing targets from permanent physical fixed-object identity."
    data["status"] = "permanent_identity_migrated"
    data["permanent_fixed_object_ids_assigned"] = True
    data["fixed_object_registry"] = "database/fixed-object-registry.json"

    TARGETS_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Migrated {migrated} physical catalog targets to permanent fixed_object_id references.")


if __name__ == "__main__":
    main()
