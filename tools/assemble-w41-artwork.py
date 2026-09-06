#!/usr/bin/env python3
"""Assemble the W41 visual layer after the canonical weekly page is copied."""
from pathlib import Path
import math, shutil

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "almanack" / "2026" / "W41"
FINDERS = OUT / "finders"
SOURCE_FINDERS = ROOT / "Star-Almanack-Repo" / "observer-views" / "W41"

BODIES = [
    ("☉","Sun",6,11+46/60),("☽","Moon",4,0+38/60),
    ("☿","Mercury",7,5+48/60),("♀","Venus",7,8+26/60),
    ("♂","Mars",4,4),("♃","Jupiter",4,20+18/60),
    ("♄","Saturn",0,11+16/60),("♅","Uranus",1,5+27/60),
    ("♆","Neptune",0,2+45/60),("⚳","Ceres",3,17+8/60),
]
SIGNS=[("♈","Aries"),("♉","Taurus"),("♊","Gemini"),("♋","Cancer"),("♌","Leo"),("♍","Virgo"),("♎","Libra"),("♏","Scorpio"),("♐","Sagittarius"),("♑","Capricorn"),("♒","Aquarius"),("♓","Pisces")]
W=H=1400; CX=CY=700; RO=560; RI=430

def xy(lon,r):
    t=math.radians(180+lon)
    return CX+r*math.cos(t), CY-r*math.sin(t)

def label_svg(x,y,text,fs,boxw):
    return f'<rect x="{x-boxw/2:.1f}" y="{y-24:.1f}" width="{boxw:.1f}" height="48" rx="10" fill="white" stroke="#111" stroke-width="1.4"/><text x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="{fs}">{text}</text>'

def chart(mode):
    s=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 1400">','<rect width="1400" height="1400" fill="white"/>','<style>text{font-family:Georgia,"Times New Roman",serif;fill:#111}.sans{font-family:Arial,Helvetica,sans-serif}.z{fill:#111!important;color:#111!important;-webkit-text-fill-color:#111!important}</style>']
    s += [f'<text x="700" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO 2026-W41 Planet Finder</text>',f'<text x="700" y="110" text-anchor="middle" font-size="23">{mode} · Monday, October 5, 2026 · 00:00 UTC</text>',f'<circle cx="700" cy="700" r="560" fill="none" stroke="#111" stroke-width="4"/>',f'<circle cx="700" cy="700" r="430" fill="none" stroke="#111" stroke-width="2"/>']
    for i in range(12):
        x1,y1=xy(i*30,RI); x2,y2=xy(i*30,RO); s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i,(sym,name) in enumerate(SIGNS):
        x,y=xy(i*30+15,495)
        text=(sym+'\ufe0e') if mode=='Greek / Symbols' else name if mode=='Latin' else f'{sym}\ufe0e {name}'
        fs=46 if mode=='Greek / Symbols' else 24 if mode=='Latin' else 22
        s.append(f'<text class="z" x="{x:.1f}" y="{y+8:.1f}" text-anchor="middle" font-size="{fs}">{text}</text>')
    used=[]
    for sym,name,si,deg in BODIES:
        L=si*30+deg
        if name=='Ceres': r=230; shift=-125
        else: r=345; shift=0
        x0,y0=xy(L,r)
        if not shift: 
            # move crowded labels through radial slots
            for rr in (345,290,235,180,400,150):
                xx,yy=xy(L,rr); w=112 if len(name)<8 else 130; cand=(xx,yy,w,48)
                if all(abs(xx-u[0])>(w+u[2])/2+16 or abs(yy-u[1])>32 for u in used):
                    r, x0,y0=rr,xx,yy; break
        th=math.radians(180+L); tx=-math.sin(th); ty=-math.cos(th); x=x0+shift*tx; y=y0+shift*ty
        w=112 if len(name)<8 else 130; used.append((x,y,w,48))
        ex,ey=xy(L,RI-5); s.append(f'<line x1="{ex:.1f}" y1="{ey:.1f}" x2="{x:.1f}" y2="{y:.1f}" stroke="#777" stroke-width="1.3"/>')
        if mode=='Greek / Symbols':
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="29" fill="white" stroke="#111"/><text x="{x:.1f}" y="{y+13:.1f}" text-anchor="middle" font-size="44">{sym}</text>')
        elif mode=='Latin': s.append(label_svg(x,y,name,18,w))
        else: s.append(label_svg(x,y,f'{sym} {name}',17,w+18))
    s += ['<text x="700" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>','<text x="700" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>','<text x="700" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>','</svg>']
    return ''.join(s)

def main():
    OUT.mkdir(parents=True,exist_ok=True); FINDERS.mkdir(exist_ok=True)
    for src,name in (("enif-finder.svg","enif-finder.svg"),("sadalmelik-finder.svg","sadalmelik-finder.svg")):
        shutil.copy2(SOURCE_FINDERS/src,FINDERS/name)
    for mode,fn in (("Greek / Symbols","planet-finder-greek-symbols.svg"),("Latin","planet-finder-latin.svg"),("Mixed / Learner","planet-finder-mixed-learner.svg")):
        (FINDERS/fn).write_text(chart(mode),encoding='utf-8')
    page=OUT/'index.html'; text=page.read_text(encoding='utf-8')
    css='''<style>.w41-finder-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:1rem;margin:1.25rem 0 2rem}.w41-finder-strip figure,.w41-star-finder{margin:0}.w41-finder-strip img,.w41-star-finder img{display:block;width:100%;height:auto}.w41-finder-strip figcaption,.w41-star-finder figcaption{text-align:center;font-family:system-ui,sans-serif;font-size:.82rem;color:var(--muted);margin-top:.35rem}.w41-star-finder{max-width:820px;margin:1.1rem auto 1.6rem}.w41-star-finder img{border:1px solid var(--rule);border-radius:.4rem}@media(max-width:760px){.w41-finder-strip{grid-template-columns:1fr}.w41-star-finder{max-width:none}}</style>'''
    text=text.replace('</head>',css+'</head>',1)
    strip='''<div class="w41-finder-strip"><figure><img src="finders/planet-finder-greek-symbols.svg" alt="Planet Finder — Greek / Symbols"><figcaption>Greek / Symbols</figcaption></figure><figure><img src="finders/planet-finder-latin.svg" alt="Planet Finder — Latin"><figcaption>Latin</figcaption></figure><figure><img src="finders/planet-finder-mixed-learner.svg" alt="Planet Finder — Mixed / Learner"><figcaption>Mixed / Learner</figcaption></figure></div>'''
    text=text.replace('</table>\n<h3>Sky Note</h3>', '</table>\n'+strip+'\n<h3>Sky Note</h3>',1)
    nfm='''<figure class="w41-star-finder"><img src="finders/enif-finder.svg" alt="Enif and M15 finder"><figcaption>Enif and M15</figcaption></figure>'''
    text=text.replace('</p>\n<p><strong>Naked eye:</strong>', '</p>\n'+nfm+'\n<p><strong>Naked eye:</strong>',1)
    aq='''<figure class="w41-star-finder"><img src="finders/sadalmelik-finder.svg" alt="Aquarius and Sadalmelik finder"><figcaption>Aquarius and Sadalmelik</figcaption></figure>'''
    # Place the Aquarius finder at the end of the W41 Sky Note, before the next heading.
    pos=text.find('<h3>', text.find('<h3>Sky Note</h3>')+len('<h3>Sky Note</h3>'))
    if pos!=-1: text=text[:pos]+aq+'\n'+text[pos:]
    page.write_text(text,encoding='utf-8')
    print('Assembled W41 artwork:', FINDERS)

if __name__=='__main__': main()
