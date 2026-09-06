#!/usr/bin/env python3

"""

Star Almanack — compact-Sun / frame-conversion prosecution lineup.

Purpose

-------

Separate two possible sources of the epoch-dependent solar error seen in

Star Almanack eclipse validation:

    1. the compact solar model itself

    2. the ecliptic-of-date -> J2000 frame conversion

For every test epoch this diagnostic computes four principal Sun vectors:

    RAW COMPACT

        Star Almanack compact solar model in mean ecliptic-of-date

        coordinates, before the production frame transformation.

    PRODUCTION

        eclipse_engine.sun_vector_j2000(), exactly as used by the

        production eclipse calculation.

    ERFA TRANSFORMED

        The same raw compact vector transformed independently from

        mean ecliptic-of-date to J2000 ecliptic using ERFA / IAU 2006

        reference-frame routines.

    JPL HORIZONS

        Independent geometric geocentric Sun vector from JPL Horizons

        in ICRF/J2000 ecliptic coordinates.

The JPL vector is also independently transformed by ERFA into

ecliptic-of-date coordinates.

Principal measurements

----------------------

MODEL-ONLY RESIDUAL

    raw compact Sun

        minus

    JPL Sun transformed to ecliptic-of-date

FRAME DISAGREEMENT

    production transformed compact Sun

        minus

    ERFA-transformed compact Sun

PRODUCTION RESIDUAL

    production transformed compact Sun

        minus

    JPL Sun in J2000 ecliptic

ERFA COMBINED RESIDUAL

    ERFA-transformed compact Sun

        minus

    JPL Sun in J2000 ecliptic

The diagnostic also prints direct rectangular-vector difference magnitudes:

    RAW COMPACT - JPL/DATE

    PRODUCTION - JPL/J2000

    ERFA - JPL/J2000

    PRODUCTION - ERFA

Frame magnitude experiment

--------------------------

The production frame transformation and ERFA transformation are applied

to the exact same raw compact vector.

For each epoch we measure:

    production frame angular shift

    ERFA frame angular shift

    production / ERFA shift-magnitude ratio

A ratio near:

    1.0000

means the two transformations have essentially the same rotation

magnitude for that Sun vector.

The previously registered investigative target:

    1.0560

is printed explicitly for comparison. This target is diagnostic only.

It is not assumed to be correct and does not affect PASS/FAIL.

Full 3-D frame experiment

-------------------------

A single Sun vector cannot completely characterize a three-dimensional

rotation. Therefore this diagnostic also applies both transformations to

the Cartesian X, Y, and Z basis vectors.

From those transformed basis vectors it reconstructs the complete

production and ERFA rotation matrices.

It then measures:

    disagreement of transformed X, Y, and Z basis vectors

    complete production rotation magnitude

    complete ERFA rotation magnitude

    production / ERFA rotation-magnitude ratio

    rotation-axis agreement

    residual rotation from ERFA to production

    matrix Frobenius difference

    determinant

    orthogonality error

The residual rotation:

    production_matrix @ erfa_matrix.T

is the cleanest direct measure of disagreement between the two complete

date-to-J2000 transformations.

Interpretation

--------------

If MODEL-ONLY RESIDUAL is large:

    the compact solar model itself contributes real error.

If FRAME DISAGREEMENT is large:

    the production date-to-J2000 transformation contributes real error.

If the complete matrix magnitude ratio is far from 1:

    the production transformation has the wrong rotation magnitude.

If the rotation axes strongly disagree:

    the production transformation has a wrong axis and/or direction.

If the relative production-vs-ERFA rotation is large:

    the production transformation is independently implicated.

If both model-only and frame errors are large:

    both members of the crime family are guilty.

If both become small after correction but eclipse timing still has a

systematic residual:

    the surviving residual becomes evidence for another culprit elsewhere

    in the eclipse calculation.

Independent frame authority

---------------------------

This diagnostic uses PyERFA, the Python wrapper around ERFA, which is

derived from the IAU SOFA Standards of Fundamental Astronomy routines.

ERFA's ecm06() supplies the IAU 2006 rotation matrix from ICRS equatorial

coordinates to mean ecliptic coordinates for a specified TT date.

The transformation performed here is therefore independent of the

classical IAU-1976 precession implementation inside eclipse_engine.py.

Time convention

---------------

The same production approximate dynamical JD used by the eclipse engine is

used for the compact Sun and for the JPL Horizons request.

ERFA's frame routines formally accept TT. For this diagnostic the

production approximate TDB/TT argument is used as TT for the frame rotation.

The TDB-TT difference is vastly too small to explain degree-scale

epoch-dependent frame errors and is irrelevant to the question being tested.

Network behavior

----------------

This diagnostic intentionally contacts JPL Horizons.

A Horizons/network failure is diagnostic unavailability, not a Star

Almanack validation failure. The program reports the failure and exits

successfully.

This file is DIAGNOSTIC ONLY. It does not modify production eclipse

geometry and does not supply JPL data to eclipse_engine.py.

"""

from __future__ import annotations

import json

import math

import re

from urllib.parse import urlencode

from urllib.request import Request, urlopen

import erfa

import numpy as np

import eclipse_engine

HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"

J2000_JD = 2451545.0

AU_KM = eclipse_engine.AU_KM

DEG = math.pi / 180.0

# Previously registered investigative clue.

#

# This is NOT treated as truth and does NOT affect PASS/FAIL.

MAGNITUDE_TARGET = 1.0560

# ---------------------------------------------------------------------------

# Representative epochs

# ---------------------------------------------------------------------------

TEST_EPOCHS = [

    (

        "1919 eclipse",

        "1919-05-29T13:08:34Z",

    ),

    (

        "1963 eclipse",

        "1963-07-20T20:35:38Z",

    ),

    (

        "1991 eclipse",

        "1991-07-11T19:06:03Z",

    ),

    (

        "J2000",

        "2000-01-01T12:00:00Z",

    ),

    (

        "2017 eclipse",

        "2017-08-21T18:25:30Z",

    ),

    (

        "2024 eclipse",

        "2024-04-08T18:17:15Z",

    ),

]

# ---------------------------------------------------------------------------

# General vector helpers

# ---------------------------------------------------------------------------

def wrap_signed_deg(angle: float) -> float:

    """Normalize degrees to [-180, +180)."""

    return (angle + 180.0) % 360.0 - 180.0

def vector_longitude_deg(

    v: eclipse_engine.Vec3,

) -> float:

    """Ecliptic longitude of a rectangular vector."""

    return math.degrees(

        math.atan2(

            v.y,

            v.x,

        )

    ) % 360.0

def angle_between_deg(

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> float:

    """Three-dimensional angular separation between two vectors."""

    denom = a.norm() * b.norm()

    if denom == 0.0:

        return float("nan")

    cosine = a.dot(b) / denom

    cosine = max(

        -1.0,

        min(

            1.0,

            cosine,

        ),

    )

    return math.degrees(

        math.acos(cosine)

    )

def vec_to_numpy(

    v: eclipse_engine.Vec3,

) -> np.ndarray:

    """Convert Star Almanack Vec3 to a NumPy vector."""

    return np.array(

        [

            v.x,

            v.y,

            v.z,

        ],

        dtype=float,

    )

def numpy_to_vec(

    a: np.ndarray,

) -> eclipse_engine.Vec3:

    """Convert a three-element NumPy vector to Star Almanack Vec3."""

    return eclipse_engine.Vec3(

        float(a[0]),

        float(a[1]),

        float(a[2]),

    )

def vector_difference(

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> eclipse_engine.Vec3:

    """Rectangular vector a - b."""

    return eclipse_engine.Vec3(

        a.x - b.x,

        a.y - b.y,

        a.z - b.z,

    )

def vector_difference_km(

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> float:

    """Magnitude of rectangular vector difference a - b, kilometers."""

    return vector_difference(

        a,

        b,

    ).norm()

def safe_ratio(

    numerator: float,

    denominator: float,

) -> float:

    """Divide while handling an effectively-zero denominator."""

    if abs(denominator) < 1.0e-15:

        return float("nan")

    return numerator / denominator

def finite_values(

    values: list[float],

) -> list[float]:

    """Remove NaN and infinity from a list."""

    return [

        value

        for value in values

        if math.isfinite(value)

    ]

def print_vector(

    label: str,

    vector: eclipse_engine.Vec3,

) -> None:

    """Print a rectangular vector."""

    print(

        f"  {label:<22}"

        f"x={vector.x:+.3f} km  "

        f"y={vector.y:+.3f} km  "

        f"z={vector.z:+.3f} km"

    )

def print_difference(

    label: str,

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> float:

    """

    Print a-b rectangular components and magnitude.

    Returns magnitude in kilometers.

    """

    difference = vector_difference(

        a,

        b,

    )

    magnitude = difference.norm()

    print(

        f"  {label:<24}"

        f"dx={difference.x:+.3f} km  "

        f"dy={difference.y:+.3f} km  "

        f"dz={difference.z:+.3f} km"

    )

    print(

        f"  {'magnitude':<24}"

        f"{magnitude:.3f} km"

    )

    return magnitude

# ---------------------------------------------------------------------------

# Civil timestamp -> production dynamical argument

# ---------------------------------------------------------------------------

def iso_z_to_jd(

    text: str,

) -> float:

    """

    Convert an ISO UTC-like timestamp to Julian Date using the same calendar

    routine used by the production eclipse engine.

    """

    date_part, time_part = text.rstrip("Z").split("T")

    year, month, day = (

        int(part)

        for part in date_part.split("-")

    )

    hour_text, minute_text, second_text = time_part.split(":")

    hour = int(hour_text)

    minute = int(minute_text)

    second = float(second_text)

    decimal_hour = (

        hour

        + minute / 60.0

        + second / 3600.0

    )

    return eclipse_engine.gregorian_to_jd(

        year,

        month,

        day,

        decimal_hour,

    )

def production_tdb_jd(

    civil_text: str,

) -> tuple[float, float]:

    """

    Return the civil JD and the same approximate dynamical JD used by the

    production eclipse engine.

    """

    jd_civil = iso_z_to_jd(

        civil_text

    )

    jd_tdb = eclipse_engine.utc_to_tdb_approx(

        jd_civil

    )

    return (

        jd_civil,

        jd_tdb,

    )

# ---------------------------------------------------------------------------

# Raw Star Almanack compact solar model

# ---------------------------------------------------------------------------

def compact_sun_ecliptic_of_date(

    jd_tdb: float,

) -> eclipse_engine.Vec3:

    """

    Evaluate the Star Almanack compact Sun exactly as production does,

    but STOP before the ecliptic-of-date -> J2000 frame transformation.

    Output:

        mean ecliptic-of-date rectangular vector, kilometers

    """

    d = jd_tdb - 2451543.5

    w = (

        282.9404

        + 0.0000470935 * d

    ) % 360.0

    e = (

        0.016709

        - 0.000000001151 * d

    )

    M = (

        356.0470

        + 0.9856002585 * d

    ) % 360.0

    w_rad = w * DEG

    M_rad = M * DEG

    E = M_rad

    for _ in range(12):

        f = (

            E

            - e * math.sin(E)

            - M_rad

        )

        fp = (

            1.0

            - e * math.cos(E)

        )

        step = f / fp

        E -= step

        if abs(step) < 1e-14:

            break

    x_orbit = (

        math.cos(E)

        - e

    )

    y_orbit = (

        math.sqrt(

            1.0 - e * e

        )

        * math.sin(E)

    )

    r_au = math.hypot(

        x_orbit,

        y_orbit,

    )

    true_anomaly = math.atan2(

        y_orbit,

        x_orbit,

    )

    longitude = (

        true_anomaly

        + w_rad

    )

    return eclipse_engine.Vec3(

        r_au * math.cos(longitude) * AU_KM,

        r_au * math.sin(longitude) * AU_KM,

        0.0,

    )

# ---------------------------------------------------------------------------

# Independent ERFA frame transformations

# ---------------------------------------------------------------------------

def erfa_ecliptic_matrix(

    jd_tt: float,

) -> np.ndarray:

    """

    IAU 2006 ICRS-equatorial -> mean-ecliptic-of-date rotation matrix.

    """

    date1 = J2000_JD

    date2 = jd_tt - J2000_JD

    matrix = erfa.ecm06(

        date1,

        date2,

    )

    return np.asarray(

        matrix,

        dtype=float,

    )

def erfa_ecliptic_date_to_j2000(

    vector_date: eclipse_engine.Vec3,

    jd_tt: float,

) -> eclipse_engine.Vec3:

    """

    Transform mean ecliptic-of-date -> J2000 mean ecliptic independently.

    """

    date_matrix = erfa_ecliptic_matrix(

        jd_tt

    )

    j2000_matrix = erfa_ecliptic_matrix(

        J2000_JD

    )

    v_date = vec_to_numpy(

        vector_date

    )

    v_icrs = date_matrix.T @ v_date

    v_j2000 = j2000_matrix @ v_icrs

    return numpy_to_vec(

        v_j2000

    )

def erfa_ecliptic_j2000_to_date(

    vector_j2000: eclipse_engine.Vec3,

    jd_tt: float,

) -> eclipse_engine.Vec3:

    """

    Transform J2000 mean ecliptic -> mean ecliptic-of-date independently.

    """

    date_matrix = erfa_ecliptic_matrix(

        jd_tt

    )

    j2000_matrix = erfa_ecliptic_matrix(

        J2000_JD

    )

    v_j2000 = vec_to_numpy(

        vector_j2000

    )

    v_icrs = j2000_matrix.T @ v_j2000

    v_date = date_matrix @ v_icrs

    return numpy_to_vec(

        v_date

    )

# ---------------------------------------------------------------------------

# Full production-vs-ERFA frame rotation test

# ---------------------------------------------------------------------------

def production_ecliptic_date_to_j2000(

    vector_date: eclipse_engine.Vec3,

    jd_tt: float,

) -> eclipse_engine.Vec3:

    """

    Apply exactly the frame transformation currently used by production

    to an arbitrary input vector.

    """

    eq_date = eclipse_engine._rot_x(

        vector_date,

        eclipse_engine._mean_obliquity_rad(jd_tt),

    )

    eq_j2000 = eclipse_engine._precess_equatorial_date_to_j2000(

        eq_date,

        jd_tt,

    )

    return eclipse_engine._rot_x(

        eq_j2000,

        -eclipse_engine._mean_obliquity_rad(J2000_JD),

    )

def frame_matrix(

    transform,

    jd_tt: float,

) -> np.ndarray:

    """

    Reconstruct a complete 3x3 rotation matrix by transforming

    Cartesian basis vectors.

    """

    basis = (

        eclipse_engine.Vec3(

            1.0,

            0.0,

            0.0,

        ),

        eclipse_engine.Vec3(

            0.0,

            1.0,

            0.0,

        ),

        eclipse_engine.Vec3(

            0.0,

            0.0,

            1.0,

        ),

    )

    columns = [

        vec_to_numpy(

            transform(

                vector,

                jd_tt,

            )

        )

        for vector in basis

    ]

    return np.column_stack(

        columns

    )

def rotation_angle_deg(

    matrix: np.ndarray,

) -> float:

    """Principal angular magnitude of a proper 3-D rotation matrix."""

    cosine = (

        float(np.trace(matrix))

        - 1.0

    ) / 2.0

    cosine = max(

        -1.0,

        min(

            1.0,

            cosine,

        ),

    )

    return math.degrees(

        math.acos(cosine)

    )

def rotation_vector_deg(

    matrix: np.ndarray,

) -> np.ndarray:

    """

    Axis-angle rotation represented as a 3-vector in degrees.

    Direction gives the rotation axis.

    Vector magnitude gives the rotation angle.

    """

    angle = rotation_angle_deg(

        matrix

    )

    angle_rad = math.radians(

        angle

    )

    if abs(angle_rad) < 1.0e-12:

        return np.zeros(

            3,

            dtype=float,

        )

    denominator = (

        2.0

        * math.sin(angle_rad)

    )

    if abs(denominator) < 1.0e-15:

        return np.zeros(

            3,

            dtype=float,

        )

    axis = np.array(

        [

            matrix[2, 1] - matrix[1, 2],

            matrix[0, 2] - matrix[2, 0],

            matrix[1, 0] - matrix[0, 1],

        ],

        dtype=float,

    ) / denominator

    axis_norm = float(

        np.linalg.norm(axis)

    )

    if axis_norm == 0.0:

        return np.zeros(

            3,

            dtype=float,

        )

    axis /= axis_norm

    return axis * angle

def rotation_vector_magnitude(

    vector: np.ndarray,

) -> float:

    """Magnitude of an axis-angle rotation vector, degrees."""

    return float(

        np.linalg.norm(vector)

    )

def rotation_axis_cosine(

    a: np.ndarray,

    b: np.ndarray,

) -> float:

    """

    Cosine of the angle between two rotation axes.

      +1 -> same direction

      -1 -> opposite direction

       0 -> perpendicular

    """

    a_norm = float(

        np.linalg.norm(a)

    )

    b_norm = float(

        np.linalg.norm(b)

    )

    if (

        a_norm < 1.0e-15

        or b_norm < 1.0e-15

    ):

        return float("nan")

    return float(

        np.dot(

            a,

            b,

        )

        / (

            a_norm

            * b_norm

        )

    )

def orthogonality_error(

    matrix: np.ndarray,

) -> float:

    """Frobenius norm of R R^T - I."""

    identity = np.identity(

        3,

        dtype=float,

    )

    return float(

        np.linalg.norm(

            matrix @ matrix.T

            - identity,

            ord="fro",

        )

    )

# ---------------------------------------------------------------------------

# JPL Horizons

# ---------------------------------------------------------------------------

def horizons_request(

    jd_tdb: float,

) -> str:

    """

    Request a geometric geocentric Sun vector from JPL Horizons.

    """

    params = {

        "format": "json",

        "COMMAND": "'10'",

        "CENTER": "'500@399'",

        "EPHEM_TYPE": "'VECTORS'",

        "REF_SYSTEM": "'ICRF'",

        "REF_PLANE": "'ECLIPTIC'",

        "OUT_UNITS": "'KM-S'",

        "VEC_TABLE": "'2'",

        "VEC_CORR": "'NONE'",

        "CSV_FORMAT": "'NO'",

        "TIME_TYPE": "'TDB'",

        "TLIST_TYPE": "'JD'",

        "TLIST": f"'{jd_tdb:.12f}'",

    }

    url = (

        HORIZONS_API

        + "?"

        + urlencode(params)

    )

    request = Request(

        url,

        headers={

            "User-Agent":

                "Star-Almanack-Sun-Frame-Lineup-Diagnostic/3.0"

        },

    )

    with urlopen(

        request,

        timeout=30,

    ) as response:

        raw = response.read().decode(

            "utf-8"

        )

    payload = json.loads(

        raw

    )

    if "result" not in payload:

        raise RuntimeError(

            "Horizons response did not contain a result field"

        )

    return payload["result"]

def parse_horizons_vector(

    text: str,

) -> eclipse_engine.Vec3:

    """Extract X, Y, Z from the Horizons vector ephemeris block."""

    if "$$SOE" not in text or "$$EOE" not in text:

        raise RuntimeError(

            "Horizons result did not contain an ephemeris data block"

        )

    block = (

        text

        .split(

            "$$SOE",

            1,

        )[1]

        .split(

            "$$EOE",

            1,

        )[0]

    )

    pattern = re.compile(

        r"X\s*=\s*"

        r"([+-]?\d+(?:\.\d*)?(?:[Ee][+-]?\d+)?)"

        r"\s+Y\s*=\s*"

        r"([+-]?\d+(?:\.\d*)?(?:[Ee][+-]?\d+)?)"

        r"\s+Z\s*=\s*"

        r"([+-]?\d+(?:\.\d*)?(?:[Ee][+-]?\d+)?)"

    )

    match = pattern.search(

        block

    )

    if match is None:

        raise RuntimeError(

            "Could not parse X/Y/Z from Horizons vector output"

        )

    return eclipse_engine.Vec3(

        float(match.group(1)),

        float(match.group(2)),

        float(match.group(3)),

    )

# ---------------------------------------------------------------------------

# One prosecution-lineup case

# ---------------------------------------------------------------------------

def run_case(

    label: str,

    civil_text: str,

) -> dict[str, float]:

    """Run one complete model / frame / production comparison."""

    (

        jd_civil,

        jd_tdb,

    ) = production_tdb_jd(

        civil_text

    )

    raw_compact = compact_sun_ecliptic_of_date(

        jd_tdb

    )

    production = eclipse_engine.sun_vector_j2000(

        jd_tdb

    )

    erfa_transformed = erfa_ecliptic_date_to_j2000(

        raw_compact,

        jd_tdb,

    )

    horizons_text = horizons_request(

        jd_tdb

    )

    jpl_j2000 = parse_horizons_vector(

        horizons_text

    )

    jpl_date = erfa_ecliptic_j2000_to_date(

        jpl_j2000,

        jd_tdb,

    )

    raw_lon = vector_longitude_deg(

        raw_compact

    )

    jpl_date_lon = vector_longitude_deg(

        jpl_date

    )

    production_lon = vector_longitude_deg(

        production

    )

    erfa_lon = vector_longitude_deg(

        erfa_transformed

    )

    jpl_j2000_lon = vector_longitude_deg(

        jpl_j2000

    )

    # ------------------------------------------------------------------

    # Principal longitude evidence

    # ------------------------------------------------------------------

    model_only_residual = wrap_signed_deg(

        raw_lon

        - jpl_date_lon

    )

    frame_disagreement = wrap_signed_deg(

        production_lon

        - erfa_lon

    )

    production_residual = wrap_signed_deg(

        production_lon

        - jpl_j2000_lon

    )

    erfa_combined_residual = wrap_signed_deg(

        erfa_lon

        - jpl_j2000_lon

    )

    # ------------------------------------------------------------------

    # Signed frame shifts

    # ------------------------------------------------------------------

    production_frame_shift = wrap_signed_deg(

        production_lon

        - raw_lon

    )

    erfa_frame_shift = wrap_signed_deg(

        erfa_lon

        - raw_lon

    )

    signed_shift_ratio = safe_ratio(

        production_frame_shift,

        erfa_frame_shift,

    )

    longitude_shift_magnitude_ratio = safe_ratio(

        abs(production_frame_shift),

        abs(erfa_frame_shift),

    )

    # ------------------------------------------------------------------

    # Three-dimensional angular evidence

    # ------------------------------------------------------------------

    model_angular_error = angle_between_deg(

        raw_compact,

        jpl_date,

    )

    frame_angular_disagreement = angle_between_deg(

        production,

        erfa_transformed,

    )

    production_angular_error = angle_between_deg(

        production,

        jpl_j2000,

    )

    erfa_angular_error = angle_between_deg(

        erfa_transformed,

        jpl_j2000,

    )

    production_frame_angular_shift = angle_between_deg(

        raw_compact,

        production,

    )

    erfa_frame_angular_shift = angle_between_deg(

        raw_compact,

        erfa_transformed,

    )

    frame_magnitude_ratio = safe_ratio(

        production_frame_angular_shift,

        erfa_frame_angular_shift,

    )

    frame_magnitude_target_delta = (

        frame_magnitude_ratio

        - MAGNITUDE_TARGET

        if math.isfinite(frame_magnitude_ratio)

        else float("nan")

    )

    # ------------------------------------------------------------------

    # Full basis-vector / rotation-matrix evidence

    # ------------------------------------------------------------------

    production_matrix = frame_matrix(

        production_ecliptic_date_to_j2000,

        jd_tdb,

    )

    erfa_matrix = frame_matrix(

        erfa_ecliptic_date_to_j2000,

        jd_tdb,

    )

    relative_matrix = (

        production_matrix

        @ erfa_matrix.T

    )

    production_rotation_vector = rotation_vector_deg(

        production_matrix

    )

    erfa_rotation_vector = rotation_vector_deg(

        erfa_matrix

    )

    production_rotation_magnitude = rotation_vector_magnitude(

        production_rotation_vector

    )

    erfa_rotation_magnitude = rotation_vector_magnitude(

        erfa_rotation_vector

    )

    matrix_magnitude_ratio = safe_ratio(

        production_rotation_magnitude,

        erfa_rotation_magnitude,

    )

    axis_cosine = rotation_axis_cosine(

        production_rotation_vector,

        erfa_rotation_vector,

    )

    relative_rotation_angle = rotation_angle_deg(

        relative_matrix

    )

    matrix_frobenius_difference = float(

        np.linalg.norm(

            production_matrix

            - erfa_matrix,

            ord="fro",

        )

    )

    production_determinant = float(

        np.linalg.det(

            production_matrix

        )

    )

    erfa_determinant = float(

        np.linalg.det(

            erfa_matrix

        )

    )

    production_orthogonality_error = orthogonality_error(

        production_matrix

    )

    erfa_orthogonality_error = orthogonality_error(

        erfa_matrix

    )

    basis_vectors = (

        (

            "X",

            eclipse_engine.Vec3(

                1.0,

                0.0,

                0.0,

            ),

        ),

        (

            "Y",

            eclipse_engine.Vec3(

                0.0,

                1.0,

                0.0,

            ),

        ),

        (

            "Z",

            eclipse_engine.Vec3(

                0.0,

                0.0,

                1.0,

            ),

        ),

    )

    basis_disagreements: dict[str, float] = {}

    for basis_name, basis_vector in basis_vectors:

        production_basis = production_ecliptic_date_to_j2000(

            basis_vector,

            jd_tdb,

        )

        erfa_basis = erfa_ecliptic_date_to_j2000(

            basis_vector,

            jd_tdb,

        )

        basis_disagreements[basis_name] = angle_between_deg(

            production_basis,

            erfa_basis,

        )

    # ------------------------------------------------------------------

    # Direct rectangular vector differences

    # ------------------------------------------------------------------

    raw_minus_jpl_date_km = vector_difference_km(

        raw_compact,

        jpl_date,

    )

    production_minus_jpl_km = vector_difference_km(

        production,

        jpl_j2000,

    )

    erfa_minus_jpl_km = vector_difference_km(

        erfa_transformed,

        jpl_j2000,

    )

    production_minus_erfa_km = vector_difference_km(

        production,

        erfa_transformed,

    )

    adopted_offset_seconds = (

        jd_tdb

        - jd_civil

    ) * 86400.0

    # ------------------------------------------------------------------

    # Report

    # ------------------------------------------------------------------

    print()

    print("=" * 78)

    print(label)

    print("=" * 78)

    print(

        f"  reference civil epoch:      "

        f"{civil_text}"

    )

    print(

        f"  JD civil input:             "

        f"{jd_civil:.12f}"

    )

    print(

        f"  production dynamical JD:    "

        f"{jd_tdb:.12f}"

    )

    print(

        f"  adopted time offset:        "

        f"{adopted_offset_seconds:+.6f} s"

    )

    print()

    print("  VECTORS")

    print_vector(

        "RAW compact/date:",

        raw_compact,

    )

    print_vector(

        "JPL/date via ERFA:",

        jpl_date,

    )

    print_vector(

        "PRODUCTION/J2000:",

        production,

    )

    print_vector(

        "ERFA/J2000:",

        erfa_transformed,

    )

    print_vector(

        "JPL/J2000:",

        jpl_j2000,

    )

    print()

    print("  LONGITUDES")

    print(

        f"  RAW compact/date:           "

        f"{raw_lon:.9f} deg"

    )

    print(

        f"  JPL/date via ERFA:          "

        f"{jpl_date_lon:.9f} deg"

    )

    print(

        f"  PRODUCTION/J2000:           "

        f"{production_lon:.9f} deg"

    )

    print(

        f"  ERFA/J2000:                 "

        f"{erfa_lon:.9f} deg"

    )

    print(

        f"  JPL/J2000:                  "

        f"{jpl_j2000_lon:.9f} deg"

    )

    print()

    print("  PROSECUTION EVIDENCE")

    print(

        f"  MODEL-ONLY residual:        "

        f"{model_only_residual:+.9f} deg"

    )

    print(

        f"  FRAME disagreement:         "

        f"{frame_disagreement:+.9f} deg"

    )

    print(

        f"  PRODUCTION residual:        "

        f"{production_residual:+.9f} deg"

    )

    print(

        f"  ERFA combined residual:     "

        f"{erfa_combined_residual:+.9f} deg"

    )

    print()

    print("  DIRECT VECTOR DIFFERENCES")

    print()

    print_difference(

        "RAW - JPL/date:",

        raw_compact,

        jpl_date,

    )

    print()

    print_difference(

        "PRODUCTION - JPL:",

        production,

        jpl_j2000,

    )

    print()

    print_difference(

        "ERFA - JPL:",

        erfa_transformed,

        jpl_j2000,

    )

    print()

    print_difference(

        "PRODUCTION - ERFA:",

        production,

        erfa_transformed,

    )

    print()

    print("  FRAME SHIFTS")

    print(

        f"  production longitude shift: "

        f"{production_frame_shift:+.9f} deg"

    )

    print(

        f"  ERFA longitude shift:       "

        f"{erfa_frame_shift:+.9f} deg"

    )

    print(

        f"  shift disagreement:         "

        f"{frame_disagreement:+.9f} deg"

    )

    if math.isfinite(

        signed_shift_ratio

    ):

        print(

            f"  signed shift ratio P/E:     "

            f"{signed_shift_ratio:+.9f}"

        )

    else:

        print(

            "  signed shift ratio P/E:     "

            "undefined at zero frame shift"

        )

    if math.isfinite(

        longitude_shift_magnitude_ratio

    ):

        print(

            f"  |longitude shift| P/E:      "

            f"{longitude_shift_magnitude_ratio:.9f}"

        )

    else:

        print(

            "  |longitude shift| P/E:      "

            "undefined at zero frame shift"

        )

    print()

    print("  THREE-DIMENSIONAL CHECKS")

    print(

        f"  model-only angular error:   "

        f"{model_angular_error:.9f} deg"

    )

    print(

        f"  frame angular disagreement: "

        f"{frame_angular_disagreement:.9f} deg"

    )

    print(

        f"  production angular error:   "

        f"{production_angular_error:.9f} deg"

    )

    print(

        f"  ERFA angular error:         "

        f"{erfa_angular_error:.9f} deg"

    )

    print()

    print("  FRAME MAGNITUDE TEST")

    print(

        f"  production angular shift:   "

        f"{production_frame_angular_shift:.9f} deg"

    )

    print(

        f"  ERFA angular shift:         "

        f"{erfa_frame_angular_shift:.9f} deg"

    )

    if math.isfinite(

        frame_magnitude_ratio

    ):

        print(

            f"  production / ERFA magnitude:"

            f" {frame_magnitude_ratio:.9f}"

        )

        print(

            f"  magnitude target:           "

            f"{MAGNITUDE_TARGET:.4f}"

        )

        print(

            f"  ratio - target:             "

            f"{frame_magnitude_target_delta:+.9f}"

        )

        print(

            f"  ratio - unity:              "

            f"{frame_magnitude_ratio - 1.0:+.9f}"

        )

    else:

        print(

            "  production / ERFA magnitude:"

            " undefined at zero frame shift"

        )

        print(

            f"  magnitude target:           "

            f"{MAGNITUDE_TARGET:.4f}"

        )

    print()

    print("  FULL 3-D FRAME MATRIX TEST")

    print(

        f"  X basis disagreement:       "

        f"{basis_disagreements['X']:.9f} deg"

    )

    print(

        f"  Y basis disagreement:       "

        f"{basis_disagreements['Y']:.9f} deg"

    )

    print(

        f"  Z basis disagreement:       "

        f"{basis_disagreements['Z']:.9f} deg"

    )

    print()

    print(

        f"  production rotation:        "

        f"{production_rotation_magnitude:.9f} deg"

    )

    print(

        f"  ERFA rotation:              "

        f"{erfa_rotation_magnitude:.9f} deg"

    )

    if math.isfinite(

        matrix_magnitude_ratio

    ):

        print(

            f"  matrix magnitude P/E:       "

            f"{matrix_magnitude_ratio:.9f}"

        )

        print(

            f"  matrix ratio - unity:       "

            f"{matrix_magnitude_ratio - 1.0:+.9f}"

        )

    else:

        print(

            "  matrix magnitude P/E:       "

            "undefined at zero rotation"

        )

    if math.isfinite(

        axis_cosine

    ):

        print(

            f"  rotation-axis cosine:       "

            f"{axis_cosine:+.9f}"

        )

    else:

        print(

            "  rotation-axis cosine:       "

            "undefined at zero rotation"

        )

    print(

        f"  P relative to ERFA rotation:"

        f" {relative_rotation_angle:.9f} deg"

    )

    print(

        f"  matrix Frobenius difference:"

        f" {matrix_frobenius_difference:.12e}"

    )

    print()

    print(

        f"  production determinant:     "

        f"{production_determinant:.12f}"

    )

    print(

        f"  ERFA determinant:           "

        f"{erfa_determinant:.12f}"

    )

    print(

        f"  production orthogonality:   "

        f"{production_orthogonality_error:.12e}"

    )

    print(

        f"  ERFA orthogonality:         "

        f"{erfa_orthogonality_error:.12e}"

    )

    return {

        "model_only_residual_deg":

            model_only_residual,

        "frame_disagreement_deg":

            frame_disagreement,

        "production_residual_deg":

            production_residual,

        "erfa_combined_residual_deg":

            erfa_combined_residual,

        "production_frame_shift_deg":

            production_frame_shift,

        "erfa_frame_shift_deg":

            erfa_frame_shift,

        "signed_shift_ratio":

            signed_shift_ratio,

        "longitude_shift_magnitude_ratio":

            longitude_shift_magnitude_ratio,

        "model_angular_error_deg":

            model_angular_error,

        "frame_angular_disagreement_deg":

            frame_angular_disagreement,

        "production_angular_error_deg":

            production_angular_error,

        "erfa_angular_error_deg":

            erfa_angular_error,

        "production_frame_angular_shift_deg":

            production_frame_angular_shift,

        "erfa_frame_angular_shift_deg":

            erfa_frame_angular_shift,

        "frame_magnitude_ratio":

            frame_magnitude_ratio,

        "frame_magnitude_target_delta":

            frame_magnitude_target_delta,

        "basis_x_disagreement_deg":

            basis_disagreements["X"],

        "basis_y_disagreement_deg":

            basis_disagreements["Y"],

        "basis_z_disagreement_deg":

            basis_disagreements["Z"],

        "production_matrix_rotation_deg":

            production_rotation_magnitude,

        "erfa_matrix_rotation_deg":

            erfa_rotation_magnitude,

        "matrix_magnitude_ratio":

            matrix_magnitude_ratio,

        "rotation_axis_cosine":

            axis_cosine,

        "relative_matrix_rotation_deg":

            relative_rotation_angle,

        "matrix_frobenius_difference":

            matrix_frobenius_difference,

        "production_matrix_determinant":

            production_determinant,

        "erfa_matrix_determinant":

            erfa_determinant,

        "production_orthogonality_error":

            production_orthogonality_error,

        "erfa_orthogonality_error":

            erfa_orthogonality_error,

        "raw_minus_jpl_date_km":

            raw_minus_jpl_date_km,

        "production_minus_jpl_km":

            production_minus_jpl_km,

        "erfa_minus_jpl_km":

            erfa_minus_jpl_km,

        "production_minus_erfa_km":

            production_minus_erfa_km,

    }

# ---------------------------------------------------------------------------

# Summary helpers

# ---------------------------------------------------------------------------

def mean(

    values: list[float],

) -> float:

    """Arithmetic mean."""

    usable = finite_values(

        values

    )

    if not usable:

        return float("nan")

    return sum(usable) / len(usable)

def mean_abs(

    values: list[float],

) -> float:

    """Mean absolute value."""

    usable = finite_values(

        values

    )

    if not usable:

        return float("nan")

    return (

        sum(

            abs(value)

            for value in usable

        )

        / len(usable)

    )

def print_summary(

    results: list[

        tuple[

            str,

            dict[str, float],

        ]

    ],

) -> None:

    """Print compact cross-epoch prosecution summary."""

    print()

    print()

    print("=" * 78)

    print("PROSECUTION SUMMARY")

    print("=" * 78)

    print()

    print(

        f"{'epoch':<18}"

        f"{'model-only':>16}"

        f"{'frame':>16}"

        f"{'production':>16}"

    )

    print(

        f"{'':<18}"

        f"{'(deg)':>16}"

        f"{'(deg)':>16}"

        f"{'(deg)':>16}"

    )

    print("-" * 66)

    for label, result in results:

        print(

            f"{label:<18}"

            f"{result['model_only_residual_deg']:>+16.9f}"

            f"{result['frame_disagreement_deg']:>+16.9f}"

            f"{result['production_residual_deg']:>+16.9f}"

        )

    model_values = [

        result["model_only_residual_deg"]

        for _, result in results

    ]

    frame_values = [

        result["frame_disagreement_deg"]

        for _, result in results

    ]

    production_values = [

        result["production_residual_deg"]

        for _, result in results

    ]

    magnitude_ratios = [

        result["frame_magnitude_ratio"]

        for _, result in results

        if math.isfinite(

            result["frame_magnitude_ratio"]

        )

    ]

    signed_ratios = [

        result["signed_shift_ratio"]

        for _, result in results

        if math.isfinite(

            result["signed_shift_ratio"]

        )

    ]

    matrix_ratios = [

        result["matrix_magnitude_ratio"]

        for _, result in results

        if math.isfinite(

            result["matrix_magnitude_ratio"]

        )

    ]

    relative_rotations = [

        result["relative_matrix_rotation_deg"]

        for _, result in results

    ]

    axis_cosines = [

        result["rotation_axis_cosine"]

        for _, result in results

        if math.isfinite(

            result["rotation_axis_cosine"]

        )

    ]

    raw_jpl_km = [

        result["raw_minus_jpl_date_km"]

        for _, result in results

    ]

    production_jpl_km = [

        result["production_minus_jpl_km"]

        for _, result in results

    ]

    erfa_jpl_km = [

        result["erfa_minus_jpl_km"]

        for _, result in results

    ]

    production_erfa_km = [

        result["production_minus_erfa_km"]

        for _, result in results

    ]

    print()

    print("ALL-EPOCH STATISTICS")

    print(

        f"  mean model-only residual:       "

        f"{mean(model_values):+.9f} deg"

    )

    print(

        f"  mean |model-only residual|:     "

        f"{mean_abs(model_values):.9f} deg"

    )

    print(

        f"  mean frame disagreement:        "

        f"{mean(frame_values):+.9f} deg"

    )

    print(

        f"  mean |frame disagreement|:      "

        f"{mean_abs(frame_values):.9f} deg"

    )

    print(

        f"  mean production residual:       "

        f"{mean(production_values):+.9f} deg"

    )

    print(

        f"  mean |production residual|:     "

        f"{mean_abs(production_values):.9f} deg"

    )

    print()

    print("DIRECT VECTOR DIFFERENCE STATISTICS")

    print(

        f"  mean RAW - JPL/date:            "

        f"{mean(raw_jpl_km):.3f} km"

    )

    print(

        f"  mean PRODUCTION - JPL:          "

        f"{mean(production_jpl_km):.3f} km"

    )

    print(

        f"  mean ERFA - JPL:                "

        f"{mean(erfa_jpl_km):.3f} km"

    )

    print(

        f"  mean PRODUCTION - ERFA:         "

        f"{mean(production_erfa_km):.3f} km"

    )

    print()

    print("SUN-VECTOR FRAME MAGNITUDE SUMMARY")

    if magnitude_ratios:

        mean_magnitude_ratio = mean(

            magnitude_ratios

        )

        print(

            f"  mean production / ERFA:         "

            f"{mean_magnitude_ratio:.9f}"

        )

        print(

            f"  unity expectation:              "

            f"{1.0:.4f}"

        )

        print(

            f"  registered magnitude target:    "

            f"{MAGNITUDE_TARGET:.4f}"

        )

        print(

            f"  mean ratio - unity:             "

            f"{mean_magnitude_ratio - 1.0:+.9f}"

        )

        print(

            f"  mean ratio - target:            "

            f"{mean_magnitude_ratio - MAGNITUDE_TARGET:+.9f}"

        )

    else:

        print(

            "  no nonzero frame epochs available"

        )

    if signed_ratios:

        mean_signed_ratio = mean(

            signed_ratios

        )

        print(

            f"  mean signed longitude P/E:      "

            f"{mean_signed_ratio:+.9f}"

        )

        if mean_signed_ratio < 0.0:

            print(

                "  direction clue:                 "

                "PRODUCTION AND ERFA HAVE OPPOSITE SIGNS"

            )

        else:

            print(

                "  direction clue:                 "

                "production and ERFA shifts have same sign"

            )

    print()

    print("FULL 3-D FRAME MATRIX SUMMARY")

    if matrix_ratios:

        mean_matrix_ratio = mean(

            matrix_ratios

        )

        print(

            f"  mean matrix magnitude P/E:      "

            f"{mean_matrix_ratio:.9f}"

        )

        print(

            f"  mean matrix ratio - unity:      "

            f"{mean_matrix_ratio - 1.0:+.9f}"

        )

    else:

        print(

            "  matrix magnitude ratio undefined"

        )

    print(

        f"  mean P-relative-ERFA rotation:  "

        f"{mean(relative_rotations):.9f} deg"

    )

    print(

        f"  max P-relative-ERFA rotation:   "

        f"{max(finite_values(relative_rotations)):.9f} deg"

    )

    if axis_cosines:

        print(

            f"  mean rotation-axis cosine:      "

            f"{mean(axis_cosines):+.9f}"

        )

    print()

    print(

        "  basis disagreement means:"

    )

    print(

        "      0 deg      -> transformations agree on that axis"

    )

    print(

        "      large      -> transformations genuinely disagree"

    )

    print(

        "  rotation-axis cosine means:"

    )

    print(

        "      +1         -> same rotation-axis direction"

    )

    print(

        "      -1         -> opposite rotation-axis direction"

    )

    print()

    before = [

        result

        for label, result in results

        if label in {

            "1919 eclipse",

            "1963 eclipse",

            "1991 eclipse",

        }

    ]

    after = [

        result

        for label, result in results

        if label in {

            "2017 eclipse",

            "2024 eclipse",

        }

    ]

    print("BEFORE / AFTER J2000")

    if before:

        print(

            f"  model mean before J2000:        "

            f"{mean([r['model_only_residual_deg'] for r in before]):+.9f} deg"

        )

        print(

            f"  frame mean before J2000:        "

            f"{mean([r['frame_disagreement_deg'] for r in before]):+.9f} deg"

        )

        print(

            f"  production mean before J2000:   "

            f"{mean([r['production_residual_deg'] for r in before]):+.9f} deg"

        )

        print(

            f"  Sun-vector ratio before J2000:  "

            f"{mean([r['frame_magnitude_ratio'] for r in before]):.9f}"

        )

        print(

            f"  matrix ratio before J2000:      "

            f"{mean([r['matrix_magnitude_ratio'] for r in before]):.9f}"

        )

        print(

            f"  relative rotation before J2000: "

            f"{mean([r['relative_matrix_rotation_deg'] for r in before]):.9f} deg"

        )

    if after:

        print(

            f"  model mean after J2000:         "

            f"{mean([r['model_only_residual_deg'] for r in after]):+.9f} deg"

        )

        print(

            f"  frame mean after J2000:         "

            f"{mean([r['frame_disagreement_deg'] for r in after]):+.9f} deg"

        )

        print(

            f"  production mean after J2000:    "

            f"{mean([r['production_residual_deg'] for r in after]):+.9f} deg"

        )

        print(

            f"  Sun-vector ratio after J2000:   "

            f"{mean([r['frame_magnitude_ratio'] for r in after]):.9f}"

        )

        print(

            f"  matrix ratio after J2000:       "

            f"{mean([r['matrix_magnitude_ratio'] for r in after]):.9f}"

        )

        print(

            f"  relative rotation after J2000:  "

            f"{mean([r['relative_matrix_rotation_deg'] for r in after]):.9f} deg"

        )

    print()

    print("INTERPRETATION KEY")

    print()

    print(

        "  MODEL-ONLY residual large"

        "       -> compact solar model contributes error."

    )

    print(

        "  FRAME disagreement large"

        "        -> production frame conversion contributes error."

    )

    print(

        "  Sun-vector magnitude ~= 1"

        "       -> both move this Sun vector by similar amounts."

    )

    print(

        "  matrix magnitude ratio ~= 1"

        "      -> complete rotations have similar magnitudes."

    )

    print(

        "  matrix magnitude ratio != 1"

        "      -> production rotation magnitude is suspect."

    )

    print(

        "  rotation-axis cosine ~= +1"

        "      -> production and ERFA rotate about similar axes."

    )

    print(

        "  rotation-axis cosine ~= -1"

        "      -> rotation directions are opposite."

    )

    print(

        "  relative matrix rotation large"

        "    -> complete production transformation is implicated."

    )

    print(

        "  ERFA much closer to JPL"

        "              -> production transformation is implicated."

    )

    print(

        "  ERFA and production both poor"

        "       -> compact model/frame assumption remains implicated."

    )

    print(

        "  residual remains after both"

        "         -> continue searching for another culprit."

    )

# ---------------------------------------------------------------------------

# Main

# ---------------------------------------------------------------------------

def main() -> int:

    """Run the complete prosecution lineup."""

    print(

        "STAR ALMANACK SUN / FRAME PROSECUTION LINEUP"

    )

    print(

        "=" * 78

    )

    print()

    print(

        "Independent authorities:"

    )

    print(

        "  solar position: JPL Horizons"

    )

    print(

        "  frame conversion: ERFA / IAU 2006"

    )

    print()

    print(

        "Registered frame-magnitude investigative target:"

    )

    print(

        f"  {MAGNITUDE_TARGET:.4f}"

    )

    print()

    print(

        "This diagnostic does NOT modify production eclipse geometry."

    )

    results: list[

        tuple[

            str,

            dict[str, float],

        ]

    ] = []

    try:

        for label, civil_text in TEST_EPOCHS:

            result = run_case(

                label,

                civil_text,

            )

            results.append(

                (

                    label,

                    result,

                )

            )

    except Exception as exc:

        print()

        print("=" * 78)

        print(

            "SUN / FRAME LINEUP SKIPPED / UNAVAILABLE"

        )

        print("=" * 78)

        print(

            f"{type(exc).__name__}: {exc}"

        )

        print()

        print(

            "This diagnostic depends on PyERFA and live JPL Horizons access."

        )

        print(

            "Diagnostic unavailability does not constitute a Star Almanack"

        )

        print(

            "validation failure."

        )

        return 0

    print_summary(

        results

    )

    print()

    print(

        "SUN / FRAME PROSECUTION LINEUP COMPLETE"

    )

    return 0

if __name__ == "__main__":

    raise SystemExit(

        main()

    )