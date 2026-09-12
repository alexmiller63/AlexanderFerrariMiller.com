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

def point_in_box(p,box,pad=0):
    x,y=p; bx,by,bw,bh=box
    return bx-bw/2-pad <= x <= bx+bw/2+pad and by-bh/2-pad <= y <= by+bh/2+pad

def seg_hits_box(a,b,box,pad=8):
    """Return True when segment a-b enters an axis-aligned label box."""
    x1,y1=a; x2,y2=b
    bx,by,bw,bh=box
    xmin=bx-bw/2-pad; xmax=bx+bw/2+pad
    ymin=by-bh/2-pad; ymax=by+bh/2+pad
    dx=x2-x1; dy=y2-y1
    t0=0.0; t1=1.0
    for p,q in ((-dx,x1-xmin),(dx,xmax-x1),(-dy,y1-ymin),(dy,ymax-y1)):
        if abs(p) < 1e-9:
            if q < 0: return False
            continue
        r=q/p
        if p < 0:
            if r > t1: return False
            if r > t0: t0=r
        else:
            if r < t0: return False
            if r < t1: t1=r
    return t0 <= t1

def box_edge(center,box,toward):
    """Point on box perimeter reached from center in direction toward."""
    cx,cy=center; tx,ty=toward; _,_,bw,bh=box
    dx=tx-cx; dy=ty-cy
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return center
    sx=(bw/2)/abs(dx) if abs(dx) > 1e-9 else float('inf')
    sy=(bh/2)/abs(dy) if abs(dy) > 1e-9 else float('inf')
    s=min(sx,sy)
    return cx+dx*s, cy+dy*s

def route_leader(anchor,target_box,L,r,obstacles):
    """Route from exact longitude anchor to target label without crossing labels.

    The anchor never moves. Prefer a direct segment; otherwise move inward along
    the same longitude, then use a tangential dogleg. This preserves the exact
    longitude reference while routing around occupied label boxes.
    """
    tx,ty,_,_=target_box
    target=(tx,ty)

    def clear(points):
        for a,b in zip(points,points[1:]):
            if any(seg_hits_box(a,b,box,10) for box in obstacles):
                return False
        return True

    end=box_edge(target,target_box,anchor)
    direct=[anchor,end]
    if clear(direct):
        return direct

    route_radii=[]
    for rr in (min(RI-55,max(r+55,170)), r, max(r-55,150), max(r-95,130), 180, 150):
        if rr not in route_radii:
            route_radii.append(rr)

    theta=math.radians(180+L)
    tangent=(-math.sin(theta), math.cos(theta))
    for rr in route_radii:
        radial=xy(L,rr)
        for shift in (0,40,-40,70,-70,100,-100,130,-130,160,-160):
            bend=(radial[0]+shift*tangent[0], radial[1]+shift*tangent[1])
            end=box_edge(target,target_box,bend)
            pts=[anchor,bend,end]
            if clear(pts):
                return pts

    # Deterministic fallback: preserve the exact anchor and stop at the label
    # edge even if no collision-free dogleg is available.
    return direct

def build(mode):
    pos=[]; placed=[]
    center_reserved=[(C,C-18,540,46),(C,C+22,690,40),(C,C+57,440,40)]
    reserved=list(center_reserved)
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

    all_boxes=[(x,y,w,h) for _,_,_,_,_,_,_,x,y,w,h in pos]
    for idx,(sym,name,sgn,d,m,L,r,x,y,w,h) in enumerate(pos):
        ex,ey=xy(L,RI-5)
        target_box=(x,y,w,h)
        obstacles=center_reserved + [b for j,b in enumerate(all_boxes) if j != idx]
        route=route_leader((ex,ey),target_box,L,r,obstacles)
        pts=' '.join(f'{px:.1f},{py:.1f}' for px,py in route)
        s.append(f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round"/>')
        if mode=='symbols': s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="29" fill="white" stroke="#111"/><text x="{x:.1f}" y="{y+13:.1f}" text-anchor="middle" font-size="44">{sym}</text>')
        else:
            label=name if mode=='latin' else f'{sym} {name}'; ww=max(100,13*len(name)+26) if mode=='latin' else max(118,12*len(name)+58); s.append(f'<rect x="{x-ww/2:.1f}" y="{y-24:.1f}" width="{ww:.1f}" height="48" rx="10" fill="white" stroke="#111"/><text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="18">{label}</text>')
    s += [f'<text x="{C}" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>',f'<text x="{C}" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>',f'<text x="{C}" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>','</svg>']
    (OUT/f'planet-finder-{mode}.svg').write_text('\n'.join(s),encoding='utf-8')

for mode in ('symbols','latin','mixed'): build(mode)
print('Generated three W41 Planet Finder SVGs')
