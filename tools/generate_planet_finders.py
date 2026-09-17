#!/usr/bin/env python3
"""Generate canonical weekly Planet Finder SVGs from Star Almanack calculations.

The renderer follows the frozen Planet Finder specification. It consumes the
same internally calculated planetary positions as the weekly ephemeris and does
not query Horizons or another answer service.
"""
from __future__ import annotations

import argparse
import html
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from populate_ephemeris import TARGETS, computed_ephemeris, week_count
from star_almanack_ephemeris import StarAlmanackEphemeris

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
    "sun": "☉", "moon": "☾", "mercury": "☿", "venus": "♀", "mars": "♂",
    "jupiter": "♃", "saturn": "♄", "uranus": "♅", "neptune": "♆",
    "ceres": "⚳", "pluto": "♇",
}
CANONICAL = ["Sun", "Moon", "Mercury", "Venus", "Mars", "Jupiter", "Saturn", "Ceres", "Uranus", "Neptune", "Pluto"]

@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float


def xy(lon: float, radius: float):
    a = math.radians(lon - 90)
    return CX + radius * math.cos(a), CY + radius * math.sin(a)


def boxes_overlap(a: Box, b: Box, pad: float = 0):
    return not (a.x + a.w / 2 + pad <= b.x - b.w / 2 or
                a.x - a.w / 2 - pad >= b.x + b.w / 2 or
                a.y + a.h / 2 + pad <= b.y - b.h / 2 or
                a.y - a.h / 2 - pad >= b.y + b.h / 2)


def segment_hits_box(a, b, box: Box, pad: float = 0):
    xmin, xmax = box.x - box.w / 2 - pad, box.x + box.w / 2 + pad
    ymin, ymax = box.y - box.h / 2 - pad, box.y + box.h / 2 + pad
    dx, dy = b[0] - a[0], b[1] - a[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, a[0] - xmin), (dx, xmax - a[0]), (-dy, a[1] - ymin), (dy, ymax - a[1])):
        if p == 0:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            if r < t0:
                return False
            t1 = min(t1, r)
    return True


def candidate_positions(longitude):
    bx, by = xy(longitude, RI - 70)
    tx, ty = math.cos(math.radians(longitude)), math.sin(math.radians(longitude))
    shifts = (0, -28, 28, -56, 56, -84, 84, -112, 112, -140, 140, -168, 168)
    preferred_radii = (300, 280, 320, 260, 340, 240, 360, 220, 380, 200, 400, 180, 160, 140, 120, 100)
    seen = set()

    def offer(radii, shifts):
        for r in radii:
            for shift in shifts:
                x, y = bx + shift * tx, by + shift * ty
                key = (round(x * 10), round(y * 10))
                if key not in seen:
                    seen.add(key)
                    yield x, y

    yield from offer(preferred_radii, shifts)
    expanded_radii = tuple(range(400, 79, -20))
    expanded_shifts = (0,) + tuple(v for n in range(28, 337, 28) for v in (-n, n))
    yield from offer(expanded_radii, expanded_shifts)


def route(anchor: tuple[float, float], center: tuple[float, float], obstacles: list[Box]):
    """Prefer a straight leader; otherwise try deterministic radial elbows."""
    if all(not segment_hits_box(anchor, center, b, 8) for b in obstacles):
        return [anchor, center]
    ax, ay = anchor
    for r in (395, 365, 335, 305, 275, 245, 215, 185, 155):
        lon = math.degrees(math.atan2(-(ay - CY), ax - CX)) - 180
        ex, ey = xy(lon, r)
        if all(not segment_hits_box(anchor, (ex, ey), b, 8) for b in obstacles) and all(not segment_hits_box((ex, ey), center, b, 8) for b in obstacles):
            return [anchor, (ex, ey), center]
    return None


def _solve_order(mode: str, bodies, order):
    """Solve one complete placement pass in the supplied body order."""
    reserved = reserved_boxes(mode)
    staged = {}
    placed: list[Box] = []
    leaders: list[list[tuple[float, float]]] = []
    nodes = 0
    max_nodes = 1_000_000

    def solve(position: int) -> bool:
        nonlocal nodes
        nodes += 1
        if nodes > max_nodes:
            raise RuntimeError(
                f"Planet Finder search budget exhausted in {mode} mode "
                f"starting with {order[0][1][1]} after {max_nodes:,} recursive nodes"
            )
        if position == len(order):
            return True

        original_index, (symbol, name, longitude) = order[position]
        w, h = label_size(mode, name)
        anchor = xy(longitude, RI - 5)

        for x, y in candidate_positions(longitude):
            box = Box(x, y, w, h)
            if any(boxes_overlap(box, b, 14) for b in reserved + placed):
                continue
            if any(segment_hits_box(seg[i], seg[i + 1], box, 10) for seg in leaders for i in range(len(seg) - 1)):
                continue
            path = route(anchor, (x, y), reserved + placed)
            if path is None:
                continue

            placed.append(box)
            leaders.append(path)
            staged[original_index] = (symbol, name, longitude, box, path)
            if solve(position + 1):
                return True
            del staged[original_index]
            leaders.pop()
            placed.pop()
        return False

    solved = solve(0)
    if not solved:
        return False, None
    return True, [staged[i] for i in range(len(bodies))]


def layout(mode: str, bodies: list[tuple[str, str, float]]):
    """Find a collision-free layout, rotating the starting body after failure."""
    canonical_index = {name: i for i, name in enumerate(CANONICAL)}
    indexed = list(enumerate(bodies))
    indexed.sort(key=lambda item: canonical_index[item[1][1]])

    if len(indexed) != len(CANONICAL):
        raise RuntimeError(f"Planet Finder body set has {len(indexed)} bodies; expected {len(CANONICAL)}")
    if {name for _, (_, name, _) in indexed} != set(CANONICAL):
        raise RuntimeError("Planet Finder body set does not match the canonical Solar-System objects")

    for start in range(len(indexed)):
        order = indexed[start:] + indexed[:start]
        print(f"Planet Finder {mode}: starting search with {order[0][1][1]}", flush=True)
        solved, result = _solve_order(mode, bodies, order)
        if solved:
            print(f"Planet Finder {mode}: solved with {order[0][1][1]} first", flush=True)
            return result
        print(f"Planet Finder {mode}: no solution with {order[0][1][1]} first", flush=True)

    raise RuntimeError(f"No collision-free Planet Finder layout exists in {mode} mode after trying every starting body")
