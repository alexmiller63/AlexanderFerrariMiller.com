#!/usr/bin/env python3
"""Reject broken or stale Star Almanack pages in the Jekyll output."""

from pathlib import Path
import re


ROOT = Path("_site/almanack/2026")
DAY_ONE_NAME = re.compile(
    r'class="zodiac-glyph">[^<]+</span>\s+\([A-Za-z]+\)\s+1</td>'
)
INGRESS = re.compile(r"[A-Za-z]+ ingress \(")
WRAPPED_INGRESS = re.compile(
    r'<span class="zodiac-glyph">.*?</span>\s+[A-Za-z]+ ingress \('
)


def main() -> None:
    index = ROOT / "index.html"
    pages = [ROOT / f"W{week:02d}" / "index.html" for week in range(1, 54)]
    missing = [str(path) for path in [index, *pages] if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing rendered Almanack pages: {missing}")

    rendered = "\n".join(path.read_text(encoding="utf-8") for path in pages)

    if DAY_ONE_NAME.search(rendered):
        raise SystemExit("A zodiac day-1 cell still contains a redundant sign name")

    ingress_count = len(INGRESS.findall(rendered))
    wrapped_ingress_count = len(WRAPPED_INGRESS.findall(rendered))
    if ingress_count == 0 or wrapped_ingress_count != ingress_count:
        raise SystemExit(
            "Every ingress glyph must use the monochrome zodiac-glyph wrapper "
            f"({wrapped_ingress_count}/{ingress_count} wrapped)"
        )

    required_css = (
        "font-family: 'Apple Symbols'",
        "font-variant-emoji: text",
        "-webkit-text-fill-color: currentColor",
    )
    missing_css = [rule for rule in required_css if rule not in rendered]
    if missing_css:
        raise SystemExit(f"Missing monochrome zodiac CSS: {missing_css}")

    print("PASS: Jekyll rendered the 2026 index and all 53 weekly pages")
    print("PASS: zodiac day 1 contains no redundant sign name")
    print(f"PASS: all {ingress_count} ingress glyphs are monochrome text symbols")


if __name__ == "__main__":
    main()
