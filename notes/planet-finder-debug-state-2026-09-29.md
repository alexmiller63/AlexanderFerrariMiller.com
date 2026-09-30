# Planet Finder debug state — 2026-09-29/30

## Exact stopping point
Alexander went to bed while **AA- Test Planet Finder Conjunctions** was running after commit `8e242481e0d84f044670cce799d97b0ac9b654aa` (`8e24248`). On return, inspect that run before making any further changes.

## What the preceding completed run established
Run/job supplied immediately before this state:
- Run `36669751385`
- Job `109742012405`
- Completed result discussed: 11 failed, 2 passed in about 13m33s.

The important diagnostics from that run were:
- W01 Greek progressive ladder passed through exact-W01.
- W36 repeatedly exposed an **Uranus -> Venus dead end**.
- Diagnostic seen: `REPEATED-DEAD-END STOP ... body=Venus dead-ends=2,000`.
- W36 summary seen: `prefixes=1,999 zero-viable=1,999 venus-generated=0 venus-viable=0`.
- This Uranus/Venus behavior occurred in Greek, Latin, and Mixed.
- Promotion also exposed a separate issue in Greek: `ordering cycle while promoting Uranus`.
- A later Pluto `nodes=0/candidates=0` timeout was determined not to mean Pluto itself consumed the whole clock; the preceding search had already consumed essentially the shared 60-second budget before DFS reached Pluto.

## Correction made before the current run
Earlier shorthand was misread: `uranus-250` and `uranus-055` are **absolute longitudes 250° and 55°**, NOT 2.50° and 0.55°.

Existing `tests/test_planet_finder_ultimate_ladders.py` had:
- `uranus-250` at Uranus=250
- `uranus-055` at Uranus=55
- `uranus-060` at Uranus=60
- `uranus-061` at Uranus=61
- real W36 Uranus longitude about 60°05′39″

At 61°, Uranus joins the Ceres/Mars alignment group according to the test's expected classification.

## Change just committed
Commit: `8e242481e0d84f044670cce799d97b0ac9b654aa`

Purpose: add a focused W36 Uranus longitude sweep/breakpoint diagnostic to find the actual transition associated with Venus losing viable candidates, while explicitly checking alignment classification and stopping/reporting around the first failure rather than rerunning the entire expensive suite blindly.

File modified:
- `tests/test_planet_finder_ultimate_ladders.py`

## Current hypothesis / debugging order
Treat these as two distinct problems until evidence connects them:
1. **Primary:** W36 Uranus-prefix geometry/search state systematically leaves Venus with zero viable candidates. Determine the precise Uranus-longitude breakpoint and what changes there (classification vs candidate/validator behavior).
2. **Secondary:** promotion state machine can cycle (`ordering cycle while promoting Uranus`). Do not redesign promotion until the Uranus/Venus breakpoint is understood.

Do NOT return to broad architectural rewriting. The goal is a small deterministic reproducer and a concrete implementation bug.

## Tomorrow's first action
1. Inspect the currently-running AA- Test Planet Finder Conjunctions run started after commit `8e24248`.
2. Read its summary for the new Uranus sweep/breakpoint diagnostic.
3. Identify the last passing longitude and first failing longitude, plus whether the alignment classification changed at that boundary.
4. Only then inspect the candidate-generation/viability path responsible for Venus=0 viable candidates.

Production solver code was intentionally not changed by the diagnostic test modification.