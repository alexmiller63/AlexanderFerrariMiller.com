#!/usr/bin/env python3
"""High-resolution spot-check of sensitive constellation centroids.

Recompute selected large, polar, multipart, irregular, or numerically sensitive
IAU constellation regions at 0.05 and 0.025 degree sampling. Compare spherical
centroid displacement and the resulting 2026 Night of Observance date.

This is a numerical validation experiment. It does not change the production
resolution by itself.
"""

from __future__ import annotations

import csv
import datetime as dt
import math
from pathlib import Path

from compute_bayer_visibility_2026 import best_visibility
from compute_constellation_observance_2026 import CONSTELLATIONS, centroid_for

CACHE_DIR = Path('.cache/iau-constellation-boundaries')
OUTPUT = Path('constellation-centroid-spotcheck-2026.csv')

# Includes the only 0.10 -> 0.05 date mover (UMi), the largest measured
# centroid movers, and deliberately difficult geometries.
SELECTED = {
    'And', 'Aqr', 'Cep', 'Cet', 'Crt', 'Dra', 'Eri', 'Hya', 'Oct',
    'Scl', 'Ser', 'Sge', 'Tri', 'UMa', 'UMi',
}


def angular_separation_deg(ra1_h: float, dec1_deg: float, ra2_h: float, dec2_deg: float) -> float:
    r1 = math.radians(ra1_h * 15.0)
    r2 = math.radians(ra2_h * 15.0)
    d1 = math.radians(dec1_deg)
    d2 = math.radians(dec2_deg)
    dot = (
        math.cos(d1) * math.cos(d2) * math.cos(r1 - r2)
        + math.sin(d1) * math.sin(d2)
    )
    dot = max(-1.0, min(1.0, dot))
    return math.degrees(math.acos(dot))


def day_shift(a: dt.date, b: dt.date) -> int:
    return abs((a - b).days)


def main() -> None:
    selected_rows = [(name, abbr) for name, abbr in CONSTELLATIONS if abbr in SELECTED]
    if len(selected_rows) != len(SELECTED):
        missing = SELECTED - {abbr for _, abbr in selected_rows}
        raise SystemExit(f'Missing selected constellations: {sorted(missing)}')

    rows = []
    exact = 0
    within_one_day = 0
    max_sep = 0.0
    max_shift = 0

    for name, abbr in selected_rows:
        r005, d005, a005 = centroid_for(abbr, CACHE_DIR, 0.05)
        _, date005 = best_visibility(r005)
        r0025, d0025, a0025 = centroid_for(abbr, CACHE_DIR, 0.025)
        _, date0025 = best_visibility(r0025)

        sep = angular_separation_deg(r005, d005, r0025, d0025)
        shift = day_shift(date005, date0025)
        exact += date005 == date0025
        within_one_day += shift <= 1
        max_sep = max(max_sep, sep)
        max_shift = max(max_shift, shift)

        rows.append({
            'name': name,
            'abbr': abbr,
            'ra_h_0.05': f'{r005:.8f}',
            'dec_deg_0.05': f'{d005:.8f}',
            'area_sq_deg_0.05': f'{a005:.4f}',
            'date_0.05': date005.isoformat(),
            'ra_h_0.025': f'{r0025:.8f}',
            'dec_deg_0.025': f'{d0025:.8f}',
            'area_sq_deg_0.025': f'{a0025:.4f}',
            'date_0.025': date0025.isoformat(),
            'centroid_shift_deg_0.05_to_0.025': f'{sep:.6f}',
            'date_shift_days_0.05_to_0.025': str(shift),
        })
        print(
            f'{abbr:3s} {name:20s} {date005} -> {date0025}; '
            f'shift {sep:.6f} deg / {shift} d'
        )

    with OUTPUT.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print()
    print(f'0.05° vs 0.025° exact-date agreement: {exact}/{len(rows)}')
    print(f'0.05° vs 0.025° within 1 day: {within_one_day}/{len(rows)}')
    print(f'Max 0.05° -> 0.025° centroid displacement: {max_sep:.6f}°')
    print(f'Max 0.05° -> 0.025° Night-of-Observance shift: {max_shift} day(s)')
    print(f'Wrote {len(rows)} rows to {OUTPUT}')


if __name__ == '__main__':
    main()
