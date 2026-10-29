# Seasonal Star Almanack — implementation contract

The seasonal calendar is an alternative view of the same data used by the ISO-week calendar, not an independent astronomical computation.

## Coverage and navigation
- Thirteen chronological pages: Winter 2024, Spring–Winter 2025, Spring–Winter 2026, Spring–Winter 2027.
- Winter is named for its starting year. Winter 2024 includes January 1, 2025; Winter 2027 continues into 2028.
- Every seasonal page links to the previous and next season when present, and to the seasonal index.
- Add **Seasons** to the Star Almanack navigation, alongside the existing Calendar.

## Date and zodiac rules
- Season Day 1 is the UTC civil date of the existing solar ingress: Aries 0°, Cancer 90°, Libra 180°, Capricorn 270°.
- The last date of a season is the civil day preceding the next season's ingress date.
- Include every civil day exactly once; do not fix seasons to 90, 91, 92, or 93 days.
- Preserve the existing zodiac-day labels and ingress-date convention in `calendar_core.py`; each season spans three consecutive zodiac signs.
- Ingresses are computed once in the existing calendar pipeline, then reused; no separate intercalation rule.

## Event selection
- Retain the same nonplanetary objects, best-visibility events, links, and observing labels as the weekly source data, on their original single best-visibility dates.
- Omit routine daily planetary positions and planetary finder tables. Retain significant observational planetary events: oppositions, greatest elongations, close apparent conjunctions, maximum brilliance, apparent retrograde/direct stations, lunar occultations of planets, and rare solar transits. Include apparent retrograde and direct stations (start and end of apparent westward motion), with UTC time, constellation, sky position, and observing conditions. These are astronomical events, not astrological interpretations. No astrology or astrological interpretations.
- The weekly calendar is the canonical event source. Add special planetary events to its event-generation pipeline first; seasonal pages must reuse the same dated records without independent calculations.
- Include solar and lunar eclipses on their event dates, with type and existing information links.
- Include meteor showers on their peak dates, with activity intervals in descriptions and existing information links.
- Retain the Moon's four principal phases (New, First Quarter, Full, Last Quarter) only on their event dates, not daily Moon positions.
- Full Moon names must be read from the canonical naming engine, not guessed from Gregorian month names: preserve the protected Harvest Moon, Moon Before Yule, Moon After Yule, seasonal Blue Moon, and any Frost Moon.
- Preserve any other nonplanetary calendar events from the weekly view without introducing duplicate events.

## Presentation and verification
- One date row per civil day, with columns Date, Zodiac Day, Events. Group visually by month if helpful, without splitting the season.
- Use a responsive, accessible table and the same notation conventions as the weekly calendar.
- Assert: 13 pages, consecutive nonoverlapping day coverage, correct seasonal boundaries, exactly three sign ingresses per season, no daily lunar positions, no routine daily planet positions, and event parity with the weekly source.
- Validate cross-year coverage against the 2025–2027 weekly source, including the 2024 and 2028 winter edges. Do not publish an incomplete season as complete.

## Missing boundary ISO weeks
- Generate and populate ISO 2024-W51 and 2024-W52 to cover the December 2024 solstice through December 29. ISO 2025-W01 already covers December 30–31, 2024.
- Generate and populate the ISO 2028 weeks required through the March 2028 equinox (likely W01–W12; determine the last required week from the canonical ingress calculation, not an assumed date).
- Use `tools/scaffold_almanack_weeks.py` for shells, then the existing calendar, fixed-sky, eclipse, and meteor pipelines. A shell is not a complete week.
- Validate boundary-week dates, zodiac labels, event completeness, and season coverage before publishing. Do not silently invent or omit astronomical events.
