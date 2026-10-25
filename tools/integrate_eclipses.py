#!/usr/bin/env python3
"""Idempotent provisional eclipse publication overlay; does not run Build All."""
import argparse, html, json, re
from datetime import date
from pathlib import Path
from eclipse_editorial import load_events, render_page
from eclipse_calendar import populate_eclipse_calendar
ROOT=Path(__file__).resolve().parents[1]
START='<!-- ECLIPSE-OVERLAY START -->'
END='<!-- ECLIPSE-OVERLAY END -->'
def write(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists() or path.read_text(encoding='utf-8')!=value:
        path.write_text(value,encoding='utf-8')
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',type=Path,required=True)
    a=p.parse_args()
    data=json.loads(a.catalog.read_text(encoding='utf-8'))
    rows=data['eclipses']
    if not rows: raise ValueError('Empty eclipse catalog')
    publication_events = load_events(ROOT)
    weeks={}
    for e in rows:
        day=date.fromisoformat(e['date_utc'])
        eid=e['id']
        if not re.fullmatch(r'ECL-\d{4}-\d{2}-\d{2}-[SL]',eid): raise ValueError('Unsafe eclipse ID: '+eid)
        title=f"{e['type'].title()} {e['kind'].title()} Eclipse"
        url=f"/almanack/eclipses/{eid}.html"
        detail=render_page({**e, **{key: value for key, value in publication_events.get(eid, {}).items() if key in ("magnitude", "visibility", "observing_note")}})
        write(ROOT/'almanack'/f'eclipses/{eid}.html',detail)
        if 2025<=day.year<=2027:
            y,w,_=day.isocalendar()
            weeks.setdefault((y,w),[]).append((day,title,url))
    for (y,w),events in weeks.items():
        page=ROOT/'almanack'/str(y)/f'W{w:02d}'/'index.html'
        if not page.exists():
            print('SKIP missing weekly page',page)
            continue
        content=page.read_text(encoding='utf-8')
        content=populate_eclipse_calendar(content, page, publication_events)
        links=''.join(f'<li><time datetime="{d}">{d}</time>: <a href="{u}">{html.escape(t)}</a> (provisional)</li>' for d,t,u in events)
        block=f'{START}<section id="eclipse-events" aria-label="Eclipses this week"><h2>Eclipses this week</h2><ul>{links}</ul></section>{END}'
        if START in content and END in content:
            content=re.sub(re.escape(START)+r'.*?'+re.escape(END),lambda _:block,content,flags=re.S)
        elif '</main>' in content:
            content=content.replace('</main>',block+'</main>',1)
        else:
            print('SKIP weekly page without main',page)
            continue
        write(page,content)
    cards=''.join(f'<li><a href="/almanack/eclipses/{e["id"]}.html">{html.escape(e["date_utc"])} — {html.escape(e["type"].title())} {html.escape(e["kind"].title())} Eclipse</a></li>' for e in rows)
    index='<!doctype html><html lang="en"><meta charset="utf-8"><title>Eclipses 2025–2036 — Star Almanack</title><main><h1>Eclipses 2025–2036</h1><p>Provisional calculations; times and geometry are not independently validated.</p><ul>'+cards+'</ul></main></html>'
    write(ROOT/'almanack/eclipses/index.html',index)
    print('Published',len(rows),'provisional eclipse pages; updated',len(weeks),'candidate weeks')
if __name__=='__main__':main()


