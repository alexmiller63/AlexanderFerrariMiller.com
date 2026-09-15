#!/usr/bin/env python3
"""Audit Star Almanack fixed-object identity before permanent IDs are assigned."""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
OUT = SRC / "generated" / "fixed-object-identity-audit.json"
REVIEW_OUT = SRC / "generated" / "fixed-object-contradiction-review.json"
TARGET_LAYER = SRC / "database" / "catalog-entry-targets.json"
SUPPLEMENTAL_OBJECTS = SRC / "database" / "supplemental-physical-objects.json"

CATALOG_RE = re.compile(r"^(NGC|IC)\s*0*(\d+)$", re.I)
HIP_RE = re.compile(r"^HIP\s*0*(\d+)$", re.I)
SH2_RE = re.compile(r"^Sh\s*2\s*[- ]\s*0*(\d+)$", re.I)
VARIABLE_STAR_RE = re.compile(r"^([A-Z]{1,2}\d+)\s+([A-Za-z]{3})$")

CROSS_SOURCE_NAMESPACES = {
    "ngc", "ic", "hip", "hd", "gaia_dr3", "wds", "bayer", "sh2", "variable_star"
}
STABLE_SOURCE_NAMESPACES = {
    "messier", "caldwell", "finest_ngc", "special", "component", "asterism_member_label"
}
TYPE_FAMILIES = {
    "Gal": "galaxy", "ScG": "galaxy", "SbG": "galaxy", "dE0G": "galaxy",
    "E6G": "galaxy", "IG": "galaxy", "SG": "galaxy", "EG": "galaxy",
    "LG": "galaxy", "BG": "galaxy", "BN": "emission_nebula",
    "EN": "emission_nebula", "E/RN": "emission_nebula", "DN": "dark_nebula",
    "PN": "planetary_nebula", "OC": "open_cluster", "GC": "globular_cluster",
    "SN": "supernova_remnant", "SNR": "supernova_remnant", "DS": "double_star",
    "MW": "milky_way", "AS": "asterism", "star": "star"
}
PHYSICAL_TARGET_MODELS = {"physical_object_with_asterism"}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def norm_catalog(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "null":
        return None
    m = CATALOG_RE.match(text)
    if m:
        return f"{m.group(1).upper()} {int(m.group(2))}"
    if text.isdigit():
        return f"NGC {int(text)}"
    return text


def catalog_identifier(value):
    cat = norm_catalog(value)
    if not cat:
        return None
    m = CATALOG_RE.match(cat)
    if m:
        return (m.group(1).lower(), str(int(m.group(2))))
    m = HIP_RE.match(cat)
    if m:
        return ("hip", str(int(m.group(1))))
    m = SH2_RE.match(cat)
    if m:
        return ("sh2", str(int(m.group(1))))
    m = VARIABLE_STAR_RE.match(cat)
    if m:
        return ("variable_star", f"{m.group(1)} {m.group(2)}")
    return ("catalog_label", cat)


def type_family(value):
    return TYPE_FAMILIES.get(value, value) if value else None


def schemas():
    return {
        "messier": ["id", "ngc", "name", "type", "con", "ra_h", "dec_deg", "mag", "size_arcmin", "best", "iso"],
        "bayer": ["bayer", "con", "name", "ra_h", "dec_deg", "mag", "best", "iso"],
        "special": ["id", "name", "catalog", "con", "ra_h", "dec_deg", "mag", "best", "iso", "note"],
        "component": ["bayer", "con", "component", "name", "ra_h", "dec_deg", "mag"],
    }


def parse_fixed_simple_yaml(path):
    schema = schemas()
    result = {key: [] for key in schema}
    current = None
    inside_schema = True
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith(" ") and raw.rstrip().endswith(":"):
            key = raw.strip()[:-1]
            inside_schema = key == "schema"
            current = None if inside_schema else (key if key in schema else None)
            continue
        if inside_schema or current is None:
            continue
        text = raw.strip()
        if text.startswith("- [") and text.endswith("]"):
            values = next(csv.reader([text[3:-1]], skipinitialspace=True))
            result[current].append([None if v.strip().lower() == "null" else v.strip() for v in values])
    return result


def row_dict(section, values):
    names = schemas()[section]
    return {names[i]: values[i] if i < len(values) else None for i in range(len(names))}


def add_candidate(cs, source, key, ids, name=None, con=None, ra_h=None, dec_deg=None, obj_type=None, notes=None):
    clean = []
    seen = set()
    for namespace, value in ids:
        if value is None:
            continue
        value = str(value).strip()
        pair = (namespace, value)
        if not value or value.lower() == "null" or pair in seen:
            continue
        seen.add(pair)
        clean.append({"namespace": namespace, "value": value})
    cs.append({
        "candidate_id": len(cs) + 1,
        "source": source,
        "source_key": key,
        "identifiers": clean,
        "name": name or None,
        "constellation": con or None,
        "ra_h": ra_h if ra_h is not None else None,
        "dec_deg": dec_deg if dec_deg is not None else None,
        "object_type": obj_type or None,
        "object_type_family": type_family(obj_type),
        "notes": notes or None,
        "identity_role": "physical_object_candidate",
    })


def load_source_candidates():
    cs = []
    fixed = parse_fixed_simple_yaml(SRC / "fixed-objects.yaml")
    for section, rows in fixed.items():
        for n, values in enumerate(rows, 1):
            row = row_dict(section, values)
            ids = []
            key = f"{section}:{n}"
            if section == "messier":
                ids = [("messier", row["id"])]
                ident = catalog_identifier(row["ngc"])
                ids += [ident] if ident else []
                key = str(row["id"])
            elif section == "bayer":
                ids = [("bayer", f"{row['bayer']} {row['con']}")]
                key = f"{row['bayer']} {row['con']}"
            elif section == "special":
                ids = [("special", row["id"])]
                ident = catalog_identifier(row["catalog"])
                ids += [ident] if ident else []
                key = str(row["id"])
            elif section == "component":
                ids = [("bayer", f"{row['bayer']} {row['con']}"), ("component", row["component"])]
                key = f"{row['bayer']} {row['con']}:{row['component']}"
            add_candidate(cs, f"fixed-objects.yaml:{section}", key, ids, row.get("name"), row.get("con"), row.get("ra_h"), row.get("dec_deg"), row.get("type"), row.get("note"))

    for row in read_csv(SRC / "caldwell-catalog.csv"):
        ids = [("caldwell", row.get("caldwell"))]
        ident = catalog_identifier(row.get("catalog"))
        ids += [ident] if ident else []
        add_candidate(cs, "caldwell-catalog.csv", row.get("caldwell", ""), ids, row.get("name"), row.get("con"), row.get("ra_h"), row.get("dec_deg"), row.get("type"))

    for row in read_csv(SRC / "finest-ngc-catalog.csv"):
        ids = [("finest_ngc", row.get("finest_ngc"))]
        ident = catalog_identifier(row.get("catalog"))
        ids += [ident] if ident else []
        add_candidate(cs, "finest-ngc-catalog.csv", row.get("finest_ngc", ""), ids, row.get("name"), row.get("con"), row.get("ra_h"), row.get("dec_deg"), row.get("type"))

    for n, row in enumerate(read_csv(SRC / "asterism-member-coordinates.csv"), 1):
        ids = []
        hip = HIP_RE.match((row.get("coordinate_source_id") or "").strip())
        ids += [("hip", str(int(hip.group(1))))] if hip else []
        ids.append(("asterism_member_label", row.get("member")))
        add_candidate(cs, "asterism-member-coordinates.csv", f"row:{n}", ids, row.get("resolved_object"), None, row.get("ra_h"), row.get("dec_deg"), "star", f"asterism={row.get('asterism', '')}")
    return cs


def append_supplemental_candidates(cs):
    data = read_json(SUPPLEMENTAL_OBJECTS)
    validation = {
        "path": str(SUPPLEMENTAL_OBJECTS.relative_to(ROOT)),
        "loaded": data is not None,
        "object_count": 0,
        "candidate_ids": [],
        "errors": [],
    }
    if data is None:
        validation["errors"].append("supplemental physical-object file is missing")
        return validation
    objects = data.get("objects") or []
    validation["object_count"] = len(objects)
    seen_keys = set()
    for obj in objects:
        key = str(obj.get("supplemental_key") or "").strip()
        if not key or key in seen_keys:
            validation["errors"].append(f"invalid or duplicate supplemental_key: {key!r}")
            continue
        seen_keys.add(key)
        ids = [(str(i.get("namespace") or "").strip(), str(i.get("value") or "").strip()) for i in (obj.get("identifiers") or [])]
        if not any(ns and value for ns, value in ids):
            validation["errors"].append(f"{key}: no identifiers")
            continue
        add_candidate(cs, "database/supplemental-physical-objects.json", key, ids, obj.get("name"), obj.get("constellation"), obj.get("ra_h"), obj.get("dec_deg"), obj.get("object_type"), obj.get("source_note"))
        cs[-1]["object_type_family"] = obj.get("object_type_family") or cs[-1]["object_type_family"]
        cs[-1]["supplemental_source"] = obj.get("source")
        cs[-1]["supplemental_source_record"] = obj.get("source_record")
        validation["candidate_ids"].append(cs[-1]["candidate_id"])
    return validation


def angular_sep_deg(a, b):
    try:
        r1, d1 = math.radians(float(a["ra_h"]) * 15), math.radians(float(a["dec_deg"]))
        r2, d2 = math.radians(float(b["ra_h"]) * 15), math.radians(float(b["dec_deg"]))
    except (TypeError, ValueError):
        return None
    x = max(-1, min(1, math.sin(d1) * math.sin(d2) + math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)))
    return math.degrees(math.acos(x))


def reconcile(cs):
    parent = {c["candidate_id"]: c["candidate_id"] for c in cs}
    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        a, b = find(a), find(b)
        if a != b:
            parent[max(a, b)] = min(a, b)

    by = defaultdict(list)
    for c in cs:
        for ident in c["identifiers"]:
            if ident["namespace"] in CROSS_SOURCE_NAMESPACES:
                by[(ident["namespace"], ident["value"])].append(c["candidate_id"])
    for ids in by.values():
        for candidate_id in ids[1:]:
            union(ids[0], candidate_id)

    grouped = defaultdict(list)
    for c in cs:
        grouped[find(c["candidate_id"])].append(c["candidate_id"])
    cmap = {c["candidate_id"]: c for c in cs}
    groups = []
    for number, ids in enumerate(sorted(grouped.values(), key=min), 1):
        idset = set(ids)
        evidence = []
        for (namespace, value), members in sorted(by.items()):
            shared = sorted(idset.intersection(members))
            if len(shared) > 1:
                evidence.append({"namespace": namespace, "value": value, "candidate_ids": shared})
        contradictions = []
        max_sep = 0.0
        if len(ids) > 1:
            rows = [cmap[i] for i in ids]
            constellations = sorted({r["constellation"] for r in rows if r["constellation"]})
            raw_types = sorted({r["object_type"] for r in rows if r["object_type"]})
            families = sorted({r["object_type_family"] for r in rows if r["object_type_family"]})
            if len(constellations) > 1:
                contradictions.append({"kind": "constellation", "values": constellations, "severity": "boundary_review"})
            if len(families) > 1:
                contradictions.append({"kind": "object_type_family", "values": families, "raw_values": raw_types, "severity": "review"})
            for x in range(len(rows)):
                for y in range(x + 1, len(rows)):
                    sep = angular_sep_deg(rows[x], rows[y])
                    max_sep = max(max_sep, sep or 0.0)
            if max_sep > 1.0:
                contradictions.append({"kind": "coordinates", "max_separation_deg": round(max_sep, 6), "severity": "review"})
        status = "singleton" if len(ids) == 1 else ("contradiction_review" if contradictions else "validated_exact_identifier")
        groups.append({
            "provisional_group_id": number,
            "candidate_ids": sorted(ids),
            "candidate_count": len(ids),
            "merge_evidence": evidence,
            "max_coordinate_separation_deg": round(max_sep, 6) if len(ids) > 1 else None,
            "contradictions": contradictions,
            "review_status": status,
        })
    return groups, by


def apply_catalog_target_layer(cs):
    layer = read_json(TARGET_LAYER)
    validation = {
        "path": str(TARGET_LAYER.relative_to(ROOT)),
        "loaded": layer is not None,
        "catalog_entry_count": 0,
        "resolved_entry_count": 0,
        "excluded_catalog_target_candidate_count": 0,
        "physical_candidate_entry_count": 0,
        "unresolved_target_identifier_count": 0,
        "unresolved_target_identifiers": [],
        "errors": [],
        "warnings": [],
    }
    if layer is None:
        validation["errors"].append("catalog target relationship layer is missing")
        return validation

    entries = layer.get("catalog_entries") or []
    validation["catalog_entry_count"] = len(entries)
    cmap = {c["candidate_id"]: c for c in cs}
    by_source_key = {(c["source"], str(c["source_key"])): c for c in cs}
    identifiers = defaultdict(list)
    for c in cs:
        for ident in c["identifiers"]:
            identifiers[(ident["namespace"], ident["value"])].append(c["candidate_id"])

    seen_candidate_ids = set()
    for entry in entries:
        cid = entry.get("audit_candidate_id")
        source = entry.get("source")
        source_key = str(entry.get("source_key") or "")
        target_model = entry.get("target_model")
        expected = by_source_key.get((source, source_key))
        candidate = cmap.get(cid)
        if candidate is None:
            validation["errors"].append(f"{entry.get('catalog_entry_key')}: audit_candidate_id {cid} does not exist")
            continue
        if expected is None or expected["candidate_id"] != cid:
            validation["errors"].append(f"{entry.get('catalog_entry_key')}: source/source_key does not match candidate {cid}")
            continue
        if cid in seen_candidate_ids:
            validation["errors"].append(f"{entry.get('catalog_entry_key')}: candidate {cid} appears more than once")
            continue
        seen_candidate_ids.add(cid)
        validation["resolved_entry_count"] += 1
        candidate["catalog_entry_key"] = entry.get("catalog_entry_key")
        candidate["catalog_target_model"] = target_model
        if target_model in PHYSICAL_TARGET_MODELS:
            validation["physical_candidate_entry_count"] += 1
        else:
            candidate["identity_role"] = "catalog_target_only"
            validation["excluded_catalog_target_candidate_count"] += 1

        for target in entry.get("targets") or []:
            if target.get("target_kind") != "physical_object_identifier":
                continue
            ident = target.get("identifier") or {}
            ns, value = str(ident.get("namespace") or "").strip(), str(ident.get("value") or "").strip()
            if not ns or not value:
                validation["errors"].append(f"{entry.get('catalog_entry_key')}: physical_object_identifier target is incomplete")
                continue
            if not identifiers.get((ns, value)):
                validation["unresolved_target_identifiers"].append({
                    "catalog_entry_key": entry.get("catalog_entry_key"),
                    "namespace": ns,
                    "value": value,
                    "display_name": target.get("display_name"),
                })

    validation["unresolved_target_identifier_count"] = len(validation["unresolved_target_identifiers"])
    if validation["unresolved_target_identifier_count"]:
        validation["warnings"].append("Some catalog-entry physical targets are not yet represented by a candidate.")
    return validation


def main():
    cs = load_source_candidates()
    original_candidate_count = len(cs)
    supplemental_validation = append_supplemental_candidates(cs)
    target_validation = apply_catalog_target_layer(cs)

    groups, by = reconcile(cs)
    physical_candidates = [c for c in cs if c["identity_role"] == "physical_object_candidate"]
    physical_groups, physical_by = reconcile(physical_candidates)

    overlaps = [{"namespace": ns, "value": value, "candidate_ids": ids} for (ns, value), ids in sorted(by.items()) if len(ids) > 1]
    physical_overlaps = [{"namespace": ns, "value": value, "candidate_ids": ids} for (ns, value), ids in sorted(physical_by.items()) if len(ids) > 1]
    explicit = {
        "finest_ngc_caldwell": read_csv(SRC / "finest-ngc-caldwell-overlap.csv"),
        "asterism_catalog": read_csv(SRC / "asterism-catalog-overlap.csv"),
    }
    counts = Counter(c["source"] for c in cs)
    identifier_counts = Counter(i["namespace"] for c in cs for i in c["identifiers"])
    no_cross = [c["candidate_id"] for c in cs if not any(i["namespace"] in CROSS_SOURCE_NAMESPACES for i in c["identifiers"])]
    no_cross_physical = [c["candidate_id"] for c in physical_candidates if not any(i["namespace"] in CROSS_SOURCE_NAMESPACES for i in c["identifiers"])]
    no_any = [c["candidate_id"] for c in cs if not c["identifiers"]]

    merged = [g for g in groups if g["candidate_count"] > 1]
    review = [g for g in merged if g["contradictions"]]
    validated = [g for g in merged if not g["contradictions"]]
    physical_merged = [g for g in physical_groups if g["candidate_count"] > 1]
    physical_review = [g for g in physical_merged if g["contradictions"]]
    physical_validated = [g for g in physical_merged if not g["contradictions"]]

    blockers = []
    if supplemental_validation["errors"]:
        blockers.append("supplemental_physical_object_errors")
    if target_validation["errors"]:
        blockers.append("catalog_target_layer_errors")
    if target_validation["unresolved_target_identifier_count"]:
        blockers.append("unresolved_catalog_target_identifiers")
    m40 = next((e for e in (read_json(TARGET_LAYER) or {}).get("catalog_entries", []) if e.get("catalog_entry_key") == "messier:M40"), None)
    if m40 and m40.get("component_resolution_status") != "resolved":
        blockers.append("m40_component_resolution")

    registry_ready = not blockers and not physical_review
    result = {
        "schema_version": 9,
        "purpose": "pre-migration physical fixed-object identity audit; no permanent IDs assigned",
        "canonical_source": "Star-Almanack-Repo/fixed-objects.yaml",
        "original_candidate_count": original_candidate_count,
        "supplemental_physical_objects": supplemental_validation,
        "catalog_target_relationship_layer": target_validation,
        "candidate_count": len(cs),
        "physical_object_candidate_count": len(physical_candidates),
        "catalog_target_only_candidate_count": len(cs) - len(physical_candidates),
        "provisional_reconciliation_group_count": len(groups),
        "provisional_merged_group_count": len(merged),
        "provisional_singleton_group_count": len(groups) - len(merged),
        "validated_exact_identifier_group_count": len(validated),
        "contradiction_review_group_count": len(review),
        "physical_reconciliation_group_count": len(physical_groups),
        "physical_merged_group_count": len(physical_merged),
        "physical_singleton_group_count": len(physical_groups) - len(physical_merged),
        "physical_validated_exact_identifier_group_count": len(physical_validated),
        "physical_contradiction_review_group_count": len(physical_review),
        "physical_registry_ready": registry_ready,
        "physical_registry_blockers": blockers,
        "source_counts": dict(sorted(counts.items())),
        "identifier_counts": dict(sorted(identifier_counts.items())),
        "cross_source_identifier_namespaces": sorted(CROSS_SOURCE_NAMESPACES),
        "stable_source_identifier_namespaces": sorted(STABLE_SOURCE_NAMESPACES),
        "object_type_families": TYPE_FAMILIES,
        "cross_source_identifier_overlap_count": len(overlaps),
        "cross_source_identifier_overlaps": overlaps,
        "physical_cross_source_identifier_overlap_count": len(physical_overlaps),
        "physical_cross_source_identifier_overlaps": physical_overlaps,
        "candidates_without_cross_source_identifier": no_cross,
        "physical_candidates_without_cross_source_identifier": no_cross_physical,
        "candidates_without_any_identifier": no_any,
        "explicit_overlap_counts": {k: len(v) for k, v in explicit.items()},
        "warnings": [],
        "provisional_reconciliation_groups": groups,
        "physical_reconciliation_groups": physical_groups,
        "candidates": cs,
        "explicit_overlap_records": explicit,
    }

    cmap = {c["candidate_id"]: c for c in cs}
    review_result = {
        "schema_version": 5,
        "purpose": "focused review after catalog-target separation and supplemental physical-object resolution",
        "group_count": len(physical_review),
        "groups": [dict(g, candidates=[cmap[i] for i in g["candidate_ids"]]) for g in physical_review],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    REVIEW_OUT.write_text(json.dumps(review_result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Wrote {REVIEW_OUT.relative_to(ROOT)}")
    print(f"Candidates: {len(cs)}; physical candidates: {len(physical_candidates)}")
    print(f"Supplemental physical objects: {supplemental_validation['object_count']}")
    print(f"Physical groups: {len(physical_groups)}; merged: {len(physical_merged)}; validated: {len(physical_validated)}; review: {len(physical_review)}")
    print(f"Catalog-target exclusions: {len(cs) - len(physical_candidates)}; unresolved target identifiers: {target_validation['unresolved_target_identifier_count']}")
    print(f"Physical registry ready: {registry_ready}; blockers: {blockers}")
    print("No fixed_object_id values were assigned.")


if __name__ == "__main__":
    main()
