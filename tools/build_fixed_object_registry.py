#!/usr/bin/env python3
"""Build and maintain the permanent Star Almanack fixed-object registry.

The initial registry is assigned deterministically from the reconciled physical
identity audit. After creation, existing fixed_object_id values are immutable:
reruns preserve IDs by matching stable identifiers and append new IDs only for
new physical identities. Ambiguous merges/splits fail loudly for human review.
Human-reviewed historical duplicate IDs may be redirected explicitly through
fixed-object-id-merges.json; IDs are never recycled or silently discarded.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT
AUDIT_PATH = SRC / "generated" / "fixed-object-identity-audit.json"
REGISTRY_PATH = SRC / "database" / "fixed-object-registry.json"
MERGES_PATH = SRC / "database" / "fixed-object-id-merges.json"
COLLISION_REPORT_PATH = SRC / "generated" / "fixed-object-identity-collisions.json"

MATCH_NAMESPACES = {
    "ngc", "ic", "hip", "hd", "gaia_dr3", "wds", "bayer", "sh2",
    "variable_star", "messier", "caldwell", "finest_ngc", "special", "component",
}

NAMESPACE_PRIORITY = {
    "hip": 0, "hd": 1, "gaia_dr3": 2, "wds": 3, "ngc": 4, "ic": 5,
    "sh2": 6, "bayer": 7, "variable_star": 8, "messier": 9, "caldwell": 10,
    "finest_ngc": 11, "special": 12, "component": 13,
    "asterism_member_label": 14, "catalog_label": 15,
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
        refs.append({"source": candidate["source"], "source_key": candidate["source_key"]})
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


def load_merge_redirects(records):
    payload = read_json(MERGES_PATH) or {"merges": []}
    known_ids = {r["fixed_object_id"] for r in records}
    redirects = {}
    for item in payload.get("merges") or []:
        retired = int(item["retired_fixed_object_id"])
        survivor = int(item["surviving_fixed_object_id"])
        if retired == survivor:
            raise SystemExit(f"Invalid fixed-object merge {retired} -> itself")
        if retired not in known_ids or survivor not in known_ids:
            raise SystemExit(f"Fixed-object merge references unknown ID: {retired} -> {survivor}")
        if retired in redirects and redirects[retired] != survivor:
            raise SystemExit(f"Conflicting fixed-object merge for ID {retired}")
        redirects[retired] = survivor

    def resolve(fixed_id):
        seen = set()
        while fixed_id in redirects:
            if fixed_id in seen:
                raise SystemExit("Cycle in fixed-object ID merge redirects")
            seen.add(fixed_id)
            fixed_id = redirects[fixed_id]
        return fixed_id

    return {retired: resolve(survivor) for retired, survivor in redirects.items()}


def registry_alias_index(records, redirects=None):
    redirects = redirects or {}
    index = {}
    for record in records:
        fixed_id = record["fixed_object_id"]
        effective_id = redirects.get(fixed_id, fixed_id)
        for alias in record.get("identifiers") or []:
            key = alias_key(alias)
            prior = index.get(key)
            if prior is not None and prior != effective_id:
                raise SystemExit(f"Registry identifier collision {key}: fixed_object_id {prior} and {effective_id}")
            if alias["namespace"] in MATCH_NAMESPACES:
                index[key] = effective_id
    return index


def classify_identity_collision(group, aliases, matches, alias_index, by_id, candidate_map):
    evidence = {}
    for alias in aliases:
        key = alias_key(alias)
        fixed_id = alias_index.get(key)
        if fixed_id in matches:
            evidence.setdefault(fixed_id, []).append(alias)

    namespaces = {alias["namespace"] for items in evidence.values() for alias in items}
    refs = source_refs(group, candidate_map)
    sources = {ref["source"] for ref in refs}

    if "figure_stars" in sources or any("figure" in source.casefold() for source in sources):
        classification = "figure_star_introduction"
    elif len(matches) == 2 and any(ns in namespaces for ns in {"hip", "hd", "gaia_dr3", "wds"}):
        classification = "likely_historical_duplicate_identity"
    elif len(matches) == 2:
        classification = "likely_legacy_permanent_id_duplicate"
    else:
        classification = "multi_id_ambiguous_identity"

    return {
        "type": "physical_group_matches_multiple_permanent_ids",
        "classification": classification,
        "provisional_group_id": group["provisional_group_id"],
        "permanent_ids": matches,
        "matching_identifiers_by_permanent_id": {
            str(fixed_id): sorted(evidence.get(fixed_id, []), key=alias_sort_key)
            for fixed_id in matches
        },
        "permanent_id_canonical_identities": {
            str(fixed_id): by_id[fixed_id].get("canonical_identity")
            for fixed_id in matches if fixed_id in by_id
        },
        "current_group_identifiers": aliases,
        "source_refs": refs,
    }


def write_collision_report(identity_details, split_collisions, by_id):
    classifications = Counter(item["classification"] for item in identity_details)
    split_details = []
    for fixed_id, group_id in split_collisions:
        split_details.append({
            "type": "permanent_id_matches_multiple_physical_groups",
            "classification": "physical_identity_split",
            "fixed_object_id": fixed_id,
            "additional_provisional_group_id": group_id,
            "canonical_identity": by_id.get(fixed_id, {}).get("canonical_identity"),
        })
    if split_details:
        classifications["physical_identity_split"] += len(split_details)

    payload = {
        "schema_version": 1,
        "purpose": "Complete fixed-object identity collision classification for batch review.",
        "total_collision_count": len(identity_details) + len(split_details),
        "classification_counts": dict(sorted(classifications.items())),
        "identity_collisions": identity_details,
        "split_collisions": split_details,
    }
    COLLISION_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    COLLISION_REPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def main():
    audit = read_json(AUDIT_PATH)
    if audit is None:
        raise SystemExit(f"Missing audit: {AUDIT_PATH}")
    if not audit.get("physical_registry_ready"):
        raise SystemExit("Physical registry is not ready; blockers: " + repr(audit.get("physical_registry_blockers")))
    if audit.get("physical_contradiction_review_group_count") != 0:
        raise SystemExit("Physical contradiction reviews remain unresolved.")

    candidates = audit.get("candidates") or []
    groups = audit.get("physical_reconciliation_groups") or []
    candidate_map = {c["candidate_id"]: c for c in candidates}
    if len(groups) != audit.get("physical_reconciliation_group_count"):
        raise SystemExit("Audit physical group count does not match group payload.")

    prepared = [(group, group_aliases(group, candidate_map)) for group in groups]
    existing = read_json(REGISTRY_PATH)

    if existing is None:
        records = []
        for fixed_id, (group, aliases) in enumerate(sorted(prepared, key=initial_group_sort_key), 1):
            records.append({
                "fixed_object_id": fixed_id,
                "status": "active",
                "canonical_identity": canonical_alias(aliases),
                "identifiers": aliases,
                "source_refs": source_refs(group, candidate_map),
            })
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

        redirects = load_merge_redirects(records)
        alias_index = registry_alias_index(records, redirects)
        group_matches = []
        used_existing_ids = set()
        new_groups = []
        identity_collisions = []
        split_collisions = []
        for group, aliases in prepared:
            matches = {
                alias_index[alias_key(alias)]
                for alias in aliases
                if alias["namespace"] in MATCH_NAMESPACES and alias_key(alias) in alias_index
            }
            if len(matches) > 1:
                sorted_matches = sorted(matches)
                identity_collisions.append(classify_identity_collision(
                    group, aliases, sorted_matches, alias_index, by_id, candidate_map
                ))
                continue
            if matches:
                fixed_id = next(iter(matches))
                if fixed_id in used_existing_ids:
                    split_collisions.append((fixed_id, group["provisional_group_id"]))
                    continue
                used_existing_ids.add(fixed_id)
                group_matches.append((fixed_id, group, aliases))
            else:
                new_groups.append((group, aliases))

        if identity_collisions or split_collisions:
            report = write_collision_report(identity_collisions, split_collisions, by_id)
            print("Fixed-object identity validation failed:")
            print(f"\nCollected {report['total_collision_count']} collision(s) into {COLLISION_REPORT_PATH.relative_to(ROOT)}")
            print("Classification summary:")
            for classification, count in report["classification_counts"].items():
                print(f"  {classification}: {count}")
            print("\nPhysical groups matching multiple permanent IDs:")
            for item in identity_collisions:
                print(f"  Physical group {item['provisional_group_id']} -> permanent IDs {item['permanent_ids']} [{item['classification']}]")
            if split_collisions:
                print("\nPermanent IDs matching more than one current physical group:")
                for fixed_id, group_id in split_collisions:
                    print(f"  Permanent ID {fixed_id} -> additional physical group {group_id} [physical_identity_split]")
            raise SystemExit(f"\n{report['total_collision_count']} fixed-object identity collision(s) require review; registry not built.")

        preserved = len(group_matches)
        next_id = max(by_id, default=0) + 1
        appended = 0
        for fixed_id, group, aliases in group_matches:
            record = by_id[fixed_id]
            merged_aliases = {alias_key(alias): alias for alias in (record.get("identifiers") or [])}
            for alias in aliases:
                merged_aliases[alias_key(alias)] = alias
            record["status"] = "active"
            record.pop("merged_into_fixed_object_id", None)
            record["identifiers"] = sorted(merged_aliases.values(), key=alias_sort_key)
            record["source_refs"] = source_refs(group, candidate_map)

        historical_max = max(by_id, default=0)
        for group, aliases in sorted(new_groups, key=initial_group_sort_key):
            record = {
                "fixed_object_id": next_id,
                "status": "active",
                "canonical_identity": canonical_alias(aliases),
                "identifiers": aliases,
                "source_refs": source_refs(group, candidate_map),
            }
            records.append(record)
            by_id[next_id] = record
            next_id += 1
            appended += 1

        for fixed_id, record in by_id.items():
            if fixed_id in redirects:
                record["status"] = "merged_historical_duplicate"
                record["merged_into_fixed_object_id"] = redirects[fixed_id]
            elif fixed_id not in used_existing_ids and fixed_id <= historical_max:
                record["status"] = "missing_from_current_audit"
                record.pop("merged_into_fixed_object_id", None)

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
    print(f"Permanent IDs: {len(records)} total; {preserved} preserved; {appended} appended; mode={mode}")


if __name__ == "__main__":
    main()
