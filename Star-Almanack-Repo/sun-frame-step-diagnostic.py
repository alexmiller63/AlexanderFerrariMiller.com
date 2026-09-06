#!/usr/bin/env python3

"""

Star Almanack — frame-conversion step diagnostic.

Purpose

-------

Instrument the production compact-Sun frame conversion one operation at a

time and compare each operation with an independent ERFA / IAU 2006 reference.

This diagnostic does NOT change eclipse_engine.py and does NOT use a different

solar orbit. Every comparison starts from the same compact solar vector, so a

disagreement here belongs to the frame-conversion path rather than the compact

solar model.

Production chain

----------------

    compact ecliptic-of-date

        -> equatorial-of-date

        -> equatorial J2000

        -> ecliptic J2000

For each epoch this program performs three "same input" prosecutions:

    STEP 1

        Production ecliptic-of-date -> equatorial-of-date

        versus ERFA's equivalent conversion of the exact same input vector.

    STEP 2

        Production equatorial-of-date -> J2000 equatorial

        versus the inverse ERFA IAU 2006 precession-bias matrix, again using

        the exact same input vector.

    STEP 3

        Production equatorial J2000 -> ecliptic J2000

        versus ERFA's J2000 ecliptic matrix, using the exact same input vector.

It also prints the cumulative production-versus-ERFA end-to-end separation.

A large discrepancy appearing for the first time at one step identifies the

operation that introduces the frame error.

"""

from __future__ import annotations

import argparse

import math

import erfa

import eclipse_engine as ee

DEFAULT_DATES = (

    "1919-05-29",

    "1991-07-11",

    "2024-04-08",

)

def mat_vec(m, v: ee.Vec3) -> ee.Vec3:

    """Apply a 3x3 ERFA rotation matrix to a Vec3."""

    return ee.Vec3(

        float(m[0][0] * v.x + m[0][1] * v.y + m[0][2] * v.z),

        float(m[1][0] * v.x + m[1][1] * v.y + m[1][2] * v.z),

        float(m[2][0] * v.x + m[2][1] * v.y + m[2][2] * v.z),

    )

def transpose(m):

    """Transpose a 3x3 ERFA matrix without requiring NumPy in this file."""

    return (

        (m[0][0], m[1][0], m[2][0]),

        (m[0][1], m[1][1], m[2][1]),

        (m[0][2], m[1][2], m[2][2]),

    )

def rot_y(v: ee.Vec3, a: float) -> ee.Vec3:

    """Match the local y-axis rotation used inside eclipse_engine.py."""

    c, s = math.cos(a), math.sin(a)

    return ee.Vec3(

        c * v.x + s * v.z,

        v.y,

        -s * v.x + c * v.z,

    )

def angular_separation_rad(a: ee.Vec3, b: ee.Vec3) -> float:

    """Stable angular separation between two nonzero vectors."""

    ua = a.unit()

    ub = b.unit()

    cross_x = ua.y * ub.z - ua.z * ub.y

    cross_y = ua.z * ub.x - ua.x * ub.z

    cross_z = ua.x * ub.y - ua.y * ub.x

    cross_norm = math.sqrt(

        cross_x * cross_x

        + cross_y * cross_y

        + cross_z * cross_z

    )

    dot = max(-1.0, min(1.0, ua.dot(ub)))

    return math.atan2(cross_norm, dot)

def separation_arcsec(a: ee.Vec3, b: ee.Vec3) -> float:

    return angular_separation_rad(a, b) / ee.ARCSEC

def longitude_deg(v: ee.Vec3) -> float:

    return math.degrees(math.atan2(v.y, v.x)) % 360.0

def latitude_deg(v: ee.Vec3) -> float:

    return math.degrees(

        math.atan2(v.z, math.hypot(v.x, v.y))

    )

def compact_ecliptic_of_date(jd_tdb: float) -> ee.Vec3:

    """

    Reproduce only the raw compact-Sun portion of sun_vector_j2000().

    The returned vector is geocentric ecliptic-of-date, in kilometers.

    """

    d = jd_tdb - 2451543.5

    w = ee._wrap_deg(

        282.9404 + 0.0000470935 * d

    ) * ee.DEG

    e = 0.016709 - 0.000000001151 * d

    M = ee._wrap_deg(

        356.0470 + 0.9856002585 * d

    ) * ee.DEG

    E = M

    for _ in range(12):

        f = E - e * math.sin(E) - M

        fp = 1.0 - e * math.cos(E)

        step = f / fp

        E -= step

        if abs(step) < 1e-14:

            break

    x = math.cos(E) - e

    y = (

        math.sqrt(1.0 - e * e)

        * math.sin(E)

    )

    r_au = math.hypot(x, y)

    true_anom = math.atan2(y, x)

    lon = true_anom + w

    return ee.Vec3(

        r_au * math.cos(lon),

        r_au * math.sin(lon),

        0.0,

    ) * ee.AU_KM

def production_precession_steps(

    eq_date: ee.Vec3,

    jd_tdb: float,

):

    """

    Reproduce eclipse_engine._precess_equatorial_date_to_j2000(),

    exposing every intermediate rotation.

    """

    t = (

        (jd_tdb - 2451545.0)

        / 36525.0

    )

    zeta = (

        2306.2181 * t

        + 0.30188 * t * t

        + 0.017998 * t**3

    ) * ee.ARCSEC

    z = (

        2306.2181 * t

        + 1.09468 * t * t

        + 0.018203 * t**3

    ) * ee.ARCSEC

    theta = (

        2004.3109 * t

        - 0.42665 * t * t

        - 0.041833 * t**3

    ) * ee.ARCSEC

    after_z = ee._rot_z(

        eq_date,

        -z,

    )

    after_y = rot_y(

        after_z,

        theta,

    )

    after_zeta = ee._rot_z(

        after_y,

        -zeta,

    )

    return (

        after_z,

        after_y,

        after_zeta,

        zeta,

        z,

        theta,

    )

def format_sep(arcsec: float) -> str:

    return (

        f"{arcsec:12.6f} arcsec  "

        f"({arcsec / 3600.0:+.9f} deg)"

    )

def print_vector(

    label: str,

    v: ee.Vec3,

) -> None:

    print(

        f"{label:<26}"

        f" lon={longitude_deg(v):12.8f} deg"

        f"  lat={latitude_deg(v):+12.8f} deg"

        f"  r={v.norm():15.3f} km"

    )

def diagnose_date(

    date_utc: str,

    threshold_arcsec: float,

) -> None:

    year, month, day = (

        int(x)

        for x in date_utc.split("-")

    )

    jd_utc = ee.gregorian_to_jd(

        year,

        month,

        day,

        0.0,

    )

    jd_tdb = ee.utc_to_tdb_approx(

        jd_utc

    )

    raw = compact_ecliptic_of_date(

        jd_tdb

    )

    # -------------------------------------------------

    # Production frame-conversion chain, fully exposed.

    # -------------------------------------------------

    eps_date = ee._mean_obliquity_rad(

        jd_tdb

    )

    prod_eq_date = ee._rot_x(

        raw,

        eps_date,

    )

    (

        prod_after_z,

        prod_after_y,

        prod_eq_j2000,

        zeta,

        z,

        theta,

    ) = production_precession_steps(

        prod_eq_date,

        jd_tdb,

    )

    eps_j2000 = ee._mean_obliquity_rad(

        2451545.0

    )

    prod_ecl_j2000 = ee._rot_x(

        prod_eq_j2000,

        -eps_j2000,

    )

    # Verify that exposing the individual production

    # operations did not alter the production result.

    production_function = (

        ee.sun_vector_j2000(

            jd_tdb

        )

    )

    reconstruction_sep = (

        separation_arcsec(

            prod_ecl_j2000,

            production_function,

        )

    )

    # ---------------------------------

    # Independent ERFA / IAU reference.

    # ---------------------------------

    #

    # erfa.ecm06:

    #     GCRS/ICRS equatorial

    #       ->

    #     mean ecliptic/equinox of date

    #

    # Therefore transpose(ecm06) gives:

    #

    #     ecliptic-of-date

    #       ->

    #     GCRS/ICRS

    #

    # erfa.pmat06:

    #

    #     GCRS

    #       ->

    #     mean equator/equinox of date

    #

    ecm_date = erfa.ecm06(

        jd_tdb,

        0.0,

    )

    pmat_date = erfa.pmat06(

        jd_tdb,

        0.0,

    )

    ecm_j2000 = erfa.ecm06(

        2451545.0,

        0.0,

    )

    # STEP 1 reference:

    #

    # ecliptic-of-date

    #     -> GCRS

    #     -> mean equatorial-of-date

    erfa_gcrs_from_raw = mat_vec(

        transpose(ecm_date),

        raw,

    )

    erfa_eq_date_same_input = mat_vec(

        pmat_date,

        erfa_gcrs_from_raw,

    )

    # STEP 2 reference:

    #

    # Use the production eq-date vector as the

    # identical input to both transformations.

    #

    # mean equatorial-of-date

    #     -> GCRS

    erfa_eq_j2000_same_input = mat_vec(

        transpose(pmat_date),

        prod_eq_date,

    )

    # STEP 3 reference:

    #

    # Use the production J2000-equatorial vector

    # as the identical input.

    #

    # GCRS/J2000 equatorial

    #     -> J2000 ecliptic

    erfa_ecl_j2000_same_input = mat_vec(

        ecm_j2000,

        prod_eq_j2000,

    )

    # Pure ERFA end-to-end conversion:

    #

    # raw ecliptic-of-date

    #     -> GCRS

    #     -> J2000 ecliptic

    erfa_ecl_j2000_end_to_end = mat_vec(

        ecm_j2000,

        erfa_gcrs_from_raw,

    )

    step1 = separation_arcsec(

        prod_eq_date,

        erfa_eq_date_same_input,

    )

    step2 = separation_arcsec(

        prod_eq_j2000,

        erfa_eq_j2000_same_input,

    )

    step3 = separation_arcsec(

        prod_ecl_j2000,

        erfa_ecl_j2000_same_input,

    )

    end_to_end = separation_arcsec(

        prod_ecl_j2000,

        erfa_ecl_j2000_end_to_end,

    )

    print()

    print("=" * 88)

    print(

        f"DATE: {date_utc}"

    )

    print(

        f"JD UTC: {jd_utc:.9f}"

    )

    print(

        f"JD TT/TDB approx: "

        f"{jd_tdb:.9f}"

    )

    print("=" * 88)

    print()

    print(

        "RAW COMPACT SUN"

    )

    print_vector(

        "ecliptic of date",

        raw,

    )

    print()

    print(

        "PRODUCTION PRECESSION ANGLES"

    )

    print(

        f"zeta  = "

        f"{zeta / ee.ARCSEC:+.9f} arcsec"

    )

    print(

        f"z     = "

        f"{z / ee.ARCSEC:+.9f} arcsec"

    )

    print(

        f"theta = "

        f"{theta / ee.ARCSEC:+.9f} arcsec"

    )

    print(

        f"eps(date)  = "

        f"{math.degrees(eps_date):+.9f} deg"

    )

    print(

        f"eps(J2000) = "

        f"{math.degrees(eps_j2000):+.9f} deg"

    )

    print()

    print(

        "PRODUCTION INTERMEDIATES"

    )

    print_vector(

        "after ecl->eq date",

        prod_eq_date,

    )

    print_vector(

        "after Rz(-z)",

        prod_after_z,

    )

    print_vector(

        "after Ry(theta)",

        prod_after_y,

    )

    print_vector(

        "after Rz(-zeta)",

        prod_eq_j2000,

    )

    print_vector(

        "final ecl J2000",

        prod_ecl_j2000,

    )

    print()

    print(

        "SAME-INPUT STEP PROSECUTION"

    )

    print(

        "STEP 1  ecl-date -> eq-date:       "

        f"{format_sep(step1)}"

    )

    print(

        "STEP 2  eq-date  -> eq-J2000:      "

        f"{format_sep(step2)}"

    )

    print(

        "STEP 3  eq-J2000 -> ecl-J2000:     "

        f"{format_sep(step3)}"

    )

    print(

        "END TO END production vs ERFA:     "

        f"{format_sep(end_to_end)}"

    )

    print(

        "RECONSTRUCTION vs production fn:   "

        f"{format_sep(reconstruction_sep)}"

    )

    print()

    print(

        "ERFA REFERENCE VECTORS"

    )

    print_vector(

        "ERFA eq of date",

        erfa_eq_date_same_input,

    )

    print_vector(

        "ERFA GCRS/J2000",

        erfa_gcrs_from_raw,

    )

    print_vector(

        "ERFA ecl J2000",

        erfa_ecl_j2000_end_to_end,

    )

    first = None

    for (

        number,

        value,

        description,

    ) in (

        (

            1,

            step1,

            "ecliptic-of-date -> "

            "equatorial-of-date",

        ),

        (

            2,

            step2,

            "equatorial-of-date -> "

            "equatorial J2000",

        ),

        (

            3,

            step3,

            "equatorial J2000 -> "

            "ecliptic J2000",

        ),

    ):

        if value > threshold_arcsec:

            first = (

                number,

                value,

                description,

            )

            break

    print()

    if first is None:

        print(

            "VERDICT: no individual production "

            "step exceeds "

            f"{threshold_arcsec:g} arcsec."

        )

        if end_to_end > threshold_arcsec:

            print(

                "         The cumulative chain "

                "still exceeds the threshold; "

                "inspect model-definition "

                "differences."

            )

    else:

        (

            number,

            value,

            description,

        ) = first

        print(

            f"VERDICT: STEP {number} is the "

            "first divergence above "

            f"{threshold_arcsec:g} arcsec."

        )

        print(

            "         Suspect operation: "

            f"{description}"

        )

        print(

            "         Separation: "

            f"{format_sep(value)}"

        )

def main() -> None:

    parser = argparse.ArgumentParser(

        description=(

            "Instrument Star Almanack's "

            "compact-Sun frame conversion "

            "one production step at a time."

        )

    )

    parser.add_argument(

        "--date",

        action="append",

        dest="dates",

        metavar="YYYY-MM-DD",

        help=(

            "UTC date to diagnose; may be "

            "supplied more than once. "

            "Defaults to 1919-05-29, "

            "1991-07-11, and 2024-04-08."

        ),

    )

    parser.add_argument(

        "--threshold-arcsec",

        type=float,

        default=10.0,

        help=(

            "separation that counts as a "

            "material divergence "

            "(default: 10 arcsec)"

        ),

    )

    args = parser.parse_args()

    dates = (

        tuple(args.dates)

        if args.dates

        else DEFAULT_DATES

    )

    print(

        "Star Almanack — "

        "frame-conversion step diagnostic"

    )

    print(

        "Same compact solar vector; "

        "production rotations vs "

        "ERFA/IAU 2006."

    )

    print(

        "A first large same-input separation "

        "identifies the operation that "

        "introduces the error."

    )

    for date_utc in dates:

        diagnose_date(

            date_utc,

            args.threshold_arcsec,

        )

if __name__ == "__main__":

    main()