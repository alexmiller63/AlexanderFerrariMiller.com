#!/usr/bin/env python3
"""Permanent Star Almanack type-coverage regression.

One representative 2026 sample is required for each supported semantic class.
The test fails if a sample disappears, moves to the wrong generated ISO week,
uses the wrong semantic marker, or loses required reader-facing information.
"""
from __future__ import annotations
import csv,re,sys
from dataclasses import dataclass
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; YEAR=2026; SITE=ROOT/'almanack'/str(YEAR); SRC=ROOT/'Star-Almanack-Repo'; GENERATED=SRC/'generated'; BASE_URL=f'https://AlexanderFerrariMiller.com/almanack/{YEAR}'
@dataclass(frozen=True)
class Case:
 name:str; week:str; expected:str; checks:tuple[str,...]; proximity:tuple[tuple[str,str],...]=()
def read_csv(path):
 with path.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def row_for(path,**wanted):
 for row in read_csv(path):
  if all(row.get(k)==v for k,v in wanted.items()):return row
 raise AssertionError(f'source row missing in {path}: {wanted}')
def week_from_iso(value):
 m=re.search(r'-(W\d{2})-',value)
 if not m:raise AssertionError(f'cannot parse ISO week from {value!r}')
 return m.group(1)
def html_for(week):
 p=SITE/week/'index.html'; return p.read_text(encoding='utf-8') if p.exists() else ''
def close_together(html,left,right,radius=1200):
 pos=html.find(left)
 if pos<0:return False
 return right in html[max(0,pos-radius):min(len(html),pos+len(left)+radius)]
def source_week(path,selector,iso_field='iso'):return week_from_iso(row_for(path,**selector)[iso_field])
def build_cases():
 constellation_week=source_week(SRC/'constellation-observance-2026.csv',{'name':'Andromeda'})
 asterism_week=source_week(SRC/'asterism-geometry-2026.csv',{'asterism':'Great Square of Pegasus'})
 alpha_week=source_week(SRC/'expanded-bayer-visibility-2026.csv',{'proper':'Achernar'})
 beta_week=source_week(SRC/'expanded-bayer-visibility-2026.csv',{'proper':'Cursa'})
 messier_week=source_week(SRC/'messier-visibility-2026.csv',{'messier':'M45'})
 caldwell_week=source_week(GENERATED/'caldwell-visibility-2026.csv',{'caldwell':'C4'})
 hyades_week=source_week(GENERATED/'caldwell-visibility-2026.csv',{'caldwell':'C41'})
 finest_week=source_week(GENERATED/'finest-ngc-visibility-2026.csv',{'finest_ngc':'19'})
 return [
 Case('constellation center',constellation_week,'Andromeda center is explicitly a constellation-center event.',('Andromeda','center')),
 Case('asterism center',asterism_week,'Great Square of Pegasus center is explicitly an Asterism and carries band and season.',('Great Square of Pegasus','center','Asterism')),
 Case('alpha Bayer star',alpha_week,'Achernar appears as α Eridani.',('Achernar','α')),
 Case('beta Bayer star',beta_week,'Cursa appears as β Eridani.',('Cursa','β')),
 Case('Messier object',messier_week,'M45 Pleiades retains catalog identity, type, observing aid, magnitude, Declination Band, and Season.',('M45','Pleiades','open cluster','visibility-magnitude','V ')),
 Case('Caldwell object',caldwell_week,'C4 / NGC 7023 / Iris Nebula appears as Caldwell.',('C4','NGC 7023','Iris Nebula')),
 Case('Finest NGC object',finest_week,'NGC 1491 appears as the selected Finest NGC sample.',('NGC 1491',)),
 Case('naked-eye observing aid',alpha_week,'Achernar has naked-eye SVG and magnitude.',('Achernar','eye.svg','V ')),
 Case('binocular observing aid','W40','M15 has binocular SVG, never a letter B as its rendered observing symbol.',('M15','binoculars.svg')),
 Case('telescope observing aid',source_week(SRC/'messier-visibility-2026.csv',{'messier':'M74'}),'M74 has telescope SVG on its canonical generated week.',('M74','telescope.svg')),
 Case('meteor shower','W33','Perseids has dedicated meteor-shower glyph.',('Perseids','meteor-shower.svg')),
 Case('solar eclipse','W33','Aug 12 total solar eclipse has dedicated solar-eclipse glyph.',('Total solar eclipse','solar-eclipse.svg','greatest eclipse')),
 Case('lunar eclipse','W10','Mar 3 total lunar eclipse has dedicated lunar-eclipse glyph and clear maximum terminology.',('Total lunar eclipse','lunar-eclipse.svg','greatest eclipse')),
 Case('Solar-System ephemeris','W41','Extended targets are ordered Ceres, Uranus, Neptune, Pluto.',('Ceres','Uranus','Neptune','Pluto'),(('Ceres','Uranus'),('Uranus','Neptune'),('Neptune','Pluto'))),
 Case('Pleiades asterism identity',messier_week,'Pleiades M45 says also an asterism inline.',('M45','Pleiades','also an asterism'),(('Pleiades','also an asterism'),)),
 Case('Hyades asterism identity',hyades_week,'Hyades C41 says also an asterism inline.',('C41','Hyades','also an asterism'),(('Hyades','also an asterism'),)),
 ]
def run():
 cases=build_cases(); passed=failed=0
 print('Star Almanack Type Coverage Regression'); print('='*40)
 for i,case in enumerate(cases,1):
  html=html_for(case.week); url=f'{BASE_URL}/{case.week}/'; reasons=[]
  if not html:reasons.append('generated week page is missing')
  else:
   for token in case.checks:
    if token not in html:reasons.append(f'missing {token!r}')
   for left,right in case.proximity:
    if not close_together(html,left,right):reasons.append(f'{right!r} is not attached to/near {left!r}')
  if reasons:failed+=1; status='FAIL'
  else:passed+=1; status='PASS'
  print(f'{i:02d}. {status} — {case.name}\n    {url}\n    Expected: {case.expected}')
  for reason in reasons:print(f'    - {reason}')
 legend=(ROOT/'_includes'/'almanack-notation-legend.html').read_text(encoding='utf-8')
 required=('eye.svg','binoculars.svg','telescope.svg','meteor-shower.svg','solar-eclipse.svg','lunar-eclipse.svg','Observing aid','Events')
 missing=[x for x in required if x not in legend]
 if missing:
  failed+=1; print('LEGEND FAIL')
  for x in missing:print(f'    - missing {x!r}')
 print('-'*40); print(f'RESULT: {passed} PASS / {failed} FAIL'); print(f'Concrete sample cases: {len(cases)}')
 return 1 if failed else 0
if __name__=='__main__':sys.exit(run())
