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

COLLECTIONS = {"alpha-stars", "beta-stars", "special-stars", "messier", "caldwell", "finest"}
ARTWORK_KINDS = {"stellar-finder"}


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


def baseline_story(fixed_object_id: int) -> Story:
    """Build the always-present baseline note for one permanent fixed-object ID."""
    meta = _fixed_object_meta(fixed_object_id)
    name = meta.get("name") or f"Fixed object {fixed_object_id}"
    family = meta.get("object_type_family") or "fixed-sky object"
    constellation = meta.get("constellation")
    if family == "star":
        location = f" in {constellation}" if constellation else ""
        reason = f"{name} is a charted star{location} selected by the Calendar as part of this week’s fixed-sky observing framework."
    else:
        reason = f"{name} is a charted deep-sky object selected by the Calendar as one of this week’s fixed-sky observing targets."
    routes = _routes_for(name)
    if routes:
        route_text = " ".join(route.get("instruction", "").strip() for route in routes if route.get("instruction"))
        body = f"Why it is here: {reason}\n\nHow to find it: {route_text}"
    else:
        context = f"Use its charted position in {constellation} and the surrounding figure stars to identify the field." if constellation else "Use the surrounding charted stars and finder geometry to identify the field before increasing magnification."
        body = f"Why it is here: {reason}\n\nHow to find it: {context}"
    return Story("baseline", fixed_object_id, FIXED_OBJECT_DATABASE, name, reason, body,
                 url_override=f"/stories/baseline/{fixed_object_id}.html")


def write_public_story(story: Story) -> Path:
    """Materialize the human-readable HTML representation for any story."""
    path = STORIES_ROOT / story.collection / f"{story.fixed_object_id}.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    paragraphs = "\n".join(
        f"<p>{html.escape(' '.join(part.splitlines()))}</p>"
        for part in re.split(r"\n\s*\n", story.body.strip()) if part.strip()
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
           f"<a href=\"../../sky-notes-artwork/objects/{story.fixed_object_id}/finder.svg\">"
           f"<img src=\"../../sky-notes-artwork/objects/{story.fixed_object_id}/finder.svg\" "
           f"alt=\"Stellar finder for {html.escape(story.hed, quote=True)}\" loading=\"lazy\"></a></figure>\n"
           if (ROOT / "sky-notes-artwork" / "objects" / str(story.fixed_object_id) / "finder.svg").exists() else "")
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
