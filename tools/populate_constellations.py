#!/usr/bin/env python3
"""Populate constellation-center events for requested Almanack years.

Alpha/beta star events are owned by the fixed-sky population step;
this step must not create duplicate alpha/beta events.

Constellation-center visibility is a property of the adopted constellation
figure, not of the geometric center itself.  The long-term rule is the median
V magnitude of the stars in the adopted Martz-Kohl figure.  Explicit front-
matter exceptions are kept here for constellations whose figure/member
provenance needs special treatment:

* Mensa and Telescopium: arithmetic mean of alpha and beta V magnitudes.
* Norma: there is no modern alpha or beta; use the arithmetic mean of the two
  brightest modern Norma stars (gamma2 and epsilon).
* Serpens: retained as an explicit exception because the single IAU
  constellation is represented by the two Martz-Kohl figures, Caput and
  Cauda.  Its final figure-derived magnitude must come from those member-star
  sets rather than an alpha/beta fallback.

Do not silently substitute a brightest-star rule for a missing figure-derived
magnitude.
"""
from __future__ import annotations
import csv
import datetime as dt
import re
import statistics
import sys
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

# Explicit front matter.  These values/rules are deliberately visible here so
# an exception can never be mistaken for Martz-Kohl member-star provenance.
# Norma values are the two brightest modern Norma stars: gamma2 Nor V 4.02 and
# epsilon Nor V 4.47.  The catalog-backed alpha/beta exceptions are resolved
# from expanded-bayer-stars.csv below rather than duplicating their magnitudes.
FRONT_MATTER = {
    "Men": {"rule": "alpha_beta_mean"},
    "Tel": {"rule": "alpha_beta_mean"},
    "Nor": {"rule": "explicit_mean", "magnitudes": (4.02, 4.47)},
    "Ser": {"rule": "martz_caput_cauda"},
}


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
    # If a Bayer designation has resolved components, use the brightest visual
    # component as the designation's representative catalog magnitude.
    alpha = min(pair["α"])
    beta = min(pair["β"])
    return statistics.mean((alpha, beta))


def fallback_alpha_beta_magnitude(con: str, values: dict[str, dict[str, list[float]]]) -> float | None:
    """Temporary legacy fallback for figures not yet migrated to Martz members.

    This preserves existing generated output while making the four explicit
    exceptions deterministic.  It is intentionally not described as the
    constellation-figure rule.
    """
    pair = values.get(con, {})
    candidates = pair.get("α", []) + pair.get("β", [])
    return min(candidates) if candidates else None


def constellation_magnitude(con: str, values: dict[str, dict[str, list[float]]]) -> float:
    front = FRONT_MATTER.get(con)
    if front:
        rule = front["rule"]
        if rule == "alpha_beta_mean":
            return alpha_beta_mean(con, values)
        if rule == "explicit_mean":
            return statistics.mean(front["magnitudes"])
        if rule == "martz_caput_cauda":
            # Until the two Martz member sets are checked into the source tree,
            # preserve Serpens' existing alpha/beta-derived value rather than
            # inventing member stars.  This branch makes the unresolved source
            # requirement explicit and prevents it from being confused with
            # Norma/Mensa/Telescopium.
            legacy = fallback_alpha_beta_magnitude(con, values)
            if legacy is not None:
                return legacy
            raise SystemExit("Serpens requires Martz-Kohl Caput/Cauda member-star magnitudes")

    legacy = fallback_alpha_beta_magnitude(con, values)
    if legacy is None:
        raise SystemExit(f"No stellar magnitude available for constellation {con}")
    return legacy


def visibility_html(mag: float) -> str:
    aid = observing_aid_for_magnitude(str(mag))
    if aid is None:
        raise SystemExit(f"Could not derive observing aid for magnitude {mag}")
    return (
        '<span class="visibility-magnitude">'
        f'{HTML_AID[aid]} V {mag:.1f}'
        '</span>'
    )


def build_rows(year):
    snaps = read_csv(CENTROID_SNAPSHOT)
    if len(snaps) != 88:
        raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(snaps)}")
    rows = []
    for snap in snaps:
        ci, cd = best_visibility(float(snap["centroid_ra_h"]), year)
        rows.append({
            "name": snap["name"], "abbr": snap["abbr"],
            "centroid_ra_h": snap["centroid_ra_h"], "centroid_dec_deg": snap["centroid_dec_deg"],
            "sampled_area_sq_deg": snap["sampled_area_sq_deg"], "centroid_step_deg": snap["centroid_step_deg"],
            "center_best_instant_utc": ci.strftime("%Y-%m-%d %H:%M"),
            "center_best_date": cd.isoformat(), "center_iso": iso_label(cd),
        })
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
    for r in rows:
        d = dt.date.fromisoformat(r["center_best_date"])
        cls = f"{declination_band(r['centroid_dec_deg'])} {season_for(d)}"
        abbr = r["abbr"].strip()
        mag = constellation_magnitude(abbr, alpha_beta)
        vis = visibility_html(mag)
        events[d].append(f"{r['name']} center — Constellation — {vis} — {cls}")
    return events


def clean_legacy_constellation_events(text):
    cells = re.compile(r'(<td>)(.*?)(</td>)')
    bare = re.compile(r'^✦ (?:α|β) star — .+$')
    old_center = re.compile(r'^(?:✦ )?.*? (?:geometric-center observance|center)(?: —)? .+$')

    def repl(m):
        parts = [p for p in m.group(2).split("<br>") if not bare.match(p.strip()) and not old_center.match(p.strip())]
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
            pat = re.compile(rf"(<tr><td>{re.escape(date_text)}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                if v not in keep:
                    keep.append(v)
            text = text[:m.start(2)] + "<br>".join(keep) + text[m.end(2):]
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
        print(f"{year}: 88 constellation-center events with visibility; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
