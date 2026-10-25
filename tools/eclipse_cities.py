"""Select nearby geographic reference cities from the site's cached gazetteer.

City markers are orientation aids only, not predicted observing locations.
GeoNames cities15000, adapted by tools/build_ephemera_browser.py, CC BY 4.0.
"""
import json
import math
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def unit(latitude, longitude):
    lat, lon = map(math.radians, (latitude, longitude))
    return math.cos(lat)*math.cos(lon), math.cos(lat)*math.sin(lon), math.sin(lat)


@lru_cache(maxsize=1)
def city_rows():
    path = ROOT / 'star-almanack/assets/ephemera/cities.json'
    rows = json.loads(path.read_text(encoding='utf-8'))
    if not rows:
        raise ValueError('Empty cached city gazetteer')
    return [(row, unit(row[3], row[4])) for row in rows]


def reference_cities(points, limit=6, radius_km=900):
    """Pick nearby, well-separated cities; do not imply central-path inclusion.

    Distances select context only. The sampled track and selected cities do
    not define a path boundary or provide local eclipse circumstances.
    """
    if not points:
        return []
    stride = max(1, math.ceil(len(points)/96))
    samples = points[::stride] + [points[-1]]
    vectors = [unit(p['latitude_deg'], p['longitude_deg']) for p in samples]
    min_dot = math.cos(radius_km/6378.137)
    candidates = []
    for row, (x, y, z) in city_rows():
        best = max(x*a+y*b+z*c for a,b,c in vectors)
        if best >= min_dot:
            candidates.append((-best, row))
    chosen = []
    boxes = []
    for _, row in sorted(candidates, key=lambda v: (v[0], v[1][0])):
        label = row[1].split(',')[0] + ', ' + row[1].rsplit(',', 1)[-1].strip()
        x = 120 + (row[4]+180)*3.2
        y = 1300 + (90-row[3])*1.6
        width = len(label)*8
        tx = max(124, min(1268-width, x+7))
        # Reserve surrounding space for the marker and label, including a
        # margin between neighbouring cities. Stay inside the plotting frame.
        ty = max(1317, min(1580, y-8))
        box = (min(x-5,tx)-8, min(y-5,ty-14)-8,
               max(x+5,tx+width)+8, max(y+5,ty+3)+8)
        if any(not (box[2]<b[0] or box[0]>b[2] or box[3]<b[1] or box[1]>b[3]) for b in boxes):
            continue
        chosen.append({'id':row[0], 'label':label, 'latitude_deg':row[3],
                       'longitude_deg':row[4], 'x':x, 'y':y, 'tx':tx, 'ty':ty})
        boxes.append(box)
        if len(chosen) == limit:
            break
    return chosen
