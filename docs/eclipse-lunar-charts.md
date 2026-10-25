# Detailed calculated lunar eclipse charts

`tools/lunar_eclipse_chart.py` generates an original SVG study chart for each
lunar catalog entry through the existing eclipse publisher. No published
charts, eclipse predictions, coastlines, or network requests enter this code.
The local JPL DE440s kernel supplies geometric positional vectors.

The generator evaluates the Moon and Sun with the catalog engine's UTC-to-TT
approximation. It rotates the J2000 ecliptic vectors to J2000 equatorial
coordinates and projects the Moon onto a shadow-centered tangent plane.
Celestial north points up; east points left. The local tangent basis follows
the anti-solar axis. Each plotted contact disk uses the catalog's rounded UTC
instant and the same fixed lunar radius as the numerical engine. The path is
sampled at intervals no longer than two minutes and extends 25 minutes before
P1 and after P4. Shadow reference circles use the greatest-eclipse radii;
contact data preserve the instantaneous radii. The chart rejects a catalog
whose stored greatest axis distance disagrees with its calculated position.

The three equirectangular maps show geometric topocentric Moon-center horizon
visibility at P1, greatest eclipse, and P4. For a surface normal `n`, spherical
Earth radius `R`, and geocentric terrestrial Moon vector `m`, the Moon's center
is above the horizon when `m dot n > R`. This includes geometric parallax.
Skyfield supplies the ITRS rotation and its built-in timescale; no external
Earth-orientation tables are downloaded. Future UT1 is an estimate. Map cells
are 1 degree; the eight named reference places are approximate coordinates,
not geographic outlines. The maps do not establish whole-event visibility.
Atmospheric refraction, terrain, twilight suppression, and weather are omitted.

Contact CSV and complete chart JSON files accompany each SVG. The JSON includes
the track, contact positions, instantaneous shadow radii, terrestrial Moon
vectors, and geocentric equatorial coordinates. Magnitudes and durations on
the chart are derived from these calculations and stored UTC times. Negative
umbral magnitude is retained for penumbral eclipses rather than clipped to zero.

Generate through:

```sh
python -m pip install skyfield
python tools/integrate_eclipses.py --catalog generated/eclipse-catalog/eclipses-2025-2036.json
python -m unittest discover -s tests -p test_eclipse_artwork.py
python -m unittest discover -s tests -p test_eclipse_path.py
```

The numerical tests check all stored lunar events, contact tangency to the
instantaneous shadow within one kilometer (rounded timestamps), greatest-axis
agreement, and topocentric horizon behavior. SVGs are rendered separately for
visual inspection. Solar charts retain their existing cross-sections and
calculated central tracks; this generator is specifically for lunar events.
