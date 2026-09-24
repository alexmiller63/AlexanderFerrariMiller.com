#!/usr/bin/env python3
"""Stable GitHub Actions launcher for the Planet Finder generator."""
from __future__ import annotations
from datetime import date
import os
import subprocess
import sys

def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is required")
    return value

def positive_int(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer") from None
    if number <= 0:
        raise SystemExit(f"{name} must be positive")
    return str(number)

def nonnegative_int(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    try:
        number = int(value)
    except ValueError:
        raise SystemExit(f"{name} must be an integer") from None
    if number < 0:
        raise SystemExit(f"{name} must be zero or greater")
    return str(number)

def iso_week_date(year_name: str, week_name: str) -> date:
    year = int(required(year_name))
    week = int(required(week_name))
    try:
        return date.fromisocalendar(year, week, 1)
    except ValueError as exc:
        raise SystemExit(f"Invalid ISO week: {year}-W{week:02d}: {exc}") from None

def main() -> None:
    start = iso_week_date("PLANET_FINDER_START_YEAR", "PLANET_FINDER_START_WEEK")
    end = iso_week_date("PLANET_FINDER_END_YEAR", "PLANET_FINDER_END_WEEK")
    if end < start:
        raise SystemExit("End ISO week must not precede start ISO week")
    env = os.environ.copy()
    env["PLANET_FINDER_CANDIDATES"] = positive_int("PLANET_FINDER_CANDIDATES", "5")
    env["PLANET_FINDER_MAX_NODE_CANDIDATES"] = positive_int("PLANET_FINDER_MAX_NODE_CANDIDATES", "200")
    env["PLANET_FINDER_MAX_SECONDS"] = positive_int("PLANET_FINDER_MAX_SECONDS", "180")
    env["PLANET_FINDER_DIAGNOSTIC_LEVEL"] = nonnegative_int("PLANET_FINDER_DIAGNOSTIC_LEVEL", "1")
    print(
        "Planet Finder launcher: "
        f"{start.isocalendar().year}-W{start.isocalendar().week:02d} through "
        f"{end.isocalendar().year}-W{end.isocalendar().week:02d}; "
        f"candidates={env['PLANET_FINDER_CANDIDATES']}; "
        f"body-cap={env['PLANET_FINDER_MAX_NODE_CANDIDATES']}; "
        f"seconds/mode={env['PLANET_FINDER_MAX_SECONDS']}; "
        f"diagnostic={env['PLANET_FINDER_DIAGNOSTIC_LEVEL']}",
        flush=True,
    )
    subprocess.run(
        [sys.executable, "tools/populate_ephemeris_planet_finder_by_date.py",
         start.isoformat(), end.isoformat()],
        check=True,
        env=env,
    )

if __name__ == "__main__":
    main()
