#!/usr/bin/env python3
"""Render source-driven observer views for Star Almanack.

This script produces three reproducible views from the same upstream stellar
catalog used by Star Almanack:

* finder     — wide field for locating the target
* binoculars — 10x50-class view
* telescope  — 6-inch-class low-power eyepiece view

The renderings are catalog-derived diagrams, not astrophotographs. The
Almanack can explain that convention once in its legend/front matter and
caption individual figures simply as, for example:

    Eyepiece view · 6-inch telescope · 50× · 1.2° field

The target center is read from fixed-objects.yaml. Star positions and
magnitudes are read directly from an HYG v4.1 CSV, the primary upstream
stellar catalog already used by Star Almanack's catalog builders. No network
access is used by this renderer.

Required HYG v4.1 columns:

    id, ra, dec, mag

The standard HYG fields proper, bayer, and con are used for labels when
present. Finder labels use Greek Bayer symbols plus proper names when a proper
name exists, without repeating the constellation abbreviation. The renderer
deliberately consumes the full HYG input rather than only the curated
Bayer/bright/special subsets, because realistic finder, binocular, and
eyepiece fields require the fainter background stars that are not part of
those editorial subsets.

Examples:

    python render_observer_views.py M35 hyg_v41.csv --view finder
    python render_observer_views.py M35 hyg_v41.csv --view binoculars
    python render_observer_views.py M35 hyg_v41.csv --view telescope
    python render_observer_views.py M35 hyg_v41.csv --view all --out-dir views

SVG is the default output because it is text, scales cleanly in Jekyll, and
keeps generated binary files out of the source repository. PNG may be
requested explicitly with --format png.
"""

from __future__ import annotations

import argparse
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt


@dataclass(frozen=True)
class ViewPreset:
    key: str
    title: str
    field_deg: float
    limiting_mag: float
    aperture: str | None = None
    magnification: str | None = None

    @property
    def caption(self) -> str:
        if self.key == "finder":
            return f"Finder chart · {self.field_deg:g}° field"
        if self.key == "binoculars":
            return (
                f"Binocular view · {self.aperture} · {self.magnification} · "
                f"{self.field_deg:g}° field"
            )
        return (
            f"Eyepiece view · {self.aperture} · {self.magnification} · "
            f"{self.field_deg:g}° field"
        )


PRESETS = {
    "finder": ViewPreset(
        key="finder",
        title="Finder chart",
        field_deg=30.0,
        limiting_mag=7.0,
    ),
    "binoculars": ViewPreset(
        key="binoculars",
        title="Binocular view",
        field_deg=6.5,
        limiting_mag=9.5,
        aperture="10×50 binoculars",
        magnification="10×",
    ),
    "telescope": ViewPreset(
        key="telescope",
        title="Eyepiece view",
        field_deg=1.2,
        limiting_mag=12.5,
        aperture="6-inch telescope",
        magnification="50×",
    ),
}


GREEK_BAYER = {
    "Alp": "α",
    "Bet": "β",
    "Gam": "γ",
    "Del": "δ",
    "Eps": "ε",
    "Zet": "ζ",
    "Eta": "η",
    "The": "θ",
    "Iot": "ι",
    "Kap": "κ",
    "Lam": "λ",
    "Mu": "μ",
    "Nu": "ν",
    "Xi": "ξ",
    "Omi": "ο",
    "Pi": "π",
    "Rho": "ρ",
    "Sig": "σ",
    "Tau": "τ",
    "Ups": "υ",
    "Phi": "φ",
    "Chi": "χ",
    "Psi": "ψ",
    "Ome": "ω",
}


@dataclass
class Star:
    ra_deg: float
    dec_deg: float
    mag: float
    label: str = ""
    hyg_id: str = ""


@dataclass(frozen=True)
class Target:
    designation: str
    ra_deg: float
    dec_deg: float
    name: str | None
    ngc_or_ic: str | None


def _split_yaml_row(text: str) -> list[str]:
    """Split the simple bracket-row format used by fixed-objects.yaml."""
    row = next(csv.reader([text], skipinitialspace=True))
    return [item.strip().strip("'\"") for item in row]


def load_target(path: Path, designation: str) -> Target:
    wanted = designation.upper()
    pattern = re.compile(r"^\s*-\s*\[(.*)\]\s*$")

    for line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(line)
        if not match:
            continue
        fields = _split_yaml_row(match.group(1))
        if not fields or fields[0].upper() != wanted:
            continue

        # Messier schema:
        # id, ngc, name, type, con, ra_h, dec_deg, mag, size_arcmin, best, iso
        if len(fields) < 8:
            raise ValueError(f"Malformed fixed-object row for {designation}")

        ngc = fields[1] if fields[1].lower() not in {"", "null", "none"} else None
        if ngc and ngc.isdigit():
            ngc = f"NGC {ngc}"
        name = fields[2] if fields[2].lower() not in {"", "null", "none"} else None
        ra_deg = float(fields[5]) * 15.0
        dec_deg = float(fields[6])
        return Target(wanted, ra_deg, dec_deg, name, ngc)

    raise KeyError(f"Target {designation!r} not found in {path}")


def greek_bayer_symbol(bayer: str) -> str:
    """Convert HYG's Bayer abbreviation to a Greek glyph when possible."""
    if not bayer:
        return ""
    prefix = bayer[:3].title()
    symbol = GREEK_BAYER.get(prefix)
    if not symbol:
        return bayer
    suffix = bayer[3:]
    return f"{symbol}{suffix}"


def hyg_label(row: dict[str, str]) -> str:
    """Finder label: Greek Bayer symbol plus proper name; no constellation tag."""
    proper = (row.get("proper") or "").strip()
    bayer = (row.get("bayer") or "").strip()
    greek = greek_bayer_symbol(bayer)

    if greek and proper:
        return f"{greek} {proper}"
    if proper:
        return proper
    if greek:
        return greek
    return ""


def load_hyg_stars(path: Path) -> list[Star]:
    """Load the full upstream HYG v4.1 catalog used by Star Almanack builders."""
    stars: list[Star] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"id", "ra", "dec", "mag"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                "HYG v4.1 catalog is missing required columns: "
                + ", ".join(sorted(missing))
            )

        for row in reader:
            ra_text = (row.get("ra") or "").strip()
            dec_text = (row.get("dec") or "").strip()
            mag_text = (row.get("mag") or "").strip()
            if not ra_text or not dec_text or not mag_text:
                continue

            stars.append(
                Star(
                    ra_deg=float(ra_text) * 15.0,
                    dec_deg=float(dec_text),
                    mag=float(mag_text),
                    label=hyg_label(row),
                    hyg_id=(row.get("id") or "").strip(),
                )
            )
    return stars


def tangent_plane(
    ra_deg: float,
    dec_deg: float,
    center_ra_deg: float,
    center_dec_deg: float,
) -> tuple[float, float] | None:
    """Gnomonic projection, returned in angular-degree-like tangent units."""
    ra = math.radians(ra_deg)
    dec = math.radians(dec_deg)
    ra0 = math.radians(center_ra_deg)
    dec0 = math.radians(center_dec_deg)

    dra = (ra - ra0 + math.pi) % (2.0 * math.pi) - math.pi
    cosc = math.sin(dec0) * math.sin(dec) + math.cos(dec0) * math.cos(dec) * math.cos(dra)
    if cosc <= 0:
        return None

    x = math.cos(dec) * math.sin(dra) / cosc
    y = (
        math.cos(dec0) * math.sin(dec)
        - math.sin(dec0) * math.cos(dec) * math.cos(dra)
    ) / cosc
    return math.degrees(math.atan(x)), math.degrees(math.atan(y))


def angular_separation_deg(
    ra1_deg: float, dec1_deg: float, ra2_deg: float, dec2_deg: float
) -> float:
    ra1, dec1, ra2, dec2 = map(
        math.radians, (ra1_deg, dec1_deg, ra2_deg, dec2_deg)
    )
    value = (
        math.sin(dec1) * math.sin(dec2)
        + math.cos(dec1) * math.cos(dec2) * math.cos(ra1 - ra2)
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, value))))


def view_center(
    target: Target, stars: Iterable[Star], preset: ViewPreset
) -> tuple[float, float]:
    """Return plot center; M35 finder includes Castor and Pollux."""
    if preset.key == "finder" and target.designation == "M35":
        anchors = [
            star
            for star in stars
            if star.label.endswith(" Castor") or star.label.endswith(" Pollux")
        ]
        if len(anchors) == 2:
            # Average unit vectors so RA wrap is handled correctly.
            vectors = []
            for ra_deg, dec_deg in [(target.ra_deg, target.dec_deg)] + [
                (star.ra_deg, star.dec_deg) for star in anchors
            ]:
                ra = math.radians(ra_deg)
                dec = math.radians(dec_deg)
                vectors.append((
                    math.cos(dec) * math.cos(ra),
                    math.cos(dec) * math.sin(ra),
                    math.sin(dec),
                ))
            x = sum(v[0] for v in vectors)
            y = sum(v[1] for v in vectors)
            z = sum(v[2] for v in vectors)
            center_ra = math.degrees(math.atan2(y, x)) % 360.0
            center_dec = math.degrees(math.atan2(z, math.hypot(x, y)))
            return center_ra, center_dec
    return target.ra_deg, target.dec_deg


def visible_stars(
    stars: Iterable[Star], center: tuple[float, float], preset: ViewPreset
) -> list[Star]:
    radius = preset.field_deg / 2.0
    center_ra, center_dec = center
    return [
        star
        for star in stars
        if star.mag <= preset.limiting_mag
        and angular_separation_deg(
            star.ra_deg, star.dec_deg, center_ra, center_dec
        )
        <= radius * 1.05
    ]


def marker_area(mag: float, limiting_mag: float) -> float:
    """Map stellar magnitude to a restrained plotted disk area."""
    return max(2.0, 5.0 + 5.0 * (limiting_mag - mag))


def render_view(
    target: Target,
    stars: list[Star],
    preset: ViewPreset,
    output: Path,
    dpi: int,
) -> None:
    center_ra, center_dec = view_center(target, stars, preset)
    selected = visible_stars(stars, (center_ra, center_dec), preset)
    projected: list[tuple[float, float, Star]] = []
    for star in selected:
        xy = tangent_plane(star.ra_deg, star.dec_deg, center_ra, center_dec)
        if xy is not None:
            projected.append((xy[0], xy[1], star))

    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    radius = preset.field_deg / 2.0

    # Astronomical charts conventionally put east to the left.
    ax.set_xlim(radius, -radius)
    ax.set_ylim(-radius, radius)
    ax.set_aspect("equal", adjustable="box")

    if projected:
        xs = [p[0] for p in projected]
        ys = [p[1] for p in projected]
        sizes = [marker_area(p[2].mag, preset.limiting_mag) for p in projected]
        ax.scatter(xs, ys, s=sizes)

    if preset.key == "finder":
        for x, y, star in projected:
            if star.label and star.mag <= 5.0:
                ax.annotate(
                    star.label,
                    (x, y),
                    xytext=(4, 4),
                    textcoords="offset points",
                    fontsize=7,
                )

    target_xy = tangent_plane(
        target.ra_deg, target.dec_deg, center_ra, center_dec
    )
    if preset.key == "finder" and target_xy is not None:
        tx, ty = target_xy
        target_circle = plt.Circle((tx, ty), 0.45, fill=False, linewidth=1.0)
        ax.add_patch(target_circle)
        ax.annotate(
            target.designation,
            (tx, ty),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=8,
        )

    target_label = target.designation
    if target.name:
        target_label += f" · {target.name}"
    elif target.ngc_or_ic:
        target_label += f" · {target.ngc_or_ic}"

    ax.set_title(f"{target_label}\n{preset.caption}")
    ax.set_xlabel("East ←   angular offset   → West")
    ax.set_ylabel("South   angular offset   North")
    ax.grid(False)

    if preset.key in {"binoculars", "telescope"}:
        circle = plt.Circle((0, 0), radius, fill=False)
        ax.add_patch(circle)

    fig.tight_layout()
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=dpi, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", help="Fixed-object designation, for example M35")
    parser.add_argument(
        "hyg_catalog",
        type=Path,
        help="full HYG v4.1 CSV used as Star Almanack's upstream stellar catalog",
    )
    parser.add_argument(
        "--fixed-objects",
        type=Path,
        default=Path("fixed-objects.yaml"),
        help="authoritative fixed-object source (default: fixed-objects.yaml)",
    )
    parser.add_argument(
        "--view",
        choices=["finder", "binoculars", "telescope", "all"],
        default="all",
        help="view to render (default: all)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("observer-views"),
        help="output directory (default: observer-views)",
    )
    parser.add_argument(
        "--format",
        choices=["svg", "png"],
        default="svg",
        help="output format (default: svg)",
    )
    parser.add_argument("--dpi", type=int, default=180, help="PNG/SVG save DPI metadata")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target = load_target(args.fixed_objects, args.target)
    stars = load_hyg_stars(args.hyg_catalog)

    keys = list(PRESETS) if args.view == "all" else [args.view]
    for key in keys:
        preset = PRESETS[key]
        filename = f"{target.designation}-{key}.{args.format}"
        output = args.out_dir / filename
        render_view(target, stars, preset, output, args.dpi)
        print(f"wrote {output} — {preset.caption}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
