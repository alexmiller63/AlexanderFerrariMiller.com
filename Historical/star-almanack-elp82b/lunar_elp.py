#!/usr/bin/env python3
"""
Star Almanack lunar engine — ELP2000-82B numerical evaluator.

This is a Python translation of the numerical logic in the Bureau des
Longitudes reference routine `elp82b.f`.  It consumes the normalized JSON
produced by `normalize_elp82b.py`; the archival CDS VI/79 tables remain
unchanged.

The reference routine's independent variable is Julian Date TDB.  For many
near-Earth applications TT and TDB differ only slightly, but this evaluator
names the argument `jd_tdb` so the time scale is explicit.

Output rectangular coordinates are geocentric, in kilometers, referred to the
mean dynamical ecliptic and inertial equinox of J2000, matching the reference
Fortran routine.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.request import Request, urlopen
import argparse
import gzip
import json
import math
from typing import Any, Iterable


CDS_BASE = "https://cdsarc.cds.unistra.fr/ftp/VI/79"

# Local filenames expected by the rest of the Star Almanack tools.
AUX_FILES = ("ReadMe", "elp82b.f", "example.f", "elp82b.ps")

# CDS stores three of the auxiliary files gzip-compressed.  Bootstrap downloads
# the published .gz objects and expands them to the local filenames above.
AUX_DOWNLOADS = {
    "ReadMe": "ReadMe",
    "elp82b.f": "elp82b.f.gz",
    "example.f": "example.f.gz",
    "elp82b.ps": "elp82b.ps.gz",
}


def _download(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "Star-Almanack/1.0"})
    with urlopen(req, timeout=60) as response:
        dest.write_bytes(response.read())


def _download_gzip(url: str, dest: Path) -> None:
    req = Request(url, headers={"User-Agent": "Star-Almanack/1.0"})
    with urlopen(req, timeout=60) as response:
        compressed = response.read()
    dest.write_bytes(gzip.decompress(compressed))


def bootstrap(directory: Path) -> None:
    """Download and expand the official CDS VI/79 ELP2000-82B archive."""
    directory.mkdir(parents=True, exist_ok=True)

    for local_name, remote_name in AUX_DOWNLOADS.items():
        dest = directory / local_name
        if not dest.exists():
            print(f"fetch {remote_name}")
            url = f"{CDS_BASE}/{remote_name}"
            if remote_name.endswith(".gz"):
                _download_gzip(url, dest)
            else:
                _download(url, dest)

    for i in range(1, 37):
        name = f"ELP{i}"
        dest = directory / name
        if not dest.exists():
            print(f"fetch {name}")
            _download(f"{CDS_BASE}/{name}", dest)

    verify(directory)


def verify(directory: Path) -> None:
    """Verify that all 36 coefficient tables and reference files are present."""
    missing = []

    for i in range(1, 37):
        if not (directory / f"ELP{i}").exists():
            missing.append(f"ELP{i}")

    for name in AUX_FILES:
        if not (directory / name).exists():
            missing.append(name)

    if missing:
        raise SystemExit("Missing ELP2000-82B files: " + ", ".join(missing))

    print("Verification passed: all 36 coefficient tables and reference files are present.")


J2000 = 2451545.0
DAYS_PER_JULIAN_CENTURY = 36525.0
PI = math.pi
TWOPI = 2.0 * PI
DEG = PI / 180.0
ARCSEC_PER_RADIAN = 648000.0 / PI

# Reference constants from elp82b.f
ATH = 384747.9806743165
A0 = 384747.9806448954
AM = 0.074801329518
ALFA = 0.002571881335
DTASM = 2.0 * ALFA / (3.0 * AM)

# Mean lunar and terrestrial arguments, expressed in arcseconds as polynomial
# coefficients in Julian centuries from J2000.  These are converted to radians
# during initialization.
W1_ARCSEC = (785939.95571, 1732559343.73604, -5.8883, 0.006604, -0.00003169)
W2_ARCSEC = (300071.67475, 14643420.2632, -38.2776, -0.045047, 0.00021301)
W3_ARCSEC = (450160.39816, -6967919.3622, 6.3622, 0.007625, -0.00003586)
EARTH_ARCSEC = (361679.22059, 129597742.2758, -0.0202, 0.000009, 0.00000015)
PERI_ARCSEC = (370574.42753, 1161.2283, 0.5327, -0.000138, 0.0)

# Planetary mean longitudes: constant and linear terms, arcseconds.
PLANET_ARCSEC = (
    (908103.25986, 538101628.68898),   # Mercury
    (655127.28305, 210664136.43355),   # Venus
    (361679.22059, 129597742.2758),    # Earth
    (1279559.78866, 68905077.59284),   # Mars
    (123665.34212, 10925660.42861),    # Jupiter
    (180278.89694, 4399609.65932),     # Saturn
    (1130598.01841, 1542481.19393),    # Uranus
    (1095655.19575, 786550.32074),     # Neptune
)

PRECES_ARCSEC = 5029.0966

# DE200/LE200 fit corrections from elp82b.f.
DELNU_ARCSEC = +0.55604
DELE_ARCSEC = +0.01789
DELG_ARCSEC = -0.08066
DELNP_ARCSEC = -0.06424
DELEP_ARCSEC = -0.12879

# Precession matrix coefficients.
P1 = 0.10180391e-4
P2 = 0.47020439e-6
P3 = -0.5417367e-9
P4 = -0.2507948e-11
P5 = 0.463486e-14

Q1 = -0.113469002e-3
Q2 = 0.12372674e-6
Q3 = 0.1265417e-8
Q4 = -0.1371808e-11
Q5 = -0.320334e-14


def arcsec_to_rad(x: float) -> float:
    return x / ARCSEC_PER_RADIAN


def arcsec_poly_to_rad(coeffs: Iterable[float]) -> tuple[float, ...]:
    return tuple(arcsec_to_rad(x) for x in coeffs)


W1 = arcsec_poly_to_rad(W1_ARCSEC)
W2 = arcsec_poly_to_rad(W2_ARCSEC)
W3 = arcsec_poly_to_rad(W3_ARCSEC)
EARTH = arcsec_poly_to_rad(EARTH_ARCSEC)
PERI = arcsec_poly_to_rad(PERI_ARCSEC)
PLANETS = tuple((arcsec_to_rad(a0), arcsec_to_rad(a1)) for a0, a1 in PLANET_ARCSEC)
PRECES = arcsec_to_rad(PRECES_ARCSEC)

# The Fortran definitions are:
# delnu = +0.55604/rad/w(1,2)
# dele   = +0.01789/rad
# delg   = -0.08066/rad
# delnp  = -0.06424/rad/w(1,2)
# delep  = -0.12879/rad
DELNU = arcsec_to_rad(DELNU_ARCSEC) / W1[1]
DELE = arcsec_to_rad(DELE_ARCSEC)
DELG = arcsec_to_rad(DELG_ARCSEC)
DELNP = arcsec_to_rad(DELNP_ARCSEC) / W1[1]
DELEP = arcsec_to_rad(DELEP_ARCSEC)


def poly(coeffs: tuple[float, ...], t: float) -> float:
    total = 0.0
    power = 1.0
    for c in coeffs:
        total += c * power
        power *= t
    return total


@dataclass(frozen=True)
class ArgumentSet:
    t: tuple[float, float, float, float, float]
    w1: tuple[float, float, float, float, float]
    delaunay: tuple[
        tuple[float, float, float, float, float],
        tuple[float, float, float, float, float],
        tuple[float, float, float, float, float],
        tuple[float, float, float, float, float],
    ]
    zeta: tuple[float, float]
    planets: tuple[
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
        tuple[float, float],
    ]


@dataclass(frozen=True)
class LunarSpherical:
    longitude_rad: float
    latitude_rad: float
    distance_km: float


@dataclass(frozen=True)
class LunarRectangular:
    x_km: float
    y_km: float
    z_km: float


@dataclass(frozen=True)
class Evaluation:
    jd_tdb: float
    precision_rad: float
    spherical: LunarSpherical
    rectangular: LunarRectangular
    table_sums: tuple[float, ...]


def build_arguments(jd_tdb: float) -> ArgumentSet:
    tc = (jd_tdb - J2000) / DAYS_PER_JULIAN_CENTURY
    t = (1.0, tc, tc * tc, tc * tc * tc, tc * tc * tc * tc)

    # del(1)=W1-Earth+pi ; del(2)=Earth-Peri ;
    # del(3)=W1-W2 ; del(4)=W1-W3
    d1 = tuple(W1[i] - EARTH[i] for i in range(5))
    d1 = (d1[0] + PI, d1[1], d1[2], d1[3], d1[4])
    d2 = tuple(EARTH[i] - PERI[i] for i in range(5))
    d3 = tuple(W1[i] - W2[i] for i in range(5))
    d4 = tuple(W1[i] - W3[i] for i in range(5))

    zeta = (W1[0], W1[1] + PRECES)
    planets = PLANETS

    return ArgumentSet(
        t=t,
        w1=W1,
        delaunay=(d1, d2, d3, d4),
        zeta=zeta,
        planets=planets,
    )


def _sum_main_problem(
    file_number: int,
    records: list[dict[str, Any]],
    args: ArgumentSet,
    threshold: float,
) -> float:
    iv = (file_number - 1) % 3
    total = 0.0

    for rec in records:
        ilu = rec["ilu"]
        coef = list(rec["coef"])
        x0 = coef[0]

        if abs(x0) < threshold:
            continue

        tgv = coef[1] + DTASM * coef[5]

        if file_number == 3:
            coef[0] = coef[0] - 2.0 * coef[0] * DELNU / 3.0

        x = (
            coef[0]
            + tgv * (DELNP - AM * DELNU)
            + coef[2] * DELG
            + coef[3] * DELE
            + coef[4] * DELEP
        )

        phase = 0.0
        for k in range(5):
            tk = args.t[k]
            for i in range(4):
                phase += ilu[i] * args.delaunay[i][k] * tk

        if iv == 2:
            phase += PI / 2.0

        total += x * math.sin(math.fmod(phase, TWOPI))

    return total


def _sum_figure_tide(
    file_number: int,
    records: list[dict[str, Any]],
    args: ArgumentSet,
    threshold: float,
) -> float:
    total = 0.0

    for rec in records:
        x = rec["x"]
        if x < threshold:
            continue

        if 7 <= file_number <= 9 or 25 <= file_number <= 27:
            x *= args.t[1]
        elif 34 <= file_number <= 36:
            x *= args.t[2]

        phase = rec["pha"] * DEG
        iz = rec["iz"]
        ilu = rec["ilu"]

        for k in range(2):
            tk = args.t[k]
            phase += iz * args.zeta[k] * tk
            for i in range(4):
                phase += ilu[i] * args.delaunay[i][k] * tk

        total += x * math.sin(math.fmod(phase, TWOPI))

    return total


def _sum_planetary(
    file_number: int,
    records: list[dict[str, Any]],
    args: ArgumentSet,
    threshold: float,
) -> float:
    total = 0.0

    for rec in records:
        x = rec["x"]
        if x < threshold:
            continue

        if 13 <= file_number <= 15 or 19 <= file_number <= 21:
            x *= args.t[1]

        phase = rec["pha"] * DEG
        ipla = rec["ipla"]

        if file_number < 16:
            for k in range(2):
                tk = args.t[k]
                phase += (
                    ipla[8] * args.delaunay[0][k]
                    + ipla[9] * args.delaunay[2][k]
                    + ipla[10] * args.delaunay[3][k]
                ) * tk
                for i in range(8):
                    phase += ipla[i] * args.planets[i][k] * tk
        else:
            for k in range(2):
                tk = args.t[k]
                for i in range(4):
                    phase += ipla[i + 7] * args.delaunay[i][k] * tk
                for i in range(7):
                    phase += ipla[i] * args.planets[i][k] * tk

        total += x * math.sin(math.fmod(phase, TWOPI))

    return total


def _precess_to_j2000(
    longitude_rad: float,
    latitude_rad: float,
    distance_km: float,
    tc: float,
) -> LunarRectangular:
    x1 = distance_km * math.cos(latitude_rad)
    x2 = x1 * math.sin(longitude_rad)
    x1 = x1 * math.cos(longitude_rad)
    x3 = distance_km * math.sin(latitude_rad)

    pw = (P1 + P2 * tc + P3 * tc**2 + P4 * tc**3 + P5 * tc**4) * tc
    qw = (Q1 + Q2 * tc + Q3 * tc**2 + Q4 * tc**3 + Q5 * tc**4) * tc

    ra = 2.0 * math.sqrt(max(0.0, 1.0 - pw * pw - qw * qw))
    pwqw = 2.0 * pw * qw
    pw2 = 1.0 - 2.0 * pw * pw
    qw2 = 1.0 - 2.0 * qw * qw
    pwr = pw * ra
    qwr = qw * ra

    return LunarRectangular(
        x_km=pw2 * x1 + pwqw * x2 + pwr * x3,
        y_km=pwqw * x1 + qw2 * x2 - qwr * x3,
        z_km=-pwr * x1 + qwr * x2 + (pw2 + qw2 - 1.0) * x3,
    )


def load_normalized(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("model") != "ELP2000-82B":
        raise ValueError(f"{path}: expected model ELP2000-82B")
    tables = payload.get("tables")
    if not isinstance(tables, list) or len(tables) != 36:
        raise ValueError(f"{path}: expected 36 normalized tables")
    return payload


def evaluate(
    normalized: dict[str, Any],
    jd_tdb: float,
    precision_rad: float = 0.0,
) -> Evaluation:
    """
    Evaluate ELP2000-82B.

    `precision_rad` follows the reference Fortran truncation parameter.
    Use 0.0 to retain every normalized term.
    """
    args = build_arguments(jd_tdb)

    thresholds = (
        precision_rad * ARCSEC_PER_RADIAN,
        precision_rad * ARCSEC_PER_RADIAN,
        precision_rad * ATH,
    )

    accum = [0.0, 0.0, 0.0]
    table_sums: list[float] = []

    tables = normalized["tables"]
    for file_number, table in enumerate(tables, start=1):
        records = table["records"]
        iv = (file_number - 1) % 3
        threshold = thresholds[iv]

        if 1 <= file_number <= 3:
            contribution = _sum_main_problem(file_number, records, args, threshold)
        elif 10 <= file_number <= 21:
            contribution = _sum_planetary(file_number, records, args, threshold)
        else:
            contribution = _sum_figure_tide(file_number, records, args, threshold)

        accum[iv] += contribution
        table_sums.append(contribution)

    tc = args.t[1]

    mean_longitude = sum(args.w1[k] * args.t[k] for k in range(5))
    longitude = accum[0] / ARCSEC_PER_RADIAN + mean_longitude
    latitude = accum[1] / ARCSEC_PER_RADIAN
    distance = accum[2] * A0 / ATH

    rectangular = _precess_to_j2000(longitude, latitude, distance, tc)

    return Evaluation(
        jd_tdb=jd_tdb,
        precision_rad=precision_rad,
        spherical=LunarSpherical(
            longitude_rad=longitude,
            latitude_rad=latitude,
            distance_km=distance,
        ),
        rectangular=rectangular,
        table_sums=tuple(table_sums),
    )


def _print_evaluation(result: Evaluation) -> None:
    sph = result.spherical
    rect = result.rectangular
    print(f"JD(TDB): {result.jd_tdb:.9f}")
    print(f"precision: {result.precision_rad:.12g} rad")
    print(f"longitude: {math.degrees(sph.longitude_rad) % 360.0:.12f} deg")
    print(f"latitude:  {math.degrees(sph.latitude_rad):.12f} deg")
    print(f"distance:  {sph.distance_km:.6f} km")
    print("J2000 ecliptic rectangular:")
    print(f"  X = {rect.x_km:.6f} km")
    print(f"  Y = {rect.y_km:.6f} km")
    print(f"  Z = {rect.z_km:.6f} km")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Star Almanack ELP2000-82B lunar engine.")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap", help="download official CDS VI/79 model files")
    p.add_argument("directory", type=Path)

    p = sub.add_parser("verify", help="verify archive files are present")
    p.add_argument("directory", type=Path)

    p = sub.add_parser("arguments", help="print the ELP argument set for JD(TDB)")
    p.add_argument("jd_tdb", type=float)

    p = sub.add_parser("evaluate", help="evaluate normalized ELP2000-82B coefficients")
    p.add_argument("normalized_json", type=Path)
    p.add_argument("jd_tdb", type=float)
    p.add_argument(
        "--precision",
        type=float,
        default=0.0,
        help="reference truncation level in radians (default: 0, retain all terms)",
    )

    args = ap.parse_args(argv)

    if args.command == "bootstrap":
        bootstrap(args.directory)
    elif args.command == "verify":
        verify(args.directory)
    elif args.command == "arguments":
        a = build_arguments(args.jd_tdb)
        print(a)
    elif args.command == "evaluate":
        normalized = load_normalized(args.normalized_json)
        result = evaluate(normalized, args.jd_tdb, args.precision)
        _print_evaluation(result)


if __name__ == "__main__":
    main()
