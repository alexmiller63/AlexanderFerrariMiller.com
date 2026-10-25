#!/usr/bin/env python3
"""Publish cached meteor results without rerunning the astronomy or Build All."""
import argparse
import json
import re
from datetime import date
from pathlib import Path

from almanack_calendar import CalendarEvent, ensure_calendar_metadata, get_event_records, set_events
from meteor_editorial import ROOT, event_id, href, load_events, render_card, render_index, week_notes

START = '<!-- METEOR-NOTES START -->'
END = '<!-- METEOR-NOTES END -->'


def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8') != content:
        path.write_text(content, encoding='utf-8')


def notes_block(path, highlights=False, root=ROOT):
    return START + week_notes(path, highlights, root) + END


def publish_year(year, root=ROOT, require_notes=True):
    events = load_events(root, [year])
    weeks = {}
    for event in events:
        target = root / 'almanack' / 'meteors'
        write(target / f'{event_id(event)}.html', render_card(event))
        write(target / f'{event_id(event)}.json', json.dumps(event, indent=2, ensure_ascii=False) + '\n')
        day = date.fromisoformat(event['utc'][:10])
        y, w, _ = day.isocalendar()
        weeks.setdefault((y, w), []).append((day, event))
    for (y, w), weekly in weeks.items():
        path = root / 'almanack' / str(y) / f'W{w:02d}' / 'index.html'
        if not path.exists():
            raise FileNotFoundError(f'Missing meteor week: {path}')
        content = ensure_calendar_metadata(path.read_text(encoding='utf-8'), path)
        for day in sorted({d for d, _ in weekly}):
            todays = [e for d, e in weekly if d == day]
            records = get_event_records(content, day)
            if records is None:
                raise ValueError(f'Missing calendar row: {day} in {path}')
            names = [e['name'] for e in todays]
            keep = [r for r in records if 'data-meteor-id=' not in r.html and
                    not any(name in r.html and 'peak' in r.html for name in names)]
            additions = [CalendarEvent(
                f'<span data-meteor-id="{event_id(e)}"><a href="{href(e)}">{e["calendar_label"]}</a>'
                f' · nominal peak {e["utc"][11:19]} UTC</span>') for e in todays]
            content, found = set_events(content, day, additions + keep)
            if not found:
                raise ValueError(f'Cannot publish meteor calendar row: {day}')
        # Update only these owned blocks inside existing Sky Notes; retain all
        # stories, planets, eclipses, and the two-mode presentation.
        content = re.sub(re.escape(START) + r'.*?' + re.escape(END), '', content, flags=re.S)
        for mode in ('wordy', 'highlights'):
            pattern = r'(<div\b[^>]*class="sky-note-' + mode + r'"[^>]*>)'
            content, count = re.subn(pattern, lambda m: m[1] + notes_block(path, mode == 'highlights', root), content, count=1)
            if count != 1 and require_notes:
                raise ValueError(f'Missing Sky Notes {mode} in {path}')
        write(path, content)
    write(root / 'almanack/meteors/index.html', render_index(load_events(root)))
    print(f'{year}: published {len(events)} meteor cards and {len(weeks)} weekly pages')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('years', type=int, nargs='+')
    for year in dict.fromkeys(parser.parse_args().years):
        publish_year(year)


if __name__ == '__main__':
    main()
