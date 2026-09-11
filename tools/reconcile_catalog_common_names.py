#!/usr/bin/env python3
"""Apply one common-name policy to Messier, Caldwell, and Finest NGC output."""
from __future__ import annotations

import datetime as dt

import catalog_common_names as names
import standardize_messier_calendar as messier
import populate_caldwell as caldwell
import populate_finest_ngc as finest
from star_almanack_astronomy import declination_band, season_for

# Messier common-name policy now lives in the canonical Messier renderer.

# Caldwell: preserve genuine Caldwell common names, and fill overlap names from
# the RASC Finest NGC source when Caldwell itself is blank.
# Keep this wrapper API-compatible with populate_caldwell.calendar_label so the
# shared reconciliation pass can replace the renderer without dropping current
# observing-aid or asterism behavior.
def caldwell_label(r, finest_ids, asterism_ids):
    cid = r["caldwell"].strip()
    catalog = r.get("catalog", "").strip()
    name = names.preferred_deep_sky_name(catalog, r.get("name", ""))
    obj_type = caldwell.TYPE_LABELS.get(r.get("type", "").strip(), "deep-sky object")
    constellation = caldwell.CONSTELLATIONS.get(r.get("con", "").strip(), r.get("con", "").strip())

    identity = [cid]
    for value in (catalog, name):
        if value and value.casefold() not in {x.casefold() for x in identity}:
            identity.append(value)

    head = ", ".join(identity) + f", {obj_type}"
    if cid in asterism_ids:
        head += " (also an asterism)"
    head += f" in {constellation}"

    day = dt.date.fromisoformat(r["best_date"])
    mag = r.get("mag", "").strip()
    aid = caldwell.observing_aid_for_magnitude(mag)
    glyph = caldwell.HTML_AID[aid] if aid is not None else ""
    vis = " ".join(p for p in (glyph, f"V {mag}" if mag else "") if p)

    parts = [head]
    if vis:
        parts.append(f'<span class="visibility-magnitude">{vis}</span>')
    if cid in finest_ids:
        parts.append("Finest NGC")
    parts.append(f"{declination_band(r['dec_deg'])} {season_for(day)}")
    return " — ".join(parts)

caldwell.calendar_label = caldwell_label

# Finest NGC: suppress alternate catalog identifiers masquerading as names;
# retain genuine names such as UFO Galaxy, PacMan Nebula, and Flame Nebula.
def finest_label(r):
    catalog = r["catalog"].strip()
    name = names.preferred_deep_sky_name(catalog, r.get("name", ""))
    typ = finest.TYPE_LABELS.get(r.get("type", "").strip(), "deep-sky object")
    con = finest.CONSTELLATIONS.get(r.get("con", "").strip(), r.get("con", "").strip())
    head = f"{catalog}, {name}, {typ} in {con}" if name else f"{catalog}, {typ} in {con}"
    day = dt.date.fromisoformat(r["best_date"])
    mag = r.get("mag", "").strip()
    vis = f"{finest.TELESCOPE_GLYPH} V {mag}" if mag else finest.TELESCOPE_GLYPH
    observing = f'<span class="visibility-magnitude">{vis}</span>'
    return f"{head} — {observing} — Finest NGC — {declination_band(r['dec_deg'])} {season_for(day)}"

finest.label = finest_label


def main():
    # Rerun the three catalog renderers after installing the shared name policy.
    messier.main()
    caldwell.main()
    finest.main()


if __name__ == "__main__":
    main()
