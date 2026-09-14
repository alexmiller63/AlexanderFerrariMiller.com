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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from almanack_time import AstroInstant, datetime_to_jd_utc
from skyfield.api import load, load_file
from skyfield.framelib import ecliptic_frame
from skyfield.magnitudelib import planetary_magnitude
from skyfield.vectorlib import VectorFunction

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KERNEL_DIR = ROOT / ".cache" / "skyfield"
DE440S_NAME = "de440s.bsp"
CERES_NAME = "ceres_1900_2100.bsp"
SECONDS_PER_DAY = 86400.0


@dataclass(frozen=True)
class EphemerisSample:
    longitude_deg: float
    latitude_deg: float
    magnitude: float | None
    elongation_deg: float


def _norm3(v) -> float:
    return math.sqrt(float(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))


class _PiecewiseSpkPosition(VectorFunction):
    """Present several consecutive SPK segments as one Skyfield vector.

    The historical Ceres kernel is split into hundreds of Sun-to-Ceres
    segments.  They are source coefficients for different time intervals, not
    competing answers.  Skyfield exposes each interval as a separate vector,
    so this adapter selects the segment whose published coverage contains the
    requested TDB epoch and lets Skyfield evaluate that segment normally.
    """

    def __init__(self, segments) -> None:
        ordered = sorted(segments, key=lambda s: s.spk_segment.start_jd)
        if not ordered:
            raise ValueError("Piecewise SPK position requires at least one segment")
        center = ordered[0].center
        target = ordered[0].target
        if any(s.center != center or s.target != target for s in ordered):
            raise ValueError("Piecewise SPK segments must share one center/target pair")
        self.center = center
        self.target = target
        self.segments = ordered

    def _at(self, t):
        jd_tdb = float(t.tdb)
        for segment in self.segments:
            raw = segment.spk_segment
            if raw.start_jd <= jd_tdb <= raw.end_jd:
                return segment._at(t)
        first = self.segments[0].spk_segment.start_jd
        last = self.segments[-1].spk_segment.end_jd
        raise ValueError(
            f"TDB JD {jd_tdb:.9f} outside Ceres SPK coverage "
            f"{first:.9f}..{last:.9f}"
        )


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

        self.ts = load.timescale(builtin=True)
        self.planets = load_file(str(self.de440s_path))
        self.earth = self.planets["earth"]
        self.sun = self.planets["sun"]
        self.bodies = {
            "sun": self.sun,
            "moon": self.planets["moon"],
            "mercury": self.planets["mercury"],
            "venus": self.planets["venus"],
            "mars": self.planets["mars barycenter"],
            "jupiter": self.planets["jupiter barycenter"],
            "saturn": self.planets["saturn barycenter"],
            "uranus": self.planets["uranus barycenter"],
            "neptune": self.planets["neptune barycenter"],
            "pluto": self.planets["pluto barycenter"],
        }

        # Ceres is optional for calculations that need only the DE440s bodies,
        # such as calendar Sun/Moon sampling. Ephemeris generation requests it
        # explicitly and therefore fails closed if the Ceres source kernel is
        # absent.
        self.asteroids = None
        self.ceres = None
        if self.ceres_path.is_file():
            self.asteroids = load_file(str(self.ceres_path))
            # This historical NAIF kernel contains many consecutive Sun(10) ->
            # Ceres(2000001) segments but no 0 -> 10 segment.  Join those
            # intervals into one time-routed vector, then compose it with the
            # DE440s barycentric Sun vector.
            candidates = [
                segment for segment in self.asteroids.segments
                if segment.center == 10 and segment.target == 2000001
            ]
            if not candidates:
                raise RuntimeError(
                    f"{self.ceres_path} contains no Sun(10) -> Ceres(2000001) SPK segment"
                )
            ceres_relative = _PiecewiseSpkPosition(candidates)
            self.ceres = self.sun + ceres_relative
            self.bodies["ceres"] = self.ceres

    def _body(self, key: str):
        if key == "ceres" and key not in self.bodies:
            raise FileNotFoundError(
                f"Missing {self.ceres_path}. Ceres calculations require the JPL/NAIF Ceres source kernel."
            )
        try:
            return self.bodies[key]
        except KeyError as exc:
            raise KeyError(f"Unsupported Star Almanack ephemeris body: {key}") from exc

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
    def _instant_from_skyfield(t) -> AstroInstant:
        """Create the Almanack's canonical JDTDB instant from a Skyfield Time."""
        utc = t.utc_datetime()
        jd_utc = datetime_to_jd_utc(utc)
        jd_tdb = float(t.tdb)
        return AstroInstant(
            jd_tdb=jd_tdb,
            tdb_minus_utc_seconds=(jd_tdb - jd_utc) * SECONDS_PER_DAY,
        )

    @staticmethod
    def _supported_planet_magnitude(apparent) -> float | None:
        """Use Skyfield's attributed planet model; fail closed if unsupported."""
        try:
            magnitude = float(planetary_magnitude(apparent))
        except Exception:
            return None
        return magnitude if math.isfinite(magnitude) else None

    def longitude_samples(
        self,
        key: str,
        start: date,
        stop: date,
        step_hours: int = 1,
    ) -> list[tuple[AstroInstant, float]]:
        """Return locally computed apparent geocentric ecliptic longitudes.

        Sampling epochs are civil UTC grid points, but each returned epoch is
        immediately represented as the Almanack's canonical JDTDB AstroInstant.
        The stop-date midnight sample is included, matching the historical
        calendar solver's bracketing behavior.
        """
        if step_hours <= 0:
            raise ValueError("step_hours must be positive")
        if stop < start:
            raise ValueError("stop date must not precede start date")

        body = self._body(key)
        current = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
        end = datetime(stop.year, stop.month, stop.day, tzinfo=timezone.utc)
        step = timedelta(hours=step_hours)
        out: list[tuple[AstroInstant, float]] = []
        earth = self.earth
        while current <= end:
            t = self.ts.from_datetime(current)
            apparent = earth.at(t).observe(body).apparent()
            _, lon, _ = apparent.frame_latlon(ecliptic_frame)
            out.append((self._instant_from_skyfield(t), float(lon.degrees) % 360.0))
            current += step
        return out

    def sample(self, key: str, day: date) -> EphemerisSample:
        """Return a Monday-00:00-UTC publication snapshot for one body."""
        t = self.ts.utc(day.year, day.month, day.day, 0, 0, 0)
        body = self._body(key)
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
