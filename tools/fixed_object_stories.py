#!/usr/bin/env python3
"""Evergreen fixed-object story lookup for Star Almanack.

Story source is deliberately separate from database facts. A story lives at
stories/{collection}/{fixed_object_id}.md. Optional Jekyll front matter may
declare machine-readable story metadata. The Markdown H1 is the hed, the first
paragraph after the H1 is the dek, and the remaining Markdown is body.

Consumers pass a collection and permanent fixed_object_id. No object name is
used as an inter-layer key. Artwork is never inferred from story prose: a story
must explicitly declare `artwork: stellar-finder` in front matter to request it.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STORIES_ROOT = ROOT / "stories"

COLLECTIONS = {
    "alpha-stars",
    "beta-stars",
    "special-stars",
    "messier",
    "caldwell",
    "finest",
}
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

    @property
    def public_url(self) -> str:
        return f"/stories/{self.collection}/{self.fixed_object_id}.html"


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


def available_stories(fixed_object_id: int) -> list[Story]:
    stories = []
    for collection in sorted(COLLECTIONS):
        story = read_story(collection, fixed_object_id)
        if story is not None:
            stories.append(story)
    return stories
