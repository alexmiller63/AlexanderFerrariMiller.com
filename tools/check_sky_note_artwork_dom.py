#!/usr/bin/env python3
"""Validate that a rendered weekly page points at its expected Sky Note artwork."""

from __future__ import annotations

import argparse
from html.parser import HTMLParser
from pathlib import Path


class ArtworkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.figure_depth = 0
        self.artwork_srcs: list[str] = []
        self.artwork_hrefs: list[str] = []
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = set((values.get("class") or "").split())
        if tag == "figure":
            if self.figure_depth or "sky-note-artwork" in classes:
                self.figure_depth += 1
        elif tag == "img" and self.figure_depth:
            src = values.get("src")
            if src:
                self.artwork_srcs.append(src)
        elif tag == "a" and self.figure_depth:
            self._anchor_href = values.get("href")
            self._anchor_text = []

    def handle_data(self, data: str) -> None:
        if self._anchor_href is not None:
            self._anchor_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._anchor_href is not None:
            if "".join(self._anchor_text).strip() == "Artwork":
                self.artwork_hrefs.append(self._anchor_href)
            self._anchor_href = None
            self._anchor_text = []
        elif tag == "figure" and self.figure_depth:
            self.figure_depth -= 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("dom", type=Path)
    parser.add_argument("expected_svg")
    parser.add_argument("week")
    args = parser.parse_args()

    document = args.dom.read_text(encoding="utf-8")
    parsed = ArtworkParser()
    parsed.feed(document)

    if not parsed.artwork_srcs:
        raise SystemExit(f"{args.week}: Chromium rendered no artwork image")

    expected_suffix = "/" + args.expected_svg.lstrip("/")
    matches = [src for src in parsed.artwork_srcs if src.endswith(expected_suffix)]
    if not matches:
        raise SystemExit(
            f"{args.week}: rendered artwork sources {parsed.artwork_srcs!r} do not include *{expected_suffix!r}"
        )

    if not parsed.artwork_hrefs:
        raise SystemExit(f"{args.week}: Chromium rendered no Artwork link")
    bad_json = [href for href in parsed.artwork_hrefs if href.lower().split("?", 1)[0].endswith(".json")]
    if bad_json:
        raise SystemExit(f"{args.week}: Artwork link must not target JSON: {bad_json!r}")
    link_matches = [href for href in parsed.artwork_hrefs if href.endswith(expected_suffix)]
    if not link_matches:
        raise SystemExit(
            f"{args.week}: Artwork links {parsed.artwork_hrefs!r} do not include *{expected_suffix!r}"
        )

    print(f"{args.week}: Chromium rendered artwork from {matches[0]} with Artwork link {link_matches[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
