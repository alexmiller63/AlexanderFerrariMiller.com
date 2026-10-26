# Panoramic Sky Atlas — generator contract

The Chart Library's panoramic atlas is generated artwork, not hand-edited pages.

## Views
Six observer latitudes: +75°, +45°, +15°, −15°, −45°, −75°.
Four solar-longitude events per tropical year: 0°, 90°, 180°, 270°.
24 views per year, named by the **event**, not by a hemisphere-dependent season.
Northern and southern season names may be shown as explanatory subtitles.

## Time and geometry
Use the instant of each actual equinox/solstice, determined from the Sun's
apparent geocentric ecliptic longitude (not fixed calendar dates).
The reference sky is at 21:00 local apparent solar time on the event's local
civil date, with the reference meridian explicitly defined in the generator.
Sidereal orientation must be derived from the Sun's right ascension and
the apparent-solar-time convention, including the equation of time;
do not simply treat 21:00 as a UTC clock time.

Use a true horizon-centered all-sky projection; horizon, zenith and cardinal
directions must be labeled. Show the celestial equator, ecliptic, north/south
celestial poles, and celestial tropics. Zodiac signs (twelve equal 30° sectors)
and zodiac constellations (unequal IAU spans, including Ophiuchus) must be
distinctly identified, not conflated.

## Data and rendering
Use Star Almanack's local star data and constellation figure definitions.
Apply magnitude-scaled stars, existing figure conventions and Greek/Mixed/
English notation. Use deterministic chart IDs and output paths.
A generator run must publish a machine-readable manifest with inputs,
calculation provenance, successes and failures, and validate all 24 views.
Never hand-patch a generated chart or its generated index.

## Initial milestone
Generate and validate the six March-equinox observer views before running
the other eighteen. Do not advertise charts as available until files exist.
