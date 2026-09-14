#!/usr/bin/env python3
"""Star Almanack planetary calculation layer.

This module computes Almanack positions from locally cached public-domain JPL
SPK source data.  It does not query Horizons or any other answer service.

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

        # The NAIF Ceres kernel is centered on the Sun.  Skyfield vector
        # functions compose, producing a Solar-System-barycentric Ceres vector.
        try:
            ceres_relative = self.asteroids[10, 2000001]
        except Exception:
            # Some SPK readers expose the segment by numeric target alone.
            ceres_relative = self.asteroids[2000001]
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
        an = math.sqrt(float(av[0] ** 2 + av[1] ** 2 + av[2] ** 2))
        bn = math.sqrt(float(bv[0] ** 2 + bv[1] ** 2 + bv[2] ** 2))
        cosine = max(-1.0, min(1.0, dot / (an * bn)))
        return math.degrees(math.acos(cosine))

    def _ceres_magnitude(self, t, apparent) -> float:
        """IAU H-G visual magnitude from independently computed geometry."""
        # Public catalog constants commonly adopted for (1) Ceres.
        h, g = 3.34, 0.12
        sun_to_ceres = (self.ceres - self.sun).at(t)
        earth_to_ceres = apparent
        ceres_to_sun = (self.sun - self.ceres).at(t)
        ceres_to_earth = (self.earth - self.ceres).at(t)
        r = float(sun_to_ceres.distance().au)
        delta = float(earth_to_ceres.distance().au)
        phase = math.radians(self._angle_between(ceres_to_sun, ceres_to_earth))
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
            # Pluto remains far below the Almanack's binocular threshold; use
            # absolute-magnitude distance scaling rather than an answer table.
            r = float((self.bodies["pluto"] - self.sun).at(t).distance().au)
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
