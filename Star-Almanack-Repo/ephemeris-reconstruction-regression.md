# Star Almanack Ephemeris Reconstruction — Regression Check

The reconstructed compact Sun/Moon engine was tested against representative
weekly positions already preserved in `ephem.md`.

The residual is reconstructed longitude minus preserved longitude, in arcminutes.

| Week | Sun residual | Moon residual |
|---|---:|---:|
| 2026-W01 | -0.06′ | -1.42′ |
| 2026-W08 | +0.28′ | -0.59′ |
| 2026-W16 | +0.53′ | +1.19′ |
| 2026-W24 | +1.05′ | -1.14′ |
| 2026-W33 | -0.25′ | -1.64′ |
| 2026-W40 | -0.31′ | -2.22′ |
| 2026-W48 | +0.08′ | -2.39′ |
| 2026-W52 | +0.12′ | -0.68′ |

## Result

The reconstruction matches the preserved solar longitudes to about 1 arcminute
or better across the sampled year, and the lunar longitudes to about 2.4
arcminutes or better across the sampled year.

This is strong evidence that the compact orbital-element model with the listed
lunar perturbation terms is substantially the same computational machinery that
generated the preserved 2026 weekly Sun/Moon ephemeris.

It is therefore suitable as the recovered baseline engine. The next step is to
upgrade the time treatment to TT/UT1 and use higher-precision vectors for the
eclipse geometry, while retaining this engine as a regression baseline.
