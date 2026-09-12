#!/usr/bin/env python3
"""Populate constellation-center events for requested Almanack years.

Alpha/beta star events are owned by the fixed-sky population step; this step
must not create duplicate alpha/beta events.

A constellation center recurs once per astronomical Aries-to-Aries cycle, not
necessarily once per ISO week-numbering year. A 52-week ISO year can therefore
contain zero occurrences for an identity near the year boundary, while a
53-week ISO year can contain two. The generator must preserve those real
occurrences rather than forcing a one-per-ISO-year invariant.
"""
from __future__ import annotations

import csv
import datetime as dt
import re
import statistics
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from star_almanack_astronomy import (
    best_visibility_occurrences_for_iso_year,
    declination_band,
    season_for,
)
from star_almanack_objects import HTML_AID, observing_aid_for_magnitude

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
DEFAULT_YEARS = (2025, 2026, 2027)
CENTROID_SNAPSHOT = SRC / "constellation-observance-2026.csv"
BAYER_STARS = SRC / "expanded-bayer-stars.csv"
MARTZ_FIGURES = Path("/tmp/constellation_lines_iau.dat")
HYG_CATALOG = Path("/tmp/hygdata_v41.csv")

HYG_HIPPARCOS_SUPPLEMENTS = {"55203": 3.79}

FRONT_MATTER = {
    "Men": {"rule": "alpha_beta_mean"},
    "Mic": {"rule": "alpha_beta_mean"},
    "Ser": {"rule": "martz_caput_cauda"},
}

SERPENS_COMPONENTS = (
    {
        "name": "Serpens Caput",
        "figure_part": "Caput",
        "figure_key": "SerpensB",
        "centroid_ra_h": "15.695035",
        "centroid_dec_deg": "9.909187",
        "sampled_area_sq_deg": "428.632",
        "centroid_step_deg": "0.100",
    },
    {
        "name": "Serpens Cauda",
        "figure_part": "Cauda",
        "figure_key": "SerpensA",
        "centroid_ra_h": "18.162525",
        "centroid_dec_deg": "-6.367014",
        "sampled_area_sq_deg": "208.365",
        "centroid_step_deg": "0.100",
    },
)


def requested_years() -> tuple[int, ...]:
    if len(sys.argv) == 1:
        return DEFAULT_YEARS
    try:
        years = tuple(dict.fromkeys(int(x) for x in sys.argv[1:]))
    except ValueError as exc:
        raise SystemExit("Years must be integers, e.g. 2025 2026 2027") from exc
    if any(y < 1 for y in years):
        raise SystemExit("Years must be positive integers")
    return years


def read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9]", "", text.lower())


def alpha_beta_magnitudes() -> dict[str, dict[str, list[float]]]:
    values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for row in read_csv(BAYER_STARS):
        con = (row.get("con") or "").strip()
        greek = (row.get("greek") or "").strip()
        raw_mag = (row.get("mag") or "").strip()
        if not con or greek not in {"α", "β"} or not raw_mag:
            continue
        try:
            values[con][greek].append(float(raw_mag))
        except ValueError:
            pass
    return values


def alpha_beta_mean(con: str, values: dict[str, dict[str, list[float]]]) -> float:
    pair = values.get(con, {})
    if not pair.get("α") or not pair.get("β"):
        raise SystemExit(f"Front-matter alpha/beta rule cannot be resolved for {con}")
    return statistics.mean((min(pair["α"]), min(pair["β"])))


def read_hyg(path: Path) -> dict[str, float]:
    if not path.is_file():
        raise SystemExit(f"Missing pinned HYG catalog: {path}")
    by_hip: dict[str, float] = {}
    for row in read_csv(path):
        raw_mag = (row.get("mag") or "").strip()
        hip = (row.get("hip") or "").strip()
        if not raw_mag or not hip:
            continue
        try:
            by_hip[str(int(float(hip)))] = float(raw_mag)
        except ValueError:
            continue
    for hip, mag in HYG_HIPPARCOS_SUPPLEMENTS.items():
        by_hip.setdefault(hip, mag)
    return by_hip


def read_martz_figures(path: Path) -> dict[str, list[str]]:
    if not path.is_file():
        raise SystemExit(f"Missing pinned Martz/MacRobert figure data: {path}")
    figures: dict[str, list[str]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("* "):
            current = line[2:].strip()
            figures.setdefault(current, [])
            continue
        if current is None or not line.startswith("["):
            continue
        for hip in re.findall(r'"(\d+)\*?"', line):
            if hip not in figures[current]:
                figures[current].append(hip)
    return figures


def median_figure_magnitude(figure_key, figures, by_hip) -> float:
    hips = figures.get(figure_key, [])
    if not hips:
        raise SystemExit(f"No member stars enumerated for adopted figure {figure_key}")
    missing = [hip for hip in hips if hip not in by_hip]
    if missing:
        raise SystemExit(
            "Pinned HYG/Hipparcos magnitude set lacks V magnitudes for "
            f"{figure_key} member HIP(s): " + ", ".join(missing)
        )
    return statistics.median(by_hip[hip] for hip in hips)


def normal_figure_key(name: str, figures: dict[str, list[str]]) -> str:
    wanted = normalize_name(name)
    matches = [key for key in figures if normalize_name(key) == wanted]
    if len(matches) != 1:
        raise SystemExit(f"Could not uniquely match {name} to adopted Martz/MacRobert figure data")
    return matches[0]


def constellation_magnitude(row, alpha_beta, figures, by_hip) -> float:
    con = row["abbr"].strip()
    front = FRONT_MATTER.get(con)
    if front:
        rule = front["rule"]
        if rule == "alpha_beta_mean":
            return alpha_beta_mean(con, alpha_beta)
        if rule == "martz_caput_cauda":
            part = row.get("figure_part", "").strip()
            component = next((x for x in SERPENS_COMPONENTS if x["figure_part"] == part), None)
            if component is None:
                raise SystemExit(f"Serpens row lacks a recognized Caput/Cauda component: {part!r}")
            return median_figure_magnitude(component["figure_key"], figures, by_hip)
        raise SystemExit(f"Unknown front-matter constellation rule for {con}: {rule}")
    key = normal_figure_key(row["name"], figures)
    return median_figure_magnitude(key, figures, by_hip)


def visibility_html(mag: float) -> str:
    aid = observing_aid_for_magnitude(str(mag))
    if aid is None:
        raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
    return f'<span class="visibility-magnitude">{HTML_AID[aid]} V {mag:.1f}</span>'


def make_rows(source: dict[str, str], iso_year: int) -> list[dict[str, str]]:
    rows = []
    for instant, day in best_visibility_occurrences_for_iso_year(
        float(source["centroid_ra_h"]), iso_year
    ):
        rows.append({
            "name": source["name"],
            "abbr": source["abbr"],
            "figure_part": source.get("figure_part", ""),
            "centroid_ra_h": source["centroid_ra_h"],
            "centroid_dec_deg": source["centroid_dec_deg"],
            "sampled_area_sq_deg": source["sampled_area_sq_deg"],
            "centroid_step_deg": source["centroid_step_deg"],
            "center_best_instant_utc": instant.strftime("%Y-%m-%d %H:%M"),
            "center_best_date": day.isoformat(),
            "center_iso": iso_label(day),
        })
    return rows


def source_rows() -> list[dict[str, str]]:
    snaps = read_csv(CENTROID_SNAPSHOT)
    if len(snaps) != 88:
        raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
    sources = []
    for snap in snaps:
        if snap["abbr"].strip() != "Ser":
            sources.append(snap)
        else:
            for component in SERPENS_COMPONENTS:
                sources.append({**component, "abbr": "Ser"})
    if len(sources) != 89:
        raise SystemExit(f"Expected 89 center identities after splitting Serpens, got {len(sources)}")
    return sources


def build_rows(year: int) -> list[dict[str, str]]:
    rows = []
    for source in source_rows():
        rows.extend(make_rows(source, year))
    if not rows:
        raise SystemExit(f"No constellation-center occurrences fall in ISO year {year}")
    for row in rows:
        if dt.date.fromisoformat(row["center_best_date"]).isocalendar().year != year:
            raise SystemExit(f"Out-of-year constellation occurrence leaked into {year}: {row}")
    return rows


def write_csv(year: int, rows: list[dict[str, str]]) -> None:
    out = SRC / "generated" / f"constellation-observance-{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def event_map(rows):
    events = defaultdict(list)
    alpha_beta = alpha_beta_magnitudes()
    figures = read_martz_figures(MARTZ_FIGURES)
    by_hip = read_hyg(HYG_CATALOG)
    for row in rows:
        day = dt.date.fromisoformat(row["center_best_date"])
        cls = f"{declination_band(row['centroid_dec_deg'])} {season_for(day)}"
        mag = constellation_magnitude(row, alpha_beta, figures, by_hip)
        vis = visibility_html(mag)
        events[day].append(f"{row['name']} center — Constellation — {vis} — {cls}")
    return events


BARE_LEGACY_STAR = re.compile(r'^✦ (?:α|β) star — .+$')
LEGACY_CENTER = re.compile(r'^(?:✦ )?.*? (?:geometric-center observance|center)(?: —)? .+$')


def clean_target_event_cell(cell: str) -> list[str]:
    if cell in ("", "—"):
        return []
    kept = []
    for item in cell.split("<br>"):
        stripped = item.strip()
        if not stripped:
            continue
        if BARE_LEGACY_STAR.match(stripped):
            continue
        if " — Constellation — " in stripped:
            continue
        if "geometric-center observance" in stripped:
            continue
        if LEGACY_CENTER.match(stripped) and " — Asterism — " not in stripped:
            continue
        kept.append(item)
    return kept


def page_for_date(root: Path, day: dt.date) -> Path:
    iso = day.isocalendar()
    return root / str(iso.year) / f"W{iso.week:02d}" / "index.html"


def row_pattern(day: dt.date) -> re.Pattern[str]:
    date_text = day.strftime("%a, %b %d, %Y")
    return re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")


def inject(root: Path, events) -> int:
    changed = 0
    events_by_page = defaultdict(list)
    for day, vals in events.items():
        events_by_page[page_for_date(root, day)].append((day, vals))
    for page, dated_events in sorted(events_by_page.items(), key=lambda x: str(x[0])):
        if not page.exists():
            raise SystemExit(f"Missing weekly page for constellation event(s): {page}")
        text = page.read_text(encoding="utf-8")
        original = text
        for day, vals in dated_events:
            match = row_pattern(day).search(text)
            if not match:
                raise SystemExit(f"Could not find calendar row for {day} in {page}")
            keep = clean_target_event_cell(match.group(2))
            for value in vals:
                if value not in keep:
                    keep.append(value)
            replacement = "<br>".join(keep) if keep else "—"
            text = text[:match.start(2)] + replacement + text[match.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def validate(root: Path, events) -> None:
    for day, vals in events.items():
        page = page_for_date(root, day)
        if not page.exists():
            raise SystemExit(f"Missing weekly page while validating constellation event(s): {page}")
        text = page.read_text(encoding="utf-8")
        match = row_pattern(day).search(text)
        if not match:
            raise SystemExit(f"Could not find calendar row for {day} while validating {page}")
        items = match.group(2).split("<br>") if match.group(2) not in ("", "—") else []
        for value in vals:
            count = items.count(value)
            if count != 1:
                raise SystemExit(
                    f"{root}: expected {value!r} exactly once on {day} in {page}, found {count}"
                )


def main() -> None:
    for year in requested_years():
        rows = build_rows(year)
        write_csv(year, rows)
        events = event_map(rows)
        source_changed = inject(SOURCE_SITE, events)
        public_changed = inject(PUBLIC, events)
        validate(SOURCE_SITE, events)
        validate(PUBLIC, events)
        identities = {(row["abbr"], row.get("figure_part", "")) for row in rows}
        print(
            f"{year}: {len(rows)} constellation-center ISO-year occurrence(s) across "
            f"{len(identities)} represented identities; updated {source_changed} source + "
            f"{public_changed} public pages"
        )


if __name__ == "__main__":
    main()
