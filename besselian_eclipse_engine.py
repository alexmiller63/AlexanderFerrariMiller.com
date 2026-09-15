#!/usr/bin/env python3
"""Star Almanack production Besselian greatest-eclipse backend.

This module deliberately keeps the production search independent of the
validation catalog. It computes the minimum distance of the lunar shadow axis
from the center of the Besselian fundamental plane over a UTC civil day.

Time architecture
-----------------

UTC is used only to define the requested civil-day search window and to render
the published result. The astronomical solution is represented canonically as
JDTDB. Skyfield Time objects are constructed from JDTDB values only at the
library boundary required by the Besselian/SPK routines.

The bounded scalar minimizer does not operate directly on the large absolute
Julian-Date value. SciPy's bounded method includes a floating-point relative
term in its stopping criterion; at JD ~= 2.4 million that term is large enough
to degrade a millisecond-scale search by tens or hundreds of seconds. Instead,
the minimizer uses a small day offset from the UTC-day's starting JDTDB and the
objective immediately reconstructs the absolute JDTDB. This preserves JDTDB as
the astronomical coordinate while avoiding loss of numerical resolution.

Third-party dependency
----------------------

The Besselian element calculation is provided by ``eclipse-calc``:

    https://github.com/lkangas/eclipse-calc
    pinned revision: 23853a8f9e0d1a25e026203207aca16de1d7bb31

``eclipse-calc`` is MIT licensed, Copyright (c) 2026 komakallio. Star
Almanack's complete retained notice is in ``THIRD-PARTY-LICENSES.md``. The
upstream package is imported rather than copied into this file.

Ephemeris
---------

A JPL SPK kernel path is supplied by the caller. The validated production
configuration uses DE440s. Kernel acquisition/caching belongs to the build or
runtime environment; this module never downloads data implicitly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
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
    greatest_jd_tdb: float
    greatest_utc: str
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

    def _time_from_jd_tdb(self, jd_tdb: float):
        """Skyfield boundary conversion from canonical JDTDB to Time."""
        return self._timescale.tdb_jd(float(jd_tdb))

    def _axis_distance_squared_jd_tdb(self, jd_tdb: float) -> float:
        t = self._time_from_jd_tdb(jd_tdb)
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

        ``date_utc`` must be ``YYYY-MM-DD``. No published eclipse time is used
        as a seed. UTC defines only the civil-day bounds. The coarse search is
        sampled in JDTDB. The bounded refinement uses a small offset in TDB days
        from ``start_jd_tdb`` and reconstructs absolute JDTDB for each objective
        evaluation, avoiding the large-JD tolerance problem in SciPy's bounded
        minimizer.
        """
        year, month, day = map(int, date_utc.split("-"))
        utc_start = self._timescale.utc(year, month, day, 0, 0, 0)
        utc_stop = utc_start + 1.0
        start_jd_tdb = float(utc_start.tdb)
        stop_jd_tdb = float(utc_stop.tdb)

        step_days = grid_seconds / DAY_SECONDS
        coarse_jd_tdb = np.arange(
            start_jd_tdb,
            stop_jd_tdb + step_days * 0.5,
            step_days,
        )
        coarse_times = self._timescale.tdb_jd(coarse_jd_tdb)
        elements = bessels_at(coarse_times, self._ephemeris)
        q = elements["x"].to_numpy() ** 2 + elements["y"].to_numpy() ** 2
        index = int(np.argmin(q))
        center_jd_tdb = float(coarse_jd_tdb[index])

        half_window_days = refine_half_window_seconds / DAY_SECONDS
        lo_jd_tdb = max(start_jd_tdb, center_jd_tdb - half_window_days)
        hi_jd_tdb = min(stop_jd_tdb, center_jd_tdb + half_window_days)
        lo_offset_days = lo_jd_tdb - start_jd_tdb
        hi_offset_days = hi_jd_tdb - start_jd_tdb

        def objective_offset_days(offset_days: float) -> float:
            return self._axis_distance_squared_jd_tdb(
                start_jd_tdb + float(offset_days)
            )

        result = minimize_scalar(
            objective_offset_days,
            bounds=(lo_offset_days, hi_offset_days),
            method="bounded",
            options={"xatol": 0.001 / DAY_SECONDS},
        )
        if not result.success:
            raise RuntimeError(
                f"Besselian greatest-eclipse minimization failed for {date_utc}: "
                f"{result.message}"
            )

        greatest_jd_tdb = start_jd_tdb + float(result.x)
        t_best = self._time_from_jd_tdb(greatest_jd_tdb)
        row = bessels_at(t_best, self._ephemeris).iloc[0]
        x = float(row.x)
        y = float(row.y)
        gamma = float(np.hypot(x, y))

        # Publication conversion happens once, after the astronomical solution.
        dt = t_best.utc_datetime()
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        greatest_utc = dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        return BesselianGreatestEclipse(
            date_utc=date_utc,
            greatest_jd_tdb=greatest_jd_tdb,
            greatest_utc=greatest_utc,
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
    print(f"JDTDB={event.greatest_jd_tdb:.12f}")
    print(event.greatest_utc)
    print(f"gamma={event.gamma:.9f}")
    print(f"x={event.x:.9f} y={event.y:.9f} l1={event.l1:.9f} l2={event.l2:.9f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
