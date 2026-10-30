#!/usr/bin/env python3
"""Refresh existing Sky Notes headlines and deks from their linked reader pages."""
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'<a\b[^>]*href="[^"<>]*stories/(?P<collection>[a-z-]+)/(?P<id>\d+)\.html"[^>]*>(?P<body>.*?)</a>', re.S)


@lru_cache(maxsize=None)
def fields(collection, object_id):
    path = ROOT / "stories" / collection / f"{object_id}.html"
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    hed = re.search(r'<h1\b[^>]*data-story-field="hed"[^>]*>(.*?)</h1>', text, re.S)
    dek = re.search(r'<p\b[^>]*data-story-field="dek"[^>]*>(.*?)</p>', text, re.S)
    return (hed[1], dek[1]) if hed and dek else None


def refresh(text):
    def replace(match):
        body = match["body"]
        if 'class="sky-note-story-hed"' not in body:
            return match[0]
        current = fields(match["collection"], match["id"])
        if current is None:
            return match[0]
        for tag, field, value in (("strong", "hed", current[0]), ("span", "dek", current[1])):
            body = re.sub(r'(<'+tag+r' class="sky-note-story-'+field+r'">).*?(</'+tag+r'>)',
                          lambda m: m[1] + value + m[2], body, flags=re.S)
        return match[0][:match.start("body")-match.start()] + body + "</a>"
    return LINK.sub(replace, text)


def main():
    count = 0
    for path in sorted((ROOT / "almanack").rglob("*.html")):
        text = path.read_text(encoding="utf-8")
        updated = refresh(text)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            count += 1
    print(f"Refreshed story references on {count} pages")


if __name__ == "__main__":
    main()
