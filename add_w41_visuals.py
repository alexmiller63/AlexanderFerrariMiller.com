#!/usr/bin/env python3
"""Insert the frozen W41 visual finders into the generated weekly page.

The weekly publisher owns the HTML generation. This post-processing step keeps
W41's creative composition separate and deterministic: the three Planet
Finders sit immediately below the ephemerides, while the Enif/M15 and
Aquarius/Sadalmelik finders are embedded in the Sky Note.
"""
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).parent
PAGE = ROOT / "site" / "2026" / "W41" / "index.html"
SOURCE = ROOT / "observer-views" / "W41"
DEST = PAGE.parent

PLANET_FINDERS = (
    ("planet-finder-greek-symbols.svg", "Greek / Symbols"),
    ("planet-finder-latin.svg", "Latin"),
    ("planet-finder-mixed-learner.svg", "Mixed / Learner"),
)
STELLAR_FINDERS = (
    ("enif-finder.svg", "Enif / M15 finder"),
    ("sadalmelik-finder.svg", "Aquarius / Sadalmelik finder"),
)

CSS = '''<style id="w41-visuals-css">
.w41-planet-finders{display:flex;flex-wrap:wrap;gap:1rem;justify-content:center;margin:1.25rem 0 2rem}
.w41-planet-finder{flex:1 1 300px;max-width:480px;margin:0;text-align:center}
.w41-planet-finder img{display:block;width:100%;height:auto;border:1px solid #cbd3da;border-radius:.5rem;background:#fff}
.w41-planet-finder figcaption,.w41-stellar-finder figcaption{text-align:center;margin-top:.35rem;font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;font-size:.82rem;color:var(--muted)}
.w41-stellar-finder{margin:1.15rem auto 1.35rem;max-width:760px;text-align:center}
.w41-stellar-finder img{display:block;width:100%;height:auto;border:1px solid #cbd3da;border-radius:.5rem;background:#fff}
@media(max-width:760px){.w41-planet-finder{flex-basis:100%;max-width:100%}.w41-stellar-finder{margin-left:0;margin-right:0}}
</style>'''


def copy_assets() -> None:
    for filename, _ in PLANET_FINDERS + STELLAR_FINDERS:
        source = SOURCE / filename
        if not source.is_file():
            raise SystemExit(f"Missing W41 visual source: {source}")
        shutil.copy2(source, DEST / filename)


def planet_block() -> str:
    items = []
    for filename, label in PLANET_FINDERS:
        items.append(
            f'<figure class="w41-planet-finder"><img src="{filename}" alt="W41 Planet Finder — {label}"><figcaption>{label}</figcaption></figure>'
        )
    return '<section class="w41-planet-finders" aria-label="W41 Planet Finders">' + ''.join(items) + '</section>'


def stellar_block(filename: str, label: str) -> str:
    return f'<figure class="w41-stellar-finder"><img src="{filename}" alt="{label}"><figcaption>{label}</figcaption></figure>'


def insert_once(text: str, needle: str, insertion: str, description: str) -> str:
    if insertion in text:
        return text
    if needle not in text:
        raise SystemExit(f"W41 visual insertion point not found: {description}")
    return text.replace(needle, needle + insertion, 1)


def main() -> None:
    if not PAGE.is_file():
        raise SystemExit(f"Missing generated W41 page: {PAGE}")
    text = PAGE.read_text(encoding="utf-8")
    copy_assets()

    # Keep the CSS in the page head, not in the content flow.
    if 'id="w41-visuals-css"' not in text:
        text = text.replace('</style></head>', CSS + '</style></head>', 1)

    # Planet Finders immediately after the Extended targets table.
    extended = re.search(r'(<p><strong>Extended targets:</strong></p><table>.*?</table>)', text)
    if not extended:
        raise SystemExit("Could not locate W41 extended-targets ephemeris")
    if 'aria-label="W41 Planet Finders"' not in text:
        end = extended.end()
        text = text[:end] + planet_block() + text[end:]

    # Enif/M15 finder belongs inside the Sky Note, directly after the opening
    # paragraph that introduces Enif and M15.
    enif_pattern = r'(<h3>Sky Note</h3><p>The New Moon on Saturday, October 10.*?</p>)'
    if 'enif-finder.svg' not in text:
        text, count = re.subn(enif_pattern, r'\1' + stellar_block('enif-finder.svg','Enif / M15 finder'), text, count=1, flags=re.S)
        if count != 1:
            raise SystemExit("Could not locate W41 Enif/M15 Sky Note insertion point")

    # Aquarius/Sadalmelik finder belongs at the end of the W41 Sky Note, just
    # before the existing Chart section.
    if 'sadalmelik-finder.svg' not in text:
        marker = '<h3>Chart</h3>'
        text = insert_once(text, marker, stellar_block('sadalmelik-finder.svg','Aquarius / Sadalmelik finder'), 'Chart heading')

    PAGE.write_text(text, encoding="utf-8")
    print("Inserted frozen W41 Planet Finders and stellar finders")


if __name__ == '__main__':
    main()
