"""Planet Finder SVG rendering."""
from __future__ import annotations

import html
import math
from datetime import date

from planet_finder_geometry import (
    W, H, CX, CY, RO, RI, SIGNS, BODY_SYMBOLS, BODY_NAMES,
    FinderMode, xy, label_size,
)
from planet_finder_search import layout

def polyline(points):
    pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    return f'<polyline points="{pts}" fill="none" stroke="#777" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>'


def segment_box_entry(a, b, box):
    """Return the first point where segment a->b enters the label rectangle.

    None means the segment never reaches the rectangle.  This is deliberately
    independent of which route segment was intended to be the final approach:
    rendering stops at the *first* contact with the body's own label.
    """
    x0, y0 = a
    dx = b[0] - x0
    dy = b[1] - y0
    t_enter = 0.0
    t_exit = 1.0

    for p, q in (
        (-dx, x0 - box.left),
        ( dx, box.right - x0),
        (-dy, y0 - box.top),
        ( dy, box.bottom - y0),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return None
            continue
        r = q / p
        if p < 0:
            t_enter = max(t_enter, r)
        else:
            t_exit = min(t_exit, r)
        if t_enter > t_exit:
            return None

    if t_exit < 0.0 or t_enter > 1.0:
        return None
    t = max(0.0, t_enter)
    return x0 + t * dx, y0 + t * dy


def leader_endpoint_before_box(a, hit, clearance=2.0):
    """Move a clipped leader endpoint slightly outside the label boundary.

    SVG round line caps extend beyond the mathematical endpoint.  Stopping
    exactly on the rectangle edge can therefore still paint into the label.
    Backing off by a small geometric clearance keeps the visible stroke out.
    """
    dx = hit[0] - a[0]
    dy = hit[1] - a[1]
    length = math.hypot(dx, dy)
    if length <= clearance or length < 1e-12:
        return a
    scale = (length - clearance) / length
    return a[0] + dx * scale, a[1] + dy * scale


def rendered_leader(path, box):
    """Clip a routed leader just before first contact with its own label.

    A route normally ends at the label center, but a dogleg can encounter the
    label on an earlier segment.  Clipping only the nominal final segment lets
    that earlier segment penetrate the label.  First-contact clipping plus a
    small stroke clearance keeps own-label penetration out of the rendered SVG.
    """
    if len(path) < 2:
        return path
    rendered = [path[0]]
    for a, b in zip(path, path[1:]):
        hit = segment_box_entry(a, b, box)
        if hit is not None:
            rendered.append(leader_endpoint_before_box(a, hit))
            return rendered
        rendered.append(b)
    return rendered


def render(
    year: int,
    week: int,
    monday: date,
    mode: FinderMode,
    bodies: list[tuple[str, str, float]],
    glyph_radii: dict[str, float] | None = None,
    budget: dict | None = None,
    context_label: str | None = None,
) -> str:
    mode = FinderMode(mode)
    labels = {
        FinderMode.GREEK: "Greek / Symbols",
        FinderMode.LATIN: "Latin",
        FinderMode.MIXED: "Mixed / Learner",
    }
    title = labels[mode]
    placed = layout(mode, bodies, budget=budget, context_label=context_label)
    if glyph_radii is None:
        glyph_radii = {name: RI - 5 for _, name, _ in bodies}
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
        x1, y1 = xy(i * 30, RI)
        x2, y2 = xy(i * 30, RO)
        out.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#111" stroke-width="2"/>')
    for i, (symbol, name) in enumerate(SIGNS):
        x, y = xy(i * 30 + 15, (RI + RO) / 2)
        if mode == "greek":
            text, fs = symbol + "\ufe0e", 48
        elif mode == "latin":
            text, fs = name, 24
        else:
            text, fs = f'{symbol}\ufe0e {name}', 22
        out.append(f'<text x="{x:.1f}" y="{y+10:.1f}" text-anchor="middle" font-size="{fs}">{html.escape(text)}</text>')
    # Fixed geometric annotation: 0° Aries is the 9-o'clock boundary.
    # Put the annotation beyond the outer rim, not inside the zodiac band.
    aries_x, aries_y = xy(0, RO)
    out.append(
        f'<text x="{aries_x - 28:.1f}" y="{aries_y + 7:.1f}" '
        'text-anchor="end" font-size="20" class="sans">0° Aries</text>'
    )

    # Body anchors are geometric attachment points only.  Do not render a
    # second glyph at the astronomical anchor; the visible glyph belongs to
    # the displaced label at the end of its leader.
    for symbol, name, _, box, path in placed:
        if year == 2026 and week == 1 and mode == FinderMode.MIXED:
            rendered = rendered_leader(path, box)
            print(
                "PF_TRACE W01 MIXED BODY "
                f"symbol={symbol!r} name={name!r} "
                f"box=center({box.x:.6f},{box.y:.6f}) size({box.w:.6f},{box.h:.6f}) "
                f"search_path={path!r} rendered_path={rendered!r}"
            )
        # Stop just before first contact with this label, even when a dogleg
        # reaches it before the route's nominal final approach.
        out.append(polyline(rendered_leader(path, box)))
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