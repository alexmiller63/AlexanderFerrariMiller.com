#!/usr/bin/env python3
"""Replay the preserved nine-case production audit. No network or publication."""
from pathlib import Path
import os
import sys
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from datetime import datetime
from pathlib import Path

import numpy as np
import yaml

from skyfield.api import load

from besselian_eclipse_engine import BesselianEclipseEngine

kernel = Path('.cache') / 'skyfield' / 'de440s.bsp'
ts = load.timescale(builtin=True)
engine = BesselianEclipseEngine(kernel)

with open('eclipse-validation-cases.yaml', 'r', encoding='utf-8') as f:
    suite = yaml.safe_load(f)

cases = []
for case in suite['historical']:
    if case.get('expected_exists'):
        cases.append((case['label'], case['date_utc'], case['nasa_greatest_td']))
for case in suite['future_jello']['cases']:
    if case.get('expected_exists'):
        cases.append((case['label'], case['date_utc'], case['nasa_greatest_td']))

print('STAR ALMANACK — PRODUCTION BESSELIAN GREATEST-ECLIPSE AUDIT')
print('Backend: besselian_eclipse_engine.py')
print('Dependency: lkangas/eclipse-calc @ 23853a8f9e0d1a25e026203207aca16de1d7bb31')
print('License notice: THIRD-PARTY-LICENSES.md')
print('Ephemeris: JPL DE440s via Skyfield')
print('Residual: calculated TT minus published NASA TD; no UT/UTC conversion')
print()
print(f"{'Case':38s} {'NASA TD':20s} {'Besselian TT':24s} {'Residual':>10s} {'gamma':>10s}")
print('-' * 110)

residuals = []
for label, date_text, ref_text in cases:
    event = engine.find_greatest_eclipse(date_text)
    if ref_text.endswith('Z'):
        raise ValueError('TD reference must not carry a UTC Z suffix')
    ref_dt = datetime.fromisoformat(ref_text)
    if ref_dt.tzinfo is not None:
        raise ValueError('TD reference must be a timezone-free TT calendar label')
    ref = ts.tt(ref_dt.year, ref_dt.month, ref_dt.day,
                ref_dt.hour, ref_dt.minute, ref_dt.second + ref_dt.microsecond / 1e6)
    calc = ts.tdb_jd(event.greatest_jd_tdb)
    residual = float((calc.tt - ref.tt) * 86400.0)
    residuals.append(residual)
    print(
        f'{label:38.38s} {ref_text:20s} {calc.tt_strftime('%Y-%m-%dT%H:%M:%S'):24s} '
        f'{residual:+9.3f}s {event.gamma:10.6f}'
    )

arr = np.asarray(residuals, dtype=float)
print()
print('SUMMARY')
print('-' * 72)
print(f'n={len(arr)}')
print(f'mean signed residual = {arr.mean():+.3f} s')
print(f'mean absolute error  = {np.abs(arr).mean():.3f} s')
print(f'max absolute error   = {np.abs(arr).max():.3f} s')

# Whole-second NASA references allow 0.5 s rounding uncertainty;
# the 1 s gate also allows small ephemeris/model differences.
tolerance = float(suite['tolerances']['besselian_greatest_time_seconds'])
if np.abs(arr).max() > tolerance:
    raise SystemExit(
        f'production Besselian TT regression: max error {np.abs(arr).max():.3f}s > {tolerance:.3f}s'
    )
