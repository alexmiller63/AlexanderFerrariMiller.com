#!/usr/bin/env python3
"""Populate 2025/2027 constellation alpha, beta, and geometric-center events.

Constellation membership/geometry is based on the official IAU J2000 boundary
polygons. The center is the spherical area centroid (the project's "balance
point"), estimated with the same solid-angle weighted sampler used by the 2026
centroid experiment. Alpha and beta events come from the audited Bayer source.
All three dates are independently recomputed for each requested year with the
Star Almanack 9 PM apparent-solar-time visibility rule.
"""
from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
YEARS = (2025, 2027)

# Load the proven 2026 boundary/centroid implementation without duplicating it.
spec = importlib.util.spec_from_file_location(
    "constellation2026", SRC / "compute_constellation_observance_2026.py"
)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
# Its import of compute_bayer_visibility_2026 expects the source directory on sys.path.
sys.path.insert(0, str(SRC))
spec.loader.exec_module(mod)

# Load the year-independent visibility function already used for 2025/2027 stars.
fspec = importlib.util.spec_from_file_location(
    "fixedsky", ROOT / "tools" / "populate_2025_2027_fixed_sky.py"
)
fixed = importlib.util.module_from_spec(fspec)
assert fspec and fspec.loader
fspec.loader.exec_module(fixed)


def read_bayer() -> list[dict[str, str]]:
    with (SRC / "expanded-bayer-visibility-2026.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def preferred_ab(rows: list[dict[str, str]], abbr: str, greek: str) -> dict[str, str] | None:
    candidates = [r for r in rows if r.get("con") == abbr and r.get("greek") == greek]
    if not candidates:
        return None
    # Prefer an unsuffixed Bayer designation when one exists; otherwise preserve
    # the first legitimate numbered component rather than inventing a star.
    unsuffixed = [r for r in candidates if not r.get("suffix", "").strip()]
    return (unsuffixed or candidates)[0]


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def build_rows(year: int) -> list[dict[str, str]]:
    bayer = read_bayer()
    cache = SRC / ".cache" / "iau-constellation-boundaries"
    rows: list[dict[str, str]] = []
    for name, abbr in mod.CONSTELLATIONS:
        center_ra, center_dec, area = mod.centroid_for(abbr, cache, mod.DEFAULT_STEP_DEG)
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
            "centroid_ra_h": f"{center_ra:.6f}",
            "centroid_dec_deg": f"{center_dec:.6f}",
            "sampled_area_sq_deg": f"{area:.3f}",
            "centroid_step_deg": f"{mod.DEFAULT_STEP_DEG:.3f}",
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
        w.writeheader(); w.writerows(rows)


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
        if len(rows) != 88:
            raise SystemExit(f"Expected 88 constellation rows, got {len(rows)}")
        write_csv(year, rows)
        events = event_map(rows)
        c1 = inject(SOURCE_SITE, year, events)
        c2 = inject(PUBLIC, year, events)
        print(f"{year}: 88 constellation centers plus legitimate alpha/beta events; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
