#!/usr/bin/env python3
"""Read-only three-year weekly Sky Notes story-link coverage audit."""
import argparse
import csv
import json
import re
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
STORY = re.compile(r"(?:^|/)stories/([^/]+)/([^/]+)\.html$", re.I)

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)

def inspect(year, week, minimum):
    folder = ROOT / "almanack" / str(year) / f"W{week:02d}"
    page = folder / "index.html"
    if not page.exists():
        return dict(year=year, week=week, status="MISSING_PAGE", distinct_stories=0,
                    finished_links=0, draft_links=0, broken_links=0,
                    broken_targets="", draft_targets="", sky_notes_present=False,
                    issues="weekly page missing")
    source = page.read_text(encoding="utf-8")
    parser = Links()
    parser.feed(source)
    stories, drafts, broken = set(), set(), set()
    for href in parser.hrefs:
        url = urlsplit(href)
        if url.scheme or url.netloc or href.startswith("#"):
            continue
        target = unquote(url.path)
        match = STORY.search(target)
        if not match:
            continue
        resolved = (ROOT / target.lstrip("/")) if target.startswith("/") else (folder / target)
        resolved = resolved.resolve()
        # Do not follow links outside the repository.
        if not resolved.is_relative_to(ROOT):
            broken.add(href)
            continue
        stories.add(str(resolved.relative_to(ROOT)))
        if match.group(1).lower() in ("draft", "drafts"):
            drafts.add(str(resolved.relative_to(ROOT)))
        if not resolved.is_file():
            broken.add(href)
    # Check for Sky Notes as an identifiable section, not merely a navigation link.
    sky_notes_present = ("data-almanack-section-name=\"sky-notes\"" in source or bool(re.search(r"<h[1-6][^>]*>\\s*Sky Notes", source, re.I)))
    issues = []
    if len(stories) < minimum:
        issues.append("fewer than target story links")
    if drafts:
        issues.append("draft links")
    if broken:
        issues.append("missing story files")
    if not sky_notes_present:
        issues.append("Sky Notes section requires inspection")
    return dict(year=year, week=week, status="REVIEW" if issues else "STRUCTURAL_PASS",
                distinct_stories=len(stories), finished_links=len(stories - drafts),
                draft_links=len(drafts), broken_links=len(broken),
                broken_targets="; ".join(sorted(broken)),
                draft_targets="; ".join(sorted(drafts)),
                sky_notes_present=sky_notes_present, issues="; ".join(issues))

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minimum", type=int, default=5)
    p.add_argument("--output", default="generated/sky-notes-coverage-2025-2027.csv")
    args = p.parse_args()
    rows = [inspect(y, w, args.minimum) for y in (2025, 2026, 2027)
            for w in range(1, date(y, 12, 28).isocalendar().week + 1)]
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {"weeks": len(rows), "missing_pages": sum(r["status"] == "MISSING_PAGE" for r in rows),
               "below_target": sum(r["distinct_stories"] < args.minimum for r in rows),
               "weeks_with_drafts": sum(r["draft_links"] > 0 for r in rows),
               "weeks_with_broken_story_links": sum(r["broken_links"] > 0 for r in rows),
               "structural_pass": sum(r["status"] == "STRUCTURAL_PASS" for r in rows),
               "note": "Structural audit only: finished_links means non-draft paths, not editorial verification. Sky Notes depth and scientific accuracy require separate review."}
    summary_path = output.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print("Reports:", output, summary_path)

if __name__ == "__main__":
    main()
