#!/usr/bin/env python3
"""Verify Calendar fixed-object identity and reader-facing Sky Note links."""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright


def weeks_between(start: str, end: str):
    d = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    out = []
    while d <= last:
        iso = d.isocalendar()
        pair = (iso.year, iso.week)
        if pair not in out:
            out.append(pair)
        d += dt.timedelta(days=1)
    return out


def verify_reader_links(page, rel: str):
    """Reader-facing Sky Note links must never expose descriptor JSON."""
    links = page.locator('.sky-note a')
    for index in range(links.count()):
        link = links.nth(index)
        href = link.get_attribute('href') or ''
        media_type = (link.get_attribute('type') or '').lower()
        if href.lower().split('?', 1)[0].endswith('.json') or media_type == 'application/json':
            text = link.inner_text().strip()
            raise SystemExit(
                f'Reader-facing Sky Note link exposes machine JSON in {rel}: '
                f'{text!r} -> {href!r}'
            )

    story_links = page.locator('.sky-note-story a[href]')
    checked = set()
    for index in range(story_links.count()):
        href = story_links.nth(index).get_attribute('href') or ''
        if not href or href.startswith('#') or href in checked:
            continue
        checked.add(href)
        target = urljoin(page.url, href)
        response = page.request.get(target, timeout=120000)
        if not response.ok:
            raise SystemExit(f'Sky Note story link failed in {rel}: {href} -> HTTP {response.status}')
        content_type = (response.headers.get('content-type') or '').lower()
        if 'text/html' not in content_type:
            raise SystemExit(
                f'Sky Note story link is not HTML in {rel}: {href} -> {content_type or "unknown content type"}'
            )
    print(f'Sky Note reader-link PASS: {rel} ({len(checked)} story destinations)')


def verify_page(page, rel: str):
    if page.locator('table.calendar').count() != 1:
        raise SystemExit(f'Calendar table missing in {rel}')
    events = page.locator('table.calendar .event-cell')
    if events.count() == 0:
        raise SystemExit(f'Calendar event cells missing in {rel}')

    fixed = page.locator('table.calendar .event-cell[data-fixed-object-id]')
    ids = fixed.evaluate_all("els => els.map(el => el.dataset.fixedObjectId)")
    bad = [value for value in ids if not value or not value.isdigit() or int(value) <= 0]
    if bad:
        raise SystemExit(f'Invalid data-fixed-object-id in {rel}: {bad[:5]}')
    if len(ids) != len(set(ids)):
        print(f'{rel}: {len(ids)} fixed-object references, {len(set(ids))} unique IDs')
    else:
        print(f'{rel}: {len(ids)} fixed-object references, all IDs valid')

    orphan_aids = page.locator(
        'table.calendar .event-cell:not([data-fixed-object-id]) '
        '.observing-aid-notation, '
        'table.calendar .event-cell:not([data-fixed-object-id]) '
        '.observing-notation-item'
    ).count()
    if orphan_aids:
        raise SystemExit(
            f'Observing-aid presentation without fixed-object ID in {rel}: {orphan_aids}'
        )

    toggle = '.section-notation-toggle[data-notation-target="calendar"]'
    for mode in ('greek', 'latin', 'mixed'):
        button = page.locator(f'{toggle} button[data-bayer-mode="{mode}"]')
        if button.count() != 1:
            raise SystemExit(f'Calendar notation button missing in {rel}: {mode}')
        before = fixed.evaluate_all("els => els.map(el => el.dataset.fixedObjectId)")
        button.click()
        page.wait_for_timeout(50)
        after = fixed.evaluate_all("els => els.map(el => el.dataset.fixedObjectId)")
        if before != after:
            raise SystemExit(f'Fixed-object IDs changed in {rel} after {mode} rendering')

        overflow = page.evaluate("""() => {
          const viewportRight = window.innerWidth + 1;
          const offenders = [...document.querySelectorAll('body *')]
            .filter(el => {
              const rect = el.getBoundingClientRect();
              return rect.right > viewportRight || rect.left < -1;
            })
            .slice(0, 8)
            .map(el => ({
              tag: el.tagName.toLowerCase(),
              id: el.id || '',
              class: typeof el.className === 'string' ? el.className : '',
              right: Math.round(el.getBoundingClientRect().right),
              scrollWidth: el.scrollWidth,
              clientWidth: el.clientWidth
            }));
          return {
          page: document.documentElement.scrollWidth > viewportRight,
          pageScrollWidth: document.documentElement.scrollWidth,
          viewportWidth: window.innerWidth,
          offenders,
          calendar: (() => {
            const el = document.querySelector('table.calendar');
            return !!el && el.scrollWidth > el.clientWidth + 1;
          })()
        }}""")
        if overflow['page']:
            raise SystemExit(
                f'Mobile Calendar layout failure in {rel} mode={mode}: {overflow}'
            )

    verify_reader_links(page, rel)
    print(f'Calendar fixed-object ID PASS all notation modes: {rel}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('start_date')
    parser.add_argument('end_date')
    parser.add_argument('--base-url')
    args = parser.parse_args()

    root = Path.cwd()
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 390, 'height': 844})
        for year, week in weeks_between(args.start_date, args.end_date):
            rel = f'almanack/{year}/W{week:02d}/index.html'
            if args.base_url:
                url = f"{args.base_url.rstrip('/')}/{rel}"
            else:
                path = (root / rel).resolve()
                if not path.exists():
                    raise SystemExit(f'Missing generated page: {rel}')
                url = path.as_uri()
            response = page.goto(url, wait_until='networkidle', timeout=120000)
            if args.base_url and (response is None or not response.ok):
                status = None if response is None else response.status
                raise SystemExit(f'Chromium failed to load {rel}: HTTP {status}')
            verify_page(page, rel)
        browser.close()


if __name__ == '__main__':
    main()
