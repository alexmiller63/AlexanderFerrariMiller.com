# Star Almanack — Candidate Objects

This document contains the expanded working catalog of stars and Messier objects used in the development and testing of Star Almanack.

Best visibility is defined as the annual moment when an object transits the local meridian at 9:00 PM local apparent solar time.

For an object with right ascension α:

α_sun = α_object − 9h

The annual instant at which the apparent Sun reaches that right ascension determines the object's best-visibility date.

## Declination Bands

Star Almanack groups objects into five declination bands based approximately on Earth's axial tilt:

- **Arctic:** +66.5° to +90°

- **Northern:** +23.5° to +66.5°

- **Tropical:** −23.5° to +23.5°

- **Southern:** −66.5° to −23.5°

- **Antarctic:** −90° to −66.5°

These categories provide a simple physical description of an object's position north or south of the celestial equator without requiring the reader to work directly with declination coordinates.

## Season Convention

Star Almanack uses astronomical rather than meteorological seasons.

Season boundaries are defined by the calculated apparent solar-longitude crossings:

- **0° — March equinox — Spring begins**

- **90° — June solstice — Summer begins**

- **180° — September equinox — Autumn begins**

- **270° — December solstice — Winter begins**

For 2026, the calculated boundaries are:

- March equinox — Mar 20, 14:45:58 UTC

- June solstice — Jun 21, 08:24:31 UTC

- September equinox — Sep 23, 00:05:13 UTC

- December solstice — Dec 21, 20:50:15 UTC

These four boundaries are calculated using the same solar-longitude machinery used for the twelve zodiac ingresses.

Published U.S. Naval Observatory values agree with all four calculations to the Observatory's published one-minute precision.

For **Arctic** and **Antarctic** objects, Star Almanack does not assign a single observing season. Their season field is left blank.

---

# Original 20-Object Validation Set

The original expanded test set consists of 10 stars and 10 Messier objects.

These results are preserved as regression cases.

## 10 Stars

| Star | Bayer designation | Best visibility |

|---|---|---|

| Canopus | α Carinae | Feb 7 |

| Alpha Centauri | α Centauri | Jun 16 |

| Achernar | α Eridani | Dec 3 |

| Acrux | α Crucis | May 15 |

| Bellatrix | γ Orionis | Jan 24 |

| Fomalhaut | α Piscis Austrini | Oct 25 |

| Castor | α Geminorum | Feb 26 |

| Alkaid | η Ursae Majoris | Jun 4 |

| Dubhe | α Ursae Majoris | Apr 23 |

| Polaris | α Ursae Minoris | Dec 16 |

## 10 Messier Objects

| Object | Common name/type | Best visibility |

|---|---|---|

| M31 | Andromeda Galaxy | Nov 20 |

| M42 | Orion Nebula | Jan 26 |

| M45 | Pleiades | Jan 1 |

| M44 | Beehive Cluster | Mar 15 |

| M13 | Hercules Cluster | Jul 16 |

| M57 | Ring Nebula | Aug 19 |

| M8 | Lagoon Nebula | Aug 6 |

| M20 | Trifid Nebula | Aug 6 |

| M27 | Dumbbell Nebula | Sep 6 |

| M51 | Whirlpool Galaxy | May 31 |

---

# 80 Additional Candidate Objects

These 80 objects extend the original 20-object set to a working catalog of 100 objects.

## 40 Additional Stars

| Star | Bayer designation | Best visibility | Season | Declination band |

|---|---|---|---|---|

| Sirius | α Canis Majoris | Feb 13 | Winter | Tropical |

| Rigel | β Orionis | Jan 21 | Winter | Tropical |

| Capella | α Aurigae | Jan 22 | Winter | Northern |

| Betelgeuse | α Orionis | Jan 31 | Winter | Tropical |

| Procyon | α Canis Minoris | Feb 27 | Winter | Tropical |

| Pollux | β Geminorum | Feb 28 | Winter | Northern |

| Regulus | α Leonis | Apr 8 | Spring | Tropical |

| Spica | α Virginis | May 29 | Spring | Tropical |

| Arcturus | α Boötis | Jun 11 | Spring | Tropical |

| Antares | α Scorpii | Jul 13 | Summer | Southern |

| Vega | α Lyrae | Aug 15 | Summer | Northern |

| Albireo | β Cygni | Aug 29 | Summer | Northern |

| Altair | α Aquilae | Sep 4 | Summer | Tropical |

| Deneb | α Cygni | Sep 18 | Summer | Northern |

| Aldebaran | α Tauri | Jan 12 | Winter | Tropical |

| Hadar | β Centauri | Jun 8 | Spring | Southern |

| Mimosa | β Crucis | May 20 | Spring | Southern |

| Gacrux | γ Crucis | May 16 | Spring | Southern |

| Alioth | ε Ursae Majoris | May 22 | Spring | Northern |

| Mizar | ζ Ursae Majoris | May 29 | Spring | Northern |

| Merak | β Ursae Majoris | Apr 23 | Spring | Northern |

| Phecda | γ Ursae Majoris | May 6 | Spring | Northern |

| Megrez | δ Ursae Majoris | May 12 | Spring | Northern |

| Alnilam | ε Orionis | Jan 27 | Winter | Tropical |

| Alnitak | ζ Orionis | Jan 28 | Winter | Tropical |

| Mintaka | δ Orionis | Jan 26 | Winter | Tropical |

| Saiph | κ Orionis | Jan 29 | Winter | Tropical |

| Elnath | β Tauri | Jan 24 | Winter | Northern |

| Mirfak | α Persei | Dec 27 | Winter | Northern |

| Algol | β Persei | Dec 24 | Winter | Northern |

| Denebola | β Leonis | May 5 | Spring | Tropical |

| Alphecca | α Coronae Borealis | Jun 30 | Summer | Northern |

| Rasalhague | α Ophiuchi | Jul 29 | Summer | Tropical |

| Shaula | λ Scorpii | Jul 29 | Summer | Southern |

| Kaus Australis | ε Sagittarii | Aug 11 | Summer | Southern |

| Nunki | σ Sagittarii | Aug 20 | Summer | Southern |

| Enif | ε Pegasi | Oct 5 | Autumn | Tropical |

| Markab | α Pegasi | Oct 27 | Autumn | Tropical |

| Alpheratz | α Andromedae | Nov 12 | Autumn | Northern |

| Kochab | β Ursae Minoris | Jun 19 | — | Arctic |

## 40 Additional Messier Objects

| Object | Common name/type | Best visibility | Season | Declination band |

|---|---|---|---|---|

| M1 | Crab Nebula | Jan 26 | Winter | Tropical |

| M2 | Globular Cluster | Oct 2 | Autumn | Tropical |

| M3 | Globular Cluster | Jun 3 | Spring | Northern |

| M4 | Globular Cluster | Jul 12 | Summer | Southern |

| M5 | Globular Cluster | Jun 26 | Summer | Tropical |

| M6 | Butterfly Cluster | Jul 31 | Summer | Southern |

| M7 | Ptolemy's Cluster | Aug 3 | Summer | Southern |

| M10 | Globular Cluster | Jul 20 | Summer | Tropical |

| M11 | Wild Duck Cluster | Aug 18 | Summer | Tropical |

| M12 | Globular Cluster | Jul 17 | Summer | Tropical |

| M15 | Globular Cluster | Oct 1 | Autumn | Tropical |

| M16 | Eagle Nebula | Aug 10 | Summer | Tropical |

| M17 | Omega Nebula | Aug 10 | Summer | Tropical |

| M22 | Globular Cluster | Aug 14 | Summer | Southern |

| M24 | Sagittarius Star Cloud | Aug 9 | Summer | Tropical |

| M33 | Triangulum Galaxy | Dec 2 | Autumn | Northern |

| M34 | Open Cluster | Dec 18 | Autumn | Northern |

| M35 | Open Cluster | Feb 4 | Winter | Northern |

| M36 | Open Cluster | Jan 27 | Winter | Northern |

| M37 | Open Cluster | Jan 31 | Winter | Northern |

| M38 | Open Cluster | Jan 25 | Winter | Northern |

| M39 | Open Cluster | Oct 2 | Autumn | Northern |

| M41 | Open Cluster | Feb 13 | Winter | Tropical |

| M46 | Open Cluster | Feb 27 | Winter | Tropical |

| M47 | Open Cluster | Feb 26 | Winter | Tropical |

| M50 | Open Cluster | Feb 17 | Winter | Tropical |

| M52 | Open Cluster | Nov 1 | Autumn | Northern |

| M63 | Sunflower Galaxy | May 27 | Spring | Northern |

| M64 | Black Eye Galaxy | May 22 | Spring | Tropical |

| M65 | Galaxy | Apr 27 | Spring | Tropical |

| M66 | Galaxy | Apr 28 | Spring | Tropical |

| M67 | Open Cluster | Mar 18 | Winter | Tropical |

| M81 | Bode's Galaxy | Apr 5 | — | Arctic |

| M82 | Cigar Galaxy | Apr 5 | — | Arctic |

| M92 | Globular Cluster | Jul 25 | Summer | Northern |

| M97 | Owl Nebula | Apr 26 | Spring | Northern |

| M101 | Pinwheel Galaxy | Jun 8 | Spring | Northern |

| M104 | Sombrero Galaxy | May 18 | Spring | Tropical |

| M106 | Galaxy | May 13 | Spring | Northern |

| M110 | Satellite Galaxy of M31 | Nov 20 | Autumn | Northern |

---

# Working Catalog

The current Star Almanack working catalog therefore contains:

- 50 stars

- 50 Messier objects

- 100 objects total

The original 20-object validation set remains preserved separately within this document so that later changes to the calculations can be checked against the historical results.

The 80-object expansion provides a broader range of right ascensions, declination bands, observing seasons, stellar landmarks, clusters, nebulae, and galaxies for development of the 2026 Almanack.

## Arctic and Antarctic Objects

Arctic and Antarctic objects require a different interpretation of

best visibility from objects in the Northern, Tropical, and Southern

declination bands.

They are therefore not assigned an observing season.

At sufficiently favorable terrestrial latitudes, an Arctic or

Antarctic object may be circumpolar and remain above the horizon

throughout the year. At other latitudes, the same object may rise and

set, remain very low above the horizon, or never become visible at all.

Star Almanack nevertheless retains a best-visibility date for these

objects.

For an Arctic or Antarctic object, the best-visibility date identifies

when the object transits the local meridian at 9:00 PM local apparent

solar time. At meridian transit the object reaches its greatest altitude

for that daily passage.

The date therefore describes favorable evening placement rather than

the beginning or center of an observing season.

This distinction is particularly useful near the limits of an object's

visibility. An object that barely rises from a particular latitude is

most favorably placed when its meridian transit occurs at a convenient

evening hour. Roughly six months away from that date, its corresponding

meridian transit occurs approximately twelve hours away in local time,

and the object may be below the horizon at 9:00 PM.

For this reason, Arctic and Antarctic objects retain their

best-visibility dates even though they are not assigned seasons.

