#!/usr/bin/env python3
"""Patch build_expanded_almanack.py for the extended Solar-System ephemeris.

This is intentionally narrow and self-checking: it replaces only the known
7-body ephemeris helper and weekly heading in the existing builder. The legacy
input paragraph must remain unchanged so the builder can still recognize the
historical almanack.md source before producing updated expanded-edition prose.
"""
from pathlib import Path

path = Path(__file__).parent / "build_expanded_almanack.py"
text = path.read_text(encoding="utf-8")

old = '''    def ephem_table(row):
        cols = [("☉ Sun", row["sun"]), ("☽ Moon", row["moon"]), ("☿ Mercury", row["mercury"]),
                ("♀ Venus", row["venus"]), ("♂ Mars", row["mars"]), ("♃ Jupiter", row["jupiter"]),
                ("♄ Saturn", row["saturn"])]
        return ("| " + " | ".join(x[0] for x in cols) + " |\\n"
                "|---:|---:|---:|---:|---:|---:|\\n"
                "| " + " | ".join(x[1] for x in cols) + " |")
'''
new = '''    def ephem_table(row):
        primary = [("☉ Sun", row["sun"]), ("☽ Moon", row["moon"]), ("☿ Mercury", row["mercury"]),
                   ("♀ Venus", row["venus"]), ("♂ Mars", row["mars"]), ("♃ Jupiter", row["jupiter"]),
                   ("♄ Saturn", row["saturn"])]
        extended = [("♅ Uranus", row["uranus"]), ("♆ Neptune", row["neptune"]), ("⚳ Ceres", row["ceres"])]

        def render(cols):
            return ("| " + " | ".join(x[0] for x in cols) + " |\\n"
                    "|" + "|".join("---:" for _ in cols) + "|\\n"
                    "| " + " | ".join(x[1] for x in cols) + " |")

        return render(primary) + "\\n\\n**Extended targets:**\\n\\n" + render(extended)
'''
if old in text:
    text = text.replace(old, new, 1)
elif 'extended = [("♅ Uranus"' not in text:
    raise SystemExit("Expected legacy ephem_table helper was not found")

text = text.replace('"### Weekly Classical-Planet Ephemeris\\n\\n"', '"### Weekly Solar-System Ephemeris\\n\\n"')

# Keep the exact legacy input paragraph intact. An earlier patch changed this
# string and made the builder reject the still-correct historical source.
text = text.replace(
    'This working edition integrates the supplied 2026 zodiac calendar, best-visibility dates for 100 selected stars and Messier objects, lunar phases, Wheel-of-the-Year points, named full moons, and the 53 weekly Solar-System snapshots.',
    'This working edition integrates the supplied 2026 zodiac calendar, best-visibility dates for 100 selected stars and Messier objects, lunar phases, Wheel-of-the-Year points, named full moons, and the 53 weekly classical-planet snapshots.',
)

# The generated expanded edition should use the new observer-facing scope.
expanded_marker = 'This working edition covers the complete 53-week ISO 2026 week-year'
if expanded_marker in text:
    before, after = text.split(expanded_marker, 1)
    after = after.replace('weekly classical-planet snapshots.', 'weekly Solar-System snapshots.', 1)
    text = before + expanded_marker + after

path.write_text(text, encoding="utf-8")
print("Patched build_expanded_almanack.py for Uranus, Neptune, and Ceres")
