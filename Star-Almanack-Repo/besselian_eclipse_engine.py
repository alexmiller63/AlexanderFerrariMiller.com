#!/usr/bin/env python3
"""Star Almanack production Besselian greatest-eclipse backend.

This module deliberately keeps the production search independent of the
validation catalog.  It computes the minimum distance of the lunar shadow axis
from the center of the Besselian fundamental plane over a UTC civil day.

Third-party dependency
----------------------

The Besselian element calculation is provided by ``eclipse-calc``:

    https://github.com/lkangas/eclipse-calc
    pinned revision: 23853a8f9e0d1a25e026203207aca16de1d7bb31

``eclipse-calc`` is MIT licensed, Copyright (c) 2026 komakallio.  Star
Almanack's complete retained notice is in ``THIRD-PARTY-LICENSES.md``.  The
upstream package is imported rather than copied into this file.

Ephemeris
---------

A JPL SPK kernel path is supplied by the caller.  The validated production
configuration uses DE440s.  Kernel acquisition/caching belongs to the build or
runtime environment; this module never downloads data implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from skyfield.api import load, load_file
from eclipse_calc.elements import bessels_at

DAY_SECONDS = 86_400.0
DEFAULT_GRID_SECONDS = 600.0
DEFAULT_REFINE_HALF_WINDOW_SECONDS = 1_200.0


@dataclass(frozen=True)
class BesselianGreatestEclipse:
    date_utc: str
    greatest_utc: str
    greatest_seconds_utc: float
    gamma: float
    x: float
    y: float
    l1: float
    l2: float


class BesselianEclipseEngine:
    """Compute greatest-eclipse geometry from ephemeris-direct Besselian elements."""

    def __init__(self, kernel_path: str | Path) -> None:
        self.kernel_path = Path(kernel_path)
        if not self.kernel_path.is_file():
            raise FileNotFoundError(self.kernel_path)
        self._timescale = load.timescale(builtin=True)
        self._ephemeris = load_file(str(self.kernel_path))

    def _axis_distance_squared(self, t) -> float:
        row = bessels_at(t, self._ephemeris).iloc[0]
        return float(row.x * row.x + row.y * row.y)

    def find_greatest_eclipse(
        self,
        date_utc: str,
        *,
        grid_seconds: float = DEFAULT_GRID_SECONDS,
        refine_half_window_seconds: float = DEFAULT_REFINE_HALF_WINDOW_SECONDS,
    ) -> BesselianGreatestEclipse:
        """Return the day's reference-free Besselian shadow-axis minimum.

        ``date_utc`` must be ``YYYY-MM-DD``.  No published eclipse time is used
        as a seed.  A coarse full-day search finds the candidate minimum, then
        a bounded scalar minimization refines it to millisecond-scale timing.
        """
        year, month, day = map(int, date_utc.split("-"))
        base = self._timescale.utc(year, month, day, 0, 0, 0)

        coarse_seconds = np.arange(0.0, DAY_SECONDS + 1.0, grid_seconds)
        coarse_times = base + coarse_seconds / DAY_SECONDS
        elements = bessels_at(coarse_times, self._ephemeris)
        q = elements["x"].to_numpy() ** 2 + elements["y"].to_numpy() ** 2
        index = int(np.argmin(q))
        center = float(coarse_seconds[index])

        lo = max(0.0, center - refine_half_window_seconds)
        hi = min(DAY_SECONDS, center + refine_half_window_seconds)
        result = minimize_scalar(
            lambda seconds: self._axis_distance_squared(
                base + float(seconds) / DAY_SECONDS
            ),
            bounds=(lo, hi),
            method="bounded",
            options={"xatol": 0.001},
        )
        if not result.success:
            raise RuntimeError(
                f"Besselian greatest-eclipse minimization failed for {date_utc}: "
                f"{result.message}"
            )

        seconds = float(result.x)
        t_best = base + seconds / DAY_SECONDS
        row = bessels_at(t_best, self._ephemeris).iloc[0]
        x = float(row.x)
        y = float(row.y)
        gamma = float(np.hypot(x, y))

        dt = t_best.utc_datetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        greatest_utc = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        return BesselianGreatestEclipse(
            date_utc=date_utc,
            greatest_utc=greatest_utc,
            greatest_seconds_utc=seconds,
            gamma=gamma,
            x=x,
            y=y,
            l1=float(row.l1),
            l2=float(row.l2),
        )


def _main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date_utc", help="UTC civil date, YYYY-MM-DD")
    parser.add_argument("kernel", help="Path to a JPL SPK kernel, e.g. de440s.bsp")
    args = parser.parse_args()

    event = BesselianEclipseEngine(args.kernel).find_greatest_eclipse(args.date_utc)
    print(event.greatest_utc)
    print(f"gamma={event.gamma:.9f}")
    print(f"x={event.x:.9f} y={event.y:.9f} l1={event.l1:.9f} l2={event.l2:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
