#!/usr/bin/env python3
"""Shared astronomical rules for Star Almanack generators and audits."""
from __future__ import annotations
import datetime as dt
import math
OBLIQUITY_DEG=23.44
POLAR_LIMIT_DEG=90.0-OBLIQUITY_DEG

def julian_date(x:dt.datetime)->float:
    year,month=x.year,x.month; day=x.day+(x.hour+(x.minute+x.second/60.0)/60.0)/24.0
    if month<=2: year-=1; month+=12
    a=year//100; b=2-a+a//4
    return int(365.25*(year+4716))+int(30.6001*(month+1))+day+b-1524.5

def apparent_sun_ra_hours(x:dt.datetime)->float:
    jd=julian_date(x); t=(jd-2451545.0)/36525.0
    ml=(280.46646+t*(36000.76983+0.0003032*t))%360.0
    ma=math.radians((357.52911+t*(35999.05029-0.0001537*t))%360.0)
    c=((1.914602-t*(0.004817+0.000014*t))*math.sin(ma)+(0.019993-0.000101*t)*math.sin(2*ma)+0.000289*math.sin(3*ma))
    omega=math.radians(125.04-1934.136*t)
    lam=math.radians((ml+c-0.00569-0.00478*math.sin(omega))%360.0)
    sec=21.448-t*(46.8150+t*(0.00059-t*0.001813)); eps0=23.0+(26.0+sec/60.0)/60.0
    eps=math.radians(eps0+0.00256*math.cos(omega))
    return (math.degrees(math.atan2(math.cos(eps)*math.sin(lam),math.cos(lam)))%360.0)/15.0

def hour_distance(a:float,b:float)->float:return abs((a-b+12.0)%24.0-12.0)

def _best_time_for_solar_ra(target:float,start:dt.datetime,end:dt.datetime)->dt.datetime:
    best_t,best_d=start,float("inf"); x=start
    while x<=end:
        d=hour_distance(apparent_sun_ra_hours(x),target)
        if d<best_d: best_t,best_d=x,d
        x+=dt.timedelta(hours=6)
    x=max(start,best_t-dt.timedelta(hours=8)); hi=min(end,best_t+dt.timedelta(hours=8))
    while x<=hi:
        d=hour_distance(apparent_sun_ra_hours(x),target)
        if d<best_d: best_t,best_d=x,d
        x+=dt.timedelta(minutes=1)
    return best_t

def best_time_for_solar_ra(target:float,year:int)->dt.datetime:return _best_time_for_solar_ra(target,first_point_of_aries(year),first_point_of_aries(year+1))

def first_point_of_aries(year:int)->dt.datetime:return _best_time_for_solar_ra(0.0,dt.datetime(year,3,18),dt.datetime(year,3,22,23,59))

def best_visibility(ra_h:float,year:int)->tuple[dt.datetime,dt.date]:
    instant=best_time_for_solar_ra((ra_h-9.0)%24.0,year); return instant,(instant+dt.timedelta(hours=12)).date()

def iso_year_bounds(iso_year:int)->tuple[dt.date,dt.date]:
    start=dt.date.fromisocalendar(iso_year,1,1); weeks=dt.date(iso_year,12,28).isocalendar().week
    return start,dt.date.fromisocalendar(iso_year,weeks,7)

def solar_ra_occurrences_for_iso_year(target:float,iso_year:int,*,date_mode:str="utc")->list[tuple[dt.datetime,dt.date]]:
    """Return solar-RA recurrences; raw phases use their containing UTC civil date."""
    if date_mode not in {"nearest","utc"}: raise ValueError(f"Unknown date mode: {date_mode!r}")
    first,last=iso_year_bounds(iso_year); occurrences=[]; seen=set()
    for cycle_year in (iso_year-1,iso_year,iso_year+1):
        instant=best_time_for_solar_ra(target,cycle_year)
        day=(instant+dt.timedelta(hours=12)).date() if date_mode=="nearest" else instant.date()
        if first<=day<=last and day.isocalendar().year==iso_year and instant not in seen:
            occurrences.append((instant,day)); seen.add(instant)
    occurrences.sort(key=lambda item:item[0]); return occurrences

def best_visibility_occurrences_for_iso_year(ra_h:float,iso_year:int)->list[tuple[dt.datetime,dt.date]]:
    return solar_ra_occurrences_for_iso_year((ra_h-9.0)%24.0,iso_year,date_mode="nearest")

def declination_band(dec_deg:str|float)->str:
    dec=float(dec_deg)
    if not -90.0<=dec<=90.0: raise ValueError(f"Declination outside physical range: {dec}")
    if dec>=POLAR_LIMIT_DEG:return "Arctic"
    if dec>OBLIQUITY_DEG:return "Northern"
    if dec>=-OBLIQUITY_DEG:return "Tropical"
    if dec>-POLAR_LIMIT_DEG:return "Southern"
    return "Antarctic"

def season_for(d:dt.date)->str:
    md=(d.month,d.day)
    if (3,20)<=md<(6,21):return "Spring"
    if (6,21)<=md<(9,22):return "Summer"
    if (9,22)<=md<(12,21):return "Autumn"
    return "Winter"
