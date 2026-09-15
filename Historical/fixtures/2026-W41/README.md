# ISO 2026-W41 preserved recreation fixture

This directory preserves the approved ISO 2026-W41 state as a reconstruction and regression reference.

The immutable reference commit is:

`1bd40b5c05db344f1cb959f3c1385c7ee39f0bf3`

That commit contains the approved W41 page, its curated Sky Note source, its published Planet Finder artwork, and the observer-view source artwork used by the Sky Note.

## Ownership boundaries

W41 is preserved as a whole reference, but recreation must respect the Almanack population architecture:

- Calendar is owned by **Populate Calendar — by ISO date**.
- Ephemeris and Planet Finder are owned by **Populate Ephemeris + Planet Finder — by ISO date**.
- Sky Note prose is owned by **Populate Sky Notes — by ISO date**.
- Sky Note artwork and its embeds are owned by **Populate Sky Notes Artwork — by ISO date**.

The Sky Notes Artwork workflow must never regenerate or overwrite the Planet Finder.

## Sky Note artwork recreation

Run `python tools/recreate_w41_sky_note_artwork.py` to recreate only the approved Sky Note artwork layer. It copies the preserved Enif/M15 and Sadalmelik/Aquarius finder sources into the published W41 finder directory and restores their placements inside the Sky Note without rewriting Calendar, Ephemeris, Planet Finder, or Sky Note prose.

The source artwork is already preserved under `Historical/observer-views/W41/`. The expected Git blob SHAs and placement rules are recorded in `manifest.json`.

## Full historical recovery

If a future reconstruction needs to inspect the exact approved W41 state, any tracked file can be recovered directly from the baseline commit, for example:

`git show 1bd40b5c05db344f1cb959f3c1385c7ee39f0bf3:almanack/2026/W41/index.html`

The baseline page is a reference specimen, not a replacement template: do not copy the entire page over a newer page because that would overwrite sections owned by other population workflows.
