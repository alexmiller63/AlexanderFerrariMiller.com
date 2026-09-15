#!/usr/bin/env python3
"""Reconcile GCVS V-system bright-variable candidates with the HYG bright-star baseline.

This is deliberately conservative. It does not automatically promote every GCVS
maximum into the Almanack bright-star layer. It separates ordinary/periodic
variables from eruptive/transient objects and records whether the object is
already represented by the HYG V<=2.50 baseline.
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

GREEK_TO_HYG = {
    'alf': 'Alp', 'bet': 'Bet', 'gam': 'Gam', 'del': 'Del', 'eps': 'Eps',
    'zet': 'Zet', 'eta': 'Eta', 'the': 'The', 'iot': 'Iot', 'kap': 'Kap',
    'lam': 'Lam', 'mu': 'Mu', 'nu': 'Nu', 'ksi': 'Xi', 'omi': 'Omi',
    'pi': 'Pi', 'rho': 'Rho', 'sig': 'Sig', 'tau': 'Tau', 'ups': 'Ups',
    'phi': 'Phi', 'chi': 'Chi', 'psi': 'Psi', 'ome': 'Ome',
}

# GCVS classes dominated by eruptions/transients. These maxima belong in
# "Outbursts and exceptional brightness", not automatic catalog membership.
EXCEPTIONAL_PREFIXES = ('SN', 'NA', 'NB', 'NC', 'NR', 'N:', 'NA+', 'NB+', 'NR+')


def norm(s: str) -> str:
    return re.sub(r'[^a-z0-9]+', '', (s or '').lower())


def gcvs_bayer_key(name: str) -> tuple[str, str] | None:
    parts = name.strip().split()
    if len(parts) < 2:
        return None
    g = parts[0].lower()
    if g not in GREEK_TO_HYG:
        return None
    con = parts[-1].title()
    middle = ''.join(parts[1:-1])
    suffix = ''.join(ch for ch in middle if ch.isdigit())
    return (GREEK_TO_HYG[g] + suffix, con)


def is_exceptional(var_type: str) -> bool:
    t = (var_type or '').upper().strip()
    return any(t.startswith(p) for p in EXCEPTIONAL_PREFIXES)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument('gcvs', type=Path, nargs='?', default=Path('gcvs-bright-boundary-audit.csv'))
    p.add_argument('bright', type=Path, nargs='?', default=Path('bright-stars-2mag.csv'))
    p.add_argument('output', type=Path, nargs='?', default=Path('bright-variable-reconciliation.csv'))
    args = p.parse_args()

    with args.gcvs.open(newline='', encoding='utf-8') as f:
        gcvs = list(csv.DictReader(f))
    with args.bright.open(newline='', encoding='utf-8') as f:
        bright = list(csv.DictReader(f))

    by_bayer = set()
    by_proper = set()
    for r in bright:
        b = (r.get('bayer') or '').strip()
        c = (r.get('con') or '').strip()
        if b and c:
            by_bayer.add((b, c))
        if r.get('proper'):
            by_proper.add(norm(r['proper']))

    rows = []
    for r in gcvs:
        if (r.get('mag_system') or '').strip().upper() != 'V':
            continue
        name = r['name'].strip()
        key = gcvs_bayer_key(name)
        overlap = bool(key and key in by_bayer)
        if not overlap and norm(name) in by_proper:
            overlap = True

        vt = r.get('variability_type', '')
        if is_exceptional(vt):
            classification = 'exceptional-outburst-only'
            reason = 'eruptive/transient GCVS class; maximum is not representative ordinary brightness'
        elif overlap:
            classification = 'already-in-HYG-baseline'
            reason = 'already represented in V<=2.50 HYG baseline; use GCVS to enrich variability range/note'
        else:
            classification = 'needs-source-check'
            reason = 'V-system maximum reaches threshold but object is not confidently reconciled to HYG baseline'

        rows.append({
            'name': name,
            'gcvs_max_v': r.get('max_mag',''),
            'gcvs_min_v': r.get('min_mag',''),
            'variability_type': vt,
            'hyg_baseline_overlap': 'yes' if overlap else 'no',
            'classification': classification,
            'reason': reason,
        })

    rows.sort(key=lambda r: (r['classification'], float(r['gcvs_max_v']), r['name']))
    fields = ['name','gcvs_max_v','gcvs_min_v','variability_type','hyg_baseline_overlap','classification','reason']
    with args.output.open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader(); w.writerows(rows)

    from collections import Counter
    counts = Counter(r['classification'] for r in rows)
    print(f'GCVS V-system candidates reconciled: {len(rows)}')
    for k in ('already-in-HYG-baseline','exceptional-outburst-only','needs-source-check'):
        print(f'{k}: {counts[k]}')
    print(f'Wrote {args.output}')


if __name__ == '__main__':
    main()
