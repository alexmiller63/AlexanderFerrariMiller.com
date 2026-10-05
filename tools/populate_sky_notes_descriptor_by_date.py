#!/usr/bin/env python3
"""Populate descriptor-first Sky Notes and story presentations from Calendar IDs."""
from __future__ import annotations

import csv
import html
import json
import re

from almanack_sections import replace_section_inner
from almanack_paths import week_index
from iso_date_range import group_by_year, parse_range_args
from star_almanack_planets import load_weekly_longitudes
import populate_sky_notes_by_date as base
from fixed_object_stories import available_stories, reader_story_url
from sky_note_descriptors import build_descriptors, decorate_note_html, lunar_highlight_descriptors, write_descriptor_records

FIXED_OBJECT_DATABASE = base.ROOT / "database" / "fixed-objects.json"
FIXED_OBJECT_REGISTRY = base.ROOT / "database" / "fixed-object-registry.json"
STELLAR_CATALOG = base.ROOT / "bright-stars-2mag.csv"

BAYER_NAMES = {"Alp":"Alpha","Bet":"Beta","Gam":"Gamma","Del":"Delta","Eps":"Epsilon","Zet":"Zeta","Eta":"Eta","The":"Theta","Iot":"Iota","Kap":"Kappa","Lam":"Lambda","Mu":"Mu","Nu":"Nu","Xi":"Xi","Omi":"Omicron","Pi":"Pi","Rho":"Rho","Sig":"Sigma","Tau":"Tau","Ups":"Upsilon","Phi":"Phi","Chi":"Chi","Psi":"Psi","Ome":"Omega"}

def _bayer_display_name(code: str, constellation: str) -> str:
    """Render a catalogued Bayer code as a reader-facing stellar name."""
    match = re.match(r"([A-Za-z]+)(.*)", code)
    stem, suffix = (match.group(1), match.group(2)) if match else (code, "")
    return f"{BAYER_NAMES.get(stem, stem)}{suffix} {constellation}"


def _bayer_fallback_name(facts: dict) -> str | None:
    """Recover an unnamed Bayer star from database facts, never Calendar display text."""
    notes = str(facts.get("notes") or "")
    match = re.search(r"(?:^|;\\s*)bayer_code=([^;]+)", notes)
    code = match.group(1).strip() if match else ""
    con = str(facts.get("constellation") or "").strip()
    if not code or not con:
        return None
    m = re.match(r"([A-Za-z]+)(.*)", code)
    stem, suffix = (m.group(1), m.group(2)) if m else (code, "")
    return f"{BAYER_NAMES.get(stem, stem)}{suffix} {con}"


def calendar_fixed_object_ids(page_path) -> list[int]:
    """Read permanent object identities carried by Calendar event cells."""
    text = page_path.read_text(encoding="utf-8")
    ids = []
    seen = set()
    for raw in re.findall(r'\bdata-fixed-object-id="(\d+)"', text):
        fixed_id = int(raw)
        if fixed_id not in seen:
            seen.add(fixed_id)
            ids.append(fixed_id)
    return ids


def calendar_observing_aids(page_path) -> dict[int, str]:
    """Read semantic observing-aid metadata attached to Calendar identities."""
    text = page_path.read_text(encoding="utf-8")
    aids: dict[int, str] = {}
    for match in re.finditer(
        r'<div[^>]*class="[^"]*event-cell[^"]*"[^>]*data-fixed-object-id="(\d+)"[^>]*data-observing-aid="([^"]+)"[^>]*>',
        text,
        flags=re.I,
    ):
        aids[int(match.group(1))] = match.group(2).lower().replace("_", " ")
    return aids


def fixed_object_metadata() -> dict[int, dict]:
    """Resolve presentation metadata from normalized records keyed by immutable ID."""
    payload = json.loads(FIXED_OBJECT_DATABASE.read_text(encoding="utf-8"))
    result: dict[int, dict] = {}
    for obj in payload.get("fixed_objects") or []:
        fixed_id = obj["fixed_object_id"]
        meta = {"fixed_object_id": fixed_id}
        for record in obj.get("source_records") or []:
            facts = record.get("facts") or {}
            if facts.get("name") and not meta.get("name"):
                meta["name"] = facts["name"]
            if facts.get("constellation") and not meta.get("constellation"):
                meta["constellation"] = facts["constellation"]
            family = facts.get("object_type_family")
            if family and not meta.get("object_type_family"):
                meta["object_type_family"] = family
            if record.get("source") == "fixed-objects.yaml:bayer":
                bayer_name = facts.get("name") or _bayer_fallback_name(facts)
                if bayer_name:
                    meta["name"] = bayer_name
                if facts.get("constellation"):
                    meta["constellation"] = facts["constellation"]
        result[fixed_id] = meta

    # Some bright stars intentionally have no proper name (for example
    # Gamma-2 Velorum).  Resolve their Bayer identity through the permanent
    # HIP identifier, exactly as the Sky Notes artwork generator does.
    registry = json.loads(FIXED_OBJECT_REGISTRY.read_text(encoding="utf-8"))
    registry_hip: dict[str, int] = {}
    for obj in registry.get("fixed_objects") or []:
        fixed_id = obj.get("fixed_object_id")
        for identifier in obj.get("identifiers") or []:
            if str(identifier.get("namespace", "")).lower() == "hip":
                registry_hip[str(identifier.get("value"))] = fixed_id

    with STELLAR_CATALOG.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            fixed_id = registry_hip.get(str(row.get("hip") or "").strip())
            if fixed_id is None or fixed_id not in result:
                continue
            bayer = str(row.get("bayer") or "").strip()
            constellation = str(row.get("con") or "").strip()
            proper = str(row.get("proper") or row.get("name") or "").strip()
            if constellation:
                result[fixed_id]["constellation"] = constellation
            if proper:
                result[fixed_id]["name"] = proper
            elif bayer and constellation and not result[fixed_id].get("name"):
                result[fixed_id]["name"] = _bayer_display_name(bayer, constellation)
            if bayer:
                result[fixed_id]["object_type_family"] = "star"
    return result


def fixed_sky_from_ids(fixed_ids: list[int], metadata: dict[int, dict]) -> list[dict]:
    """Build fixed-sky objects from identity records, never from Calendar display text."""
    result = []
    for fixed_id in fixed_ids:
        meta = metadata.get(fixed_id)
        if meta is None:
            raise RuntimeError(f"Calendar references unknown fixed_object_id {fixed_id}")
        name = meta.get("name")
        family = meta.get("object_type_family")
        if not name or not family:
            continue
        item = {
            "fixed_object_id": fixed_id,
            "type": "star" if family == "star" else "deep-sky",
            "name": name,
        }
        if family == "star" and meta.get("constellation"):
            item["constellation"] = meta["constellation"]
        result.append(item)
    return result


def story_candidates(fixed_ids: list[int]) -> list[dict]:
    """Return the complete ordered story pool; never apply presentation limits here."""
    candidates = []
    seen = set()
    for fixed_id in fixed_ids:
        for story in available_stories(fixed_id):
            key = (story.collection, story.fixed_object_id)
            if key in seen:
                continue
            seen.add(key)
            candidate = {
                "fixed_object_id": story.fixed_object_id,
                "collection": story.collection,
                "hed": story.hed,
                "dek": story.dek,
                "body": story.body,
                "url": story.public_url,
            }
            # Absence of artwork is represented by absence of the field, not a
            # public null placeholder.  Curated stories add the field only
            # when they actually declare an artwork kind.
            if story.artwork is not None:
                candidate["artwork"] = story.artwork
            candidates.append(candidate)
    return candidates


def story_presentations(candidates: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep prose on canonical story pages; expose every story as a weekly reader link."""
    return [], list(candidates)


def binocular_finder_guidance(items: list[dict]) -> str:
    """Give binocular targets a concrete, source-backed finder instruction."""
    instructions = []
    for item in items:
        fixed_id = item["fixed_object_id"]
        spec_path = base.ROOT / "sky-notes-artwork" / "specs" / "objects" / f"{fixed_id}.json"
        if spec_path.exists():
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            constellation = str(spec.get("name") or item.get("constellation") or "").strip()
            target = str(
                (spec.get("artwork_owner_identity") or {}).get("proper_name")
                or item.get("name") or ""
            ).strip()
            paths = spec.get("figure_paths") or []
            target_ref = (spec.get("artwork_owner_identity") or {}).get("renderer_ref")
            target_paths = [path for path in paths if target_ref in path]
            closed_paths = [
                path for path in target_paths
                if len(path) >= 4 and path[0] == path[-1]
            ]
            four_corner = any(len(set(path[:-1])) == 4 for path in closed_paths)
            closed = bool(closed_paths)
            if constellation and target:
                if four_corner:
                    shape = "diamond-shaped figure"
                elif closed:
                    shape = "closed figure"
                else:
                    shape = "charted figure"
                instructions.append(
                    f"Trace {constellation}’s {shape} in the finder, then identify {target} at its charted position."
                )
                continue
        constellation = str(item.get("constellation") or "").strip()
        name = str(item.get("name") or "").strip()
        if constellation:
            instructions.append(f"Trace the charted figure of {constellation}, then identify {name} at its plotted position.")
        else:
            instructions.append(f"Use the object finder to identify {name} from the surrounding plotted stars.")
    return " ".join(instructions)


def observer_note(year: int, week: int, page_path, fixed: list[dict], relations: list[dict]) -> str:
    """Compose observer prose from identity-backed fixed-sky objects."""
    rows = base.calendar_events_from_page(page_path)
    monday, sunday = rows[0][0], rows[-1][0]
    entries = [entry for _, items in rows for entry in items]
    moon = next((entry for entry in entries if re.search(r"\b(New Moon|First Quarter|Full Moon|Last Quarter)\b", entry, flags=re.I)), None)
    opening = f"ISO {year}-W{week:02d} runs from {monday.strftime('%B')} {monday.day} through {sunday.strftime('%B')} {sunday.day}."
    if relations:
        opening += " " + " ".join(base.relation_sentence(item) for item in relations[:2])

    moon_text = moon or "No principal lunar phase is listed this week"
    if moon and "New Moon" in moon:
        condition = "The dark Moon favors faint targets and extended star fields."
    elif moon and "Full Moon" in moon:
        condition = "Bright moonlight favors prominent stars and planets while reducing contrast on faint deep-sky objects."
    elif moon:
        condition = "Moderate moonlight makes timing and local sky position important for faint targets."
    else:
        condition = "Check the Moon's position each night and favor darker hours for low-contrast targets."

    # Calendar is authoritative for observing aid; immutable object ID joins
    # that classification to normalized Sky Notes identity.
    observing_aids = calendar_observing_aids(page_path)
    by_id = {item["fixed_object_id"]: item for item in fixed}
    naked = [by_id[i]["name"] for i, aid in observing_aids.items() if aid == "naked eye" and i in by_id]
    binocular_items = [by_id[i] for i, aid in observing_aids.items() if aid == "binoculars" and i in by_id]
    binocular = [item["name"] for item in binocular_items]
    telescope = [by_id[i]["name"] for i, aid in observing_aids.items() if aid == "telescope" and i in by_id]
    substantial = [by_id[i]["name"] for i, aid in observing_aids.items() if aid == "substantial telescope" and i in by_id]
    naked_guidance = (
        f"Use {', '.join(naked)} as the week’s fixed-sky framework."
        if naked else
        "No fixed-sky Calendar object is classified for naked-eye observing this week."
    )
    binocular_guidance = (
        binocular_finder_guidance(binocular_items)
        if binocular_items else
        "No fixed-sky Calendar object is classified for binocular observing this week."
    )
    telescope_guidance = (
        f"Concentrate on {', '.join(telescope)}. Increase magnification only after the target and surrounding pattern are secure."
        if telescope else
        "No fixed-sky Calendar object is classified for telescope observing this week."
    )
    substantial_guidance = (
        f"These targets call for a substantial telescope: {', '.join(substantial)}."
        if substantial else
        "No fixed-sky Calendar object is classified as requiring a substantial telescope this week."
    )
    deep_sky_notice = "" if any(item["type"] == "deep-sky" for item in fixed) else "No deep-sky objects are featured this week."
    planet_paragraph = (
        " ".join(base.relation_sentence(item) for item in relations)
        if relations else
        "No close longitude relationship passes the conservative weekly selection threshold; use the Planet Finder for the broader Solar-System pattern."
    )
    return "\n\n".join((
        opening,
        f"**Naked eye:** {moon_text}. {condition} {naked_guidance}",
        f"**Planets:** {planet_paragraph}",
        f"**Binoculars:** {binocular_guidance}",
        f"**Small telescope:** {telescope_guidance}",
        f"**Substantial telescope:** {substantial_guidance}",
        deep_sky_notice,
    ))


def story_artwork_descriptor(year: int, week: int, fixed_sky: list[dict], relations: list[dict], stories: list[dict]) -> dict | None:
    requests = [story for story in stories if story.get("artwork")]
    if not requests:
        return None
    kinds = {story["artwork"] for story in requests}
    if kinds != {"stellar-finder"}:
        raise RuntimeError(f"Unsupported story artwork request(s) for ISO {year}-W{week:02d}: {sorted(kinds)}")
    descriptor = base.artwork_descriptor(year, week, fixed_sky, relations)
    if descriptor is None:
        raise RuntimeError(
            f"ISO {year}-W{week:02d}: Calendar story requests stellar-finder artwork "
            "but accepted fixed-sky geometry cannot supply it"
        )
    descriptor["story_sources"] = [
        {"collection": story["collection"], "fixed_object_id": story["fixed_object_id"], "artwork": story["artwork"]}
        for story in requests
    ]
    return descriptor


def render_inline_stories(stories: list[dict]) -> str:
    blocks = []
    for story in stories:
        hed = html.escape(story["hed"])
        dek = html.escape(story["dek"])
        url = html.escape(reader_story_url(story["url"]), quote=True)
        body_html = "".join(
            f"<p>{html.escape(' '.join(part.splitlines()))}</p>"
            for part in re.split(r"\n\s*\n", story["body"].strip()) if part.strip()
        )
        blocks.append(
            '<article class="sky-note-story sky-note-story-inline" '
            f'data-fixed-object-id="{story["fixed_object_id"]}" data-story-collection="{html.escape(story["collection"], quote=True)}">'
            f'<h4><a href="{url}">{hed}</a></h4>'
            f'<p class="sky-note-story-dek">{dek}</p>'
            f'{body_html}'
            f'<p><a href="{url}">Read the story.</a></p>'
            '</article>'
        )
    return "\n".join(blocks)


def render_linked_stories(stories: list[dict]) -> str:
    if not stories:
        return ""
    items = []
    for story in stories:
        hed = html.escape(story["hed"])
        dek = html.escape(story["dek"])
        url = html.escape(reader_story_url(story["url"]), quote=True)
        items.append(
            f'<li data-fixed-object-id="{story["fixed_object_id"]}" '
            f'data-story-collection="{html.escape(story["collection"], quote=True)}">'
            f'<a href="{url}">{hed}</a> — {dek}</li>'
        )
    return '<div class="sky-note-more-stories"><h4>More Sky Notes</h4><ul>' + "".join(items) + '</ul></div>'


def descriptor_policy() -> dict:
    return {
        "source_of_truth": "machine-readable JSON",
        "candidate_pool": "complete; presentation never limits discovery",
        "presentation": "Wordy",
        "story_limit": None,
        "wordy_policy": "rich weekly observing prose; link to complete object stories rather than embedding them",
        "future_presentations": [],
        "link_target": "/almanack/descriptors/<fixed_object_id>.json for fixed-object descriptors",
        "artwork_descriptor_is_separate": True,
        "artwork_source": "explicit story front matter only",
        "fixed_sky_identity_source": "Calendar data-fixed-object-id + data-observing-aid + database/fixed-objects.json",
        "story_identity_source": "Calendar data-fixed-object-id only",
        "story_source": "stories/<collection>/<fixed_object_id>.md",
        "inline_story_content": "hed + dek + body",
        "linked_story_content": "reader-facing links to every available canonical object story",
        "annual_note_is_separate_from_evergreen_story": True,
    }


def generated_note(year: int, week: int, page_path, yearly, stars: list[dict]) -> dict:
    payload = base.generated_note(year, week, page_path, yearly, stars)
    fixed_ids = calendar_fixed_object_ids(page_path)
    fixed = fixed_sky_from_ids(fixed_ids, fixed_object_metadata())
    payload["fixed_sky"] = fixed
    payload["note"] = observer_note(year, week, page_path, fixed, payload["planet_relations"])
    payload["descriptors"] = build_descriptors(
        fixed, payload["planet_relations"], stars,
        base.CONSTELLATION_NAMES, base.ASTERISMS,
    )
    payload["descriptors"].extend(lunar_highlight_descriptors(page_path))
    candidates = story_candidates(fixed_ids)
    inline, linked = story_presentations(candidates)
    payload["calendar_fixed_object_ids"] = fixed_ids
    payload["story_candidates"] = candidates
    payload["inline_stories"] = inline
    payload["linked_stories"] = linked
    payload["stories"] = candidates
    # Fixed-object artwork remains immutable/object-owned. Planet finder
    # artwork is generated explicitly because base.generated_note() intentionally
    # does not emit legacy week-owned artwork.
    weekly_artwork = base.artwork_descriptor(year, week, fixed, payload["planet_relations"])
    if weekly_artwork and (weekly_artwork.get("finder_route") or {}).get("planet"):
        payload["planet_finder_artwork"] = weekly_artwork
    payload.pop("artwork", None)
    payload["descriptor_policy"] = descriptor_policy()
    return payload


def patch_page(path, payload: dict) -> bool:
    text = path.read_text(encoding="utf-8")
    rendered = base.render_note(payload["note"])
    rendered = decorate_note_html(rendered, payload["descriptors"], payload.get("calendar_fixed_object_ids", []))
    # Object-story prose is not embedded in weekly pages.  The observing guide
    # links to canonical story pages, which own the prose and artwork.
    inline = render_inline_stories(payload.get("inline_stories", []))
    linked = render_linked_stories(payload.get("linked_stories", []))
    # Legacy week-owned artwork is deliberately removed. Fixed-object artwork
    # belongs on the object story/package and is published independently.
    artwork_slot = ""
    body = rendered + "\n"
    if inline:
        body += inline + "\n"
    if linked:
        body += linked + "\n"
    if artwork_slot:
        body += artwork_slot + "\n"
    # Highlights and Wordy are two views of the same structured Sky Note.
    # The toggle state is controlled entirely by setMode() below.
    mode_toggle = (
        '<div class="sky-note-mode-toggle" role="group" aria-label="Sky Notes presentation" '
        'style="display:inline-flex;align-items:center;gap:0;padding:.18rem;border:1px solid currentColor;border-radius:999px">'
        '<span class="sky-note-mode-label" style="padding:0 .55rem 0 .35rem">View:</span>'
        '<button type="button" data-sky-note-mode="highlights" aria-pressed="false" '
        'style="border:0;border-radius:999px 0 0 999px;padding:.35rem .7rem">Highlights</button>'
        '<button type="button" data-sky-note-mode="wordy" aria-pressed="true" '
        'style="border:0;border-left:1px solid currentColor;border-radius:0 999px 999px 0;padding:.35rem .7rem">Wordy</button>'
        '</div>'
    )
    highlights = render_linked_stories(payload.get("linked_stories", []))
    if not highlights:
        highlights = '<p class="sky-note-highlights-empty">No linked Sky Note stories are available for this week.</p>'
    script = '''<script id="sky-note-mode-script">(function(){
const root=document.querySelector('.sky-note');
const buttons=document.querySelectorAll('[data-sky-note-mode]');
if(!root||!buttons.length)return;
const wordy=root.querySelector('.sky-note-wordy');
const highlights=root.querySelector('.sky-note-highlights');
function setMode(mode){
  const isHighlights=mode==='highlights';
  if(wordy)wordy.hidden=isHighlights;
  if(highlights)highlights.hidden=!isHighlights;
  buttons.forEach(b=>{
    const active=b.dataset.skyNoteMode===mode;
    b.setAttribute('aria-pressed',active?'true':'false');
    b.classList.toggle('is-active',active);
    b.style.fontWeight=active?'700':'400';
    b.style.textDecoration='none';
    b.style.boxShadow=active?'inset 0 0 0 2px currentColor':'none';
    b.style.opacity=active?'1':'.72';
  });
}
buttons.forEach(b=>b.addEventListener('click',()=>setMode(b.dataset.skyNoteMode)));
setMode('wordy');
})();</script>'''
    section_html = '<h3>Sky Notes</h3>' + mode_toggle + '<div class="sky-note">\n' + '<div class="sky-note-wordy">' + body + '</div>\n' + '<div class="sky-note-highlights" hidden><h4>Highlights</h4>' + highlights + '</div>\n' + script + '</div>'
    new = replace_section_inner(text, 5, section_html, path)
    if new == text:
        return False
    path.write_text(new, encoding="utf-8")
    return True


def main() -> None:
    start, end, weeks = parse_range_args("Create descriptor-first Star Almanack Sky Notes by inclusive ISO date range")
    stars = base.load_bright_stars()
    metadata = fixed_object_metadata()
    grouped = group_by_year(weeks)
    yearly = {year: load_weekly_longitudes(year) for year in grouped}
    changed = 0

    for item in weeks:
        week_key = f"W{item.week:02d}"
        public_page = week_index(item.year, item.week)
        if not public_page.exists():
            raise RuntimeError(f"Missing weekly page: {public_page.relative_to(base.ROOT)}")

        payload = base.generated_note(item.year, item.week, public_page, yearly[item.year], stars)
        fixed_ids = calendar_fixed_object_ids(public_page)
        fixed = fixed_sky_from_ids(fixed_ids, metadata)
        payload["fixed_sky"] = fixed
        payload["note"] = observer_note(item.year, item.week, public_page, fixed, payload["planet_relations"])
        payload["descriptors"] = build_descriptors(
            fixed, payload["planet_relations"], stars, base.CONSTELLATION_NAMES, base.ASTERISMS
        )
        payload["descriptors"].extend(lunar_highlight_descriptors(public_page))
        candidates = story_candidates(fixed_ids)
        inline, linked = story_presentations(candidates)
        payload["calendar_fixed_object_ids"] = fixed_ids
        payload["story_candidates"] = candidates
        payload["inline_stories"] = inline
        payload["linked_stories"] = linked
        payload["stories"] = candidates
        # Fixed-object artwork remains immutable/object-owned. Planet finder
        # artwork is generated explicitly because base.generated_note() intentionally
        # does not emit legacy week-owned artwork.
        weekly_artwork = base.artwork_descriptor(item.year, item.week, fixed, payload["planet_relations"])
        if weekly_artwork and (weekly_artwork.get("finder_route") or {}).get("planet"):
            payload["planet_finder_artwork"] = weekly_artwork
        payload.pop("artwork", None)
        payload["descriptor_policy"] = descriptor_policy()
        descriptor_ids = {str(record["id"]) for record in payload["descriptors"]}
        missing_descriptor_ids = [str(fixed_id) for fixed_id in fixed_ids if str(fixed_id) not in descriptor_ids]
        if missing_descriptor_ids:
            raise RuntimeError(
                f"ISO {item.year}-{week_key}: fixed objects missing descriptor records: " + ", ".join(missing_descriptor_ids)
            )
        write_descriptor_records(payload["descriptors"])
        source = base.write_generated_source(item.year, item.week, payload)

        path = week_index(item.year, item.week)
        if not path.exists():
            raise RuntimeError(f"Missing weekly page: {path.relative_to(base.ROOT)}")
        if patch_page(path, payload):
            changed += 1

        art_state = "fixed-object artwork plus weekly planet finder when applicable"
        print(
            f"Generated descriptor-first Sky Note for ISO {item.year}-{week_key}: "
            f"{source.relative_to(base.ROOT)} ({len(payload['descriptors'])} descriptors; "
            f"{len(payload['story_candidates'])} story candidates; "
            f"{len(payload['inline_stories'])} inline; {len(payload['linked_stories'])} linked; {art_state})"
        )

    print(
        f"Descriptor-first Sky Notes complete for {start.isoformat()} through {end.isoformat()}: "
        f"{len(weeks)} notes generated, {changed} page copies updated"
    )


if __name__ == "__main__":
    main()
