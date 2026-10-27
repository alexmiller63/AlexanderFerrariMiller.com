#!/usr/bin/env python3
"""Offline J2000 constellation portraits. Generated artwork; no hand-edited SVGs."""
import argparse
import csv
import html
import json
import math
from pathlib import Path

from constellation_cards import card, document, generate_collection

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "star-almanack/chart-library/constellations"
W, H = 1100, 800

def boundary(abbr):
    path = ROOT / "reference-data/iau-constellation-boundaries" / (abbr.lower() + ".txt")
    points = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split("|")
        if len(fields) < 2:
            raise ValueError(f"{path}:{number}: expected RA|Dec boundary record: {line!r}")
        ra, dec = fields[:2]
        h, m, s = map(float, ra.strip().split())
        points.append((h + m/60 + s/3600, float(dec)))
    return points

def portrait_figures():
    figures = json.loads((ROOT/"finder-geometry/martz-macrobert.json").read_text())["constellations"]
    serpent = figures.pop("Ser")
    # Component paths carry identities; resolved coordinates live in the parent paths.
    coordinates = {(v["catalog"], v["id"]): v for path in serpent["paths"] for v in path}
    for index, component in enumerate(serpent["components"], 1):
        figures[f"Ser{index}"] = {
            "name": "Serpens " + component["name"],
            "paths": [[coordinates[(v["catalog"], v["id"])] for v in path] for path in component["paths"]],
        }
    return {key: value for key, value in figures.items() if key not in {"Men", "Mic"}}


def render(abbr="Ori"):
    figure = portrait_figures()[abbr]
    border = boundary(abbr)
    paths = [[(float(v["ra_h"]),float(v["dec_deg"]),float(v.get("magnitude") or 6)) for v in p]
             for p in figure["paths"]]
    # Preserve a rectangular aspect in angular coordinates, with RA corrected for declination.
    center_dec = (min(p[1] for p in border)+max(p[1] for p in border))/2
    scale_ra = 15 * math.cos(math.radians(center_dec))
    angles = [ra for ra, dec in border]
    center_ra = math.atan2(sum(math.sin(ra*math.pi/12) for ra in angles),
                           sum(math.cos(ra*math.pi/12) for ra in angles))*12/math.pi % 24
    def unwrap(ra):
        return center_ra + ((ra-center_ra+12)%24)-12
    raw = [(unwrap(ra)*scale_ra, dec) for ra,dec in border]
    xmin,xmax = min(x for x,y in raw),max(x for x,y in raw)
    ymin,ymax = min(y for x,y in raw),max(y for x,y in raw)
    dx,dy = xmax-xmin,ymax-ymin
    xmin-=dx*.18; xmax+=dx*.18; ymin-=dy*.18; ymax+=dy*.18
    scale = min(960/(xmax-xmin), 650/(ymax-ymin))
    cx,cy = (xmin+xmax)/2,(ymin+ymax)/2
    def xy(ra,dec):
        return (W/2+(unwrap(ra)*scale_ra-cx)*scale,H/2-(dec-cy)*scale)
    def poly(points):
        return " ".join(f"{xy(a,b)[0]:.2f},{xy(a,b)[1]:.2f}" for a,b in points)
    def group(layer,parts):
        return f'<g data-atlas-layer="{layer}">'+"".join(parts)+"</g>"
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" role="img" aria-label="{html.escape(figure["name"])} constellation portrait">',
           f'<rect width="{W}" height="{H}" fill="#071527"/>',
           f'<text x="{W/2}" y="39" text-anchor="middle" font-size="27" fill="#fff">{html.escape(figure["name"])} · J2000.0</text>']
    out.append(group("boundaries",[f'<polygon points="{poly(border)}" fill="none" stroke="#8494a8" stroke-width="1.6" stroke-dasharray="5 4"/>']))
    out.append(group("figures",[f'<polyline points="{poly([(ra,dec) for ra,dec,mag in p])}" fill="none" stroke="#75aaff" stroke-width="2.8" stroke-linejoin="round"/>' for p in paths]))
    stars = {}
    for p in paths:
        for ra,dec,mag in p:
            stars[(round(ra,5),round(dec,5))] = (ra,dec,mag)
    with (ROOT/"bright-stars-2mag.csv").open(newline="") as f:
        bright = [r for r in csv.DictReader(f) if r["con"] == ("Ser" if abbr.startswith("Ser") else abbr) and (not abbr.startswith("Ser") or xmin <= unwrap(float(r["ra_h"]))*scale_ra <= xmax and ymin <= float(r["dec_deg"]) <= ymax)]
    for r in bright:
        ra,dec = float(r["ra_h"]),float(r["dec_deg"])
        stars[(round(ra,5),round(dec,5))] = (ra,dec,float(r["representative_vmax"]))
    dots=[]
    for ra,dec,mag in stars.values():
        x,y=xy(ra,dec)
        dots.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{max(1.3,5-mag*.6):.2f}" fill="#e8f3ff"/>')
    out.append(group("stars",dots))
    labels=[]
    for r in bright:
        if not r["proper"]: continue
        x,y=xy(float(r["ra_h"]),float(r["dec_deg"]))
        labels.append(f'<text x="{x+8:.1f}" y="{y-8:.1f}" fill="#e4efff" font-size="14">{html.escape(r["proper"])}</text>')
    out.append(group("names",labels))
    asterisms = json.loads((ROOT/"asterism-figure-paths.json").read_text())["asterisms"]
    coords={}
    with (ROOT/"asterism-member-coordinates.csv").open(newline="") as f:
        for row in csv.DictReader(f):
            coords[(row["asterism"],row["member"])] = (float(row["ra_h"]),float(row["dec_deg"]))
    overlays=[]
    for name,entry in asterisms.items():
        if not any(an == name and xmin <= unwrap(pt[0])*scale_ra <= xmax and ymin <= pt[1] <= ymax for (an,member),pt in coords.items()): continue
        label_points = []
        for p in entry["paths"]:
            pts=[coords.get((name,member)) for member in p]
            if any(pt is None for pt in pts): continue
            overlays.append(f'<polyline points="{poly(pts)}" fill="none" stroke="#69dc94" stroke-width="3.5"/>')
            label_points.extend(pts)
        if label_points:
            mx,my=xy(*label_points[len(label_points)//2])
            label_width = len(name) * 8.5
            lx = mx - label_width - 18 if name == "Winter Hexagon" else mx + 10
            lx = max(12, min(W - label_width - 12, lx))
            ly = max(60, min(H - 12, my + 22))
            overlays.append(f'<text x="{lx:.1f}" y="{ly:.1f}" font-size="15" fill="#69dc94">{html.escape(name)}</text>')
    out.append(group("asterisms",overlays))
    # Catalog-driven layer, deduplicated by NGC identity where available.
    catalogs = [
        ("generated/messier-visibility-2026.csv", "id"),
        ("caldwell-catalog.csv", "caldwell"),
        ("finest-ngc-catalog.csv", "catalog"),
    ]
    entries = {}
    for filename, label_field in catalogs:
        with (ROOT / filename).open(newline="") as stream:
            for row in csv.DictReader(stream):
                if row.get("con") != ("Ser" if abbr.startswith("Ser") else abbr):
                    continue
                try:
                    ra, dec = float(row["ra_h"]), float(row["dec_deg"])
                except (KeyError, ValueError, TypeError):
                    continue
                if abbr.startswith("Ser") and not (xmin <= unwrap(ra)*scale_ra <= xmax and ymin <= dec <= ymax):
                    continue
                label = row[label_field].strip()
                ngc = (row.get("ngc") or "").strip().upper()
                if ngc.isdigit():
                    ngc = "NGC " + ngc
                identity = ngc or label.upper()
                entry = entries.setdefault(identity, {"ra": ra, "dec": dec, "labels": set()})
                entry["labels"].add(label)
                if ngc:
                    entry["labels"].add(ngc)
    def priority(label):
        return (0 if label.startswith("M") and label[1:].isdigit() else
                1 if label.startswith("C") and label[1:].isdigit() else 2, label)
    objects = []
    for entry in entries.values():
        x, y = xy(entry["ra"], entry["dec"])
        labels = sorted(entry["labels"], key=priority)
        primary = labels[0]
        aliases = ", ".join(labels)
        objects.append(
            f'<g><title>{html.escape(aliases)}</title>'
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="none" stroke="#ffcc77" stroke-width="1.8"/>'
            f'<text x="{x+9:.1f}" y="{y-7:.1f}" font-size="13" fill="#ffcc77">{html.escape(primary)}</text></g>'
        )
    out.append(group("catalog", objects))
    out.append('</svg>')
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/(abbr.lower()+".svg")).write_text("\n".join(out)+"\n",encoding="utf-8")
    # Inline SVG is necessary for independent, client-side layer toggles.
    svg="\n".join(out)
    controls=[("asterisms","Asterisms",True),("boundaries","Boundaries",True),
              ("figures","Stick figures",True),("names","Named stars",True),
              ("stars","Stars",True),("catalog","Catalog objects",False)]
    toggles=" ".join(f'<label><input type="checkbox" data-atlas-toggle="{key}" {"checked" if checked else ""}> {label}</label>' for key,label,checked in controls)
    subject = "Ser" if abbr.startswith("Ser") else abbr
    editorial = card(subject, [], collection="../../constellations/", show_portraits=False)
    page = document(figure["name"] + " · Constellation Atlas",
        '<p><a href="./">← Constellation Atlas</a></p>' + editorial +
        '<nav aria-label="Chart layers">' + toggles + '</nav><div data-atlas-chart>' + svg +
        f'</div><p><a href="{abbr.lower()}.svg">Full-resolution SVG</a></p>' +
        '<script src="../atlas-toggles.js?v=8134e6a"></script>')
    (OUT/(abbr.lower()+".html")).write_text(page,encoding="utf-8")
    print(f"Generated {figure['name']} portrait")

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--constellation",default="all",help="IAU abbreviation or all")
    args=parser.parse_args()
    geometry=portrait_figures()
    available=[k for k in sorted(geometry) if (ROOT/"reference-data/iau-constellation-boundaries"/(k.lower()+".txt")).exists()]
    targets=available if args.constellation=="all" else [args.constellation]
    for abbr in targets:
        render(abbr)
    # A single-constellation pilot must not replace the complete atlas index.
    if args.constellation == "all":
        portraits = [(key, geometry[key]["name"]) for key in available]
        links = ''.join(card("Ser" if key.startswith("Ser") else key,
                             [(key, name)], collection="../../constellations/").replace('id="ser"', f'id="{key.lower()}"')
                        for key, name in portraits)
        index = document("Constellation Atlas", '<p><a href="../">Chart Library</a> · '
            '<a href="../../constellations/">All 88 constellations</a></p>'
            '<p>87 stick-figure portraits of 86 constellations, with separate views of Serpens Caput and Cauda. '
            'Mensa and Microscopium have no adopted stick figures.</p><div class="card-grid">' + links + '</div>')
        (OUT / "index.html").write_text(index, encoding="utf-8")
        generate_collection(portraits)
        library = OUT.parent / "index.html"
        library_text = library.read_text()
        library_text = library_text.replace(
            "86 of the 88 IAU constellations currently represented, with Serpens Caput and Serpens Cauda on separate charts: 87 views. Mensa and Microscopium remain to be completed.",
            "87 portraits of 86 constellations, with separate charts for Serpens Caput and Serpens Cauda. Mensa and Microscopium have no adopted stick figures.")
        if 'href="../constellations/"' not in library_text:
            library_text = library_text.replace('<section class="library-grid" aria-label="Chart Library collections">',
                '<section class="library-grid" aria-label="Chart Library collections">\n'
                '<article><h2><a href="../constellations/">Constellations</a></h2>'
                '<p>Individual Heds and Deks for all 88 constellations, with links to their portraits.</p></article>')
        library.write_text(library_text)

        # Retire the two formerly generated empty portraits.
        for excluded in ("men", "mic"):
            for extension in (".html", ".svg"):
                (OUT / (excluded + extension)).unlink(missing_ok=True)
    if args.constellation == "all":
        if len(targets) != 87:
            raise RuntimeError(f"Expected 87 constellation portraits, generated {len(targets)}")
        index_text = (OUT / "index.html").read_text(encoding="utf-8")
        if not index_text.startswith("---\nlayout: null\n---\n"):
            raise RuntimeError("Atlas index has invalid Jekyll front matter")
        for abbr in targets:
            html_path = OUT / (abbr.lower() + ".html")
            svg_path = OUT / (abbr.lower() + ".svg")
            if not html_path.is_file() or not svg_path.is_file():
                raise RuntimeError(f"Missing atlas output for {abbr}")
            page_text = html_path.read_text(encoding="utf-8")
            if '{html.escape(' in page_text or '{abbr.lower()}' in page_text:
                raise RuntimeError(f"Unexpanded template placeholder in {html_path}")
            if f'href="{abbr.lower()}.svg"' not in page_text:
                raise RuntimeError(f"Incorrect SVG link in {html_path}")
            if f'href="{abbr.lower()}.html"' not in index_text:
                raise RuntimeError(f"Missing index link for {abbr}")
    print(f"Generated {len(targets)} constellation portraits")
