#!/usr/bin/env python3
"""Star Almanack planetary calculation layer.

This module computes Almanack positions from locally cached JPL/NAIF SPK source
kernels. It does not query Horizons or any other service for finished answers.

Source data:
- JPL DE440s planetary SPK for Sun, Moon, and planets.
- JPL/NAIF Ceres 1900-2100 SPK for Ceres.

The kernels are inputs, not published ephemeris answers. NAIF permits kernels on
its server to be downloaded and used subject to its published SPICE rules; do
not describe them as "public domain" without a source that actually says so.

Calculation dependency:
- Skyfield (MIT licensed), used as an imported library to read SPK data and
  perform apparent-position and reference-frame calculations.
- Skyfield's planetary_magnitude() is used only for bodies it supports. Its
  documentation attributes those magnitude formulae to Mallama & Hilton (2018).
  Star Almanack does not copy those formulae into this module.

Kernel acquisition/caching belongs to the workflow/runtime environment. The
normal GitHub Actions path stores the kernels under .cache/skyfield and reuses
them through actions/cache. See Star-Almanack-Repo/EPHEMERIS-PROVENANCE.md.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from skyfield.api import load, load_file
from skyfield.framelib import ecliptic_frame
from skyfield.magnitudelib import planetary_magnitude

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KERNEL_DIR = ROOT / ".cache" / "skyfield"
DE440S_NAME = "de440s.bsp"
CERES_NAME = "ceres_1900_2100.bsp"


@dataclass(frozen=True)
class EphemerisSample:
    longitude_deg: float
    latitude_deg: float
    magnitude: float | None
    elongation_deg: float


def _norm3(v) -> float:
    return math.sqrt(float(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))


class StarAlmanackEphemeris:
    """Compute geocentric apparent ecliptic positions from cached SPK inputs."""

    def __init__(self, kernel_dir: str | Path | None = None) -> None:
        configured = kernel_dir or os.environ.get("STAR_ALMANACK_EPHEMERIS_DIR")
        self.kernel_dir = Path(configured) if configured else DEFAULT_KERNEL_DIR
        self.de440s_path = self.kernel_dir / DE440S_NAME
        self.ceres_path = self.kernel_dir / CERES_NAME
        if not self.de440s_path.is_file():
            raise FileNotFoundError(
                f"Missing {self.de440s_path}. The workflow must restore/download the JPL/NAIF DE440s source kernel first."
            )
        if not self.ceres_path.is_file():
            raise FileNotFoundError(
                f"Missing {self.ceres_path}. The workflow must restore/download the JPL/NAIF Ceres source kernel first."
            )

        self.ts = load.timescale(builtin=True)
        self.planets = load_file(str(self.de440s_path))
        self.asteroids = load_file(str(self.ceres_path))
        self.earth = self.planets["earth"]
        self.sun = self.planets["sun"]

        # NAIF's Ceres kernel segment is Sun-centered. Skyfield vector
        # composition supplies the barycentric vector needed by observe().
        ceres_relative = self.asteroids[10, 2000001]
        self.ceres = self.sun + ceres_relative

        self.bodies = {
            "sun": self.sun,
            "moon": self.planets["moon"],
            "mercury": self.planets["mercury"],
            "venus": self.planets["venus"],
            "mars": self.planets["mars barycenter"],
            "jupiter": self.planets["jupiter barycenter"],
            "saturn": self.planets["saturn barycenter"],
            "ceres": self.ceres,
            "uranus": self.planets["uranus barycenter"],
            "neptune": self.planets["neptune barycenter"],
            "pluto": self.planets["pluto barycenter"],
        }

    @staticmethod
    def _angle_between(a, b) -> float:
        av = a.position.au
        bv = b.position.au
        dot = float(av[0] * bv[0] + av[1] * bv[1] + av[2] * bv[2])
        an = _norm3(av)
        bn = _norm3(bv)
        cosine = max(-1.0, min(1.0, dot / (an * bn)))
        return math.degrees(math.acos(cosine))

    @staticmethod
    def _supported_planet_magnitude(apparent) -> float | None:
        """Use Skyfield's attributed planet model; fail closed if unsupported."""
        try:
            magnitude = float(planetary_magnitude(apparent))
        except Exception:
            return None
        return magnitude if math.isfinite(magnitude) else None

    def sample(self, key: str, day: date) -> EphemerisSample:
        """Return a Monday-00:00-UTC publication snapshot for one body."""
        t = self.ts.utc(day.year, day.month, day.day, 0, 0, 0)
        body = self.bodies[key]
        apparent = self.earth.at(t).observe(body).apparent()
        lat, lon, _ = apparent.frame_latlon(ecliptic_frame)

        sun_apparent = self.earth.at(t).observe(self.sun).apparent()
        elongation = 0.0 if key == "sun" else self._angle_between(apparent, sun_apparent)
        magnitude = self._supported_planet_magnitude(apparent)

        return EphemerisSample(
            longitude_deg=float(lon.degrees) % 360.0,
            latitude_deg=float(lat.degrees),
            magnitude=magnitude,
            elongation_deg=elongation,
        )
