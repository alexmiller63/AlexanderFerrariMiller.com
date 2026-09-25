from pathlib import Path

path = Path("tools/planet_finder_search_core.py")
text = path.read_text()

old = '''            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue
            # The inner zodiac rim is protected geometry, not a scoring
'''

new = '''            if path is None:
                rejected_route += 1
                stats["route"] += 1
                continue

            # A new leader must not cross any label already placed by DFS.
            # The opposite direction is checked earlier: a new label may not
            # cross an existing leader. Both directions are required because
            # placement order must not change collision legality.
            if any(
                segment_hits_box(path[i], path[i + 1], placed_box, 10)
                for placed_box in placed
                for i in range(len(path) - 1)
            ):
                rejected_leader += 1
                stats["leader"] += 1
                stats["leader_existing"] += 1
                continue

            # The inner zodiac rim is protected geometry, not a scoring
'''

count = text.count(old)

if count != 1:
    raise SystemExit(
        f"Safety stop: expected old block exactly once; found {count}"
    )

path.write_text(text.replace(old, new, 1))

print("Repair applied successfully.")