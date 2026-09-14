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

Production version: `1.55`.

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

`tools/star_almanack_ephemeris.py` is the shared local calculation layer. It
constructs geocentric apparent vectors from cached SPK source data and converts
them to ecliptic coordinates.

The weekly ephemeris and Planet Finder use Monday 00:00 UTC publication
snapshots. The calendar/event generators use one-hour Sun/Moon samples from the
same local calculation layer, immediately represented as canonical JDTDB
`AstroInstant` values for interpolation.

Solar elongation is calculated locally from the angle between a body's and the
Sun's geocentric apparent vectors.

The following production paths must not call JPL Horizons or another
finished-answer service:

- weekly Solar-System ephemeris;
- Planet Finder;
- zodiac ingresses and Zodiac Days;
- equinoxes, solstices, and 45-degree Wheel stations;
- lunar phases and derived seasonal Moon names;
- meteor-shower solar-longitude crossings and Moon illumination context;
- Sun/Galactic-Center conjunction.

## Meteor-shower editorial source data

`tools/populate_meteor_showers.py` contains a small frozen editorial table of
nominal shower maximum solar longitudes, radiant constellations, and expected
ZHR values. These are observational/reference inputs, not downloaded ephemeris
answers.

Reference authority: International Meteor Organization (IMO), Meteor Shower
Calendar / Working List of Visual Meteor Showers.

Current reference landing page:
`https://www.imo.net/resources/calendar/`

The actual maximum instant published by Star Almanack is not copied from the
IMO calendar. Star Almanack solves the specified solar-longitude crossing from
its own locally calculated Sun longitude, then computes Moon illumination from
its own Sun/Moon geometry.

Audit note: the frozen IMO-derived constants must be compared against the
edition appropriate to each publication year before they are treated as
current editorial values. Some IMO ZHR estimates change as the working list is
revised. Provenance documentation makes that review requirement explicit rather
than silently presenting those constants as timeless computed facts.

## Galactic Center source data and method

The physical Galactic Center event uses Sagittarius A* as its fixed-source
reference.

The J2000 radio position currently encoded in
`tools/populate_galactic_center.py` is:

- RA 17h 45m 40.0409s;
- Dec -29° 00′ 28.118″.

Source: Reid & Brunthaler (2004), *The Proper Motion of Sagittarius A*. II. The
Mass of Sagittarius A**, ApJ 616, 872. Later papers reproduce these coordinates
with attribution to Reid & Brunthaler. SIMBAD provides an independently
maintained catalog position and bibliographic trail and may be used for
validation.

The ecliptic-of-date conversion uses an independently implemented IAU 1976
precession model. The coefficient source is the published astronomical standard
associated with Lieske et al. (1977), "Expressions for the Precession Quantities
Based upon the IAU (1976) System of Astronomical Constants," A&A 58, 1. No
third-party software implementation of those formulae is copied into the
Almanack.

The conjunction time is solved by Star Almanack from the locally calculated Sun
longitude and the attributed Sgr A* source coordinates; it is not copied from a
published conjunction table.

## Validation

External ephemerides may be consulted as independent checks. A validation source
must not become the generator's source of truth merely because its output is
convenient to parse. Validation comparisons should be identified as such in the
workflow or audit record.

JPL Horizons remains an acceptable validation authority. It is not a production
answer feed.

## Audit status

As of 2026-09-13:

- unaudited hand-entered magnitude constants and the unattributed Ceres H-G
  implementation were removed from the production module;
- weekly ephemeris and Planet Finder were moved from runtime Horizons answers to
  locally computed SPK-based positions;
- calendar Sun/Moon astronomy was moved to the same local SPK calculation path;
- meteor-shower and Galactic-Center event solvers were detached from the former
  Horizons calendar feed;
- Skyfield is pinned and recorded as an MIT-licensed imported dependency;
- the meteor-shower frozen editorial table remains flagged for year-by-year IMO
  source review rather than being represented as independently derived data.

Legacy, diagnostic, validation, and historical files may still mention or query
Horizons. Their presence is acceptable only if they cannot feed production
outputs without an explicit validation-only boundary.
