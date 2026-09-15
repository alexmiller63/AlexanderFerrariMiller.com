#!/usr/bin/env python3
"""Re-render the Enif finder with the official Pegasus boundary and a tight frame."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import render_stellar_finders as r

PEG_BOUNDARY_J2000 = [
(321.5834955,2.539374),(321.5011200,13.039057),(318.2444595,13.013195),(318.2502030,12.346552),(317.2483335,12.338258),(317.1787620,20.004634),(320.1883890,20.029074),(320.1516780,24.028930),(322.6619610,24.048204),(322.6200930,28.548047),(327.3952185,28.581788),(327.3199935,36.581538),(331.3504695,36.606899),(331.3595505,35.606926),(343.7064795,35.665603),(343.7091450,35.165608),(354.0441585,35.191302),(354.0491415,32.774639),(357.8280885,32.778500),(357.8287455,32.028500),(1.6069590,32.029361),(1.6061985,28.696028),(2.6127735,28.695750),(2.6099490,22.695751),(3.7405770,22.695184),(3.7340490,13.195186),(1.6031565,13.196028),(1.6027140,10.696028),(359.0971620,10.695789),(359.0980875,8.195789),(342.8214075,8.162161),(342.8422005,2.662200),(331.5872715,2.607601),(331.5887550,2.357605),(326.5870110,2.325684),(326.5853010,2.575678),(326.5801665,3.325661),(323.5786740,3.304384),(323.5841970,2.554404),(322.5838425,2.546972)]
HIGHLIGHT_YELLOW="#ffd84d"

def draw_boundary_tight(ax,con,center):
    pts=r.boundary_projected(con,center)
    if len(pts)>=2:
        closed=pts+[pts[0]]
        ax.plot([p[0] for p in closed],[p[1] for p in closed],lw=1.6,color=r.BOUNDARY,alpha=.9,linestyle=(0,(4,3)),zorder=1)
    if con=="Peg" and pts:
        xs=[p[0] for p in pts];ys=[p[1] for p in pts]
        padx=max(1.0,(max(xs)-min(xs))*.04);pady=max(1.0,(max(ys)-min(ys))*.04)
        ax.set_xlim(max(xs)+padx,min(xs)-padx);ax.set_ylim(min(ys)-pady,max(ys)+pady)

def center_refs_without_label_only_paths(spec):
    refs={spec["target"]}
    for path in spec.get("figure_paths",[]):
        if len(path)>=2:refs.update(path)
    return refs

def draw_enif_m15_objects(ax,spec,idx,center):
    """Highlight Enif and M15 with yellow rings; no guide arrows."""
    for d in spec.get("deep_sky_objects",[]):
        xy=r.project(float(d["ra_deg"]),float(d["dec_deg"]),*center)
        if not xy:continue
        ax.scatter([xy[0]],[xy[1]],s=180,facecolors="none",edgecolors=HIGHLIGHT_YELLOW,linewidths=2.6,zorder=8)
        label=" · ".join(x for x in (d.get("name",""),d.get("type","")) if x)
        # Put the complete M15 label to the left.  Its right edge sits one
        # character-width beyond the cluster ring, leaving room for the
        # word "cluster" to shift left by its full width plus one character.
        ax.annotate(label,xy,xytext=(-18,10),textcoords="offset points",ha="right",va="bottom",fontsize=9,color=r.TEXT,bbox=dict(facecolor=r.NIGHT,edgecolor="none",pad=.8),zorder=9)
        ref=d.get("from_ref")
        if ref and ref in idx:
            s=idx[ref];fxy=r.project(s.ra_deg,s.dec_deg,*center)
            if fxy:
                ax.scatter([fxy[0]],[fxy[1]],s=180,facecolors="none",edgecolors=HIGHLIGHT_YELLOW,linewidths=2.6,zorder=8)
        if d.get("distance_label") and ref and ref in idx:
            s=idx[ref];fxy=r.project(s.ra_deg,s.dec_deg,*center)
            if fxy:
                mx=(xy[0]+fxy[0])/2;my=(xy[1]+fxy[1])/2
                ax.annotate(d["distance_label"],(mx,my),xytext=(0,8),textcoords="offset points",ha="center",va="bottom",fontsize=8,color=HIGHLIGHT_YELLOW,bbox=dict(facecolor=r.NIGHT,edgecolor="none",pad=.5),zorder=9)

def add_axes_frame(svg_path:Path):
    text=svg_path.read_text(encoding="utf-8");needle='style="fill: #071423"'
    first=text.find(needle);second=text.find(needle,first+len(needle))
    if second<0:raise RuntimeError("Could not locate axes background in Enif SVG")
    replacement='style="fill: #071423; stroke: #c4ccd8; stroke-width: 0.9"'
    text=text[:second]+text[second:].replace(needle,replacement,1)
    svg_path.write_text(text,encoding="utf-8")

def make_great_square_green(svg_path:Path):
    text=svg_path.read_text(encoding="utf-8");marker="Great Square of Pegasus";pos=text.find(marker)
    if pos<0:raise RuntimeError("Great Square label not found in Enif SVG")
    before=text[:pos];blue="#5c8fe8";green="#59c86d";pathpos=before.rfind(blue)
    if pathpos<0:raise RuntimeError("Great Square path color not found")
    before=before[:pathpos]+before[pathpos:].replace(blue,green,1);after=text[pos:].replace(blue,green,1)
    svg_path.write_text(before+after,encoding="utf-8")

def main():
    p=argparse.ArgumentParser();p.add_argument("hyg_catalog",type=Path);p.add_argument("--config",type=Path,default=Path("constellation-figures.json"));p.add_argument("--out-dir",type=Path,default=Path("observer-views/W41"));a=p.parse_args()
    specs=json.loads(a.config.read_text(encoding="utf-8"));stars=r.load_hyg(a.hyg_catalog);spec=specs["Pegasus"]
    spec["chart_title"]="Enif M15 Finder"
    spec["figure_paths"]=list(spec.get("figure_paths",[]))+[["Alp And"],["Gam Peg"]]
    r.IAU_BOUNDARIES_J2000["Peg"]=PEG_BOUNDARY_J2000;r.draw_boundary=draw_boundary_tight;r.center_refs=center_refs_without_label_only_paths;r.draw_deep_sky_objects=draw_enif_m15_objects
    outputs=r.render_figure("Pegasus",spec,stars,a.out_dir);enif=next(path for path in outputs if path.name=="enif-finder.svg")
    make_great_square_green(enif);add_axes_frame(enif);print(f"bounded {enif}")

if __name__=="__main__":main()
