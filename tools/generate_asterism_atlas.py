#!/usr/bin/env python3
"""Generate 28 deterministic J2000 asterism charts from accepted paths."""
import csv, html, json, math, argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
 p=argparse.ArgumentParser();p.add_argument("--output",type=Path,default=ROOT/"star-almanack/chart-library/asterisms");a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 paths=json.loads((ROOT/"asterism-figure-paths.json").read_text())["asterisms"]
 stars=[]
 with (ROOT/"expanded-bayer-stars.csv").open(newline="",encoding="utf-8") as catalog:
  for star in csv.DictReader(catalog):
   try:
    mag=float(star["mag"])
    if mag<=5.0: stars.append((float(star["ra_h"])*15,float(star["dec_deg"]),mag,star["proper"] or star["bayer"]))
   except (ValueError,KeyError): continue
 rows={}
 with (ROOT/"asterism-member-coordinates.csv").open(newline="",encoding="utf-8") as f:
  for r in csv.DictReader(f):
   rows[(r["asterism"],r["member"])]=r
 assert len(paths)==28, f"Expected 28 asterisms, got {len(paths)}"
 manifest=[]
 for name,entry in paths.items():
  members={m:r for (n,m),r in rows.items() if n==name}
  if not members: raise ValueError(f"No coordinates: {name}")
  pts={m:(float(r["ra_h"])*15,float(r["dec_deg"]),float(r["mag"])) for m,r in members.items()}
  for path in entry["paths"]:
   for m in path:
    if m not in pts:raise ValueError(f"Missing {name}: {m}")
  # Circular RA centroid prevents a 0h/24h seam artifact.
  angles=[math.radians(v[0]) for v in pts.values()]
  center=math.degrees(math.atan2(sum(math.sin(t) for t in angles),sum(math.cos(t) for t in angles)))%360
  coords={m:(((ra-center+180)%360)-180,dec,mag) for m,(ra,dec,mag) in pts.items()}
  minx=min(v[0] for v in coords.values());maxx=max(v[0] for v in coords.values())
  miny=min(v[1] for v in coords.values());maxy=max(v[1] for v in coords.values())
  # Scale axes together and retain breathing room.
  span=max((maxx-minx)*max(.25,math.cos(math.radians((miny+maxy)/2))),maxy-miny,2)
  scale=520/(span*1.3)
  midx=(minx+maxx)/2;midy=(miny+maxy)/2
  def xy(m):
   x,y,_=coords[m];return 600+(x-midx)*scale*max(.25,math.cos(math.radians(midy))),370-(y-midy)*scale
  parts=['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="740" viewBox="0 0 1200 740">','<rect width="1200" height="740" fill="#071527"/>',f'<text x="600" y="55" text-anchor="middle" font-size="30" fill="#d9efff">{html.escape(name)}</text>','<text x="600" y="84" text-anchor="middle" font-size="15" fill="#a9c7d9">Star Almanack · J2000.0 · accepted asterism geometry</text>']
  # Context stars share the exact projection used for accepted asterism geometry.
  # Keep the original scale and geometry unchanged; only add a background layer.
  for ra,dec,mag,label in stars:
   dx=((ra-center+180)%360)-180
   x=600+(dx-midx)*scale*max(.25,math.cos(math.radians(midy)))
   y=370-(dec-midy)*scale
   if 24<x<1176 and 112<y<714:
    rad=max(.75,min(3.8,3.4-.48*mag))
    parts.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{rad:.2f}" fill="#aabed0" opacity=".78"/>')
  for path in entry["paths"]:
   for u,v in zip(path,path[1:]):
    x1,y1=xy(u);x2,y2=xy(v)
    parts.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#4fc47b" stroke-width="3"/>')
  for m,(ra,dec,mag) in coords.items():
   x,y=xy(m);rad=max(2.5,min(7,6.5-mag*.6))
   parts.extend([f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{rad:.1f}" fill="#f6f4dc"/>',f'<text x="{x+9:.2f}" y="{y-9:.2f}" fill="#d9efff" font-size="14" paint-order="stroke" stroke="#071527" stroke-width="3">{html.escape(m)}</text>'])
  parts.append('</svg>')
  filename="asterism-"+str(entry["id"])+".svg"
  (a.output/filename).write_text("\n".join(parts),encoding="utf-8")
  manifest.append({"name":name,"file":filename,"members":len(members)})
 (a.output/"manifest.json").write_text(json.dumps({"epoch":"J2000.0","views":manifest},indent=2)+"\n")
 print(f"Generated {len(manifest)} charts in {a.output}")
if __name__=="__main__":main()
