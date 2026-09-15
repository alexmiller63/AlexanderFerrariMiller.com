# Constellation Observance Validation — 2026

Status: experimental validation of the boundary-centroid / 9:00 PM LAT method.

## Independent comparison set

All 88 calculated `best_date` values in `constellation-observance-2026.csv` were compared against the published **month for best visibility at 21:00 (9 p.m.)** in Wikipedia's *IAU designated constellations by geographical visibility* table.

Reference: https://en.wikipedia.org/wiki/IAU_designated_constellations_by_geographical_visibility

The published month is used only as an external check. It is not an input to the Star Almanack calculation.

## Result

- 88 constellations compared.
- 75 calculated dates fall in exactly the same named month as the published 21:00 best-visibility month.
- 13 calculated dates fall in the immediately adjacent month.
- 0 constellations differ by two or more months.

This is a strong qualitative validation of the experimental method. The comparison is especially meaningful because both systems describe approximately the same observer geometry at 21:00, while the Star Almanack date is derived independently from the official IAU boundary geometry and the apparent-Sun right-ascension calculation.

## Adjacent-month cases

| Constellation | Calculated Night of Observance | Published 21:00 month | Relation |
|---|---:|---|---|
| Camelopardalis | 2026-01-28 | February | 4 days before month begins |
| Cepheus | 2026-10-15 | November | earlier adjacent month; polar geometry diagnostic |
| Cetus | 2026-12-03 | November | 3 days after month ends |
| Corona Borealis | 2026-07-04 | June | 4 days after month ends |
| Eridanus | 2026-01-01 | December | annual-cycle boundary |
| Indus | 2026-10-01 | September | 1 day after month ends |
| Lynx | 2026-03-06 | February | 6 days after month ends |
| Norma | 2026-07-07 | June | 7 days after month ends |
| Octans | 2026-09-27 | October | 4 days before month begins; polar geometry diagnostic |
| Reticulum | 2026-01-03 | December | annual-cycle boundary |
| Sagitta | 2026-09-01 | August | 1 day after month ends |
| Tucana | 2026-11-07 | October | 7 days after month ends |
| Volans | 2026-03-01 | February | 1 day after month ends |

The adjacent-month cases are not treated as failures because the external reference is quantized to whole months, whereas the Star Almanack produces a specific date. Most are within one week of the referenced month's boundary. Cepheus is the conspicuous case to retain as a geometry diagnostic because its high declination makes a simple RA midpoint and a spherical area centroid substantially different constructions.

## Interpretation

For this validation stage:

- **Exact-month agreement:** PASS.
- **Immediately adjacent month:** boundary-compatible PASS, retained for review.
- **Difference of two or more months:** would be a validation failure requiring investigation.

By that criterion the 88-constellation experiment is **88/88 PASS**, with 75 exact-month matches and 13 adjacent-month boundary cases.

This result supports, but does not by itself finalize, promotion of **Night of Observance** into the formal Star Almanack specification. A numerical centroid-convergence check should still be completed before the experimental status is removed.
