#!/usr/bin/env python3
"""Generate the three frozen W41 Planet Finder SVGs."""
from pathlib import Path
import math

OUT = Path("observer-views/W41")
OUT.mkdir(parents=True, exist_ok=True)
BODIES = [("☉","Sun","♎",11,46),("☽","Moon","♌",0,38),("☿","Mercury","♏",5,48),("♀","Venus","♏",8,26),("♂","Mars","♌",4,0),("♃","Jupiter","♌",20,18),("♄","Saturn","♈",11,16),("♅","Uranus","♊",5,27),("♆","Neptune","♈",2,45),("⚳","Ceres","♋",17,8)]
SIGNS=[("♈","Aries"),("♉","Taurus"),("♊","Gemini"),("♋","Cancer"),("♌","Leo"),("♍","Virgo"),("♎","Libra"),("♏","Scorpio"),("♐","Sagittarius"),("♑","Capricorn"),("♒","Aquarius"),("♓","Pisces")]
IDX={s:i for i,(s,_) in enumerate(SIGNS)}
W=H=1400; C=700; RO=560; RI=430

def xy(lon,r):
    t=math.radians(180+lon); return C+r*math.cos(t),C-r*math.sin(t)

def ov(a,b,p=12):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    return abs(ax-bx)<(aw+bw)/2+p and abs(ay-by)<(ah+bh)/2+p

def build(mode):
    pos=[]; placed=[]
    reserved=[(C,C-18,540,46),(C,C+22,690,40),(C,C+57,440,40)]
    for i,(_,n) in enumerate(SIGNS):
        x,y=xy(i*30+15,(RI+RO)/2); reserved.append((x,y,170 if n in ('Aries','Cancer') else 130,66 if n in ('Aries','Cancer') else 50))
    slots=[345,290,235,180,400,150]
    for sym,name,sgn,d,m in BODIES:
        L=IDX[sgn]*30+d+m/60; w,h=(64,64) if mode=='symbols' else (max(100,13*len(name)+26),48)
        if name=='Ceres' and mode!='symbols':
            r=230; x0,y0=xy(L,r); t=math.radians(180+L); x=x0+125*math.sin(t); y=y0+125*math.cos(t); chosen=(r,x,y,w,h)
        else:
            chosen=None
            for r in slots:
                x,y=xy(L,r); cand=(x,y,w,h)
                if all(not ov(cand,q,16) for q in placed) and all(not ov(cand,q,20) for q in reserved): chosen=(r,x,y,w,h); break
            if chosen is None:
                for r in slots:
                    for sh in (-36,36,-64,64,-92,92,-120,120,-148,148,-176,176):
                        x0,y0=xy(L,r); t=math.radians(180+L); x=x0-sh*math.sin(t); y=y0-sh*math.cos(t); cand=(x,y,w,h)
                        if all(not ov(cand,q,14) for q in placed) and all(not ov(cand,q,18) for q in reserved): chosen=(r,x,y,w,h); break
                    if chosen: break
            if chosen is None: chosen=(100,*xy(L,100),w,h)
        r,x,y,w,h=chosen; placed.append((x,y,w,h)); pos.append((sym,name,sgn,d,m,L,r,x,y,w,h))
    title={'symbols':'Greek / Symbols','latin':'Latin','mixed':'Mixed / Learner'}[mode]
    s=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><rect width="100%" height="100%" fill="white"/><style>text{{font-family:Georgia,"Times New Roman",serif;fill:#111}}.sans{{font-family:Arial,Helvetica,sans-serif}}</style>',f'<text x="{C}" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO 2026-W41 Planet Finder</text>',f'<text x="{C}" y="110" text-anchor="middle" font-size="23">{title} · Monday, October 5, 2026 · 00:00 UTC</text>',f'<circle cx="{C}" cy="{C}" r="{RO}" fill="none" stroke="#111" stroke-width="4"/><circle cx="{C}" cy="{C}" r="{RI}" fill="none" stroke="#111" stroke-width="2"/>']
    for i in range(12):
        x1,y1=xy(i*30,RI); x2,y2=xy(i*30,RO); s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i,(sgn,n) in enumerate(SIGNS):
        x,y=xy(i*30+15,(RI+RO)/2); txt=sgn if mode=='symbols' else (n if mode=='latin' else f'{sgn} {n}'); fs=48 if mode=='symbols' else (24 if mode=='latin' else 22); s.append(f'<text x="{x:.1f}" y="{y+10:.1f}" text-anchor="middle" font-size="{fs}">{txt}</text>')
    s.append(f'<text x="250" y="708" text-anchor="end" font-size="20" class="sans">0° Aries</text>')
    for sym,name,sgn,d,m,L,r,x,y,w,h in pos:
        ex,ey=xy(L,RI-5); s.append(f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#777" stroke-width="1.3"/>')
        if mode=='symbols': s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="29" fill="white" stroke="#111"/><text x="{x:.1f}" y="{y+13:.1f}" text-anchor="middle" font-size="44">{sym}</text>')
        else:
            label=name if mode=='latin' else f'{sym} {name}'; ww=max(100,13*len(name)+26) if mode=='latin' else max(118,12*len(name)+58); s.append(f'<rect x="{x-ww/2:.1f}" y="{y-24:.1f}" width="{ww:.1f}" height="48" rx="10" fill="white" stroke="#111"/><text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="18">{label}</text>')
    s += [f'<text x="{C}" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>',f'<text x="{C}" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>',f'<text x="{C}" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>','</svg>']
    (OUT/f'planet-finder-{mode}.svg').write_text('\n'.join(s),encoding='utf-8')

for mode in ('symbols','latin','mixed'): build(mode)
print('Generated three W41 Planet Finder SVGs')
