#!/usr/bin/env python3
"""Regression checks for the Sky Notes finder display contract."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERER = ROOT / "tools" / "render_sky_note_finder.py"
GENERATOR = ROOT / "tools" / "populate_fixed_object_artwork_by_date.py"


def require(source: str, fragment: str, message: str) -> None:
    if fragment not in source:
        raise SystemExit(message)


def main() -> None:
    renderer = RENDERER.read_text(encoding="utf-8")
    generator = GENERATOR.read_text(encoding="utf-8")
    ast.parse(renderer)
    ast.parse(generator)

    require(generator, '"constellation_abbreviation": con',
            "generator must retain the home IAU abbreviation")
    require(generator, '"name": full_name',
            "generator must use the canonical full constellation name")
    require(generator, '"candidate_constellations": all_constellation_specs(registry)',
            "generator must supply accepted neighboring constellation geometry")
    require(generator, '"candidate_asterisms": all_asterism_specs(registry)',
            "generator must supply accepted asterism geometry")

    require(renderer, "return greek_bayer_symbol(stored)",
            "stored Bayer abbreviations must be normalized to Greek")
    require(renderer, "(target_greek, target_const, target_name)",
            "stellar target labels must include Greek, IAU abbreviation, and proper name")
    require(renderer, 'f"{target_name} in {figure_constellation}"',
            "finder title must use target name and full constellation name")
    require(renderer, '"\\n".join(legend)',
            "legend entries must be line separated")
    require(renderer, "load_iau_boundaries()",
            "renderer must use repository-owned IAU boundaries")
    require(renderer, 'linestyle="--"',
            "IAU boundaries must be dashed")
    require(renderer, "place_label(ax, label, point, occupied_labels",
            "Greek labels must use collision-aware placement")
    require(renderer, "place_label(ax, figure_constellation, constellation_point, occupied_labels",
            "constellation labels must share collision-aware placement")

    # Guard against the two observed failure modes without special-casing either
    # object in production code.
    for forbidden in ("Altair", "Vulpecula"):
        if forbidden in renderer:
            raise SystemExit(f"renderer contains object-specific special case: {forbidden}")

    print("Sky Notes finder contract verified")


if __name__ == "__main__":
    main()
