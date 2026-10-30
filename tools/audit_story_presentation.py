#!/usr/bin/env python3
"""Read-only checks for dangling citations and exposed dek Markdown."""
import json
import re
from clean_story_sources import manuscripts, ROOT

DANGLING = re.compile(r'\b(?:according to|(?:reported|listed|recorded|provided) (?:by|in)|taken from|drawn from)\s*[.,;:]', re.I)


def main():
    paths = list(manuscripts())
    issues = []
    for path in paths:
        text = path.read_text(encoding='utf-8')
        if path.suffix == '.json':
            payload = json.loads(text)
            text = '\n'.join(payload.get(k, '') for k in ('hed', 'dek', 'body'))
        for match in DANGLING.finditer(text):
            issues.append({'path': str(path.relative_to(ROOT)), 'issue': match.group()})
    pages = list((ROOT / 'stories').rglob('*.html'))
    for path in pages:
        text = path.read_text(encoding='utf-8')
        for match in DANGLING.finditer(text):
            issues.append({'path': str(path.relative_to(ROOT)), 'issue': match.group()})
        for dek in re.findall(r'<p[^>]*data-story-field="dek"[^>]*>(.*?)</p>', text, re.S):
            if re.search(r'\*[^*]+\*', dek):
                issues.append({'path': str(path.relative_to(ROOT)), 'issue': 'unrendered dek emphasis'})
    print(json.dumps({'manuscripts_checked': len(paths), 'reader_pages_checked': len(pages), 'issues': issues}, indent=2))
    return bool(issues)


if __name__ == '__main__':
    raise SystemExit(main())
