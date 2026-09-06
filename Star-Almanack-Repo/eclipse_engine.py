#!/usr/bin/env python3

"""

Star Almanack — solar eclipse geometry engine.

Purpose

-------

Calculate whether a solar eclipse occurs from independently computed

Sun–Earth–Moon geometry. Published eclipse catalogs are NOT used by this

module.

The Moon is supplied by the Star Almanack ELP2000-82B evaluator. The Sun is

computed with the compact solar model recorded in astronomical-constants.yaml.

The compact Sun vector is rotated into the J2000 mean ecliptic frame so that

it can be compared with the ELP2000-82B Moon vector.

This is the calculation layer. Validation against historical observations

and frozen NASA "Jell-O" targets belongs in validate_star_almanack.py.

Coordinate convention

---------------------

Geocentric rectangular vectors, kilometers, mean ecliptic/equinox J2000.

Time convention

---------------

The public search function accepts a UTC civil date.

For dates in the leap-second era, the numerical ephemeris argument is

approximated as TT/TDB by converting UTC -> TAI -> TT using the published

TAI-UTC offset plus the fixed TT-TAI offset of 32.184 seconds.

For historical dates before 1972, the supplied civil time is treated as an

approximation to UT1 and Delta-T = TT - UT1 is used.

TDB-TT periodic terms are below the accuracy targeted by this eclipse-search

layer and are not modeled here.

The Delta-T model is an engineering approximation; it is intentionally

isolated so it can be replaced by the Almanack's final time-scale layer

without changing the eclipse geometry.

This module does not import or read eclipse-validation-cases.yaml.

"""

from __future__ import annotations

from dataclasses import dataclass

from datetime import datetime, timezone

from pathlib import Path

import argparse

import math

import sys

from typing import Callable

ROOT = Path(__file__).resolve().parent

ELP_DIR = ROOT / "star-almanack-elp82b"

ELP_MANIFEST = ELP_DIR / "elp82b-manifest.json"

# Adopted physical constants.

AU_KM = 149_597_870.700

EARTH_RADIUS_KM = 6_378.137

MOON_RADIUS_KM = 1_737.4

SUN_RADIUS_KM = 695_700.0

DEG = math.pi / 180.0

ARCSEC = DEG / 3600.0

@dataclass(frozen=True)

class Vec3:

    x: float

    y: float

    z: float

    def __add__(self, other: "Vec3") -> "Vec3":

        return Vec3(

            self.x + other.x,

            self.y + other.y,

            self.z + other.z,

        )

    def __sub__(self, other: "Vec3") -> "Vec3":

        return Vec3(

            self.x - other.x,

            self.y - other.y,

            self.z - other.z,

        )

    def __mul__(self, scalar: float) -> "Vec3":

        return Vec3(

            self.x * scalar,

            self.y * scalar,

            self.z * scalar,

        )

    __rmul__ = __mul__

    def dot(self, other: "Vec3") -> float:

        return (

            self.x * other.x

            + self.y * other.y

            + self.z * other.z

        )

    def norm(self) -> float:

        return math.sqrt(self.dot(self))

    def unit(self) -> "Vec3":

        n = self.norm()

        if n == 0.0:

            raise ValueError("zero-length vector")

        return self * (1.0 / n)

@dataclass(frozen=True)

class SolarGeometry:

    jd_utc: float

    jd_tdb_approx: float

    moon: Vec3

    sun: Vec3

    sun_moon_distance_km: float

    q_min_km: float

    axis_distance_km: float

    core_radius_km: float

    penumbra_radius_km: float

    eclipse_margin_km: float

    central_margin_km: float

    eclipse_exists: bool

    eclipse_type: str

@dataclass(frozen=True)

class SolarEclipseEvent:

    date_utc: str

    greatest_jd_utc: float

    greatest_utc: str

    eclipse_exists: bool

    eclipse_type: str

    geometry: SolarGeometry

def _wrap_deg(x: float) -> float:

    return x % 360.0

def _rot_x(v: Vec3, a: float) -> Vec3:

    c, s = math.cos(a), math.sin(a)

    return Vec3(

        v.x,

        c * v.y - s * v.z,

        s * v.y + c * v.z,

    )

def _rot_z(v: Vec3, a: float) -> Vec3:

    c, s = math.cos(a), math.sin(a)

    return Vec3(

        c * v.x - s * v.y,

        s * v.x + c * v.y,

        v.z,

    )

def _mean_obliquity_rad(jd: float) -> float:

    """IAU-style mean obliquity polynomial, adequate for frame conversion."""

    t = (jd - 2451545.0) / 36525.0

    seconds = (

        84381.448

        - 46.8150 * t

        - 0.00059 * t * t

        + 0.001813 * t * t * t

    )

    return seconds * ARCSEC

def _precess_equatorial_date_to_j2000(v: Vec3, jd: float) -> Vec3:

    """

    Rotate an equatorial mean-of-date vector to J2000 using the classical

    IAU 1976 precession angles.

    The angles zeta, z, and theta conventionally describe the

    J2000 -> mean-of-date transformation. Because this function requires

    the inverse transformation, the rotations are applied in inverse order

    with inverse signs.

    Distance is preserved.

    """

    t = (jd - 2451545.0) / 36525.0

    # J2000 -> date precession angles, arcseconds.

    zeta = (

        2306.2181 * t

        + 0.30188 * t * t

        + 0.017998 * t**3

    ) * ARCSEC

    z = (

        2306.2181 * t

        + 1.09468 * t * t

        + 0.018203 * t**3

    ) * ARCSEC

    theta = (

        2004.3109 * t

        - 0.42665 * t * t

        - 0.041833 * t**3

    ) * ARCSEC

    def rot_y(w: Vec3, a: float) -> Vec3:

        c, s = math.cos(a), math.sin(a)

        return Vec3(

            c * w.x + s * w.z,

            w.y,

            -s * w.x + c * w.z,

        )

    # With this module's active-vector rotation convention, the forward

    # J2000 -> date transformation is:

    #

    #     Rz(z) Ry(-theta) Rz(zeta)

    #

    # Therefore date -> J2000 is the inverse:

    #

    #     Rz(-zeta) Ry(theta) Rz(-z)

    #

    # The transformations below act sequentially on the vector, so the

    # rightmost matrix is applied first.

    w = _rot_z(v, -z)

    w = rot_y(w, theta)

    w = _rot_z(w, -zeta)

    return w

def sun_vector_j2000(jd_tdb: float) -> Vec3:

    """

    Compact geocentric Sun vector in J2000 mean ecliptic coordinates.

    The orbital elements are the adopted Star Almanack compact coefficients:

      w = 282.9404 + 4.70935e-5 d

      e = 0.016709 - 1.151e-9 d

      M = 356.0470 + 0.9856002585 d

    where d is days since 2000 Jan 0.0 UT (JD 2451543.5).

    The resulting ecliptic-of-date vector is converted to equatorial-of-date,

    precessed to J2000, then converted to J2000 ecliptic.

    """

    d = jd_tdb - 2451543.5

    w = _wrap_deg(

        282.9404 + 0.0000470935 * d

    ) * DEG

    e = 0.016709 - 0.000000001151 * d

    M = _wrap_deg(

        356.0470 + 0.9856002585 * d

    ) * DEG

    # Solve Kepler's equation.

    E = M

    for _ in range(12):

        f = E - e * math.sin(E) - M

        fp = 1.0 - e * math.cos(E)

        step = f / fp

        E -= step

        if abs(step) < 1e-14:

            break

    # The adopted compact coefficients already describe the Sun's apparent

    # geocentric orbit. true_anom + w therefore gives the geocentric solar

    # longitude directly. Adding another 180 degrees here would reverse the

    # Sun vector and place it on the opposite side of the celestial sphere.

    x = math.cos(E) - e

    y = math.sqrt(1.0 - e * e) * math.sin(E)

    r_au = math.hypot(x, y)

    true_anom = math.atan2(y, x)

    lon = true_anom + w

    ecl_date = Vec3(

        r_au * math.cos(lon),

        r_au * math.sin(lon),

        0.0,

    ) * AU_KM

    # Ecliptic-of-date -> equatorial-of-date.

    eq_date = _rot_x(

        ecl_date,

        _mean_obliquity_rad(jd_tdb),

    )

    # Equatorial-of-date -> equatorial J2000.

    eq_j2000 = _precess_equatorial_date_to_j2000(

        eq_date,

        jd_tdb,

    )

    # Equatorial J2000 -> ecliptic J2000.

    return _rot_x(

        eq_j2000,

        -_mean_obliquity_rad(2451545.0),

    )

def delta_t_seconds(year: float) -> float:

    """

    Piecewise engineering approximation to Delta-T = TT - UT1, seconds.

    Based on standard polynomial approximations commonly used for historical

    eclipse work. It is intentionally encapsulated so a future IERS/Almanack

    time-scale provider can replace it.

    """

    y = year

    if y < -500:

        u = (y - 1820.0) / 100.0

        return -20.0 + 32.0 * u * u

    if y < 500:

        u = y / 100.0

        return (

            10583.6

            - 1014.41 * u

            + 33.78311 * u**2

            - 5.952053 * u**3

            - 0.1798452 * u**4

            + 0.022174192 * u**5

            + 0.0090316521 * u**6

        )

    if y < 1600:

        u = (y - 1000.0) / 100.0

        return (

            1574.2

            - 556.01 * u

            + 71.23472 * u**2

            + 0.319781 * u**3

            - 0.8503463 * u**4

            - 0.005050998 * u**5

            + 0.0083572073 * u**6

        )

    if y < 1700:

        t = y - 1600.0

        return (

            120.0

            - 0.9808 * t

            - 0.01532 * t**2

            + t**3 / 7129.0

        )

    if y < 1800:

        t = y - 1700.0

        return (

            8.83

            + 0.1603 * t

            - 0.0059285 * t**2

            + 0.00013336 * t**3

            - t**4 / 1174000.0

        )

    if y < 1860:

        t = y - 1800.0

        return (

            13.72

            - 0.332447 * t

            + 0.0068612 * t**2

            + 0.0041116 * t**3

            - 0.00037436 * t**4

            + 0.0000121272 * t**5

            - 0.0000001699 * t**6

            + 0.000000000875 * t**7

        )

    if y < 1900:

        t = y - 1860.0

        return (

            7.62

            + 0.5737 * t

            - 0.251754 * t**2

            + 0.01680668 * t**3

            - 0.0004473624 * t**4

            + t**5 / 233174.0

        )

    if y < 1920:

        t = y - 1900.0

        return (

            -2.79

            + 1.494119 * t

            - 0.0598939 * t**2

            + 0.0061966 * t**3

            - 0.000197 * t**4

        )

    if y < 1941:

        t = y - 1920.0

        return (

            21.20

            + 0.84493 * t

            - 0.076100 * t**2

            + 0.0020936 * t**3

        )

    if y < 1961:

        t = y - 1950.0

        return (

            29.07

            + 0.407 * t

            - t**2 / 233.0

            + t**3 / 2547.0

        )

    if y < 1986:

        t = y - 1975.0

        return (

            45.45

            + 1.067 * t

            - t**2 / 260.0

            - t**3 / 718.0

        )

    if y < 2005:

        t = y - 2000.0

        return (

            63.86

            + 0.3345 * t

            - 0.060374 * t**2

            + 0.0017275 * t**3

            + 0.000651814 * t**4

            + 0.00002373599 * t**5

        )

    if y < 2050:

        t = y - 2000.0

        return (

            62.92

            + 0.32217 * t

            + 0.005589 * t**2

        )

    if y < 2150:

        return (

            -20.0

            + 32.0 * ((y - 1820.0) / 100.0) ** 2

            - 0.5628 * (2150.0 - y)

        )

    u = (y - 1820.0) / 100.0

    return -20.0 + 32.0 * u * u

def gregorian_to_jd(

    year: int,

    month: int,

    day: int,

    hour: float = 0.0,

) -> float:

    """Proleptic Gregorian calendar to Julian Date."""

    y, m = year, month

    if m <= 2:

        y -= 1

        m += 12

    A = math.floor(y / 100)

    B = 2 - A + math.floor(A / 4)

    return (

        math.floor(365.25 * (y + 4716))

        + math.floor(30.6001 * (m + 1))

        + day

        + B

        - 1524.5

        + hour / 24.0

    )

def jd_to_iso_utc(jd: float) -> str:

    """

    Convert a Julian Date to a proleptic-Gregorian UTC string.

    The returned value has whole-second resolution. The instant is normalized

    to that resolution *before* it is decomposed into calendar date and clock

    time. This ordering is deliberate.

    Why this matters

    ----------------

    A Julian Date can represent an instant such as 23:59:59.6. Rounding that

    instant to the nearest displayed second must produce 00:00:00 on the next

    civil day. If the calendar date is computed first and the seconds are

    rounded afterward, the time-of-day can become 86400 seconds: an invalid

    clock value that actually belongs to the following date.

    An earlier implementation tried to repair that state by recursively calling

    this function. At the exact 86400-second boundary the adjustment could be

    zero, causing the function to call itself forever until Python raised a

    RecursionError. Normalizing the astronomical instant first removes the

    invalid intermediate state completely. No recursive boundary repair is

    needed, and this function always performs one calendar decomposition.

    """

    # Julian Dates are floating-point day counts. Convert to an integer count

    # of displayed seconds relative to the Julian epoch, then convert back to

    # days. Integer-second normalization carries naturally across midnight.

    #

    # Using floor(x + 0.5) states the intended "nearest second" rule explicitly

    # instead of relying on Python's bankers-rounding behavior for exact .5

    # ties.

    whole_seconds = math.floor(

        jd * 86400.0 + 0.5

    )

    normalized_jd = whole_seconds / 86400.0

    # Julian days begin at noon. Adding 0.5 shifts the boundary to civil

    # midnight before the Gregorian decomposition.

    zf = normalized_jd + 0.5

    Z = math.floor(zf)

    F = zf - Z

    alpha = math.floor(

        (Z - 1867216.25) / 36524.25

    )

    A = Z + 1 + alpha - math.floor(alpha / 4)

    B = A + 1524

    C = math.floor((B - 122.1) / 365.25)

    D = math.floor(365.25 * C)

    E = math.floor((B - D) / 30.6001)

    day_f = (

        B

        - D

        - math.floor(30.6001 * E)

        + F

    )

    day = math.floor(day_f)

    month = (

        E - 1

        if E < 14

        else E - 13

    )

    year = (

        C - 4716

        if month > 2

        else C - 4715

    )

    # Because normalized_jd is already on a whole-second boundary, this value

    # is guaranteed to describe a valid time within the computed civil day.

    # A final round protects against the tiny floating-point error introduced

    # when whole_seconds was divided by 86400 above.

    seconds = round(

        (day_f - day) * 86400.0

    )

    # The arithmetic normalization above should make this invariant true.

    # Keep the assertion close to the conversion so a future code change fails

    # loudly during testing rather than silently recreating a midnight bug.

    if not 0 <= seconds < 86400:

        raise ArithmeticError(

            "Julian-Date normalization failed: "

            "seconds outside civil day"

        )

    hh, rem = divmod(seconds, 3600)

    mm, ss = divmod(rem, 60)

    return (

        f"{year:04d}-{month:02d}-{day:02d}"

        f"T{hh:02d}:{mm:02d}:{ss:02d}Z"

    )

def _decimal_year_from_jd(jd: float) -> float:

    # Sufficient for Delta-T interpolation.

    iso = jd_to_iso_utc(jd)

    year = int(iso[0:4])

    month = int(iso[5:7])

    day = int(iso[8:10])

    return (

        year

        + (month - 0.5) / 12.0

        + (day - 15.0) / 365.2425

    )

def tai_minus_utc_seconds(

    jd_utc: float,

) -> float | None:

    """

    Return TAI - UTC in seconds for the leap-second era.

    Returns None before 1972-01-01. For earlier eclipse work, this search

    layer treats the supplied historical civil time as an approximation to

    UT1 and uses Delta-T = TT - UT1 instead.

    """

    leap_seconds = (

        (2017, 1, 1, 37),

        (2015, 7, 1, 36),

        (2012, 7, 1, 35),

        (2009, 1, 1, 34),

        (2006, 1, 1, 33),

        (1999, 1, 1, 32),

        (1997, 7, 1, 31),

        (1996, 1, 1, 30),

        (1994, 7, 1, 29),

        (1993, 7, 1, 28),

        (1992, 7, 1, 27),

        (1991, 1, 1, 26),

        (1990, 1, 1, 25),

        (1988, 1, 1, 24),

        (1985, 7, 1, 23),

        (1983, 7, 1, 22),

        (1982, 7, 1, 21),

        (1981, 7, 1, 20),

        (1980, 1, 1, 19),

        (1979, 1, 1, 18),

        (1978, 1, 1, 17),

        (1977, 1, 1, 16),

        (1976, 1, 1, 15),

        (1975, 1, 1, 14),

        (1974, 1, 1, 13),

        (1973, 1, 1, 12),

        (1972, 7, 1, 11),

        (1972, 1, 1, 10),

    )

    for year, month, day, offset in leap_seconds:

        if jd_utc >= gregorian_to_jd(

            year,

            month,

            day,

        ):

            return float(offset)

    return None

def utc_to_tdb_approx(jd_utc: float) -> float:

    """

    Approximate UTC/UT1 -> TT/TDB for orbital geometry.

    In the leap-second era, convert UTC -> TAI -> TT using the published

    TAI-UTC offset plus the fixed TT-TAI offset of 32.184 seconds.

    Before 1972, this search layer treats the historical civil argument as

    an approximation to UT1 and obtains TT from Delta-T = TT - UT1.

    TDB-TT periodic terms are below the accuracy targeted by this first

    eclipse-search layer and are not modeled here.

    """

    tai_minus_utc = tai_minus_utc_seconds(

        jd_utc

    )

    if tai_minus_utc is not None:

        tt_minus_utc = (

            tai_minus_utc + 32.184

        )

        return (

            jd_utc

            + tt_minus_utc / 86400.0

        )

    dt = delta_t_seconds(

        _decimal_year_from_jd(jd_utc)

    )

    return jd_utc + dt / 86400.0

class EclipseEngine:

    def __init__(

        self,

        manifest: Path = ELP_MANIFEST,

    ):

        if not manifest.exists():

            raise FileNotFoundError(

                f"ELP2000 normalized manifest not found: {manifest}\n"

                "Run the repository bootstrap/normalize workflow first."

            )

        sys.path.insert(

            0,

            str(ELP_DIR),

        )

        import lunar_elp  # local project module

        self._lunar_elp = lunar_elp

        self._normalized = (

            lunar_elp.load_normalized(

                manifest

            )

        )

    def moon_vector_j2000(

        self,

        jd_tdb: float,

    ) -> Vec3:

        result = self._lunar_elp.evaluate(

            self._normalized,

            jd_tdb,

            precision_rad=0.0,

        )

        r = result.rectangular

        return Vec3(

            float(r.x_km),

            float(r.y_km),

            float(r.z_km),

        )

    def geometry_at_utc_jd(

        self,

        jd_utc: float,

    ) -> SolarGeometry:

        jd_tdb = utc_to_tdb_approx(

            jd_utc

        )

        moon = self.moon_vector_j2000(

            jd_tdb

        )

        sun = sun_vector_j2000(

            jd_tdb

        )

        sm = moon - sun

        L = sm.norm()

        u = sm.unit()

        q = -moon.dot(u)

        closest = moon + u * q

        rho = closest.norm()

        if q <= 0.0:

            # Shadow axis points away from Earth:

            # not solar-eclipse geometry.

            r_core = float("nan")

            r_pen = 0.0

            eclipse_margin = float("inf")

            central_margin = float("inf")

            exists = False

            kind = "none"

        else:

            r_core = (

                MOON_RADIUS_KM

                - q

                * (

                    SUN_RADIUS_KM

                    - MOON_RADIUS_KM

                )

                / L

            )

            r_pen = (

                MOON_RADIUS_KM

                + q

                * (

                    SUN_RADIUS_KM

                    + MOON_RADIUS_KM

                )

                / L

            )

            # Penumbra intersects Earth if the distance between the two axes

            # is no greater than the sum of their radii.

            eclipse_margin = (

                rho

                - (

                    EARTH_RADIUS_KM

                    + r_pen

                )

            )

            central_margin = (

                rho

                - EARTH_RADIUS_KM

            )

            exists = (

                eclipse_margin <= 0.0

            )

            if not exists:

                kind = "none"

            elif central_margin > 0.0:

                kind = "partial"

            elif r_core > 0.0:

                kind = "total"

            elif r_core < 0.0:

                kind = "annular"

            else:

                kind = "central"

        return SolarGeometry(

            jd_utc=jd_utc,

            jd_tdb_approx=jd_tdb,

            moon=moon,

            sun=sun,

            sun_moon_distance_km=L,

            q_min_km=q,

            axis_distance_km=rho,

            core_radius_km=r_core,

            penumbra_radius_km=r_pen,

            eclipse_margin_km=eclipse_margin,

            central_margin_km=central_margin,

            eclipse_exists=exists,

            eclipse_type=kind,

        )

    def find_solar_eclipse(

        self,

        date_utc: str,

        *,

        search_hours: float = 36.0,

    ) -> SolarEclipseEvent:

        """

        Search for the best Sun-Moon shadow alignment around a UTC date.

        The objective is axis_distance_km. A coarse scan finds the basin,

        then golden-section minimization refines the instant.

        """

        year, month, day = (

            int(x)

            for x in date_utc.split("-")

        )

        jd0 = gregorian_to_jd(

            year,

            month,

            day,

            0.0,

        )

        half = search_hours / 24.0

        start = jd0 - half

        end = jd0 + half

        # Coarse scan every 30 minutes.

        step = 0.5 / 24.0

        best_jd = start

        best_val = float("inf")

        t = start

        while t <= end + 1e-12:

            g = self.geometry_at_utc_jd(

                t

            )

            if (

                g.q_min_km > 0.0

                and g.axis_distance_km < best_val

            ):

                best_val = g.axis_distance_km

                best_jd = t

            t += step

        # Refine within +/- 1 hour of the best coarse sample.

        a = max(

            start,

            best_jd - 1.0 / 24.0,

        )

        b = min(

            end,

            best_jd + 1.0 / 24.0,

        )

        def objective(jd: float) -> float:

            g = self.geometry_at_utc_jd(

                jd

            )

            if g.q_min_km <= 0.0:

                return 1e99

            return g.axis_distance_km

        best_jd = _golden_minimize(

            objective,

            a,

            b,

            tolerance_seconds=0.05,

        )

        geom = self.geometry_at_utc_jd(

            best_jd

        )

        return SolarEclipseEvent(

            date_utc=date_utc,

            greatest_jd_utc=best_jd,

            greatest_utc=jd_to_iso_utc(

                best_jd

            ),

            eclipse_exists=geom.eclipse_exists,

            eclipse_type=geom.eclipse_type,

            geometry=geom,

        )

def _golden_minimize(

    f: Callable[[float], float],

    a: float,

    b: float,

    *,

    tolerance_seconds: float,

) -> float:

    """Golden-section minimization on a Julian-Date interval."""

    invphi = (

        math.sqrt(5.0) - 1.0

    ) / 2.0

    tol_days = (

        tolerance_seconds / 86400.0

    )

    c = b - invphi * (b - a)

    d = a + invphi * (b - a)

    fc = f(c)

    fd = f(d)

    for _ in range(100):

        if (b - a) <= tol_days:

            break

        if fc < fd:

            b, d, fd = d, c, fc

            c = b - invphi * (b - a)

            fc = f(c)

        else:

            a, c, fc = c, d, fd

            d = a + invphi * (b - a)

            fd = f(d)

    return (a + b) / 2.0

def _print_event(

    event: SolarEclipseEvent,

) -> None:

    g = event.geometry

    print(

        f"date requested:      "

        f"{event.date_utc}"

    )

    print(

        f"greatest alignment:  "

        f"{event.greatest_utc}"

    )

    print(

        f"eclipse exists:      "

        f"{'yes' if event.eclipse_exists else 'no'}"

    )

    print(

        f"classification:      "

        f"{event.eclipse_type}"

    )

    print(

        f"axis distance:       "

        f"{g.axis_distance_km:.3f} km"

    )

    print(

        f"Earth radius:        "

        f"{EARTH_RADIUS_KM:.3f} km"

    )

    print(

        f"core radius:         "

        f"{g.core_radius_km:.3f} km"

    )

    print(

        f"penumbra radius:     "

        f"{g.penumbra_radius_km:.3f} km"

    )

    print(

        f"eclipse margin:      "

        f"{g.eclipse_margin_km:+.3f} km"

    )

    print(

        f"central margin:      "

        f"{g.central_margin_km:+.3f} km"

    )

    print(

        f"q(min):              "

        f"{g.q_min_km:.3f} km"

    )

    print(

        f"Sun-Moon distance:   "

        f"{g.sun_moon_distance_km:.3f} km"

    )

def main() -> None:

    parser = argparse.ArgumentParser(

        description=(

            "Star Almanack independent "

            "solar eclipse geometry engine"

        )

    )

    parser.add_argument(

        "date",

        help=(

            "UTC date to search, "

            "YYYY-MM-DD "

            "(proleptic Gregorian)"

        ),

    )

    parser.add_argument(

        "--manifest",

        type=Path,

        default=ELP_MANIFEST,

        help="normalized ELP2000-82B manifest",

    )

    parser.add_argument(

        "--search-hours",

        type=float,

        default=36.0,

        help=(

            "hours on either side of "

            "00:00 UTC to search "

            "(default 36)"

        ),

    )

    args = parser.parse_args()

    engine = EclipseEngine(

        args.manifest

    )

    event = engine.find_solar_eclipse(

        args.date,

        search_hours=args.search_hours,

    )

    _print_event(event)

if __name__ == "__main__":

    main()