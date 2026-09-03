#!/usr/bin/env python3
"""Reject broken or stale Star Almanack pages in the Jekyll output."""

from pathlib import Path
import re


ALMANACK_ROOT = Path("_site/almanack")
ROOT = ALMANACK_ROOT / "2026"
DAY_ONE_NAME = re.compile(
    r'class="zodiac-glyph">[^<]+</span>\s+\([A-Za-z]+\)\s+1</td>'
)
INGRESS = re.compile(r"[A-Za-z]+ ingress \(")
WRAPPED_INGRESS = re.compile(
    r'<span class="zodiac-glyph">.*?</span>\s+[A-Za-z]+ ingress \('
)
CSS_REQUIREMENTS = {
    "Apple Symbols font": re.compile(r"font-family\s*:\s*['\"]Apple Symbols['\"]"),
    "text emoji variant": re.compile(r"font-variant-emoji\s*:\s*text"),
    "current-color WebKit fill": re.compile(r"-webkit-text-fill-color\s*:\s*currentColor"),
}


def main() -> None:
    index = ROOT / "index.html"
    pages = [ROOT / f"W{week:02d}" / "index.html" for week in range(1, 54)]
    missing = [str(path) for path in [index, *pages] if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing rendered Almanack pages: {missing}")

    legacy_files = sorted(ALMANACK_ROOT.glob("ISO2026-W*.html"))
    legacy_tree = ALMANACK_ROOT / "weeks"
    if legacy_files or legacy_tree.exists():
        raise SystemExit(
            "Legacy Almanack weekly output survived Jekyll build: "
            f"files={legacy_files}, weeks_tree={legacy_tree.exists()}"
        )

    rendered = "\n".join(path.read_text(encoding="utf-8") for path in pages)

    if DAY_ONE_NAME.search(rendered):
        raise SystemExit("A zodiac day-1 cell still contains a redundant sign name")

    if "Best visibility:" in rendered:
        raise SystemExit("Rendered Almanack still contains obsolete 'Best visibility:' labels")

    ingress_count = len(INGRESS.findall(rendered))
    wrapped_ingress_count = len(WRAPPED_INGRESS.findall(rendered))
    if ingress_count == 0 or wrapped_ingress_count != ingress_count:
        raise SystemExit(
            "Every ingress glyph must use the monochrome zodiac-glyph wrapper "
            f"({wrapped_ingress_count}/{ingress_count} wrapped)"
        )

    missing_css = [name for name, pattern in CSS_REQUIREMENTS.items() if not pattern.search(rendered)]
    if missing_css:
        raise SystemExit(f"Missing monochrome zodiac CSS semantics: {missing_css}")

    print("PASS: Jekyll rendered the canonical 2026 index and all 53 weekly pages")
    print("PASS: no legacy ISO2026-Wxx or almanack/weeks output remains")
    print("PASS: zodiac day 1 contains no redundant sign name")
    print("PASS: obsolete Best visibility labels are absent")
    print(f"PASS: all {ingress_count} ingress glyphs are monochrome text symbols")


if __name__ == "__main__":
    main()
