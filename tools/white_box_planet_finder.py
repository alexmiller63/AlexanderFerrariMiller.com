#!/usr/bin/env python3
"""Deterministic white-box stress harness for Planet Finder search."""
from __future__ import annotations
import argparse, math, os, time
from planet_finder_geometry import (
    BODY_SYMBOLS, CANONICAL, CX, CY, FinderMode, LABEL_RIM_CLEARANCE, RI,
    candidate_positions, boxes_overlap, label_size, legal_candidate_positions,
    leader_hits_zodiac_rim, leaders_too_close, reserved_boxes, route, xy,
)
from planet_finder_search import layout, new_search_budget


def crowded_bodies(center=15.0, span=6.0):
    if not 0.0 <= center < 360.0: raise ValueError("center must be in [0, 360)")
    if not 0.0 <= span < 30.0: raise ValueError("span must be in [0, 30)")
    n=len(CANONICAL); start=center-span/2; step=span/(n-1) if n>1 else 0
    return [(BODY_SYMBOLS[name.lower()], name, (start+i*step)%360.0) for i,name in enumerate(CANONICAL)]


def reserved_name(index):
    if index == 0: return "center-title"
    if index == 1: return "center-subtitle"
    if index == 2: return "center-footer"
    signs=("Aries","Taurus","Gemini","Cancer","Leo","Virgo","Libra","Scorpio","Sagittarius","Capricorn","Aquarius","Pisces")
    j=index-3
    return f"zodiac:{signs[j]}" if 0 <= j < len(signs) else f"reserved#{index}"


def named_counts(d):
    out={}
    for key,value in d.items():
        if key.startswith("obstacle_"):
            key=reserved_name(int(key.split("_",1)[1]))
        out[key]=out.get(key,0)+value
    return out


def isolated_sun_audit(mode, bodies, scale=2.0, sample_limit=12):
    """Audit Sun as move 1 only: no DFS, no other bodies, no caps or forward checking."""
    sun = next((b for b in bodies if b[1] == "Sun"), None)
    if sun is None:
        print("SUN-FIRST AUDIT: no Sun in body list", flush=True); return
    _, name, lon = sun
    from planet_finder_geometry import Box, LABEL_COLLISION_PADDING
    reserved = reserved_boxes(mode); immutable_count = len(reserved)
    w, h = label_size(mode, name); anchor = xy(lon, RI-5)
    raw = list(candidate_positions(lon, scale))
    counts = {"raw": len(raw), "reserved": 0, "rim": 0, "route": 0, "leader_rim": 0, "accepted": 0}
    reserved_hits = {}; route_diag={"elbows": {}}
    samples = []
    limit = RI-LABEL_RIM_CLEARANCE
    for x, y in raw:
        box = Box(x, y, w, h)
        hit_index = next((i for i,o in enumerate(reserved) if boxes_overlap(box, o, LABEL_COLLISION_PADDING)), None)
        if hit_index is not None:
            counts["reserved"] += 1; reason = "reserved"
            key=reserved_name(hit_index); reserved_hits[key]=reserved_hits.get(key,0)+1
        else:
            corners=((box.left,box.top),(box.right,box.top),(box.left,box.bottom),(box.right,box.bottom))
            if max(math.hypot(px-CX,py-CY) for px,py in corners) >= limit:
                counts["rim"] += 1; reason = "rim"
            else:
                path = route(anchor, (box.x,box.y), reserved, diagnostic=route_diag, allow_initial_escape_count=immutable_count, prefix_cache={})
                if path is None:
                    counts["route"] += 1; reason = "route"
                elif leader_hits_zodiac_rim(path):
                    counts["leader_rim"] += 1; reason = "leader_rim"
                else:
                    counts["accepted"] += 1; reason = "accepted"
        if len(samples) < sample_limit:
            samples.append((x,y,reason))
    reconciled = counts["reserved"]+counts["rim"]+counts["route"]+counts["leader_rim"]+counts["accepted"]
    print("WHITE BOX SUN-FIRST ISOLATED AUDIT", flush=True)
    print(f"SUN-FIRST mode={mode.value} lon={lon:.3f} anchor=({anchor[0]:.1f},{anchor[1]:.1f}) label=({w:.1f}x{h:.1f}) immutable={immutable_count}", flush=True)
    print("SUN-FIRST COUNTS " + " ".join(f"{k}={v}" for k,v in counts.items()) + f" reconciled={reconciled}", flush=True)
    print("SUN-FIRST RESERVED BREAKDOWN " + (" ".join(f"{k}={v}" for k,v in sorted(reserved_hits.items(), key=lambda kv:(-kv[1],kv[0]))) or "none"), flush=True)
    print(f"SUN-ROUTE SUMMARY straight_blocked={route_diag.get('straight_blocked',0)} anchor_blocked={route_diag.get('anchor_blocked',0)} route_failed={route_diag.get('route_failed',0)}",flush=True)
    straight=named_counts(route_diag.get("straight_blockers",{}))
    print("SUN-ROUTE STRAIGHT BLOCKERS " + (" ".join(f"{k}={v}" for k,v in sorted(straight.items(),key=lambda kv:(-kv[1],kv[0]))) or "none"),flush=True)
    for radius,legs in route_diag.get("elbows",{}).items():
        first=named_counts(legs.get("first",{})); second=named_counts(legs.get("second",{}))
        print(f"SUN-ROUTE ELBOW r={radius} first="+(" ".join(f"{k}:{v}" for k,v in sorted(first.items(),key=lambda kv:(-kv[1],kv[0]))) or "none")+" second="+(" ".join(f"{k}:{v}" for k,v in sorted(second.items(),key=lambda kv:(-kv[1],kv[0]))) or "none"),flush=True)
    for key,value in sorted(route_diag.items()):
        if key not in {"elbows","straight_blockers","straight_blocked","anchor_blocked","route_failed"}:
            print(f"SUN-ROUTE EXTRA {key}={value}",flush=True)
    for i,(x,y,reason) in enumerate(samples,1): print(f"  SUN-FIRST sample#{i} center=({x:.1f},{y:.1f}) first_gate={reason}", flush=True)
    if reconciled != counts["raw"]: raise AssertionError(f"Sun-first audit does not reconcile: {counts} reconciled={reconciled}")


def rim_geometry_audit(mode, bodies, scale=2.0, sample_limit=12):
    limit=RI-LABEL_RIM_CLEARANCE; reserved=reserved_boxes(mode)
    print(f"WHITE BOX RIM GEOMETRY AUDIT RI={RI} clearance={LABEL_RIM_CLEARANCE} limit={limit}",flush=True)
    for _,name,lon in bodies:
        w,h=label_size(mode,name); shown=0; rim_rejects=0; inside=0
        print(f"RIM-AUDIT body={name} lon={lon:.3f} label=({w:.1f}x{h:.1f})",flush=True)
        for x,y in candidate_positions(lon,scale):
            from planet_finder_geometry import Box, LABEL_COLLISION_PADDING
            box=Box(x,y,w,h)
            if any(boxes_overlap(box,o,LABEL_COLLISION_PADDING) for o in reserved): continue
            corners=((box.left,box.top),(box.right,box.top),(box.left,box.bottom),(box.right,box.bottom)); radii=tuple(math.hypot(px-CX,py-CY) for px,py in corners)
            center_radius=math.hypot(x-CX,y-CY); worst=max(radii); miss=worst-limit
            if miss >= 0: rim_rejects+=1; state="reject"
            else: inside+=1; state="survive"
            if shown<sample_limit:
                shown+=1; rs=",".join(f"{r:.2f}" for r in radii); tail=f"miss={miss:+.2f}" if miss>=0 else f"margin={-miss:.2f}"
                print(f"  {state} center=({x:.1f},{y:.1f}) center_r={center_radius:.2f} corners=[{rs}] worst={worst:.2f} limit={limit:.2f} {tail}",flush=True)
        print(f"  RIM-SUMMARY body={name} nonreserved_inside={inside} rim_rejected={rim_rejects}",flush=True)


def candidate_generation_audit(mode, bodies, scale=2.0):
    reserved=reserved_boxes(mode); print("WHITE BOX CANDIDATE GENERATION AUDIT", flush=True)
    for _,name,lon in bodies:
        w,h=label_size(mode,name); raw=list(candidate_positions(lon,scale)); diag={}; legal=list(legal_candidate_positions(lon,w,h,reserved,scale,diagnostic=diag)); audits=diag.get("immutable_candidate_audit",[])
        rejected_reserved=sum(1 for a in audits if a[2]=="reserved"); rejected_rim=sum(1 for a in audits if a[2]=="rim")
        print(f"CANDIDATE-AUDIT body={name} lon={lon:.3f} raw={len(raw)} legal={len(legal)} reserved={rejected_reserved} rim={rejected_rim}",flush=True)


def first_level_forward_audit(mode,bodies,displacement_scale=2.0,first_limit=12):
    reserved=reserved_boxes(mode); immutable_count=len(reserved); print("WHITE BOX FORWARD AUDIT: first-level pruning",flush=True)
    for _,first_name,first_lon in bodies:
        fw,fh=label_size(mode,first_name); anchor=xy(first_lon,RI-5); tested=0; print(f"FORWARD-AUDIT FIRST body={first_name}",flush=True)
        for _,_,first_box in legal_candidate_positions(first_lon,fw,fh,reserved,displacement_scale):
            first_path=route(anchor,(first_box.x,first_box.y),reserved,allow_initial_escape_count=immutable_count,prefix_cache={})
            if first_path is None or leader_hits_zodiac_rim(first_path): continue
            tested+=1; print(f"  first-candidate={tested}: ROUTABLE center=({first_box.x:.1f},{first_box.y:.1f})",flush=True); break
        if tested==0: print("  NO ROUTABLE FIRST PLACEMENT",flush=True)


def main():
    p=argparse.ArgumentParser(); p.add_argument("--mode",choices=[m.value for m in FinderMode],default="greek"); p.add_argument("--center",type=float,default=15.0); p.add_argument("--span",type=float,default=6.0); p.add_argument("--candidates",type=int,default=1); p.add_argument("--body-cap",type=int,default=200); p.add_argument("--seconds",type=float,default=180.0); p.add_argument("--diagnostic",type=int,default=3); a=p.parse_args()
    os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"]=str(a.diagnostic); os.environ["PLANET_FINDER_MAX_NODE_CANDIDATES"]=str(a.body_cap); os.environ["PLANET_FINDER_MAX_SECONDS"]=str(a.seconds)
    mode=FinderMode(a.mode); bodies=crowded_bodies(a.center,a.span)
    print("WHITE BOX: all bodies deliberately crowded into one zodiac sign"); print(f"mode={a.mode} center={a.center:g} span={a.span:g} candidates={a.candidates}")
    for symbol,name,lon in bodies: print(f"  {name:8s} {symbol} {lon:8.3f}°")
    isolated_sun_audit(mode,bodies); rim_geometry_audit(mode,bodies); candidate_generation_audit(mode,bodies); first_level_forward_audit(mode,bodies)
    budget=new_search_budget(); started=time.monotonic()
    try: result=layout(mode,bodies,target_solutions=a.candidates,budget=budget,context_label="WHITE-BOX-CROWDED")
    except Exception as exc: print(f"WHITE BOX RESULT: FAILURE after {time.monotonic()-started:.3f}s: {type(exc).__name__}: {exc}"); raise
    print(f"WHITE BOX RESULT: SUCCESS after {time.monotonic()-started:.3f}s; placements={len(result)}")
if __name__=="__main__": main()
