#!/usr/bin/env python3
"""Apply or check evergreen citation presentation without changing review status.

Research snapshots, API responses and audit records are deliberately excluded.
"""
import argparse
import json
import re
from pathlib import Path
from story_editorial import clean_story, source_urls

ROOT = Path(__file__).resolve().parents[1]
COLLECTIONS = ('alpha-stars', 'beta-stars', 'special-stars', 'messier', 'caldwell', 'finest', 'constellations')


def manuscripts():
    for collection in COLLECTIONS:
        yield from (p for p in (ROOT / 'stories' / collection).glob('*.md') if p.name != 'README.md')
    yield from (ROOT / 'generated/luna-pilot').glob('*.md')
    yield from (p for p in (ROOT / 'generated/sky-notes-2026-drafts').glob('*.json') if p.stem.isdigit())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Report needed edits without writing')
    args = parser.parse_args()
    changed = []
    count = 0
    for path in manuscripts():
        old = path.read_text(encoding='utf-8')
        if path.suffix == '.json':
            payload = json.loads(old)
            before = payload['body']
            after = clean_story(before).strip()
            payload['body'] = after
            for key in ('hed', 'dek'):
                payload[key] = re.sub(r'\bSIMBAD\b', 'the catalogue', payload[key])
            new = json.dumps(payload, ensure_ascii=False, indent=2) + '\n'
        else:
            before = old
            after = clean_story(before)
            new = after
        if source_urls(before) - source_urls(after):
            raise RuntimeError(f'Source URL lost: {path}')
        numbers = lambda text: set(re.findall(r'(?<!\w)[−–+\-]?\d+(?:[.,]\d+)*', text))
        if numbers(before) - numbers(after):
            raise RuntimeError(f'Numeric value lost: {path}')
        if clean_story(after).strip() != after.strip():
            raise RuntimeError(f'Cleanup not stable: {path}')
        count += 1
        # Ignore whitespace-only differences in otherwise compliant sources.
        if re.sub(r'\s+', ' ', old).strip() == re.sub(r'\s+', ' ', new).strip():
            continue
        changed.append(str(path.relative_to(ROOT)))
        if not args.check:
            path.write_text(new, encoding='utf-8')
    print(json.dumps({'manuscripts_checked': count, 'edits_needed' if args.check else 'edited': len(changed), 'paths': changed}, indent=2))
    return int(args.check and bool(changed))


if __name__ == '__main__':
    raise SystemExit(main())
