#!/usr/bin/env python3
"""Populate 2025/2027 constellation alpha, beta, and geometric-center events.

The geometric-center values are read from the committed 2026 constellation
observance CSV. That CSV is the repository snapshot of the already-computed
IAU-boundary centroids, so normal Almanack builds do not need live web access.
Alpha and beta events come from the audited Bayer source. Dates are recomputed
for each requested year with the Star Almanack 9 PM apparent-solar-time rule.
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
YEARS = (2025, 2027)
CENTROID_SNAPSHOT = SRC / "constellation-observance-2026.csv"

fspec = importlib.util.spec_from_file_location(
    "fixedsky", ROOT / "tools" / "populate_2025_2027_fixed_sky.py"
)
fixed = importlib.util.module_from_spec(fspec)
assert fspec and fspec.loader
fspec.loader.exec_module(fixed)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_bayer() -> list[dict[str, str]]:
    return read_csv(SRC / "expanded-bayer-visibility-2026.csv")


def read_centroids() -> list[dict[str, str]]:
    rows = read_csv(CENTROID_SNAPSHOT)
    if len(rows) != 88:
        raise SystemExit(f"Expected 88 centroid snapshot rows, got {len(rows)}")
    needed = {"name", "abbr", "centroid_ra_h", "centroid_dec_deg", "sampled_area_sq_deg", "centroid_step_deg"}
    if not needed.issubset(rows[0]):
        raise SystemExit("Constellation centroid snapshot is missing required columns")
    return rows


def preferred_ab(rows: list[dict[str, str]], abbr: str, greek: str) -> dict[str, str] | None:
    candidates = [r for r in rows if r.get("con") == abbr and r.get("greek") == greek]
    if not candidates:
        return None
    unsuffixed = [r for r in candidates if not r.get("suffix", "").strip()]
    return (unsuffixed or candidates)[0]


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def build_rows(year: int) -> list[dict[str, str]]:
    bayer = read_bayer()
    rows: list[dict[str, str]] = []
    for snap in read_centroids():
        name = snap["name"]
        abbr = snap["abbr"]
        center_ra = float(snap["centroid_ra_h"])
        ci, cd = fixed.best_visibility(center_ra, year)
        alpha = preferred_ab(bayer, abbr, "α")
        beta = preferred_ab(bayer, abbr, "β")
        ai = ad = bi = bd = None
        if alpha:
            ai, ad = fixed.best_visibility(float(alpha["ra_h"]), year)
        if beta:
            bi, bd = fixed.best_visibility(float(beta["ra_h"]), year)
        rows.append({
            "name": name,
            "abbr": abbr,
            "centroid_ra_h": snap["centroid_ra_h"],
            "centroid_dec_deg": snap["centroid_dec_deg"],
            "sampled_area_sq_deg": snap["sampled_area_sq_deg"],
            "centroid_step_deg": snap["centroid_step_deg"],
            "alpha_bayer": alpha.get("bayer", "") if alpha else "",
            "alpha_ra_h": alpha.get("ra_h", "") if alpha else "",
            "alpha_best_instant_utc": ai.strftime("%Y-%m-%d %H:%M") if ai else "",
            "alpha_best_date": ad.isoformat() if ad else "",
            "alpha_iso": iso_label(ad) if ad else "",
            "beta_bayer": beta.get("bayer", "") if beta else "",
            "beta_ra_h": beta.get("ra_h", "") if beta else "",
            "beta_best_instant_utc": bi.strftime("%Y-%m-%d %H:%M") if bi else "",
            "beta_best_date": bd.isoformat() if bd else "",
            "beta_iso": iso_label(bd) if bd else "",
            "center_best_instant_utc": ci.strftime("%Y-%m-%d %H:%M"),
            "center_best_date": cd.isoformat(),
            "center_iso": iso_label(cd),
        })
    return rows


def write_csv(year: int, rows: list[dict[str, str]]) -> None:
    out = SRC / "generated" / f"constellation-observance-{year}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def event_map(rows: list[dict[str, str]]) -> dict[dt.date, list[str]]:
    events: dict[dt.date, list[str]] = defaultdict(list)
    for r in rows:
        if r["alpha_best_date"]:
            events[dt.date.fromisoformat(r["alpha_best_date"])].append(
                f"✦ {r['name']} α-star observance ({r['alpha_bayer']})"
            )
        if r["beta_best_date"]:
            events[dt.date.fromisoformat(r["beta_best_date"])].append(
                f"✦ {r['name']} β-star observance ({r['beta_bayer']})"
            )
        events[dt.date.fromisoformat(r["center_best_date"])].append(
            f"✦ {r['name']} geometric-center observance"
        )
    return events


def inject(root: Path, year: int, events: dict[dt.date, list[str]]) -> int:
    changed = 0
    for page in sorted((root / str(year)).glob("W*/index.html")):
        text = page.read_text(encoding="utf-8")
        original = text
        for d, vals in events.items():
            date_text = d.strftime("%a, %b %d, %Y").replace(" 0", " ")
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


def main() -> None:
    for year in YEARS:
        rows = build_rows(year)
        write_csv(year, rows)
        events = event_map(rows)
        c1 = inject(SOURCE_SITE, year, events)
        c2 = inject(PUBLIC, year, events)
        print(f"{year}: 88 constellation centers plus legitimate alpha/beta events; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
