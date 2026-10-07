#!/usr/bin/env python3
"""Evergreen fixed-object story lookup for Star Almanack.

Every permanent fixed-object ID has a baseline story assembled from authoritative
Star Almanack data. Curated Markdown stories enrich that baseline; they never gate
whether an object can participate in Sky Notes.
"""
from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORIES_ROOT = ROOT / "stories"
FIXED_OBJECT_DATABASE = ROOT / "database" / "fixed-objects.json"
STAR_HOPS = ROOT / "guiding-star-hops.json"
FIGURE_SOURCE = ROOT / "constellation-figures.json"

COLLECTIONS = {"alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest"}
ARTWORK_KINDS = {"stellar-finder"}
BAYER_NAMES = {"Alp":"Alpha","Bet":"Beta","Gam":"Gamma","Del":"Delta","Eps":"Epsilon","Zet":"Zeta","Eta":"Eta","The":"Theta","Iot":"Iota","Kap":"Kappa","Lam":"Lambda","Mu":"Mu","Nu":"Nu","Xi":"Xi","Omi":"Omicron","Pi":"Pi","Rho":"Rho","Sig":"Sigma","Tau":"Tau","Ups":"Upsilon","Phi":"Phi","Chi":"Chi","Psi":"Psi","Ome":"Omega"}

def _bayer_fallback_name(facts: dict) -> str | None:
    notes = str(facts.get("notes") or "")
    match = re.search(r"(?:^|;\\s*)bayer_code=([^;]+)", notes)
    code = match.group(1).strip() if match else ""
    con = str(facts.get("constellation") or "").strip()
    if not code or not con:
        return None
    m = re.match(r"([A-Za-z]+)(.*)", code)
    stem, suffix = (m.group(1), m.group(2)) if m else (code, "")
    return f"{BAYER_NAMES.get(stem, stem)}{suffix} {con}"


@dataclass(frozen=True)
class Story:
    collection: str
    fixed_object_id: int
    path: Path
    hed: str
    dek: str
    body: str
    artwork: str | None = None
    url_override: str | None = None

    @property
    def public_url(self) -> str:
        if self.url_override:
            return self.url_override
        return f"/stories/{self.collection}/{self.fixed_object_id}.html"


def reader_story_url(public_url: str) -> str:
    """Return a story href that works on both custom-domain and project GitHub Pages weekly pages."""
    if not public_url.startswith("/stories/"):
        raise ValueError(f"Unexpected story public URL: {public_url!r}")
    return "../../../" + public_url.lstrip("/")


def story_path(collection: str, fixed_object_id: int) -> Path:
    if collection not in COLLECTIONS:
        raise ValueError(f"Unknown story collection: {collection}")
    if not isinstance(fixed_object_id, int) or fixed_object_id <= 0:
        raise ValueError(f"Invalid fixed_object_id: {fixed_object_id!r}")
    return STORIES_ROOT / collection / f"{fixed_object_id}.md"


def _split_front_matter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---\n", 4)
    if end < 0:
        raise RuntimeError("Unterminated Jekyll front matter")
    metadata: dict[str, str] = {}
    for raw in text[4:end].splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise RuntimeError(f"Invalid story front-matter line: {raw!r}")
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip('"\'')
    return metadata, text[end + 5:].lstrip()


def read_story(collection: str, fixed_object_id: int) -> Story | None:
    path = story_path(collection, fixed_object_id)
    if not path.exists():
        return None
    metadata, text = _split_front_matter(path.read_text(encoding="utf-8").strip())
    artwork = metadata.get("artwork") or None
    if artwork is not None and artwork not in ARTWORK_KINDS:
        raise RuntimeError(f"Unknown story artwork kind {artwork!r}: {path.relative_to(ROOT)}")
    match = re.match(r"^#\s+(.+?)\s*\n+(.*)$", text, flags=re.S)
    if not match:
        raise RuntimeError(f"Story must begin with one Markdown H1: {path.relative_to(ROOT)}")
    hed = match.group(1).strip()
    remainder = match.group(2).strip()
    parts = re.split(r"\n\s*\n", remainder, maxsplit=1)
    dek = " ".join(parts[0].splitlines()).strip()
    body = parts[1].strip() if len(parts) == 2 else ""
    if not dek:
        raise RuntimeError(f"Story must contain a dek after its H1: {path.relative_to(ROOT)}")
    return Story(collection, fixed_object_id, path, hed, dek, body, artwork)


def _fixed_object_meta(fixed_object_id: int) -> dict:
    payload = json.loads(FIXED_OBJECT_DATABASE.read_text(encoding="utf-8"))
    for obj in payload.get("fixed_objects") or []:
        if obj.get("fixed_object_id") != fixed_object_id:
            continue
        meta = {"fixed_object_id": fixed_object_id}
        for record in obj.get("source_records") or []:
            facts = record.get("facts") or {}
            if facts.get("name") and not meta.get("name"):
                meta["name"] = facts["name"]
            if facts.get("constellation") and not meta.get("constellation"):
                meta["constellation"] = facts["constellation"]
            if facts.get("object_type_family") and not meta.get("object_type_family"):
                meta["object_type_family"] = facts["object_type_family"]
            if record.get("source") == "fixed-objects.yaml:bayer":
                if facts.get("name"):
                    meta["name"] = facts["name"]
                if facts.get("constellation"):
                    meta["constellation"] = facts["constellation"]
        return meta
    raise RuntimeError(f"Unknown fixed_object_id {fixed_object_id}")


def _routes_for(name: str) -> list[dict]:
    if not STAR_HOPS.exists():
        return []
    payload = json.loads(STAR_HOPS.read_text(encoding="utf-8"))
    return [route for route in payload.get("routes") or [] if route.get("target") == name]


def _constellation_name(abbreviation: str | None) -> str | None:
    """Return the reader-facing full constellation name from accepted figure data."""
    if not abbreviation or not FIGURE_SOURCE.exists():
        return abbreviation
    payload = json.loads(FIGURE_SOURCE.read_text(encoding="utf-8"))
    for figure_name, record in payload.items():
        if record.get("constellation") == abbreviation:
            return figure_name
    return abbreviation


def _figure_context(constellation: str | None) -> str | None:
    """Describe preserved finder geometry without inventing a named asterism."""
    if not constellation or not FIGURE_SOURCE.exists():
        return None
    payload = json.loads(FIGURE_SOURCE.read_text(encoding="utf-8"))
    for figure_name, record in payload.items():
        if record.get("constellation") != constellation:
            continue
        paths = record.get("figure_paths") or []
        if not paths:
            return None
        closed = [path for path in paths if len(path) >= 4 and path[0] == path[-1]]
        four_corner = any(len(set(path[:-1])) == 4 for path in closed)
        if four_corner:
            return (
                f"Trace {figure_name}’s diamond-shaped four-star figure first, then identify the target "
                "at its charted vertex before narrowing the field."
            )
        if closed:
            return (
                f"Trace the closed {figure_name} figure first, then identify the target at its charted "
                "vertex or along its charted segment before narrowing the field."
            )
        return (
            f"Trace the preserved {figure_name} stick figure from its brighter labeled stars, then "
            "identify the target on the corresponding charted segment."
        )
    return None


def baseline_story(fixed_object_id: int) -> Story:
    """Build a useful, non-repetitive baseline note from preserved object data."""
    meta = _fixed_object_meta(fixed_object_id)
    name = meta.get("name") or f"Fixed object {fixed_object_id}"
    family = meta.get("object_type_family") or "fixed-sky object"
    constellation = meta.get("constellation")
    constellation_name = _constellation_name(constellation)
    hed = name

    if name == "Pleiades":
        hed = "Pleiades — starlight reflected in passing dust"
        dek = "The star cluster’s blue wisps are dust reflecting its stars’ light, rather than glowing on their own."
        reason = (
            "The Pleiades are a naked-eye open cluster in Taurus. Their stars also illuminate "
            "interstellar dust, producing the blue reflection nebulosity prominent in photographs. "
            "This is scattered starlight: the dust redirects light toward us rather than generating "
            "its own visible glow.\n\n"
            "Around Merope, Hubble images show how the star’s radiation affects a passing cloud. "
            "Radiation pressure pushes smaller dust particles more strongly, helping sculpt the "
            "wispy structure. The attractive photographic haze therefore records an interaction "
            "between starlight and material in the space between stars.\n\n"
            "Binoculars show the cluster’s stars over a generous field; the faint dust is a much "
            "harder visual target than those bright points.\n\n"
            "Sources: NASA/Hubble, Ghostly Reflections in the Pleiades and Reflecting Merope."
        )
    elif name == "Nunki":
        # Nunki is a deliberately rich evergreen story.  Readers return to
        # these entries year after year, so Wordy mode should reward them with
        # real astronomy rather than Calendar boilerplate.  The dek doubles as
        # the Highlights hook.
        hed = "Nunki — the Teapot’s hidden pair"
        dek = (
            "The bright guide on Sagittarius’s Teapot handle is two hot stars in a close orbit, "
            "with a name inherited through a historical mix-up."
        )
        reason = (
            "Nunki, Sigma Sagittarii (σ Sgr), looks like a single bright point on the handle of "
            "Sagittarius’s Teapot. Its visual magnitude is about 2.1. That familiar point has two "
            "stories behind it: modern observations have uncovered a close stellar pair, while "
            "scholars have untangled a mistaken identification behind its ancient-sounding name.\n\n"
            "The blue-white light belongs to hot B-type stars. Sigma Sagittarii has long served "
            "as a standard for the B2.5 V spectral class: B describes the hot stellar spectrum, "
            "2.5 refines that classification, and V is the main-sequence luminosity class. "
            "Main-sequence stars generate their central energy by fusing hydrogen. The 2026 "
            "spectral analysis estimates an effective temperature around 18,500 kelvin, more "
            "than three times the Sun’s surface temperature. That heat gives the pair its "
            "blue-white appearance.\n\n"
            "A 2025 study by Idel Waisberg, Ygal Klein and Boaz Katz resolved Nunki with the "
            "Very Large Telescope Interferometer’s GRAVITY instrument. The companion supplied "
            "nearly 88 percent as much K-band infrared light as the brighter component. The "
            "authors estimated masses of about 6.5 and 6.3 Suns and an age around 30 million years. "
            "Their measured angular separation was only about 8.6 milliarcseconds — 0.0086 of "
            "an arcsecond — corresponding to a projected separation of roughly 0.60 astronomical "
            "unit at that observation. This was a snapshot of the apparent spacing, not a complete "
            "measurement of the orbit. An astronomical unit is the Earth–Sun distance.\n\n"
            "In March 2026, Waisberg and Katz combined observations from several epochs to solve "
            "that orbit. They found a period of 134.779 days, a relative orbital semimajor axis "
            "of about 1.26 astronomical units, and eccentricity about 0.49: the spacing varies "
            "substantially around an elongated orbit. At roughly 69 parsecs, or 225 light-years, "
            "the pair remains unresolved in an ordinary backyard view. The authors also explain "
            "how rapid rotation broadens the two stars’ spectral lines, helping a similar pair "
            "hide in what looks like a single stellar spectrum.\n\n"
            "The close orbit matters for their eventual evolution. As a component expands, "
            "the system may exchange material and possibly merge into a more massive star. "
            "The 2026 authors therefore describe Nunki as a candidate for the nearest future "
            "core-collapse supernova progenitor. That is a proposed evolutionary outcome, "
            "not a prediction of an imminent explosion or a guaranteed fate.\n\n"
            "The name has an equally surprising double identity. The IAU Working Group on "
            "Star Names’ etymology researchers trace Nunki to the Sumerian term for a celestial "
            "object associated with Eridu, an ancient Mesopotamian city. But they conclude "
            "that its modern attachment to Sigma Sagittarii arose from a nineteenth-century "
            "misreading of cuneiform material. Modern scholarship places the ancient designation "
            "in a different southern sky region, associated with the old Argo constellation, "
            "rather than Sagittarius. The name has ancient roots; its assignment to this "
            "particular star is a later historical transfer.\n\n"
            "For finding your way, start with the whole Teapot — spout, body, lid and handle — "
            "then match Nunki to its plotted place on the handle. The Teapot is an asterism "
            "within Sagittarius, so its recognizable outline is useful even when the larger "
            "Archer figure is less obvious. Kaus Australis provides another conspicuous point "
            "in the pattern. Confirm the arrangement of several stars before beginning a hop; "
            "brightness alone can lead you to the wrong starting point.\n\n"
            "The chart’s bright point is the pair’s combined light, not two visually separable "
            "stars. A nearby planet is a temporary visitor: use the current week’s position "
            "for the final hop. Visibility still depends on daylight and the horizon; being "
            "a bright guide does not make Nunki observable at every season or hour.\n\n"
            "Sources: Waisberg, Klein & Katz (2025), Research Notes of the AAS 9, 71, "
            "doi:10.3847/2515-5172/adc739; Waisberg & Katz (2026), arXiv:2603.17011; "
            "The IACOB project XII, doi:10.1051/0004-6361/202449298; "
            "IAU-WGSN Etymology Group, All Skies Encyclopaedia, Nunki "
            "(ase.exopla.net/index.php/Nunki)."
        )
    elif family == "star":
        where = f" in {constellation_name}" if constellation_name else ""
        dek = f"{name} is a stellar reference{where} used by the weekly observing calendar."
        reason = (
            f"Why it is here: The Calendar selected {name} for this week’s fixed-sky observing sequence; "
            "its permanent object identity ties the weekly entry to the same star used by the finder."
        )
    else:
        where = f" in {constellation_name}" if constellation_name else ""
        dek = f"{name} is an observing target{where} carried by the weekly Calendar."
        reason = (
            f"Why it is here: The Calendar selected {name} as one of this week’s fixed-sky observing targets."
        )

    routes = _routes_for(name)
    route_texts = [
        str(route.get("instruction") or "").strip()
        for route in routes if str(route.get("instruction") or "").strip()
    ]
    if name == "Pleiades":
        context = (
            "Find Orion’s three Belt stars, follow their line toward orange Aldebaran and the Hyades / V of Taurus, "
            "then continue in the same general direction to the compact Pleiades cluster."
        )
    elif name == "Nunki":
        context = (
            "Identify Sagittarius’s Teapot, then locate Nunki on its handle using the finder’s "
            "labeled stars. Match the whole pattern before following the current chart to a nearby target."
        )
    elif route_texts:
        context = " ".join(route_texts)
    else:
        context = _figure_context(constellation)
        if context is None and constellation:
            context = (
                f"Establish the preserved {constellation} constellation figure from its labeled reference "
                "stars, then use the target’s plotted position rather than searching for an isolated star."
            )
        elif context is None:
            context = (
                "Establish the surrounding charted stars first, then use the target’s plotted position "
                "before increasing magnification."
            )

    body = f"{reason}\n\nHow to find it: {context}"
    return Story(
        "baseline", fixed_object_id, FIXED_OBJECT_DATABASE, hed, dek, body,
        url_override=f"/stories/baseline/{fixed_object_id}.html"
    )

def write_public_story(story: Story) -> Path:
    """Materialize the human-readable HTML representation for any story."""
    path = STORIES_ROOT / story.collection / f"{story.fixed_object_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    paragraphs = "\n".join(
        f"<p>{html.escape(' '.join(part.splitlines()))}</p>"
        for part in re.split(r"\n\s*\n", story.body.strip()) if part.strip()
    )
    artwork_path = ROOT / "sky-notes-artwork" / "objects" / str(story.fixed_object_id) / "finder.svg"
    artwork_version = str(artwork_path.stat().st_mtime_ns) if artwork_path.exists() else None
    artwork_url = (
        f"../../sky-notes-artwork/objects/{story.fixed_object_id}/finder.svg?v={artwork_version}"
        if artwork_version is not None else None
    )
    document = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
        f"<title>{html.escape(story.hed)} — Star Almanack Sky Notes</title>\n</head>\n"
        f"<body>\n<main class=\"sky-note-story-page\" data-fixed-object-id=\"{story.fixed_object_id}\">\n"
        f"<h1 data-story-field=\"hed\">{html.escape(story.hed)}</h1>\n"
        f"<p class=\"sky-note-story-dek story-dek\" data-story-field=\"dek\">{html.escape(story.dek)}</p>\n"
        f"<section class=\"sky-note-story-body\" data-story-field=\"body\">{paragraphs}</section>\n"
        + (f"<figure class=\"sky-note-story-artwork\" data-story-field=\"artwork\">"
           f"<a href=\"{artwork_url}\">"
           f"<img src=\"{artwork_url}\" "
           f"alt=\"Stellar finder for {html.escape(story.hed, quote=True)}\" loading=\"lazy\"></a></figure>\n"
           if artwork_url is not None else "")
        + f"<p class=\"sky-note-story-descriptor\" data-story-field=\"descriptor\">"
        f"<a class=\"descriptor-link\" data-descriptor-id=\"{story.fixed_object_id}\" "
        f"href=\"../../almanack/descriptors/{story.fixed_object_id}.json\" type=\"application/json\">Descriptor</a></p>\n"
        "</main>\n</body>\n</html>\n"
    )
    if not path.exists() or path.read_text(encoding="utf-8") != document:
        path.write_text(document, encoding="utf-8")
    return path


def available_stories(fixed_object_id: int) -> list[Story]:
    """Return curated stories when present; use the machine-derived baseline only as fallback."""
    stories = []
    for collection in sorted(COLLECTIONS):
        story = read_story(collection, fixed_object_id)
        if story is not None:
            stories.append(story)
    if stories:
        for story in stories:
            write_public_story(story)
        return stories
    baseline = baseline_story(fixed_object_id)
    write_public_story(baseline)
    return [baseline]
