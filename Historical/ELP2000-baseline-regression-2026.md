# ELP2000 Baseline Regression — 2026

This file preserves test cases for improving the Star Almanack lunar
ephemeris while retaining the recovered compact lunar model as a baseline.

The purpose is incremental regression testing: add verified cases, preserve
the baseline, then introduce one controlled improvement at a time and measure
whether it improves the residuals without breaking existing cases.

## Baseline Case 1 — 2026-W01

Sampling time:

**2025-12-29 00:00 UTC**

Preserved Moon position from `ephem.md`:

**♈ 22°56′**

Equivalent geocentric tropical ecliptic longitude:

**22.933333°**

Recovered compact lunar engine evaluated at UTC:

**22.909695°**

Residual:

**−0.023638°**

or approximately:

**−1.42 arcminutes**

Result:

**BASELINE REPRODUCED**

## Baseline Case 2 — 2026-W24

Sampling time:

**2026-06-08 00:00 UTC**

Preserved Moon position from `ephem.md`:

**♓ 12°16′**

Equivalent geocentric tropical ecliptic longitude:

**342.266667°**

Recovered compact lunar engine evaluated at UTC:

**342.247680°**

Residual:

**−0.018986°**

or approximately:

**−1.14 arcminutes**

Result:

**2/2 BASELINE REPRODUCED**

---

# Improvement 1 — Dynamical-Time Evaluation

ELP2000-82B is a dynamical lunar theory. The lunar model should therefore
be evaluated using a dynamical time argument rather than treating UTC as
the independent variable of the orbital theory.

For these 2025–2026 regression cases, use:

**TT = UTC + 69.184 seconds**

This corresponds to the modern relation:

**TT = TAI + 32.184 seconds**

with TAI−UTC = 37 seconds.

The recovered compact lunar engine is left otherwise unchanged. This makes
the time-scale correction a single isolated experimental change.

## Improved Case 1 — 2026-W01

Sampling time:

**2025-12-29 00:00 UTC**

Dynamical evaluation time:

**2025-12-29 00:01:09.184 TT**

Preserved longitude:

**22.933333°**

Compact engine evaluated with TT offset:

**22.920983°**

Residual:

**−0.012350°**

or approximately:

**−0.74 arcminutes**

Baseline residual:

**−1.42 arcminutes**

Improvement:

**about 0.68 arcminutes**

Result:

**IMPROVED**

## Improved Case 2 — 2026-W24

Sampling time:

**2026-06-08 00:00 UTC**

Dynamical evaluation time:

**2026-06-08 00:01:09.184 TT**

Preserved longitude:

**342.266667°**

Compact engine evaluated with TT offset:

**342.257930°**

Residual:

**−0.008736°**

or approximately:

**−0.52 arcminutes**

Baseline residual:

**−1.14 arcminutes**

Improvement:

**about 0.62 arcminutes**

Result:

**IMPROVED**

## Regression Result

The first controlled improvement reduces the absolute lunar-longitude
residual in both preserved cases.

**2/2 CASES IMPROVED**

No lunar perturbation coefficients were changed. The only change was the
time scale used to evaluate the lunar motion.

This is accepted as Improvement 1.

The next increment should preserve this time treatment and introduce the
first actual ELP2000 longitude-series terms as a separate, independently
testable change.
