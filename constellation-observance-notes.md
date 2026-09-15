# Constellation Observance Notes

Status: experimental notes only. These ideas are not yet part of the formal Star Almanack specification.

## Observer-centered constellation date

Treat each of the 88 IAU constellations as an official bounded region of the celestial sphere, not as a chosen stick figure or a hand-picked list of stars.

For each constellation:

1. Obtain the official IAU boundary coordinates.
2. Compute the spherical area centroid of the bounded constellation region.
3. Let the centroid right ascension be `α_constellation`.
4. Apply the Star Almanack observer-first rule at 9:00 PM local apparent time (LAT):

   `α_sun = α_constellation - 9h`

5. Solve for the annual instant when the apparent Sun reaches that right ascension.
6. Round to the nearest civil date using the same convention used for fixed-object visibility.
7. Assign the resulting date to its ISO week and zodiac month.

The result is the constellation's experimental **Night of Observance**: the night when the geometric center of the official constellation region transits the meridian at 9:00 PM LAT.

## Zodiac terminology

Keep one Sun-centered **Zodiac Month**.

For each zodiac constellation, add one observer-centered **Zodiac Night of Observance**.

- Zodiac Month: follows the Sun.
- Zodiac Night of Observance: follows the 9 PM observer.

The expected displacement is not exactly six months because the observing criterion is 9 PM transit rather than midnight opposition. A 9-hour right-ascension separation corresponds to roughly 4.5 months of the annual cycle before smaller astronomical effects and the exact constellation geometry are considered.

## Validation experiment

The 88 constellations form an independent validation set.

The calculation SHALL NOT use published observing seasons as an input. Instead:

`official boundary geometry -> spherical centroid -> 9 PM LAT date -> season/zodiac placement -> compare with published observing season`

Published descriptions such as "best seen in winter" are therefore an external sanity check rather than a fitted parameter.

Large or oddly shaped constellations are especially useful diagnostics. A disagreement may reveal a centroid-definition issue, boundary-geometry issue, or simply the coarseness of traditional seasonal labels.

## Asterism extension

The same observer-first mathematics may be tested for asterisms, but their center is defined differently:

- official constellations: spherical area centroid of the IAU boundary region;
- asterisms: spherical centroid of the defining stars.

Asterisms remain instructional/orientation features. Their proposed greatest-visibility dates are experimental until tested.

## Orientation model

Use the teaching grammar:

**Anchor -> Route -> Destination**

- Anchor: an unmistakable pattern.
- Route: a pointer line, arc, extension, or other star-hop relation.
- Destination: a star, constellation, Messier object, deep-sky object, or another asterism.

Orientation charts use **9:00 PM LAT** as their common reference time.

For the Big Dipper seasonal chart, test four same-hour silhouettes around Polaris and include the mnemonic **"spring up, fall down."**

## Data source

The International Astronomical Union publishes J2000 boundary-coordinate text files for the 88 official constellations. These boundary files, rather than star lists, should be the geometric source for the constellation-centroid experiment.
