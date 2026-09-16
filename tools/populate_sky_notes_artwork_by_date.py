#!/usr/bin/env python3
"""Create/recreate Sky Note artwork from Sky Note artwork descriptors.

This generator owns only Sky Note artwork and artwork embeds. It consumes the
structured descriptor emitted by populate_sky_notes_by_date.py. Model work is
reference material only; no ISO week is special here.

Production rule: never invent constellation geometry. A descriptor that asks
for stellar artwork may be rendered only from an accepted Martz/MacRobert
geometry registry and Star Almanack asterism definitions.
"""
from __future__ import annotations

import json
from pathlib import Path

from finder_geometry_adapter import asterism_spec, constellation_paths
from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT
DESCRIPTOR_ROOT = SOURCE_ROOT / "generated-sky-notes"
GEOMETRY_REGISTRY = SOURCE_ROOT / "finder-geometry" / "martz-macrobert.json"
RENDER_SPECS_ROOT = SOURCE_ROOT / "sky-notes-artwork" / "specs"


def load_descriptor(year: int, week: int) -> dict | None:
    source = DESCRIPTOR_ROOT / str(year) / f"W{week:02d}.json"
    if not source.exists():
        raise RuntimeError(
            f"Missing generated Sky Note source {source.relative_to(ROOT)}. "
            "Run Populate Sky Notes first so this workflow can consume its artwork descriptor."
        )
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
    if geometry.get("invent_geometry") is not False:
        raise RuntimeError(f"{expected_week}: descriptor must forbid invented geometry")
    if geometry.get("on_missing_geometry") != "fail":
        raise RuntimeError(f"{expected_week}: missing accepted geometry must be fatal")

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
        raise RuntimeError(
            "Artwork descriptor found, but the accepted Martz/MacRobert geometry registry "
            f"is not yet present at {GEOMETRY_REGISTRY.relative_to(ROOT)}. "
            "Refusing to invent constellation lines."
        )

    registry = json.loads(GEOMETRY_REGISTRY.read_text(encoding="utf-8"))
    abbreviation = descriptor["geometry"].get("constellation_abbreviation")
    figures = registry.get("constellations") or {}
    if abbreviation not in figures:
        raise RuntimeError(
            f"Accepted Martz/MacRobert geometry is undefined for {abbreviation!r}; "
            "refusing to invent a constellation figure."
        )

    asterism = descriptor.get("asterism")
    if asterism:
        asterisms = registry.get("asterisms") or {}
        asterism_id = asterism.get("id")
        if asterism_id not in asterisms:
            raise RuntimeError(
                f"Accepted Star Almanack asterism {asterism_id!r} is undefined; "
                "refusing to invent it."
            )
        accepted = asterisms[asterism_id]
        if accepted.get("geometry_status") != "accepted-paths" or not accepted.get("paths"):
            raise RuntimeError(
                f"Star Almanack asterism {asterism_id!r} has members but no accepted "
                "drawable paths; refusing to infer connections."
            )
    return registry


def build_renderer_spec(descriptor: dict, registry: dict) -> dict:
    """Translate a validated artwork descriptor into legacy renderer geometry."""
    abbreviation = descriptor["geometry"]["constellation_abbreviation"]
    targets = descriptor.get("targets") or []
    if not targets:
        raise RuntimeError(f"{descriptor['week']}: stellar finder has no target")
    target = targets[0]
    if target.get("type") != "star" or not target.get("name"):
        raise RuntimeError(
            f"{descriptor['week']}: generic renderer currently requires a named star target"
        )

    spec = {
        "name": descriptor.get("constellation") or abbreviation,
        "target": target["name"],
        "figure_paths": constellation_paths(registry, abbreviation),
        "asterisms": [],
        "deep_sky_objects": [],
    }
    requested = descriptor.get("asterism")
    if requested:
        spec["asterisms"].append(
            asterism_spec(registry, requested["id"], requested.get("name", ""))
        )
    return spec


def write_renderer_spec(year: int, week: int, spec: dict) -> Path:
    out_dir = RENDER_SPECS_ROOT / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"W{week:02d}.json"
    text = json.dumps(spec, indent=2, ensure_ascii=False) + "\n"
    if not out.exists() or out.read_text(encoding="utf-8") != text:
        out.write_text(text, encoding="utf-8")
    return out


def generate_week(year: int, week: int) -> bool:
    key = f"{year}-W{week:02d}"
    descriptor = load_descriptor(year, week)
    if descriptor is None:
        print(f"ISO {key}: Sky Note has no artwork descriptor; no artwork needed")
        return False

    validate_descriptor(descriptor, year, week)
    registry = accepted_geometry(descriptor)
    spec = build_renderer_spec(descriptor, registry)
    out = write_renderer_spec(year, week, spec)
    print(f"ISO {key}: accepted finder geometry prepared at {out.relative_to(ROOT)}")
    return True


def main() -> None:
    start, end, weeks = parse_range_args(
        "Populate Star Almanack Sky Notes artwork by inclusive ISO date range"
    )
    generated = 0
    for item in weeks:
        generated += int(generate_week(item.year, item.week))
    print(
        f"Sky Notes artwork complete for {start.isoformat()} through {end.isoformat()}: "
        f"{generated} ISO weeks prepared for rendering"
    )


if __name__ == "__main__":
    main()
