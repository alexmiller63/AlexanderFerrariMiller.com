# Star Almanack Planet Finder — Frozen Specification

Status: FROZEN

The Planet Finder is a locating chart, not a full horoscope. It shows the geocentric tropical ecliptic positions of the bodies from the weekly ephemeris.

## Geometry

- 0° Aries is fixed at 9:00 on the wheel.
- Zodiac longitude increases counterclockwise.
- The zodiac has 12 equal sectors of exactly 30° each.
- Planet placement is determined by exact tropical ecliptic longitude.
- A leader line must preserve the exact longitude anchor even when the label is moved for readability.
- No houses, Ascendant, Midheaven, aspects, or interpretive horoscope content.

## Bodies

The canonical set is Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune, and Ceres.

## Notation modes

Three distinct canonical renderings are frozen:

- Greek / Symbols
- Latin
- Mixed / Learner

The Greek / Symbols and Mixed / Learner modes use the established symbol notation. The zodiac symbols are black. Mixed / Learner is the learner-oriented combination of symbols and Latin names.

## Label collision rules

Labels may move within the available interior real estate. Exact longitude is retained by the leader line. Labels must not overlap each other, zodiac labels, or center explanatory text. Leader lines must not pass through other labels; they are routed around label boxes when necessary.

The Mixed / Learner collision layout is the reference behavior. Latin uses the same collision and leader-routing logic.

## W41 reference

The frozen reference week is ISO 2026-W41, using Monday, October 5, 2026 at 00:00 UTC from the Star Almanack weekly ephemeris.

Do not redesign the three templates when generating subsequent weeks. Only the body positions and week-specific metadata change.
