#!/usr/bin/env python3
"""Generate Star Almanack planet-finder SVGs from the canonical weekly ephemeris CSV.

Usage: python tools/generate-current-planet-finder.py 2026 37
"""
from pathlib import Path
import csv, datetime as dt, math, sys

ROOT=Path(__file__).resolve().parents[1]
SIGNS=[('♈','Aries'),('♉','Taurus'),('♊','Gemini'),('♋','Cancer'),('♌','Leo'),('♍','Virgo'),('♎','Libra'),('♏','Scorpio'),('♐','Sagittarius'),('♑','Capricorn'),('♒','Aquarius'),('♓','Pisces')]
SIGN_INDEX={s:i for i,(s,_) in enumerate(SIGNS)}
BODIES=[('☉','Sun','sun'),('☽','Moon','moon'),('☿','Mercury','mercury'),('♀','Venus','venus'),('♂','Mars','mars'),('♃','Jupiter','jupiter'),('♄','Saturn','saturn'),('♅','Uranus','uranus'),('♆','Neptune','neptune'),('⚳','Ceres','ceres')]
W=H=1400; C=700; RI=430; RO=560

def xy(lon,r):
    t=math.radians(180+lon)
    return C+r*math.cos(t),C-r*math.sin(t)

def parse_pos(value):
    sign=value[0]
    rest=value[1:].strip().replace('′','')
    deg_s,min_s=rest.split('°')
    return sign,int(deg_s),int(min_s),SIGN_INDEX[sign]*30+int(deg_s)+int(min_s)/60

def overlap(a,b,p=14):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    return abs(ax-bx)<(aw+bw)/2+p and abs(ay-by)<(ah+bh)/2+p

def dims(mode,name):
    if mode=='symbols': return 68,68
    if mode=='latin': return max(110,14*len(name)+34),52
    return max(140,14*len(name)+74),52

def place(mode,rows):
    reserved=[(700,680,380,48),(700,722,640,40),(700,758,480,40)]
    placed=[]; result={}
    lons=[r[-1] for r in rows]
    order=sorted(range(len(rows)),key=lambda i:min(abs((lons[i]-lons[j]+180)%360-180) for j in range(len(rows)) if j!=i))
    for i in order:
        sym,name,sign,d,m,L=rows[i]; w,h=dims(mode,name)
        t=math.radians(180+L); tx=-math.sin(t); ty=-math.cos(t)
        chosen=None
        for r in (340,300,260,380,220,180):
            bx,by=xy(L,r)
            for sh in (0,-70,70,-120,120,-170,170):
                x=bx+sh*tx; y=by+sh*ty; box=(x,y,w,h)
                if x-w/2<300 or x+w/2>1100 or y-h/2<300 or y+h/2>1100: continue
                if any(overlap(box,q,16) for q in placed): continue
                if any(overlap(box,q,18) for q in reserved): continue
                chosen=box; break
            if chosen: break
        if not chosen:
            raise RuntimeError(f'No collision-free label position for {name}')
        placed.append(chosen); result[i]=chosen
    return [result[i] for i in range(len(rows))]

def edge_point(x,y,w,h,ax,ay,mode):
    dx=ax-x; dy=ay-y
    if mode=='symbols':
        dist=math.hypot(dx,dy) or 1
        return x+dx/dist*34,y+dy/dist*34
    sx=(w/2)/abs(dx) if dx else 1e9; sy=(h/2)/abs(dy) if dy else 1e9
    t=min(sx,sy)
    return x+dx*t,y+dy*t

def build(mode,year,week,monday,rows):
    title={'symbols':'Greek / Symbols','latin':'Latin','mixed':'Mixed / Learner'}[mode]
    date=dt.date.fromisoformat(monday)
    date_label=f"{date.strftime('%A, %B')} {date.day}, {date.year}"
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 1400 1400">','<rect width="100%" height="100%" fill="white"/>','<style>text{font-family:Georgia,"Times New Roman",serif;fill:#111}.sans{font-family:Arial,Helvetica,sans-serif}.symbol{font-family:"Arial Unicode MS","Segoe UI Symbol","Noto Sans Symbols 2","Apple Symbols",serif;font-variant-emoji:text;fill:#111}</style>',f'<text x="700" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO {year}-W{week:02d} Planet Finder</text>',f'<text x="700" y="110" text-anchor="middle" font-size="23">{title} · {date_label} · 00:00 UTC</text>','<circle cx="700" cy="700" r="560" fill="none" stroke="#111" stroke-width="4"/>','<circle cx="700" cy="700" r="430" fill="none" stroke="#111" stroke-width="2"/>']
    for i in range(12):
        x1,y1=xy(i*30,RI); x2,y2=xy(i*30,RO)
        s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i,(sgn,name) in enumerate(SIGNS):
        x,y=xy(i*30+15,(RI+RO)/2)
        if mode=='symbols': text,fs,cls=sgn+'︎',48,' class="symbol"'
        elif mode=='latin': text,fs,cls=name,24,''
        else: text,fs,cls=sgn+'︎ '+name,22,' class="symbol"'
        s.append(f'<text{cls} x="{x:.1f}" y="{y+8:.1f}" text-anchor="middle" font-size="{fs}">{text}</text>')
    s.append('<text x="112" y="708" text-anchor="end" font-size="20" class="sans">0° Aries</text>')
    boxes=place(mode,rows)
    for row,box in zip(rows,boxes):
        sym,name,sign,d,m,L=row; x,y,w,h=box; ax,ay=xy(L,RI-5); gx,gy=xy(L,390); ex,ey=edge_point(x,y,w,h,ax,ay,mode)
        s.append(f'<polyline points="{ax:.1f},{ay:.1f} {gx:.1f},{gy:.1f} {ex:.1f},{ey:.1f}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round"/>')
        s.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="3.5" fill="#111"/>')
    for row,box in zip(rows,boxes):
        sym,name,sign,d,m,L=row; x,y,w,h=box
        if mode=='symbols':
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="34" fill="white" stroke="#111" stroke-width="1.5"/>')
            s.append(f'<text class="symbol" x="{x:.1f}" y="{y+14:.1f}" text-anchor="middle" font-size="46">{sym}︎</text>')
        else:
            label=name if mode=='latin' else sym+'︎ '+name; cls=' class="symbol"' if mode=='mixed' else ''
            s.append(f'<rect x="{x-w/2:.1f}" y="{y-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="white" stroke="#111" stroke-width="1.5"/>')
            s.append(f'<text{cls} x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="{18 if mode=="latin" else 17}">{label}</text>')
    s += ['<text x="700" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>','<text x="700" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>','<text x="700" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>','</svg>']
    return '\n'.join(s)

def main():
    year=int(sys.argv[1]); week=int(sys.argv[2]); key=f'{year}-W{week:02d}'
    csv_path=ROOT/'Star-Almanack-Repo'/f'weekly-ephemeris-{year}.csv'
    with csv_path.open(encoding='utf-8',newline='') as f:
        row=next((r for r in csv.DictReader(f) if r['iso_week']==key),None)
    if not row: raise SystemExit(f'{key} not found in {csv_path}')
    parsed=[]
    for sym,name,col in BODIES:
        sign,d,m,L=parse_pos(row[col]); parsed.append((sym,name,sign,d,m,L))
    out=ROOT/'almanack'/str(year)/f'W{week:02d}'/'finders'; out.mkdir(parents=True,exist_ok=True)
    for mode,fn in [('symbols','planet-finder-greek-symbols.svg'),('latin','planet-finder-latin.svg'),('mixed','planet-finder-mixed-learner.svg')]:
        (out/fn).write_text(build(mode,year,week,row['monday_utc'],parsed),encoding='utf-8')
    print(f'Generated collision-safe Planet Finder for {key}')

if __name__=='__main__': main()
