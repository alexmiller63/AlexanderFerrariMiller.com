#!/usr/bin/env python3
"""Evergreen fixed-object story lookup for Star Almanack.

Story source is deliberately separate from database facts.  A story lives at
stories/{collection}/{fixed_object_id}.md.  The Markdown H1 is the hed, the
first paragraph after the H1 is the dek, and the remaining Markdown is body.

Consumers pass a collection and permanent fixed_object_id.  No object name is
used as an inter-layer key.
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


@dataclass(frozen=True)
class Story:
    collection: str
    fixed_object_id: int
    path: Path
    hed: str
    dek: str
    body: str

    @property
    def public_url(self) -> str:
        return f"/stories/{self.collection}/{self.fixed_object_id}.html"


def story_path(collection: str, fixed_object_id: int) -> Path:
    if collection not in COLLECTIONS:
        raise ValueError(f"Unknown story collection: {collection}")
    if not isinstance(fixed_object_id, int) or fixed_object_id <= 0:
        raise ValueError(f"Invalid fixed_object_id: {fixed_object_id!r}")
    return STORIES_ROOT / collection / f"{fixed_object_id}.md"


def read_story(collection: str, fixed_object_id: int) -> Story | None:
    path = story_path(collection, fixed_object_id)
    if not path.exists():
        return None

    text = path.read_text(encoding="utf-8").strip()
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

    return Story(
        collection=collection,
        fixed_object_id=fixed_object_id,
        path=path,
        hed=hed,
        dek=dek,
        body=body,
    )


def available_stories(fixed_object_id: int) -> list[Story]:
    stories = []
    for collection in sorted(COLLECTIONS):
        story = read_story(collection, fixed_object_id)
        if story is not None:
            stories.append(story)
    return stories
