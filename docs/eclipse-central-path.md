# Calculated eclipse center tracks

The catalog generator now calculates the central solar track from the same
Sun–Moon vectors and spherical-Earth shadow geometry used for hybrid
classification. It reads no published eclipse paths or coordinates.

For each sample, the calculation intersects the forward shadow-axis ray with
the near side of a sphere of radius 6378.137 km. It rotates the resulting
J2000 ecliptic vector into ITRS using Skyfield's frame rotations and locally
loaded timescale, then calculates geocentric latitude and east longitude.
The signed core radius at the intersection determines whether that part of
the track is total or annular.

The default interval is 60 seconds. Greatest eclipse and any valid rounded
axis-entry/exit samples are also included. A rounded boundary falling outside
the sphere is omitted; the first/last plotted samples are not exact path
endpoints. Phase changes are sampled, not separately root-solved. Lines split
at the antimeridian rather than crossing the whole longitude plot.

The JSON catalog stores the track under `central_path`. Its CSV counterpart
stores that field as JSON. The page publisher renders an original coordinate
plot and table and exports CSV and GeoJSON beside each central eclipse page.
For these pages, the calculated track replaces the external reference map
and regional descriptions in the visibility display. Existing reference
metadata and older calculation records remain stored. Partial solar and
lunar eclipse visibility displays are unchanged by this initial central-track
implementation.

This is a center-line calculation. Path width, northern/southern limits,
partial-eclipse visibility, local contacts, Earth flattening, and propagation
of light are not yet included. Future Earth rotation uses the locally loaded
Skyfield UT1 estimate; no Earth-orientation data is fetched by the calculation.

## Run

```sh
python -m unittest discover -s tests -p test_eclipse_path.py
python tools/generate_decade_eclipses.py --start-year 2025 --end-year 2036 --kernel star-almanack/assets/ephemera/de440s.bsp
python tools/integrate_eclipses.py --catalog generated/eclipse-catalog/eclipses-2025-2036.json
```

The catalog workflow runs the focused tests before generation. Publication
continues through the existing eclipse publisher; Build All is unnecessary.
