#!/usr/bin/env python3
"""Star Almanack planetary calculation layer.

This module computes Almanack positions from locally cached public-domain JPL
SPK source data. It does not query Horizons or any other answer service.

Production source data:
- JPL DE440s planetary SPK for Sun, Moon, and planets.
- JPL/NAIF Ceres 1900-2100 SPK for Ceres.

Kernel acquisition and caching belongs to the workflow/runtime environment.
The normal GitHub Actions path stores both kernels under .cache/skyfield and
reuses them through actions/cache.
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
    """Compute weekly geocentric apparent ecliptic positions from cached SPKs."""

    def __init__(self, kernel_dir: str | Path | None = None) -> None:
        configured = kernel_dir or os.environ.get("STAR_ALMANACK_EPHEMERIS_DIR")
        self.kernel_dir = Path(configured) if configured else DEFAULT_KERNEL_DIR
        self.de440s_path = self.kernel_dir / DE440S_NAME
        self.ceres_path = self.kernel_dir / CERES_NAME
        if not self.de440s_path.is_file():
            raise FileNotFoundError(
                f"Missing {self.de440s_path}. The workflow must restore/download the public-domain DE440s source kernel first."
            )
        if not self.ceres_path.is_file():
            raise FileNotFoundError(
                f"Missing {self.ceres_path}. The workflow must restore/download the public-domain Ceres source kernel first."
            )

        self.ts = load.timescale(builtin=True)
        self.planets = load_file(str(self.de440s_path))
        self.asteroids = load_file(str(self.ceres_path))
        self.earth = self.planets["earth"]
        self.sun = self.planets["sun"]

        # NAIF's Ceres kernel segment is Sun-centered. Vector composition turns
        # it into the barycentric vector needed by Skyfield's observe() chain.
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

    def _heliocentric_distance_au(self, body, t) -> float:
        body_bary = body.at(t).position.au
        sun_bary = self.sun.at(t).position.au
        return _norm3(body_bary - sun_bary)

    def _ceres_magnitude(self, t, apparent) -> float:
        """Compute Ceres visual magnitude from H-G constants and geometry."""
        # Public catalog constants commonly adopted for (1) Ceres.
        h, g = 3.34, 0.12
        r = self._heliocentric_distance_au(self.ceres, t)
        delta = float(apparent.distance().au)
        earth_sun = float(self.earth.at(t).observe(self.sun).distance().au)

        # Phase angle at Ceres from the Sun-Ceres-Earth triangle.
        cosine = (r * r + delta * delta - earth_sun * earth_sun) / (2.0 * r * delta)
        phase = math.acos(max(-1.0, min(1.0, cosine)))
        tan_half = max(0.0, math.tan(phase / 2.0))
        phi1 = math.exp(-3.33 * tan_half ** 0.63)
        phi2 = math.exp(-1.87 * tan_half ** 1.22)
        phase_term = max(1e-12, (1.0 - g) * phi1 + g * phi2)
        return h + 5.0 * math.log10(r * delta) - 2.5 * math.log10(phase_term)

    def _fallback_magnitude(self, key: str, t, apparent) -> float | None:
        if key == "sun":
            return -26.74
        if key == "moon":
            return -12.0
        if key == "ceres":
            return self._ceres_magnitude(t, apparent)
        if key == "pluto":
            # Pluto is always far below the Almanack binocular threshold. This
            # is an internally computed distance scaling, not a published table.
            r = self._heliocentric_distance_au(self.bodies["pluto"], t)
            delta = float(apparent.distance().au)
            return -0.7 + 5.0 * math.log10(r * delta)
        return None

    def sample(self, key: str, day: date) -> EphemerisSample:
        """Return a Monday-00:00-UTC publication snapshot for one body."""
        t = self.ts.utc(day.year, day.month, day.day, 0, 0, 0)
        body = self.bodies[key]
        apparent = self.earth.at(t).observe(body).apparent()
        lat, lon, _ = apparent.frame_latlon(ecliptic_frame)

        sun_apparent = self.earth.at(t).observe(self.sun).apparent()
        elongation = 0.0 if key == "sun" else self._angle_between(apparent, sun_apparent)

        try:
            magnitude = float(planetary_magnitude(apparent))
        except Exception:
            magnitude = self._fallback_magnitude(key, t, apparent)

        return EphemerisSample(
            longitude_deg=float(lon.degrees) % 360.0,
            latitude_deg=float(lat.degrees),
            magnitude=magnitude,
            elongation_deg=elongation,
        )
