# Independent eclipse engine — implementation audit (2026–2035)

Status: **implementation in progress; NOT independently validated**. This branch must not replace the published eclipse results until all gates below pass.

## Existing production path

- `besselian_eclipse_engine.py` obtains Besselian elements through `eclipse_calc.elements.bessels_at`, an externally implemented algorithm. **Remove this dependency from production**, while retaining the existing output as a frozen regression baseline.
- Its JDTDB minimization is deliberately performed on a small offset from the day's start, preventing absolute-Julian-date stopping-tolerance errors. **Preserve this numerical technique**.
- `eclipse_engine.py` has a separate geometric solar eclipse search based on the local ELP2000-82B Moon model and a compact Sun model. Evaluate its accuracy against independently calculated SPK vectors before selecting the production geometry.
- `eclipse.yaml` has computed geometry but also publication-derived visibility/magnitude metadata. **Do not republish those fields as independent results**.
- `tools/wire_2026_eclipses.py` currently consumes the manually curated 2026 YAML. The decade generator must become its authoritative input; avoid hand-maintained year lists.

## Independent algorithm requirements

1. Read locally stored JPL SPK state vectors for Sun, Earth and Moon; document the kernel version, coordinate frame, units and time scale. No network calls during calculation.
2. Construct the Sun-to-Moon shadow axis and the fundamental plane perpendicular to that axis through Earth's center. Project the shadow axis intersection onto orthonormal plane axes to obtain x and y in Earth-equatorial-radius units. Calculate umbral/antumbral and penumbral cone radii from physical Sun/Moon radii and distances. Document sign conventions for l1/l2.
3. Search every new Moon and full Moon in 2026–2035 using computed elongation; do **not** seed the search from published eclipse tables. Find local extrema with bracketed minimization in small offsets from JDTDB.
4. For solar events, intersect the penumbral and umbral/antumbral cones with the rotating Earth ellipsoid; derive eclipse classification, local visibility and contact times geometrically. For lunar events, calculate Moon intersection with Earth's umbral/penumbral cones, with a documented atmospheric-shadow convention.
5. Convert TT/TDB to UTC only at the reporting boundary, using a documented leap-second table; explicitly separate UTC, UT1 and Earth rotation assumptions.
6. Produce machine-readable yearly output and a bordered 2026–2035 Front Matter table from that output. Do not import published magnitudes, contacts, dates or visibility text.

## Acceptance gates

- Unit tests for orthogonality, axis orientation, cone radii, no-eclipse cases and contact ordering.
- Regression against the **existing locally computed** 2026 eclipse times and geometry, with recorded numerical differences; independently investigate discrepancies rather than forcing agreement.
- Cross-year search coverage, including lunations near December/January boundaries; deduplicate events and confirm chronological order.
- Repeatable offline GitHub Actions run with pinned dependencies, locally available ephemeris input, explicit runtime limits and uploaded logs/artifacts.
- No `eclipse_calc` import anywhere on the production eclipse execution path.
- No generated output described as independent until these tests pass.

This audit records the actual current dependency and the work needed; it does **not** assert that the replacement has been written or tested.
