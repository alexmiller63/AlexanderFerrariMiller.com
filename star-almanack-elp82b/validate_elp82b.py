#!/usr/bin/env python3
"""
Star Almanack — ELP2000-82B validation harness.

This script tests the Python lunar evaluator in lunar_elp.py against
reference Cartesian coordinates produced from the original ELP2000-82B
Fortran implementation.

Exit status:
    0 = every test passed
    1 = one or more tests failed

The coordinates are geocentric J2000 mean-ecliptic rectangular coordinates
in kilometers, matching lunar_elp.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse
import math

from lunar_elp import evaluate, load_normalized


@dataclass(frozen=True)
class ReferenceCase:
    name: str
    jd_tdb: float
    x_km: float
    y_km: float
    z_km: float


# Reference generated from the original ELP2000-82B Fortran implementation.
#
# Source cross-check:
# Celestial Programming's full ELP2000-82B implementation publishes this
# Fortran-derived test case for JD(TDB) 2451555.5.
REFERENCE_CASES = (
    ReferenceCase(
        name="Fortran reference JD 2451555.5",
        jd_tdb=2451555.5,
        x_km=382979.7604730463,
        y_km=-68204.20174530084,
        z_km=-25987.71602589964,
    ),
)


def component_error(actual: float, expected: float) -> float:
    return actual - expected


def validate_case(
    normalized: dict,
    case: ReferenceCase,
    tolerance_km: float,
) -> bool:
    result = evaluate(normalized, case.jd_tdb, precision_rad=0.0)
    rect = result.rectangular

    dx = component_error(rect.x_km, case.x_km)
    dy = component_error(rect.y_km, case.y_km)
    dz = component_error(rect.z_km, case.z_km)
    error_3d = math.sqrt(dx * dx + dy * dy + dz * dz)

    passed = error_3d <= tolerance_km

    print()
    print(case.name)
    print(f"  JD(TDB): {case.jd_tdb:.9f}")
    print("  Expected:")
    print(f"    X = {case.x_km:.9f} km")
    print(f"    Y = {case.y_km:.9f} km")
    print(f"    Z = {case.z_km:.9f} km")
    print("  Calculated:")
    print(f"    X = {rect.x_km:.9f} km")
    print(f"    Y = {rect.y_km:.9f} km")
    print(f"    Z = {rect.z_km:.9f} km")
    print("  Difference:")
    print(f"    dX = {dx:+.9f} km")
    print(f"    dY = {dy:+.9f} km")
    print(f"    dZ = {dz:+.9f} km")
    print(f"    3D = {error_3d:.9f} km")
    print(f"  tolerance = {tolerance_km:.9f} km")
    print(f"  {'PASS' if passed else 'FAIL'}")

    return passed


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Validate Star Almanack's ELP2000-82B Python evaluator."
    )
    parser.add_argument(
        "normalized_json",
        type=Path,
        nargs="?",
        default=Path("elp82b-manifest.json"),
        help="normalized ELP2000-82B JSON (default: elp82b-manifest.json)",
    )
    parser.add_argument(
        "--tolerance-km",
        type=float,
        default=0.01,
        help="maximum allowed 3D error in km (default: 0.01 = 10 m)",
    )
    args = parser.parse_args(argv)

    if args.tolerance_km < 0.0:
        parser.error("--tolerance-km must be non-negative")

    normalized = load_normalized(args.normalized_json)

    print("Star Almanack ELP2000-82B validation")
    print(f"Model file: {args.normalized_json}")
    print(f"Cases: {len(REFERENCE_CASES)}")

    failures = 0
    for case in REFERENCE_CASES:
        if not validate_case(normalized, case, args.tolerance_km):
            failures += 1

    print()
    if failures:
        print(f"VALIDATION FAILED: {failures} of {len(REFERENCE_CASES)} case(s) failed.")
        raise SystemExit(1)

    print(f"VALIDATION PASSED: all {len(REFERENCE_CASES)} case(s) passed.")


if __name__ == "__main__":
    main()
