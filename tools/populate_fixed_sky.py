#!/usr/bin/env python3
"""Populate fixed-sky visibility events for requested Almanack years."""
from __future__ import annotations
import csv
import datetime as dt
import re
import sys
from collections import defaultdict
from pathlib import Path

from star_almanack_astronomy import (
    apparent_sun_ra_hours,
    best_visibility_occurrences_for_iso_year,
    solar_ra_occurrences_for_iso_year,
)
from star_almanack_objects import AlmanackObject, observing_aid_for_magnitude, render_html

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "Star-Almanack-Repo"
PUBLIC = ROOT / "almanack"
SOURCE_SITE = SRC / "site"
DEFAULT_YEARS = (2025, 2026, 2027)

GREEK_BAYER = {
    "Alp": "α", "Bet": "β", "Gam": "γ", "Del": "δ", "Eps": "ε", "Zet": "ζ",
    "Eta": "η", "The": "θ", "Iot": "ι", "Kap": "κ", "Lam": "λ", "Mu": "μ",
    "Nu": "ν", "Xi": "ξ", "Omi": "ο", "Pi": "π", "Rho": "ρ", "Sig": "σ",
    "Tau": "τ", "Ups": "υ", "Phi": "φ", "Chi": "χ", "Psi": "ψ", "Ome": "ω",
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


def iso_label(d: dt.date) -> str:
    y, w, wd = d.isocalendar()
    return f"{y}-W{w:02d}-{wd}"


def read_csv(name: str) -> list[dict[str, str]]:
    with (SRC / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def redated(rows, iso_year):
    out = []
    for row in rows:
        for instant, day in best_visibility_occurrences_for_iso_year(float(row["ra_h"]), iso_year):
            r = dict(row)
            r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
            r["best_date"] = day.isoformat()
            r["iso"] = iso_label(day)
            out.append(r)
    return out


def redated_preserving_2026_phase(rows, iso_year):
    """Carry each canonical 2026 placement by solar-RA phase into an ISO year."""
    out = []
    for row in rows:
        canonical = dt.datetime.strptime(row["best_instant_utc"], "%Y-%m-%d %H:%M")
        target = apparent_sun_ra_hours(canonical)
        for instant, day in solar_ra_occurrences_for_iso_year(target, iso_year):
            r = dict(row)
            r["best_instant_utc"] = instant.strftime("%Y-%m-%d %H:%M")
            r["best_date"] = day.isoformat()
            r["iso"] = iso_label(day)
            out.append(r)
    return out


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise RuntimeError(f"No visibility rows generated for {path.name}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def display_bayer(r: dict[str, str]) -> str:
    bayer = r.get("bayer", "").strip()
    if bayer in GREEK_BAYER:
        con = r.get("con", "").strip()
        return f"{GREEK_BAYER[bayer]} {con}" if con else GREEK_BAYER[bayer]
    return bayer


def star_label(r: dict[str, str]) -> str:
    proper = r.get("proper", "").strip()
    bayer = display_bayer(r)
    base = f"{proper} ({bayer})" if proper and bayer else (proper or bayer or f"{r.get('con','').strip()} star")
    source_mag = (r.get("representative_vmax") or r.get("catalog_v") or r.get("mag") or "").strip()
    record = AlmanackObject(
        label=base,
        object_type="fixed_star",
        dec_deg=r["dec_deg"],
        best_date=dt.date.fromisoformat(r["best_date"]),
        observing_aid=observing_aid_for_magnitude(source_mag),
        magnitude=source_mag,
        magnitude_display="whole",
        catalog_id=(r.get("hyg_id") or r.get("hip") or "").strip(),
        provenance=(r.get("brightness_basis") or "").strip(),
    )
    return render_html(record)


def page_date_map(year: int):
    bayer = redated(read_csv("expanded-bayer-visibility-2026.csv"), year)
    bright = redated(read_csv("bright-star-visibility-2026.csv"), year)
    messier = redated_preserving_2026_phase(read_csv("messier-visibility-2026.csv"), year)
    write_csv(SRC / "generated" / f"expanded-bayer-visibility-{year}.csv", bayer)
    write_csv(SRC / "generated" / f"bright-star-visibility-{year}.csv", bright)
    write_csv(SRC / "generated" / f"messier-visibility-{year}.csv", messier)
    events = defaultdict(list)
    seen = set()
    for r in bayer:
        d = dt.date.fromisoformat(r["best_date"])
        identity = (r.get("proper") or r.get("bayer") or "").strip().lower()
        key = (d, identity)
        if identity and key not in seen:
            events[d].append(star_label(r))
            seen.add(key)
    for r in bright:
        if r.get("new_non_alpha_beta", "").lower() != "yes":
            continue
        d = dt.date.fromisoformat(r["best_date"])
        identity = (r.get("proper") or (r.get("bayer", "") + r.get("con", ""))).strip().lower()
        key = (d, identity)
        if identity and key not in seen:
            events[d].append(star_label(r))
            seen.add(key)
    for r in messier:
        events[dt.date.fromisoformat(r["best_date"])].append(r["messier"] + " — 🔭")
    return events


def pages_for_events(root: Path, events) -> list[Path]:
    iso_years = sorted({d.isocalendar().year for d in events})
    pages: list[Path] = []
    for iso_year in iso_years:
        pages.extend(sorted((root / str(iso_year)).glob("W*/index.html")))
    return pages


def date_text(d: dt.date) -> str:
    return f"{d:%a, %b} {d.day}, {d:%Y}"


def inject(root: Path, year: int, events) -> int:
    changed = 0
    for page in pages_for_events(root, events):
        text = page.read_text(encoding="utf-8")
        original = text
        for d, vals in events.items():
            pat = re.compile(rf"(<tr><td>{re.escape(date_text(d))}</td><td>.*?</td><td>)(.*?)(</td></tr>)")
            m = pat.search(text)
            if not m:
                continue
            keep = [] if m.group(2) == "—" else [x for x in m.group(2).split("<br>") if x]
            for v in vals:
                base = v.split(" — ", 1)[0]
                keep = [x for x in keep if not (x == base or x.startswith(base + " — "))]
                keep.append(v)
            text = text[:m.start(2)] + ("<br>".join(keep) if keep else "—") + text[m.end(2):]
        if text != original:
            page.write_text(text, encoding="utf-8")
            changed += 1
    return changed


def main():
    for year in requested_years():
        events = page_date_map(year)
        c1 = inject(SOURCE_SITE, year, events)
        c2 = inject(PUBLIC, year, events)
        print(f"{year}: canonical fixed-sky entries with observing glyph, magnitude, declination band and season; updated {c1} source + {c2} public pages")


if __name__ == "__main__":
    main()
