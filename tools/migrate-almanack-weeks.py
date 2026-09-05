#!/usr/bin/env python3
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
WEEKS = ROOT / "almanack" / "2026"

MAIN_OPEN = '<main class="wrap">'
NAV_RE = re.compile(r'<nav class="weeknav"[^>]*>.*?</nav>', re.S)


def migrate(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        return False

    m = re.fullmatch(r"W(\d{2})", path.parent.name)
    if not m:
        return False
    week = int(m.group(1))

    start = text.find(MAIN_OPEN)
    if start < 0:
        raise RuntimeError(f"{path}: missing main wrapper")
    main = text[start + len(MAIN_OPEN):]

    # The old generated page has one nav at the top and one at the bottom.
    navs = list(NAV_RE.finditer(main))
    if len(navs) < 2:
        raise RuntimeError(f"{path}: expected two week navs, found {len(navs)}")

    body = main[navs[0].end():navs[-1].start()].strip()

    # Guard against accidentally carrying shared shell material into the content unit.
    forbidden = ["<!doctype", "<html", "<head", "<style", "bayer-toggle-wrap", "notation-legend", "<footer", "<script"]
    for token in forbidden:
        if token in body:
            raise RuntimeError(f"{path}: shared-shell token survived extraction: {token}")

    prev_lines = []
    if week > 1:
        prev_lines = [
            f"previous_week: /almanack/2026/W{week-1:02d}/",
            f"previous_label: W{week-1:02d}",
        ]
    next_lines = []
    if week < 53:
        next_lines = [
            f"next_week: /almanack/2026/W{week+1:02d}/",
            f"next_label: W{week+1:02d}",
        ]

    front = [
        "---",
        "layout: almanack-week",
        f"title: ISO 2026-W{week:02d}",
        f"iso_week: ISO 2026-W{week:02d}",
        *prev_lines,
        *next_lines,
        "---",
    ]

    output = "\n".join(front) + "\n" + body + "\n"
    path.write_text(output, encoding="utf-8")
    return True


def main() -> None:
    changed = []
    for week in range(1, 54):
        path = WEEKS / f"W{week:02d}" / "index.html"
        if not path.exists():
            raise RuntimeError(f"missing {path}")
        if migrate(path):
            changed.append(path.relative_to(ROOT).as_posix())

    print(f"Migrated {len(changed)} week pages")
    for path in changed:
        print(path)


if __name__ == "__main__":
    main()
