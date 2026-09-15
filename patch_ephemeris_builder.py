#!/usr/bin/env python3
"""Patch build_expanded_almanack.py for Pluto and ecliptic latitude beta.

This patch is intentionally narrow and idempotent. It updates only the weekly
Solar-System ephemeris helper and related observer-facing prose, leaving the
legacy input paragraph recognizable by the expanded builder.
"""
from pathlib import Path

path = Path(__file__).parent / "build_expanded_almanack.py"
text = path.read_text(encoding="utf-8")

old_extended = '''        extended = [("♅ Uranus", row["uranus"]), ("♆ Neptune", row["neptune"]), ("⚳ Ceres", row["ceres"])]

        def render(cols):
            return ("| " + " | ".join(x[0] for x in cols) + " |\\n"
                    "|" + "|".join("---:" for _ in cols) + "|\\n"
                    "| " + " | ".join(x[1] for x in cols) + " |")

        return render(primary) + "\\n\\n**Extended targets:**\\n\\n" + render(extended)
'''
new_extended = '''        extended = [("♅ Uranus", "uranus"), ("♆ Neptune", "neptune"),
                    ("⚳ Ceres", "ceres"), ("♇ Pluto", "pluto")]

        def cell(value, beta_value=""):
            return value + (f"<br><small>{beta_value}</small>" if beta_value else "")

        def render_primary(cols):
            return ("| " + " | ".join(x[0] for x in cols) + " |\\n"
                    "|" + "|".join("---:" for _ in cols) + "|\\n"
                    "| " + " | ".join(x[1] for x in cols) + " |")

        def render_extended(cols):
            return ("| " + " | ".join(label for label, _ in cols) + " |\\n"
                    "|" + "|".join("---:" for _ in cols) + "|\\n"
                    "| " + " | ".join(cell(row[key], row.get(key + "_beta", "")) for _, key in cols) + " |")

        return (render_primary(primary) + "\\n\\n**Extended targets:**\\n\\n" +
                render_extended(extended) +
                "\\n\\n**β** = ecliptic latitude (+ north, − south).")
'''

if old_extended in text:
    text = text.replace(old_extended, new_extended, 1)
elif '("♇ Pluto", "pluto")' not in text:
    raise SystemExit("Expected extended ephemeris helper was not found")

text = text.replace('"### Weekly Classical-Planet Ephemeris\\n\\n"', '"### Weekly Solar-System Ephemeris\\n\\n"')

# Keep the exact legacy input paragraph intact so historical almanack.md remains
# recognizable by the builder.
text = text.replace(
    'This working edition integrates the supplied 2026 zodiac calendar, best-visibility dates for 100 selected stars and Messier objects, lunar phases, Wheel-of-the-Year points, named full moons, and the 53 weekly Solar-System snapshots.',
    'This working edition integrates the supplied 2026 zodiac calendar, best-visibility dates for 100 selected stars and Messier objects, lunar phases, Wheel-of-the-Year points, named full moons, and the 53 weekly classical-planet snapshots.',
)

expanded_marker = 'This working edition covers the complete 53-week ISO 2026 week-year'
if expanded_marker in text:
    before, after = text.split(expanded_marker, 1)
    after = after.replace('weekly classical-planet snapshots.', 'weekly Solar-System snapshots.', 1)
    text = before + expanded_marker + after

text = text.replace(
    'Planetary positions are geocentric tropical ecliptic longitudes sampled Monday at 00:00 UTC.',
    'Planetary positions are geocentric tropical ecliptic coordinates sampled Monday at 00:00 UTC; longitude is shown in zodiac notation and β is ecliptic latitude.',
    1,
)

path.write_text(text, encoding="utf-8")
print("Patched build_expanded_almanack.py for Uranus, Neptune, Ceres, Pluto, and beta")
