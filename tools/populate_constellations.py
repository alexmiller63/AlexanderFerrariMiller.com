#!/usr/bin/env python3
"""Populate constellation-center events for requested Almanack years.

Alpha/beta star events are owned by the fixed-sky population step;
this step must not create duplicate alpha/beta events.

Constellation-center visibility is an observer-facing property of the adopted
constellation figure, not a physical magnitude of the geometric center.  The
normal rule is the median V magnitude of the unique stars in the adopted
Martz-Kohl / MacRobert figure.  Figure membership comes from the pinned IAU
stick-figure dataset used by the Martz-Kohl presentation; stellar V magnitudes
come from the pinned HYG catalog used elsewhere by the Almanack.

Explicit front-matter exceptions:

* Mensa and Microscopium have no Martz-Kohl Stars-and-Sticks figure.  For each,
  use the arithmetic mean of its alpha and beta V magnitudes.
* Serpens is one IAU constellation but has two adopted figures.  Caput and
  Cauda are emitted separately, each with its own IAU-region centroid,
  figure-member median V magnitude, observing aid, declination band, and
  season.

Norma and Telescopium are ordinary figure-median cases: both have explicit
member lists in the adopted MacRobert/IAU data, and Martz-Kohl publishes a
Stars-and-Sticks figure for Telescopium.  There is deliberately no
brightest-star or alpha/beta fallback for ordinary constellations.  Missing
figure membership is a source-data error that must be resolved explicitly
rather than silently changing the visibility rule.
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

from star_almanack_astronomy import best_visibility, declination_band, season_for
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

# Explicit front matter.  Martz-Kohl does not publish Stars-and-Sticks figures
# for Mensa or Microscopium, so those two use the same documented alpha/beta
# mean fallback.  Serpens component centroids were calculated with the same
# 0.1-degree spherical-area sampling method used for the 88-constellation
# snapshot, but on the two official IAU Serpens boundary patches separately.
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


def iso_label(d):
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
            continue
    return values


def alpha_beta_mean(con: str, values: dict[str, dict[str, list[float]]]) -> float:
    pair = values.get(con, {})
    if not pair.get("α") or not pair.get("β"):
        raise SystemExit(f"Front-matter alpha/beta rule cannot be resolved for {con}")
    # When a Bayer designation resolves into multiple catalog components, use
    # the brightest visual component as that designation's representative V.
    alpha = min(pair["α"])
    beta = min(pair["β"])
    return statistics.mean((alpha, beta))


def read_hyg(path: Path) -> dict[str, float]:
    if not path.is_file():
        raise SystemExit(f"Missing pinned HYG catalog: {path}")
    by_hip: dict[str, float] = {}
    for row in read_csv(path):
        raw_mag = (row.get("mag") or "").strip()
        if not raw_mag:
            continue
        try:
            mag = float(raw_mag)
        except ValueError:
            continue
        hip = (row.get("hip") or "").strip()
        if not hip:
            continue
        try:
            hip = str(int(float(hip)))
        except ValueError:
            continue
        by_hip[hip] = mag
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


def median_figure_magnitude(
    figure_key: str,
    figures: dict[str, list[str]],
    by_hip: dict[str, float],
) -> float:
    hips = figures.get(figure_key, [])
    if not hips:
        raise SystemExit(f"No member stars enumerated for adopted figure {figure_key}")
    missing = [hip for hip in hips if hip not in by_hip]
    if missing:
        raise SystemExit(
            f"Pinned HYG catalog lacks V magnitudes for {figure_key} member HIP(s): "
            + ", ".join(missing)
        )
    return statistics.median(by_hip[hip] for hip in hips)


def normal_figure_key(name: str, figures: dict[str, list[str]]) -> str:
    wanted = normalize_name(name)
    matches = [key for key in figures if normalize_name(key) == wanted]
    if len(matches) != 1:
        raise SystemExit(
            f"Could not uniquely match {name} to adopted Martz/MacRobert figure data"
        )
    return matches[0]


def constellation_magnitude(
    row: dict[str, str],
    alpha_beta: dict[str, dict[str, list[float]]],
    figures: dict[str, list[str]],
    by_hip: dict[str, float],
) -> float:
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

    figure_key = normal_figure_key(row["name"], figures)
    if not figures.get(figure_key):
        raise SystemExit(
            f"No member stars enumerated for adopted figure {row['name']} ({con})"
        )
    return median_figure_magnitude(figure_key, figures, by_hip)


def visibility_html(mag: float) -> str:
    aid = observing_aid_for_magnitude(str(mag))
    if aid is None:
        raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
    return (
        '<span class="visibility-magnitude">'
        f'{HTML_AID[aid]} V {mag:.1f}'
        '</span>'
    )


def make_row(source: dict[str, str], year: int) -> dict[str, str]:
    ci, cd = best_visibility(float(source["centroid_ra_h"]), year)
    return {
        "name": source["name"],
        "abbr": source["abbr"],
        "figure_part": source.get("figure_part", ""),
        "centroid_ra_h": source["centroid_ra_h"],
        "centroid_dec_deg": source["centroid_dec_deg"],
        "sampled_area_sq_deg": source["sampled_area_sq_deg"],
        "centroid_step_deg": source["centroid_step_deg"],
        "center_best_instant_utc": ci.strftime("%Y-%m-%d %H:%M"),
        "center_best_date": cd.isoformat(),
        "center_iso": iso_label(cd),
    }


def build_rows(year):
    snaps = read_csv(CENTROID_SNAPSHOT)
    if len(snaps) != 88:
        raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
    rows = []
    for snap in snaps:
        if snap["abbr"].strip() != "Ser":
            rows.append(make_row(snap, year))
            continue
        for component in SERPENS_COMPONENTS:
            rows.append(make_row({**component, "abbr": "Ser"}, year))
    if len(rows) != 89:
        raise SystemExit(f"Expected 89 center rows after splitting Serpens, got {len(rows)}")
    return rows


def write_csv(year, rows):
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
    for r in rows:
        d = dt.date.fromisoformat(r["center_best_date"])
        cls = f"{declination_band(r['centroid_dec_deg'])} {season_for(d)}"
        mag = constellation_magnitude(r, alpha_beta, figures, by_hip)
        vis = visibility_html(mag)
        events[d].append(f"{r['name']} center — Constellation — {vis} — {cls}")
    return events


def clean_legacy_constellation_events(text):
    cells = re.compile(r'(<td>)(.*?)(</td>)')
    bare = re.compile(r'^✦ (?:α|β) star — .+$')
    old_center = re.compile(r'^(?:✦ )?.*? (?:geometric-center observance|center)(?: —)? .+$')

    def repl(m):
        parts = [
            p
            for p in m.group(2).split("<br>")
            if not bare.match(p.strip()) and not old_center.match(p.strip())
        ]
        return m.group(1) + ("<br>".join(parts) if parts else "—") + m.group(3)

    return cells.sub(repl, text)


def pages_for_events(root, events):
    pages = []
    for iso_year in sorted({d.isocalendar().year for d in events}):
        pages.extend(sorted((root / str(iso_year)).glob("W*/index.html")))
    return pages


def inject(root, events):
    changed = 0
    for page in pages_for_events(root, events):
        text = page.read_text(encoding="utf-8")
        original = text
        text = clean_legacy_constellation_events(text)
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y")
            pat = re.compile(
                rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)"
            )
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                if v not in keep:
                    keep.append(v)
            text = text[: m.start(2)] + "<br>".join(keep) + text[m.end(2) :]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main():
    for year in requested_years():
        rows = build_rows(year)
        write_csv(year, rows)
        events = event_map(rows)
        c1 = inject(SOURCE_SITE, events)
        c2 = inject(PUBLIC, events)
        print(
            f"{year}: 89 constellation-center events with visibility "
            f"(Serpens split into Caput/Cauda); updated {c1} source + {c2} public pages"
        )


if __name__ == "__main__":
    main()
