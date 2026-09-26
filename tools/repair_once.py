from pathlib import Path

ENABLED = False

if not ENABLED:
    print("Repair Once is OFF; nothing to do.")
    raise SystemExit(0)

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()
start = text.index("        # Snapshot only geometry frozen before this conjunction.")
end = text.index("    forward_stats =", start)
old = text[start:end]
new = '''        # Build the whole conjunction directly rather than asking the ordinary
        # recursive candidate generator to place its members independently.
        group_rows = []
        for original_index, (symbol, name, longitude) in group_items:
            gx, gy = xy(longitude, glyph_radii[name])
            w, h = label_size(mode, name)
            label_radius = max(80.0, glyph_radii[name] - 92.0)
            lx, ly = xy(longitude, label_radius)
            box = Box(lx, ly, w, h)
            leader = [(gx, gy), (lx, ly)]
            group_rows.append((original_index, symbol, name, longitude, box, leader))

        # Commit the complete conjunction at once. It now becomes fixed
        # collision geometry for every remaining recursive body.
        for original_index, symbol, name, longitude, box, leader in group_rows:
            placed.append(box)
            leaders.append(leader)
            leader_names.append(name)
            staged[original_index] = (symbol, name, longitude, box, leader)
            diagnostic_print(
                f"Planet Finder {mode}: FIXED CONJUNCTION PLACED body={name} "
                f"lambda={longitude % 360.0:.3f}deg radius={glyph_radii[name]:.1f}",
                flush=True,
            )

'''
path.write_text(text[:start] + new + text[end:])
print("Conjunctions now use direct deterministic geometry and then freeze as collisions.")
