#!/usr/bin/env python3
"""Build and maintain the permanent Star Almanack fixed-object registry.

The initial registry is assigned deterministically from the reconciled physical
identity audit. After creation, existing fixed_object_id values are immutable:
reruns preserve IDs by matching stable identifiers and append new IDs only for
new physical identities. Ambiguous merges/splits fail loudly for human review.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
AUDIT_PATH = SRC / "generated" / "fixed-object-identity-audit.json"
REGISTRY_PATH = SRC / "database" / "fixed-object-registry.json"

MATCH_NAMESPACES = {
    "ngc",
    "ic",
    "hip",
    "hd",
    "gaia_dr3",
    "wds",
    "bayer",
    "sh2",
    "variable_star",
    "messier",
    "caldwell",
    "finest_ngc",
    "special",
    "component",
}

NAMESPACE_PRIORITY = {
    "hip": 0,
    "hd": 1,
    "gaia_dr3": 2,
    "wds": 3,
    "ngc": 4,
    "ic": 5,
    "sh2": 6,
    "bayer": 7,
    "variable_star": 8,
    "messier": 9,
    "caldwell": 10,
    "finest_ngc": 11,
    "special": 12,
    "component": 13,
    "asterism_member_label": 14,
    "catalog_label": 15,
}


def read_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def natural_key(value: str):
    return tuple(int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value))


def alias_key(alias):
    return alias["namespace"], alias["value"]


def alias_sort_key(alias):
    ns = alias["namespace"]
    return NAMESPACE_PRIORITY.get(ns, 999), natural_key(alias["value"]), ns


def group_aliases(group, candidate_map):
    aliases = {}
    for candidate_id in group["candidate_ids"]:
        candidate = candidate_map[candidate_id]
        for ident in candidate.get("identifiers") or []:
            ns = str(ident.get("namespace") or "").strip()
            value = str(ident.get("value") or "").strip()
            if ns and value:
                aliases[(ns, value)] = {"namespace": ns, "value": value}
    return sorted(aliases.values(), key=alias_sort_key)


def source_refs(group, candidate_map):
    refs = []
    for candidate_id in sorted(group["candidate_ids"]):
        candidate = candidate_map[candidate_id]
        refs.append(
            {
                "source": candidate["source"],
                "source_key": candidate["source_key"],
            }
        )
    refs.sort(key=lambda r: (r["source"], str(r["source_key"])))
    return refs


def canonical_alias(aliases):
    if not aliases:
        raise SystemExit("Physical reconciliation group has no identifiers; cannot create permanent identity.")
    return min(aliases, key=alias_sort_key)


def initial_group_sort_key(item):
    group, aliases = item
    canon = canonical_alias(aliases)
    return (
        NAMESPACE_PRIORITY.get(canon["namespace"], 999),
        natural_key(canon["value"]),
        canon["namespace"],
        min(group["candidate_ids"]),
    )


def registry_alias_index(records):
    index = {}
    for record in records:
        fixed_id = record["fixed_object_id"]
        for alias in record.get("identifiers") or []:
            key = alias_key(alias)
            prior = index.get(key)
            if prior is not None and prior != fixed_id:
                raise SystemExit(
                    f"Registry identifier collision {key}: fixed_object_id {prior} and {fixed_id}"
                )
            if alias["namespace"] in MATCH_NAMESPACES:
                index[key] = fixed_id
    return index


def main():
    audit = read_json(AUDIT_PATH)
    if audit is None:
        raise SystemExit(f"Missing audit: {AUDIT_PATH}")
    if not audit.get("physical_registry_ready"):
        raise SystemExit(
            "Physical registry is not ready; blockers: "
            + repr(audit.get("physical_registry_blockers"))
        )
    if audit.get("physical_contradiction_review_group_count") != 0:
        raise SystemExit("Physical contradiction reviews remain unresolved.")

    candidates = audit.get("candidates") or []
    groups = audit.get("physical_reconciliation_groups") or []
    candidate_map = {c["candidate_id"]: c for c in candidates}
    if len(groups) != audit.get("physical_reconciliation_group_count"):
        raise SystemExit("Audit physical group count does not match group payload.")

    prepared = []
    for group in groups:
        aliases = group_aliases(group, candidate_map)
        prepared.append((group, aliases))

    existing = read_json(REGISTRY_PATH)
    if existing is None:
        records = []
        for fixed_id, (group, aliases) in enumerate(sorted(prepared, key=initial_group_sort_key), 1):
            canon = canonical_alias(aliases)
            records.append(
                {
                    "fixed_object_id": fixed_id,
                    "status": "active",
                    "canonical_identity": canon,
                    "identifiers": aliases,
                    "source_refs": source_refs(group, candidate_map),
                }
            )
        mode = "initial_assignment"
        appended = len(records)
        preserved = 0
    else:
        records = existing.get("fixed_objects") or []
        by_id = {r["fixed_object_id"]: r for r in records}
        if len(by_id) != len(records):
            raise SystemExit("Duplicate fixed_object_id values already exist in registry.")
        if sorted(by_id) != list(range(1, max(by_id, default=0) + 1)):
            raise SystemExit("Existing registry IDs are not a contiguous historical sequence.")

        alias_index = registry_alias_index(records)
        group_matches = []
        used_existing_ids = set()
        new_groups = []

        for group, aliases in prepared:
            matches = {
                alias_index[alias_key(alias)]
                for alias in aliases
                if alias["namespace"] in MATCH_NAMESPACES and alias_key(alias) in alias_index
            }
            if len(matches) > 1:
                raise SystemExit(
                    f"Current physical group {group['provisional_group_id']} matches multiple permanent IDs: {sorted(matches)}"
                )
            if matches:
                fixed_id = next(iter(matches))
                if fixed_id in used_existing_ids:
                    raise SystemExit(
                        f"Permanent ID {fixed_id} matches more than one current physical group; possible split requires review."
                    )
                used_existing_ids.add(fixed_id)
                group_matches.append((fixed_id, group, aliases))
            else:
                new_groups.append((group, aliases))

        preserved = len(group_matches)
        next_id = max(by_id, default=0) + 1
        appended = 0

        for fixed_id, group, aliases in group_matches:
            record = by_id[fixed_id]
            merged_aliases = {
                alias_key(alias): alias for alias in (record.get("identifiers") or [])
            }
            for alias in aliases:
                merged_aliases[alias_key(alias)] = alias
            record["status"] = "active"
            record["identifiers"] = sorted(merged_aliases.values(), key=alias_sort_key)
            record["source_refs"] = source_refs(group, candidate_map)
            # canonical_identity is intentionally preserved once assigned.

        for group, aliases in sorted(new_groups, key=initial_group_sort_key):
            canon = canonical_alias(aliases)
            record = {
                "fixed_object_id": next_id,
                "status": "active",
                "canonical_identity": canon,
                "identifiers": aliases,
                "source_refs": source_refs(group, candidate_map),
            }
            records.append(record)
            by_id[next_id] = record
            next_id += 1
            appended += 1

        # IDs never disappear or get recycled. If an old object is absent from the
        # current audit, retain it and flag it for explicit identity review.
        for fixed_id, record in by_id.items():
            if fixed_id not in used_existing_ids and fixed_id <= max(by_id, default=0) - appended:
                record["status"] = "missing_from_current_audit"

        records.sort(key=lambda r: r["fixed_object_id"])
        mode = "preserve_and_append"

    result = {
        "schema_version": 1,
        "purpose": "Permanent immutable identity registry for physical fixed objects.",
        "id_policy": {
            "type": "sequential_integer",
            "immutable": True,
            "recycled": False,
            "initial_assignment": "deterministic",
            "subsequent_assignment": "preserve_existing_ids_and_append_new_ids",
        },
        "source_audit": str(AUDIT_PATH.relative_to(ROOT)),
        "source_audit_schema_version": audit.get("schema_version"),
        "build_mode": mode,
        "physical_object_count": len(records),
        "active_object_count": sum(r.get("status") == "active" for r in records),
        "preserved_id_count": preserved,
        "appended_id_count": appended,
        "fixed_objects": records,
    }

    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    REGISTRY_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {REGISTRY_PATH.relative_to(ROOT)}")
    print(
        f"Permanent IDs: {len(records)} total; {preserved} preserved; {appended} appended; mode={mode}"
    )


if __name__ == "__main__":
    main()
