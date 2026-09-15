#!/usr/bin/env python3

"""

Star Almanack — compact-Sun versus JPL Horizons diagnostic.

Purpose

-------

Compare the Star Almanack compact solar model with an independent,

high-precision JPL Horizons solar ephemeris.

This program is DIAGNOSTIC ONLY.

It does not modify the eclipse calculation, does not supply data to

eclipse_engine.py, and does not affect the Star Almanack validation

PASS/FAIL result.

Why this diagnostic exists

--------------------------

The Star Almanack eclipse engine currently computes the Sun with a compact

low-precision solar model and transforms the resulting vector into the

mean J2000 ecliptic frame used by the ELP2000-82B lunar evaluator.

Eclipse validation has revealed an epoch-dependent timing residual:

    before J2000:

        calculated greatest-eclipse times tend to be early

    after J2000:

        calculated greatest-eclipse times tend to be late

A transformed-versus-raw Sun experiment showed that bypassing the Sun

frame transformation reduces the timing residual substantially. However,

that experiment deliberately mixes coordinate frames and therefore cannot

by itself establish that the transformation is wrong.

The next independent question is:

    How accurately does the compact Sun model itself reproduce the

    geocentric Sun position given by JPL Horizons?

This diagnostic answers that question directly.

Reference geometry

------------------

JPL Horizons is asked for a geometric geocentric Sun vector:

    target:

        Sun

    center:

        Earth center

    reference system:

        ICRF / J2000

    reference plane:

        ecliptic

    time scale:

        TDB

The resulting vector can therefore be compared directly with

eclipse_engine.sun_vector_j2000() when both are evaluated at the same

dynamical epoch.

Test epochs

-----------

The epochs deliberately span both sides of J2000:

    1919 eclipse era

    1963 eclipse era

    1991 eclipse era

    J2000

    2017 eclipse era

    2024 eclipse era

The eclipse epochs use the same published/reference UT instants stored in

the Star Almanack eclipse validation catalog.

For each case:

1. The reference civil instant is converted to JD by the same calendar

   routine used by the eclipse engine.

2. The production eclipse-engine UTC/UT-like -> TDB approximation is

   called directly.

3. That exact JD(TDB) is used for BOTH:

       Star Almanack compact-Sun evaluation

       JPL Horizons vector request

This prevents the diagnostic from comparing vectors at different physical

instants.

The diagnostic prints:

    Star Almanack vector

    JPL Horizons vector

    signed ecliptic-longitude residual

    total angular separation

    radial-distance residual

The signed longitude residual is:

    Star Almanack longitude - JPL longitude

normalized to the interval:

    -180 degrees through +180 degrees

This sign is especially important because we are looking for an

epoch-dependent error that may reverse direction around J2000.

Network behavior

----------------

Unlike the permanent frozen regression tests, this diagnostic intentionally

contacts JPL Horizons over the network.

A temporary network or Horizons failure must NOT make the Star Almanack

validation fail. Such a failure is reported as SKIPPED / UNAVAILABLE and

the diagnostic exits successfully.

Published/reference data remain validation targets only. The production

eclipse engine never reads JPL Horizons data.

"""

from __future__ import annotations

import json

import math

import re

from urllib.parse import urlencode

from urllib.request import Request, urlopen

import eclipse_engine

HORIZONS_API = "https://ssd.jpl.nasa.gov/api/horizons.api"

# Representative epochs.

#

# Eclipse cases use the same published/reference UT values stored in

# eclipse-validation-cases.yaml.

#

# J2000 is included because the production date-to-J2000 transformation

# should approach zero there.

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

def wrap_signed_deg(angle: float) -> float:

    """

    Normalize an angle to [-180, +180) degrees.

    """

    return (angle + 180.0) % 360.0 - 180.0

def vector_longitude_deg(v: eclipse_engine.Vec3) -> float:

    """

    Ecliptic longitude of a rectangular vector, degrees.

    """

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

    """

    Three-dimensional angular separation between two vectors.

    """

    denom = a.norm() * b.norm()

    if denom == 0.0:

        return float("nan")

    cosine = a.dot(b) / denom

    cosine = max(-1.0, min(1.0, cosine))

    return math.degrees(

        math.acos(cosine)

    )

def iso_z_to_jd(text: str) -> float:

    """

    Convert one reference civil timestamp to Julian Date.

    The calendar-to-JD implementation is deliberately shared with the

    production eclipse engine so the diagnostic does not introduce another

    independent calendar conversion.

    """

    date_part, time_part = text.rstrip("Z").split("T")

    year, month, day = (

        int(part)

        for part in date_part.split("-")

    )

    hour_text, minute_text, second_text = (

        time_part.split(":")

    )

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

    Convert the diagnostic reference instant to the SAME approximate TDB

    argument used by production eclipse geometry.

    Returns:

        jd_civil

        jd_tdb_approx

    The first value retains the engine's current civil-time semantics.

    Before 1972, production treats the civil JD approximately as UT1.

    From 1972 onward, production treats it as UTC and applies TAI-UTC.

    This diagnostic deliberately does not "improve" that behavior. Its job is

    to test the production Sun model at exactly the time argument production

    currently uses.

    """

    jd_civil = iso_z_to_jd(

        civil_text

    )

    jd_tdb_approx = eclipse_engine.utc_to_tdb_approx(

        jd_civil

    )

    return (

        jd_civil,

        jd_tdb_approx,

    )

def horizons_request(

    jd_tdb: float,

) -> str:

    """

    Ask JPL Horizons for one geometric geocentric Sun vector.

    COMMAND 10:

        Sun

    CENTER 500@399:

        Earth center

    EPHEM_TYPE VECTORS:

        geometric Cartesian state vector

    REF_SYSTEM ICRF:

        J2000-compatible inertial reference system

    REF_PLANE ECLIPTIC:

        J2000 ecliptic reference plane

    TIME_TYPE TDB:

        interpret the requested epoch on the TDB time scale

    TLIST_TYPE JD:

        numeric TLIST value is a Julian Date

    TLIST:

        request exactly the same JD(TDB) supplied to the Star Almanack Sun

    VEC_TABLE 2:

        position and velocity vector output

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

            "User-Agent": (

                "Star-Almanack-JPL-Diagnostic/2.0"

            )

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

    """

    Extract X, Y, Z from the Horizons vector block.

    Horizons' human-readable vector output contains a line of the form:

        X = ... Y = ... Z = ...

    Only material between $$SOE and $$EOE is considered, preventing header

    metadata from being mistaken for vector data.

    """

    if "$$SOE" not in text or "$$EOE" not in text:

        raise RuntimeError(

            "Horizons result did not contain an ephemeris data block"

        )

    block = text.split(

        "$$SOE",

        1,

    )[1].split(

        "$$EOE",

        1,

    )[0]

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

def print_vector(

    label: str,

    vector: eclipse_engine.Vec3,

) -> None:

    print(

        f"  {label:<18} "

        f"x={vector.x:+.3f} km  "

        f"y={vector.y:+.3f} km  "

        f"z={vector.z:+.3f} km"

    )

def run_case(

    label: str,

    civil_text: str,

) -> dict[str, float]:

    """

    Run one Star Almanack versus Horizons comparison.

    """

    (

        jd_civil,

        jd_tdb_approx,

    ) = production_tdb_jd(

        civil_text

    )

    star = eclipse_engine.sun_vector_j2000(

        jd_tdb_approx

    )

    horizons_text = horizons_request(

        jd_tdb_approx

    )

    jpl = parse_horizons_vector(

        horizons_text

    )

    star_lon = vector_longitude_deg(

        star

    )

    jpl_lon = vector_longitude_deg(

        jpl

    )

    longitude_residual = wrap_signed_deg(

        star_lon - jpl_lon

    )

    angular_error = angle_between_deg(

        star,

        jpl,

    )

    radial_error = (

        star.norm()

        - jpl.norm()

    )

    adopted_offset_seconds = (

        jd_tdb_approx

        - jd_civil

    ) * 86400.0

    print()

    print(label)

    print(

        f"  reference civil epoch: "

        f"{civil_text}"

    )

    print(

        f"  JD civil input:        "

        f"{jd_civil:.12f}"

    )

    print(

        f"  production JD TDB:     "

        f"{jd_tdb_approx:.12f}"

    )

    print(

        f"  adopted time offset:   "

        f"{adopted_offset_seconds:+.6f} s"

    )

    print(

        "  Horizons time scale:  TDB"

    )

    print_vector(

        "Star Almanack:",

        star,

    )

    print_vector(

        "JPL Horizons:",

        jpl,

    )

    print(

        f"  Star longitude:        "

        f"{star_lon:.9f} deg"

    )

    print(

        f"  JPL longitude:         "

        f"{jpl_lon:.9f} deg"

    )

    print(

        f"  signed longitude "

        f"residual: {longitude_residual:+.9f} deg"

    )

    print(

        f"  angular separation:    "

        f"{angular_error:.9f} deg"

    )

    print(

        f"  radial residual:       "

        f"{radial_error:+.3f} km"

    )

    return {

        "longitude_residual_deg":

            longitude_residual,

        "angular_error_deg":

            angular_error,

        "radial_error_km":

            radial_error,

        "adopted_time_offset_seconds":

            adopted_offset_seconds,

    }

def main() -> int:

    print(

        "=== JPL HORIZONS / COMPACT SUN DIAGNOSTIC ==="

    )

    print()

    print(

        "INFORMATIONAL ONLY — "

        "this diagnostic cannot fail the "

        "Star Almanack validation."

    )

    print()

    print(

        "Both Star Almanack and JPL Horizons "

        "are evaluated at the same JD(TDB)."

    )

    print()

    print(

        "Signed longitude residual = "

        "Star Almanack - JPL Horizons."

    )

    print()

    print(

        "The principal question is whether the "

        "residual changes systematically with epoch."

    )

    results: list[

        tuple[

            str,

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

                    civil_text,

                    result,

                )

            )

    except Exception as exc:

        print()

        print(

            "JPL SUN DIAGNOSTIC: "

            "SKIPPED / UNAVAILABLE"

        )

        print(

            f"  {type(exc).__name__}: {exc}"

        )

        print()

        print(

            "This is an informational network "

            "diagnostic and does not affect PASS/FAIL."

        )

        return 0

    print()

    print(

        "=== SIGNED LONGITUDE RESIDUAL SUMMARY ==="

    )

    for label, civil_text, result in results:

        residual = result[

            "longitude_residual_deg"

        ]

        print(

            f"  {label:<16} "

            f"{civil_text:<21} "

            f"{residual:+.9f} deg"

        )

    before = [

        result["longitude_residual_deg"]

        for label, civil_text, result in results

        if civil_text < "2000-01-01T12:00:00Z"

    ]

    after = [

        result["longitude_residual_deg"]

        for label, civil_text, result in results

        if civil_text > "2000-01-01T12:00:00Z"

    ]

    if before and after:

        mean_before = (

            sum(before)

            / len(before)

        )

        mean_after = (

            sum(after)

            / len(after)

        )

        print()

        print(

            f"  mean before J2000: "

            f"{mean_before:+.9f} deg"

        )

        print(

            f"  mean after J2000:  "

            f"{mean_after:+.9f} deg"

        )

        if (

            mean_before < 0.0

            and mean_after > 0.0

        ) or (

            mean_before > 0.0

            and mean_after < 0.0

        ):

            print()

            print(

                "  OBSERVATION: mean signed Sun "

                "longitude residual reverses sign "

                "across J2000."

            )

        else:

            print()

            print(

                "  OBSERVATION: mean signed Sun "

                "longitude residual does NOT "

                "reverse sign across J2000."

            )

    print()

    print(

        "JPL SUN DIAGNOSTIC: COMPLETE "

        "(informational only)"

    )

    return 0

if __name__ == "__main__":

    raise SystemExit(

        main()

    )