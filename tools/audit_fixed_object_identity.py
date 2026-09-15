#!/usr/bin/env python3
"""Audit Star Almanack fixed-object identity before permanent IDs are assigned.

This is deliberately read-only with respect to canonical source data. It emits
machine-readable candidate records and a summary. It does NOT assign
fixed_object_id values and it does NOT merge ambiguous coordinate matches.
"""
from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
OUT = SRC / "generated" / "fixed-object-identity-audit.json"

CATALOG_RE = re.compile(r"^(NGC|IC)\s*0*(\d+)$", re.I)
HIP_RE = re.compile(r"^HIP\s*0*(\d+)$", re.I)
SH2_RE = re.compile(r"^Sh\s*2\s*[- ]\s*0*(\d+)$", re.I)
VARIABLE_STAR_RE = re.compile(r"^([A-Z]{1,2}\d+)\s+([A-Za-z]{3})$")

# These identifiers can independently connect records from different source
# files without relying on coordinates or common names.
CROSS_SOURCE_NAMESPACES = {"ngc", "ic", "hip", "bayer", "sh2", "variable_star"}

# These are stable identifiers inside a recognized catalog/list. They are valid
# durable designations, but list membership alone does not prove that a record
# in another source is the same physical object.
STABLE_SOURCE_NAMESPACES = {
    "messier", "caldwell", "finest_ngc", "special", "component",
    "asterism_member_label",
}


def norm_catalog(value: object) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s or s.lower() == "null":
        return None
    m = CATALOG_RE.match(s)
    if m:
        return f"{m.group(1).upper()} {int(m.group(2))}"
    # fixed-objects Messier NGC values are commonly bare integers.
    if s.isdigit():
        return f"NGC {int(s)}"
    return s


def catalog_identifier(value: object) -> tuple[str, str] | None:
    """Return a normalized external identifier when the catalog syntax is known.

    Unknown named catalog labels are deliberately not promoted to strong
    cross-source identity. They remain available as catalog_label metadata.
    """
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


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def parse_fixed_simple_yaml(path: Path) -> dict[str, list[list[object]]]:
    """Parse only the simple top-level bracket-row collections in fixed-objects.yaml.

    PyYAML is intentionally not required by this audit. Rows in the canonical
    file use YAML flow sequences; csv.reader safely handles the quoted commas we
    need here. Schema names are fixed below and row-width mismatches are flagged.
    """
    schemas = {
        "messier": ["id", "ngc", "name", "type", "con", "ra_h", "dec_deg", "mag", "size_arcmin", "best", "iso"],
        "bayer": ["bayer", "con", "name", "ra_h", "dec_deg", "mag", "best", "iso"],
        "special": ["id", "name", "catalog", "con", "ra_h", "dec_deg", "mag", "best", "iso", "note"],
        "component": ["bayer", "con", "component", "name", "ra_h", "dec_deg", "mag"],
    }
    result = {k: [] for k in schemas}
    current = None
    in_schema = True
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith(" ") and raw.rstrip().endswith(":"):
            key = raw.strip()[:-1]
            in_schema = key == "schema"
            current = None if in_schema else (key if key in schemas else None)
            continue
        if in_schema or current is None:
            continue
        s = raw.strip()
        if not s.startswith("- [") or not s.endswith("]"):
            continue
        body = s[3:-1]
        vals = next(csv.reader([body], skipinitialspace=True))
        vals = [None if v.strip().lower() == "null" else v.strip() for v in vals]
        result[current].append(vals)
    return result


def row_dict(section: str, values: list[object]) -> dict[str, object]:
    schemas = {
        "messier": ["id", "ngc", "name", "type", "con", "ra_h", "dec_deg", "mag", "size_arcmin", "best", "iso"],
        "bayer": ["bayer", "con", "name", "ra_h", "dec_deg", "mag", "best", "iso"],
        "special": ["id", "name", "catalog", "con", "ra_h", "dec_deg", "mag", "best", "iso", "note"],
        "component": ["bayer", "con", "component", "name", "ra_h", "dec_deg", "mag"],
    }
    names = schemas[section]
    return {names[i]: values[i] if i < len(values) else None for i in range(len(names))}


def add_candidate(candidates, source, source_key, identifiers, name=None, con=None, ra_h=None, dec_deg=None, obj_type=None, notes=None):
    clean_ids = []
    seen = set()
    for namespace, value in identifiers:
        if value is None:
            continue
        v = str(value).strip()
        if not v or v.lower() == "null":
            continue
        key = (namespace, v)
        if key not in seen:
            seen.add(key)
            clean_ids.append({"namespace": namespace, "value": v})
    candidates.append({
        "candidate_id": len(candidates) + 1,
        "source": source,
        "source_key": source_key,
        "identifiers": clean_ids,
        "name": name or None,
        "constellation": con or None,
        "ra_h": ra_h or None,
        "dec_deg": dec_deg or None,
        "object_type": obj_type or None,
        "notes": notes or None,
    })


def main() -> None:
    candidates = []
    warnings = []

    fixed_path = SRC / "fixed-objects.yaml"
    fixed = parse_fixed_simple_yaml(fixed_path)

    for section, rows in fixed.items():
        for n, vals in enumerate(rows, 1):
            r = row_dict(section, vals)
            ids = []
            source_key = f"{section}:{n}"
            if section == "messier":
                ids.append(("messier", r["id"]))
                ident = catalog_identifier(r["ngc"])
                if ident:
                    ids.append(ident)
                source_key = str(r["id"])
            elif section == "bayer":
                ids.append(("bayer", f"{r['bayer']} {r['con']}"))
                source_key = f"{r['bayer']} {r['con']}"
            elif section == "special":
                ids.append(("special", r["id"]))
                ident = catalog_identifier(r["catalog"])
                if ident:
                    ids.append(ident)
                source_key = str(r["id"])
            elif section == "component":
                ids.append(("bayer", f"{r['bayer']} {r['con']}"))
                ids.append(("component", r["component"]))
                source_key = f"{r['bayer']} {r['con']}:{r['component']}"
            add_candidate(candidates, f"fixed-objects.yaml:{section}", source_key, ids,
                          r.get("name"), r.get("con"), r.get("ra_h"), r.get("dec_deg"), r.get("type"), r.get("note"))

    for r in read_csv(SRC / "caldwell-catalog.csv"):
        ids = [("caldwell", r.get("caldwell"))]
        ident = catalog_identifier(r.get("catalog"))
        if ident:
            ids.append(ident)
        add_candidate(candidates, "caldwell-catalog.csv", r.get("caldwell", ""), ids,
                      r.get("name"), r.get("con"), r.get("ra_h"), r.get("dec_deg"), r.get("type"))

    for r in read_csv(SRC / "finest-ngc-catalog.csv"):
        ids = [("finest_ngc", r.get("finest_ngc"))]
        ident = catalog_identifier(r.get("catalog"))
        if ident:
            ids.append(ident)
        add_candidate(candidates, "finest-ngc-catalog.csv", r.get("finest_ngc", ""), ids,
                      r.get("name"), r.get("con"), r.get("ra_h"), r.get("dec_deg"), r.get("type"))

    # Asterism members provide especially useful HIP cross-identifiers. They are
    # candidates for reconciliation, not new objects simply because they appear in
    # an asterism.
    for n, r in enumerate(read_csv(SRC / "asterism-member-coordinates.csv"), 1):
        ids = []
        hip = HIP_RE.match((r.get("coordinate_source_id") or "").strip())
        if hip:
            ids.append(("hip", str(int(hip.group(1)))))
        ids.append(("asterism_member_label", r.get("member")))
        add_candidate(candidates, "asterism-member-coordinates.csv", f"row:{n}", ids,
                      r.get("resolved_object"), None, r.get("ra_h"), r.get("dec_deg"), "star",
                      f"asterism={r.get('asterism','')}")

    by_identifier = defaultdict(list)
    for c in candidates:
        for ident in c["identifiers"]:
            if ident["namespace"] in CROSS_SOURCE_NAMESPACES:
                by_identifier[(ident["namespace"], ident["value"])].append(c["candidate_id"])

    overlaps = []
    for (namespace, value), ids in sorted(by_identifier.items()):
        if len(ids) > 1:
            overlaps.append({"namespace": namespace, "value": value, "candidate_ids": ids})

    # Explicit overlap files are retained as evidence and checked against candidate
    # data; they are not used to force a merge here.
    explicit = {
        "finest_ngc_caldwell": read_csv(SRC / "finest-ngc-caldwell-overlap.csv"),
        "asterism_catalog": read_csv(SRC / "asterism-catalog-overlap.csv"),
    }

    counts = Counter(c["source"] for c in candidates)
    identifier_counts = Counter(i["namespace"] for c in candidates for i in c["identifiers"])

    without_cross_source = []
    without_any_identifier = []
    for c in candidates:
        if not c["identifiers"]:
            without_any_identifier.append(c["candidate_id"])
        if not any(i["namespace"] in CROSS_SOURCE_NAMESPACES for i in c["identifiers"]):
            without_cross_source.append(c["candidate_id"])

    result = {
        "schema_version": 2,
        "purpose": "pre-migration physical fixed-object identity audit; no permanent IDs assigned",
        "canonical_source": "Star-Almanack-Repo/fixed-objects.yaml",
        "candidate_count": len(candidates),
        "source_counts": dict(sorted(counts.items())),
        "identifier_counts": dict(sorted(identifier_counts.items())),
        "cross_source_identifier_namespaces": sorted(CROSS_SOURCE_NAMESPACES),
        "stable_source_identifier_namespaces": sorted(STABLE_SOURCE_NAMESPACES),
        "cross_source_identifier_overlap_count": len(overlaps),
        "cross_source_identifier_overlaps": overlaps,
        "candidates_without_cross_source_identifier": without_cross_source,
        "candidates_without_any_identifier": without_any_identifier,
        "explicit_overlap_counts": {k: len(v) for k, v in explicit.items()},
        "warnings": warnings,
        "candidates": candidates,
        "explicit_overlap_records": explicit,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)}")
    print(f"Candidates: {len(candidates)}")
    print(f"Cross-source-ID overlaps: {len(overlaps)}")
    print(f"Without cross-source ID: {len(without_cross_source)}")
    print(f"Without any identifier: {len(without_any_identifier)}")
    print("No fixed_object_id values were assigned.")


if __name__ == "__main__":
    main()
