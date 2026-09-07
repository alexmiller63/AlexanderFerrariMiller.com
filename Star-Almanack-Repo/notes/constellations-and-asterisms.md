# Star Almanack Notes — Constellations and Asterisms

## 2026-09-07 — Geometric centers for constellations and asterisms

The Almanack uses geometry rather than an arbitrary hand-selected coordinate to define the center of a sky figure.

### Constellations

A constellation is treated as its official IAU boundary region on the celestial sphere. Its center is the spherical area centroid of that region — intuitively, cut the constellation out of the celestial sphere and balance it on a finger; the balance point is the constellation's center.

This center is not the mean position of the constellation's stars and is not the center of a rectangular right-ascension/declination bounding box.

Canonical process:

1. Use the official constellation boundary.
2. Treat the enclosed region as an area on the celestial sphere.
3. Calculate the spherical area centroid (the balance point).
4. Use that calculated center for observer-first visibility timing and assignment to the appropriate Almanack date/ISO week.

Constellation membership for an object is likewise geometric: determine which official boundary region contains the object's sky position.

### Asterisms

Asterisms use the same geometric idea, but their boundary is derived from their selected member stars rather than from an official IAU constellation boundary.

Canonical process:

1. Curate the stars that define the asterism.
2. Construct a tight boundary around those stars with **no added margin**.
3. Treat that boundary as a region on the celestial sphere.
4. Calculate the spherical area centroid (the balance point).
5. Use that calculated center for observer-first visibility timing, labeling, and assignment to the appropriate Almanack date/ISO week.

Thus constellations and asterisms share one conceptual model:

- **Constellation:** official IAU boundary → spherical area centroid.
- **Asterism:** curated member stars → zero-margin derived boundary → spherical area centroid.

The distinction is the source of the boundary, not the method used to derive the center. This model is year-independent and should be part of the generalized Almanack generation architecture.