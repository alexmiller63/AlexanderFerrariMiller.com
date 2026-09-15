#!/usr/bin/env python3
"""Measure Mellinger brightness at bright and faint Milky Way validation anchors.

Vieira ``ol1`` remains authoritative for ``milky_way.inside``. Mellinger is used
only to measure optical prominence inside that boundary. Absolute central image
intensity is the primary metric; local contrast is retained as a diagnostic.
"""
from __future__ import annotations
import argparse, json, math, statistics, struct, urllib.parse, urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / ".cache" / "source-data" / "milky-way-mellinger-validation.json"
SKYVIEW = "https://skyview.gsfc.nasa.gov/cgi-bin/images"
SURVEYS = ("mell-r", "mell-g", "mell-b")

# Published bright-region anchors used as positive validation examples.
BRIGHT_ANCHORS = (
    {"name":"Carina","ra_h":10.75,"dec_deg":-60.0,"expected":"bright"},
    {"name":"Norma","ra_h":16.30,"dec_deg":-53.0,"expected":"bright"},
    {"name":"Sagittarius","ra_h":18.00,"dec_deg":-29.0,"expected":"bright"},
    {"name":"Scutum","ra_h":18.75,"dec_deg":-7.0,"expected":"bright"},
    {"name":"Cygnus","ra_h":19.50,"dec_deg":30.0,"expected":"bright"},
)

# Faint controls lie on the Galactic plane (b=0) in the published minimum-
# surface-brightness interval l=155..180 deg. Equatorial coordinates are J2000.
FAINT_CONTROLS = (
    {"name":"Faint control l=155","ra_h":4.454155,"dec_deg":48.954799,"gal_l_deg":155.0,"gal_b_deg":0.0,"expected":"faint"},
    {"name":"Faint control l=165","ra_h":5.070399,"dec_deg":41.351904,"gal_l_deg":165.0,"gal_b_deg":0.0,"expected":"faint"},
    {"name":"Faint control l=175","ra_h":5.553013,"dec_deg":33.168128,"gal_l_deg":175.0,"gal_b_deg":0.0,"expected":"faint"},
    {"name":"Galactic anticenter","ra_h":5.760333,"dec_deg":28.936174,"gal_l_deg":180.0,"gal_b_deg":0.0,"expected":"faint"},
)
ANCHORS = BRIGHT_ANCHORS + FAINT_CONTROLS

def parse_args():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    p.add_argument("--size",type=float,default=12.0)
    p.add_argument("--pixels",type=int,default=121)
    p.add_argument("--offline",action="store_true")
    return p.parse_args()

def fits_values(payload: bytes):
    cards=[]; end=None
    for offset in range(0,len(payload),80):
        card=payload[offset:offset+80].decode("ascii",errors="replace"); cards.append(card)
        if card.startswith("END"): end=offset+80; break
    if end is None: raise ValueError("FITS END card not found")
    header={}
    for card in cards:
        if len(card)>=10 and card[8:10]=="= ": header[card[:8].strip()]=card[10:80].split("/",1)[0].strip()
    bitpix=int(header["BITPIX"]); nx=int(header["NAXIS1"]); ny=int(header["NAXIS2"])
    bscale=float(header.get("BSCALE","1")); bzero=float(header.get("BZERO","0"))
    data_start=((end+2879)//2880)*2880; count=nx*ny
    formats={8:">B",16:">h",32:">i",-32:">f",-64:">d"}
    if bitpix not in formats: raise ValueError(f"Unsupported BITPIX={bitpix}")
    fmt=formats[bitpix]; step=abs(bitpix)//8
    values=[struct.unpack(fmt,payload[data_start+i*step:data_start+(i+1)*step])[0]*bscale+bzero for i in range(count)]
    return nx,ny,values

def request_channel(anchor: dict[str,Any],survey:str,size:float,pixels:int):
    params={"Survey":survey,"Position":f"{anchor['ra_h']*15.0},{anchor['dec_deg']}","Coordinates":"J2000","Projection":"Tan","Size":str(size),"Pixels":f"{pixels},{pixels}","Scaling":"Linear","Return":"FITS"}
    with urllib.request.urlopen(SKYVIEW+"?"+urllib.parse.urlencode(params),timeout=120) as response:
        return fits_values(response.read())

def measure(nx:int,ny:int,values:list[float]):
    cx,cy=(nx-1)/2.0,(ny-1)/2.0; scale=min(nx,ny)/2.0; center=[]; surround=[]
    for y in range(ny):
        for x in range(nx):
            v=values[y*nx+x]
            if not math.isfinite(v): continue
            r=math.hypot(x-cx,y-cy)/scale
            if r<=0.25: center.append(v)
            elif 0.55<=r<=0.90: surround.append(v)
    if not center or not surround: raise ValueError("insufficient finite FITS pixels")
    c=statistics.median(center); b=statistics.median(surround)
    return {"center_median":c,"surround_median":b,"local_contrast":(c-b)/b if b else float("nan")}

def analyze(args):
    result={"schema_version":3,"purpose":"bright/faint validation for named Milky Way regions","boundary_model":"Vieira ol1 remains authoritative; this file does not redefine it","source":"Axel Mellinger optical survey via NASA SkyView","primary_metric":"mean_rgb_center_median","threshold":None,"anchors":[]}
    for anchor in ANCHORS:
        entry=dict(anchor); entry["channels"]={}; brightnesses=[]; contrasts=[]
        for survey in SURVEYS:
            nx,ny,values=request_channel(anchor,survey,args.size,args.pixels); m=measure(nx,ny,values); entry["channels"][survey]=m
            if math.isfinite(m["center_median"]): brightnesses.append(m["center_median"])
            if math.isfinite(m["local_contrast"]): contrasts.append(m["local_contrast"])
        entry["mean_rgb_center_median"]=statistics.mean(brightnesses)
        entry["mean_rgb_local_contrast"]=statistics.mean(contrasts)
        result["anchors"].append(entry)
        print(f"{entry['name']} [{entry['expected']}]: mean RGB brightness={entry['mean_rgb_center_median']:.6f}; local contrast={entry['mean_rgb_local_contrast']:.6f}")
    bright=[e["mean_rgb_center_median"] for e in result["anchors"] if e["expected"]=="bright"]
    faint=[e["mean_rgb_center_median"] for e in result["anchors"] if e["expected"]=="faint"]
    result["validation"]={"bright_min":min(bright),"faint_max":max(faint),"separated":max(faint)<min(bright),"candidate_midpoint_threshold":(max(faint)+min(bright))/2 if max(faint)<min(bright) else None}
    print("Validation:",json.dumps(result["validation"],sort_keys=True))
    return result

def main():
    args=parse_args()
    if args.offline:
        print(args.output.read_text(encoding="utf-8")); return 0
    result=analyze(args); args.output.parent.mkdir(parents=True,exist_ok=True); args.output.write_text(json.dumps(result,indent=2,allow_nan=False)+"\n",encoding="utf-8"); print(f"Wrote {args.output}"); return 0
if __name__=="__main__": raise SystemExit(main())
