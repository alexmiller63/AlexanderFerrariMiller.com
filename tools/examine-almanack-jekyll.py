#!/usr/bin/env python3
"""Reject broken or stale Star Almanack pages in the Jekyll output."""

from argparse import ArgumentParser
from datetime import date
from pathlib import Path
import re

from almanack_paths import PAGE_TYPES, typed_page, year_dir

ALMANACK_ROOT = Path("_site/almanack")
DAY_ONE_NAME = re.compile(
    r'class="zodiac-glyph">[^<]+</span>\s+\([A-Za-z]+\)\s+1</td>'
)
# Canonical calendar wording is "<zodiac glyph> Sun enters Sign — ...".
# Count the semantic ingress phrase, then require the immediately preceding
# sign to use the monochrome zodiac-glyph wrapper. Accept an optional text
# variation selector because the generator/Jekyll serializer may omit it.
INGRESS = re.compile(
    r'<span class="zodiac-glyph">(?:♈|♉|♊|♋|♌|♍|♎|♏|♐|♑|♒|♓)(?:\ufe0e|&#xfe0e;)?</span>\s+'
    r'Sun enters\s+(?:Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)\b'
)
PLAIN_INGRESS = re.compile(
    r'Sun enters\s+(?:Aries|Taurus|Gemini|Cancer|Leo|Virgo|Libra|Scorpio|Sagittarius|Capricorn|Aquarius|Pisces)\b'
)
CSS_REQUIREMENTS = {
    "Apple Symbols font": re.compile(r"font-family\s*:\s*['\"]Apple Symbols['\"]"),
    "text emoji variant": re.compile(r"font-variant-emoji\s*:\s*text"),
    "current-color WebKit fill": re.compile(r"-webkit-text-fill-color\s*:\s*currentColor"),
}


def weeks_in_iso_year(year: int) -> int:
    return date(year, 12, 28).isocalendar().week


def main() -> None:
    parser = ArgumentParser()
    parser.add_argument("years", nargs="*", type=int, default=[2026])
    args = parser.parse_args()

    all_pages = []
    for year in args.years:
        root = ALMANACK_ROOT / year_dir(year).relative_to(year_dir(year).parent)
        index = root / "index.html"
        if not index.is_file():
            raise SystemExit(f"Missing rendered Almanack index for {year}: {index}")

        source_year = Path("almanack") / str(year)
        week_dirs = sorted(
            path for path in source_year.glob("W[0-9][0-9]")
            if path.is_dir()
            and any((path / content_type / "index.html").is_file()
                    for content_type in PAGE_TYPES if content_type != "artwork")
        )
        pages = [
            path / f"{content_type}/index.html"
            for path in week_dirs
            for content_type in PAGE_TYPES if content_type != "artwork"
        ]
        missing = [str(path) for path in pages if not path.is_file()]
        if missing:
            raise SystemExit(f"Missing rendered Almanack pages for published weeks in {year}: {missing}")
        all_pages.extend(pages)
        print(
            f"PASS: Jekyll rendered the canonical {year} index and "
            f"all {len(week_dirs)} published weeks × 4 typed pages"
        )

    legacy_files = sorted(ALMANACK_ROOT.glob("ISO*-W*.html"))
    legacy_tree = ALMANACK_ROOT / "weeks"
    if legacy_files or legacy_tree.exists():
        raise SystemExit(
            "Legacy Almanack weekly output survived Jekyll build: "
            f"files={legacy_files}, weeks_tree={legacy_tree.exists()}"
        )

    rendered = "\n".join(path.read_text(encoding="utf-8") for path in all_pages)

    if DAY_ONE_NAME.search(rendered):
        raise SystemExit("A zodiac day-1 cell still contains a redundant sign name")

    if "Best visibility:" in rendered:
        raise SystemExit("Rendered Almanack still contains obsolete 'Best visibility:' labels")

    ingress_count = len(PLAIN_INGRESS.findall(rendered))
    wrapped_ingress_count = len(INGRESS.findall(rendered))
    if ingress_count == 0 or wrapped_ingress_count != ingress_count:
        raise SystemExit(
            "Every ingress glyph must use the monochrome zodiac-glyph wrapper "
            f"({wrapped_ingress_count}/{ingress_count} wrapped)"
        )

    missing_css = [name for name, pattern in CSS_REQUIREMENTS.items() if not pattern.search(rendered)]
    if missing_css:
        raise SystemExit(f"Missing monochrome zodiac CSS semantics: {missing_css}")

    print("PASS: no legacy ISO-Wxx or almanack/weeks output remains")
    print("PASS: zodiac day 1 contains no redundant sign name")
    print("PASS: obsolete Best visibility labels are absent")
    print(f"PASS: all {ingress_count} ingress glyphs are monochrome text symbols")


if __name__ == "__main__":
    main()
