#!/usr/bin/env python3
"""Create/recreate Sky Note artwork for ISO weeks in an inclusive date range.

This generator owns only Sky Note artwork and artwork embeds. Model work such as
W35 and W41 is preserved separately for reference; no ISO week is special here.
It must not modify Calendar, Ephemeris, Planet Finder, or Sky Note prose.
"""
from __future__ import annotations

import runpy
from pathlib import Path

from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]


def generate_week(year: int, week: int) -> bool:
    key = f"{year}-W{week:02d}"
    script = ROOT / "tools" / "sky-notes-artwork" / f"{key}.py"

    if script.exists():
        runpy.run_path(str(script), run_name="__main__")
        print(f"Generated Sky Note artwork for ISO {key} using {script.relative_to(ROOT)}")
        return True

    manifest = ROOT / "Star-Almanack-Repo" / "sky-notes-artwork" / str(year) / f"W{week:02d}" / "manifest.json"
    if manifest.exists():
        raise RuntimeError(
            f"Artwork manifest exists for ISO {key} but no generator exists at "
            f"tools/sky-notes-artwork/{key}.py"
        )

    print(f"ISO {key}: no Sky Note artwork specification; no artwork generated")
    return False


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Sky Notes artwork by inclusive ISO date range")
    generated = 0
    for item in weeks:
        generated += int(generate_week(item.year, item.week))
    print(f"Sky Notes artwork complete for {start.isoformat()} through {end.isoformat()}: {generated} ISO weeks generated/recreated")


if __name__ == "__main__":
    main()
