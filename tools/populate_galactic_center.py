#!/usr/bin/env python3
"""Populate the annual Sun/Galactic-Center conjunction in Almanack event cells.

The event is the instant at which the apparent geocentric ecliptic longitude of
the Sun equals the ecliptic-of-date longitude of Sagittarius A*, used here as
the physical Galactic Center. Sun samples are calculated locally from cached
JPL/NAIF SPK source kernels. Sgr A* is precessed from J2000 using the canonical
JDTDB event epoch. UTC is created only at publication.

Provenance:
- Sgr A* J2000 radio position: Reid & Brunthaler (2004), as documented in
  EPHEMERIS-PROVENANCE.md.
- Precession model: independently implemented IAU 1976 precession formulae;
  coefficients are attributed there to the published standard rather than to
  copied software.
"""
from __future__ import annotations

import argparse
import math
from datetime import date, timedelta
from pathlib import Path

from almanack_calendar import ensure_calendar_metadata, get_events, page_dates, set_events
from almanack_time import AstroInstant, interpolate_instant
from almanack_sections import type_page
from populate_calendar import iso_bounds, source_longitudes

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_ROOT = ROOT / "almanack"

# Sagittarius A* J2000 radio position from Reid & Brunthaler (2004),
# ApJ 616, 872. These are published observational source coordinates, not a
# third-party calculated conjunction answer.
GC_RA_J2000_DEG = 266.4168370833333
GC_DEC_J2000_DEG = -29.007810555555555
EVENT_PREFIX = "☉ Galactic Center conjunction"


def galactic_center_ecliptic_longitude(jd_tdb: float) -> float:
    """Return mean ecliptic-of-date longitude of Sgr A* in degrees.

    Uses the IAU 1976 precession model (Lieske et al. published coefficients),
    independently implemented here for the Almanack's 1900–2100 interval. The
    precession epoch is evaluated directly from JDTDB rather than from a civil
    datetime.
    """
    t = (jd_tdb - 2451545.0) / 36525.0
    arcsec = math.pi / (180.0 * 3600.0)
    zeta = (2306.2181 * t + 0.30188 * t * t + 0.017998 * t**3) * arcsec
    z = (2306.2181 * t + 1.09468 * t * t + 0.018203 * t**3) * arcsec
    theta = (2004.3109 * t - 0.42665 * t * t - 0.041833 * t**3) * arcsec

    ra0 = math.radians(GC_RA_J2000_DEG)
    dec0 = math.radians(GC_DEC_J2000_DEG)
    a = math.cos(dec0) * math.sin(ra0 + zeta)
    b = (
        math.cos(theta) * math.cos(dec0) * math.cos(ra0 + zeta)
        - math.sin(theta) * math.sin(dec0)
    )
    c = (
        math.sin(theta) * math.cos(dec0) * math.cos(ra0 + zeta)
        + math.cos(theta) * math.sin(dec0)
    )
    ra = math.atan2(a, b) + z
    dec = math.asin(max(-1.0, min(1.0, c)))

    eps_arcsec = 84381.448 - 46.8150 * t - 0.00059 * t * t + 0.001813 * t**3
    eps = eps_arcsec * arcsec
    lon = math.atan2(
        math.sin(ra) * math.cos(eps) + math.tan(dec) * math.sin(eps),
        math.cos(ra),
    )
    return math.degrees(lon) % 360.0


def signed_angle(degrees: float) -> float:
    return (degrees + 180.0) % 360.0 - 180.0


def conjunctions(
    sun_samples: list[tuple[AstroInstant, float]],
) -> list[AstroInstant]:
    """Find negative-to-positive Sun−GC longitude crossings in JDTDB."""
    out: list[AstroInstant] = []
    for (t0, sun0), (t1, sun1) in zip(sun_samples, sun_samples[1:]):
        d0 = signed_angle(sun0 - galactic_center_ecliptic_longitude(t0.jd_tdb))
        d1 = signed_angle(sun1 - galactic_center_ecliptic_longitude(t1.jd_tdb))
        # The opposition wrap is nearly 360 degrees; reject it explicitly.
        if d0 <= 0.0 < d1 and 0.0 < d1 - d0 < 10.0:
            fraction = -d0 / (d1 - d0)
            out.append(interpolate_instant(t0, t1, fraction))
    return out


def fmt_utc(ts: AstroInstant) -> str:
    return ts.publication_time_text()


def patch_page(path: Path, event_times: dict[date, AstroInstant]) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8")
    text = ensure_calendar_metadata(original, path)
    for day in page_dates(path):
        current = get_events(text, day)
        if current is None:
            raise RuntimeError(f"Missing machine-readable calendar row for {day} in {path}")
        keep = [
            item for item in current.split("<br>")
            if item and item != "—" and "Galactic Center conjunction" not in item
        ]
        if day in event_times:
            keep.append(f"{EVENT_PREFIX} — {fmt_utc(event_times[day])}")
        text, found = set_events(text, day, "<br>".join(keep) if keep else "—")
        if not found:
            raise RuntimeError(f"Could not update Galactic Center event for {day} in {path}")
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def expected_for_year(year: int) -> dict[date, AstroInstant]:
    first, last = iso_bounds(year)
    # Margin guarantees a bracketing sample around an ISO-year boundary.
    sun = source_longitudes("sun", first - timedelta(days=2), last + timedelta(days=2))
    hits = [
        ts for ts in conjunctions(sun)
        if first <= ts.publication_date() <= last
    ]
    if len(hits) != 1:
        raise RuntimeError(
            f"Expected exactly one Galactic Center conjunction in ISO year {year}; found {len(hits)}"
        )
    return {hits[0].publication_date(): hits[0]}


def count_occurrences(base: Path, year: int) -> int:
    weeks = date(year, 12, 28).isocalendar().week
    count = 0
    for week in range(1, weeks + 1):
        page = type_page(base, year, week, "calendar")
        if not page.exists():
            continue
        count += page.read_text(encoding="utf-8").count("Galactic Center conjunction")
    return count


def populate_year(year: int) -> int:
    events = expected_for_year(year)
    changed = 0
    weeks = date(year, 12, 28).isocalendar().week
    for base in (PUBLIC_ROOT,):
        for week in range(1, weeks + 1):
            if patch_page(type_page(base, year, week, "calendar"), events):
                changed += 1
    for base in (PUBLIC_ROOT,):
        count = count_occurrences(base, year)
        if count != 1:
            raise RuntimeError(
                f"{base}: expected exactly one Galactic Center event for {year}, found {count}"
            )
    ts = next(iter(events.values()))
    print(
        f"{year}: Galactic Center conjunction "
        f"{ts.publication_utc().isoformat().replace('+00:00', 'Z')}; "
        f"JDTDB {ts.jd_tdb:.9f}; {changed} pages updated"
    )
    return changed


def verify_year(year: int) -> None:
    expected_for_year(year)
    for base in (PUBLIC_ROOT,):
        count = count_occurrences(base, year)
        if count != 1:
            raise RuntimeError(
                f"{base}: expected exactly one Galactic Center event for {year}, found {count}"
            )
    print(f"{year}: Galactic Center event verified in canonical Almanack calendar")


def parse_args() -> tuple[list[int], bool]:
    parser = argparse.ArgumentParser(description="Populate the annual Galactic Center calendar event")
    parser.add_argument("years", metavar="YEAR", type=int, nargs="+", help="ISO years to populate")
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Verify exactly one event per requested year without editing",
    )
    args = parser.parse_args()
    years = list(dict.fromkeys(args.years))
    for year in years:
        if not 1900 <= year <= 2100:
            parser.error(f"YEAR must be between 1900 and 2100: {year}")
    return years, args.verify_only


def main() -> None:
    years, verify_only = parse_args()
    if verify_only:
        for year in years:
            verify_year(year)
    else:
        total = sum(populate_year(year) for year in years)
        print(
            f"Updated {total} calendar page files for Galactic Center: "
            f"{' '.join(map(str, years))}"
        )


if __name__ == "__main__":
    main()
