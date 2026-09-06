# Stellar Finder Standard

## Status

Version 1 of the Star Almanack stellar finder standard is established by 2 approved reference finders:

- `observer-views/W41/sadalmelik-finder.svg` — Aquarius / Sadalmelik
- `observer-views/W41/enif-finder.svg` — Enif / M15

These are **golden-reference finders**. Future renderer changes must not alter their approved appearance as a side effect of work on other finders.

## Standing production rule

Do **not** use image generation for Star Almanack charts, finders, constellation diagrams, or SVG revisions. Build and revise them from source code / SVG only.

## Figure and boundary conventions

- Use the Martz/MacRobert constellation stick-figure convention, based on the IAU / Sky & Telescope line dataset, for the 88 constellations.
- Treat official IAU constellation boundaries as authoritative boundaries.
- Orient the observer first with recognizable asterisms, then with recognizable constellation stick figures.
- Ordinary constellation stick figures use blue (`#5c8fe8`).
- Recognizable orienting asterisms use green (`#59c86d`).
- Official constellation boundaries use the established light boundary style (`#c4ccd8`).

## Target and object highlighting

- Use open yellow circles for target or specifically highlighted objects.
- Standard yellow: `#ffd84d`.
- Standard reference ring style: `s=180`, `linewidth=2.6`, no fill.
- Do not use target arrows in the approved reference style.

## Labels

- Labels must remain legible and must not be obscured by constellation lines.
- Use night-sky background boxes where necessary to keep labels readable.
- Bayer designations use Greek symbols with 3-letter constellation abbreviations where needed.
- Preserve correct constellation ownership across boundaries; for example, Alpheratz is α And.
- Deep-sky labels should identify the object and object type where useful; avoid unnecessary proper-name clutter.

## Aquarius / Sadalmelik reference

Approved features include:

- Sadalmelik highlighted with a yellow open circle and no arrow.
- Aquarius Martz/MacRobert stick figure retained.
- Official Aquarius boundary retained.
- Water Jar used as the primary orienting asterism.
- Main Aquarius view keeps the Water Jar uncluttered by proper star names.
- A dedicated Water Jar binocular inset supplies proper names and Greek/Bayer identifiers.
- The inset is embedded in available night-sky space in the main finder.
- Sadalmelik label remains to the right of the star.
- Previously resolved label collisions must remain resolved.

## Enif / M15 reference

Approved features include:

- Title: `Enif M15 Finder`.
- Enif and M15 highlighted with yellow open circles and no arrows.
- M15 labeled `M15 · globular cluster`.
- Approximate Enif–M15 separation label `≈4°` retained.
- Great Square retained as the green orienting asterism.
- Ordinary Pegasus stick figure retained in blue.
- Great Square corners preserve their correct identities: Markab = α Peg, Scheat = β Peg, Algenib = γ Peg, Alpheratz = α And.
- Official boundary and rectangular framing retained.

## Regression rule

Before changing shared finder-rendering code, verify both approved reference finders after the change. If a change is intended only for another finder, Aquarius and Enif/M15 should remain visually unchanged.

The approved SVGs are the practical visual specification when prose and rendering behavior disagree.
