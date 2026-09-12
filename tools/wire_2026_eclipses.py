#!/usr/bin/env python3
"""Wire independently calculated eclipse data into Almanack year pages."""
from __future__ import annotations
import html,re,sys
from datetime import date
from pathlib import Path
from almanack_calendar import ensure_calendar_metadata,get_events,set_events
ROOT=Path(__file__).resolve().parents[1]; DEFAULT_ECLIPSE_SOURCE=ROOT/"Star-Almanack-Repo"/"eclipse.yaml"; ALMANACK_SOURCE=ROOT/"Star-Almanack-Repo"/"almanack-expanded.md"; ECLIPSE_PAGE=ROOT/"star-almanack"/"eclipses.html"
GLYPHS={"solar":'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/solar-eclipse.svg" alt="Solar eclipse" aria-label="Solar eclipse">',"lunar":'<img class="visibility-glyph" src="/assets/almanack/visibility-glyphs/masters/lunar-eclipse.svg" alt="Lunar eclipse" aria-label="Lunar eclipse">'}
def parse_year(text):
 m=re.search(r"(?m)^year:\s*(\d{4})\s*$",text)
 if not m:raise SystemExit("Eclipse source is missing a top-level year: value")
 return int(m.group(1))
def parse_eclipses(text,year):
 out=[]
 for block in re.split(r"(?m)^  - id: ",text)[1:]:
  def required(key):
   m=re.search(rf"(?m)^    {re.escape(key)}: ?\"?([^\"\n]+)\"?$",block)
   if not m:raise SystemExit(f"Eclipse entry is missing {key}")
   return m.group(1).strip()
  def optional(key):
   m=re.search(rf"(?m)^    {re.escape(key)}: ?\"?([^\"\n]+)\"?$",block); return m.group(1).strip() if m else ""
  kind=required("kind"); typ=required("type"); day=required("date"); maximum=required("maximum_geometry_utc")
  if date.fromisoformat(day).year!=year:raise SystemExit(f"Eclipse {day} does not belong to declared year {year}")
  out.append({"kind":kind,"type":typ,"date":day,"maximum":maximum,"magnitude":optional("magnitude"),"visibility":optional("visibility"),"observing_note":optional("observing_note")})
 if not out:raise SystemExit(f"No eclipses found for {year}")
 return out
def details(e):
 parts=[f"greatest eclipse {e['maximum'][:5]} UTC"]
 if e.get("magnitude"):parts.append(f"magnitude {e['magnitude']}")
 if e.get("visibility"):parts.append(f"visibility: {e['visibility']}")
 if e.get("observing_note"):parts.append(f"observing: {e['observing_note']}")
 return parts
def label(e,html_output=True):
 glyph=GLYPHS[e["kind"]] if html_output else ("☀" if e["kind"]=="solar" else "☾"); return f"{glyph} {e['type'].title()} {e['kind']} eclipse · {' · '.join(details(e))}"
def update_markdown(text,e):
 d=date.fromisoformat(e["date"]); iso_year,week,weekday=d.isocalendar(); heading=f"## ISO {iso_year}-W{week:02d}"; start=text.find(heading)
 if start<0:raise SystemExit(f"ISO week section not found for {e['date']}")
 next_start=text.find("\n## ISO ",start+len(heading)); end=len(text) if next_start<0 else next_start; section=text[start:end]
 row_matches=[m for m in re.finditer(r"(?m)^\| ([^|\n]+) \| ([^|\n]+) \| ([^|\n]*) \|$",section) if m.group(1).strip()!="Date" and not set(m.group(1).strip())<={"-",":"}]
 if len(row_matches)<7:raise SystemExit(f"Expected 7 calendar rows in {heading}, found {len(row_matches)}")
 m=row_matches[weekday-1]; existing=m.group(3).strip(); parts=[] if existing in ("","—") else [p for p in existing.split("<br>") if " eclipse " not in p]; new="<br>".join([label(e,False)]+parts); replacement=f"| {m.group(1)} | {m.group(2)} | {new} |"; section=section[:m.start()]+replacement+section[m.end():]; return text[:start]+section+text[end:]
def update_html(text,e,page):
 d=date.fromisoformat(e["date"]); text=ensure_calendar_metadata(text,page); existing=get_events(text,d)
 if existing is None:raise SystemExit(f"Canonical HTML calendar row not found for {e['date']} in {page}")
 parts=[] if existing.strip() in ("","—") else [p for p in existing.split("<br>") if " eclipse " not in p]; new="<br>".join([label(e,True)]+parts); text,found=set_events(text,d,new)
 if not found:raise SystemExit(f"Could not update eclipse row for {e['date']} in {page}")
 return text
def page_table(eclipses):
 rows=[]
 for e in eclipses:
  d=date.fromisoformat(e["date"]); visibility=html.escape(e.get("visibility", "")) or "—"; magnitude=html.escape(e.get("magnitude", "")) or "—"; observing=html.escape(e.get("observing_note", "")) or "—"; rows.append(f"<tr><td>{d.strftime('%B')} {d.day}, {d.year}</td><td>{e['type'].title()} {e['kind']}</td><td>{e['maximum'][:5]} UTC</td><td>{magnitude}</td><td>{visibility}</td><td>{observing}</td></tr>")
 return "<table><thead><tr><th>Date</th><th>Eclipse</th><th>Greatest eclipse</th><th>Magnitude</th><th>Visibility</th><th>Observing note</th></tr></thead><tbody>"+"".join(rows)+"</tbody></table>"
def update_eclipse_page(text,year,eclipses):
 table=page_table(eclipses); start=f"      <h2>{year} eclipses</h2>"; block=start+"\n      "+table
 if start in text:return re.sub(rf"      <h2>{year} eclipses</h2>.*?(?=\n\s*<h2>|\n\s*</section>)",block,text,count=1,flags=re.S)
 for h in re.finditer(r"      <h2>(\d{4}) eclipses</h2>",text):
  if int(h.group(1))>year:return text[:h.start()]+block+"\n\n"+text[h.start():]
 marker="      <h2>Publication and research remain separate</h2>"
 if marker not in text:raise SystemExit("Expected eclipse-page insertion marker not found")
 return text.replace(marker,block+"\n\n"+marker,1)
def publish(source_path):
 source_text=source_path.read_text(encoding="utf-8"); year=parse_year(source_text); eclipses=parse_eclipses(source_text,year)
 if year==2026:
  source=ALMANACK_SOURCE.read_text(encoding="utf-8")
  for e in eclipses:source=update_markdown(source,e)
  ALMANACK_SOURCE.write_text(source,encoding="utf-8")
 for e in eclipses:
  iso_year,week,_=date.fromisoformat(e["date"]).isocalendar()
  for root in (ROOT/"Star-Almanack-Repo"/"site"/str(iso_year),ROOT/"almanack"/str(iso_year)):
   page=root/f"W{week:02d}"/"index.html"
   if not page.exists():raise SystemExit(f"Missing Almanack week page: {page}")
   page.write_text(update_html(page.read_text(encoding="utf-8"),e,page),encoding="utf-8")
 page_text=ECLIPSE_PAGE.read_text(encoding="utf-8"); ECLIPSE_PAGE.write_text(update_eclipse_page(page_text,year,eclipses),encoding="utf-8"); print(f"{year}: wired {len(eclipses)} eclipses with magnitude, visibility, and observing details; PASS"); return year,len(eclipses)
def main():
 paths=[Path(x) for x in sys.argv[1:]] or [DEFAULT_ECLIPSE_SOURCE]; total=0; years=[]
 for path in paths:
  year,count=publish(path); years.append(str(year)); total+=count
 print(f"Eclipse publication parameterized for {', '.join(years)}; {total} event(s) total")
if __name__=="__main__":main()
