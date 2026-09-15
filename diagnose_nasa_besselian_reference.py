#!/usr/bin/env python3
"""
Independent NASA Besselian-reference diagnostic.

Purpose
-------
Verify that NASA's published polynomial Besselian elements reproduce NASA's
published instant of greatest eclipse without using the Star Almanack eclipse
engine. This is a control calculation for isolating the eclipse-geometry layer.

Reference case
--------------
Total solar eclipse of 2026-08-12.
NASA Besselian elements page:
https://eclipse.gsfc.nasa.gov/SEsearch/SEdata.php?Ecl=20260812

For the fundamental-plane shadow-axis coordinates x(t), y(t), greatest eclipse
occurs at the minimum geocentric axis distance sqrt(x^2 + y^2). Therefore the
stationary condition is:

    x dx/dt + y dy/dt = 0

The published elements are polynomials in hours from t0 = 18.000 TDT.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot


@dataclass(frozen=True)
class Polynomial:
    c0: float
    c1: float
    c2: float = 0.0
    c3: float = 0.0

    def value(self, t: float) -> float:
        return self.c0 + self.c1 * t + self.c2 * t * t + self.c3 * t * t * t

    def derivative(self, t: float) -> float:
        return self.c1 + 2.0 * self.c2 * t + 3.0 * self.c3 * t * t


X = Polynomial(0.4755140, 0.5189249, -0.0000773, -0.0000080)
Y = Polynomial(0.7711830, -0.2301680, -0.0001246, 0.0000038)
T0_TDT_HOURS = 18.0
NASA_GREATEST_TDT_SECONDS = 17 * 3600 + 47 * 60 + 6
NASA_OLDER_GREATEST_TDT_SECONDS = 17 * 3600 + 47 * 60 + 5.2


def stationary(t: float) -> float:
    return X.value(t) * X.derivative(t) + Y.value(t) * Y.derivative(t)


def solve_bisection(lo: float, hi: float, iterations: int = 100) -> float:
    flo = stationary(lo)
    fhi = stationary(hi)
    if flo == 0.0:
        return lo
    if fhi == 0.0:
        return hi
    if flo * fhi > 0.0:
        raise RuntimeError("stationary condition is not bracketed")

    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        fm = stationary(mid)
        if flo * fm <= 0.0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm
    return (lo + hi) / 2.0


def hms(total_seconds: float) -> str:
    h = int(total_seconds // 3600)
    total_seconds -= h * 3600
    m = int(total_seconds // 60)
    s = total_seconds - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def main() -> int:
    # The published elements are valid for 15 <= TDT <= 21, i.e. -3 <= t <= +3.
    # The known root is near t = -0.215 h; use a deliberately broad bracket.
    t = solve_bisection(-1.0, 1.0)
    greatest_tdt_seconds = (T0_TDT_HOURS + t) * 3600.0
    rho = hypot(X.value(t), Y.value(t))

    residual_current = greatest_tdt_seconds - NASA_GREATEST_TDT_SECONDS
    residual_older = greatest_tdt_seconds - NASA_OLDER_GREATEST_TDT_SECONDS

    print("NASA BESSELIAN REFERENCE CONTROL — 2026-08-12")
    print("------------------------------------------------")
    print(f"stationary t from 18:00 TDT : {t:+.12f} h")
    print(f"Besselian greatest TDT       : {hms(greatest_tdt_seconds)}")
    print(f"minimum axis distance gamma  : {rho:.7f} Earth radii")
    print(f"NASA current published TDT   : 17:47:06.000")
    print(f"residual vs current NASA     : {residual_current:+.3f} s")
    print(f"NASA older published TDT     : 17:47:05.200")
    print(f"residual vs older NASA       : {residual_older:+.3f} s")
    print()

    # Passing criterion: published polynomial elements should reproduce the
    # published greatest-eclipse instant to within their displayed precision.
    if abs(residual_current) <= 1.0:
        print("PASS: NASA's published Besselian polynomials reproduce NASA greatest eclipse.")
        return 0

    print("FAIL: published Besselian control misses NASA by more than 1 second.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
