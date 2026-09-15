#!/usr/bin/env python3
"""Compute experimental 2026 Nights of Observance for the 88 IAU constellations.

Constellation boundary geometry is read only from the repository snapshot.
Normal Almanack builds must not depend on a live external reference site.
"""
from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

from compute_bayer_visibility_2026 import best_visibility, iso_date

DEFAULT_STEP_DEG = 0.10
SNAPSHOT_DIR = Path(__file__).resolve().parent / "reference-data" / "iau-constellation-boundaries"

CONSTELLATIONS = [
    ("Andromeda", "And"), ("Antlia", "Ant"), ("Apus", "Aps"), ("Aquarius", "Aqr"), ("Aquila", "Aql"), ("Ara", "Ara"), ("Aries", "Ari"), ("Auriga", "Aur"), ("Boötes", "Boo"), ("Caelum", "Cae"), ("Camelopardalis", "Cam"), ("Cancer", "Cnc"), ("Canes Venatici", "CVn"), ("Canis Major", "CMa"), ("Canis Minor", "CMi"), ("Capricornus", "Cap"), ("Carina", "Car"), ("Cassiopeia", "Cas"), ("Centaurus", "Cen"), ("Cepheus", "Cep"), ("Cetus", "Cet"), ("Chamaeleon", "Cha"), ("Circinus", "Cir"), ("Columba", "Col"), ("Coma Berenices", "Com"), ("Corona Australis", "CrA"), ("Corona Borealis", "CrB"), ("Corvus", "Crv"), ("Crater", "Crt"), ("Crux", "Cru"), ("Cygnus", "Cyg"), ("Delphinus", "Del"), ("Dorado", "Dor"), ("Draco", "Dra"), ("Equuleus", "Equ"), ("Eridanus", "Eri"), ("Fornax", "For"), ("Gemini", "Gem"), ("Grus", "Gru"), ("Hercules", "Her"), ("Horologium", "Hor"), ("Hydra", "Hya"), ("Hydrus", "Hyi"), ("Indus", "Ind"), ("Lacerta", "Lac"), ("Leo", "Leo"), ("Leo Minor", "LMi"), ("Lepus", "Lep"), ("Libra", "Lib"), ("Lupus", "Lup"), ("Lynx", "Lyn"), ("Lyra", "Lyr"), ("Mensa", "Men"), ("Microscopium", "Mic"), ("Monoceros", "Mon"), ("Musca", "Mus"), ("Norma", "Nor"), ("Octans", "Oct"), ("Ophiuchus", "Oph"), ("Orion", "Ori"), ("Pavo", "Pav"), ("Pegasus", "Peg"), ("Perseus", "Per"), ("Phoenix", "Phe"), ("Pictor", "Pic"), ("Pisces", "Psc"), ("Piscis Austrinus", "PsA"), ("Puppis", "Pup"), ("Pyxis", "Pyx"), ("Reticulum", "Ret"), ("Sagitta", "Sge"), ("Sagittarius", "Sgr"), ("Scorpius", "Sco"), ("Sculptor", "Scl"), ("Scutum", "Sct"), ("Serpens", "Ser"), ("Sextans", "Sex"), ("Taurus", "Tau"), ("Telescopium", "Tel"), ("Triangulum", "Tri"), ("Triangulum Australe", "TrA"), ("Tucana", "Tuc"), ("Ursa Major", "UMa"), ("Ursa Minor", "UMi"), ("Vela", "Vel"), ("Virgo", "Vir"), ("Volans", "Vol"), ("Vulpecula", "Vul"),
]

def boundary_filenames(abbr: str) -> list[str]:
    return ["ser1.txt", "ser2.txt"] if abbr == "Ser" else [abbr.lower() + ".txt"]

def fetch_boundary(filename: str, snapshot_dir: Path) -> str:
    path = snapshot_dir / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing IAU constellation-boundary snapshot: {path}. Refresh the repository reference-data snapshot explicitly; normal builds do not fetch reference data from the web.")
    return path.read_text(encoding="utf-8")

def parse_boundary(text: str) -> list[tuple[float, float]]:
    points=[]
    for raw in text.splitlines():
        if not raw.strip(): continue
        ra_field, dec_field, _ = raw.split("|")
        hh, mm, ss = ra_field.split()
        points.append((15.0*(float(hh)+float(mm)/60.0+float(ss)/3600.0), float(dec_field)))
    if len(points)<3: raise ValueError("Boundary has fewer than three vertices")
    return points

def unwrap_ra(points):
    out=[points[0]]; previous=points[0][0]
    for ra,dec in points[1:]:
        while ra-previous>180: ra-=360
        while ra-previous<-180: ra+=360
        out.append((ra,dec)); previous=ra
    return out

def point_in_polygon(x,y,poly):
    inside=False; j=len(poly)-1
    for i in range(len(poly)):
        xi,yi=poly[i]; xj,yj=poly[j]
        if (yi>y)!=(yj>y):
            if x < (xj-xi)*(y-yi)/(yj-yi)+xi: inside=not inside
        j=i
    return inside

def sampled_polygon_moments(poly,step_deg):
    poly=unwrap_ra(poly); min_ra=min(p[0] for p in poly); max_ra=max(p[0] for p in poly); min_dec=max(-90.0,min(p[1] for p in poly)); max_dec=min(90.0,max(p[1] for p in poly)); area=mx=my=mz=0.0; dec=min_dec+step_deg/2; d_ra=math.radians(step_deg); d_dec=math.radians(step_deg)
    while dec<max_dec:
        cos_dec=math.cos(math.radians(dec)); cell=d_ra*d_dec*cos_dec; ra=min_ra+step_deg/2
        while ra<max_ra:
            if point_in_polygon(ra,dec,poly):
                r=math.radians(ra%360); d=math.radians(dec); area+=cell; mx+=cell*math.cos(d)*math.cos(r); my+=cell*math.cos(d)*math.sin(r); mz+=cell*math.sin(d)
            ra+=step_deg
        dec+=step_deg
    return area,mx,my,mz

def centroid_for(abbr,snapshot_dir,step_deg):
    area=mx=my=mz=0.0
    for filename in boundary_filenames(abbr):
        a,x,y,z=sampled_polygon_moments(parse_boundary(fetch_boundary(filename,snapshot_dir)),step_deg); area+=a; mx+=x; my+=y; mz+=z
    if area<=0: raise RuntimeError(f"No sampled area for {abbr}")
    return (math.degrees(math.atan2(my,mx))%360)/15.0, math.degrees(math.atan2(mz,math.hypot(mx,my))), area*(180/math.pi)**2

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("output",type=Path,nargs="?",default=Path("constellation-observance-2026.csv")); parser.add_argument("--cache-dir",dest="snapshot_dir",type=Path,default=SNAPSHOT_DIR,help="Compatibility name: repository snapshot directory; no network fetching occurs"); parser.add_argument("--step-deg",type=float,default=DEFAULT_STEP_DEG); args=parser.parse_args()
    if len(CONSTELLATIONS)!=88 or len({a for _,a in CONSTELLATIONS})!=88: raise SystemExit("Constellation table must contain exactly 88 unique IAU abbreviations")
    rows=[]
    for name,abbr in CONSTELLATIONS:
        ra_h,dec_deg,area_sq_deg=centroid_for(abbr,args.snapshot_dir,args.step_deg); instant,date=best_visibility(ra_h); rows.append({"name":name,"abbr":abbr,"centroid_ra_h":f"{ra_h:.6f}","centroid_dec_deg":f"{dec_deg:.6f}","sampled_area_sq_deg":f"{area_sq_deg:.3f}","centroid_step_deg":f"{args.step_deg:.3f}","best_instant_utc":instant.strftime("%Y-%m-%d %H:%M"),"best_date":date.isoformat(),"iso":iso_date(date)})
    with args.output.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} constellation Nights of Observance to {args.output}")
if __name__=="__main__": main()
