#!/usr/bin/env python3
"""Create/recreate Sky Note artwork from Sky Note artwork descriptors."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

from finder_geometry_adapter import asterism_spec, constellation_paths
from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]
DESCRIPTOR_ROOT = ROOT / "generated-sky-notes"
GEOMETRY_REGISTRY = ROOT / "finder-geometry" / "martz-macrobert.json"
FIXED_OBJECT_REGISTRY = ROOT / "database" / "fixed-object-registry.json"
FIXED_OBJECT_DATABASE = ROOT / "database" / "fixed-objects.json"
BAYER_CATALOG = ROOT / "expanded-bayer-stars.csv"
RENDER_SPECS_ROOT = ROOT / "sky-notes-artwork" / "specs"


def load_descriptor(year: int, week: int) -> dict | None:
    source = DESCRIPTOR_ROOT / str(year) / f"W{week:02d}.json"
    if not source.exists():
        raise RuntimeError(f"Missing generated Sky Note source {source.relative_to(ROOT)}. Run Populate Sky Notes first.")
    payload = json.loads(source.read_text(encoding="utf-8"))
    descriptor = payload.get("artwork")
    if descriptor is None:
        return None
    if not isinstance(descriptor, dict):
        raise RuntimeError(f"Invalid artwork descriptor in {source.relative_to(ROOT)}")
    return descriptor


def validate_descriptor(descriptor: dict, year: int, week: int) -> None:
    expected_week = f"{year}-W{week:02d}"
    if descriptor.get("schema_version") != 1:
        raise RuntimeError(f"{expected_week}: unsupported artwork descriptor schema")
    if descriptor.get("week") != expected_week:
        raise RuntimeError(f"{expected_week}: descriptor week is {descriptor.get('week')!r}")
    if descriptor.get("kind") != "stellar-finder":
        raise RuntimeError(f"{expected_week}: unsupported artwork kind {descriptor.get('kind')!r}")
    geometry = descriptor.get("geometry") or {}
    if geometry.get("constellation_system") != "Martz/MacRobert":
        raise RuntimeError(f"{expected_week}: stellar artwork must use Martz/MacRobert geometry")
    if geometry.get("invent_geometry") is not False or geometry.get("on_missing_geometry") != "fail":
        raise RuntimeError(f"{expected_week}: descriptor must forbid invented geometry")
    style = descriptor.get("style") or {}
    if (style.get("constellation") or {}).get("stroke") != "#5c8fe8":
        raise RuntimeError(f"{expected_week}: constellation figure must use approved blue #5c8fe8")
    if (style.get("asterism") or {}).get("stroke") != "#59c86d":
        raise RuntimeError(f"{expected_week}: asterism must use approved green #59c86d")
    if (style.get("target") or {}).get("stroke") != "#ffd84d":
        raise RuntimeError(f"{expected_week}: targets must use approved yellow #ffd84d")
    if style.get("target_arrows") is not False:
        raise RuntimeError(f"{expected_week}: approved finder style does not use target arrows")


def accepted_geometry(descriptor: dict) -> dict:
    if not GEOMETRY_REGISTRY.exists():
        raise RuntimeError(f"Accepted Martz/MacRobert geometry registry is not present at {GEOMETRY_REGISTRY.relative_to(ROOT)}")
    registry = json.loads(GEOMETRY_REGISTRY.read_text(encoding="utf-8"))
    abbreviation = descriptor["geometry"].get("constellation_abbreviation")
    figures = registry.get("constellations") or {}
    if abbreviation not in figures:
        raise RuntimeError(f"Accepted Martz/MacRobert geometry is undefined for {abbreviation!r}")
    asterism = descriptor.get("asterism")
    if asterism:
        asterisms = registry.get("asterisms") or {}
        asterism_id = asterism.get("id")
        if asterism_id not in asterisms:
            raise RuntimeError(f"Accepted Star Almanack asterism {asterism_id!r} is undefined")
        accepted = asterisms[asterism_id]
        if accepted.get("geometry_status") != "accepted-paths" or not accepted.get("paths"):
            raise RuntimeError(f"Star Almanack asterism {asterism_id!r} has no accepted drawable paths")
    return registry


def fixed_object_id_by_hip() -> dict[str, int]:
    registry = json.loads(FIXED_OBJECT_REGISTRY.read_text(encoding="utf-8"))
    result = {}
    for obj in registry.get("fixed_objects") or []:
        if obj.get("status") != "active":
            continue
        for identifier in obj.get("identifiers") or []:
            if str(identifier.get("namespace", "")).lower() == "hip":
                result[str(identifier.get("value"))] = obj["fixed_object_id"]
    return result


def fixed_object_metadata() -> tuple[dict[int, dict], dict[str, list[int]]]:
    """Return immutable-ID metadata, enriched from the authoritative Bayer catalog."""
    payload = json.loads(FIXED_OBJECT_DATABASE.read_text(encoding="utf-8"))
    by_id: dict[int, dict] = {}
    by_name: dict[str, list[int]] = {}
    for obj in payload.get("fixed_objects") or []:
        fixed_id = obj["fixed_object_id"]
        meta = {"fixed_object_id": fixed_id}
        for record in obj.get("source_records") or []:
            facts = record.get("facts") or {}
            name = facts.get("name")
            constellation = facts.get("constellation")
            if name and not meta.get("proper_name"):
                meta["proper_name"] = name
            if constellation and not meta.get("constellation_abbreviation"):
                meta["constellation_abbreviation"] = constellation
            if record.get("source") == "fixed-objects.yaml:bayer":
                source_key = str(record.get("source_key", ""))
                parts = source_key.split()
                if parts:
                    meta["bayer"] = parts[0]
                if len(parts) > 1:
                    meta["constellation_abbreviation"] = parts[-1]
                if name:
                    meta["proper_name"] = name
        by_id[fixed_id] = meta
        if meta.get("proper_name"):
            by_name.setdefault(meta["proper_name"].casefold(), []).append(fixed_id)

    if not BAYER_CATALOG.exists():
        raise RuntimeError(f"Authoritative Bayer catalog is missing at {BAYER_CATALOG.relative_to(ROOT)}")
    registry = json.loads(FIXED_OBJECT_REGISTRY.read_text(encoding="utf-8"))
    registry_hip = {}
    for obj in registry.get("fixed_objects") or []:
        fid = obj.get("fixed_object_id")
        for identifier in obj.get("identifiers") or []:
            if str(identifier.get("namespace", "")).lower() == "hip":
                registry_hip[str(identifier.get("value"))] = fid
    with BAYER_CATALOG.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            hip = str(row.get("hip") or "").strip()
            fid = registry_hip.get(hip)
            if fid is None or fid not in by_id:
                continue
            bayer = str(row.get("bayer") or "").strip()
            constellation = str(row.get("con") or "").strip()
            proper = str(row.get("proper") or row.get("name") or "").strip()
            if bayer:
                by_id[fid]["bayer"] = bayer
            if constellation:
                by_id[fid]["constellation_abbreviation"] = constellation
            if proper:
                by_id[fid]["proper_name"] = proper
                by_name.setdefault(proper.casefold(), [])
                if fid not in by_name[proper.casefold()]:
                    by_name[proper.casefold()].append(fid)
    return by_id, by_name


def hip_number(ref: str) -> str | None:
    match = re.fullmatch(r"HIP\s+(\d+)", str(ref).strip(), flags=re.IGNORECASE)
    return match.group(1) if match else None


def catalog_target_refs(target_name: str) -> list[str]:
    """Resolve a named stellar target to authoritative HIP renderer refs.

    A finder target need not be a vertex of the accepted constellation or
    asterism line geometry.  Its point position comes from the authoritative
    Bayer catalog; this does not invent or alter figure geometry.
    """
    matches = []
    with BAYER_CATALOG.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            proper = str(row.get("proper") or row.get("name") or "").strip()
            hip = str(row.get("hip") or "").strip()
            if proper.casefold() == target_name.casefold() and hip:
                matches.append(f"HIP {hip}")
    return list(dict.fromkeys(matches))


def attach_fixed_object_ids(spec: dict) -> dict:
    by_hip = fixed_object_id_by_hip()
    metadata_by_id, ids_by_name = fixed_object_metadata()
    refs, seen = [], set()
    for path in spec.get("figure_paths") or []:
        for ref in path:
            if ref not in seen:
                seen.add(ref); refs.append(ref)
    for asterism in spec.get("asterisms") or []:
        for path in asterism.get("paths") or []:
            for ref in path:
                if ref not in seen:
                    seen.add(ref); refs.append(ref)

    target_name = str(spec.get("target") or "").strip()
    target_refs = catalog_target_refs(target_name) if target_name else []
    if len(target_refs) != 1:
        raise RuntimeError(f"Finder target {target_name!r} resolves to authoritative catalog refs {target_refs}; expected exactly one HIP renderer ref")
    target_ref = target_refs[0]
    if target_ref not in seen:
        seen.add(target_ref); refs.append(target_ref)

    identities, unresolved = [], []
    for ref in refs:
        hip = hip_number(ref)
        if not hip:
            continue
        fixed_id = by_hip.get(hip)
        if fixed_id is None:
            unresolved.append(ref); continue
        identity = {"fixed_object_id": fixed_id, "renderer_ref": ref, "identifiers": {"hip": hip}}
        identity.update({k: v for k, v in metadata_by_id.get(fixed_id, {}).items() if k != "fixed_object_id" and v})
        identities.append(identity)
    if unresolved:
        raise RuntimeError("Finder geometry/targets contain HIP stars with no Star Almanack fixed_object_id: " + ", ".join(unresolved))

    candidate_ids = ids_by_name.get(target_name.casefold(), []) if target_name else []
    if not candidate_ids:
        raise RuntimeError(f"Finder target {target_name!r} has no database fixed_object_id")
    identity_by_id = {identity["fixed_object_id"]: identity for identity in identities}
    target_hip = hip_number(target_ref)
    target_id = by_hip.get(target_hip) if target_hip else None
    if target_id is None or target_id not in candidate_ids:
        raise RuntimeError(f"Finder target {target_name!r} resolves to database IDs {candidate_ids}, but authoritative catalog ref {target_ref!r} resolves to immutable ID {target_id!r}")
    target_meta = metadata_by_id.get(target_id, {})
    target_identity = {"fixed_object_id": target_id}
    target_identity.update({k: v for k, v in target_meta.items() if k != "fixed_object_id" and v})
    target_identity["renderer_ref"] = identity_by_id[target_id]["renderer_ref"]
    target_identity["identifiers"] = identity_by_id[target_id]["identifiers"]
    spec["fixed_object_identities"] = identities
    spec["target_identity"] = target_identity
    return spec


def build_renderer_spec(descriptor: dict, registry: dict) -> dict:
    abbreviation = descriptor["geometry"]["constellation_abbreviation"]
    targets = descriptor.get("targets") or []
    if not targets:
        raise RuntimeError(f"{descriptor['week']}: stellar finder has no target")
    target = targets[0]
    if target.get("type") != "star" or not target.get("name"):
        raise RuntimeError(f"{descriptor['week']}: generic renderer requires a named star target")
    spec = {"name": descriptor.get("constellation") or abbreviation,
            "target": target["name"],
            "figure_paths": constellation_paths(registry, abbreviation),
            "asterisms": [], "deep_sky_objects": []}
    requested = descriptor.get("asterism")
    if requested:
        spec["asterisms"].append(asterism_spec(registry, requested["id"], requested.get("name", "")))
    return attach_fixed_object_ids(spec)


def write_renderer_spec(year: int, week: int, spec: dict) -> Path:
    out_dir = RENDER_SPECS_ROOT / str(year); out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"W{week:02d}.json"
    text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")
    return out


def generate_week(year: int, week: int) -> bool:
    key = f"{year}-W{week:02d}"
    descriptor = load_descriptor(year, week)
    if descriptor is None:
        print(f"ISO {key}: Sky Note has no artwork descriptor; no artwork needed"); return False
    validate_descriptor(descriptor, year, week)
    registry = accepted_geometry(descriptor)
    spec = build_renderer_spec(descriptor, registry)
    out = write_renderer_spec(year, week, spec)
    print(f"ISO {key}: accepted finder geometry prepared at {out.relative_to(ROOT)}")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Sky Notes artwork by inclusive ISO date range")
    generated = sum(int(generate_week(item.year, item.week)) for item in weeks)
    print(f"Sky Notes artwork complete for {start.isoformat()} through {end.isoformat()}: {generated} ISO weeks prepared for rendering")


if __name__ == "__main__":
    main()
