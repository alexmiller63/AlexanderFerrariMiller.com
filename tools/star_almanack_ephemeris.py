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
- Moon magnitude is calculated locally from the published Allen/Schaefer lunar
  phase approximation, with Earth-Moon and Sun-Moon distance correction.
- Ceres magnitude is calculated locally with the standard IAU H-G asteroid
  phase law using JPL's published Ceres H=3.34 and G=0.12 parameters.
- Pluto magnitude is calculated locally from SPK-derived Sun/Pluto/Earth
  geometry using the published linear visual phase law
  V = -1.01 + 5 log10(r delta) + 0.041 alpha.

Kernel acquisition/caching belongs to the workflow/runtime environment. The
normal GitHub Actions path stores the kernels under .cache/skyfield and reuses
them through actions/cache. See EPHEMERIS-PROVENANCE.md.
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
AU_KM = 149597870.7
MEAN_LUNAR_DISTANCE_KM = 384400.0
CERES_H = 3.34
CERES_G = 0.12
PLUTO_V_1_0 = -1.01
PLUTO_PHASE_COEFF = 0.041
DEFAULT_OBSERVER_LATITUDE_DEG = 45.0
PLANET_HORIZON_DEG = -0.5667
SUN_HORIZON_DEG = -0.8333
OBSERVING_HOUR_ANGLE_HOURS = 9.0


@dataclass(frozen=True)
class EphemerisSample:
    longitude_deg: float
    latitude_deg: float
    magnitude: float | None
    elongation_deg: float
    right_ascension_hours: float
    declination_deg: float
    sun_right_ascension_hours: float
    sun_declination_deg: float


def _norm3(v) -> float:
    return math.sqrt(float(v[0] ** 2 + v[1] ** 2 + v[2] ** 2))


def _difference(a, b):
    return (
        float(a[0] - b[0]),
        float(a[1] - b[1]),
        float(a[2] - b[2]),
    )


def _angle_deg(a, b) -> float:
    dot = float(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])
    an = _norm3(a)
    bn = _norm3(b)
    cosine = max(-1.0, min(1.0, dot / (an * bn)))
    return math.degrees(math.acos(cosine))


class _PiecewiseSpkPosition(VectorFunction):
    """Present several consecutive SPK segments as one Skyfield vector.

    The historical Ceres kernel is split into hundreds of Sun-to-Ceres
    segments. They are source coefficients for different time intervals, not
    competing answers. Skyfield exposes each interval as a separate vector,
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

        self.asteroids = None
        self.ceres = None
        if self.ceres_path.is_file():
            self.asteroids = load_file(str(self.ceres_path))
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
        return _angle_deg(a.position.au, b.position.au)

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

    @staticmethod
    def _moon_magnitude(body_at, sun_at, earth_at) -> float:
        """Approximate apparent V magnitude from local geometry."""
        moon = body_at.position.au
        sun = sun_at.position.au
        earth = earth_at.position.au
        moon_to_sun = _difference(sun, moon)
        moon_to_earth = _difference(earth, moon)
        phase = _angle_deg(moon_to_sun, moon_to_earth)
        earth_distance_au = _norm3(moon_to_earth)
        sun_distance_au = _norm3(moon_to_sun)
        mean_lunar_distance_au = MEAN_LUNAR_DISTANCE_KM / AU_KM
        distance_term = 5.0 * math.log10(
            (earth_distance_au / mean_lunar_distance_au) * sun_distance_au
        )
        return -12.73 + 0.026 * phase + 4.0e-9 * phase ** 4 + distance_term

    @staticmethod
    def _ceres_magnitude(body_at, sun_at, earth_at) -> float:
        """Calculate Ceres apparent V magnitude with the standard H-G law."""
        ceres = body_at.position.au
        sun = sun_at.position.au
        earth = earth_at.position.au
        ceres_to_sun = _difference(sun, ceres)
        ceres_to_earth = _difference(earth, ceres)
        phase_deg = _angle_deg(ceres_to_sun, ceres_to_earth)
        phase_rad = math.radians(phase_deg)
        tangent = math.tan(phase_rad / 2.0)
        phi1 = math.exp(-3.33 * tangent ** 0.63)
        phi2 = math.exp(-1.87 * tangent ** 1.22)
        phase_term = (1.0 - CERES_G) * phi1 + CERES_G * phi2
        r_au = _norm3(ceres_to_sun)
        delta_au = _norm3(ceres_to_earth)
        return (
            CERES_H
            + 5.0 * math.log10(r_au * delta_au)
            - 2.5 * math.log10(phase_term)
        )

    @staticmethod
    def _pluto_magnitude(body_at, sun_at, earth_at) -> float:
        """Calculate Pluto apparent visual magnitude from local geometry.

        The published linear phase relation is evaluated with r (Sun-Pluto
        distance), delta (Earth-Pluto distance), and alpha (phase angle) all
        calculated here from the cached JPL SPK vectors. No ephemeris magnitude
        answer is downloaded.
        """
        pluto = body_at.position.au
        sun = sun_at.position.au
        earth = earth_at.position.au
        pluto_to_sun = _difference(sun, pluto)
        pluto_to_earth = _difference(earth, pluto)
        phase_deg = _angle_deg(pluto_to_sun, pluto_to_earth)
        r_au = _norm3(pluto_to_sun)
        delta_au = _norm3(pluto_to_earth)
        return (
            PLUTO_V_1_0
            + 5.0 * math.log10(r_au * delta_au)
            + PLUTO_PHASE_COEFF * phase_deg
        )

    def longitude_samples(
        self,
        key: str,
        start: date,
        stop: date,
        step_hours: int = 1,
    ) -> list[tuple[AstroInstant, float]]:
        """Return locally computed apparent geocentric ecliptic longitudes."""
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

    @staticmethod
    def _format_lat(hours: float) -> str:
        total_minutes = int(round((hours % 24.0) * 60.0)) % (24 * 60)
        hour, minute = divmod(total_minutes, 60)
        return f"{hour:02d}:{minute:02d}"

    @staticmethod
    def rise_set_lat(sample: EphemerisSample, key: str, latitude_deg: float) -> tuple[str, str]:
        """Return rise and set times in Local Apparent Time for one snapshot.

        The calculation uses the body's apparent right ascension/declination at
        the Monday 00:00 UTC snapshot.  LAT is derived from the body's rise/set
        hour angle relative to the Sun's apparent right ascension, so longitude
        is not required for the published LAT result.
        """
        if not -90.0 <= latitude_deg <= 90.0:
            raise ValueError("latitude_deg must be between -90 and +90 degrees")

        latitude = math.radians(latitude_deg)
        declination = math.radians(sample.declination_deg)
        horizon = math.radians(SUN_HORIZON_DEG if key == "sun" else PLANET_HORIZON_DEG)
        sin_lat = math.sin(latitude)
        cos_lat = math.cos(latitude)
        sin_dec = math.sin(declination)
        cos_dec = math.cos(declination)

        if abs(cos_lat * cos_dec) < 1.0e-12:
            always_up = sin_lat * sin_dec > math.sin(horizon)
            if always_up:
                return ("always up", "does not set")
            return ("does not rise", "does not set")

        cosine_hour_angle = (math.sin(horizon) - sin_lat * sin_dec) / (cos_lat * cos_dec)
        if cosine_hour_angle < -1.0:
            return ("always up", "does not set")
        if cosine_hour_angle > 1.0:
            return ("does not rise", "does not set")

        hour_angle = math.degrees(math.acos(max(-1.0, min(1.0, cosine_hour_angle)))) / 15.0
        rise_lat = 12.0 + (sample.right_ascension_hours - hour_angle - sample.sun_right_ascension_hours)
        set_lat = 12.0 + (sample.right_ascension_hours + hour_angle - sample.sun_right_ascension_hours)
        return (StarAlmanackEphemeris._format_lat(rise_lat), StarAlmanackEphemeris._format_lat(set_lat))

    @staticmethod
    def daylight_at_observing_time(sample: EphemerisSample, latitude_deg: float) -> bool:
        """Whether daylight reaches the standard apparent horizon at 21:00 LAT."""
        if not -90.0 <= latitude_deg <= 90.0:
            raise ValueError("latitude_deg must be between -90 and +90 degrees")
        latitude = math.radians(latitude_deg)
        declination = math.radians(sample.sun_declination_deg)
        hour_angle = math.radians(15.0 * OBSERVING_HOUR_ANGLE_HOURS)
        altitude = math.asin(
            math.sin(latitude) * math.sin(declination)
            + math.cos(latitude) * math.cos(declination) * math.cos(hour_angle)
        )
        return math.degrees(altitude) > SUN_HORIZON_DEG

    def sample(self, key: str, day: date) -> EphemerisSample:
        """Return a Monday-00:00-UTC publication snapshot for one body."""
        t = self.ts.utc(day.year, day.month, day.day, 0, 0, 0)
        body = self._body(key)
        earth_at = self.earth.at(t)
        sun_at = self.sun.at(t)
        body_at = body.at(t)
        apparent = earth_at.observe(body).apparent()
        lat, lon, _ = apparent.frame_latlon(ecliptic_frame)

        sun_apparent = earth_at.observe(self.sun).apparent()
        ra, dec, _ = apparent.radec()
        sun_ra, sun_dec, _ = sun_apparent.radec()
        elongation = 0.0 if key == "sun" else self._angle_between(apparent, sun_apparent)
        if key == "moon":
            magnitude = self._moon_magnitude(body_at, sun_at, earth_at)
        elif key == "ceres":
            magnitude = self._ceres_magnitude(body_at, sun_at, earth_at)
        elif key == "pluto":
            magnitude = self._pluto_magnitude(body_at, sun_at, earth_at)
        else:
            magnitude = self._supported_planet_magnitude(apparent)

        return EphemerisSample(
            longitude_deg=float(lon.degrees) % 360.0,
            latitude_deg=float(lat.degrees),
            magnitude=magnitude,
            elongation_deg=elongation,
            right_ascension_hours=float(ra.hours) % 24.0,
            declination_deg=float(dec.degrees),
            sun_right_ascension_hours=float(sun_ra.hours) % 24.0,
            sun_declination_deg=float(sun_dec.degrees),
        )
