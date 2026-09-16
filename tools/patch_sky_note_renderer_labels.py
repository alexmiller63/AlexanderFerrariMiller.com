#!/usr/bin/env python3
from pathlib import Path

p = Path('tools/render_sky_note_finder.py')
s = p.read_text(encoding='utf-8')

s = s.replace(
    'from render_stellar_finders import load_hyg, marker_area, project, spherical_center, star_index',
    'from render_stellar_finders import greek_bayer_symbol, load_hyg, marker_area, project, spherical_center, star_index'
)

needle = '''def refs_from_paths(paths):\n    return {ref for path in paths for ref in path}\n\n\n'''
insert = '''def refs_from_paths(paths):\n    return {ref for path in paths for ref in path}\n\n\ndef bayer_label(star, figure_constellation):\n    label = greek_bayer_symbol(star.bayer) if star.bayer else ""\n    if label and star.con and star.con != figure_constellation:\n        label += f" {star.con}"\n    return label\n\n\n'''
if needle not in s:
    raise SystemExit('refs_from_paths insertion point not found')
s = s.replace(needle, insert, 1)

needle = '''    for path in figure_paths:\n        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.7)\n    for asterism in asterisms:\n'''
insert = '''    for path in figure_paths:\n        draw_path(ax, path, idx, center, FIGURE_BLUE, 2.7)\n\n    figure_refs = []\n    seen = set()\n    for path in figure_paths:\n        for ref in path:\n            if ref not in seen:\n                seen.add(ref)\n                figure_refs.append(ref)\n    figure_stars = [idx[ref] for ref in figure_refs]\n    figure_constellation = spec.get("name") or ""\n\n    figure_points = []\n    for star in figure_stars:\n        point = project(star.ra_deg, star.dec_deg, *center)\n        if point is None:\n            continue\n        figure_points.append(point)\n        label = bayer_label(star, figure_constellation)\n        if label:\n            ax.annotate(label, point, xytext=(5, 5), textcoords="offset points",\n                        fontsize=8, color=TEXT, zorder=6)\n\n    if figure_constellation and figure_points:\n        ax.text(sum(x for x, _ in figure_points) / len(figure_points),\n                sum(y for _, y in figure_points) / len(figure_points),\n                figure_constellation, color=FIGURE_BLUE, fontsize=10,\n                ha="center", va="center", zorder=5)\n\n    for asterism in asterisms:\n'''
if needle not in s:
    raise SystemExit('figure insertion point not found')
s = s.replace(needle, insert, 1)

needle = '''    ax.text(\n        0.5,\n        -0.035,\n        "East ←                                      → West",\n        transform=ax.transAxes,\n        ha="center",\n        va="top",\n        fontsize=8,\n        color=TEXT,\n    )\n'''
insert = needle + '''    legend = []\n    for star in figure_stars:\n        designation = bayer_label(star, figure_constellation)\n        if designation:\n            legend.append(f"{designation} — {star.proper}" if star.proper else designation)\n    if legend:\n        ax.text(0.5, -0.075, "   •   ".join(legend), transform=ax.transAxes,\n                ha="center", va="top", fontsize=7, color=TEXT, wrap=True)\n'''
if needle not in s:
    raise SystemExit('legend insertion point not found')
s = s.replace(needle, insert, 1)

s = s.replace('    fig.tight_layout()\n', '    fig.tight_layout(rect=(0, 0.08, 1, 1))\n', 1)
p.write_text(s, encoding='utf-8')
print(f'patched {p}')
