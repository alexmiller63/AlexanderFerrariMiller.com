#!/usr/bin/env python3
"""Audit GCVS variables whose cataloged maximum reaches V <= +2.50.

Input is the HEASARC GCVS VOTable. Output is a compact CSV of all rows whose
maximum magnitude is <= 2.50, retaining photometric-system/type metadata so
that visual/Johnson-V membership can be reviewed against the HYG
second-magnitude baseline.
"""

from __future__ import annotations

import argparse
import csv
import xml.etree.ElementTree as ET
from pathlib import Path


def local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('votable', type=Path)
    p.add_argument('output', type=Path, nargs='?', default=Path('gcvs-bright-boundary-audit.csv'))
    args = p.parse_args()

    root = ET.parse(args.votable).getroot()
    table = next((x for x in root.iter() if local(x.tag) == 'TABLE'), None)
    if table is None:
        raise SystemExit('No TABLE found in GCVS VOTable')

    fields = []
    for elem in table:
        if local(elem.tag) == 'FIELD':
            fields.append((elem.attrib.get('name') or elem.attrib.get('ID') or '').strip())
    if not fields:
        raise SystemExit('No FIELD definitions found in GCVS VOTable')

    index = {name.lower(): i for i, name in enumerate(fields)}

    def pick(*names: str):
        for name in names:
            if name.lower() in index:
                return index[name.lower()]
        return None

    i_name = pick('name')
    i_max = pick('max_mag')
    i_min = pick('min_mag')
    # HEASARC's current GCVS schema calls this mag_system. Older/alternate
    # tables may expose related names, so retain fallbacks for reproducibility.
    i_system = pick('mag_system', 'mag_band', 'mag_code', 'magnitude_code')
    i_type = pick('variability_type', 'var_type')
    i_maxlim = pick('max_mag_limit', 'limit_max_mag')
    i_maxflag = pick('max_mag_flag')
    if i_name is None or i_max is None:
        raise SystemExit(f'Required GCVS fields missing; available fields: {fields}')

    rows = []
    for tr in (x for x in table.iter() if local(x.tag) == 'TR'):
        vals = [(td.text or '').strip() for td in tr if local(td.tag) == 'TD']
        if len(vals) < len(fields):
            vals += [''] * (len(fields) - len(vals))
        raw = vals[i_max]
        try:
            max_mag = float(raw)
        except (TypeError, ValueError):
            continue
        if max_mag > 2.50:
            continue
        rows.append({
            'name': vals[i_name],
            'max_mag': raw,
            'max_mag_limit': vals[i_maxlim] if i_maxlim is not None else '',
            'max_mag_flag': vals[i_maxflag] if i_maxflag is not None else '',
            'mag_system': vals[i_system] if i_system is not None else '',
            'min_mag': vals[i_min] if i_min is not None else '',
            'variability_type': vals[i_type] if i_type is not None else '',
        })

    rows.sort(key=lambda r: (float(r['max_mag']), r['name']))
    fieldnames = [
        'name', 'max_mag', 'max_mag_limit', 'max_mag_flag',
        'mag_system', 'min_mag', 'variability_type'
    ]
    with args.output.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    visual_rows = [r for r in rows if r['mag_system'].strip().upper() == 'V']
    photographic_rows = [r for r in rows if r['mag_system'].strip().upper() in {'P', 'PH', 'PG'}]
    other_rows = [r for r in rows if r not in visual_rows and r not in photographic_rows]
    print(f'GCVS rows with cataloged maximum <= +2.50: {len(rows)}')
    print(f'Rows in GCVS V system (visual/photovisual/Johnson V): {len(visual_rows)}')
    print(f'Rows explicitly photographic: {len(photographic_rows)}')
    print(f'Rows in other/blank systems: {len(other_rows)}')
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
