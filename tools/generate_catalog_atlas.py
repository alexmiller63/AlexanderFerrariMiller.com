#!/usr/bin/env python3
"""Build the catalog panorama viewer from saved sky charts and repository catalogs.

All catalog entries are included, without a magnitude cutoff. Catalog objects
and official J2000 IAU boundaries have independent script-free display controls.
"""
from pathlib import Path
import argparse, csv, html, json, math, re
import yaml
import generate_panoramic_atlas as gen
ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--panoramas',type=Path,default=ROOT/'star-almanack/chart-library/panoramic')
    parser.add_argument('--output',type=Path,default=ROOT/'star-almanack/chart-library/panoramic/index.html')
    args=parser.parse_args()
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

    def esc(v):return html.escape(str(v))
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
      for text,size in [(label,12),(label,11)]:
       w=len(text)*size*.59
       for radius in [12,20,30,42,60,80,105,135,170,210,260]:
        for dx,dy in [(radius,-radius),(radius,radius),(-radius-w,-radius),(-radius-w,radius),(radius,4),(-radius-w,4)]+[(radius*math.cos(a*math.pi/16)-w/2,radius*math.sin(a*math.pi/16)) for a in range(32)]:
         tx,ty=x+dx,y+dy;box=(tx-3,ty-size-3,tx+w+3,ty+4)
         if not inside(box[0],box[1],2) or not inside(box[2],box[3],2):continue
         if any(box[0]<b[2] and b[0]<box[2] and box[1]<b[3] and b[1]<box[3] for b in occupied):continue
         if any(hits((a,b),(c,d),box) for a,b,c,d in segments):continue
         if any(box[0]-5<ox<box[2]+5 and box[1]-5<oy<box[3]+5 for _,ox,oy in visible):continue
         parts.append(f'<path d="M{x:.2f} {y:.2f} L{tx if dx>0 else tx+w:.2f} {ty-4:.2f}" stroke="{color}" opacity=".5" fill="none"/><text x="{tx:.2f}" y="{ty:.2f}" font-size="{size}" fill="{color}" paint-order="stroke" stroke="#071527" stroke-width="3">{esc(text)}</text>')
         occupied.append(box);placed=True;break
        if placed:break
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
    def clip(a,b,box):
     x,y=a;dx=b[0]-x;dy=b[1]-y;lo,hi=0.,1.
     for p,q in [(-dx,x-box[0]),(dx,box[2]-x),(-dy,y-box[1]),(dy,box[3]-y)]:
      if abs(p)<1e-12:
       if q<0:return None
      elif p<0:lo=max(lo,q/p)
      else:hi=min(hi,q/p)
      if lo>hi:return None
     return ((x+lo*dx,y+lo*dy),(x+hi*dx,y+hi*dy))
    manifest=json.loads((args.panoramas/'manifest.json').read_text());starts=gen.boundaries(2000)
    css='body{margin:0;background:#071527;color:#d9efff;font:16px system-ui}main,header{padding:16px}h1{font-size:26px}a{color:#d9efff}.card{display:block;max-width:700px;padding:20px;border:1px solid #7290ac;border-radius:10px;background:#10263b;text-decoration:none}.card h2{margin:0 0 10px}.chart-list{display:flex;flex-wrap:wrap;gap:8px}.chart-list a,.chart-nav a{padding:8px;border:1px solid #7290ac;border-radius:5px;text-decoration:none}figure{margin:0;display:none}figure:target{display:block}body:not(:has(figure:target)) #view-0{display:block}.chart-nav{display:flex;justify-content:space-between;align-items:center;padding:12px}.chart-scroll{overflow:auto}svg{width:100%;height:auto;min-width:900px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:8px;text-align:left;border-bottom:1px solid #294158}details{padding:12px}summary{cursor:pointer}'
    parts=['<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Catalog Objects · Star Almanack</title><style>'+css+'</style></head><body><header><h1>Star Almanack · Chart Library</h1><a class="card" href="#view-0"><h2>Catalog Objects</h2><p>Fourteen panoramic sky charts with all Messier, Caldwell, and Finest NGC objects. No magnitude limit.</p><strong>Open the Catalog Object Atlas →</strong></a><p>Green: asterisms · Blue: constellations · Amber: catalog objects · J2000.0</p><p>Pan across each chart to inspect the full detail. Open its object list for catalog identities and names.</p><details><summary>Choose a panorama</summary><nav class="chart-list">']
    for i,v in enumerate(manifest['views']):parts.append(f'<a href="#view-{i}">{esc(v["region"]+" "+(v["season"] or ""))}</a>')
    parts.append('</nav></details></header><main>')
    seen=set();report=[]
    for i,v in enumerate(manifest['views']):
     svg=(args.panoramas/v['file']).read_text();base=svg
     region,season=v['region'],v['season'];title=region+(' '+season if season else '')
     if season is None:
      def project(ra,dec):return gen.polar_xy(region,ra/15,dec)
      def inside(x,y,margin=0):return gen.math.hypot(x-600,y-385)<=290-margin
     else:
      low,high,ra0,span,left,right,top,bottom,xy=gen.chart_frame((region,season),2000,starts)
      def project(ra,dec):return xy(ra/15,dec)
      def inside(x,y,margin=0):return left+margin<=x<=right-margin and top+margin<=y<=bottom-margin
     overlay,visible=annotate(svg,project,inside,'panorama')
     # Preserve every original star, constellation, asterism and coordinate line.
     svg=svg.replace('</svg>',overlay+'</svg>')
     for o,x,y in visible:seen.add(id(o))
     assert re.findall('<line\\b[^>]*/>',base)==re.findall('<line\\b[^>]*/>',svg)
     parts.append(f'<figure id="view-{i}"><nav class="chart-nav"><a href="#view-{(i-1)%14}">← Previous</a><span>{esc(title)} · {len(visible)} objects</span><a href="#view-{(i+1)%14}">Next →</a></nav><div class="chart-scroll">{svg}</div><details><summary>Objects in this panorama ({len(visible)})</summary><table><thead><tr><th>Catalog</th><th>Name</th><th>Type</th></tr></thead><tbody>')
     for n,(o,x,y) in enumerate(visible,1):parts.append(f'<tr><td>{esc(" / ".join(o["labels"]))}</td><td>{esc(o["name"])}</td><td>{esc(o["kind"])}</td></tr>')
     parts.append('</tbody></table></details></figure>');report.append((title,len(visible)))
    parts.append('</main></body></html>')
    missing=[o['labels'] for o in objects.values() if id(o) not in seen]
    assert not missing,missing
    s=''.join(parts)
    css='.catalog-objects,.catalog-key{display:none}body:has(#catalog-toggle:checked) .catalog-objects{display:inline}body:has(#catalog-toggle:checked) .catalog-key{display:block}.catalog-toggle{display:flex;align-items:center;gap:12px;padding:14px;margin:12px 0;border:1px solid #7290ac;border-radius:8px;background:#10263b;cursor:pointer;font-weight:600}.catalog-toggle input{width:24px;height:24px;accent-color:#ffc66d}.catalog-toggle:focus-within{outline:2px solid #ffc66d;outline-offset:3px}'
    s=s.replace('</style>',css+'</style>',1)
    control='<label class="catalog-toggle" for="catalog-toggle"><input type="checkbox" id="catalog-toggle" aria-controls="panorama-charts"><span>Show catalog objects</span></label>'
    s=s.replace('</header><main>',control+'</header><main id="panorama-charts">',1)
    s=s.replace('<details><summary>Objects in this panorama','<details class="catalog-key"><summary>Objects in this panorama')
    s=s.replace('<h1>Star Almanack · Chart Library</h1>','<p><a href="../">← Chart Library</a></p><h1>Panoramic Sky Atlas · Star Almanack</h1>')
    s=s.replace('Open its object list for catalog identities and names.','Turn on “Show catalog objects” to reveal markers, labels, and object lists.')
    old=s;counts=[]
    for m in list(re.finditer(r'<figure id="view-(\d+)".*?</figure>',s,re.S))[::-1]:
     idx=int(m.group(1));f=m.group();v=manifest['views'][idx];region,season=v['region'],v['season'];lines=[]
     if season is None:
      clipshape='<circle cx="600" cy="385" r="290"/>'
      for a,b in segments:
       # Segments far outside the cap cannot touch the view.
       if region=='Arctic' and max(a[1],b[1])<65:continue
       if region=='Antarctic' and min(a[1],b[1])>-65:continue
       p,q=gen.polar_xy(region,a[0]/15,a[1]),gen.polar_xy(region,b[0]/15,b[1]);lines.append((p,q))
     else:
      low,high,start,span,left,right,top,bottom,xy=gen.chart_frame((region,season),2000,starts);period=(right-left)*24/span;box=(left,top,right,bottom)
      clipshape=f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}"/>'
      for a,b in segments:
       if max(a[1],b[1])<low or min(a[1],b[1])>high:continue
       x,y=xy(a[0]/15,a[1]);u,w=xy(b[0]/15,b[1]);u=x+(u-x+period/2)%period-period/2
       for shift in [-period,0,period]:
        pair=clip((x+shift,y),(u+shift,w),box)
        if pair and math.dist(*pair)>.005:lines.append(pair)
     # Rounded paths are deduplicated again after clipping.
     paths=sorted(set(f'M{a[0]:.2f},{a[1]:.2f}L{b[0]:.2f},{b[1]:.2f}' for a,b in lines))
     layer=f'<defs><clipPath id="boundary-clip-{idx}">{clipshape}</clipPath></defs><g class="constellation-boundaries" clip-path="url(#boundary-clip-{idx})" fill="none" stroke="#d0d6de" stroke-width="1" opacity=".48" aria-label="Official IAU constellation boundaries">'+''.join(f'<path d="{p}"/>' for p in paths)+'</g>'
     # Place boundaries behind stars and figure labels.
     pos=f.index('<circle ');f=f[:pos]+layer+f[pos:];s=s[:m.start()]+f+s[m.end():];counts.append((idx,len(paths)))
    css='.constellation-boundaries{display:none}body:has(#boundaries-toggle:checked) .constellation-boundaries{display:inline}'
    s=s.replace('</style>',css+'</style>',1)
    control='<label class="catalog-toggle" for="boundaries-toggle"><input type="checkbox" id="boundaries-toggle" aria-controls="panorama-charts"><span>Show constellation boundaries</span></label>'
    s=s.replace('</header><main',control+'</header><main',1)
    s=s.replace('Panoramas · Show or Hide Catalog Objects','Panoramas · Optional Catalog Objects and Constellation Boundaries')
    s=s.replace('Amber: catalog objects · J2000.0','Amber: catalog objects · Muted white: IAU boundaries · J2000.0')
    # Invariants: existing star symbols, figure lines, and catalog layers are identical.
    assert re.findall(r'<line\b[^>]*/>',s)==re.findall(r'<line\b[^>]*/>',old)
    stripped=re.sub(r'<defs><clipPath id="boundary-clip-\d+">.*?</clipPath></defs>', '', s, flags=re.S)
    assert re.findall(r'<circle\b[^>]*/>',stripped)==re.findall(r'<circle\b[^>]*/>',old)
    assert s.count('class="constellation-boundaries"')==14
    assert 'id="boundaries-toggle" checked' not in s and 'id="catalog-toggle" checked' not in s

    s=re.sub(r'<a class="card" href="#view-0">.*?</a>', '<p>Fourteen panoramic sky charts. Use the optional layers to explore catalog objects and constellation boundaries.</p>', s, count=1, flags=re.S)
    s=s.replace('<title>Catalog Objects · Star Almanack</title>','<title>Panoramic Sky Atlas · Star Almanack</title>')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(s,encoding='utf-8')
    print(f'Generated {len(manifest["views"])} panoramas with {len(objects)} catalog entries and independent display toggles')

if __name__=="__main__":
    main()
