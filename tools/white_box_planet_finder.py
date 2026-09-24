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
    samples = []
    limit = RI-LABEL_RIM_CLEARANCE
    for x, y in raw:
        box = Box(x, y, w, h)
        hit = next((o for o in reserved if boxes_overlap(box, o, LABEL_COLLISION_PADDING)), None)
        if hit is not None:
            counts["reserved"] += 1; reason = "reserved"
        else:
            corners=((box.left,box.top),(box.right,box.top),(box.left,box.bottom),(box.right,box.bottom))
            if max(math.hypot(px-CX,py-CY) for px,py in corners) >= limit:
                counts["rim"] += 1; reason = "rim"
            else:
                path = route(anchor, (box.x,box.y), reserved, allow_initial_escape_count=immutable_count, prefix_cache={})
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
    for i,(x,y,reason) in enumerate(samples,1): print(f"  SUN-FIRST sample#{i} center=({x:.1f},{y:.1f}) first_gate={reason}", flush=True)
    if reconciled != counts["raw"]: raise AssertionError(f"Sun-first audit does not reconcile: {counts} reconciled={reconciled}")


def rim_geometry_audit(mode, bodies, scale=2.0, sample_limit=12):
    """Expose exactly how the immutable label-rim test treats raw proposals."""
    limit=RI-LABEL_RIM_CLEARANCE
    reserved=reserved_boxes(mode)
    print(f"WHITE BOX RIM GEOMETRY AUDIT RI={RI} clearance={LABEL_RIM_CLEARANCE} limit={limit}",flush=True)
    for _,name,lon in bodies:
        w,h=label_size(mode,name); shown=0; rim_rejects=0; inside=0
        print(f"RIM-AUDIT body={name} lon={lon:.3f} label=({w:.1f}x{h:.1f})",flush=True)
        for x,y in candidate_positions(lon,scale):
            from planet_finder_geometry import Box, LABEL_COLLISION_PADDING
            box=Box(x,y,w,h)
            if any(boxes_overlap(box,o,LABEL_COLLISION_PADDING) for o in reserved): continue
            corners=((box.left,box.top),(box.right,box.top),(box.left,box.bottom),(box.right,box.bottom))
            radii=tuple(math.hypot(px-CX,py-CY) for px,py in corners)
            center_radius=math.hypot(x-CX,y-CY); worst=max(radii); miss=worst-limit
            if miss >= 0:
                rim_rejects+=1
                if shown<sample_limit:
                    shown+=1; rs=",".join(f"{r:.2f}" for r in radii)
                    print(f"  reject center=({x:.1f},{y:.1f}) center_r={center_radius:.2f} corners=[{rs}] worst={worst:.2f} limit={limit:.2f} miss={miss:+.2f}",flush=True)
            else:
                inside+=1
                if shown<sample_limit:
                    shown+=1; rs=",".join(f"{r:.2f}" for r in radii)
                    print(f"  survive center=({x:.1f},{y:.1f}) center_r={center_radius:.2f} corners=[{rs}] worst={worst:.2f} limit={limit:.2f} margin={-miss:.2f}",flush=True)
        print(f"  RIM-SUMMARY body={name} nonreserved_inside={inside} rim_rejected={rim_rejects}",flush=True)


def candidate_generation_audit(mode, bodies, scale=2.0):
    reserved=reserved_boxes(mode); print("WHITE BOX CANDIDATE GENERATION AUDIT", flush=True)
    for _,name,lon in bodies:
        w,h=label_size(mode,name); raw=list(candidate_positions(lon,scale)); diag={}
        legal=list(legal_candidate_positions(lon,w,h,reserved,scale,diagnostic=diag)); audits=diag.get("immutable_candidate_audit",[])
        rejected_reserved=sum(1 for a in audits if a[2]=="reserved"); rejected_rim=sum(1 for a in audits if a[2]=="rim"); reasons={}
        for _,_,reason,detail in audits:
            key=reason if reason!="reserved" else f"reserved:{detail}"; reasons[key]=reasons.get(key,0)+1
        print(f"CANDIDATE-AUDIT body={name} lon={lon:.3f} raw={len(raw)} legal={len(legal)} reserved={rejected_reserved} rim={rejected_rim}",flush=True)
        if not legal:
            print(f"  ZERO-LEGAL reasons={reasons}",flush=True)
            for i,(x,y,reason,detail) in enumerate(audits[:20],1): print(f"    reject#{i} center=({x:.1f},{y:.1f}) reason={reason} detail={detail}",flush=True)


def first_level_forward_audit(mode,bodies,displacement_scale=2.0,first_limit=12):
    reserved=reserved_boxes(mode); immutable_count=len(reserved); print("WHITE BOX FORWARD AUDIT: first-level pruning",flush=True)
    print(f"WHITE BOX ROUTING: initial escape permitted only from an immutable obstacle containing the body anchor; immutable_count={immutable_count}",flush=True)
    for _,first_name,first_lon in bodies:
        fw,fh=label_size(mode,first_name); anchor=xy(first_lon,RI-5); tested=0; print(f"FORWARD-AUDIT FIRST body={first_name}",flush=True)
        for _,_,first_box in legal_candidate_positions(first_lon,fw,fh,reserved,displacement_scale):
            first_path=route(anchor,(first_box.x,first_box.y),reserved,allow_initial_escape_count=immutable_count,prefix_cache={})
            if first_path is None or leader_hits_zodiac_rim(first_path): continue
            tested+=1; dead=None; counts=None
            for _,future_name,future_lon in bodies:
                if future_name==first_name: continue
                w,h=label_size(mode,future_name); a=xy(future_lon,RI-5); c={"raw":0,"overlap":0,"route":0,"rim":0,"leader":0}; witness=False
                for _,_,box in legal_candidate_positions(future_lon,w,h,reserved,displacement_scale):
                    c["raw"]+=1
                    if boxes_overlap(box,first_box,14): c["overlap"]+=1; continue
                    path=route(a,(box.x,box.y),[*reserved,first_box],allow_initial_escape_count=immutable_count,prefix_cache={})
                    if path is None: c["route"]+=1; continue
                    if leader_hits_zodiac_rim(path): c["rim"]+=1; continue
                    if leaders_too_close(path,[first_path]): c["leader"]+=1; continue
                    witness=True; break
                if not witness: dead=future_name; counts=c; break
            if dead is None: print(f"  first-candidate={tested}: SURVIVES center=({first_box.x:.1f},{first_box.y:.1f})",flush=True); break
            print(f"  first-candidate={tested}: PRUNED by={dead} center=({first_box.x:.1f},{first_box.y:.1f}) raw={counts['raw']} overlap={counts['overlap']} route={counts['route']} rim={counts['rim']} leader={counts['leader']}",flush=True)
            if tested>=first_limit: break
        if tested==0: print("  NO LEGAL FIRST PLACEMENT",flush=True)


def main():
    p=argparse.ArgumentParser(); p.add_argument("--mode",choices=[m.value for m in FinderMode],default="greek"); p.add_argument("--center",type=float,default=15.0); p.add_argument("--span",type=float,default=6.0); p.add_argument("--candidates",type=int,default=1); p.add_argument("--body-cap",type=int,default=200); p.add_argument("--seconds",type=float,default=180.0); p.add_argument("--diagnostic",type=int,default=3); a=p.parse_args()
    os.environ["PLANET_FINDER_DIAGNOSTIC_LEVEL"]=str(a.diagnostic); os.environ["PLANET_FINDER_MAX_NODE_CANDIDATES"]=str(a.body_cap); os.environ["PLANET_FINDER_MAX_SECONDS"]=str(a.seconds)
    mode=FinderMode(a.mode); bodies=crowded_bodies(a.center,a.span)
    print("WHITE BOX: all bodies deliberately crowded into one zodiac sign"); print(f"mode={a.mode} center={a.center:g} span={a.span:g} candidates={a.candidates}")
    for symbol,name,lon in bodies: print(f"  {name:8s} {symbol} {lon:8.3f}°")
    isolated_sun_audit(mode,bodies)
    rim_geometry_audit(mode,bodies); candidate_generation_audit(mode,bodies); first_level_forward_audit(mode,bodies)
    budget=new_search_budget(); started=time.monotonic()
    try: result=layout(mode,bodies,target_solutions=a.candidates,budget=budget,context_label="WHITE-BOX-CROWDED")
    except Exception as exc: print(f"WHITE BOX RESULT: FAILURE after {time.monotonic()-started:.3f}s: {type(exc).__name__}: {exc}"); raise
    print(f"WHITE BOX RESULT: SUCCESS after {time.monotonic()-started:.3f}s; placements={len(result)}")
if __name__=="__main__": main()
