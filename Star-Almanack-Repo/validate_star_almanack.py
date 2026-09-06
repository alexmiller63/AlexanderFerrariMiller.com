#!/usr/bin/env python3

"""

Star Almanack — aggregate validation harness.

One command, one final PASS/FAIL, with section-level diagnostics.

Required sections

-----------------

1. ELP2000-82B lunar reference regression.

2. Julian-Date / UTC boundary regression.

Diagnostic sections

-------------------

3. Sun frame / J2000 diagnostic, including a stage-by-stage decomposition.

4. Solar eclipse geometry tests, including transformed-vs-raw Sun A/B test.

The eclipse engine is always exercised. While required_now is false in

eclipse-validation-cases.yaml, eclipse failures are reported diagnostically

but do not fail the overall workflow. Once the eclipse layer is satisfactory,

set required_now: true and the same tests become release-blocking.

Important

---------

Published eclipse data are used only as validation targets. eclipse_engine.py

does not read the validation catalog.

Why the UTC boundary tests are release-blocking

------------------------------------------------

The eclipse engine converts calculated Julian Dates back to civil UTC strings.

A rounding edge immediately before midnight once produced 86400 seconds within

a day. The old repair recursively called the same conversion routine and, at

the exact boundary, could call itself with the same value indefinitely.

The production converter now normalizes the astronomical instant to whole-

second resolution before decomposing it into a calendar date and clock time.

The tests below deliberately straddle midnight so that this invariant remains

protected against future "cleanup" changes.

Why the Sun-frame diagnostic exists

-----------------------------------

The ELP2000-82B lunar evaluator independently validates against the Bureau des

Longitudes reference implementation and returns geocentric rectangular

coordinates in the mean dynamical ecliptic and inertial equinox of J2000.

The compact Sun model begins with a vector treated by the eclipse engine as

ecliptic-of-date. The production code then performs three transformations:

    stage 0:

        raw compact Sun, ecliptic-of-date

    stage 1:

        ecliptic-of-date -> equatorial-of-date

    stage 2:

        equatorial-of-date -> equatorial J2000

    stage 3:

        equatorial J2000 -> ecliptic J2000

The eclipse timing residuals vary strongly with epoch. A direct A/B test has

also shown that bypassing the complete Sun-frame transformation can materially

reduce the timing residual.

That makes the transformation boundary a leading object of investigation.

The diagnostic therefore does three different things:

1. It observes the numerical vector after every production transformation.

2. It checks the mathematical reversibility of every individual stage.

3. It compares Sun-Moon separation in two properly matched coordinate frames.

Those are deliberately different questions.

A rotation can move the numerical components substantially and still be

perfectly correct, because the coordinates before and after a frame change are

expressed in different bases. Therefore a large stage-to-stage angular change

must NOT by itself be interpreted as an astronomical error.

Round-trip closure, however, compares vectors after returning them to the SAME

coordinate frame. It is therefore a useful implementation check.

Likewise, the matched-frame diagnostic compares:

    production Sun in J2000 ecliptic

        against

    ELP2000 Moon in J2000 ecliptic

and separately:

    raw compact Sun in ecliptic-of-date

        against

    the same ELP2000 Moon transformed back to ecliptic-of-date

If both coordinate transformations represent the same physical geometry, the

two Sun-Moon angular separations should agree to numerical precision.

This section is INFORMATIONAL ONLY. It cannot affect PASS/FAIL.

Why the transformed-vs-raw Sun A/B diagnostic exists

-----------------------------------------------------

The eclipse residuals show a particularly interesting epoch-dependent pattern:

  * before J2000, calculated greatest-eclipse times tend to be early;

  * after J2000, calculated greatest-eclipse times tend to be late;

  * the production Sun frame transformation is essentially zero at J2000

    and grows with distance from J2000.

Correlation alone does not prove that the frame transformation is wrong.

Therefore every positive eclipse case with a published/reference greatest time

is subjected to a direct A/B experiment:

  A — current production calculation:

      compact Sun -> current J2000 frame transformation.

  B — diagnostic calculation:

      raw compact Sun vector with the J2000 transformation bypassed.

IMPORTANT:

The B calculation deliberately mixes the raw compact Sun with the existing

J2000 Moon and is therefore an experimental perturbation, not a physically

matched coordinate-frame calculation.

Its timing response is useful because it reveals sensitivity to the frame

boundary, but it must not be interpreted by itself as proving that the raw Sun

is the correct physical representation.

The matched-frame diagnostic in section 3 exists to test that hypothesis

without mixing coordinate systems.

The B calculation temporarily substitutes the raw compact Sun function only

inside this validation process. The original production Sun function is always

restored immediately afterward with a try/finally block.

Nothing in eclipse_engine.py is modified.

The diagnostic prints SIGNED timing residuals:

    calculated greatest - reference greatest

so:

  negative = Star Almanack is EARLY

  positive = Star Almanack is LATE

It also reports whether bypassing the transformation improves or worsens the

absolute timing residual.

Why the eclipse geometry diagnostics exist

-------------------------------------------

When a positive eclipse case has a published/reference greatest-eclipse time,

the harness evaluates the Star Almanack geometry at BOTH:

  * the engine's calculated greatest-eclipse instant, and

  * the published/reference greatest-eclipse instant.

This does not change the calculation, classification, search algorithm, or

PASS/FAIL rules. It is instrumentation only.

The comparison helps distinguish two classes of defect:

  * search defect:

      the reference instant has the better Star Almanack geometry, but the

      search routine selected another instant;

  * geometry/ephemeris/frame defect:

      Star Almanack's own geometry is genuinely better at the calculated

      instant, meaning the displaced result originates upstream of the search.

The diagnostic is intentionally general and runs for every positive eclipse

case that supplies an expected/reference greatest-eclipse time.

"""

from __future__ import annotations

from datetime import datetime, timezone

from pathlib import Path

import math

import sys

import yaml

ROOT = Path(__file__).resolve().parent

ELP_DIR = ROOT / "star-almanack-elp82b"

LUNAR_CASES = ELP_DIR / "lunar-validation-cases.yaml"

ECLIPSE_CASES = ROOT / "eclipse-validation-cases.yaml"

MODEL = ELP_DIR / "elp82b-manifest.json"

sys.path.insert(0, str(ELP_DIR))

import lunar_elp  # noqa: E402

import eclipse_engine  # noqa: E402

def load_yaml(path: Path) -> dict:

    with path.open("r", encoding="utf-8") as f:

        return yaml.safe_load(f)

def validate_lunar() -> tuple[bool, int, int]:

    spec = load_yaml(LUNAR_CASES)

    tolerance = float(spec["tolerance_km"])

    normalized = lunar_elp.load_normalized(MODEL)

    print("\n=== 1. LUNAR ELP2000-82B REFERENCE TESTS ===")

    failures = 0

    for case in spec["cases"]:

        result = lunar_elp.evaluate(

            normalized,

            float(case["jd_tdb"]),

            precision_rad=0.0,

        )

        rect = result.rectangular

        exp = case["expected"]

        dx = rect.x_km - float(exp["x_km"])

        dy = rect.y_km - float(exp["y_km"])

        dz = rect.z_km - float(exp["z_km"])

        error = math.sqrt(dx * dx + dy * dy + dz * dz)

        passed = error <= tolerance

        print(f"\n{case['name']}")

        print(f"  dX = {dx:+.9f} km")

        print(f"  dY = {dy:+.9f} km")

        print(f"  dZ = {dz:+.9f} km")

        print(f"  3D = {error:.9f} km")

        print(f"  tolerance = {tolerance:.9f} km")

        print(f"  {'PASS' if passed else 'FAIL'}")

        if not passed:

            failures += 1

    count = len(spec["cases"])

    ok = failures == 0

    print(

        f"\nLUNAR SECTION: {'PASS' if ok else 'FAIL'} "

        f"({count - failures}/{count})"

    )

    return ok, count - failures, count

def validate_utc_boundaries() -> tuple[bool, int, int]:

    """

    Regression-test Julian-Date -> UTC conversion across a civil midnight.

    """

    print("\n=== 2. JULIAN-DATE / UTC BOUNDARY TESTS ===")

    midnight = eclipse_engine.gregorian_to_jd(

        2026,

        8,

        19,

        0.0,

    )

    cases = [

        (

            "just before rounding threshold",

            midnight - 0.6 / 86400.0,

            "2026-08-18T23:59:59Z",

        ),

        (

            "just after rounding threshold",

            midnight - 0.4 / 86400.0,

            "2026-08-19T00:00:00Z",

        ),

        (

            "exact midnight",

            midnight,

            "2026-08-19T00:00:00Z",

        ),

        (

            "just after midnight, below next-second threshold",

            midnight + 0.4 / 86400.0,

            "2026-08-19T00:00:00Z",

        ),

        (

            "just after midnight, above next-second threshold",

            midnight + 0.6 / 86400.0,

            "2026-08-19T00:00:01Z",

        ),

    ]

    passed_count = 0

    for label, jd, expected in cases:

        try:

            calculated = eclipse_engine.jd_to_iso_utc(jd)

            passed = calculated == expected

        except Exception as exc:

            calculated = f"{type(exc).__name__}: {exc}"

            passed = False

        print(f"\n{label}")

        print(f"  JD:          {jd:.12f}")

        print(f"  calculated:  {calculated}")

        print(f"  expected:    {expected}")

        print(f"  {'PASS' if passed else 'FAIL'}")

        if passed:

            passed_count += 1

    total = len(cases)

    ok = passed_count == total

    print(

        f"\nUTC BOUNDARY SECTION: {'PASS' if ok else 'FAIL'} "

        f"({passed_count}/{total})"

    )

    return ok, passed_count, total

def _parse_iso_z(text: str) -> datetime:

    return datetime.fromisoformat(

        text.replace("Z", "+00:00")

    )

def _signed_seconds_difference(

    calculated: str,

    expected: str,

) -> float:

    a = _parse_iso_z(calculated)

    b = _parse_iso_z(expected)

    return (a - b).total_seconds()

def _seconds_difference(

    calculated: str,

    expected: str,

) -> float:

    return abs(

        _signed_seconds_difference(

            calculated,

            expected,

        )

    )

def _format_signed_time_error(seconds: float) -> str:

    sign = "+" if seconds >= 0.0 else "-"

    direction = (

        "LATE"

        if seconds > 0.0

        else "EARLY"

        if seconds < 0.0

        else "EXACT"

    )

    whole = int(round(abs(seconds)))

    hours, rem = divmod(whole, 3600)

    minutes, secs = divmod(rem, 60)

    return (

        f"{sign}{hours:02d}:{minutes:02d}:{secs:02d} "

        f"({direction})"

    )

def _iso_z_to_jd(text: str) -> float:

    dt = _parse_iso_z(text).astimezone(

        timezone.utc

    )

    hour = (

        dt.hour

        + dt.minute / 60.0

        + dt.second / 3600.0

        + dt.microsecond / 3_600_000_000.0

    )

    return eclipse_engine.gregorian_to_jd(

        dt.year,

        dt.month,

        dt.day,

        hour,

    )

def _angle_between_deg(

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> float:

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

def _vector_difference_km(

    a: eclipse_engine.Vec3,

    b: eclipse_engine.Vec3,

) -> float:

    return (a - b).norm()

def _print_vec(

    label: str,

    v: eclipse_engine.Vec3,

) -> None:

    print(

        f"      {label:<13} "

        f"x={v.x:+.3f} km  "

        f"y={v.y:+.3f} km  "

        f"z={v.z:+.3f} km"

    )

def _compact_sun_ecliptic_of_date(

    jd_tdb: float,

) -> eclipse_engine.Vec3:

    """

    Reconstruct the compact Sun vector before the production J2000 frame

    transformation.

    """

    d = jd_tdb - 2451543.5

    w = (

        (

            282.9404

            + 0.0000470935 * d

        )

        % 360.0

    ) * eclipse_engine.DEG

    e = (

        0.016709

        - 0.000000001151 * d

    )

    M = (

        (

            356.0470

            + 0.9856002585 * d

        )

        % 360.0

    ) * eclipse_engine.DEG

    E = M

    for _ in range(12):

        f = E - e * math.sin(E) - M

        fp = 1.0 - e * math.cos(E)

        step = f / fp

        E -= step

        if abs(step) < 1e-14:

            break

    x = math.cos(E) - e

    y = math.sqrt(1.0 - e * e) * math.sin(E)

    r_au = math.hypot(

        x,

        y,

    )

    true_anom = math.atan2(

        y,

        x,

    )

    lon = true_anom + w

    return eclipse_engine.Vec3(

        r_au

        * math.cos(lon)

        * eclipse_engine.AU_KM,

        r_au

        * math.sin(lon)

        * eclipse_engine.AU_KM,

        0.0,

    )

def _rot_y(

    v: eclipse_engine.Vec3,

    angle: float,

) -> eclipse_engine.Vec3:

    c = math.cos(angle)

    s = math.sin(angle)

    return eclipse_engine.Vec3(

        c * v.x + s * v.z,

        v.y,

        -s * v.x + c * v.z,

    )

def _precession_angles_rad(

    jd: float,

) -> tuple[float, float, float]:

    t = (

        jd - 2451545.0

    ) / 36525.0

    zeta = (

        2306.2181 * t

        + 0.30188 * t * t

        + 0.017998 * t**3

    ) * eclipse_engine.ARCSEC

    z = (

        2306.2181 * t

        + 1.09468 * t * t

        + 0.018203 * t**3

    ) * eclipse_engine.ARCSEC

    theta = (

        2004.3109 * t

        - 0.42665 * t * t

        - 0.041833 * t**3

    ) * eclipse_engine.ARCSEC

    return (

        zeta,

        z,

        theta,

    )

def _precess_equatorial_j2000_to_date(

    v: eclipse_engine.Vec3,

    jd: float,

) -> eclipse_engine.Vec3:

    """

    Exact matrix inverse of the production date->J2000 precession rotation.

    """

    zeta, z, theta = _precession_angles_rad(

        jd

    )

    w = eclipse_engine._rot_z(

        v,

        zeta,

    )

    w = _rot_y(

        w,

        -theta,

    )

    w = eclipse_engine._rot_z(

        w,

        z,

    )

    return w

def _moon_j2000_to_ecliptic_of_date(

    moon_j2000: eclipse_engine.Vec3,

    jd_tdb: float,

) -> eclipse_engine.Vec3:

    """

    Convert the ELP2000 Moon from J2000 mean ecliptic coordinates

    to mean ecliptic-of-date coordinates.

    This function exists only for diagnostic comparison.

    Pipeline:

        ecliptic J2000

            -> equatorial J2000

            -> equatorial of date

            -> ecliptic of date

    It allows the raw compact Sun and the Moon to be compared in the same

    coordinate frame instead of deliberately mixing date and J2000 frames.

    """

    equatorial_j2000 = eclipse_engine._rot_x(

        moon_j2000,

        eclipse_engine._mean_obliquity_rad(

            2451545.0

        ),

    )

    equatorial_date = _precess_equatorial_j2000_to_date(

        equatorial_j2000,

        jd_tdb,

    )

    ecliptic_date = eclipse_engine._rot_x(

        equatorial_date,

        -eclipse_engine._mean_obliquity_rad(

            jd_tdb

        ),

    )

    return ecliptic_date

def _sun_frame_stages(

    jd_tdb: float,

) -> tuple[

    eclipse_engine.Vec3,

    eclipse_engine.Vec3,

    eclipse_engine.Vec3,

    eclipse_engine.Vec3,

]:

    raw_ecliptic_date = (

        _compact_sun_ecliptic_of_date(

            jd_tdb

        )

    )

    equatorial_date = (

        eclipse_engine._rot_x(

            raw_ecliptic_date,

            eclipse_engine._mean_obliquity_rad(

                jd_tdb

            ),

        )

    )

    equatorial_j2000 = (

        eclipse_engine._precess_equatorial_date_to_j2000(

            equatorial_date,

            jd_tdb,

        )

    )

    ecliptic_j2000 = (

        eclipse_engine._rot_x(

            equatorial_j2000,

            -eclipse_engine._mean_obliquity_rad(

                2451545.0

            ),

        )

    )

    return (

        raw_ecliptic_date,

        equatorial_date,

        equatorial_j2000,

        ecliptic_j2000,

    )

def _print_sun_frame_stage_diagnostic(

    jd_tdb: float,

    production_sun: eclipse_engine.Vec3,

) -> None:

    (

        raw_ecliptic_date,

        equatorial_date,

        equatorial_j2000,

        ecliptic_j2000,

    ) = _sun_frame_stages(

        jd_tdb

    )

    print("\n  STAGE-BY-STAGE TRANSFORMATION")

    _print_vec(

        "0 raw ecl-date",

        raw_ecliptic_date,

    )

    _print_vec(

        "1 eq-date",

        equatorial_date,

    )

    _print_vec(

        "2 eq-J2000",

        equatorial_j2000,

    )

    _print_vec(

        "3 ecl-J2000",

        ecliptic_j2000,

    )

    print("\n  NUMERICAL ROTATION MAGNITUDES")

    print(

        "    NOTE: adjacent stages use different coordinate bases."

    )

    print(

        "    These angles describe the numerical rotation being applied;"

    )

    print(

        "    they are NOT direct physical sky-position errors."

    )

    step_01 = _angle_between_deg(

        raw_ecliptic_date,

        equatorial_date,

    )

    step_12 = _angle_between_deg(

        equatorial_date,

        equatorial_j2000,

    )

    step_23 = _angle_between_deg(

        equatorial_j2000,

        ecliptic_j2000,

    )

    raw_to_final = _angle_between_deg(

        raw_ecliptic_date,

        ecliptic_j2000,

    )

    print(

        f"    stage 0 -> 1 numeric rotation: "

        f"{step_01:.9f} deg"

    )

    print(

        f"    stage 1 -> 2 numeric rotation: "

        f"{step_12:.9f} deg"

    )

    print(

        f"    stage 2 -> 3 numeric rotation: "

        f"{step_23:.9f} deg"

    )

    print(

        f"    raw -> final numeric shift:    "

        f"{raw_to_final:.9f} deg"

    )

    back_to_ecliptic_date = (

        eclipse_engine._rot_x(

            equatorial_date,

            -eclipse_engine._mean_obliquity_rad(

                jd_tdb

            ),

        )

    )

    closure_01_km = _vector_difference_km(

        raw_ecliptic_date,

        back_to_ecliptic_date,

    )

    closure_01_deg = _angle_between_deg(

        raw_ecliptic_date,

        back_to_ecliptic_date,

    )

    back_to_equatorial_date = (

        _precess_equatorial_j2000_to_date(

            equatorial_j2000,

            jd_tdb,

        )

    )

    closure_12_km = _vector_difference_km(

        equatorial_date,

        back_to_equatorial_date,

    )

    closure_12_deg = _angle_between_deg(

        equatorial_date,

        back_to_equatorial_date,

    )

    back_to_equatorial_j2000 = (

        eclipse_engine._rot_x(

            ecliptic_j2000,

            eclipse_engine._mean_obliquity_rad(

                2451545.0

            ),

        )

    )

    closure_23_km = _vector_difference_km(

        equatorial_j2000,

        back_to_equatorial_j2000,

    )

    closure_23_deg = _angle_between_deg(

        equatorial_j2000,

        back_to_equatorial_j2000,

    )

    production_difference_km = (

        _vector_difference_km(

            ecliptic_j2000,

            production_sun,

        )

    )

    production_difference_deg = (

        _angle_between_deg(

            ecliptic_j2000,

            production_sun,

        )

    )

    print("\n  ROUND-TRIP CLOSURE TESTS")

    print("    stage 0 -> 1 -> 0:")

    print(

        f"      vector closure:            "

        f"{closure_01_km:.12f} km"

    )

    print(

        f"      angular closure:           "

        f"{closure_01_deg:.12f} deg"

    )

    print("    stage 1 -> 2 -> 1:")

    print(

        f"      vector closure:            "

        f"{closure_12_km:.12f} km"

    )

    print(

        f"      angular closure:           "

        f"{closure_12_deg:.12f} deg"

    )

    print("    stage 2 -> 3 -> 2:")

    print(

        f"      vector closure:            "

        f"{closure_23_km:.12f} km"

    )

    print(

        f"      angular closure:           "

        f"{closure_23_deg:.12f} deg"

    )

    print("\n  PRODUCTION AGREEMENT CHECK")

    print(

        f"    staged final vs production:  "

        f"{production_difference_km:.12f} km"

    )

    print(

        f"    staged angular difference:   "

        f"{production_difference_deg:.12f} deg"

    )

    closure_tolerance_km = 0.001

    all_closures_good = (

        closure_01_km <= closure_tolerance_km

        and closure_12_km <= closure_tolerance_km

        and closure_23_km <= closure_tolerance_km

        and production_difference_km <= closure_tolerance_km

    )

    print("\n  STAGE DIAGNOSTIC INTERPRETATION")

    if all_closures_good:

        print(

            "    All transformation stages close within "

            f"{closure_tolerance_km:.3f} km."

        )

        print(

            "    The staged calculation also reproduces the production Sun."

        )

        print(

            "    This argues AGAINST a simple non-invertible rotation/sign/"

            "matrix-order defect."

        )

        print(

            "    If eclipse timing still improves when the transformation is "

            "bypassed,"

        )

        print(

            "    investigate the FRAME ASSUMPTION: whether the compact Sun "

            "coefficients"

        )

        print(

            "    actually require this ecliptic-of-date -> J2000 conversion."

        )

    else:

        print(

            "    At least one transformation fails round-trip closure or does "

            "not"

        )

        print(

            "    reproduce the production Sun vector."

        )

        print(

            "    Investigate that mathematical stage before changing the "

            "underlying"

        )

        print(

            "    frame interpretation."

        )

def validate_sun_frame_diagnostic() -> None:

    """

    Observe the Sun vector before, during, and after its current J2000

    transformation at epochs spanning both sides of J2000.

    Also compare Sun-Moon separation in properly matched coordinate frames.

    """

    print(

        "\n=== 3. SUN FRAME / J2000 DIAGNOSTIC ==="

    )

    print(

        "  enforcement:                  DIAGNOSTIC ONLY"

    )

    print(

        "  Moon frame:                   ELP2000-82B J2000 ecliptic"

    )

    print(

        "  raw Sun:                      compact pre-transform vector"

    )

    print(

        "  transformed Sun:              current production J2000 conversion"

    )

    print(

        "  question 1:                   how much numerical displacement "

        "does the conversion introduce?"

    )

    print(

        "  question 2:                   does every mathematical stage "

        "round-trip correctly?"

    )

    print(

        "  question 3:                   does the staged result exactly "

        "reproduce production?"

    )

    print(

        "  question 4:                   do Sun-Moon separations agree when "

        "both bodies are expressed in matched frames?"

    )

    epochs = [

        (

            "1919 eclipse epoch",

            "1919-05-29T13:08:34Z",

        ),

        (

            "1991 eclipse epoch",

            "1991-07-11T19:06:03Z",

        ),

        (

            "J2000 epoch",

            "2000-01-01T12:00:00Z",

        ),

        (

            "2017 eclipse epoch",

            "2017-08-21T18:25:30Z",

        ),

        (

            "2024 eclipse epoch",

            "2024-04-08T18:17:15Z",

        ),

        (

            "2028 eclipse epoch",

            "2028-07-22T02:56:39Z",

        ),

    ]

    engine = eclipse_engine.EclipseEngine(

        MODEL

    )

    for label, iso_utc in epochs:

        jd_utc = _iso_z_to_jd(

            iso_utc

        )

        geometry = engine.geometry_at_utc_jd(

            jd_utc

        )

        raw_sun = (

            _compact_sun_ecliptic_of_date(

                geometry.jd_tdb_approx

            )

        )

        transformed_sun = geometry.sun

        moon = geometry.moon

        moon_ecliptic_date = (

            _moon_j2000_to_ecliptic_of_date(

                moon,

                geometry.jd_tdb_approx,

            )

        )

        separation_j2000_deg = (

            _angle_between_deg(

                transformed_sun,

                moon,

            )

        )

        separation_date_deg = (

            _angle_between_deg(

                raw_sun,

                moon_ecliptic_date,

            )

        )

        separation_frame_difference_deg = (

            separation_date_deg

            - separation_j2000_deg

        )

        frame_shift_deg = (

            _angle_between_deg(

                raw_sun,

                transformed_sun,

            )

        )

        epoch_offset_years = (

            geometry.jd_tdb_approx

            - 2451545.0

        ) / 365.25

        print(f"\n{label}")

        print(

            f"  UTC:                         "

            f"{iso_utc}"

        )

        print(

            f"  JD TDB approx:               "

            f"{geometry.jd_tdb_approx:.12f}"

        )

        print(

            f"  years from J2000:            "

            f"{epoch_offset_years:+.6f}"

        )

        print(

            f"  full raw-to-final numeric "

            f"shift: {frame_shift_deg:.9f} deg"

        )

        print(

            f"  matched J2000 Sun-Moon sep:   "

            f"{separation_j2000_deg:.9f} deg"

        )

        print(

            f"  matched date-frame separation: "

            f"{separation_date_deg:.9f} deg"

        )

        print(

            f"  date-frame minus J2000 sep:    "

            f"{separation_frame_difference_deg:+.9f} deg"

        )

        _print_vec(

            "Raw",

            raw_sun,

        )

        _print_vec(

            "J2000",

            transformed_sun,

        )

        _print_vec(

            "Moon",

            moon,

        )

        _print_vec(

            "Moon date",

            moon_ecliptic_date,

        )

        _print_sun_frame_stage_diagnostic(

            geometry.jd_tdb_approx,

            transformed_sun,

        )

    print(

        "\nSUN FRAME DIAGNOSTIC: INFORMATIONAL "

        "(does not affect final PASS/FAIL)"

    )

def _print_geometry_snapshot(

    label: str,

    iso_utc: str,

    geometry: eclipse_engine.SolarGeometry,

) -> None:

    separation_deg = _angle_between_deg(

        geometry.sun,

        geometry.moon,

    )

    print(f"\n    {label}")

    print(

        f"      UTC:                 "

        f"{iso_utc}"

    )

    print(

        f"      JD UTC:              "

        f"{geometry.jd_utc:.12f}"

    )

    print(

        f"      JD TDB approx:       "

        f"{geometry.jd_tdb_approx:.12f}"

    )

    print(

        f"      Sun-Moon separation: "

        f"{separation_deg:.9f} deg"

    )

    print(

        f"      axis distance:       "

        f"{geometry.axis_distance_km:.3f} km"

    )

    print(

        f"      q(min):              "

        f"{geometry.q_min_km:.3f} km"

    )

    print(

        f"      eclipse margin:      "

        f"{geometry.eclipse_margin_km:+.3f} km"

    )

    print(

        f"      central margin:      "

        f"{geometry.central_margin_km:+.3f} km"

    )

    print(

        f"      eclipse type:        "

        f"{geometry.eclipse_type}"

    )

    _print_vec(

        "Sun",

        geometry.sun,

    )

    _print_vec(

        "Moon",

        geometry.moon,

    )

def _print_reference_geometry_diagnostic(

    engine: eclipse_engine.EclipseEngine,

    event: eclipse_engine.SolarEclipseEvent,

    expected_time: str,

) -> None:

    reference_jd = _iso_z_to_jd(

        expected_time

    )

    reference_geometry = (

        engine.geometry_at_utc_jd(

            reference_jd

        )

    )

    calculated_geometry = (

        event.geometry

    )

    _print_geometry_snapshot(

        "geometry at CALCULATED greatest",

        event.greatest_utc,

        calculated_geometry,

    )

    _print_geometry_snapshot(

        "geometry at REFERENCE greatest",

        expected_time,

        reference_geometry,

    )

    axis_delta = (

        reference_geometry.axis_distance_km

        - calculated_geometry.axis_distance_km

    )

    sep_calc = _angle_between_deg(

        calculated_geometry.sun,

        calculated_geometry.moon,

    )

    sep_ref = _angle_between_deg(

        reference_geometry.sun,

        reference_geometry.moon,

    )

    separation_delta = (

        sep_ref - sep_calc

    )

    print(

        "\n    diagnostic comparison"

    )

    print(

        f"      reference - calculated axis distance: "

        f"{axis_delta:+.3f} km"

    )

    print(

        f"      reference - calculated angular sep.:  "

        f"{separation_delta:+.9f} deg"

    )

    if axis_delta < 0.0:

        print(

            "      search clue: reference time has SMALLER axis distance; "

            "inspect search/bracketing."

        )

    elif axis_delta > 0.0:

        print(

            "      geometry clue: calculated time has SMALLER axis distance; "

            "inspect ephemeris/frame/time inputs."

        )

    else:

        print(

            "      geometry clue: axis distances are equal at displayed "

            "precision."

        )

def _find_eclipse_with_raw_sun(

    engine: eclipse_engine.EclipseEngine,

    date_utc: str,

) -> eclipse_engine.SolarEclipseEvent:

    production_sun_function = (

        eclipse_engine.sun_vector_j2000

    )

    try:

        eclipse_engine.sun_vector_j2000 = (

            _compact_sun_ecliptic_of_date

        )

        return engine.find_solar_eclipse(

            date_utc

        )

    finally:

        eclipse_engine.sun_vector_j2000 = (

            production_sun_function

        )

def _print_sun_ab_diagnostic(

    engine: eclipse_engine.EclipseEngine,

    production_event: eclipse_engine.SolarEclipseEvent,

    case: dict,

    expected_time: str,

) -> None:

    print(

        "\n    SUN FRAME A/B DIAGNOSTIC"

    )

    print(

        "      signed residual = calculated - reference"

    )

    print(

        "      negative = EARLY; positive = LATE"

    )

    print(

        "      NOTE: B/raw is a deliberate mixed-frame perturbation; "

        "see section 3 for matched-frame geometry."

    )

    production_signed_error = (

        _signed_seconds_difference(

            production_event.greatest_utc,

            expected_time,

        )

    )

    try:

        raw_event = (

            _find_eclipse_with_raw_sun(

                engine,

                case["date_utc"],

            )

        )

    except Exception as exc:

        print(

            "      B/raw diagnostic failed: "

            f"{type(exc).__name__}: {exc}"

        )

        print(

            "      production Sun function was restored in finally."

        )

        return

    raw_signed_error = (

        _signed_seconds_difference(

            raw_event.greatest_utc,

            expected_time,

        )

    )

    production_abs_error = abs(

        production_signed_error

    )

    raw_abs_error = abs(

        raw_signed_error

    )

    improvement_seconds = (

        production_abs_error

        - raw_abs_error

    )

    print("")

    print(

        "      A — PRODUCTION TRANSFORMED SUN"

    )

    print(

        f"        greatest:             "

        f"{production_event.greatest_utc}"

    )

    print(

        f"        signed error:         "

        f"{production_signed_error:+.1f} s"

    )

    print(

        f"        human residual:       "

        f"{_format_signed_time_error(production_signed_error)}"

    )

    print(

        f"        eclipse type:         "

        f"{production_event.eclipse_type}"

    )

    print(

        f"        axis distance:        "

        f"{production_event.geometry.axis_distance_km:.3f} km"

    )

    print("")

    print(

        "      B — RAW COMPACT SUN"

    )

    print(

        f"        greatest:             "

        f"{raw_event.greatest_utc}"

    )

    print(

        f"        signed error:         "

        f"{raw_signed_error:+.1f} s"

    )

    print(

        f"        human residual:       "

        f"{_format_signed_time_error(raw_signed_error)}"

    )

    print(

        f"        eclipse type:         "

        f"{raw_event.eclipse_type}"

    )

    print(

        f"        axis distance:        "

        f"{raw_event.geometry.axis_distance_km:.3f} km"

    )

    print("")

    print(

        "      A/B RESULT"

    )

    if improvement_seconds > 0.5:

        print(

            f"        raw Sun IMPROVES absolute timing error by "

            f"{improvement_seconds:.1f} s"

        )

    elif improvement_seconds < -0.5:

        print(

            f"        raw Sun WORSENS absolute timing error by "

            f"{abs(improvement_seconds):.1f} s"

        )

    else:

        print(

            "        raw Sun makes essentially no change to "

            "absolute timing error"

        )

    if production_abs_error > 0.0:

        ratio = (

            raw_abs_error

            / production_abs_error

        )

        print(

            f"        |B error| / |A error|: "

            f"{ratio:.6f}"

        )

        if ratio < 0.25:

            print(

                "        diagnostic clue: VERY STRONG support for "

                "investigating the production Sun-frame transformation."

            )

        elif ratio < 0.75:

            print(

                "        diagnostic clue: meaningful support for "

                "investigating the production Sun-frame transformation."

            )

        elif ratio > 1.25:

            print(

                "        diagnostic clue: bypassing the frame transform "

                "does not explain this case."

            )

        else:

            print(

                "        diagnostic clue: A and B are too similar here "

                "for this case alone to identify the cause."

            )

def _run_eclipse_case(

    engine: eclipse_engine.EclipseEngine,

    case: dict,

    *,

    time_tolerance_seconds: float,

) -> bool:

    event = engine.find_solar_eclipse(

        case["date_utc"]

    )

    expected_exists = bool(

        case["expected_exists"]

    )

    existence_ok = (

        event.eclipse_exists

        == expected_exists

    )

    print(

        f"\n{case['id']} — {case['label']}"

    )

    print(

        f"  requested date:       "

        f"{case['date_utc']}"

    )

    print(

        f"  calculated eclipse:   "

        f"{'yes' if event.eclipse_exists else 'no'}"

    )

    print(

        f"  expected eclipse:     "

        f"{'yes' if expected_exists else 'no'}"

    )

    if not expected_exists:

        print(

            f"  closest alignment:    "

            f"{event.greatest_utc}"

        )

        print(

            f"  classification:       "

            f"{event.eclipse_type}"

        )

        print(

            f"  eclipse margin:       "

            f"{event.geometry.eclipse_margin_km:+.3f} km"

        )

        print(

            f"  {'PASS' if existence_ok else 'FAIL'}"

        )

        return existence_ok

    expected_type = str(

        case["expected_type"]

    )

    type_ok = (

        event.eclipse_type

        == expected_type

    )

    expected_time = case.get(

        "expected_greatest_utc"

    )

    if expected_time is None:

        expected_time = case.get(

            "nasa_greatest_utc"

        )

    time_ok = True

    time_error = None

    signed_time_error = None

    if expected_time:

        signed_time_error = (

            _signed_seconds_difference(

                event.greatest_utc,

                expected_time,

            )

        )

        time_error = abs(

            signed_time_error

        )

        time_ok = (

            time_error

            <= time_tolerance_seconds

        )

    print(

        f"  calculated type:      "

        f"{event.eclipse_type}"

    )

    print(

        f"  expected type:        "

        f"{expected_type}"

    )

    print(

        f"  calculated greatest:  "

        f"{event.greatest_utc}"

    )

    if expected_time:

        print(

            f"  expected greatest:    "

            f"{expected_time}"

        )

        print(

            f"  time error absolute:  "

            f"{time_error:.1f} s"

        )

        print(

            f"  time error signed:    "

            f"{signed_time_error:+.1f} s"

        )

        print(

            f"  signed residual:      "

            f"{_format_signed_time_error(signed_time_error)}"

        )

        print(

            f"  time tolerance:       "

            f"{time_tolerance_seconds:.1f} s"

        )

        _print_reference_geometry_diagnostic(

            engine,

            event,

            expected_time,

        )

        _print_sun_ab_diagnostic(

            engine,

            event,

            case,

            expected_time,

        )

    magnitude_target = case.get(

        "expected_magnitude"

    )

    if magnitude_target is None:

        magnitude_target = case.get(

            "nasa_magnitude"

        )

    if magnitude_target is not None:

        print(

            f"  magnitude target:     "

            f"{float(magnitude_target):.4f} "

            "(registered; calculation not yet implemented)"

        )

    passed = (

        existence_ok

        and type_ok

        and time_ok

    )

    print(

        f"  {'PASS' if passed else 'FAIL'}"

    )

    return passed

def validate_eclipses() -> tuple[

    bool,

    int,

    int,

    bool,

]:

    spec = load_yaml(

        ECLIPSE_CASES

    )

    historical = spec.get(

        "historical",

        [],

    )

    negative = spec.get(

        "negative_controls",

        [],

    )

    future = (

        spec.get(

            "future_jello",

            {},

        )

        .get(

            "cases",

            [],

        )

    )

    all_cases = (

        historical

        + negative

        + future

    )

    required = bool(

        spec.get(

            "required_now",

            False,

        )

    )

    tolerance = float(

        spec.get(

            "tolerances",

            {},

        ).get(

            "greatest_time_seconds",

            120,

        )

    )

    print(

        "\n=== 4. SOLAR ECLIPSE GEOMETRY "

        "AND SUN-FRAME A/B TESTS ==="

    )

    print(

        f"  Historical positive controls: "

        f"{len(historical)}"

    )

    print(

        f"  Negative controls:            "

        f"{len(negative)}"

    )

    print(

        f"  Future Jell-O comparisons:    "

        f"{len(future)}"

    )

    print(

        f"  enforcement:                  "

        f"{'REQUIRED' if required else 'DIAGNOSTIC'}"

    )

    print(

        "  A/B experiment:              "

        "A=production transformed Sun; B=raw compact Sun"

    )

    print(

        "  A/B enforcement:             "

        "DIAGNOSTIC ONLY"

    )

    engine = eclipse_engine.EclipseEngine(

        MODEL

    )

    passed = 0

    for case in all_cases:

        if _run_eclipse_case(

            engine,

            case,

            time_tolerance_seconds=tolerance,

        ):

            passed += 1

    total = len(

        all_cases

    )

    ok = (

        passed == total

    )

    print(

        f"\nECLIPSE SECTION: "

        f"{'PASS' if ok else 'FAIL'} "

        f"({passed}/{total})"

    )

    if not required:

        print(

            "  NOTE: Eclipse results are diagnostic until "

            "required_now is set to true."

        )

    print(

        "  NOTE: Raw-vs-transformed Sun A/B results are "

        "always informational and never alter PASS/FAIL."

    )

    return (

        ok,

        passed,

        total,

        required,

    )

def main() -> None:

    print(

        "Star Almanack — complete validation"

    )

    print(

        f"UTC run time: "

        f"{datetime.now(timezone.utc).isoformat()}"

    )

    (

        lunar_ok,

        lunar_passed,

        lunar_total,

    ) = validate_lunar()

    (

        utc_ok,

        utc_passed,

        utc_total,

    ) = validate_utc_boundaries()

    validate_sun_frame_diagnostic()

    (

        eclipse_ok,

        eclipse_passed,

        eclipse_total,

        eclipse_required,

    ) = validate_eclipses()

    required_results = [

        lunar_ok,

        utc_ok,

    ]

    if eclipse_required:

        required_results.append(

            eclipse_ok

        )

    overall = all(

        required_results

    )

    print(

        "\n=== FINAL RESULT ==="

    )

    print(

        f"Required lunar cases: "

        f"{lunar_passed}/{lunar_total} passed"

    )

    print(

        f"Required UTC boundary cases: "

        f"{utc_passed}/{utc_total} passed"

    )

    if eclipse_required:

        print(

            f"Required eclipse cases: "

            f"{eclipse_passed}/{eclipse_total} passed"

        )

    else:

        print(

            f"Diagnostic eclipse cases: "

            f"{eclipse_passed}/{eclipse_total} passed"

        )

    print(

        "Sun frame staged diagnostic: "

        "DIAGNOSTIC ONLY"

    )

    print(

        "Sun frame matched-coordinate diagnostic: "

        "DIAGNOSTIC ONLY"

    )

    print(

        "Sun frame A/B experiment: "

        "DIAGNOSTIC ONLY"

    )

    print(

        f"STAR ALMANACK VALIDATION: "

        f"{'PASS' if overall else 'FAIL'}"

    )

    raise SystemExit(

        0 if overall else 1

    )

if __name__ == "__main__":

    main()