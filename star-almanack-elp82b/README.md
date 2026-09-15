# Star Almanack — ELP2000-82B lunar engine

This directory begins the eclipse-grade lunar ephemeris layer.

## What is imported

The **model coefficients** are imported from the CDS/VizieR archival release
`VI/79`, *Lunar Solution ELP 2000-82B* by Chapront-Touzé and Chapront.

The archive contains 36 coefficient tables for lunar longitude, latitude and
distance. It also contains the original reference Fortran subroutine.

We do **not** import a table saying where the Moon is on a particular date.
The Star Almanack evaluates the lunar theory from the coefficients.

## Why this is separate from `ephemeris_engine.py`

`ephemeris_engine.py` is the recovered compact baseline that reproduced the
existing weekly Almanack ephemeris. It should remain frozen as a regression
reference.

`lunar_elp.py` is the higher-precision eclipse engine.

## Time

The ELP model is evaluated using **TT (Terrestrial Time)**. UTC remains the
civil publication time; UT1 is used separately when terrestrial orientation
is required.

## Bootstrap

On a computer with Internet access:

```bash
python lunar_elp.py bootstrap data/elp82b
python lunar_elp.py verify data/elp82b
python normalize_elp82b.py data/elp82b elp82b-manifest.json
```

The bootstrap source is the official CDS archive:

`https://cdsarc.cds.unistra.fr/ftp/VI/79/`

## Current build status

The time/argument layer and archive bootstrap are implemented.

The 36-table numerical series evaluator is the next stage. Its parser will be
derived from the archived reference `elp82b.f`; field widths will not be
guessed. After that evaluator is complete, the first regression is the
Apr 8, 2024 eclipse, followed by Feb 17, 2026.
