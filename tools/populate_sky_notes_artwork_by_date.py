#!/usr/bin/env python3
"""Create/recreate Sky Note artwork for ISO weeks in an inclusive date range.

This generator owns only Sky Note artwork and artwork embeds. It must not modify
Calendar, Ephemeris, Planet Finder, or Sky Note prose.
"""
from __future__ import annotations

import hashlib
import re
import runpy
from pathlib import Path

from iso_date_range import parse_range_args

ROOT = Path(__file__).resolve().parents[1]


def digest(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sky_note_prose_signature(path: Path) -> tuple[str, ...] | None:
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    marker = "<h3>Sky Note</h3>"
    start = text.find(marker)
    if start < 0:
        return None
    body_start = start + len(marker)
    next_heading = re.search(r"<h[23]>.*?</h[23]>", text[body_start:], flags=re.S)
    end = body_start + next_heading.start() if next_heading else text.find("</main>", body_start)
    if end < 0:
        end = len(text)
    return tuple(re.findall(r"<p>.*?</p>", text[body_start:end], flags=re.S))


def w41_owned_elsewhere_snapshot() -> tuple[dict[str, str | None], tuple[str, ...] | None]:
    week = ROOT / "almanack" / "2026" / "W41"
    finder_dir = week / "finders"
    hashes = {
        name: digest(finder_dir / name)
        for name in (
            "planet-finder-greek-symbols.svg",
            "planet-finder-latin.svg",
            "planet-finder-mixed-learner.svg",
        )
    }
    return hashes, sky_note_prose_signature(week / "index.html")


def generate_week(year: int, week: int) -> bool:
    key = f"{year}-W{week:02d}"

    if year == 2026 and week == 41:
        from recreate_w41_sky_note_artwork import main as recreate_w41
        before = w41_owned_elsewhere_snapshot()
        recreate_w41()
        after = w41_owned_elsewhere_snapshot()
        if before != after:
            raise RuntimeError(
                "W41 Sky Note artwork recreation changed Planet Finder assets or Sky Note prose; "
                "ownership boundary violated"
            )
        print(f"Recreated preserved Sky Note artwork fixture for ISO {key}; Planet Finder and prose unchanged")
        return True

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

    print(f"ISO {key}: no Sky Note artwork specification; prose is left unchanged")
    return False


def main() -> None:
    start, end, weeks = parse_range_args("Populate Star Almanack Sky Notes artwork by inclusive ISO date range")
    generated = 0
    for item in weeks:
        generated += int(generate_week(item.year, item.week))
    print(f"Sky Notes artwork complete for {start.isoformat()} through {end.isoformat()}: {generated} ISO weeks generated/recreated")


if __name__ == "__main__":
    main()
