#!/usr/bin/env python3
"""Generate one canonical stellar-finder renderer spec per Calendar fixed object.

Artwork is owned by immutable fixed_object_id, not by the first target in a
week-level presentation descriptor.  A week can therefore request several
independent story finders without collapsing them onto one owner.
"""
from __future__ import annotations

import json
from pathlib import Path

from compute_constellation_observance_2026 import CONSTELLATIONS

from finder_geometry_adapter import all_asterism_specs, all_constellation_specs, constellation_paths
from iso_date_range import parse_range_args
import populate_sky_notes_artwork_by_date as legacy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "sky-notes-artwork" / "specs" / "objects"


def constellation_for(fixed_id: int, item: dict, metadata: dict[int, dict]) -> str:
    con = str(item.get("constellation") or metadata.get(fixed_id, {}).get("constellation_abbreviation") or "").strip()
    if not con:
        raise RuntimeError(f"fixed object {fixed_id} has no authoritative constellation")
    return con


def owner_identity(fixed_id: int, item: dict, by_hip: dict[str, int], metadata: dict[int, dict]) -> dict:
    owner = {"fixed_object_id": fixed_id, "name": item.get("name")}
    owner.update({k: v for k, v in metadata.get(fixed_id, {}).items() if k != "fixed_object_id" and v})
    if item.get("type") == "star":
        # Renderer identity comes from the immutable fixed-object registry, not
        # from a presentation name.  Proper names such as Sham need not be
        # aliases in the renderer catalog as long as this fixed_object_id owns
        # exactly one HIP identifier.
        owned_hips = [hip for hip, fid in by_hip.items() if fid == fixed_id]
        if len(owned_hips) != 1:
            raise RuntimeError(
                f"fixed object {fixed_id} {item.get('name')!r} owns HIP identifiers "
                f"{owned_hips}; expected exactly one"
            )
        owner["renderer_ref"] = f"HIP {owned_hips[0]}"
    return owner


def make_spec(item: dict, registry: dict, by_hip: dict[str, int], metadata: dict[int, dict]) -> dict:
    fixed_id = int(item["fixed_object_id"])
    con = constellation_for(fixed_id, item, metadata)
    figures = registry.get("constellations") or {}
    if con not in figures:
        raise RuntimeError(f"fixed object {fixed_id}: accepted Martz/MacRobert geometry is undefined for {con!r}")
    paths = constellation_paths(registry, con)
    refs = []
    seen = set()
    for path in paths:
        for ref in path:
            if ref not in seen:
                seen.add(ref)
                refs.append(ref)

    identities = []
    for ref in refs:
        hip = legacy.hip_number(ref)
        if not hip:
            continue
        fid = by_hip.get(hip)
        if fid is None:
            raise RuntimeError(f"fixed object {fixed_id}: geometry ref {ref} has no immutable fixed_object_id")
        identity = {"fixed_object_id": fid, "renderer_ref": ref, "identifiers": {"hip": hip}}
        identity.update({k: v for k, v in metadata.get(fid, {}).items() if k != "fixed_object_id" and v})
        identities.append(identity)

    owner = owner_identity(fixed_id, item, by_hip, metadata)
    if owner.get("renderer_ref") and owner["renderer_ref"] not in seen:
        identities.append(dict(owner, identifiers={"hip": legacy.hip_number(owner["renderer_ref"])}))

    full_name = dict((abbr, name) for name, abbr in CONSTELLATIONS).get(con, con)
    return {
        "name": full_name,
        "constellation_abbreviation": con,
        "figure_paths": paths,
        "candidate_constellations": all_constellation_specs(registry),
        "candidate_asterisms": all_asterism_specs(registry),
        "asterisms": [],
        "deep_sky_objects": [],
        "fixed_object_identities": identities,
        "artwork_owner_identity": owner,
        "guide_objects": [],
    }


def main() -> None:
    start, end, weeks = parse_range_args("Prepare one fixed-object Artwork spec for every Calendar Sky Note object")
    registry = json.loads(legacy.GEOMETRY_REGISTRY.read_text(encoding="utf-8"))
    by_hip = legacy.fixed_object_id_by_hip()
    metadata, _ = legacy.fixed_object_metadata()
    made = 0
    for week in weeks:
        payload = legacy.load_generated_source(week.year, week.week)
        items = list(payload.get("fixed_sky") or [])
        known = {int(item["fixed_object_id"]) for item in items if isinstance(item.get("fixed_object_id"), int)}
        for descriptor in payload.get("descriptors") or []:
            descriptor_id = str(descriptor.get("id", ""))
            if descriptor.get("type") not in {"star", "deep-sky-object"} or not descriptor_id.isdigit():
                continue
            fixed_id = int(descriptor_id)
            if fixed_id in known:
                continue
            known.add(fixed_id)
            items.append({
                "fixed_object_id": fixed_id,
                "name": descriptor.get("name"),
                "type": "deep-sky" if descriptor.get("type") == "deep-sky-object" else "star",
                "constellation": descriptor.get("constellation_abbreviation"),
            })
        for item in items:
            fixed_id = item.get("fixed_object_id")
            if not isinstance(fixed_id, int):
                raise RuntimeError(f"{week.year}-W{week.week:02d}: artwork item has no immutable ID")
            spec = make_spec(item, registry, by_hip, metadata)
            OUT.mkdir(parents=True, exist_ok=True)
            path = OUT / f"{fixed_id}.json"
            text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                path.write_text(text, encoding="utf-8")
            print(f"{week.year}-W{week.week:02d}: fixed object {fixed_id} -> {path.relative_to(ROOT)}")
            made += 1
    print(f"Prepared {made} fixed-object Artwork request(s) for {start} through {end}")


if __name__ == "__main__":
    main()
