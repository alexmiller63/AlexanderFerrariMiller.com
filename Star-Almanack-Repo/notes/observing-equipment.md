# Observing Equipment Convention

## Editorial principle

The Star Almanack is an observer-facing almanack, not merely a printed catalog. Its equipment recommendation should answer:

> What should a city observer take outside to enjoy this object?

It should **not** answer the more theoretical question of whether an exceptional observer might possibly detect the object without optical aid under favorable or dark-sky conditions.

## Urban-observer baseline

The Almanack is designed with a city observer in mind. Light pollution therefore makes a conservative naked-eye recommendation appropriate. Objects that may technically be naked-eye objects under dark skies may deliberately receive a **Binocular** recommendation for an urban observer.

**Binocular is an important positive observing category**, not merely a fallback between naked eye and telescope. This also supports the Almanack's role as an advertisement for binocular observing.

## Symbols

- Naked eye: Star Almanack eye SVG
- Binocular: Star Almanack binoculars SVG
- Telescope: Star Almanack telescope SVG

The generated calendar should use these shared SVG assets rather than literal placeholder letters or unrelated Unicode symbols.

## Stellar-pattern classification

Constellations and asterisms are classified from the **median V magnitude of their member stars**.

- For an asterism, use every star in the resolved asterism membership list, not merely convex-hull vertices.
- For a constellation, use every star that participates in the adopted Martz/MacRobert stick figure, not every star inside the IAU boundary.
- For an even number of member stars, use the ordinary statistical median: the mean of the two middle magnitudes after sorting.
- The classification is intrinsic to the stellar pattern and is therefore reused across Almanack years; the annual date still comes from the 9:00 PM local-apparent-solar-time transit rule.

For stellar patterns the shared observer thresholds are:

- median V <= 3.0: **Naked eye**
- 3.0 < median V <= 6.0: **Binoculars**
- median V > 6.0: **Telescope**

These thresholds live in one shared source module so constellation and asterism generators cannot drift apart.

## Constellation stick-figure source rule

The adopted IAU/MacRobert stick-figure dataset supplies source-defined figures for 86 of the 88 constellations. It explicitly records **Mensa** and **Microscopium** as having **no stick figure**. The Almanack treats that absence as part of the source convention, not as missing data to be filled in.

Therefore:

- Do not invent or supplement stick figures for Mensa or Microscopium merely to force a set of 88 figures.
- Do not calculate a stick-figure median V magnitude or derived observer glyph for either constellation.
- Preserve an explicit `no stick figure` state in the constellation data model.
- Other field guides and atlases may use different constellation stick figures. Those are legitimate alternative conventions, but the Almanack should use one internally consistent convention rather than mix figures from multiple traditions.

### Front-matter note

Preserve a short explanatory front-matter section titled **“What’s with Mensa and Microscopium?”** It should explain that constellation stick figures are conventions rather than official constellation boundaries; different field guides may connect stars differently; the Almanack adopts one consistent IAU/MacRobert convention; and that convention explicitly leaves Mensa and Microscopium without stick figures. The Almanack should preserve that intentional distinction rather than manufacture figures for them.

## Extended-object classification status

The median-star rule above applies only to stellar patterns. Exact equipment borders for extended deep-sky objects are **not settled by this rule**. Integrated magnitude can be misleading for galaxies, nebulae, and other extended objects, so those recommendations should continue to be based on practical observer-facing guidance and object type rather than reusing the stellar-pattern thresholds mechanically.
