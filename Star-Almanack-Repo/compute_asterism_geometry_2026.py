#!/usr/bin/env python3
"""Compute Star Almanack geometry, visibility, and median member magnitude.

The resolved member catalog is the single source of truth for the stellar
coordinates and magnitudes used here.  This module derives asterism-level
properties from those member rows; it does not introduce another stellar-data
source.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from dataclasses import dataclass
from pathlib import Path

from compute_bayer_visibility_2026 import best_visibility, iso_date

EPS = 1.0e-12


@dataclass(frozen=True)
class SkyPoint:
    name: str
    ra_h: float
    dec_deg: float
    mag: float


def dot(a, b): return a[0]*b[0] + a[1]*b[1] + a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def add(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def scale(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def norm(a): return math.sqrt(dot(a, a))

def unit(a):
    n = norm(a)
    if n <= EPS: raise ValueError("Cannot normalize a zero vector")
    return scale(a, 1.0/n)

def to_vector(ra_h, dec_deg):
    ra, dec = math.radians(15*ra_h), math.radians(dec_deg)
    c = math.cos(dec)
    return (c*math.cos(ra), c*math.sin(ra), math.sin(dec))

def to_radec(v):
    v = unit(v)
    return (math.degrees(math.atan2(v[1], v[0])) % 360)/15, math.degrees(math.asin(max(-1, min(1, v[2]))))

def great_circle_midpoint(a, b):
    if dot(a,b) <= -1 + 1e-12: raise ValueError("Antipodal points have no unique minor-arc midpoint")
    return unit(add(a,b))

def tangent_basis(center):
    z=(0.,0.,1.); ref=z if abs(dot(center,z))<.95 else (1.,0.,0.)
    e1=unit(cross(ref,center)); return e1,unit(cross(center,e1))

def hemisphere_center(points):
    s=(0.,0.,0.)
    for p in points: s=add(s,p)
    c=unit(s)
    if min(dot(c,p) for p in points)<=EPS: raise ValueError("Member set is not contained in the selected open hemisphere")
    return c

def projected_hull_indices(points):
    center=hemisphere_center(points); e1,e2=tangent_basis(center)
    projected=sorted((dot(e1,p)/dot(center,p),dot(e2,p)/dot(center,p),i) for i,p in enumerate(points))
    unique=[]
    for item in projected:
        if not unique or abs(item[0]-unique[-1][0])>EPS or abs(item[1]-unique[-1][1])>EPS: unique.append(item)
    if len(unique)<3:return [p[2] for p in unique]
    def orient(o,a,b):return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    lower=[]
    for p in unique:
        while len(lower)>=2 and orient(lower[-2],lower[-1],p)<=EPS:lower.pop()
        lower.append(p)
    upper=[]
    for p in reversed(unique):
        while len(upper)>=2 and orient(upper[-2],upper[-1],p)<=EPS:upper.pop()
        upper.append(p)
    return [p[2] for p in lower[:-1]+upper[:-1]]

def triangle_area(a,b,c):return abs(2*math.atan2(dot(a,cross(b,c)),1+dot(a,b)+dot(b,c)+dot(c,a)))
def oriented_edge_moment(a,b):
    n=cross(a,b); nl=norm(n)
    if nl<=EPS:return (0.,0.,0.)
    return scale(n,math.atan2(nl,dot(a,b))/nl)
def triangle_first_moment(a,b,c):return scale(add(add(oriented_edge_moment(a,b),oriented_edge_moment(b,c)),oriented_edge_moment(c,a)),.5)

def polygon_geometry(points):
    if len(points)==1:return points[0],0.,[0],"single-member"
    if len(points)==2:return great_circle_midpoint(points[0],points[1]),0.,[0,1],"great-circle-midpoint"
    hull=projected_hull_indices(points)
    if len(hull)==1:return points[hull[0]],0.,hull,"degenerate-single"
    if len(hull)==2:return great_circle_midpoint(points[hull[0]],points[hull[1]]),0.,hull,"degenerate-great-circle-midpoint"
    vertices=[points[i] for i in hull]; interior=hemisphere_center(vertices)
    total_area=0.; total_moment=(0.,0.,0.)
    for i,a in enumerate(vertices):
        b=vertices[(i+1)%len(vertices)]
        if dot(interior,cross(a,b))<0:a,b=b,a
        total_area+=triangle_area(interior,a,b)
        moment=triangle_first_moment(interior,a,b)
        if dot(moment,interior)<0:moment=scale(moment,-1)
        total_moment=add(total_moment,moment)
    if total_area<=EPS or norm(total_moment)<=EPS:raise ValueError("Degenerate spherical polygon")
    return unit(total_moment),total_area,hull,"spherical-convex-hull-area-centroid"

def read_members(path):
    groups={}
    with path.open(newline="",encoding="utf-8") as handle:
        reader=csv.DictReader(handle)
        required={"asterism","member","ra_h","dec_deg","mag","magnitude_source","magnitude_source_id"}
        missing=required-set(reader.fieldnames or [])
        if missing:raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        for row in reader:
            if not row["magnitude_source"].strip() or not row["magnitude_source_id"].strip():
                raise ValueError(f"Incomplete magnitude provenance: {row['asterism']} / {row['member']}")
            groups.setdefault(row["asterism"],[]).append(SkyPoint(row["member"],float(row["ra_h"]),float(row["dec_deg"]),float(row["mag"])))
    return groups

def main():
    parser=argparse.ArgumentParser(); parser.add_argument("members_csv",type=Path); parser.add_argument("output",type=Path,nargs="?",default=Path("asterism-geometry-2026.csv")); args=parser.parse_args()
    groups=read_members(args.members_csv); rows=[]
    for name,members in groups.items():
        center,area_sr,hull,method=polygon_geometry([to_vector(p.ra_h,p.dec_deg) for p in members])
        ra_h,dec_deg=to_radec(center); instant,date=best_visibility(ra_h)
        median_mag=statistics.median(p.mag for p in members)
        rows.append({"asterism":name,"member_count":len(members),"median_mag":f"{median_mag:.2f}","magnitude_method":"median-member-magnitude","hull_member_count":len(hull),"hull_members":"; ".join(members[i].name for i in hull),"geometry_method":method,"centroid_ra_h":f"{ra_h:.8f}","centroid_dec_deg":f"{dec_deg:.8f}","area_sr":f"{area_sr:.12f}","area_sq_deg":f"{area_sr*(180/math.pi)**2:.6f}","best_instant_utc":instant.strftime("%Y-%m-%d %H:%M"),"best_date":date.isoformat(),"iso":iso_date(date)})
        print(f"{name:32s} mag {median_mag:5.2f} RA {ra_h:10.7f}h Dec {dec_deg:+10.6f} -> {date.isoformat()} ({method})")
    if not rows:raise SystemExit("No asterism member coordinates found")
    with args.output.open("w",newline="",encoding="utf-8") as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} asterism geometry rows to {args.output}")
if __name__=="__main__":main()
