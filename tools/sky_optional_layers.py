"""Optional asterism sky layers, using saved repository catalogs and boundaries."""
from pathlib import Path
import csv, html, math, re
import yaml
ROOT=Path(__file__).resolve().parents[1]
def esc(v):return html.escape(str(v))
def load_layers():
    objects={}
    def add(key,ra,dec,label,name,kind,mag):
     key=re.sub(r'\s+','',str(key)).upper()
     if key not in objects:objects[key]={'ra':float(ra)*15,'dec':float(dec),'labels':[],'name':name or '', 'kind':kind}
     o=objects[key]
     if label not in o['labels']:o['labels'].append(label)
     if not o['name'] and name:o['name']=name
    for r in yaml.safe_load((ROOT/'fixed-objects.yaml').read_text())['messier']:
     add('NGC'+str(r[1]) if r[1] else r[0],r[5],r[6],r[0],r[2],r[3],r[7])
    for r in csv.DictReader((ROOT/'caldwell-catalog.csv').open()):
     add(r['catalog'],r['ra_h'],r['dec_deg'],r['caldwell'],r['name'],r['type'],r['mag'])
    for r in csv.DictReader((ROOT/'finest-ngc-catalog.csv').open()):
     add(r['catalog'],r['ra_h'],r['dec_deg'],r['catalog']+' (Finest)',r['name'],r['type'],r['mag'])

    def annotate(svg,project,inside,tag):
     # Labels are checked against existing text, stars, and every stick segment.
     occupied=[];segments=[]
     for t in re.findall(r'<text\b[^>]*>.*?</text>',svg):
      def attr(a,default):
       m=re.search(a+r'="([^"]+)"',t);return m.group(1) if m else default
      x=float(attr('x','0'));y=float(attr('y','0'));size=float(attr('font-size','14'));w=len(html.unescape(re.sub('<[^>]+>','',t)))*size*.59
      anchor=attr('text-anchor','start');x-=w/2 if anchor=='middle' else w if anchor=='end' else 0
      occupied.append((x-4,y-size-4,x+w+4,y+5))
     for l in re.findall(r'<line\b[^>]*/>',svg):
      vals=[re.search(k+r'="([^"]+)"',l) for k in ['x1','y1','x2','y2']]
      if all(vals):segments.append(tuple(float(v.group(1)) for v in vals))
     def hits(a,b,box):
      x,y=a;dx=b[0]-x;dy=b[1]-y;lo,hi=0.,1.
      for v,q in [(-dx,x-box[0]),(dx,box[2]-x),(-dy,y-box[1]),(dy,box[3]-y)]:
       if abs(v)<1e-12:
        if q<0:return False
       elif v<0:lo=max(lo,q/v)
       else:hi=min(hi,q/v)
       if lo>hi:return False
      return True
     visible=[]
     for o in objects.values():
      pt=project(o['ra'],o['dec'])
      if pt is not None and inside(*pt,0):visible.append((o,*pt))
     parts=[f'<g class="catalog-objects" data-view="{tag}">']
     for idx,(o,x,y) in enumerate(visible,1):
      label=re.sub(r' \(Finest\)$', '', o['labels'][0]);color='#ffc66d'
      parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#071527" stroke="{color}" stroke-width="1.7"><title>{esc(label+": "+o["name"])}</title></circle>')
      # Prefer the catalog identity. A numbered key keeps a crowded field legible.
      placed=False
      for text,size in [(label,12),(label,11),(label,10)]:
       w=len(text)*size*.59
       # Search all candidate positions by leader length. Previously the
       # whole-chart grid ran inside the first ring, before closer rings.
       candidates=[]
       for radius in [12,20,30,42,60,80,105,135,170,210,260,320,400,500,650,800,1000]:
        candidates.extend([(radius,-radius),(radius,radius),(-radius-w,-radius),(-radius-w,radius),(radius,4),(-radius-w,4)])
        candidates.extend((radius*math.cos(a*math.pi/16)-w/2,radius*math.sin(a*math.pi/16)) for a in range(32))
       candidates.extend((tx-x,ty-y) for ty in range(130,950,18) for tx in range(40,1710,30))
       candidates.sort(key=lambda p: math.hypot(max(p[0],min(0,p[0]+w)),p[1]-4))
       for dx,dy in candidates:
        tx,ty=x+dx,y+dy;box=(tx-3,ty-size-3,tx+w+3,ty+4)
        if not inside(box[0],box[1],2) or not inside(box[2],box[3],2):continue
        if any(box[0]<b[2] and b[0]<box[2] and box[1]<b[3] and b[1]<box[3] for b in occupied):continue
        if any(hits((a,b),(c,d),box) for a,b,c,d in segments):continue
        if any(box[0]-5<ox<box[2]+5 and box[1]-5<oy<box[3]+5 for _,ox,oy in visible):continue
        parts.append(f'<path d="M{x:.2f} {y:.2f} L{max(tx,min(x,tx+w)):.2f} {ty-4:.2f}" stroke="{color}" opacity=".5" fill="none"/><text x="{tx:.2f}" y="{ty:.2f}" font-size="{size}" fill="{color}" paint-order="stroke" stroke="#071527" stroke-width="3">{esc(text)}</text>')
        occupied.append(box);placed=True;break
       if placed:break
      assert placed, ('Cannot place catalog label', label, tag)
     parts.append('</g>')
     return ''.join(parts),visible
    bounds={p.stem:p.read_text() for p in (ROOT/'reference-data/iau-constellation-boundaries').glob('*.txt')};assert len(bounds)==89
    segments=[];seen=set()
    for name,text in bounds.items():
     pts=[]
     for line in text.splitlines():
      if not line.strip():continue
      ra,dec,_=line.split('|');h,m,sec=map(float,ra.split());pts.append((15*(h+m/60+sec/3600),float(dec)))
     assert len(pts)>=3,name
     for a,b in zip(pts,pts[1:]+pts[:1]):
      key=tuple(sorted((tuple(round(v,5) for v in a),tuple(round(v,5) for v in b))))
      if key in seen:continue
      seen.add(key)
      da=(b[0]-a[0]+180)%360-180;dd=b[1]-a[1]
      n=max(1,math.ceil(max(abs(da)*math.cos(math.radians((a[1]+b[1])/2)),abs(dd))/.4))
      ps=[(a[0]+da*i/n,a[1]+dd*i/n) for i in range(n+1)]
      segments.extend(zip(ps,ps[1:]))
    return annotate, segments
