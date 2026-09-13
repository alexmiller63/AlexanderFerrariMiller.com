#!/usr/bin/env python3
"""Generate Star Almanack planet-finder SVGs from the canonical weekly ephemeris CSV.

Usage: python tools/generate-current-planet-finder.py 2026 37
"""
from pathlib import Path
import csv, datetime as dt, heapq, math, sys

ROOT=Path(__file__).resolve().parents[1]
SIGNS=[('♈','Aries'),('♉','Taurus'),('♊','Gemini'),('♋','Cancer'),('♌','Leo'),('♍','Virgo'),('♎','Libra'),('♏','Scorpio'),('♐','Sagittarius'),('♑','Capricorn'),('♒','Aquarius'),('♓','Pisces')]
SIGN_INDEX={s:i for i,(s,_) in enumerate(SIGNS)}
BODIES=[('☉','Sun','sun'),('☽','Moon','moon'),('☿','Mercury','mercury'),('♀','Venus','venus'),('♂','Mars','mars'),('♃','Jupiter','jupiter'),('♄','Saturn','saturn'),('♅','Uranus','uranus'),('♆','Neptune','neptune'),('⚳','Ceres','ceres')]
W=H=1400; C=700; RI=430; RO=560
CENTER_RESERVED=[(700,680,380,48),(700,722,640,40),(700,758,480,40)]

def xy(lon,r):
    t=math.radians(180+lon)
    return C+r*math.cos(t),C-r*math.sin(t)

def parse_pos(value):
    sign=value[0]
    rest=value[1:].strip().replace('′','')
    deg_s,min_s=rest.split('°')
    return sign,int(deg_s),int(min_s),SIGN_INDEX[sign]*30+int(deg_s)+int(min_s)/60

def overlap(a,b,p=14):
    ax,ay,aw,ah=a; bx,by,bw,bh=b
    return abs(ax-bx)<(aw+bw)/2+p and abs(ay-by)<(ah+bh)/2+p

def dims(mode,name):
    if mode=='symbols': return 68,68
    if mode=='latin': return max(110,14*len(name)+34),52
    return max(140,14*len(name)+74),52

def point_inside_inner_rim(point,clearance=1):
    """Keep leader geometry strictly inside the zodiac inner rim."""
    x,y=point
    return math.hypot(x-C,y-C)<=RI-clearance

def box_inside_inner_rim(box,clearance=10):
    """Require every label corner to remain inside the zodiac inner rim."""
    x,y,w,h=box
    limit=RI-clearance
    return all(math.hypot(px-C,py-C)<=limit
               for px in (x-w/2,x+w/2)
               for py in (y-h/2,y+h/2))

def place(mode,rows):
    """Place all labels with finite, bounded recursive backtracking.

    Candidate geometry is finite and precomputed. Each recursive call assigns
    exactly one previously-unassigned label, so recursion depth can never exceed
    len(rows). The next label is chosen with a minimum-remaining-values heuristic
    to expose dead ends early, while the original crowded-first ordering is used
    as a deterministic tie-breaker. A generous state budget protects CI from an
    accidental combinatorial explosion without permitting a recursion loop.
    """
    reserved=tuple(CENTER_RESERVED)
    lons=[r[-1] for r in rows]
    anchors=[xy(L,RI-5) for L in lons]
    nearest=[min(abs((lons[i]-lons[j]+180)%360-180)
                 for j in range(len(rows)) if j!=i)
             for i in range(len(rows))]
    original_order=sorted(range(len(rows)),key=lambda i:(nearest[i],lons[i]))
    priority={i:rank for rank,i in enumerate(original_order)}

    radii=(340,300,260,380,220,180)
    shifts=(0,-70,70,-120,120,-170,170)
    candidate_specs=([(r,sh) for sh in (0,-45,45,-80,80,-120,120) for r in radii]
                     if mode=='symbols' else [(r,sh) for r in radii for sh in shifts])
    label_pad=4 if mode=='symbols' else 16
    reserved_pad=8 if mode=='symbols' else 18
    anchor_pad=2 if mode=='symbols' else 10

    candidates={}
    for i,row in enumerate(rows):
        sym,name,sign,d,m,L=row; w,h=dims(mode,name)
        t=math.radians(180+L); tx=-math.sin(t); ty=-math.cos(t)
        options=[]
        for r,sh in candidate_specs:
            bx,by=xy(L,r); x=bx+sh*tx; y=by+sh*ty; box=(x,y,w,h)
            if x-w/2<300 or x+w/2>1100 or y-h/2<300 or y+h/2>1100: continue
            if mode!='symbols' and not box_inside_inner_rim(box): continue
            if any(overlap(box,q,reserved_pad) for q in reserved): continue
            if any(abs(ax-x)<=w/2+anchor_pad and abs(ay-y)<=h/2+anchor_pad
                   for ax,ay in anchors): continue
            options.append(box)
        if not options:
            raise RuntimeError(f'No statically valid label positions for {name}')
        candidates[i]=tuple(options)

    assigned={}
    search_nodes=0
    node_limit=1_000_000

    def compatible(box):
        return all(not overlap(box,q,label_pad) for q in assigned.values())

    def solve():
        nonlocal search_nodes
        search_nodes+=1
        if search_nodes>node_limit:
            raise RuntimeError(f'Label placement search exceeded {node_limit} states')
        if len(assigned)==len(rows):
            return True

        best_i=None; best_options=None
        for i in range(len(rows)):
            if i in assigned: continue
            options=[box for box in candidates[i] if compatible(box)]
            if not options:
                return False
            if (best_options is None or len(options)<len(best_options) or
                (len(options)==len(best_options) and priority[i]<priority[best_i])):
                best_i=i; best_options=options

        for box in best_options:
            assigned[best_i]=box
            if solve():
                return True
            del assigned[best_i]
        return False

    if not solve():
        raise RuntimeError(f'No collision-free label arrangement for {mode} after {search_nodes} search states')
    return [assigned[i] for i in range(len(rows))]

def edge_point(x,y,w,h,ax,ay,mode):
    dx=ax-x; dy=ay-y
    if mode=='symbols':
        dist=math.hypot(dx,dy) or 1
        return x+dx/dist*34,y+dy/dist*34
    sx=(w/2)/abs(dx) if dx else 1e9; sy=(h/2)/abs(dy) if dy else 1e9
    t=min(sx,sy); return x+dx*t,y+dy*t

def seg_hits_box(a,b,box,pad=10):
    x1,y1=a; x2,y2=b; bx,by,bw,bh=box
    xmin=bx-bw/2-pad; xmax=bx+bw/2+pad; ymin=by-bh/2-pad; ymax=by+bh/2+pad
    dx=x2-x1; dy=y2-y1; t0=0.0; t1=1.0
    for p,q in ((-dx,x1-xmin),(dx,xmax-x1),(-dy,y1-ymin),(dy,ymax-y1)):
        if abs(p)<1e-9:
            if q<0: return False
            continue
        r=q/p
        if p<0:
            if r>t1: return False
            if r>t0: t0=r
        else:
            if r<t0: return False
            if r<t1: t1=r
    return t0<=t1

def point_in_box(point,box,pad=10):
    x,y=point; bx,by,bw,bh=box
    return bx-bw/2-pad<=x<=bx+bw/2+pad and by-bh/2-pad<=y<=by+bh/2+pad

def smart_route(anchor,target_box,mode,obstacles):
    x,y,w,h=target_box; collision_pad=2 if mode=='symbols' else 10
    def end_from(point): return edge_point(x,y,w,h,point[0],point[1],mode)
    def clear_segment(a,b):
        return (point_inside_inner_rim(a) and point_inside_inner_rim(b)
                and not any(seg_hits_box(a,b,q,collision_pad) for q in obstacles))
    gap=16 if mode=='symbols' else 24
    approaches=[(x-w/2-gap,y),(x+w/2+gap,y),(x,y-h/2-gap),(x,y+h/2+gap),(x-w/2-gap,y-h/2-gap),(x+w/2+gap,y-h/2-gap),(x-w/2-gap,y+h/2+gap),(x+w/2+gap,y+h/2+gap)]
    approaches=[p for p in approaches if clear_segment(p,end_from(p))]
    if not approaches: return None
    nodes=[anchor]; goal_ids=[]
    for p in approaches: goal_ids.append(len(nodes)); nodes.append(p)
    for bx,by,bw,bh in obstacles:
        pad=collision_pad+4; xmin=bx-bw/2-pad; xmax=bx+bw/2+pad; ymin=by-bh/2-pad; ymax=by+bh/2+pad
        candidates=[(xmin,ymin),(xmax,ymin),(xmin,ymax),(xmax,ymax),((xmin+xmax)/2,ymin),((xmin+xmax)/2,ymax),(xmin,(ymin+ymax)/2),(xmax,(ymin+ymax)/2)]
        for p in candidates:
            if not point_inside_inner_rim(p): continue
            if any(point_in_box(p,q,collision_pad) for q in obstacles): continue
            nodes.append(p)
    n=len(nodes); graph=[[] for _ in range(n)]
    for i in range(n):
        for j in range(i+1,n):
            if not clear_segment(nodes[i],nodes[j]): continue
            distance=math.hypot(nodes[i][0]-nodes[j][0],nodes[i][1]-nodes[j][1])+4
            graph[i].append((j,distance)); graph[j].append((i,distance))
    goals=set(goal_ids); dist=[float('inf')]*n; prev=[None]*n; dist[0]=0.0; queue=[(0.0,0)]; found=None
    while queue:
        current_dist,i=heapq.heappop(queue)
        if current_dist!=dist[i]: continue
        if i in goals: found=i; break
        for j,cost in graph[i]:
            new_dist=current_dist+cost
            if new_dist<dist[j]: dist[j]=new_dist; prev[j]=i; heapq.heappush(queue,(new_dist,j))
    if found is None: return None
    route=[]; i=found
    while i is not None: route.append(nodes[i]); i=prev[i]
    route.reverse(); route.append(end_from(route[-1])); return route

def route_leader(anchor,target_box,L,mode,obstacles):
    """Choose a collision-free leader by balancing obstacle, rim, and detour costs."""
    x,y,w,h=target_box; collision_pad=2 if mode=='symbols' else 10
    def end_from(point): return edge_point(x,y,w,h,point[0],point[1],mode)
    def clear(points,pad=collision_pad):
        return (all(point_inside_inner_rim(p) for p in points)
                and all(not any(seg_hits_box(a,b,q,pad) for q in obstacles)
                        for a,b in zip(points,points[1:])))
    def route_length(points):
        return sum(math.hypot(b[0]-a[0],b[1]-a[1]) for a,b in zip(points,points[1:]))
    def rim_clearance(points,ignore_start=18.0):
        """Minimum inner-rim clearance after the leader has left its anchor."""
        best=float('inf'); traveled=0.0
        for a,b in zip(points,points[1:]):
            seg_len=math.hypot(b[0]-a[0],b[1]-a[1])
            steps=max(1,math.ceil(seg_len/6.0))
            for step in range(1,steps+1):
                frac=step/steps
                distance=traveled+frac*seg_len
                if distance<=ignore_start: continue
                px=a[0]+(b[0]-a[0])*frac; py=a[1]+(b[1]-a[1])*frac
                best=min(best,RI-math.hypot(px-C,py-C))
            traveled+=seg_len
        return best

    candidates=[]
    direct=[anchor,end_from(anchor)]
    if clear(direct): candidates.append(direct)

    theta=math.radians(180+L); tx=-math.sin(theta); ty=-math.cos(theta)
    for radius in (400,370,340,310,280,250,220,190,160,130):
        rx,ry=xy(L,radius)
        for shift in (0,-35,35,-70,70,-105,105,-140,140,-175,175,-210,210):
            bend=(rx+shift*tx,ry+shift*ty); route=[anchor,bend,end_from(bend)]
            if clear(route): candidates.append(route)

    if candidates:
        # Three independent aesthetic penalties: crowding another object,
        # crowding the zodiac rim after leaving the anchor, and excess detour.
        # The rim term prevents near-tangent leaders from visually merging with
        # the circle without imposing a hard route shape or a body-specific fix.
        desired_clearance=22 if mode=='symbols' else 24
        desired_rim_clearance=26
        clearance_steps=tuple(range(desired_clearance,collision_pad-1,-2))
        direct_length=route_length(direct)
        def route_score(route):
            clearance=max((pad for pad in clearance_steps if clear(route,pad)),default=collision_pad)
            clearance_penalty=max(0,desired_clearance-clearance) ** 2
            rim_deficit=max(0.0,desired_rim_clearance-rim_clearance(route))
            rim_penalty=0.75*rim_deficit**2
            detour=max(0.0,route_length(route)-direct_length)
            detour_penalty=0.12*detour
            return clearance_penalty+rim_penalty+detour_penalty
        return min(candidates,key=route_score)

    route=smart_route(anchor,target_box,mode,obstacles)
    if route: return route
    raise RuntimeError('No collision-free leader route after visibility-graph search')

def build(mode,year,week,monday,rows):
    title={'symbols':'Greek / Symbols','latin':'Latin','mixed':'Mixed / Learner'}[mode]
    date=dt.date.fromisoformat(monday); date_label=f"{date.strftime('%A, %B')} {date.day}, {date.year}"
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 1400 1400">','<rect width="100%" height="100%" fill="white"/>','<style>text{font-family:Georgia,"Times New Roman",serif;fill:#111}.sans{font-family:Arial,Helvetica,sans-serif}.symbol{font-family:"Arial Unicode MS","Segoe UI Symbol","Noto Sans Symbols 2","Apple Symbols",serif;font-variant-emoji:text;fill:#111}</style>',f'<text x="700" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO {year}-W{week:02d} Planet Finder</text>',f'<text x="700" y="110" text-anchor="middle" font-size="23">{title} · {date_label} · 00:00 UTC</text>','<circle cx="700" cy="700" r="560" fill="none" stroke="#111" stroke-width="4"/>','<circle cx="700" cy="700" r="430" fill="none" stroke="#111" stroke-width="2"/>']
    for i in range(12):
        x1,y1=xy(i*30,RI); x2,y2=xy(i*30,RO); s.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i,(sgn,name) in enumerate(SIGNS):
        x,y=xy(i*30+15,(RI+RO)/2)
        if mode=='symbols': text,fs,cls=sgn+'︎',48,' class="symbol"'
        elif mode=='latin': text,fs,cls=name,24,''
        else: text,fs,cls=sgn+'︎ '+name,22,' class="symbol"'
        s.append(f'<text{cls} x="{x:.1f}" y="{y+8:.1f}" text-anchor="middle" font-size="{fs}">{text}</text>')
    s.append('<text x="112" y="708" text-anchor="end" font-size="20" class="sans">0° Aries</text>')
    boxes=place(mode,rows)
    for idx,(row,box) in enumerate(zip(rows,boxes)):
        sym,name,sign,d,m,L=row; ax,ay=xy(L,RI-5); obstacles=list(CENTER_RESERVED)+[q for j,q in enumerate(boxes) if j!=idx]
        route=route_leader((ax,ay),box,L,mode,obstacles); points=' '.join(f'{px:.1f},{py:.1f}' for px,py in route)
        s.append(f'<polyline points="{points}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'); s.append(f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="3.5" fill="#111"/>')
    for row,box in zip(rows,boxes):
        sym,name,sign,d,m,L=row; x,y,w,h=box
        if mode=='symbols':
            s.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="34" fill="white" stroke="#111" stroke-width="1.5"/>'); s.append(f'<text class="symbol" x="{x:.1f}" y="{y+14:.1f}" text-anchor="middle" font-size="46">{sym}︎</text>')
        else:
            label=name if mode=='latin' else sym+'︎ '+name; cls=' class="symbol"' if mode=='mixed' else ''
            s.append(f'<rect x="{x-w/2:.1f}" y="{y-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="10" fill="white" stroke="#111" stroke-width="1.5"/>'); s.append(f'<text{cls} x="{x:.1f}" y="{y+7:.1f}" text-anchor="middle" font-size="{18 if mode=="latin" else 17}">{label}</text>')
    s += ['<text x="700" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>','<text x="700" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>','<text x="700" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>','</svg>']; return '\n'.join(s)

def main():
    year=int(sys.argv[1]); week=int(sys.argv[2]); key=f'{year}-W{week:02d}'; csv_path=ROOT/'Star-Almanack-Repo'/f'weekly-ephemeris-{year}.csv'
    with csv_path.open(encoding='utf-8',newline='') as f: row=next((r for r in csv.DictReader(f) if r['iso_week']==key),None)
    if not row: raise SystemExit(f'{key} not found in {csv_path}')
    parsed=[]
    for sym,name,col in BODIES:
        sign,d,m,L=parse_pos(row[col]); parsed.append((sym,name,sign,d,m,L))
    out=ROOT/'almanack'/str(year)/f'W{week:02d}'/'finders'; out.mkdir(parents=True,exist_ok=True)
    for mode,fn in [('symbols','planet-finder-greek-symbols.svg'),('latin','planet-finder-latin.svg'),('mixed','planet-finder-mixed-learner.svg')]: (out/fn).write_text(build(mode,year,week,row['monday_utc'],parsed),encoding='utf-8')
    print(f'Generated collision-safe Planet Finder for {key}')

if __name__=='__main__': main()
