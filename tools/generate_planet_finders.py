#!/usr/bin/env python3
"""Generate canonical weekly Planet Finder SVGs from the exact JPL ephemeris.

The renderer follows the frozen Planet Finder specification. It uses the same
JPL Horizons source as tools/populate_ephemeris.py, preserves each body's exact
tropical ecliptic longitude at the leader-line anchor, and deterministically
places labels so that labels do not overlap one another, zodiac labels, center
text, or existing leader lines.
"""
from __future__ import annotations

import argparse
import html
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from populate_ephemeris import TARGETS, horizons_ephemeris, week_count

ROOT = Path(__file__).resolve().parents[1]
W = H = 1400
CX = CY = 700
RO = 560
RI = 430
SIGNS = [
    ("♈", "Aries"), ("♉", "Taurus"), ("♊", "Gemini"), ("♋", "Cancer"),
    ("♌", "Leo"), ("♍", "Virgo"), ("♎", "Libra"), ("♏", "Scorpio"),
    ("♐", "Sagittarius"), ("♑", "Capricorn"), ("♒", "Aquarius"), ("♓", "Pisces"),
]
BODY_SYMBOLS = {
    "sun": "☉", "moon": "☽", "mercury": "☿", "venus": "♀", "mars": "♂",
    "jupiter": "♃", "saturn": "♄", "uranus": "♅", "neptune": "♆", "ceres": "⚳",
}
BODY_NAMES = {display.split(" ", 1)[1]: key for display, key, _ in TARGETS}
CANONICAL = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune", "Ceres"]


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self): return self.x - self.w / 2
    @property
    def right(self): return self.x + self.w / 2
    @property
    def top(self): return self.y - self.h / 2
    @property
    def bottom(self): return self.y + self.h / 2


def xy(longitude: float, radius: float) -> tuple[float, float]:
    theta = math.radians(180 + longitude)
    return CX + radius * math.cos(theta), CY - radius * math.sin(theta)


def boxes_overlap(a: Box, b: Box, pad: float = 0) -> bool:
    return not (
        a.right + pad <= b.left or b.right + pad <= a.left or
        a.bottom + pad <= b.top or b.bottom + pad <= a.top
    )


def point_in_box(x: float, y: float, b: Box, pad: float = 0) -> bool:
    return b.left - pad <= x <= b.right + pad and b.top - pad <= y <= b.bottom + pad


def segment_hits_box(a: tuple[float, float], b: tuple[float, float], box: Box, pad: float = 0) -> bool:
    # Liang-Barsky segment/rectangle clipping.
    x0, y0 = a; x1, y1 = b
    left, right = box.left - pad, box.right + pad
    top, bottom = box.top - pad, box.bottom + pad
    dx, dy = x1 - x0, y1 - y0
    p = (-dx, dx, -dy, dy)
    q = (x0 - left, right - x0, y0 - top, bottom - y0)
    u1, u2 = 0.0, 1.0
    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0: return False
            continue
        t = qi / pi
        if pi < 0:
            if t > u2: return False
            u1 = max(u1, t)
        else:
            if t < u1: return False
            u2 = min(u2, t)
    return True


def label_size(mode: str, name: str) -> tuple[float, float]:
    if mode == "greek":
        return 64, 64
    if mode == "latin":
        return max(104, 13 * len(name) + 28), 50
    return max(132, 13 * len(name) + 68), 50


def reserved_boxes(mode: str) -> list[Box]:
    boxes = [Box(CX, 682, 520, 40), Box(CX, 722, 690, 34), Box(CX, 757, 440, 34)]
    for i, (_, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek":
            boxes.append(Box(x, y, 66, 66))
        elif mode == "latin":
            boxes.append(Box(x, y, max(92, 14 * len(name)), 46))
        else:
            boxes.append(Box(x, y, max(122, 14 * len(name) + 45), 46))
    return boxes


def candidate_positions(longitude: float):
    radii = (345, 300, 255, 210, 390, 165, 120)
    shifts = (0, -42, 42, -84, 84, -126, 126, -168, 168, -210, 210)
    theta = math.radians(180 + longitude)
    tx, ty = -math.sin(theta), -math.cos(theta)
    for r in radii:
        bx, by = xy(longitude, r)
        for shift in shifts:
            yield bx + shift * tx, by + shift * ty


def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box]) -> list[tuple[float, float]] | None:
    # Prefer a straight leader; otherwise try deterministic radial elbows.
    if all(not segment_hits_box(anchor, center, b, 8) for b in obstacles):
        return [anchor, center]
    ax, ay = anchor
    for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
        # radial elbow shares the anchor longitude
        lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
        ex, ey = xy(lon, r)
        if all(not segment_hits_box(anchor, (ex, ey), b, 8) for b in obstacles) and all(not segment_hits_box((ex, ey), center, b, 8) for b in obstacles):
            return [anchor, (ex, ey), center]
    return None


def layout(mode: str, bodies: list[tuple[str, str, float]]):
    reserved = reserved_boxes(mode)
    placed: list[Box] = []
    leaders: list[list[tuple[float, float]]] = []
    result = []

    # Densest neighborhoods first, then canonical order, makes the greedy layout stable.
    def crowd(item):
        _, _, lon = item
        return -sum(1 for _, _, other in bodies if other != lon and min((lon-other) % 360, (other-lon) % 360) < 18)
    ordered = sorted(enumerate(bodies), key=lambda p: (crowd(p[1]), p[0]))

    staged = {}
    for original_index, (symbol, name, longitude) in ordered:
        w, h = label_size(mode, name)
        anchor = xy(longitude, RI - 5)
        chosen = None
        for x, y in candidate_positions(longitude):
            box = Box(x, y, w, h)
            if any(boxes_overlap(box, b, 14) for b in reserved + placed):
                continue
            if any(segment_hits_box(seg[i], seg[i+1], box, 10) for seg in leaders for i in range(len(seg)-1)):
                continue
            path = route(anchor, (x, y), reserved + placed)
            if path is None:
                continue
            chosen = (box, path)
            break
        if chosen is None:
            raise RuntimeError(f"No collision-free Planet Finder placement for {name} at {longitude:.6f}° in {mode} mode")
        box, path = chosen
        placed.append(box); leaders.append(path)
        staged[original_index] = (symbol, name, longitude, box, path)
    return [staged[i] for i in range(len(bodies))]


def polyline(points):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'


def render(year: int, week: int, monday: date, mode: str, bodies: list[tuple[str, str, float]]) -> str:
    labels = {"greek": "Greek / Symbols", "latin": "Latin", "mixed": "Mixed / Learner"}
    title = labels[mode]
    placed = layout(mode, bodies)
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="1400" viewBox="0 0 {W} {H}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<style>text{font-family:Georgia,"Times New Roman",serif;fill:#111!important;color:#111!important;-webkit-text-fill-color:#111!important}.sans{font-family:Arial,Helvetica,sans-serif}</style>',
        f'<text x="{CX}" y="72" text-anchor="middle" font-size="38" font-weight="700">ISO {year}-W{week:02d} Planet Finder</text>',
        f'<text x="{CX}" y="110" text-anchor="middle" font-size="23">{title} · Monday, {monday.strftime("%B")} {monday.day}, {year} · 00:00 UTC</text>',
        f'<circle cx="{CX}" cy="{CY}" r="{RO}" fill="none" stroke="#111" stroke-width="4"/>',
        f'<circle cx="{CX}" cy="{CY}" r="{RI}" fill="none" stroke="#111" stroke-width="2"/>',
    ]
    for i in range(12):
        x1, y1 = xy(i * 30, RI); x2, y2 = xy(i * 30, RO)
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i, (symbol, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek": text, fs = symbol + "\ufe0e", 48
        elif mode == "latin": text, fs = name, 24
        else: text, fs = f'{symbol}\ufe0e {name}', 22
        out.append(f'<text x="{x:.1f}" y="{y+10:.1f}" text-anchor="middle" font-size="{fs}">{html.escape(text)}</text>')
    out.append('<text x="250" y="708" text-anchor="end" font-size="20" class="sans">0° Aries</text>')

    for symbol, name, _, box, path in placed:
        out.append(polyline(path))
        if mode == "greek":
            out.append(f'<circle cx="{box.x:.1f}" cy="{box.y:.1f}" r="29" fill="white" stroke="#111"/>')
            out.append(f'<text x="{box.x:.1f}" y="{box.y+13:.1f}" text-anchor="middle" font-size="44">{html.escape(symbol)}\ufe0e</text>')
        else:
            text = name if mode == "latin" else f"{symbol}\ufe0e {name}"
            out.append(f'<rect x="{box.left:.1f}" y="{box.top:.1f}" width="{box.w:.1f}" height="{box.h:.1f}" rx="10" fill="white" stroke="#111"/>')
            out.append(f'<text x="{box.x:.1f}" y="{box.y+7:.1f}" text-anchor="middle" font-size="18">{html.escape(text)}</text>')

    out.extend([
        f'<text x="{CX}" y="682" text-anchor="middle" font-size="28" font-weight="700">Tropical ecliptic longitude</text>',
        f'<text x="{CX}" y="722" text-anchor="middle" font-size="22">0° Aries at 9:00 · zodiac increases counterclockwise</text>',
        f'<text x="{CX}" y="757" text-anchor="middle" font-size="22">12 equal sectors · 30° each</text>',
        '</svg>',
    ])
    return "\n".join(out) + "\n"


def generate_week(year: int, week: int):
    if not 1 <= week <= week_count(year):
        raise ValueError(f"Invalid ISO week {year}-W{week:02d}")
    monday = date.fromisocalendar(year, week, 1)
    needed = {BODY_NAMES[name] for name in CANONICAL}
    values = {}
    for display, key, command in TARGETS:
        if key in needed:
            print(f"Fetching {year} {key} from JPL Horizons")
            values[key] = horizons_ephemeris(year, command)[week - 1][0]
    bodies = [(BODY_SYMBOLS[BODY_NAMES[name]], name, values[BODY_NAMES[name]] % 360) for name in CANONICAL]
    outdir = ROOT / "almanack" / str(year) / f"W{week:02d}" / "finders"
    outdir.mkdir(parents=True, exist_ok=True)
    filenames = {"greek": "planet-finder-greek-symbols.svg", "latin": "planet-finder-latin.svg", "mixed": "planet-finder-mixed-learner.svg"}
    for mode, filename in filenames.items():
        (outdir / filename).write_text(render(year, week, monday, mode, bodies), encoding="utf-8")
    print(f"Generated collision-free Planet Finders for ISO {year}-W{week:02d}")


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--current", action="store_true", help="generate the current UTC ISO week")
    g.add_argument("--year", type=int, help="ISO week-year")
    p.add_argument("--week", type=int, help="ISO week number; required with --year")
    args = p.parse_args()
    if args.year is not None and args.week is None:
        p.error("--week is required with --year")
    return args


def main():
    args = parse_args()
    if args.current:
        today = date.today(); iso = today.isocalendar(); year, week = iso.year, iso.week
    else:
        year, week = args.year, args.week
    generate_week(year, week)


if __name__ == "__main__":
    main()
