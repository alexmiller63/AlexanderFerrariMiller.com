#!/usr/bin/env python3
"""Re-render Aquarius with a yellow target ring and no target arrow."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import render_stellar_finders as r

HIGHLIGHT_YELLOW="#ffd84d"

def draw_target_highlight(ax,spec,idx,center):
    """Draw only a yellow ring around the Aquarius target."""
    s=idx[spec["target"]]
    xy=r.project(s.ra_deg,s.dec_deg,*center)
    if xy:
        ax.scatter([xy[0]],[xy[1]],s=180,facecolors="none",edgecolors=HIGHLIGHT_YELLOW,linewidths=2.6,zorder=8)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("hyg_catalog",type=Path)
    p.add_argument("--config",type=Path,default=Path("constellation-figures.json"))
    p.add_argument("--out-dir",type=Path,default=Path("observer-views/W41"))
    a=p.parse_args()
    specs=json.loads(a.config.read_text(encoding="utf-8"))
    stars=r.load_hyg(a.hyg_catalog)
    spec=specs["Aquarius"]
    # A truthy DSO list suppresses the standard target arrow.  The custom
    # drawer below replaces it with the same yellow ring used by Enif/M15.
    spec["deep_sky_objects"]=[{"from_ref":spec["target"]}]
    r.draw_deep_sky_objects=draw_target_highlight
    for out in r.render_figure("Aquarius",spec,stars,a.out_dir):
        print(f"highlighted {out}")

if __name__=="__main__":main()
