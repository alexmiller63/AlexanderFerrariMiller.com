# Seasonal Star Almanack — implementation contract

The seasonal calendar is an alternative view of the same data used by the ISO-week calendar, not an independent astronomical computation.

## Coverage and navigation
- Fourteen chronological pages: Winter 2024, Spring–Winter 2025, Spring–Winter 2026, Spring–Winter 2027.
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
- Omit planetary positions, planetary finder tables, and planet-only events.
- Retain the Moon's four principal phases (New, First Quarter, Full, Last Quarter) only on their event dates, not daily Moon positions.
- Full Moon names must be read from the canonical naming engine, not guessed from Gregorian month names: preserve the protected Harvest Moon, Moon Before Yule, Moon After Yule, seasonal Blue Moon, and any Frost Moon.
- Preserve any other nonplanetary calendar events from the weekly view without introducing duplicate events.

## Presentation and verification
- One date row per civil day, with columns Date, Zodiac Day, Events. Group visually by month if helpful, without splitting the season.
- Use a responsive, accessible table and the same notation conventions as the weekly calendar.
- Assert: 14 pages, consecutive nonoverlapping day coverage, correct seasonal boundaries, exactly three sign ingresses per season, no daily lunar positions, no planet events, and event parity with the weekly source.
- Validate cross-year coverage against the 2025–2027 weekly source, including the 2024 and 2028 winter edges. Do not publish an incomplete season as complete.
