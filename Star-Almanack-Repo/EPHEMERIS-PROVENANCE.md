# Ephemeris Provenance

## Rule

Star Almanack downloads source data, not finished astronomical answers.
Published tables, web ephemerides, and answer services may be used for external
validation, but they are not the production source of the Almanack's positions.

The production boundary is therefore:

1. acquire an identified astronomical source dataset under documented terms;
2. cache and reuse that dataset rather than repeatedly requesting answers;
3. compute the Almanack result locally;
4. keep third-party software dependencies identified and licensed;
5. do not copy third-party implementation code or numerical models into Star
   Almanack without explicit provenance and permission.

Keplerian ephemera in the front matter are a study aid. They are not the
production planetary ephemeris engine.

## Planetary source kernels

### JPL DE440s

Purpose: source state-vector data for the Sun, Moon, and planets over the
Almanack's current publication range.

Acquisition: cached as `.cache/skyfield/de440s.bsp` by the GitHub Actions
runtime. The kernel is reused across generator runs.

Authority: NASA/JPL Navigation and Ancillary Information Facility (NAIF).

Usage terms: NAIF's published SPICE rules state that kernels placed on the NAIF
server may be downloaded and used by anyone subject to those rules, and that
unmodified NAIF-distributed kernels may be redistributed. Acknowledgement of
SPICE/NAIF resources and source-data providers is encouraged.

Do not label this file "public domain" unless an authoritative source for that
specific legal characterization is recorded. "Freely available under the NAIF
SPICE rules" is the documented statement.

### Ceres 1900-2100 SPK

Purpose: source state-vector data for (1) Ceres, which is not supplied as a
usable Ceres target by DE440s.

Acquisition source:
`https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/asteroids/a_old_versions/ceres_1900_2100.bsp`

Runtime cache: `.cache/skyfield/ceres_1900_2100.bsp`.

Usage is governed by the same NAIF SPICE rules above. Star Almanack currently
uses the file as a runtime input and does not commit the binary kernel to this
repository.

## Calculation software

### Skyfield

Source: `https://github.com/skyfielders/python-skyfield`

License: MIT.

Role: imported runtime library for reading JPL SPK kernels, constructing
observer/body vectors, applying apparent-position corrections, converting to
the ecliptic reference frame, and calculating visual magnitude for supported
major planets.

Star Almanack does not copy Skyfield source code into its ephemeris module.
The workflow installs a pinned Skyfield release so regenerated values do not
silently change when the library is upgraded.

Skyfield documents its `planetary_magnitude()` formulae as coming from Mallama
and Hilton, "Computing Apparent Planetary Magnitude for the Astronomical
Almanac" (2018). Star Almanack calls Skyfield's implementation rather than
transcribing those formulae.

Unsupported-body magnitude models are deliberately omitted until each model's
source and constants have been separately documented. This avoids silently
introducing unattributed formulae or catalog constants for the Sun, Moon,
Ceres, or Pluto.

## Production calculations

`tools/star_almanack_ephemeris.py` computes each publication snapshot at Monday
00:00 UTC from the cached kernels. It constructs a geocentric apparent vector,
converts it to ecliptic coordinates, and returns longitude and latitude.
Solar elongation is calculated locally from the angle between the body's and
Sun's geocentric apparent vectors.

Planet Finder consumes the resulting locally computed longitude. The weekly
ephemeris consumes the same calculation layer. Neither should call JPL Horizons
or another finished-answer service in production.

## Validation

External ephemerides may be consulted as independent checks. A validation source
must not become the generator's source of truth merely because its output is
convenient to parse. Validation comparisons should be identified as such in the
workflow or audit record.

## Audit status

As of 2026-09-13, the new shared planetary calculation path has been placed
under provenance review. Unaudited hand-entered magnitude constants and an
unattributed H-G implementation were removed from the production module. The
remaining production path uses identified SPK source data plus the imported,
licensed Skyfield dependency.
