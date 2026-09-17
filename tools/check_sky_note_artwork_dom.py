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

    def handle_endtag(self, tag: str) -> None:
        if tag == "figure" and self.figure_depth:
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

    print(f"{args.week}: Chromium rendered artwork from {matches[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
