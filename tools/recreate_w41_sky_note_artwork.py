#!/usr/bin/env python3
"""Recreate only the approved ISO 2026-W41 Sky Note artwork layer.

This script deliberately does not touch Calendar, Ephemeris, Planet Finder, or
Sky Note prose. It restores only the W41 Sky Note-specific finder assets and
embeds them inside the existing Sky Note section.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "almanack" / "2026" / "W41" / "index.html"
FINDERS = PAGE.parent / "finders"
SOURCE = ROOT / "Star-Almanack-Repo" / "observer-views" / "W41"

ASSETS = (
    ("enif-finder.svg", "enif-finder.svg"),
    ("sadalmelik-finder.svg", "sadalmelik-finder.svg"),
)

CSS = """<style id=\"w41-sky-note-artwork-css\">\n.w41-star-finder{margin:1.1rem auto 1.6rem;max-width:820px}\n.w41-star-finder img{display:block;width:100%;height:auto;border:1px solid var(--rule);border-radius:.4rem}\n.w41-star-finder figcaption{text-align:center;font-family:system-ui,sans-serif;font-size:.82rem;color:var(--muted);margin-top:.35rem}\n@media(max-width:760px){.w41-star-finder{max-width:none}}\n</style>"""

ENIF = '<figure class="w41-star-finder" data-sky-note-artwork="enif-m15"><img src="finders/enif-finder.svg" alt="Enif and M15 finder"><figcaption>Enif and M15</figcaption></figure>'
SADALMELIK = '<figure class="w41-star-finder" data-sky-note-artwork="sadalmelik-aquarius"><img src="finders/sadalmelik-finder.svg" alt="Aquarius and Sadalmelik finder"><figcaption>Aquarius and Sadalmelik</figcaption></figure>'


def sky_note_bounds(text: str) -> tuple[int, int]:
    start = text.find("<h3>Sky Note</h3>")
    if start < 0:
        raise RuntimeError("W41 Sky Note heading not found")
    next_heading = re.search(r"<h[23]>.*?</h[23]>", text[start + len("<h3>Sky Note</h3>"):], re.S)
    if next_heading:
        end = start + len("<h3>Sky Note</h3>") + next_heading.start()
    else:
        end = text.find("</main>", start)
        if end < 0:
            end = len(text)
    return start, end


def strip_owned_artwork(section: str) -> str:
    return re.sub(
        r'<figure class="w41-star-finder"[^>]*data-sky-note-artwork="(?:enif-m15|sadalmelik-aquarius)".*?</figure>\s*',
        "",
        section,
        flags=re.S,
    )


def insert_artwork(section: str) -> str:
    # Enif/M15 belongs directly after the opening prose paragraph.
    opening = re.search(r'(<h3>Sky Note</h3>\s*<p>.*?</p>)', section, re.S)
    if not opening:
        raise RuntimeError("Could not locate W41 Sky Note opening paragraph")
    section = section[:opening.end()] + "\n" + ENIF + section[opening.end():]

    # Sadalmelik/Aquarius belongs at the end of the Sky Note, before the next section.
    section = section.rstrip() + "\n" + SADALMELIK + "\n"
    return section


def main() -> None:
    if not PAGE.exists():
        raise SystemExit(f"Missing {PAGE.relative_to(ROOT)}")

    FINDERS.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in ASSETS:
        src = SOURCE / src_name
        if not src.exists():
            raise SystemExit(f"Missing preserved W41 source artwork: {src.relative_to(ROOT)}")
        shutil.copy2(src, FINDERS / dst_name)

    text = PAGE.read_text(encoding="utf-8")

    # Replace only our own style block; leave all other page CSS untouched.
    text = re.sub(r'<style id="w41-sky-note-artwork-css">.*?</style>', "", text, flags=re.S)
    if "</head>" not in text:
        raise SystemExit("W41 page has no </head>")
    text = text.replace("</head>", CSS + "</head>", 1)

    start, end = sky_note_bounds(text)
    section = strip_owned_artwork(text[start:end])
    section = insert_artwork(section)
    text = text[:start] + section + text[end:]

    PAGE.write_text(text, encoding="utf-8")
    print("Recreated ISO 2026-W41 Sky Note artwork without touching Calendar, Ephemeris, Planet Finder, or Sky Note prose")


if __name__ == "__main__":
    main()
